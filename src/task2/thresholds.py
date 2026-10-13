"""Per-label decision thresholds for Task 2 (macro-F1 rewards getting rare labels right)."""
from __future__ import annotations

import numpy as np

GRID = np.round(np.arange(0.25, 0.851, 0.05), 2)


def best_threshold(p, y, grid=GRID, default: float = 0.5) -> float:
    """Grid value with the best F1 on (p, y); `default` when y has no positive or no value scores.
    When multiple thresholds achieve the same best F1, picks the one closest to 0.45 to prevent collapse."""
    p, y = np.asarray(p, float), np.asarray(y).astype(bool)
    if not y.any():
        return float(default)
    best_f = 0.0
    candidates: list[float] = []
    for t in grid:
        pred = p >= t
        tp = int((pred & y).sum())
        fp = int((pred & ~y).sum())
        fn = int((~pred & y).sum())
        denom = 2 * tp + fp + fn
        f = 2 * tp / denom if denom else 0.0
        if f > best_f + 1e-12:
            best_f = f
            candidates = [float(t)]
        elif abs(f - best_f) <= 1e-12 and best_f > 0:
            candidates.append(float(t))
    if not candidates or best_f <= 0.0:
        return float(default)
    return min(candidates, key=lambda t: abs(t - 0.45))


def tune_thresholds(P, Y, grid=GRID, default: float = 0.5) -> np.ndarray:
    P, Y = np.asarray(P, float), np.asarray(Y).astype(bool)
    return np.array([best_threshold(P[:, j], Y[:, j], grid, default) for j in range(P.shape[1])])


def apply_thresholds(P, thr, min_rate: float = 0.0, max_labels: int | None = None) -> np.ndarray:
    """P >= thr per label; then every label gets at least ceil(min_rate * n) positives (highest P first).
    If max_labels is set, caps each sample to at most max_labels positives by highest margin (P - thr)."""
    P = np.asarray(P, float)
    thr = np.asarray(thr, float)
    pred = P >= thr[None, :]
    k = int(np.ceil(min_rate * P.shape[0])) if min_rate > 0 else 0
    if k:
        for j in range(P.shape[1]):
            if pred[:, j].sum() < k:
                pred[np.argsort(-P[:, j], kind="stable")[:k], j] = True
    if max_labels is not None and max_labels > 0:
        margins = P - thr[None, :]
        for i in range(pred.shape[0]):
            pos = np.where(pred[i])[0]
            if len(pos) > max_labels:
                top = pos[np.argsort(-margins[i, pos], kind="stable")[:max_labels]]
                pred[i] = False
                pred[i, top] = True
    return pred
