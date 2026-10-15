"""Ensemble V2: Combines Qwen's semantic predictions with dynamic test execution
and isolated compiler gating.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.task2.compile import attach_compile_logs, has_compile_error
from src.task2.data import load_task2
from src.task2.evaluator import validate_predictions, write_submission
from src.task2.labels import LABELS
from scripts.full_diagnostic_audit import audit_final_1, audit_midterm_1, audit_midterm_2, audit_multi_problem
import tempfile


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("==> Loading Public Test dataset and compiler logs...")
    ds_pub = load_task2("data/public_test_release")
    [samples], _ = attach_compile_logs({}, [ds_pub.samples])
    print(f"Loaded {len(samples)} public test samples.")

    # Load Qwen raw predictions
    qwen_path = Path(r"c:\Users\tranduytan\Downloads\results (1)\task2_predictions.json")
    if not qwen_path.exists():
        qwen_path = Path("outputs/task2/task2_predictions_qwen.json")
    
    qwen_raw = json.loads(qwen_path.read_text(encoding="utf-8"))
    qwen_map = {item["sample_id"]: set(item.get("output", {}).get("taxonomy_error", [])) for item in qwen_raw}

    final_preds = {}
    with tempfile.TemporaryDirectory() as td:
        for s in samples:
            exam_id = s.exam_id
            sid = s.sample_id
            qwen_labels = qwen_map.get(sid, set())

            # Check compile error FIRST
            if has_compile_error(s.compile_log):
                # Code failed to compile: instructor only assigns compile error (and hard-code if #include *.csv)
                cur = {"Lỗi biên dịch"}
                if "50-best" in s.code or "battles.csv" in s.code:
                    cur.add("Lỗi hard-code")
                final_preds[sid] = [l for l in LABELS if l in cur]
                continue

            # Code compiles cleanly: run dynamic audit
            if exam_id == "Class03-Final-1":
                audit_labels = set(audit_final_1(s, td))
            elif exam_id == "Class03-Midterm-1":
                audit_labels = set(audit_midterm_1(s, td))
            elif exam_id == "Class03-Midterm-2":
                audit_labels = set(audit_midterm_2(s, td))
            else:
                audit_labels = set(audit_multi_problem(s))

            # Never include compile error on compilable code
            audit_labels.discard("Lỗi biên dịch")

            # Merge with high-confidence Qwen labels
            merged = set(audit_labels)
            for lab in qwen_labels:
                if lab == "Lỗi edge case":
                    # If model suspected edge case, it's usually logic/algo
                    merged.add("Lỗi logic")
                elif lab == "Lỗi biên dịch":
                    # Discard hallucinated compile errors
                    pass
                elif lab in ["Lỗi style", "Lỗi hard-code", "Lỗi vòng lặp"]:
                    merged.add(lab)
                elif lab == "Lỗi logic" and not merged:
                    merged.add("Lỗi logic")

            final_preds[sid] = [l for l in LABELS if l in merged]

    # Summary
    counts = Counter()
    empty_count = 0
    for sid, labs in final_preds.items():
        if not labs:
            empty_count += 1
        for l in labs:
            counts[l] += 1

    print("\n==> Ensemble V2 Results on 328 Public Test Samples:")
    print(f"Total samples: {len(final_preds)}")
    print(f"Empty (clean) predictions: {empty_count} ({empty_count / len(final_preds) * 100:.1f}%)")
    print("\nLabel breakdown:")
    for l in LABELS:
        print(f"  {l:15}: {counts[l]}")

    # Write final submission files
    out_dir = Path("outputs/task2/task2_calibrated")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "task2_predictions.json"
    
    all_ids = [s.sample_id for s in samples]
    sub = write_submission(out_file, final_preds, all_ids)
    print(f"\n[OK] Predictions written to: {out_file}")

    # Copy to user Downloads
    dl_copy = Path(r"c:\Users\tranduytan\Downloads\task2_predictions_calibrated.json")
    try:
        dl_copy.write_text(out_file.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[OK] Download copy updated at: {dl_copy}")
    except Exception as exc:
        print(f"[Notice] Could not update Downloads: {exc}")

    # Validate
    errs = validate_predictions(sub, all_ids)
    if errs:
        print(f"[ERROR] Validation errors: {errs}")
    else:
        print("[SUCCESS] All 328 predictions are 100% valid according to contest format!")


if __name__ == "__main__":
    main()
