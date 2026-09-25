"""Unit tests for the model layer: artifacts, calibration, Shapley, lead-time decay."""
import os
import sys
from itertools import combinations
from math import factorial

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from app.core import archive
from app.core.config import settings
from app.core.explain import exact_interventional_shapley
from app.core.ml_engine import ml_engine
from app.core.regions import REGIONS

HIGH_INSTABILITY = {
    "cape_j_kg": 5900.0,
    "precipitable_water_mm": 89.0,
    "wind_shear_divergence": 17.5,
    "rh_700_pct": 98.0,
    "nwp_forecast_precip_mm": 180.0,
    "ensemble_spread_std": 40.0,
}

QUIESCENT = {
    "cape_j_kg": 0.0,
    "precipitable_water_mm": 6.0,
    "wind_shear_divergence": 1.0,
    "rh_700_pct": 28.0,
    "nwp_forecast_precip_mm": 0.0,
    "ensemble_spread_std": 1.0,
}


def test_artifacts_are_present_and_loaded():
    assert ml_engine.is_ready, ml_engine.load_error
    assert len(ml_engine.feature_names) == 13
    assert set(ml_engine.feature_names) == set(archive.ARCHIVE_FEATURES)
    assert ml_engine.classifier_bundle is not None
    assert ml_engine.regressor_bundle is not None


def test_region_registry_is_complete():
    assert len(REGIONS) == 20
    ids = [r["grid_id"] for r in REGIONS]
    assert len(set(ids)) == 20
    for region in REGIONS:
        assert 8.0 <= region["lat"] <= 37.0
        assert 68.0 <= region["lon"] <= 97.0
        assert 1000.0 <= region["baseline_slp"] <= 1020.0
        assert 10.0 <= region["base_pwat"] <= 80.0
        assert 0.0 <= region["published_bust_freq_pct"] <= 100.0


def test_probabilities_are_bounded_and_near_archive_base_rate():
    grid = ml_engine.get_forecast_grid(lead_day=1)
    probabilities = [c["bust_probability"] for c in grid["grid_cells"]]
    assert all(0.0 <= p <= 1.0 for p in probabilities)
    # Calibration is asserted on held-out data; live predictions should sit in a
    # plausible band rather than pinned to either extreme.
    assert 0.05 < float(np.mean(probabilities)) < 0.85


def test_confidence_is_exact_complement():
    grid = ml_engine.get_forecast_grid(lead_day=4)
    for cell in grid["grid_cells"]:
        expected = (1.0 - cell["bust_probability"]) * 100.0
        assert abs(cell["confidence_percentage"] - expected) < 0.11


def test_lead_time_skill_degrades_on_average():
    means = [
        ml_engine.get_forecast_grid(lead_day=day)["domain_telemetry"]["mean_bust_risk"]
        for day in range(1, 11)
    ]
    assert means[-1] > means[0], means
    assert means[-1] - means[0] > 0.2, means


def test_lead_time_profile_spans_full_horizon():
    profile = ml_engine.get_lead_time_profile()
    assert [e["lead_day"] for e in profile["domain_profile"]] == list(range(1, 11))
    assert len(profile["regions"]) == len(REGIONS)
    for region in profile["regions"]:
        assert [p["lead_day"] for p in region["series"]] == list(range(1, 11))


def test_shapley_additivity_for_live_cell():
    result = ml_engine.explain_grid_cell("IND-M-17", lead_day=7)
    shap_sum = sum(a["shap_value"] for a in result["shap_attributions"])
    assert abs(
        shap_sum - (result["bust_probability"] - result["shap_base_value"])
    ) < 0.01


def test_shapley_matches_naive_reference():
    """Validates the exact Shapley algorithm itself, independent of the model."""

    def f(X: np.ndarray) -> np.ndarray:
        a, b, c, d = X[:, 0], X[:, 1], X[:, 2], X[:, 3]
        return 1.0 / (1.0 + np.exp(-(0.8 * a - 0.5 * b * b + 0.3 * c * d - 1.2)))

    def naive_shapley(x: np.ndarray, bg: np.ndarray):
        n = len(x)
        values = {}
        for size in range(n + 1):
            for subset in combinations(range(n), size):
                total = 0.0
                for background_row in bg:
                    z = np.array(
                        [
                            x[j] if j in subset else background_row[j]
                            for j in range(n)
                        ]
                    )
                    total += f(z[None, :])[0]
                values[subset] = total / len(bg)
        out = np.zeros(n)
        for i in range(n):
            for size in range(n):
                others = [j for j in range(n) if j != i]
                for subset in combinations(others, size):
                    weight = factorial(size) * factorial(n - size - 1) / factorial(n)
                    out[i] += weight * (
                        values[tuple(sorted(subset + (i,)))] - values[subset]
                    )
        return out, values[()]

    rng = np.random.default_rng(0)
    x = rng.normal(size=4)
    bg = rng.normal(size=(7, 4))
    naive, base = naive_shapley(x, bg)
    fast = exact_interventional_shapley(f, x[None, :], bg)

    assert np.allclose(naive, fast["shap_values"][0], atol=1e-12)
    assert abs(base - fast["base_value"][0]) < 1e-12
    assert abs(
        fast["base_value"][0] + fast["shap_values"][0].sum() - f(x[None, :])[0]
    ) < 1e-12


def test_shapley_attribution_cache_returns_consistent_values():
    first = ml_engine.explain_grid_cell("IND-NC-03", lead_day=3)
    second = ml_engine.explain_grid_cell("IND-NC-03", lead_day=3)
    assert first["bust_probability"] == second["bust_probability"]
    assert first["shap_base_value"] == second["shap_base_value"]


def test_custom_features_are_range_checked_and_reported():
    result = ml_engine.explain_grid_cell(
        "IND-E-16",
        lead_day=2,
        custom_features={
            "precipitable_water_mm": 900.0,  # above the physical limit
            "cape_j_kg": 3000.0,  # valid, must be applied
            "geopotential_anomaly_m": 5.0,  # valid
            "bogus_feature": 1.0,  # unknown
        },
    )
    assert "precipitable_water_mm" in result["ignored_custom_features"]
    assert "bogus_feature" in result["ignored_custom_features"]
    assert "cape_j_kg" not in result["ignored_custom_features"]
    assert "geopotential_anomaly_m" not in result["ignored_custom_features"]
    assert result["observed_features"]["cape_j_kg"] == 3000.0
    assert result["observed_features"]["precipitable_water_mm"] <= 90.0


def test_model_responds_to_instability():
    """The model must actually use the meteorological inputs, not just lead time."""
    baseline = ml_engine.explain_grid_cell("IND-W-12", lead_day=7)
    unstable = ml_engine.explain_grid_cell(
        "IND-W-12", lead_day=7, custom_features=HIGH_INSTABILITY
    )
    quiescent = ml_engine.explain_grid_cell(
        "IND-W-12", lead_day=7, custom_features=QUIESCENT
    )
    assert unstable["bust_probability"] > baseline["bust_probability"]
    assert quiescent["bust_probability"] < baseline["bust_probability"]


def test_archive_climatology_uses_training_split_only():
    """The historical baseline must be reproducible from the train split alone.

    If the test or validation rows had leaked into climatology, the recomputed
    train-only statistics would not match the ones shipped in the archive.
    """
    built = archive.build_archive(n_samples=4000, seed=7)
    train_idx = built["train_idx"]
    assert len(train_idx) == int(4000 * 0.7)

    recomputed = archive.derive_regional_climatology(
        region_idx=built["region_idx"][train_idx],
        bust_labels=built["y_bust"][train_idx],
        abs_errors=built["y_abs_error"][train_idx],
        X=built["X"][train_idx],
        lead_days=built["lead_day"][train_idx],
    )

    assert set(recomputed) == set(built["climatology"])
    for grid_id, stats in recomputed.items():
        shipped = built["climatology"][grid_id]
        assert stats["hist_bust_freq_pct"] == pytest.approx(
            shipped["hist_bust_freq_pct"], abs=1e-9
        )
        assert stats["hist_mean_abs_err_mm"] == pytest.approx(
            shipped["hist_mean_abs_err_mm"], abs=1e-9
        )
        # Every region must be represented, and the counts must sum to the
        # training rows rather than the whole archive.
        assert stats["archive_samples"] > 0

    assert sum(s["archive_samples"] for s in recomputed.values()) == len(train_idx)

    # Using the full archive instead must give a different answer, which proves
    # the derivation is actually sensitive to which rows it is given.
    full = archive.derive_regional_climatology(
        region_idx=built["region_idx"],
        bust_labels=built["y_bust"],
        abs_errors=built["y_abs_error"],
        X=built["X"],
        lead_days=built["lead_day"],
    )
    assert any(
        full[grid_id]["archive_samples"] != recomputed[grid_id]["archive_samples"]
        for grid_id in recomputed
    )


def test_training_report_skill_is_positive():
    skill = ml_engine.training_report["classifier_skill"]
    assert skill["roc_auc"] > 0.65
    assert skill["brier_skill_score"] > 0.0
    assert skill["expected_calibration_error"] < 0.05
    low, high = skill["roc_auc_cluster_ci90"]
    assert low < skill["roc_auc"] < high

    regressor = ml_engine.training_report["regressor_skill"]
    assert regressor["mae_mm"] < regressor["climatology_mae_mm"]

    assert ml_engine.training_report["target"]["error_threshold_mm"] == (
        settings.BUST_ERROR_THRESHOLD_MM
    )
    assert "synthetic" in ml_engine.training_report["archive"]["provenance"].lower()


def test_lead_bounds_match_settings():
    grid = ml_engine.get_forecast_grid(lead_day=settings.LEAD_DAY_MAX)
    assert grid["lead_day"] == settings.LEAD_DAY_MAX
    assert grid["domain"]["lat_bounds"] == [settings.LAT_MIN, settings.LAT_MAX]
    assert grid["domain"]["lon_bounds"] == [settings.LON_MIN, settings.LON_MAX]
