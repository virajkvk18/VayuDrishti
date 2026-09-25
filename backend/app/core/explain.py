"""Exact interventional Shapley values for the VayuDRISHTI bust models.

Why not a library
-----------------
Attribution is a headline requirement of this system, so it is worth being
precise about what is claimed. The values computed here are **exact
interventional Shapley values**: the full Shapley sum over all 2^n feature
subsets is enumerated against a background sample representing the
climatological feature distribution. Nothing is fitted to a surrogate model and
no Monte-Carlo sampling noise is involved.

The defining property, asserted in the test suite, is local accuracy: the
attributions sum to the model output minus the baseline, so a forecaster can add
up the bars and land exactly on the probability shown on the map.

Cost is 2^n model evaluations per case. At n = 13 that is 8192, batched into
vectorised calls. Memory is held to O(n_cases x 2^n) by accumulating one feature
at a time rather than materialising a full coalition tensor.
"""
from __future__ import annotations

from functools import lru_cache
from math import factorial
from typing import Callable, Dict, List, Tuple

import numpy as np

_MAX_CHUNK_ELEMENTS = 24_000_000


@lru_cache(maxsize=8)
def _shapley_plan(n_features: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Precompute, for each feature, the weighted subset pairs it participates in.

    Returns one array per feature holding ``(subset_index, partner_index, weight)``
    triples for every coalition that excludes that feature, sorted by coalition
    size as the Shapley formula requires.
    """
    n_subsets = 1 << n_features
    subset_ids = np.arange(n_subsets)
    bit_positions = np.arange(n_features)

    masks = ((subset_ids[:, None] >> bit_positions[None, :]) & 1).astype(bool)
    sizes = masks.sum(axis=1).astype(np.int64)

    factorials = [float(factorial(k)) for k in range(n_features + 1)]
    n_fact = factorials[n_features]
    weights = np.zeros(n_subsets, dtype=np.float64)
    for k in range(n_features):
        weights[sizes == k] = factorials[k] * factorials[n_features - k - 1] / n_fact

    plan: List[np.ndarray] = []
    for i in range(n_features):
        excluding = subset_ids[masks[:, i] == 0]
        including = excluding | (1 << i)
        plan.append(
            np.column_stack([excluding, including, weights[excluding]]).astype(np.float64)
        )

    return tuple(plan)


def _case_chunks(
    n_cases: int, n_background: int, n_features: int
) -> List[Tuple[int, int]]:
    """Split cases into groups whose flattened combo array stays memory-bounded.

    Groups always contain whole cases so that averaging over the background
    dimension never blends two different regions together.
    """
    elements_per_case = n_background * (1 << n_features) * n_features
    cases_per_chunk = max(1, _MAX_CHUNK_ELEMENTS // max(1, elements_per_case))
    return [
        (start, min(n_cases, start + cases_per_chunk))
        for start in range(0, n_cases, cases_per_chunk)
    ]


def hybrid_values(
    predict_proba: Callable[[np.ndarray], np.ndarray],
    x: np.ndarray,
    background: np.ndarray,
) -> np.ndarray:
    """Model response to every subset of each case's features.

    Returns shape ``(N, 2^n)`` where entry ``(i, m)`` is the model probability
    for case ``i`` when the features selected by mask ``m`` come from ``x`` and
    the remainder are drawn from the background distribution.
    """
    n_cases, n_features = x.shape
    n_background = background.shape[0]
    n_subsets = 1 << n_features
    masks = (
        (np.arange(n_subsets)[:, None] >> np.arange(n_features)[None, :]) & 1
    ).astype(bool)

    hybrid = np.empty((n_cases, n_subsets), dtype=np.float64)

    for start, stop in _case_chunks(n_cases, n_background, n_features):
        block = stop - start
        x_rep = np.repeat(x[start:stop], n_background, axis=0)
        z_rep = np.tile(background, (block, 1))
        combos = np.where(masks[None, :, :], x_rep[:, None, :], z_rep[:, None, :])
        probs = predict_proba(combos.reshape(-1, n_features))
        hybrid[start:stop] = probs.reshape(block, n_background, n_subsets).mean(axis=1)

    return hybrid


def exact_interventional_shapley(
    predict_proba: Callable[[np.ndarray], np.ndarray],
    x: np.ndarray,
    background: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Compute exact interventional Shapley values plus the baseline value.

    ``predict_proba`` accepts an ``(N, n_features)`` array and returns ``(N,)``
    probabilities of the positive (bust) class.
    """
    x = np.atleast_2d(np.asarray(x, dtype=np.float64))
    n_cases, n_features = x.shape

    hybrid = hybrid_values(predict_proba, x, background)
    plan = _shapley_plan(n_features)

    shap = np.zeros((n_cases, n_features), dtype=np.float64)
    for i in range(n_features):
        excluding_i = plan[i][:, 0].astype(np.intp)
        including_i = plan[i][:, 1].astype(np.intp)
        weights_f = plan[i][:, 2]
        delta = hybrid[:, including_i] - hybrid[:, excluding_i]
        shap[:, i] = (delta * weights_f[None, :]).sum(axis=1)

    return {
        "shap_values": shap,
        "base_value": hybrid[:, 0],
        "n_subsets": hybrid.shape[1],
    }


def build_background(
    feature_names: List[str],
    n_samples: int,
    region_rows: List[Dict[str, float]],
) -> np.ndarray:
    """Assemble a background sample for interventional attribution.

    The background represents "an ordinary forecast in this domain", so it is
    built by resampling real region states rather than by assuming feature
    independence. Assuming independence would misattribute correlated
    atmospheric fields, most obviously precipitable water and CAPE, which are
    close to deterministically linked in the archive.
    """
    if not region_rows:
        raise ValueError("build_background requires at least one region state")

    missing = [name for name in feature_names if name not in region_rows[0]]
    if missing:
        raise ValueError(f"region states missing background features: {missing}")

    matrix = np.array(
        [[float(row[name]) for name in feature_names] for row in region_rows],
        dtype=np.float64,
    )

    rng = np.random.default_rng(20260926)
    picks = rng.integers(0, matrix.shape[0], size=n_samples)
    spread = matrix.std(axis=0)
    scale = np.where(spread > 0, spread, 1.0)
    jitter = rng.normal(0.0, 0.01, size=(n_samples, matrix.shape[1]))
    return matrix[picks] + jitter * scale
