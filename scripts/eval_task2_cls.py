"""Score F-cls out-of-fold on the 32 gold samples, pick the thresholds, write predictions.json for the public set.

    python scripts/eval_task2_cls.py [--tag lr1e-4] [--out outputs/task2/cls/report]

Reads <out-root>/<name>__EX01|EX02[_tag]/probs_gold.jsonl (fold runs) and <name>__all[_tag]/probs_public.jsonl.
Three gold numbers, all out-of-fold:
- fixed: one threshold (0.5; edge case 0.9);
- cross-fold tuned (honest): each exam decided with per-label thresholds tuned on the OTHER exam;
- in-sample tuned (optimistic, for reference only): thresholds tuned on the same 32 samples.
The public predictions use per-label thresholds tuned on all 32 OOF scores when the honest cross-fold number
beats the fixed one, else the fixed thresholds. Nothing is chosen on public outputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.task2.cls_data import folds, read_jsonl  # noqa: E402
from src.task2.cls_post import (cross_fold_thresholds, decide, fixed_thresholds, matrix, score,  # noqa: E402
                                tuned_thresholds)
from src.task2.evaluator import f1_scores, validate_predictions, write_submission  # noqa: E402
from src.task2.labels import LABELS, to_vector  # noqa: E402
from src.utils.config import load_config  # noqa: E402


def _short(m: dict) -> dict:
    return {k: round(m[k], 4) for k in ("macro_f1", "micro_f1", "exact_match", "macro_f1_skip_absent")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/task2/cls_qwen7b.yaml")
    ap.add_argument("--records")
    ap.add_argument("--out-root", default="outputs/task2/cls")
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", help="report folder (default: <out-root>/<name>_report[_tag])")
    a = ap.parse_args()

    cfg = load_config(ROOT / a.config)
    pp = cfg.get("postprocess") or {}
    records = read_jsonl(ROOT / (a.records or Path(cfg["data"]["cls_dir"]) / "records.jsonl"))
    recs = {r["id"]: r for r in records}
    gold = {r["id"]: r["labels"] for r in records if r["source"] == "gold"}
    suffix = f"_{a.tag}" if a.tag else ""
    base = ROOT / a.out_root
    out = Path(a.out) if a.out else base / f"{cfg['name']}_report{suffix}"
    out.mkdir(parents=True, exist_ok=True)

    fold_ids, P_f, Y_f = {}, {}, {}
    for f in folds(records):
        path = base / f"{cfg['name']}__{f}{suffix}" / "probs_gold.jsonl"
        if not path.exists():
            raise SystemExit(f"missing {path}: train the fold first (scripts/train_task2_cls.py --holdout {f})")
        rows = read_jsonl(path)
        fold_ids[f] = [r["id"] for r in rows]
        P_f[f] = matrix(rows, fold_ids[f])
        Y_f[f] = np.array([to_vector(gold[i]) for i in fold_ids[f]])
    ids = [i for f in fold_ids for i in fold_ids[f]]
    P = np.vstack([P_f[f] for f in fold_ids])
    Y = np.vstack([Y_f[f] for f in fold_ids])

    fixed = fixed_thresholds(pp)
    m_fixed, pred_fixed = score(ids, P, recs, gold, fixed, pp)
    cross = cross_fold_thresholds(fold_ids, P_f, Y_f, pp)
    pred_cross = {}
    for f in fold_ids:
        pred_cross.update(score(fold_ids[f], P_f[f], recs, gold, cross[f], pp)[1])
    m_cross = f1_scores(gold, pred_cross)
    tuned_all = tuned_thresholds(P, Y, pp)
    m_insample, _ = score(ids, P, recs, gold, tuned_all, pp)
    use_tuned = m_cross["macro_f1"] > m_fixed["macro_f1"]
    final_thr = tuned_all if use_tuned else fixed
    metrics = {"n_gold": len(ids), "folds": {f: len(v) for f, v in fold_ids.items()},
               "fixed": m_fixed, "cross_fold_tuned": m_cross, "in_sample_tuned_optimistic": m_insample,
               "thresholds": {"fixed": fixed, "cross_fold": cross, "tuned_all": tuned_all,
                              "used_for_public": "tuned_all" if use_tuned else "fixed"}}
    print(json.dumps({"fixed": _short(m_fixed), "cross_fold_tuned": _short(m_cross),
                      "in_sample_tuned": _short(m_insample), "public_thresholds": metrics["thresholds"]["used_for_public"]},
                     ensure_ascii=False, indent=1))

    full = []
    for k, i in enumerate(ids):
        full.append({"id": i, "gold": gold[i], "pred_fixed": pred_fixed[i], "pred_cross": pred_cross[i],
                     "probs": dict(zip(LABELS, P[k].round(4).tolist()))})
    (out / "oof_gold.json").write_text(json.dumps(full, ensure_ascii=False, indent=1), encoding="utf-8")

    pub_path = base / f"{cfg['name']}__all{suffix}" / "probs_public.jsonl"
    if pub_path.exists():
        rows = read_jsonl(pub_path)
        pred = {r["id"]: decide(r["probs"], recs[r["id"]], final_thr, pp) for r in rows}
        order = [r["id"] for r in records if r["source"] == "public"]
        sub = write_submission(out / "predictions.json", pred, order)
        errs = validate_predictions(sub, order)
        metrics["public"] = {"n": len(sub), "errors": errs,
                             "label_rate": {lab: round(sum(lab in v for v in pred.values()) / len(pred), 3)
                                            for lab in LABELS}}
        (out / "predictions_full.json").write_text(json.dumps(
            [{"id": r["id"], "labels": pred[r["id"]], "probs": r["probs"]} for r in rows], ensure_ascii=False,
            indent=1), encoding="utf-8")
        print(f"public: {len(sub)} predictions, format errors: {errs} -> {out / 'predictions.json'}")
    else:
        print(f"(no {pub_path}: train the final run with --holdout all to get public predictions)")
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["| system | macro-F1 | micro-F1 | exact |", "|---|---|---|---|"]
    for name, m in (("fixed thresholds", m_fixed), ("cross-fold tuned (honest)", m_cross),
                    ("in-sample tuned (optimistic)", m_insample)):
        lines.append(f"| {name} | {m['macro_f1']:.3f} | {m['micro_f1']:.3f} | {m['exact_match']:.3f} |")
    lines += ["", "| label | support | F1 fixed | F1 cross | thr public |", "|---|---|---|---|---|"]
    for lab in LABELS:
        f_fix, f_cr = m_fixed["per_label"][lab]["f1"], m_cross["per_label"][lab]["f1"]
        lines.append(f"| {lab} | {m_fixed['per_label'][lab]['support']} | "
                     f"{'-' if f_fix is None else f'{f_fix:.2f}'} | {'-' if f_cr is None else f'{f_cr:.2f}'} | "
                     f"{final_thr[lab]:.2f} |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
