"""API contract tests for VayuDRISHTI.

The field-presence assertions in this module are deliberate regression guards.
An earlier revision of the Pydantic response models omitted several engine
outputs, so FastAPI silently discarded them and the dashboard never received
`error_prone_areas`, `historical_error_context`,
`weather_event_classification` or `reliability_flag`. Pydantic does not warn
about undeclared response fields, so the contract is asserted explicitly here.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)

ADVISORY_MARKERS = ("BUST RISK", "ELEVATED UNCERTAINTY", "NOMINAL CONFIDENCE")


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert data["model_ready"] is True


def test_health_telemetry():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert data["telemetry_state"] == "NOMINAL_GREEN"
    assert data["model_ready"] is True
    assert data["nwp_model_base"] == settings.NWP_MODEL_BASE


@pytest.mark.parametrize("lead", [1, 5, 10])
def test_forecast_grid_lead_days(lead):
    response = client.get(f"/api/v1/forecast-grid?lead_day={lead}")
    assert response.status_code == 200
    data = response.json()
    assert data["lead_day"] == lead
    assert data["lead_hour"] == lead * 24
    assert len(data["grid_cells"]) >= 20

    cell = data["grid_cells"][0]
    assert 0.0 <= cell["bust_probability"] <= 1.0
    assert 0.0 <= cell["bust_risk_score"] <= 1.0
    assert cell["risk_level"] in ["LOW", "MODERATE", "HIGH"]
    assert 0.0 <= cell["confidence_percentage"] <= 100.0
    assert len(cell["top_atmospheric_drivers"]) <= 3


def test_confidence_is_complement_of_bust_probability():
    data = client.get("/api/v1/forecast-grid?lead_day=4").json()
    for cell in data["grid_cells"]:
        expected = (1.0 - cell["bust_probability"]) * 100.0
        assert abs(cell["confidence_percentage"] - expected) < 0.11


def test_forecast_grid_exposes_error_prone_areas():
    """Expected outcome 3 must survive serialisation."""
    data = client.get("/api/v1/forecast-grid?lead_day=3").json()
    assert "error_prone_areas" in data
    assert isinstance(data["error_prone_areas"], list)
    assert len(data["error_prone_areas"]) == data["domain_telemetry"]["error_prone_cells"]

    for area in data["error_prone_areas"]:
        assert area["risk_level"] in ["LOW", "MODERATE", "HIGH"]
        assert area["reliability_flag"] in (
            "RELIABLE",
            "ELEVATED_UNCERTAINTY",
            "ERROR_PRONE",
        )
        assert area["historical_comparison_signal"] in (
            "ANOMALOUSLY_ELEVATED",
            "CONSISTENT_WITH_ARCHIVE",
            "BELOW_ARCHIVE_AVERAGE",
        )
        assert area["hist_bust_freq_pct"] > 0.0
        assert area["expected_precip_error_mm"] > 0.0

    # Sorted worst-first for the dashboard list.
    probabilities = [a["bust_probability"] for a in data["error_prone_areas"]]
    assert probabilities == sorted(probabilities, reverse=True)


def test_forecast_grid_cells_expose_historical_context_and_flag():
    data = client.get("/api/v1/forecast-grid?lead_day=2").json()
    for cell in data["grid_cells"]:
        assert "historical_error_context" in cell
        assert "reliability_flag" in cell
        context = cell["historical_error_context"]
        assert context["archive_samples"] > 0
        assert 0.0 <= context["hist_bust_frequency_pct"] <= 100.0
        assert context["historical_comparison_signal"] in (
            "ANOMALOUSLY_ELEVATED",
            "CONSISTENT_WITH_ARCHIVE",
            "BELOW_ARCHIVE_AVERAGE",
        )
        assert context["archive_provenance"]


def test_lead_time_beyond_bounds_is_rejected():
    assert client.get("/api/v1/forecast-grid?lead_day=0").status_code == 422
    assert client.get("/api/v1/forecast-grid?lead_day=11").status_code == 422


def test_lead_time_profile_covers_full_horizon():
    data = client.get("/api/v1/lead-time-profile").json()
    assert data["lead_day_range"] == [1, 10]
    assert [e["lead_day"] for e in data["domain_profile"]] == list(range(1, 11))
    assert len(data["regions"]) >= 20

    for region in data["regions"]:
        assert [p["lead_day"] for p in region["series"]] == list(range(1, 11))
        assert 1 <= region["peak_lead_day"] <= 10


def test_lead_time_profile_is_monotonically_degrading():
    """Forecast skill must decay with lead time, not improve."""
    profile = client.get("/api/v1/lead-time-profile").json()["domain_profile"]
    probabilities = [e["mean_bust_probability"] for e in profile]
    assert probabilities[-1] > probabilities[0], "risk did not grow with lead time"
    # Allow small non-monotonic wobble from per-cell noise, but demand growth.
    assert probabilities[-1] - probabilities[0] > 0.25

    errors = [e["mean_expected_precip_error_mm"] for e in profile]
    assert errors[-1] > errors[0]


def test_explain_bust_endpoint():
    response = client.post(
        "/api/v1/explain-bust",
        json={"grid_id": "IND-E-16", "lead_day": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["grid_id"] == "IND-E-16"
    assert "Odisha" in data["name"]
    assert 0.0 <= data["bust_probability"] <= 1.0
    assert 0.0 <= data["bust_risk_score"] <= 1.0
    assert data["reliability_flag"] in (
        "RELIABLE",
        "ELEVATED_UNCERTAINTY",
        "ERROR_PRONE",
    )
    assert len(data["shap_attributions"]) > 0
    assert any(marker in data["operational_advisory"] for marker in ADVISORY_MARKERS)


def test_explain_bust_exposes_xai_and_history():
    data = client.post(
        "/api/v1/explain-bust",
        json={"grid_id": "IND-NE-11", "lead_day": 5},
    ).json()

    assert "weather_event_classification" in data
    assert data["weather_event_classification"]["event_type"]
    assert "historical_error_context" in data
    assert data["historical_error_context"]["archive_samples"] > 0
    assert "model_metadata" in data
    assert data["model_metadata"]["ready"] is True
    assert data["model_metadata"]["held_out_skill"]["roc_auc"] > 0.5
    assert isinstance(data["ai_synoptic_briefing"], (str, type(None)))


def test_explain_bust_shap_additivity():
    """Exact Shapley values must reconstruct the prediction from the baseline.

    `shap_base_value` is the v(empty set) term, so a consumer can verify the
    decomposition without trusting the server.
    """
    data = client.post(
        "/api/v1/explain-bust",
        json={"grid_id": "IND-S-14", "lead_day": 6},
    ).json()
    assert "shap_base_value" in data
    shap_sum = sum(a["shap_value"] for a in data["shap_attributions"])
    residual = data["shap_base_value"] + shap_sum - data["bust_probability"]
    assert abs(residual) < 0.01, residual


def test_explain_bust_custom_features_shift_risk():
    """A high-instability sounding must raise risk versus a quiescent one."""
    baseline = client.post(
        "/api/v1/explain-bust",
        json={"grid_id": "IND-W-12", "lead_day": 7},
    ).json()

    unstable = client.post(
        "/api/v1/explain-bust",
        json={
            "grid_id": "IND-W-12",
            "lead_day": 7,
            "custom_features": {
                "cape_j_kg": 5900.0,
                "precipitable_water_mm": 89.0,
                "wind_shear_divergence": 17.5,
                "rh_700_pct": 98.0,
                "nwp_forecast_precip_mm": 180.0,
                "ensemble_spread_std": 40.0,
            },
        },
    ).json()

    quiescent = client.post(
        "/api/v1/explain-bust",
        json={
            "grid_id": "IND-W-12",
            "lead_day": 7,
            "custom_features": {
                "cape_j_kg": 0.0,
                "precipitable_water_mm": 6.0,
                "wind_shear_divergence": 1.0,
                "rh_700_pct": 28.0,
                "nwp_forecast_precip_mm": 0.0,
                "ensemble_spread_std": 1.0,
            },
        },
    ).json()

    assert unstable["bust_probability"] > baseline["bust_probability"]
    assert quiescent["bust_probability"] < baseline["bust_probability"]
    assert unstable["observed_features"]["cape_j_kg"] == 5900.0
    assert quiescent["observed_features"]["cape_j_kg"] == 0.0


def test_explain_bust_rejects_out_of_range_custom_features():
    data = client.post(
        "/api/v1/explain-bust",
        json={
            "grid_id": "IND-W-12",
            "lead_day": 2,
            "custom_features": {
                "precipitable_water_mm": 500.0,  # above physical limit of 90 mm
                "geopotential_anomaly_m": -900.0,  # below limit of -120 m
                "not_a_feature": 3.0,
            },
        },
    ).json()
    assert set(data["ignored_custom_features"]) == {
        "precipitable_water_mm",
        "geopotential_anomaly_m",
        "not_a_feature",
    }
    # The rejected values must not be echoed back as if they had been applied.
    assert data["observed_features"]["precipitable_water_mm"] <= 90.0
    assert data["observed_features"]["geopotential_anomaly_m"] >= -120.0


def test_explain_bust_rejects_non_numeric_custom_features():
    response = client.post(
        "/api/v1/explain-bust",
        json={
            "grid_id": "IND-W-12",
            "lead_day": 2,
            "custom_features": {"cape_j_kg": "not-a-number"},
        },
    )
    assert response.status_code == 422


def test_explain_bust_unknown_region_is_labelled_ad_hoc():
    """Unregistered ids are supported for what-if analysis but must say so."""
    response = client.post(
        "/api/v1/explain-bust",
        json={"grid_id": "ADHOC-99", "lead_day": 1},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["grid_id"] == "ADHOC-99"
    assert "Ad-Hoc" in payload["name"]
    assert 0.0 <= payload["bust_probability"] <= 1.0


def test_explain_bust_lead_day_validation():
    response = client.post(
        "/api/v1/explain-bust", json={"grid_id": "IND-E-16", "lead_day": 42}
    )
    assert response.status_code == 422


def test_model_info_reports_provenance_and_skill():
    data = client.get("/api/v1/model-info").json()
    assert data["ready"] is True
    assert "HistGradientBoosting" in data["algorithm"]
    assert "Shapley" in data["attribution_method"]
    assert len(data["feature_names"]) == 13
    assert data["bust_definition"]["error_threshold_mm"] == 25

    skill = data["held_out_skill"]
    assert skill["roc_auc"] > 0.65
    low, high = skill["roc_auc_cluster_ci90"]
    assert low < skill["roc_auc"] < high
    assert skill["brier_skill_score"] > 0.0
    assert skill["error_model_skill_vs_climatology_pct"] > 0.0
    assert data["archive"]["provenance"]


def test_model_info_skill_declines_with_lead_time():
    skill_by_lead = client.get("/api/v1/model-info").json()["skill_by_lead_day"]
    assert skill_by_lead["day_1"]["roc_auc"] > skill_by_lead["day_10"]["roc_auc"]
    # A useful model must beat climatology at every lead time, not just on average.
    for key, entry in skill_by_lead.items():
        assert entry["brier_skill_score"] > 0.0, f"{key} lost to climatology"
