#!/usr/bin/env python3
"""Automated pipeline to run Task 3 inference on Public Test and export valid submission JSON.

Usage:
    # 1. Run inference using trained LoRA adapter:
    python scripts/build_task3_submission.py --adapter checkpoints/task3/qlora --taxonomy-json path/to/task2.json

    # 2. Run inference using base model (zero-shot/few-shot):
    python scripts/build_task3_submission.py --taxonomy-json path/to/task2.json

    # 3. Dry-run test (no GPU, no model download):
    python scripts/build_task3_submission.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.task3.cli import run_main
from src.task3.dataset import read_json, write_json
from src.task3.pipeline import validate_predictions


def build_default_taxonomy(public_root: Path, output_path: Path) -> Path:
    """Build a baseline taxonomy by testing C++ syntax compilation on each sample."""
    feedback_payload = read_json(public_root / "task3_feedback.json")
    samples = feedback_payload["samples"]
    taxonomy_map = {}

    compile_err_re = re.compile(r"^\S+:\d+:\d+: (?:fatal )?error:", re.MULTILINE)

    print(f"Building baseline taxonomy for {len(samples)} public test samples...")
    for s in samples:
        sid = s["sample_id"]
        code_rel = s["input"]["code_file"]
        code_path = public_root / code_rel
        exam_type = s["input"].get("exam_type", "single_problem")
        
        # Test basic compilation if g++ is available
        is_compile_err = False
        if code_path.is_file() and shutil_which_gxx():
            args = ["g++", "-std=c++11", "-fsyntax-only", str(code_path)]
            try:
                res = subprocess.run(args, capture_output=True, text=True, timeout=10)
                if res.returncode != 0 and compile_err_re.search(res.stderr or ""):
                    is_compile_err = True
            except Exception:
                pass
        
        if is_compile_err:
            taxonomy_map[sid] = ["Lỗi biên dịch"]
        else:
            taxonomy_map[sid] = ["Lỗi logic"]

    write_json(output_path, taxonomy_map)
    print(f"Saved baseline taxonomy map to {output_path}")
    return output_path


def shutil_which_gxx():
    import shutil
    return shutil.which("g++") is not None


def main():
    p = argparse.ArgumentParser(description="Run Task 3 inference on Public Test and create submission JSON")
    p.add_argument("--config", default="configs/task3/baseline.yaml", help="Model config YAML")
    p.add_argument("--adapter", help="Path to LoRA adapter directory (e.g. checkpoints/task3/qlora)")
    p.add_argument("--taxonomy-json", help="Path to Task 2 prediction JSON file")
    p.add_argument("--output-dir", default="outputs/task3", help="Output directory")
    p.add_argument("--submission-name", default="task3_submission.json", help="Name of submission file")
    p.add_argument("--empty-on-clean", action="store_true", default=True, help="Set feedback='' if taxonomy_error is empty (Q13 FAQ)")
    p.add_argument("--dry-run", action="store_true", help="Run with mock backend for dry-run verification")
    args = p.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    task3_folder = ROOT.parent / "task 3 files"
    public_root = ROOT.parent / "public_test_release"

    # Resolve taxonomy file
    taxonomy_path = args.taxonomy_json
    if not taxonomy_path:
        default_tax = out_dir / "public_baseline_taxonomy.json"
        if not default_tax.is_file():
            build_default_taxonomy(public_root, default_tax)
        taxonomy_path = str(default_tax)

    pred_out = out_dir / ("public.mock.predictions.json" if args.dry_run else "public.predictions.json")

    cli_args = [
        "--config", args.config,
        "--split", "public",
        "--taxonomy-source", "task2-json",
        "--taxonomy-json", taxonomy_path,
        "--allow-unverified-task2-export",
        "--output", str(pred_out),
    ]
    if args.adapter:
        cli_args.extend(["--adapter", args.adapter])
    if args.dry_run:
        cli_args.append("--dry-run")

    print(f"Executing: python scripts/run_task3.py {' '.join(cli_args)}")
    run_main(cli_args)

    # Copy / symlink to submission location
    if pred_out.is_file():
        predictions = read_json(pred_out)
        print(f"\n[OK] Generated {len(predictions)} predictions.")
        
        # Validate submission format
        with open(ROOT / "data" / "processed" / "task3" / "public.jsonl") as f:
            expected_ids = [json.loads(line)["record"]["sample_id"] for line in f]
        validate_predictions(predictions, expected_ids)
        print("[OK] Validation passed: exact 328 sample IDs match in required order and schema.")

        # Save to outputs and to 'task 3 files' folder
        dest_submission = out_dir / args.submission_name
        write_json(dest_submission, predictions)
        print(f"[OK] Saved submission file to: {dest_submission}")

        if task3_folder.is_dir():
            target_dest = task3_folder / args.submission_name
            write_json(target_dest, predictions)
            print(f"[OK] Also saved submission file directly into 'task 3 files': {target_dest}")


if __name__ == "__main__":
    main()
