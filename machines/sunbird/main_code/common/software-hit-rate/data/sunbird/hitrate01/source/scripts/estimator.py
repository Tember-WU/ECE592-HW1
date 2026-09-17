"""Timing-only calibration and classification. No PMU or cache-spec inputs."""
import gzip
import hashlib
from pathlib import Path
import numpy as np


def read_raw(path):
    path = Path(path)
    payload = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
    if not payload or len(payload) % 8:
        raise ValueError("Raw file must contain complete uint64 samples")
    return np.frombuffer(payload, dtype="<u8"), hashlib.sha256(payload).hexdigest()


def fit(hit, miss):
    """Equal class weight; lowest balanced training error, midpoint of ties."""
    hit, miss = np.sort(hit), np.sort(miss)
    if np.median(hit) >= np.median(miss):
        raise ValueError("Calibration classes are not ordered; no valid hit threshold")
    limit = int(max(np.percentile(hit, 99), np.percentile(miss, 99))) + 1
    if limit > 1000000:
        raise ValueError("Calibration dominated by extreme timing values")
    thresholds = np.arange(limit + 1)
    fn = 1 - np.searchsorted(hit, thresholds, side="right") / len(hit)
    fp = np.searchsorted(miss, thresholds, side="right") / len(miss)
    error = (fn + fp) / 2
    best = np.flatnonzero(np.isclose(error, error.min(), rtol=0, atol=1e-12))
    threshold = int(best[len(best) // 2])
    near = np.flatnonzero(error <= error.min() + 0.01)
    return {
        "threshold_ticks": threshold,
        "rule": "hit iff single-access raw ticks <= threshold_ticks",
        "balanced_training_error": float(error[threshold]),
        "hit_false_negative_rate": float(fn[threshold]),
        "miss_false_positive_rate": float(fp[threshold]),
        "sensitivity_thresholds": [int(near.min()), int(near.max())],
        "sensitivity_definition": "Thresholds within one percentage point of minimum balanced training error; not a confidence interval",
        "thresholds": thresholds.tolist(),
        "balanced_errors": error.tolist(),
    }


def estimate(samples, model):
    classified = samples <= model["threshold_ticks"]
    # Whole contiguous blocks, rather than treating serialized accesses as iid.
    blocks = np.array([x.mean() for x in np.array_split(classified, min(100, len(samples)))])
    rng = np.random.default_rng(850085)
    boot = blocks[rng.integers(len(blocks), size=(2000, len(blocks)))].mean(axis=1)
    ci = np.percentile(boot, [2.5, 97.5])
    lo, hi = model["sensitivity_thresholds"]
    return {
        "software_hit_rate": float(classified.mean()),
        "classified_hits": int(classified.sum()),
        "block_bootstrap_95": ci.tolist(),
        "block_count": len(blocks),
        "block_rate_min_max": [float(blocks.min()), float(blocks.max())],
        "threshold_sensitivity_rates": [float((samples <= lo).mean()), float((samples <= hi).mean())],
        "uncertainty_scope": "Conditional on frozen threshold and approximately exchangeable contiguous blocks; does not cover calibration bias or cross-machine drift",
    }


def statistics(x):
    q1, median, q3, p05, p95 = np.percentile(x, [25, 50, 75, 5, 95])
    lower, upper = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    inside = x[(x >= lower) & (x <= upper)]
    return {
        "n": len(x), "mean": float(x.mean()), "std": float(x.std()),
        "median": float(median), "q1": float(q1), "q3": float(q3),
        "p05": float(p05), "p95": float(p95),
        "minimum": int(x.min()), "maximum": int(x.max()),
        "outliers": int(((x < lower) | (x > upper)).sum()),
        "whisker_low": int(inside.min()), "whisker_high": int(inside.max()),
    }
