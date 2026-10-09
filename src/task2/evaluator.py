"""Task 2 metrics (macro/micro-F1 over the 10 labels) and the predictions.json format check."""
from __future__ import annotations

import json
from pathlib import Path

from src.task2.labels import LABELS, normalize_label, normalize_labels

NAN = float("nan")


def f1_scores(gold: dict[str, list[str]], pred: dict[str, list[str]]) -> dict:
    """Scores on the ids of `gold`. macro_f1 follows sklearn (label absent on both sides -> F1 0);
    macro_f1_skip_absent averages only labels that occur in gold or predictions."""
    ids = sorted(gold)
    per_label, tp_all, fp_all, fn_all = {}, 0, 0, 0
    for lab in LABELS:
        tp = fp = fn = 0
        for sid in ids:
            g, p = lab in gold[sid], lab in (pred.get(sid) or [])
            tp += g and p
            fp += p and not g
            fn += g and not p
        denom = 2 * tp + fp + fn
        per_label[lab] = {"precision": tp / (tp + fp) if tp + fp else None,
                          "recall": tp / (tp + fn) if tp + fn else None,
                          "f1": 2 * tp / denom if denom else None,
                          "support": tp + fn, "n_pred": tp + fp}
        tp_all, fp_all, fn_all = tp_all + tp, fp_all + fp, fn_all + fn
    f1s = [v["f1"] for v in per_label.values()]
    present = [f for f in f1s if f is not None]
    micro_denom = 2 * tp_all + fp_all + fn_all
    return {
        "n": len(ids),
        "macro_f1": sum(f or 0.0 for f in f1s) / len(LABELS),
        "macro_f1_skip_absent": sum(present) / len(present) if present else NAN,
        "micro_f1": 2 * tp_all / micro_denom if micro_denom else NAN,
        "exact_match": (sum(set(gold[s]) == set(pred.get(s) or []) for s in ids) / len(ids)) if ids else NAN,
        "per_label": per_label,
    }


def validate_predictions(preds, expected_ids=None) -> list[str]:
    """Errors in a Task 2 predictions.json payload (empty list = valid)."""
    if not isinstance(preds, list):
        return ["top-level must be a list"]
    errs, seen = [], set()
    for i, p in enumerate(preds):
        sid = p.get("sample_id") if isinstance(p, dict) else None
        if not sid:
            errs.append(f"[{i}] missing sample_id")
            continue
        if sid in seen:
            errs.append(f"{sid}: duplicate sample_id")
        seen.add(sid)
        labels = (p.get("output") or {}).get("taxonomy_error")
        if not isinstance(labels, list):
            errs.append(f"{sid}: taxonomy_error must be a list")
            continue
        for lab in labels:
            if normalize_label(lab) is None:
                errs.append(f"{sid}: unknown label {lab!r}")
    if expected_ids is not None:
        expected = set(expected_ids)
        if expected - seen:
            errs.append(f"missing {len(expected - seen)} sample_ids, e.g. {sorted(expected - seen)[:5]}")
        if seen - expected:
            errs.append(f"unexpected {len(seen - expected)} sample_ids, e.g. {sorted(seen - expected)[:5]}")
    return errs


def to_submission(labels_by_id: dict[str, list[str]], ids: list[str]) -> list[dict]:
    """One record per id (missing prediction -> []), labels canonicalised."""
    return [{"sample_id": sid, "output": {"taxonomy_error": normalize_labels(labels_by_id.get(sid) or [])}}
            for sid in ids]


def write_submission(path, labels_by_id: dict[str, list[str]], ids: list[str]) -> list[dict]:
    sub = to_submission(labels_by_id, ids)
    errs = validate_predictions(sub, ids)
    if errs:
        raise ValueError(f"invalid Task 2 predictions: {errs[:5]}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sub, ensure_ascii=False, indent=1), encoding="utf-8")
    return sub
