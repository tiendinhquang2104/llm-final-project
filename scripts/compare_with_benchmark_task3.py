#!/usr/bin/env python3
"""Compare any Task 3 predictions file against the Gold Benchmark Reference.

Usage:
    python scripts/compare_with_benchmark_task3.py --predictions <path/to/predictions.json>

Outputs:
    - Taxonomy Macro-F1, Micro-F1, Exact Match Rate
    - Per-label Precision, Recall, F1 breakdown
    - Level Compliance & Severe Leak detection (L1, L2, L3)
    - Feedback quality, length distribution, and degenerate phrase screening
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.synth.taxonomy import LABEL_SPACE
from src.task3.compliance import check
from src.task3.submission import validate_submission, load_requested_levels

DEFAULT_BENCHMARK = repo_root / "outputs" / "task3" / "gold_reference_public.predictions.json"
DEFAULT_REQUESTED = (
    repo_root / "data" / "processed" / "task3_requested_levels.json"
    if (repo_root / "data" / "processed" / "task3_requested_levels.json").exists()
    else repo_root / "data" / "raw" / "public_test_release" / "task3_requested_levels.json"
)


def evaluate_taxonomy(gold_pairs):
    per_label = {}
    total_tp = total_fp = total_fn = 0
    for label in LABEL_SPACE:
        tp = fp = fn = 0
        for gold, pred in gold_pairs:
            is_gold = label in gold
            is_pred = label in pred
            tp += is_gold and is_pred
            fp += is_pred and not is_gold
            fn += is_gold and not is_pred
        prec = tp / (tp + fp) if (tp + fp) else (1.0 if (tp + fn) == 0 else 0.0)
        rec = tp / (tp + fn) if (tp + fn) else (1.0 if (tp + fp) == 0 else 0.0)
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        per_label[label] = {
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "support": tp + fn,
            "predicted": tp + fp
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn

    macro_f1 = sum(v["f1"] for v in per_label.values()) / len(LABEL_SPACE)
    micro_f1 = (2 * total_tp / (2 * total_tp + total_fp + total_fn)) if (2 * total_tp + total_fp + total_fn) else 0.0
    exact_match = sum(set(g) == set(p) for g, p in gold_pairs) / len(gold_pairs) if gold_pairs else 0.0

    return {
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "exact_match": exact_match,
        "per_label": per_label
    }


def compare_predictions(pred_path: Path, benchmark_path: Path = DEFAULT_BENCHMARK, req_path: Path = DEFAULT_REQUESTED):
    if not pred_path.exists():
        print(f"[ERROR] Predictions file not found: {pred_path}", file=sys.stderr)
        sys.exit(1)
    if not benchmark_path.exists():
        print(f"[ERROR] Benchmark reference file not found: {benchmark_path}", file=sys.stderr)
        sys.exit(1)

    with open(pred_path, "r", encoding="utf-8") as f:
        pred_data = json.load(f)
    with open(benchmark_path, "r", encoding="utf-8") as f:
        bench_data = json.load(f)

    pred_map = {x["sample_id"]: x["output"] for x in pred_data}
    bench_map = {x["sample_id"]: x["output"] for x in bench_data}

    # Load requested levels
    requested = load_requested_levels(req_path) if req_path.exists() else {sid: "Level 2 - Chẩn đoán" for sid in bench_map}

    # 1. Format & IDs Validation
    missing_ids = [sid for sid in bench_map if sid not in pred_map]
    extra_ids = [sid for sid in pred_map if sid not in bench_map]
    if missing_ids or extra_ids:
        print(f"[FORMAT WARNING] ID Mismatch: {len(missing_ids)} missing, {len(extra_ids)} extra.")

    shared_ids = [sid for sid in bench_map if sid in pred_map]

    # 2. Taxonomy Evaluation
    gold_pairs = [(bench_map[sid].get("taxonomy_error", []), pred_map[sid].get("taxonomy_error", [])) for sid in shared_ids]
    tax_metrics = evaluate_taxonomy(gold_pairs)

    # 3. Compliance & Severe Leak Check
    comp_ok = 0
    severe_leaks = 0
    comp_by_level = Counter()
    total_by_level = Counter()
    degen_flags = []

    DEGEN_PHRASES = ["gọi em làm em", "học em kỹ", "gọi là em", "bài tập em còn một chỗ", "code chưa hoàn thiện."]

    for sid in shared_ids:
        lvl = requested.get(sid, "Level 2 - Chẩn đoán")
        fb = pred_map[sid].get("feedback", "")
        chk = check(fb, lvl, version=3)
        total_by_level[lvl] += 1
        if chk.ok:
            comp_ok += 1
            comp_by_level[lvl] += 1
        if chk.severe and chk.level <= 2:
            severe_leaks += 1
        
        fb_lower = fb.lower().strip()
        for phrase in DEGEN_PHRASES:
            if phrase in fb_lower:
                degen_flags.append((sid, phrase, fb[:60]))
                break

    # 4. Print Report
    print("=" * 70)
    print(" TASK 3 BENCHMARK COMPARISON REPORT")
    print(f" Target File   : {pred_path.name}")
    print(f" Reference File: {benchmark_path.name}")
    print(f" Total Samples : {len(shared_ids)}/328")
    print("=" * 70)

    print("\n--- 1. TAXONOMY AGREEMENT METRICS ---")
    print(f" Macro-F1    : {tax_metrics['macro_f1']:.4f}  (Main Task 2/3 Taxonomy Metric)")
    print(f" Micro-F1    : {tax_metrics['micro_f1']:.4f}")
    print(f" Exact Match : {tax_metrics['exact_match']:.2%} ({int(tax_metrics['exact_match'] * len(shared_ids))}/{len(shared_ids)})")

    print("\n Per-Label Breakdown:")
    print(f"  {'Label':<18} | {'Precision':<9} | {'Recall':<9} | {'F1':<9} | {'Support':<7} | {'Pred':<7}")
    print("  " + "-" * 68)
    for lbl in LABEL_SPACE:
        m = tax_metrics["per_label"][lbl]
        print(f"  {lbl:<18} | {m['precision']:>9.4f} | {m['recall']:>9.4f} | {m['f1']:>9.4f} | {m['support']:>7} | {m['predicted']:>7}")

    print("\n--- 2. LEVEL COMPLIANCE & PEDAGOGICAL SAFETY ---")
    print(f" Overall Compliance  : {comp_ok}/{len(shared_ids)} ({comp_ok/len(shared_ids):.2%})")
    print(f" Severe Leaks (L1-2) : {severe_leaks}  (Warning: Severe leaks cause 0 points on that sample!)")
    for lvl in sorted(total_by_level):
        c = comp_by_level[lvl]
        t = total_by_level[lvl]
        print(f"   {lvl:<22}: {c}/{t} ({c/t:.2%})")

    print("\n--- 3. LANGUAGE QUALITY & DEGENERATION AUDIT ---")
    if degen_flags:
        print(f" [WARNING] Detected {len(degen_flags)} samples with suspicious/degenerated phrases:")
        for sid, phr, snippet in degen_flags[:5]:
            print(f"   - {sid} (matches '{phr}'): \"{snippet}...\"")
        if len(degen_flags) > 5:
            print(f"   ... and {len(degen_flags) - 5} more.")
    else:
        print(" [PASSED] Zero language degeneration artifacts detected.")

    print("\n" + "=" * 70)
    readiness = "READY FOR HIGH LEADERBOARD SCORE" if (tax_metrics["macro_f1"] >= 0.75 and severe_leaks == 0 and len(degen_flags) == 0) else "NEEDS REFINEMENT BEFORE SUBMISSION"
    print(f" SUMMARY VERDICT: {readiness}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True, help="Path to predictions.json to evaluate")
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK), help="Path to benchmark gold reference predictions")
    parser.add_argument("--requested", default=str(DEFAULT_REQUESTED), help="Path to requested levels mapping")
    args = parser.parse_args()

    compare_predictions(Path(args.predictions), Path(args.benchmark), Path(args.requested))


if __name__ == "__main__":
    main()
