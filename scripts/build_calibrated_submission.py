"""Build the final calibrated Task 2 predictions by merging Qwen LLM predictions
with deterministic compiler gating and deep code reasoning aligned with the teacher's rubric.
"""
import json
import sys
from collections import Counter
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.task2.compile import attach_compile_logs, has_compile_error
from src.task2.data import load_task2
from src.task2.evaluator import validate_predictions, write_submission
from src.task2.expert_classifier import diagnose_submission
from src.task2.labels import LABELS, normalize_labels


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("==> Loading Public Test dataset and compiler logs...")
    ds_pub = load_task2("data/public_test_release")
    [samples], _ = attach_compile_logs({}, [ds_pub.samples])
    print(f"Loaded {len(samples)} public test samples.")

    # 1. Load Qwen predictions
    qwen_path = Path(r"c:\Users\tranduytan\Downloads\results (1)\task2_predictions.json")
    if not qwen_path.exists():
        qwen_path = Path("outputs/task2/task2_predictions_qwen.json")
    
    print(f"==> Loading Qwen raw predictions from: {qwen_path}")
    qwen_raw = json.loads(qwen_path.read_text(encoding="utf-8"))
    qwen_map = {}
    for item in qwen_raw:
        sid = item["sample_id"]
        qwen_map[sid] = item.get("output", {}).get("taxonomy_error", [])

    # 2. Process each sample with deep code reasoning + deterministic compiler gating
    final_preds = {}
    compile_err_count = 0
    edge_case_fixed = 0

    for s in samples:
        sid = s.sample_id
        qwen_labels = set(qwen_map.get(sid, []))
        expert_labels = set(diagnose_submission(s))

        # Start with expert labels
        merged = set(expert_labels)

        # Merge Qwen labels (except hallucinations)
        for lab in qwen_labels:
            if lab == "Lỗi edge case":
                # Teacher never used edge case; map to thuật toán
                merged.add("Lỗi thuật toán")
                edge_case_fixed += 1
            elif lab == "Lỗi biên dịch":
                # Handled deterministically below
                pass
            else:
                merged.add(lab)

        # DETERMINISTIC COMPILER GATING (100% precision on gold)
        has_ce = has_compile_error(s.compile_log)
        if has_ce:
            merged.add("Lỗi biên dịch")
            compile_err_count += 1
        else:
            merged.discard("Lỗi biên dịch")

        # Canonical ordering
        ordered = [l for l in LABELS if l in merged]
        final_preds[sid] = ordered

    # 3. Summary statistics
    print("\n==> Prediction summary on 328 Public Test samples:")
    counts = Counter()
    empty_count = 0
    for sid, labs in final_preds.items():
        if not labs:
            empty_count += 1
        for l in labs:
            counts[l] += 1

    print(f"Total samples: {len(final_preds)}")
    print(f"Empty (clean) predictions: {empty_count} ({empty_count / len(final_preds) * 100:.1f}%)")
    print(f"Compile errors (strictly verified): {compile_err_count}")
    print(f"Edge case labels mapped to algo: {edge_case_fixed}")
    print("\nLabel distribution:")
    for l in LABELS:
        print(f"  {l:15}: {counts[l]}")

    # 4. Write submission files
    out_dir = Path("outputs/task2/task2_calibrated")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "task2_predictions.json"
    
    all_ids = [s.sample_id for s in samples]
    sub = write_submission(out_file, final_preds, all_ids)
    print(f"\n[OK] Calibrated predictions written to: {out_file}")

    # Also copy to Downloads for user's convenience
    dl_copy = Path(r"c:\Users\tranduytan\Downloads\task2_predictions_calibrated.json")
    try:
        dl_copy.write_text(out_file.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[OK] Download copy saved to: {dl_copy}")
    except Exception as exc:
        print(f"[Notice] Could not copy to Downloads: {exc}")

    # 5. Format validation check
    val_errs = validate_predictions(sub, all_ids)
    if val_errs:
        print(f"[ERROR] Validation errors: {val_errs}")
    else:
        print("[SUCCESS] All 328 predictions are 100% format-valid and ready for submission!")


if __name__ == "__main__":
    main()
