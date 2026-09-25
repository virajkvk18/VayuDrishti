"""Training pipeline for the VayuDRISHTI forecast-bust models.

Run with::

    python -m app.core.train

Produces three artifacts in ``app/ml_models/``:

``bust_model.joblib``
    Isotonic-calibrated gradient-boosted classifier estimating
    ``P(24h precipitation error > threshold)``.
``error_model.joblib``
    Gradient-boosted regressor estimating the conditional mean 24h
    precipitation error magnitude in millimetres.
``training_report.json``
    Held-out skill metrics, reliability tables and the derived regional
    climatology served by the API.

Methodological notes
--------------------
*Cases within a region are strongly correlated*, so a naive train/test split
overstates confidence in the skill numbers. All confidence intervals here are
**cluster bootstrap** intervals that resample whole regions, not individual
cases, which is the statistically defensible unit for this design.
"""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import sklearn
from joblib import dump
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, roc_auc_score

from app.core.archive import (
    ARCHIVE_FEATURES,
    FEATURE_DESCRIPTIONS,
    FEATURE_UNITS,
    build_archive,
)
from app.core.config import settings
from app.core.regions import REGIONS

ARTIFACT_CLF = "bust_model.joblib"
ARTIFACT_REG = "error_model.joblib"
ARTIFACT_REPORT = "training_report.json"
ARCHIVE_SEED = 20260926
ARCHIVE_SAMPLES = 60000
N_BOOTSTRAP = 400
ERROR_TARGET_TRANSFORM = "sqrt"


# --------------------------------------------------------------------------- #
# Metrics helpers
# --------------------------------------------------------------------------- #


def reliability_table(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> List[Dict[str, float]]:
    """Observed bust frequency within equal-width forecast probability bins."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_index = np.clip(np.digitize(y_prob, edges[1:-1], right=False), 0, n_bins - 1)
    rows: List[Dict[str, float]] = []
    for b in range(n_bins):
        mask = bin_index == b
        count = int(mask.sum())
        rows.append(
            {
                "bin_lower": round(float(edges[b]), 3),
                "bin_upper": round(float(edges[b + 1]), 3),
                "n_cases": count,
                "mean_forecast_probability": round(float(y_prob[mask].mean()), 4)
                if count
                else None,
                "observed_bust_frequency": round(float(y_true[mask].mean()), 4)
                if count
                else None,
            }
        )
    return rows


def expected_calibration_error(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> float:
    """Population ECE across equal-width probability bins, weighted by bin mass."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_index = np.clip(np.digitize(y_prob, edges[1:-1], right=False), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        mask = bin_index == b
        if not np.any(mask):
            continue
        ece += (mask.sum() / len(y_true)) * abs(
            y_true[mask].mean() - y_prob[mask].mean()
        )
    return float(ece)


def cluster_bootstrap_auc_ci(
    y_true: np.ndarray,
    y_score: np.ndarray,
    clusters: np.ndarray,
    n_boot: int = N_BOOTSTRAP,
    alpha: float = 0.05,
    seed: int = 7,
) -> Tuple[float, float]:
    """Percentile CI for ROC-AUC resampling whole clusters (regions) with replacement.

    Resampling cases individually would treat 60000 near-duplicate synoptic
    states as 60000 independent pieces of evidence. They are not: a handful of
    regions generate most of the spread. Resampling the region is the honest
    approximation to "what if we had observed different synoptic situations".
    """
    rng = np.random.default_rng(seed)
    unique = np.unique(clusters)
    by_cluster = {c: np.flatnonzero(clusters == c) for c in unique}
    scores: List[float] = []

    for _ in range(n_boot):
        picked = rng.choice(unique, size=len(unique), replace=True)
        idx = np.concatenate([by_cluster[c] for c in picked])
        if len(np.unique(y_true[idx])) < 2:
            continue
        scores.append(float(roc_auc_score(y_true[idx], y_score[idx])))

    if not scores:
        return float("nan"), float("nan")
    lo = float(np.percentile(scores, 100 * alpha / 2))
    hi = float(np.percentile(scores, 100 * (1 - alpha / 2)))
    return lo, hi


def skill_vs_climatology(
    y_true: np.ndarray, y_pred: np.ndarray
) -> Tuple[float, float]:
    """Return ``(brier, brier_skill_score)`` relative to the base-rate forecast."""
    brier = float(brier_score_loss(y_true, y_pred))
    base = np.full(len(y_pred), float(y_true.mean()), dtype=np.float64)
    brier_ref = float(brier_score_loss(y_true, base))
    return brier, float(1.0 - brier / brier_ref) if brier_ref > 0 else 0.0


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #


def train(n_samples: int = ARCHIVE_SAMPLES, seed: int = ARCHIVE_SEED) -> Dict[str, Any]:
    print(f"[1/6] Synthesising verification archive ({n_samples} cases)...")
    archive = build_archive(n_samples=n_samples, seed=seed)
    X: np.ndarray = archive["X"]
    y: np.ndarray = archive["y_bust"]
    abs_err: np.ndarray = archive["y_abs_error"]
    region_idx: np.ndarray = archive["region_idx"]
    leads: np.ndarray = archive["lead_day"]
    train_idx: np.ndarray = archive["train_idx"]

    remaining = np.setdiff1d(np.arange(len(y)), train_idx)
    rng = np.random.default_rng(seed + 1)
    rng.shuffle(remaining)
    n_val = len(remaining) // 2
    val_idx, test_idx = remaining[:n_val], remaining[n_val:]

    print(
        f"      split -> train {len(train_idx)} | val {len(val_idx)} | test {len(test_idx)}"
    )
    print(f"      base bust rate: train {y[train_idx].mean():.3f} | test {y[test_idx].mean():.3f}")

    print("[2/6] Fitting isotonic-calibrated gradient-boosted classifier...")
    base_clf = HistGradientBoostingClassifier(
        loss="log_loss",
        learning_rate=0.06,
        max_iter=400,
        max_leaf_nodes=31,
        min_samples_leaf=60,
        l2_regularization=1.0,
        early_stopping=True,
        n_iter_no_change=25,
        validation_fraction=0.12,
        random_state=seed,
    )
    # ensemble=False fits a single base estimator on the full training split and
    # one isotonic map on its out-of-fold predictions. That keeps inference to a
    # single tree pass plus a 1-D interpolation, which matters because the
    # explainer evaluates the model 8192 times per attributed region.
    classifier = CalibratedClassifierCV(base_clf, method="isotonic", cv=5, ensemble=False)
    classifier.fit(X[train_idx], y[train_idx])

    val_prob = classifier.predict_proba(X[val_idx])[:, 1]
    val_auc = float(roc_auc_score(y[val_idx], val_prob))
    print(f"      validation ROC-AUC: {val_auc:.4f}")

    print("[3/6] Fitting gradient-boosted error-magnitude regressor...")
    if ERROR_TARGET_TRANSFORM == "sqrt":
        target = np.sqrt(abs_err)
    elif ERROR_TARGET_TRANSFORM == "log1p":
        target = np.log1p(abs_err)
    else:
        target = abs_err

    regressor = HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.06,
        max_iter=400,
        max_leaf_nodes=31,
        min_samples_leaf=60,
        l2_regularization=1.0,
        early_stopping=True,
        n_iter_no_change=25,
        validation_fraction=0.12,
        random_state=seed,
    )
    regressor.fit(X[train_idx], target[train_idx])

    print("[4/6] Scoring held-out test split...")
    test_prob = classifier.predict_proba(X[test_idx])[:, 1]
    test_pred_err = _inverse_transform(regressor.predict(X[test_idx]))
    test_true_err = abs_err[test_idx]
    test_clusters = region_idx[test_idx]
    test_leads = leads[test_idx]
    test_y = y[test_idx]

    auc = float(roc_auc_score(test_y, test_prob))
    auc_lo, auc_hi = cluster_bootstrap_auc_ci(test_y, test_prob, test_clusters)
    brier, bss = skill_vs_climatology(test_y, test_prob)
    ll = float(log_loss(test_y, test_prob, labels=[0, 1]))
    ece = expected_calibration_error(test_y, test_prob)
    sharpness = float(np.std(test_prob))

    reg_mae = float(mean_absolute_error(test_true_err, test_pred_err))
    reg_rmse = float(np.sqrt(np.mean((test_true_err - test_pred_err) ** 2)))
    ref_mae = float(mean_absolute_error(test_true_err, np.full_like(test_pred_err, test_true_err.mean())))
    ss_res = float(np.sum((test_true_err - test_pred_err) ** 2))
    ss_tot = float(np.sum((test_true_err - test_true_err.mean()) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    print(f"      ROC-AUC {auc:.4f} (cluster-bootstrap 90% CI {auc_lo:.4f}-{auc_hi:.4f})")
    print(f"      Brier {brier:.4f} | BSS {bss:+.4f} | LogLoss {ll:.4f} | ECE {ece:.4f}")
    print(f"      Error MAE {reg_mae:.2f} mm (climatology {ref_mae:.2f} mm) | R2 {r2:+.4f}")

    print("[5/6] Computing per-lead-time skill breakdown...")
    by_lead: Dict[str, Dict[str, float]] = {}
    for day in range(settings.LEAD_DAY_MIN, settings.LEAD_DAY_MAX + 1):
        mask = test_leads == day
        if not np.any(mask):
            continue
        day_brier, day_bss = skill_vs_climatology(test_y[mask], test_prob[mask])
        by_lead[f"day_{day}"] = {
            "n_cases": int(mask.sum()),
            "bust_rate": round(float(test_y[mask].mean()), 4),
            "roc_auc": round(float(roc_auc_score(test_y[mask], test_prob[mask])), 4)
            if len(np.unique(test_y[mask])) > 1
            else None,
            "brier": round(day_brier, 5),
            "brier_skill_score": round(day_bss, 5),
            "mean_forecast_probability": round(float(test_prob[mask].mean()), 4),
            "observed_bust_frequency": round(float(test_y[mask].mean()), 4),
        }

    print("[6/6] Persisting artifacts...")
    out_dir = Path(settings.resolved_artifact_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dump(
        {
            "classifier": classifier,
            "feature_names": list(ARCHIVE_FEATURES),
            "threshold_mm": settings.BUST_ERROR_THRESHOLD_MM,
            "archive_seed": seed,
            "archive_samples": n_samples,
        },
        out_dir / ARTIFACT_CLF,
    )
    dump(
        {
            "regressor": regressor,
            "feature_names": list(ARCHIVE_FEATURES),
            "target_transform": ERROR_TARGET_TRANSFORM,
        },
        out_dir / ARTIFACT_REG,
    )

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "model_version": settings.VERSION,
        "target": {
            "definition": "24h accumulated precipitation verification bust",
            "error_threshold_mm": settings.BUST_ERROR_THRESHOLD_MM,
            "regressor_target_transform": ERROR_TARGET_TRANSFORM,
        },
        "archive": {
            "n_samples": n_samples,
            "seed": seed,
            "n_regions": len(REGIONS),
            "n_train": int(len(train_idx)),
            "n_val": int(len(val_idx)),
            "n_test": int(len(test_idx)),
            "train_bust_rate": round(float(y[train_idx].mean()), 4),
            "test_bust_rate": round(float(test_y.mean()), 4),
            "provenance": "synthetic proxy for the NCMRWF verification archive",
        },
        "classifier_skill": {
            "roc_auc": round(auc, 4),
            "roc_auc_cluster_ci90": [round(auc_lo, 4), round(auc_hi, 4)],
            "brier_score": round(brier, 5),
            "brier_skill_score": round(bss, 5),
            "log_loss": round(ll, 5),
            "expected_calibration_error": round(ece, 5),
            "sharpness_std_of_probability": round(sharpness, 4),
            "validation_roc_auc": round(val_auc, 4),
            "reliability": reliability_table(test_y, test_prob),
            "skill_by_lead_day": by_lead,
        },
        "regressor_skill": {
            "mae_mm": round(reg_mae, 3),
            "rmse_mm": round(reg_rmse, 3),
            "climatology_mae_mm": round(ref_mae, 3),
            "r2": round(r2, 4),
            "skill_vs_climatology_pct": round(100.0 * (1.0 - reg_mae / ref_mae), 2)
            if ref_mae > 0
            else 0.0,
        },
        "feature_schema": {
            name: {
                "unit": FEATURE_UNITS.get(name, ""),
                "description": FEATURE_DESCRIPTIONS.get(name, ""),
            }
            for name in ARCHIVE_FEATURES
        },
        "regional_climatology": archive["climatology"],
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
        },
    }

    with open(out_dir / ARTIFACT_REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"\nArtifacts written to {out_dir}")
    return report


def _inverse_transform(pred: np.ndarray) -> np.ndarray:
    if ERROR_TARGET_TRANSFORM == "sqrt":
        return np.clip(np.square(pred), 0.0, None)
    if ERROR_TARGET_TRANSFORM == "log1p":
        return np.clip(np.expm1(pred), 0.0, None)
    return np.clip(pred, 0.0, None)


if __name__ == "__main__":
    try:
        train()
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"Training failed: {exc}", file=sys.stderr)
        raise
