"""Historical forecast-error archive synthesis for VayuDRISHTI.

Operational forecasting centres score medium-range guidance against
observations every cycle and keep that archive. This module stands in for that
archive so the prototype has a real, labelled dataset to learn from instead of
a hand-tuned formula.

What is modelled
----------------
A verification sample is a (region, lead day, forecast state) triple. Its label
is whether the 24-hour accumulated precipitation forecast busted, where a bust
is ``|forecast - observed| > BUST_ERROR_THRESHOLD_MM``.

The realised error is generated from two physically distinct contributions, then
perturbed by an irreducible stochastic term:

``model error``
    Parameterisation and resolution failure. Strong in convective and
    orographic regimes, only weakly lead-dependent. Dominates Day 1-3 busts.

``predictability error``
    Phase error from unresolved scales and initial-condition spread. Grows
    steeply with lead time and is modulated by the ensemble disagreement the
    forecaster can actually observe. Dominates Day 5-10 busts.

Because the stochastic term is unobservable, the Bayes-optimal forecast is a
*probability*, not a point value. That is what makes calibration meaningful here
rather than decorative.

Honesty note
------------
This is a synthetic proxy, not NCMRWF data. It is generated from an
independent physical error model and is deliberately *not* the scoring
expression used at inference time, so a model that scores well has genuinely
learned the mapping rather than memorised a formula. Swap `build_archive` for a
loader over real NCMRWF verification tables and the rest of the pipeline is
unchanged.
"""
from typing import Any, Dict, List, Tuple

import numpy as np

from app.core.config import settings
from app.core.regions import REGIONS

ARCHIVE_FEATURES: List[str] = [
    "slp_hpa",
    "precipitable_water_mm",
    "wind_shear_divergence",
    "temp_gradient_k",
    "cape_j_kg",
    "geopotential_anomaly_m",
    "rh_700_pct",
    "surface_wind_knots",
    "nwp_forecast_precip_mm",
    "ensemble_spread_std",
    "lead_day",
    "hist_bust_freq_pct",
    "hist_mae_mm",
]

FEATURE_UNITS: Dict[str, str] = {
    "slp_hpa": "hPa",
    "precipitable_water_mm": "mm",
    "wind_shear_divergence": "1e-5 s-1",
    "temp_gradient_k": "K km-1",
    "cape_j_kg": "J kg-1",
    "geopotential_anomaly_m": "m",
    "rh_700_pct": "%",
    "surface_wind_knots": "kt",
    "nwp_forecast_precip_mm": "mm",
    "ensemble_spread_std": "mm",
    "lead_day": "day",
    "hist_bust_freq_pct": "%",
    "hist_mae_mm": "mm",
}

FEATURE_DESCRIPTIONS: Dict[str, str] = {
    "slp_hpa": "Mean sea-level pressure",
    "precipitable_water_mm": "Column precipitable water (PWAT)",
    "wind_shear_divergence": "850-200 hPa deep-tropospheric shear magnitude",
    "temp_gradient_k": "850-500 hPa vertical lapse rate",
    "cape_j_kg": "Convective available potential energy",
    "geopotential_anomaly_m": "500 hPa geopotential height anomaly",
    "rh_700_pct": "700 hPa relative humidity",
    "surface_wind_knots": "10 m wind speed",
    "nwp_forecast_precip_mm": "NWP 24h accumulated precipitation forecast",
    "ensemble_spread_std": "Ensemble spread of 24h accumulated precipitation",
    "lead_day": "Forecast lead time",
    "hist_bust_freq_pct": "Regional historical bust frequency",
    "hist_mae_mm": "Regional historical mean absolute error",
}

FEATURE_LIMITS: Dict[str, Tuple[float, float]] = {
    "slp_hpa": (960.0, 1045.0),
    "precipitable_water_mm": (5.0, 90.0),
    "wind_shear_divergence": (0.0, 30.0),
    "temp_gradient_k": (4.0, 11.0),
    "cape_j_kg": (0.0, 6000.0),
    "geopotential_anomaly_m": (-120.0, 120.0),
    "rh_700_pct": (5.0, 100.0),
    "surface_wind_knots": (0.0, 80.0),
    "nwp_forecast_precip_mm": (0.0, 400.0),
    "ensemble_spread_std": (0.0, 60.0),
    "lead_day": (float(settings.LEAD_DAY_MIN), float(settings.LEAD_DAY_MAX)),
    "hist_bust_freq_pct": (0.0, 100.0),
    "hist_mae_mm": (0.0, 200.0),
}


def _clip(value: float, low: float, high: float) -> float:
    return float(min(high, max(low, value)))


def sample_forecast_state(
    rng: np.random.Generator, region: Dict[str, Any], lead_day: int
) -> Dict[str, float]:
    """Draw a plausible forecast state for a region at a given lead time.

    Uncertainty in the state itself widens with lead time, mirroring how a
    forecast state's own departure from climatology grows as integration
    proceeds.
    """
    lead = float(lead_day)
    spread = 1.0 + 0.16 * (lead - 1.0)

    slp = region["baseline_slp"] + rng.normal(0.0, 4.0 * spread)
    pwat = _clip(region["base_pwat"] + rng.normal(0.0, 5.5 * spread), 6.0, 88.0)
    shear = _clip(
        abs(rng.normal(4.6, 2.3)) + 0.22 * (lead - 1.0) + 0.35 * region["orographic_gain"],
        0.4,
        28.0,
    )
    lapse = _clip(rng.normal(6.25, 0.95) + 0.30 * region["orographic_gain"], 4.2, 10.8)
    cape = _clip(pwat * 37.0 + shear * 115.0 + rng.normal(0.0, 520.0), 120.0, 5800.0)
    geo_anom = rng.normal(0.0, 11.0 + 2.6 * (lead - 1.0))
    rh_700 = _clip(56.0 + 0.48 * pwat + rng.normal(0.0, 7.5), 12.0, 99.0)
    surface_wind = _clip(13.0 + 2.3 * shear + 1.05 * lead + rng.normal(0.0, 2.6), 1.0, 75.0)
    nwp_precip = _clip((pwat - 30.0) * 1.15 + abs(rng.normal(0.0, 17.0)), 0.0, 380.0)
    ensemble_spread = _clip(
        0.7 + 1.35 * lead + 0.055 * nwp_precip + abs(rng.normal(0.0, 0.55)), 0.2, 55.0
    )

    return {
        "slp_hpa": round(slp, 2),
        "precipitable_water_mm": round(pwat, 2),
        "wind_shear_divergence": round(shear, 3),
        "temp_gradient_k": round(lapse, 3),
        "cape_j_kg": round(cape, 1),
        "geopotential_anomaly_m": round(geo_anom, 2),
        "rh_700_pct": round(rh_700, 2),
        "surface_wind_knots": round(surface_wind, 2),
        "nwp_forecast_precip_mm": round(nwp_precip, 2),
        "ensemble_spread_std": round(ensemble_spread, 3),
        "lead_day": float(lead_day),
    }


def simulate_verification_error(
    rng: np.random.Generator, state: Dict[str, float], region: Dict[str, Any]
) -> Tuple[float, float]:
    """Return ``(signed_error_mm, abs_error_mm)`` for one verification sample.

    Two independent error scales are combined, then multiplied by a heavy-tailed
    draw. The Student-t draw matters: precipitation verification errors are
    strongly leptokurtic, so a Gaussian model would badly misjudge the tail
    probabilities this system exists to report.
    """
    lead = state["lead_day"]
    pwat = state["precipitable_water_mm"]
    cape = state["cape_j_kg"]
    shear = state["wind_shear_divergence"]
    spread = state["ensemble_spread_std"]

    convective_load = _clip(cape / 3000.0, 0.0, 1.7)
    moisture_load = _clip((pwat - 45.0) / 30.0, -1.2, 1.7)
    shear_load = _clip((shear - 5.0) / 6.0, -0.8, 2.0)
    orographic = region["orographic_gain"]

    model_error_scale = region["param_gain"] * (
        0.44
        + 0.26 * convective_load
        + 0.22 * max(moisture_load, 0.0)
        + 0.13 * max(shear_load, 0.0)
        + orographic
        + 0.024 * lead
    )

    predictability_error_scale = region["chaos_gain"] * (
        0.042 * spread + 0.165 * (lead - 1.0) ** 1.12
    )

    total_scale = model_error_scale + predictability_error_scale
    heavy_tailed_draw = rng.standard_t(df=4.0)
    signed_error = total_scale * heavy_tailed_draw + rng.normal(0.0, 1.2)
    return float(signed_error), float(abs(signed_error))


def build_archive(
    n_samples: int = 60000, seed: int = 20260926, train_fraction: float = 0.70
) -> Dict[str, Any]:
    """Build the labelled historical verification archive.

    The regional climatology features are derived from the *training* portion
    only. Deriving them across the full archive would leak held-out cases into
    the model's inputs and inflate the reported skill, which is exactly the kind
    of quiet optimism a confidence product must not have.

    Returns feature matrix ``X``, binary bust labels ``y_bust``, realised
    absolute errors ``y_abs_error``, the region index per sample, the split
    index and the empirically derived regional climatology.
    """
    rng = np.random.default_rng(seed)
    n_regions = len(REGIONS)

    region_idx = rng.integers(0, n_regions, size=n_samples)
    lead_days = rng.integers(
        settings.LEAD_DAY_MIN, settings.LEAD_DAY_MAX + 1, size=n_samples
    )

    X = np.zeros((n_samples, len(ARCHIVE_FEATURES)), dtype=np.float64)
    abs_errors = np.zeros(n_samples, dtype=np.float64)

    for i in range(n_samples):
        region = REGIONS[int(region_idx[i])]
        state = sample_forecast_state(rng, region, int(lead_days[i]))
        _, abs_err = simulate_verification_error(rng, state, region)
        for j, name in enumerate(ARCHIVE_FEATURES):
            if name in state:
                X[i, j] = state[name]
        abs_errors[i] = abs_err

    bust_labels = (abs_errors > settings.BUST_ERROR_THRESHOLD_MM).astype(np.int64)

    permutation = rng.permutation(n_samples)
    n_train = int(n_samples * train_fraction)
    train_idx = permutation[:n_train]

    climatology = derive_regional_climatology(
        region_idx[train_idx],
        bust_labels[train_idx],
        abs_errors[train_idx],
        X[train_idx],
        lead_days[train_idx],
    )
    for i in range(n_samples):
        grid_id = REGIONS[int(region_idx[i])]["grid_id"]
        clim = climatology[grid_id]
        X[i, ARCHIVE_FEATURES.index("hist_bust_freq_pct")] = clim["hist_bust_freq_pct"]
        X[i, ARCHIVE_FEATURES.index("hist_mae_mm")] = clim["hist_mean_abs_err_mm"]

    return {
        "X": X,
        "y_bust": bust_labels,
        "y_abs_error": abs_errors,
        "region_idx": region_idx,
        "lead_day": lead_days.astype(np.int64),
        "train_idx": train_idx,
        "climatology": climatology,
        "feature_names": list(ARCHIVE_FEATURES),
    }


def derive_regional_climatology(
    region_idx: np.ndarray,
    bust_labels: np.ndarray,
    abs_errors: np.ndarray,
    X: np.ndarray,
    lead_days: np.ndarray,
) -> Dict[str, Dict[str, Any]]:
    """Derive per-region historical bust frequency, MAE and worst lead day.

    This mirrors how an operational archive produces its climatology: group the
    verified cases by region and summarise. Because it is computed from the
    archive rather than hand-authored, the number the dashboard shows against a
    live forecast is a genuine like-for-like comparison.
    """
    lead_col = list(ARCHIVE_FEATURES).index("lead_day")
    climatology: Dict[str, Dict[str, Any]] = {}

    for idx, region in enumerate(REGIONS):
        mask = region_idx == idx
        if not np.any(mask):
            climatology[region["grid_id"]] = _fallback_climatology(region)
            continue

        region_busts = bust_labels[mask]
        region_errors = abs_errors[mask]
        region_leads = lead_days[mask]
        region_spread = X[mask, lead_col]

        per_lead_rate = []
        for day in range(settings.LEAD_DAY_MIN, settings.LEAD_DAY_MAX + 1):
            day_mask = region_leads == day
            per_lead_rate.append(
                float(region_busts[day_mask].mean()) if np.any(day_mask) else 0.0
            )

        lead_span = settings.LEAD_DAY_MAX - settings.LEAD_DAY_MIN
        worst_lead_day = int(
            settings.LEAD_DAY_MIN
            + round(np.argmax(per_lead_rate) * lead_span / max(1, len(per_lead_rate) - 1))
        )

        climatology[region["grid_id"]] = {
            "hist_bust_freq_pct": round(float(region_busts.mean() * 100.0), 2),
            "hist_mean_abs_err_mm": round(float(region_errors.mean()), 2),
            "hist_mae_p90_mm": round(float(np.percentile(region_errors, 90)), 2),
            "worst_lead_day": worst_lead_day,
            "peak_event": region["peak_event"],
            "mean_ensemble_spread_mm": round(float(region_spread.mean()), 3),
            "archive_samples": int(mask.sum()),
            "per_lead_bust_rate_pct": [
                round(rate * 100.0, 2) for rate in per_lead_rate
            ],
        }

    return climatology


def _fallback_climatology(region: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "hist_bust_freq_pct": float(region["published_bust_freq_pct"]),
        "hist_mean_abs_err_mm": float(region["published_mae_mm"]),
        "hist_mae_p90_mm": round(float(region["published_mae_mm"]) * 2.1, 2),
        "worst_lead_day": int(region["worst_lead_day"]),
        "peak_event": region["peak_event"],
        "mean_ensemble_spread_mm": 0.0,
        "archive_samples": 0,
        "per_lead_bust_rate_pct": [],
    }


def build_live_grid(seed: int = 20260926) -> List[Dict[str, Any]]:
    """Build the Day 1-10 forecast grid served to the dashboard.

    States are drawn from the same distribution as the training archive, so the
    engine is never scoring a smoother, cleaner lattice than it was fitted on.
    """
    rng = np.random.default_rng(seed)
    grid: List[Dict[str, Any]] = []

    for region in REGIONS:
        lead_days: Dict[str, Dict[str, float]] = {}
        for day in range(settings.LEAD_DAY_MIN, settings.LEAD_DAY_MAX + 1):
            state = sample_forecast_state(rng, region, day)
            state["historical_error_variance"] = round(
                0.42 * (day ** 1.35) + abs(state["ensemble_spread_std"] * 0.08), 3
            )
            lead_days[str(day)] = state

        grid.append(
            {
                "grid_id": region["grid_id"],
                "name": region["name"],
                "subdivision": region["subdivision"],
                "lat": region["lat"],
                "lon": region["lon"],
                "climate_type": region["climate_type"],
                "lead_days": lead_days,
            }
        )

    return grid
