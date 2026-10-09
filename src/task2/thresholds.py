"""Per-label decision thresholds for Task 2 (macro-F1 rewards getting rare labels right)."""
from __future__ import annotations

import numpy as np

GRID = np.round(np.arange(0.05, 0.951, 0.05), 2)


def best_threshold(p, y, grid=GRID, default: float = 0.5) -> float:
    """Smallest grid value with the best F1 on (p, y); `default` when y has no positive or no value scores."""
    p, y = np.asarray(p, float), np.asarray(y).astype(bool)
    if not y.any():
        return float(default)
    best_t, best_f = float(default), 0.0  # F1 == 0 everywhere keeps `default`
    for t in grid:
        pred = p >= t
        tp = int((pred & y).sum())
        fp = int((pred & ~y).sum())
        fn = int((~pred & y).sum())
        f = 2 * tp / (2 * tp + fp + fn)
        if f > best_f + 1e-12:
            best_t, best_f = float(t), f
    return best_t


def tune_thresholds(P, Y, grid=GRID, default: float = 0.5) -> np.ndarray:
    P, Y = np.asarray(P, float), np.asarray(Y).astype(bool)
    return np.array([best_threshold(P[:, j], Y[:, j], grid, default) for j in range(P.shape[1])])


def apply_thresholds(P, thr, min_rate: float = 0.0) -> np.ndarray:
    """P >= thr per label; then every label gets at least ceil(min_rate * n) positives (highest P first)."""
    P = np.asarray(P, float)
    pred = P >= np.asarray(thr, float)[None, :]
    k = int(np.ceil(min_rate * P.shape[0])) if min_rate > 0 else 0
    if k:
        for j in range(P.shape[1]):
            if pred[:, j].sum() < k:
                pred[np.argsort(-P[:, j], kind="stable")[:k], j] = True
    return pred
