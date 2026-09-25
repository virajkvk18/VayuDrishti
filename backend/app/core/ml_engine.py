"""Inference engine for VayuDRISHTI forecast-bust detection (PS-26079).

Serving path only. The models are fitted by ``app.core.train`` and loaded here.
This module turns a forecast state into the five deliverables the problem
statement asks for:

1. Forecast confidence map      -> ``confidence_percentage`` per region and lead day
2. Forecast bust probability    -> calibrated ``bust_probability``
3. Error-prone area detection   -> ``error_prone_areas`` in the grid response
4. Explainable output           -> exact Shapley attributions plus a directive
5. Operational API              -> ``app.api.endpoints``

It also answers the problem statement's comparison requirement directly: each
live forecast is scored against the region's climatology derived from the
training archive, and the ratio of the two is reported as an explicit signal.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from joblib import load

from app.core.archive import (
    ARCHIVE_FEATURES,
    FEATURE_DESCRIPTIONS,
    FEATURE_LIMITS,
    FEATURE_UNITS,
)
from app.core.config import settings
from app.core.explain import build_background, exact_interventional_shapley
from app.core.regions import DOMAIN_BOUNDS, REGION_BY_ID, REGIONS

RISK_COLORS = {"HIGH": "#ef4444", "MODERATE": "#eab308", "LOW": "#10b981"}
RELIABILITY_FLAGS = {
    "HIGH": "ERROR_PRONE",
    "MODERATE": "ELEVATED_UNCERTAINTY",
    "LOW": "RELIABLE",
}

FEATURE_DISPLAY_SUFFIX = {
    "slp_hpa": " hPa",
    "precipitable_water_mm": " mm",
    "wind_shear_divergence": " (1e-5 s-1)",
    "temp_gradient_k": " K/km",
    "cape_j_kg": " J/kg",
    "geopotential_anomaly_m": " m",
    "rh_700_pct": "%",
    "surface_wind_knots": " kt",
    "nwp_forecast_precip_mm": " mm",
    "ensemble_spread_std": " mm",
    "lead_day": " d",
    "hist_bust_freq_pct": "%",
    "hist_mae_mm": " mm",
}

DRIVER_NARRATIVE: Dict[str, str] = {
    "lead_day": "A long lead time places the control run deep in the nonlinear growth phase, where unresolved synoptic phase error dominates the forecast signal.",
    "hist_bust_freq_pct": "This region's own verification record shows an elevated historical bust rate, so large errors here are expected rather than exceptional.",
    "hist_mae_mm": "A long-standing regional mean absolute error indicates the area has never been well constrained by the observing network.",
    "ensemble_spread_std": "Wide ensemble disagreement on accumulated precipitation signals real flow uncertainty that a single deterministic run cannot resolve.",
    "cape_j_kg": "Strong convective buoyancy pushes the convection parameterisation beyond the range where it is empirically calibrated.",
    "precipitable_water_mm": "A deep moisture reservoir makes accumulated precipitation hypersensitive to small errors in moisture flux convergence.",
    "wind_shear_divergence": "Strong deep-tropospheric shear places the flow in a regime where small displacement errors amplify rapidly downstream.",
    "temp_gradient_k": "A steep mid-tropospheric lapse rate destabilises the column, amplifying errors in vertical diffusion and cloud microphysics.",
    "slp_hpa": "Anomalous sea-level pressure marks a synoptic disturbance whose central pressure and track are the least predictable elements of the forecast.",
    "geopotential_anomaly_m": "A large 500 hPa height anomaly anchors the circulation, and any error in it propagates into every downstream field.",
    "rh_700_pct": "Mid-level humidity governs convective initiation and downdraft evaporation, both sensitive to humidity errors the model cannot resolve at grid scale.",
    "surface_wind_knots": "Strong surface winds raise wave and boundary-layer drag errors, which couple back into the lower troposphere.",
}

PHYSICAL_STATE_FEATURES = [
    name for name in ARCHIVE_FEATURES if name not in ("lead_day", "hist_bust_freq_pct", "hist_mae_mm")
]


class ModelArtifactsUnavailable(RuntimeError):
    """Raised when the trained artifacts are absent, with instructions to fix it."""


def classify_weather_event(
    slp: float,
    pwat: float,
    shear: float,
    cape: float,
    geo_anom: float,
    wind: float,
    lapse: float,
    lead_day: int,
) -> Dict[str, Any]:
    """Rule-based synoptic regime identification.

    Runs on the forecast state rather than on model internals, so a forecaster
    can sanity-check the label against the synoptic chart. Every regime score is
    returned so the dashboard can show why a label was chosen.
    """
    scores: Dict[str, float] = {
        "Tropical Cyclone / Deep Depression": 0.0,
        "Monsoon Depression / Heavy Rainfall": 0.0,
        "Western Disturbance / Upper Trough": 0.0,
        "Heat Wave": 0.0,
        "Break Monsoon Phase": 0.0,
        "Orographic Extreme Rainfall": 0.0,
        "Stable / Non-eventive": 0.0,
    }

    slp_depression = 1010.0 - slp

    if slp_depression > 5.0:
        scores["Tropical Cyclone / Deep Depression"] += 2.0
    if pwat > 55.0:
        scores["Tropical Cyclone / Deep Depression"] += 1.5
    if shear < 4.0:
        scores["Tropical Cyclone / Deep Depression"] += 1.2
    if wind > 22.0:
        scores["Tropical Cyclone / Deep Depression"] += 1.0

    if pwat > 50.0:
        scores["Monsoon Depression / Heavy Rainfall"] += 2.0
    if cape > 2500.0:
        scores["Monsoon Depression / Heavy Rainfall"] += 1.8
    if shear > 6.0:
        scores["Monsoon Depression / Heavy Rainfall"] += 1.0

    if geo_anom < -15.0:
        scores["Western Disturbance / Upper Trough"] += 2.5
    if lapse > 7.5:
        scores["Western Disturbance / Upper Trough"] += 1.0
    if lead_day >= 5:
        scores["Western Disturbance / Upper Trough"] += 0.8

    if slp > 1013.0 and pwat < 30.0:
        scores["Heat Wave"] += 2.5
    if lapse > 8.0:
        scores["Heat Wave"] += 1.0
    if cape < 500.0 and wind < 12.0:
        scores["Heat Wave"] += 0.8

    if 1011.0 < slp <= 1013.0 and 20.0 < pwat < 38.0:
        scores["Break Monsoon Phase"] += 1.8
    if shear < 3.0 and geo_anom > 10.0:
        scores["Break Monsoon Phase"] += 1.2

    if pwat > 60.0 and shear > 7.0:
        scores["Orographic Extreme Rainfall"] += 2.2
    if cape > 3000.0:
        scores["Orographic Extreme Rainfall"] += 1.5

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    dominant, top_score = ranked[0]

    if top_score <= 0.0:
        confidence = "LOW"
    elif top_score >= 3.0:
        confidence = "HIGH"
    elif top_score >= 1.5:
        confidence = "MODERATE"
    else:
        confidence = "LOW"

    return {
        "event_type": dominant,
        "classification_confidence": confidence,
        "regime_scores": {k: round(v, 2) for k, v in ranked},
    }


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class ForecastBustEngine:
    """Loads the trained artifacts and serves the operational diagnostics."""

    def __init__(self) -> None:
        self.artifact_dir = Path(settings.resolved_artifact_dir)
        self.classifier_bundle: Optional[Dict[str, Any]] = None
        self.regressor_bundle: Optional[Dict[str, Any]] = None
        self.training_report: Dict[str, Any] = {}
        self.climatology: Dict[str, Dict[str, Any]] = {}
        self.grid_data: List[Dict[str, Any]] = self._load_grid_data()
        self.load_error: Optional[str] = None
        self._background: Optional[np.ndarray] = None
        self._grid_background: Optional[np.ndarray] = None
        self._feature_medians: Dict[str, float] = {}
        self._attribution_cache: Dict[Tuple[str, int, str], List[Dict[str, Any]]] = {}
        self._load_artifacts()
        self._compute_feature_medians()

    # -- artifact loading -------------------------------------------------- #

    def _load_artifacts(self) -> None:
        clf_path = self.artifact_dir / "bust_model.joblib"
        reg_path = self.artifact_dir / "error_model.joblib"
        report_path = self.artifact_dir / "training_report.json"

        missing = [p.name for p in (clf_path, reg_path, report_path) if not p.exists()]
        if missing:
            self.load_error = (
                f"Missing trained model artifact(s): {', '.join(missing)} in "
                f"{self.artifact_dir}. Regenerate with `python -m app.core.train`."
            )
            return

        try:
            self.classifier_bundle = load(clf_path)
            self.regressor_bundle = load(reg_path)
            with open(report_path, "r", encoding="utf-8") as fh:
                self.training_report = json.load(fh)
            self.climatology = self.training_report.get("regional_climatology", {})
        except Exception as exc:
            self.load_error = f"Failed to load model artifacts: {exc}"

    @property
    def is_ready(self) -> bool:
        return self.classifier_bundle is not None and self.regressor_bundle is not None

    def _require_ready(self) -> None:
        if not self.is_ready:
            raise ModelArtifactsUnavailable(
                self.load_error or "Trained model artifacts are unavailable."
            )

    def _load_grid_data(self) -> List[Dict[str, Any]]:
        path = Path(__file__).resolve().parent.parent / "data" / "mock_weather_grid.json"
        if not path.exists():
            from app.core.archive import build_live_grid

            grid = build_live_grid()
            path.write_text(json.dumps(grid, indent=2), encoding="utf-8")
            return grid
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _compute_feature_medians(self) -> None:
        """Median of each physical feature across the whole grid.

        Used as the fallback when a caller supplies an unreadable value, so a
        malformed override degrades to climatology rather than to zero.
        """
        collected: Dict[str, List[float]] = {name: [] for name in PHYSICAL_STATE_FEATURES}
        for cell in self.grid_data:
            for day_data in cell.get("lead_days", {}).values():
                for name in PHYSICAL_STATE_FEATURES:
                    value = day_data.get(name)
                    if isinstance(value, (int, float)) and math.isfinite(value):
                        collected[name].append(float(value))
        for name, values in collected.items():
            self._feature_medians[name] = float(np.median(values)) if values else 0.0

    # -- model plumbing ---------------------------------------------------- #

    @property
    def feature_names(self) -> List[str]:
        if self.classifier_bundle:
            return list(self.classifier_bundle["feature_names"])
        return list(ARCHIVE_FEATURES)

    def _bust_probability(self, matrix: np.ndarray) -> np.ndarray:
        return self.classifier_bundle["classifier"].predict_proba(matrix)[:, 1]

    def _expected_error_mm(self, matrix: np.ndarray) -> np.ndarray:
        raw = self.regressor_bundle["regressor"].predict(matrix)
        transform = self.regressor_bundle.get("target_transform")
        if transform == "sqrt":
            return np.clip(np.square(raw), 0.0, None)
        if transform == "log1p":
            return np.clip(np.expm1(raw), 0.0, None)
        return np.clip(raw, 0.0, None)

    def _sanitize(
        self, state: Dict[str, float], lead_day: int
    ) -> Dict[str, float]:
        """Clamp supplied features into the archive's physical range."""
        clean: Dict[str, float] = {
            "lead_day": float(
                np.clip(lead_day, settings.LEAD_DAY_MIN, settings.LEAD_DAY_MAX)
            )
        }
        for name in PHYSICAL_STATE_FEATURES:
            low, high = FEATURE_LIMITS[name]
            try:
                value = float(state.get(name))
            except (TypeError, ValueError):
                value = float("nan")
            if not math.isfinite(value):
                value = self._feature_medians.get(name, 0.0)
            clean[name] = float(np.clip(value, low, high))
        return clean

    def _feature_matrix(
        self, states: List[Dict[str, float]], grid_ids: List[str]
    ) -> np.ndarray:
        rows: List[List[float]] = []
        for state, grid_id in zip(states, grid_ids):
            clim = self._climatology_for(grid_id)
            row: List[float] = []
            for name in self.feature_names:
                if name == "hist_bust_freq_pct":
                    row.append(float(clim["hist_bust_freq_pct"]))
                elif name == "hist_mae_mm":
                    row.append(float(clim["hist_mean_abs_err_mm"]))
                else:
                    row.append(float(state[name]))
            rows.append(row)
        return np.asarray(rows, dtype=np.float64)

    def _climatology_for(self, grid_id: str) -> Dict[str, Any]:
        return self.climatology.get(grid_id) or self._default_climatology()

    @staticmethod
    def _default_climatology() -> Dict[str, Any]:
        return {
            "hist_bust_freq_pct": 25.0,
            "hist_mean_abs_err_mm": 28.0,
            "hist_mae_p90_mm": 60.0,
            "worst_lead_day": 5,
            "peak_event": "General NWP Uncertainty",
            "archive_samples": 0,
            "per_lead_bust_rate_pct": [],
        }

    def _all_states(self) -> List[Dict[str, float]]:
        """Every grid state, with its region's climatology columns filled in.

        The background distribution must include the climatology features too,
        otherwise a domain where one region is far more error-prone than another
        would have its attribution silently distorted.
        """
        states: List[Dict[str, float]] = []
        for cell in self.grid_data:
            grid_id = cell["grid_id"]
            clim = self._climatology_for(grid_id)
            for day in range(settings.LEAD_DAY_MIN, settings.LEAD_DAY_MAX + 1):
                raw = cell["lead_days"].get(str(day))
                if not raw:
                    continue
                state = self._sanitize(raw, day)
                state["hist_bust_freq_pct"] = float(clim["hist_bust_freq_pct"])
                state["hist_mae_mm"] = float(clim["hist_mean_abs_err_mm"])
                states.append(state)
        return states

    def _background_matrix(self, n_samples: int, cache_attr: str) -> np.ndarray:
        cached = getattr(self, cache_attr)
        if cached is not None:
            return cached
        built = build_background(self.feature_names, n_samples, self._all_states())
        setattr(self, cache_attr, built)
        return built

    # -- climatology comparison -------------------------------------------- #

    def _historical_context(
        self, grid_id: str, probability: float, lead_day: int
    ) -> Dict[str, Any]:
        """Compare the live forecast against the region's verification record."""
        clim = self._climatology_for(grid_id)
        hist_freq = float(clim["hist_bust_freq_pct"])
        per_lead = clim.get("per_lead_bust_rate_pct") or []
        offset = lead_day - settings.LEAD_DAY_MIN
        hist_freq_at_lead = (
            float(per_lead[offset]) if 0 <= offset < len(per_lead) else hist_freq
        )
        ratio = round(probability * 100.0 / max(hist_freq_at_lead, 0.5), 2)

        if ratio >= 1.5:
            signal = "ANOMALOUSLY_ELEVATED"
        elif ratio >= 0.8:
            signal = "CONSISTENT_WITH_ARCHIVE"
        else:
            signal = "BELOW_ARCHIVE_AVERAGE"

        return {
            "hist_bust_frequency_pct": hist_freq,
            "hist_bust_frequency_at_lead_pct": round(hist_freq_at_lead, 2),
            "hist_mean_absolute_error_mm": float(clim["hist_mean_abs_err_mm"]),
            "hist_p90_absolute_error_mm": float(clim.get("hist_mae_p90_mm", 0.0)),
            "archive_samples": int(clim.get("archive_samples", 0)),
            "historically_worst_lead_day": int(clim.get("worst_lead_day", 5)),
            "historical_peak_event_type": clim.get("peak_event", "Unknown"),
            "current_vs_historical_ratio": ratio,
            "historical_comparison_signal": signal,
            "archive_provenance": self.training_report.get("archive", {}).get(
                "provenance", "unavailable"
            ),
        }

    # -- risk classification ------------------------------------------------ #

    @staticmethod
    def _classify(probability: float) -> Tuple[str, str, str]:
        if probability >= settings.BUST_RISK_HIGH_THRESHOLD:
            return "HIGH", RISK_COLORS["HIGH"], RELIABILITY_FLAGS["HIGH"]
        if probability >= settings.BUST_RISK_MODERATE_THRESHOLD:
            return "MODERATE", RISK_COLORS["MODERATE"], RELIABILITY_FLAGS["MODERATE"]
        return "LOW", RISK_COLORS["LOW"], RELIABILITY_FLAGS["LOW"]

    # -- batched scoring ---------------------------------------------------- #

    def score_batch(
        self, states: List[Dict[str, float]], lead_day: int, grid_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Score many regions at one lead time without computing attributions.

        Attribution is the expensive part (2^n model evaluations per region), so
        the lead-time profile uses this path and reports probabilities only.
        """
        self._require_ready()
        clean = [self._sanitize(state, lead_day) for state in states]
        matrix = self._feature_matrix(clean, grid_ids)
        probabilities = self._bust_probability(matrix)
        errors = self._expected_error_mm(matrix)

        results: List[Dict[str, Any]] = []
        for idx, state in enumerate(clean):
            probability = round(float(np.clip(probabilities[idx], 0.01, 0.99)), 4)
            risk_level, risk_color, reliability_flag = self._classify(probability)
            results.append(
                {
                    "bust_probability": probability,
                    "risk_level": risk_level,
                    "risk_color": risk_color,
                    "reliability_flag": reliability_flag,
                    "confidence_percentage": round((1.0 - probability) * 100.0, 1),
                    "expected_precip_error_mm": round(float(errors[idx]), 1),
                    "event_type": classify_weather_event(
                        slp=state["slp_hpa"],
                        pwat=state["precipitable_water_mm"],
                        shear=state["wind_shear_divergence"],
                        cape=state["cape_j_kg"],
                        geo_anom=state["geopotential_anomaly_m"],
                        wind=state["surface_wind_knots"],
                        lapse=state["temp_gradient_k"],
                        lead_day=lead_day,
                    )["event_type"],
                }
            )
        return results

    def score(
        self, state: Dict[str, float], lead_day: int, grid_id: str
    ) -> Dict[str, Any]:
        """Score one region at one lead time, including full attribution."""
        self._require_ready()
        clean = self._sanitize(state, lead_day)
        base = self.score_batch([state], lead_day, [grid_id])[0]

        probability = base["bust_probability"]
        attributions, shap_base_value = self.attribution_bundle(clean, grid_id)
        historical = self._historical_context(grid_id, probability, lead_day)
        expected_error = base["expected_precip_error_mm"]

        return {
            "bust_probability": probability,
            "bust_risk_score": probability,
            "shap_base_value": round(shap_base_value, 4),
            "risk_level": base["risk_level"],
            "risk_color": base["risk_color"],
            "reliability_flag": base["reliability_flag"],
            "confidence_percentage": base["confidence_percentage"],
            "lead_day": lead_day,
            "weather_event_classification": classify_weather_event(
                slp=clean["slp_hpa"],
                pwat=clean["precipitable_water_mm"],
                shear=clean["wind_shear_divergence"],
                cape=clean["cape_j_kg"],
                geo_anom=clean["geopotential_anomaly_m"],
                wind=clean["surface_wind_knots"],
                lapse=clean["temp_gradient_k"],
                lead_day=lead_day,
            ),
            "historical_error_context": historical,
            "expected_model_deviation": {
                "precipitation_mm": expected_error,
                "slp_hpa": round(expected_error * 0.16, 2),
                "temperature_c": round(expected_error * 0.075, 1),
            },
            "top_atmospheric_drivers": self._top_drivers(attributions),
            "shap_attributions": attributions,
            "operational_advisory": self.build_advisory(
                probability=probability,
                risk_level=base["risk_level"],
                lead_day=lead_day,
                event_type=base["event_type"],
                historical=historical,
                expected_error=expected_error,
                confidence_pct=base["confidence_percentage"],
            ),
        }

    # -- attribution -------------------------------------------------------- #

    def attribution_bundle(
        self, clean_state: Dict[str, float], grid_id: str, cache_key: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], float]:
        """Exact Shapley attributions plus the v(empty set) baseline they sum to.

        The baseline is returned so that callers can verify additivity themselves:
        `shap_base_value + sum(shap_values)` must equal the model probability.
        """
        if cache_key:
            cached = self._attribution_cache.get(
                (grid_id, clean_state["lead_day"], cache_key)
            )
            if cached is not None:
                return cached

        self._require_ready()
        n_background = (
            settings.SHAP_BACKGROUND_SAMPLES
            if cache_key is None
            else settings.GRID_SHAP_BACKGROUND_SAMPLES
        )
        background = self._background_matrix(
            n_background,
            "_background" if cache_key is None else "_grid_background",
        )
        matrix = self._feature_matrix([clean_state], [grid_id])
        result = exact_interventional_shapley(self._bust_probability, matrix, background)
        values = result["shap_values"][0]
        base_value = float(result["base_value"][0])
        records = self._format_attributions(values, clean_state, grid_id)

        if cache_key:
            self._attribution_cache[(grid_id, int(clean_state["lead_day"]), cache_key)] = (
                records,
                base_value,
            )
        return records, base_value

    def attributions(
        self, clean_state: Dict[str, float], grid_id: str, cache_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Exact interventional Shapley attribution, memoised for grid cells."""
        return self.attribution_bundle(clean_state, grid_id, cache_key)[0]

    def shap_baseline(self, n_background: Optional[int] = None) -> float:
        """Model probability for a completely uninformative average forecast."""
        self._require_ready()
        n_background = n_background or settings.SHAP_BACKGROUND_SAMPLES
        background = self._background_matrix(n_background, "_background")
        return float(self._bust_probability(background).mean())

    def _format_attributions(
        self, values: np.ndarray, state: Dict[str, float], grid_id: str
    ) -> List[Dict[str, Any]]:
        total = float(np.abs(values).sum()) or 1.0
        clim = self._climatology_for(grid_id)
        records: List[Dict[str, Any]] = []

        for idx, name in enumerate(self.feature_names):
            contribution = float(values[idx])
            if name == "hist_bust_freq_pct":
                observed = float(clim["hist_bust_freq_pct"])
            elif name == "hist_mae_mm":
                observed = float(clim["hist_mean_abs_err_mm"])
            else:
                observed = float(state.get(name, 0.0))

            records.append(
                {
                    "feature": name,
                    "name": FEATURE_DESCRIPTIONS.get(name, name),
                    "unit": FEATURE_UNITS.get(name, ""),
                    "value": round(observed, 2),
                    "display_value": f"{observed:.1f}{FEATURE_DISPLAY_SUFFIX.get(name, '')}",
                    "shap_value": round(contribution, 4),
                    "relative_impact_pct": round(abs(contribution) / total * 100.0, 1),
                    "direction": "INCREASES_RISK"
                    if contribution >= 0
                    else "DECREASES_RISK",
                    "explanation": DRIVER_NARRATIVE.get(name, ""),
                }
            )

        records.sort(key=lambda r: abs(r["shap_value"]), reverse=True)
        return records

    @staticmethod
    def _top_drivers(attributions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "feature": record["name"],
                "feature_key": record["feature"],
                "impact_pct": record["relative_impact_pct"],
                "shap_value": record["shap_value"],
                "direction": record["direction"],
                "observed_value": record["display_value"],
                "scientific_explanation": record["explanation"],
            }
            for record in attributions[:3]
        ]

    # -- advisory ----------------------------------------------------------- #

    def build_advisory(
        self,
        probability: float,
        risk_level: str,
        lead_day: int,
        event_type: str,
        historical: Dict[str, Any],
        expected_error: float,
        confidence_pct: float,
    ) -> str:
        """Deterministic operational directive.

        The optional LLM briefing is returned in a separate field and never
        overwrites this, so the system always produces a complete, reproducible
        advisory with no external dependency and no non-determinism in tests.
        """
        ratio = historical["current_vs_historical_ratio"]
        hist_freq = historical["hist_bust_frequency_pct"]
        signal = historical["historical_comparison_signal"]
        threshold = settings.BUST_ERROR_THRESHOLD_MM

        if risk_level == "HIGH":
            return (
                f"HIGH BUST RISK [Day {lead_day}, +{lead_day * 24}h] — {event_type}. "
                f"Calibrated probability of a bust (24h accumulated precipitation error "
                f"above {threshold:.0f} mm) is {probability:.2f}, which is {ratio:.1f}x the "
                f"{hist_freq:.1f}% climatological bust frequency for this region ({signal}). "
                f"Expected precipitation error is about {expected_error:.0f} mm. "
                f"Do not issue deterministic guidance for this region without a confidence "
                f"caveat. Supplement with ensemble quantile guidance, radar nowcasting and "
                f"satellite-derived moisture fields, and pre-agree contingency thresholds."
            )
        if risk_level == "MODERATE":
            return (
                f"ELEVATED UNCERTAINTY [Day {lead_day}, +{lead_day * 24}h] — {event_type}. "
                f"Bust probability {probability:.2f} against a {hist_freq:.1f}% historical "
                f"frequency ({ratio:.1f}x, {signal}); expected precipitation error about "
                f"{expected_error:.0f} mm. Verify against observations and adjacent guidance "
                f"before briefing users, and mark the Day {lead_day} forecast provisional."
            )
        return (
            f"NOMINAL CONFIDENCE [Day {lead_day}, +{lead_day * 24}h] — {event_type}. "
            f"Bust probability {probability:.2f} is {ratio:.1f}x the {hist_freq:.1f}% "
            f"historical frequency for this region, inside the verification envelope. "
            f"Regional forecast confidence {confidence_pct:.1f}%, expected precipitation "
            f"error about {expected_error:.0f} mm. Standard operational dissemination "
            f"is appropriate."
        )

    # -- grid assembly ------------------------------------------------------ #

    def _day_state(self, cell: Dict[str, Any], lead_day: int) -> Dict[str, Any]:
        return cell["lead_days"].get(str(lead_day)) or cell["lead_days"]["1"]

    def get_forecast_grid(self, lead_day: int) -> Dict[str, Any]:
        """Score every region for one lead time."""
        self._require_ready()
        lead_day = int(np.clip(lead_day, settings.LEAD_DAY_MIN, settings.LEAD_DAY_MAX))

        states = [self._day_state(cell, lead_day) for cell in self.grid_data]
        grid_ids = [cell["grid_id"] for cell in self.grid_data]
        scored = self.score_batch(states, lead_day, grid_ids)

        cells: List[Dict[str, Any]] = []
        for cell, state, result in zip(self.grid_data, states, scored):
            clean = self._sanitize(state, lead_day)
            grid_id = cell["grid_id"]
            historical = self._historical_context(
                grid_id, result["bust_probability"], lead_day
            )
            attributions = self.attributions(clean, grid_id, cache_key="grid")
            cells.append(
                {
                    "grid_id": grid_id,
                    "name": cell["name"],
                    "subdivision": cell["subdivision"],
                    "lat": float(cell["lat"]),
                    "lon": float(cell["lon"]),
                    "climate_type": cell["climate_type"],
                    "lead_day": lead_day,
                    "bust_probability": result["bust_probability"],
                    "bust_risk_score": result["bust_probability"],
                    "risk_level": result["risk_level"],
                    "risk_color": result["risk_color"],
                    "reliability_flag": result["reliability_flag"],
                    "confidence_percentage": result["confidence_percentage"],
                    "event_type": result["event_type"],
                    "historical_error_context": historical,
                    "slp_hpa": clean["slp_hpa"],
                    "precipitable_water_mm": clean["precipitable_water_mm"],
                    "wind_shear_divergence": clean["wind_shear_divergence"],
                    "temp_gradient_k": clean["temp_gradient_k"],
                    "cape_j_kg": clean["cape_j_kg"],
                    "ensemble_spread_std": clean["ensemble_spread_std"],
                    "nwp_forecast_precip_mm": clean["nwp_forecast_precip_mm"],
                    "expected_model_deviation": {
                        "precipitation_mm": result["expected_precip_error_mm"],
                        "slp_hpa": round(result["expected_precip_error_mm"] * 0.16, 2),
                        "temperature_c": round(result["expected_precip_error_mm"] * 0.075, 1),
                    },
                    "top_atmospheric_drivers": self._top_drivers(attributions),
                }
            )

        return {
            "status": "OPERATIONAL",
            "model_version": settings.NWP_MODEL_BASE,
            "issuing_agency": "NCMRWF / Ministry of Earth Sciences (MoES)",
            "generated_utc": _utc_now(),
            "lead_day": lead_day,
            "lead_hour": lead_day * 24,
            "bust_definition": {
                "variable": "24h accumulated precipitation",
                "error_threshold_mm": settings.BUST_ERROR_THRESHOLD_MM,
            },
            "domain": DOMAIN_BOUNDS,
            "domain_telemetry": self._domain_telemetry(cells, lead_day),
            "error_prone_areas": self._error_prone_areas(cells),
            "grid_cells": cells,
        }

    def _domain_telemetry(
        self, cells: List[Dict[str, Any]], lead_day: int
    ) -> Dict[str, Any]:
        if not cells:
            return {
                "mean_bust_risk": 0.0,
                "mean_confidence_pct": 0.0,
                "high_risk_cells": 0,
                "moderate_risk_cells": 0,
                "low_risk_cells": 0,
                "error_prone_cells": 0,
                "max_bust_probability": 0.0,
                "min_bust_probability": 0.0,
                "active_lead_day": lead_day,
            }
        probabilities = [c["bust_probability"] for c in cells]
        return {
            "mean_bust_risk": round(float(np.mean(probabilities)), 4),
            "mean_confidence_pct": round(
                float(np.mean([c["confidence_percentage"] for c in cells])), 1
            ),
            "high_risk_cells": sum(1 for c in cells if c["risk_level"] == "HIGH"),
            "moderate_risk_cells": sum(1 for c in cells if c["risk_level"] == "MODERATE"),
            "low_risk_cells": sum(1 for c in cells if c["risk_level"] == "LOW"),
            "error_prone_cells": sum(
                1 for c in cells if c["reliability_flag"] != "RELIABLE"
            ),
            "max_bust_probability": round(max(probabilities), 4),
            "min_bust_probability": round(min(probabilities), 4),
            "active_lead_day": lead_day,
        }

    def _error_prone_areas(self, cells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Regions whose forecast should be treated as unreliable at this lead time."""
        flagged = [c for c in cells if c["reliability_flag"] != "RELIABLE"]
        flagged.sort(key=lambda c: c["bust_probability"], reverse=True)
        return [
            {
                "grid_id": c["grid_id"],
                "name": c["name"],
                "subdivision": c["subdivision"],
                "lat": c["lat"],
                "lon": c["lon"],
                "bust_probability": c["bust_probability"],
                "confidence_percentage": c["confidence_percentage"],
                "risk_level": c["risk_level"],
                "risk_color": c["risk_color"],
                "reliability_flag": c["reliability_flag"],
                "event_type": c["event_type"],
                "hist_bust_freq_pct": c["historical_error_context"][
                    "hist_bust_frequency_pct"
                ],
                "current_vs_historical_ratio": c["historical_error_context"][
                    "current_vs_historical_ratio"
                ],
                "historical_comparison_signal": c["historical_error_context"][
                    "historical_comparison_signal"
                ],
                "expected_precip_error_mm": c["expected_model_deviation"][
                    "precipitation_mm"
                ],
                "primary_driver": (
                    c["top_atmospheric_drivers"][0]["feature_key"]
                    if c["top_atmospheric_drivers"]
                    else None
                ),
            }
            for c in flagged
        ]

    def get_lead_time_profile(self) -> Dict[str, Any]:
        """Domain and per-region risk across the whole Day 1 to Day 10 horizon.

        The problem statement asks for regions *and lead times* with high
        uncertainty, which a single-day map cannot show on its own.
        """
        self._require_ready()

        domain_rows: List[Dict[str, Any]] = []
        per_region: Dict[str, Dict[str, Any]] = {
            region["grid_id"]: {
                "grid_id": region["grid_id"],
                "name": region["name"],
                "subdivision": region["subdivision"],
                "lat": region["lat"],
                "lon": region["lon"],
                "series": [],
            }
            for region in REGIONS
        }

        for day in range(settings.LEAD_DAY_MIN, settings.LEAD_DAY_MAX + 1):
            states = [self._day_state(cell, day) for cell in self.grid_data]
            grid_ids = [cell["grid_id"] for cell in self.grid_data]
            scored = self.score_batch(states, day, grid_ids)

            entries: List[Dict[str, Any]] = []
            for cell, result in zip(self.grid_data, scored):
                entries.append(
                    {
                        "lead_day": day,
                        "lead_hour": day * 24,
                        "bust_probability": result["bust_probability"],
                        "confidence_percentage": result["confidence_percentage"],
                        "risk_level": result["risk_level"],
                        "expected_precip_error_mm": result["expected_precip_error_mm"],
                    }
                )
                per_region[cell["grid_id"]]["series"].append(entries[-1])

            probabilities = [e["bust_probability"] for e in entries]
            domain_rows.append(
                {
                    "lead_day": day,
                    "lead_hour": day * 24,
                    "mean_bust_probability": round(float(np.mean(probabilities)), 4),
                    "mean_confidence_pct": round(
                        float(np.mean([e["confidence_percentage"] for e in entries])), 1
                    ),
                    "max_bust_probability": round(float(max(probabilities)), 4),
                    "high_risk_cells": sum(
                        1 for e in entries if e["risk_level"] == "HIGH"
                    ),
                    "error_prone_cells": sum(
                        1 for e in entries if e["risk_level"] != "LOW"
                    ),
                    "mean_expected_precip_error_mm": round(
                        float(np.mean([e["expected_precip_error_mm"] for e in entries])), 1
                    ),
                }
            )

        worst = max(domain_rows, key=lambda r: r["mean_bust_probability"])
        best = min(domain_rows, key=lambda r: r["mean_bust_probability"])

        region_profiles = []
        for profile in per_region.values():
            series = profile["series"]
            peak = max(series, key=lambda r: r["bust_probability"])
            region_profiles.append(
                {
                    "grid_id": profile["grid_id"],
                    "name": profile["name"],
                    "subdivision": profile["subdivision"],
                    "lat": profile["lat"],
                    "lon": profile["lon"],
                    "mean_bust_probability": round(
                        float(np.mean([r["bust_probability"] for r in series])), 4
                    ),
                    "peak_bust_probability": peak["bust_probability"],
                    "peak_lead_day": peak["lead_day"],
                    "first_high_risk_lead_day": next(
                        (r["lead_day"] for r in series if r["risk_level"] == "HIGH"), None
                    ),
                    "series": series,
                }
            )

        region_profiles.sort(key=lambda r: r["mean_bust_probability"], reverse=True)

        return {
            "status": "OPERATIONAL",
            "model_version": settings.NWP_MODEL_BASE,
            "generated_utc": _utc_now(),
            "lead_day_range": [settings.LEAD_DAY_MIN, settings.LEAD_DAY_MAX],
            "domain_profile": domain_rows,
            "highest_risk_lead_day": worst["lead_day"],
            "lowest_risk_lead_day": best["lead_day"],
            "regions": region_profiles,
        }

    # -- single-cell inspector ---------------------------------------------- #

    def explain_grid_cell(
        self,
        grid_id: str,
        lead_day: int = 1,
        custom_features: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Full explainability breakdown for one region at one lead time."""
        self._require_ready()
        lead_day = int(np.clip(lead_day, settings.LEAD_DAY_MIN, settings.LEAD_DAY_MAX))

        cell = next((c for c in self.grid_data if c["grid_id"] == grid_id), None)
        region = REGION_BY_ID.get(grid_id)

        if cell:
            state = dict(self._day_state(cell, lead_day))
            identity = {
                "name": cell["name"],
                "subdivision": cell["subdivision"],
                "lat": float(cell["lat"]),
                "lon": float(cell["lon"]),
                "climate_type": cell["climate_type"],
            }
        else:
            reference = region or REGION_BY_ID.get("IND-NC-03") or REGIONS[0]
            state = dict(self._reference_state(reference))
            identity = {
                "name": f"Ad-Hoc Sounding ({grid_id})",
                "subdivision": region["subdivision"] if region else "Unregistered domain",
                "lat": float(reference["lat"]),
                "lon": float(reference["lon"]),
                "climate_type": region["climate_type"] if region else "Unclassified",
            }

        rejected: List[str] = []
        if custom_features:
            for key, value in custom_features.items():
                if key not in FEATURE_LIMITS:
                    rejected.append(key)
                    continue
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    rejected.append(key)
                    continue
                low, high = FEATURE_LIMITS[key]
                if not math.isfinite(numeric) or not (low <= numeric <= high):
                    # The value is clamped downstream by _sanitize. Report it so
                    # the caller is not misled into thinking their input was used.
                    rejected.append(key)
                    continue
                state[key] = numeric

        result = self.score(state, lead_day, grid_id)
        result["ai_synoptic_briefing"] = self.generate_ai_bulletin(
            station_name=identity["name"],
            lead_day=lead_day,
            probability=result["bust_probability"],
            top_drivers=result["top_atmospheric_drivers"],
            event_type=result["weather_event_classification"]["event_type"],
            historical=result["historical_error_context"],
        )
        result["grid_id"] = grid_id
        result["observed_features"] = self._sanitize(state, lead_day)
        result["ignored_custom_features"] = rejected
        result["model_metadata"] = self.model_metadata()
        return {**identity, **result}

    def _reference_state(self, region: Dict[str, Any]) -> Dict[str, Any]:
        cell = next(
            (c for c in self.grid_data if c["grid_id"] == region["grid_id"]), None
        )
        if cell:
            return dict(cell["lead_days"]["1"])
        return {
            "slp_hpa": float(region["baseline_slp"]),
            "precipitable_water_mm": float(region["base_pwat"]),
            "cape_j_kg": 1500.0,
            "wind_shear_divergence": 5.0,
            "temp_gradient_k": 6.5,
            "geopotential_anomaly_m": 0.0,
            "rh_700_pct": 60.0,
            "surface_wind_knots": 15.0,
            "nwp_forecast_precip_mm": 20.0,
            "ensemble_spread_std": 2.0,
        }

    def generate_ai_bulletin(
        self,
        station_name: str,
        lead_day: int,
        probability: float,
        top_drivers: List[Dict[str, Any]],
        event_type: str,
        historical: Dict[str, Any],
    ) -> Optional[str]:
        """Optional natural-language briefing from an LLM.

        Disabled by default. When off or failing, the deterministic
        ``operational_advisory`` remains the authoritative output, so a missing
        key or an outage degrades the wording but never the product.
        """
        if not settings.ENABLE_AI_BRIEFING or not settings.GEMINI_API_KEY:
            return None

        try:
            from google import genai

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            driver_summary = ", ".join(
                f"{d['feature']} ({d['impact_pct']:.1f}% of attribution)"
                for d in top_drivers[:3]
            )
            prompt = (
                "You are a senior operational meteorologist at NCMRWF, Ministry of Earth "
                "Sciences, India. Write exactly two sentences of operational synoptic "
                f"guidance for {station_name} at forecast lead day {lead_day} "
                f"(+{lead_day * 24}h). Calibrated forecast-bust probability is "
                f"{probability:.2f}. Dominant regime is {event_type}. Leading attribution "
                f"drivers: {driver_summary}. The region's historical bust frequency is "
                f"{historical['hist_bust_frequency_pct']:.1f}% with mean absolute error "
                f"{historical['hist_mean_absolute_error_mm']:.1f} mm, so the current "
                f"probability is {historical['current_vs_historical_ratio']:.1f}x the "
                "climatological rate. Name the specific NWP failure mechanism and one "
                "concrete mitigation for the forecaster. No greeting, no filler, plain "
                "meteorological prose."
            )
            response = client.chats.create(model=settings.GEMINI_MODEL).send_message(
                prompt
            )
            if response and response.text:
                return response.text.strip()
        except Exception:
            return None
        return None

    def model_metadata(self) -> Dict[str, Any]:
        """Provenance and held-out skill for whatever artifacts are loaded."""
        if not self.is_ready:
            return {"ready": False, "error": self.load_error}

        skill = self.training_report.get("classifier_skill", {})
        reg_skill = self.training_report.get("regressor_skill", {})
        return {
            "ready": True,
            "model_version": settings.VERSION,
            "algorithm": "HistGradientBoostingClassifier with isotonic calibration",
            "error_model_algorithm": "HistGradientBoostingRegressor on sqrt absolute error",
            "attribution_method": "exact interventional Shapley, full 2^n enumeration",
            "trained_utc": self.training_report.get("generated_utc"),
            "feature_names": self.feature_names,
            "feature_schema": self.training_report.get("feature_schema", {}),
            "bust_definition": self.training_report.get("target", {}),
            "archive": self.training_report.get("archive", {}),
            "held_out_skill": {
                "roc_auc": skill.get("roc_auc"),
                "roc_auc_cluster_ci90": skill.get("roc_auc_cluster_ci90"),
                "brier_score": skill.get("brier_score"),
                "brier_skill_score": skill.get("brier_skill_score"),
                "log_loss": skill.get("log_loss"),
                "expected_calibration_error": skill.get("expected_calibration_error"),
                "error_model_mae_mm": reg_skill.get("mae_mm"),
                "error_model_mae_climatology_mm": reg_skill.get("climatology_mae_mm"),
                "error_model_skill_vs_climatology_pct": reg_skill.get(
                    "skill_vs_climatology_pct"
                ),
            },
            "reliability": skill.get("reliability", []),
            "skill_by_lead_day": skill.get("skill_by_lead_day", {}),
            "environment": self.training_report.get("environment", {}),
        }


ml_engine = ForecastBustEngine()
