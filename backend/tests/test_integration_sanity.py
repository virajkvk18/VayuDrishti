"""End-to-end integration sanity verification for VayuDRISHTI.

Run directly for a human-readable report:

    python tests/test_integration_sanity.py

It is also collected by pytest, so every assertion below is a regression guard.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.main import app


def test_integration_sanity():
    client = TestClient(app)
    print(">>> [1/6] Verifying System Health Telemetry...")
    res = client.get("/api/v1/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health = res.json()
    assert health["status"] == "OPERATIONAL"
    assert health["model_ready"] is True
    print(f"    Health Status: {health['status']} | NWP Base: {health['nwp_model_base']}")

    print(">>> [2/6] Testing Day 1 vs Day 10 Forecast Grid Dynamics...")
    grid_d1 = client.get("/api/v1/forecast-grid?lead_day=1").json()
    grid_d10 = client.get("/api/v1/forecast-grid?lead_day=10").json()
    mean_risk_d1 = grid_d1["domain_telemetry"]["mean_bust_risk"]
    mean_risk_d10 = grid_d10["domain_telemetry"]["mean_bust_risk"]
    print(f"    Day 1 Mean Bust Risk: {mean_risk_d1:.3f}")
    print(f"    Day 10 Mean Bust Risk: {mean_risk_d10:.3f}")
    assert mean_risk_d10 > mean_risk_d1, "Uncertainty did not expand with lead horizon!"

    print(">>> [3/6] Testing Error-Prone Area Detection...")
    areas = grid_d10["error_prone_areas"]
    assert areas, "No error-prone areas reported at Day 10"
    print(f"    Error-prone regions at Day 10: {len(areas)}")
    for area in areas[:3]:
        print(
            f"      - {area['name']}: {area['confidence_percentage']:.1f}% confidence, "
            f"{area['historical_comparison_signal']}"
        )
    assert all(
        a["historical_comparison_signal"] in (
            "ANOMALOUSLY_ELEVATED",
            "CONSISTENT_WITH_ARCHIVE",
            "BELOW_ARCHIVE_AVERAGE",
        )
        for a in areas
    )

    print(">>> [4/6] Testing Day 1-10 Lead-Time Confidence Profile...")
    profile = client.get("/api/v1/lead-time-profile").json()
    series = [e["mean_bust_probability"] for e in profile["domain_profile"]]
    print(f"    Domain bust probability: D1 {series[0]:.3f} -> D10 {series[-1]:.3f}")
    print(f"    Highest risk lead day: Day {profile['highest_risk_lead_day']}")
    assert series[-1] > series[0]

    print(">>> [5/6] Testing Interactive XAI Inspector Card Breakdown...")
    target_station = "IND-E-16"  # Odisha Coastal Cyclone Corridor
    exp = client.post(
        "/api/v1/explain-bust", json={"grid_id": target_station, "lead_day": 3}
    ).json()
    assert exp["grid_id"] == target_station
    assert len(exp["top_atmospheric_drivers"]) == 3
    assert len(exp["shap_attributions"]) > 0
    assert exp["reliability_flag"] in (
        "RELIABLE",
        "ELEVATED_UNCERTAINTY",
        "ERROR_PRONE",
    )
    print(f"    Station: {exp['name']} ({exp['grid_id']})")
    print(
        f"    Bust Risk: {exp['bust_probability']:.3f} | "
        f"Confidence: {exp['confidence_percentage']:.1f}% | "
        f"Flag: {exp['reliability_flag']}"
    )
    print(f"    Regime: {exp['weather_event_classification']['event_type']}")
    print(f"    Primary Driver: {exp['top_atmospheric_drivers'][0]['feature']}")
    print(f"    Advisory: {exp['operational_advisory'][:100]}...")

    print(">>> [6/6] Testing Custom Sounding Sensitivity Perturbation...")
    exp_pert = client.post(
        "/api/v1/explain-bust",
        json={
            "grid_id": target_station,
            "lead_day": 3,
            "custom_features": {
                "wind_shear_divergence": 16.0,
                "precipitable_water_mm": 78.0,
                "cape_j_kg": 4400.0,
            },
        },
    ).json()
    print(
        f"    Perturbed Bust Risk: {exp_pert['bust_probability']:.3f} "
        f"(vs baseline {exp['bust_probability']:.3f})"
    )
    assert (
        exp_pert["bust_probability"] > exp["bust_probability"]
    ), "Perturbed high instability did not elevate risk!"

    print(">>> [7/7] Verifying Model Provenance and Held-Out Skill...")
    model_info = client.get("/api/v1/model-info").json()
    skill = model_info["held_out_skill"]
    print(f"    Algorithm: {model_info['algorithm']}")
    print(
        f"    Held-out ROC-AUC: {skill['roc_auc']:.4f} "
        f"(90% CI {skill['roc_auc_cluster_ci90']})"
    )
    print(
        f"    Brier skill: {skill['brier_skill_score']:+.4f} | "
        f"ECE: {skill['expected_calibration_error']:.4f}"
    )
    print(
        f"    Error MAE: {skill['error_model_mae_mm']:.2f} mm vs climatology "
        f"{skill['error_model_mae_climatology_mm']:.2f} mm "
        f"({skill['error_model_skill_vs_climatology_pct']:+.1f}% skill)"
    )
    assert skill["brier_skill_score"] > 0.0

    print("\n>>> ALL INTEGRATION SANITY CHECKS PASSED SUCCESSFULLY (100% GREEN)!")


if __name__ == "__main__":
    test_integration_sanity()
