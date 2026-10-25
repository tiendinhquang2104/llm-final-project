"""F-cls decisions: per-label thresholds (chosen out-of-fold on gold) + the gold labelling rules.

Rules (docs/task2_teacher_rules.md, the same ones the CoT pipeline applies):
- G5: fully commented submission -> ["Lỗi style"] only;
- G4: "Lỗi biên dịch" := the self-compiled log has a compiler error; a compile error keeps at most
  `compile_max_extra` other labels (the cause), highest probability first;
- G1: at most `max_labels` labels, highest probability first;
- "Lỗi edge case" never occurs in gold (0/32): its threshold is a fixed high value, never tuned.
"""
from __future__ import annotations

import numpy as np

from src.task2.compile import has_compile_error
from src.task2.evaluator import f1_scores
from src.task2.labels import LABELS
from src.task2.thresholds import GRID, tune_thresholds

EDGE = "Lỗi edge case"
COMPILE = "Lỗi biên dịch"
STYLE = "Lỗi style"


def decide(probs: dict, rec: dict, thr: dict, pp: dict) -> list[str]:
    if pp.get("all_commented_style", True) and rec.get("all_commented"):
        return [STYLE]
    labels = [lab for lab in LABELS if probs[lab] >= thr[lab]]
    log = rec.get("compile_log")
    if pp.get("compile_rule", True) and log is not None:
        labels = [lab for lab in labels if lab != COMPILE]
        if has_compile_error(log):
            extra = sorted(labels, key=lambda lab: -probs[lab])[:int(pp.get("compile_max_extra", 1))]
            labels = [COMPILE, *extra]
    cap = int(pp.get("max_labels", 3))
    if len(labels) > cap:
        first = [COMPILE] if COMPILE in labels else []
        rest = sorted((lab for lab in labels if lab != COMPILE), key=lambda lab: -probs[lab])
        labels = first + rest[:cap - len(first)]
    return [lab for lab in LABELS if lab in labels]


def fixed_thresholds(pp: dict, value: float | None = None) -> dict:
    t = float(pp.get("default_threshold", 0.5) if value is None else value)
    out = {lab: t for lab in LABELS}
    out[EDGE] = max(t, float(pp.get("edge_case_threshold", 0.9)))
    return out


def tuned_thresholds(P: np.ndarray, Y: np.ndarray, pp: dict) -> dict:
    """Per-label threshold with the best F1 on (P, Y) (src/task2/thresholds.py); labels without a positive keep
    the default; "Lỗi edge case" keeps its fixed value."""
    t = tune_thresholds(P, Y, GRID, default=float(pp.get("default_threshold", 0.5)))
    out = {lab: float(v) for lab, v in zip(LABELS, t)}
    out[EDGE] = fixed_thresholds(pp)[EDGE]
    return out


def matrix(prob_rows: list[dict], ids: list[str]) -> np.ndarray:
    by = {r["id"]: r["probs"] for r in prob_rows}
    return np.array([[by[i][lab] for lab in LABELS] for i in ids], float)


def score(ids: list[str], P: np.ndarray, recs: dict, gold: dict, thr: dict, pp: dict) -> tuple[dict, dict]:
    pred = {i: decide(dict(zip(LABELS, P[k])), recs[i], thr, pp) for k, i in enumerate(ids)}
    return f1_scores({i: gold[i] for i in ids}, pred), pred


def cross_fold_thresholds(fold_ids: dict[str, list[str]], P_by_fold: dict, Y_by_fold: dict, pp: dict) -> dict:
    """Honest per-label thresholds: each fold is decided with thresholds tuned on the OTHER folds' OOF scores."""
    out = {}
    for f in fold_ids:
        others = [g for g in fold_ids if g != f]
        if not others:
            out[f] = fixed_thresholds(pp)
            continue
        P = np.vstack([P_by_fold[g] for g in others])
        Y = np.vstack([Y_by_fold[g] for g in others])
        out[f] = tuned_thresholds(P, Y, pp)
    return out
