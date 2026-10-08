"""Task-agnostic metrics. Task 1: QWK (primary) and MAE on the 0-10 total score."""
from __future__ import annotations


def quadratic_weighted_kappa(y_true: list[int], y_pred: list[int], min_rating: int = 0,
                             max_rating: int = 10) -> float:
    """Cohen's kappa with quadratic weights over the fixed rating range [min_rating, max_rating]."""
    if len(y_true) != len(y_pred):
        raise ValueError("length mismatch")
    if not y_true:
        return float("nan")
    k = max_rating - min_rating + 1
    clip = lambda v: min(max(int(v), min_rating), max_rating) - min_rating  # noqa: E731
    t = [clip(v) for v in y_true]
    p = [clip(v) for v in y_pred]
    n = len(t)
    observed = [[0.0] * k for _ in range(k)]
    for a, b in zip(t, p):
        observed[a][b] += 1
    hist_t = [t.count(i) for i in range(k)]
    hist_p = [p.count(i) for i in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / (k - 1) ** 2
            num += w * observed[i][j]
            den += w * hist_t[i] * hist_p[j] / n
    if den == 0:
        # Both raters constant: agreement is perfect only if they agree everywhere.
        return 1.0 if t == p else 0.0
    return 1.0 - num / den


def mean_absolute_error(y_true: list[float], y_pred: list[float]) -> float:
    if not y_true:
        return float("nan")
    return sum(abs(a - b) for a, b in zip(y_true, y_pred)) / len(y_true)
