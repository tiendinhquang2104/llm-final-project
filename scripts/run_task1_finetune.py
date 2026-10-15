"""One command for the whole Task 1 fine-tuned system (Hướng 2) on a CUDA machine (Kaggle, Colab, local GPU).

    python scripts/run_task1_finetune.py --gold-root <sample_dataset> --public-root <public_test_release> \
        --silver-root <generate-dataset> --work-dir <empty dir> [--smoke] [--preflight]

Steps (each is an existing, tested script): gold ChatML + fixed 26/6 split (must equal data/splits) -> P1..P4
run states of the silver code (scripts/derive_task1_silver_status.py, g++) -> audited silver with those states ->
training preflight -> QLoRA gold-only vs silver->gold, adapter chosen on gold validation -> error analysis
of the chosen adapter -> prediction of the release with best_adapter (task1_predictions.json, format-checked).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252; the help text is Vietnamese
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold-root", type=Path, required=True, help="sample_dataset (32 teacher-graded samples)")
    ap.add_argument("--public-root", type=Path, required=True, help="release to predict (public or private test)")
    ap.add_argument("--silver-root", type=Path, required=True, help="generate-dataset (synthetic silver)")
    ap.add_argument("--work-dir", type=Path, required=True, help="new directory for processed data and outputs")
    ap.add_argument("--config", type=Path, default=ROOT / "configs/task1/lora_7b.yaml")
    ap.add_argument("--source-manifest", type=Path, help="optional ZIP hash manifest copied into the run")
    ap.add_argument("--smoke", action="store_true", help="1 step per stage, 1 validation sample, 1 public sample/exam")
    ap.add_argument("--preflight", action="store_true", help="data + token checks only, no GPU")
    ap.add_argument("--no-status", action="store_true",
                    help="skip the P1..P4 silver states (adapter then answers rubric only: no prerequisite rule)")
    return ap.parse_args()


def run(*cmd) -> None:
    print("$", " ".join(map(str, cmd)), flush=True)
    env = {**os.environ, "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True", "PYTHONUNBUFFERED": "1"}
    subprocess.run([sys.executable, *map(str, cmd)], cwd=ROOT, check=True, env=env)


def main() -> None:
    a = parse_args()
    work = a.work_dir
    processed, splits, silver = work / "gold_processed", work / "gold_splits", work / "silver_processed"
    out = work / "qlora"
    if not processed.exists():
        run("scripts/prepare_data.py", "--data_dir", a.gold_root, "--output_dir", processed, "--splits_dir", splits,
            "--seed", 42, "--val_ratio", 0.2)
    for part in ("train", "val"):  # the evaluation split must be exactly the committed one
        committed = json.loads((ROOT / "data/splits" / f"{part}_ids.json").read_text(encoding="utf-8"))
        if committed != json.loads((splits / f"{part}_ids.json").read_text(encoding="utf-8")):
            sys.exit(f"gold {part} split differs from data/splits/{part}_ids.json")
    status_file = work / "silver_status.jsonl"
    if not a.no_status and not status_file.exists():  # P1..P4 run states of the silver code (needs g++)
        run("scripts/derive_task1_silver_status.py", "--silver-root", a.silver_root, "--out", status_file)
    if not (silver / "silver_manifest.json").exists():
        run("scripts/prepare_task1_silver.py", "--silver-root", a.silver_root, "--gold-root", a.gold_root,
            "--public-root", a.public_root, "--output-dir", silver,
            *([] if a.no_status else ["--status-file", status_file]))
    train = ["scripts/train_task1.py", "--config", a.config, "--processed-dir", processed, "--splits-dir", splits,
             "--silver-processed-dir", silver, "--output-dir", out, "--gold-root", a.gold_root]
    if a.source_manifest:
        train += ["--source-manifest", a.source_manifest]
    run(*train, "--preflight")
    if a.preflight:
        return
    # One process per arm: a 16 GB T4 cannot hold the first arm's leftovers and the second arm at once.
    for stage in ("gold_only", "silver_then_gold", "select"):
        run(*train, "--stage", stage, *(["--smoke"] if a.smoke else []))
    run_dir = out / "smoke" if a.smoke else out

    from src.task1.finetune import validation_error_report

    (run_dir / "error_analysis.md").write_text(validation_error_report(run_dir), encoding="utf-8")
    predict = ["scripts/predict_task1_finetuned.py", "--config", a.config, "--adapter", run_dir / "best_adapter",
               "--public-root", a.public_root, "--processed-dir", processed, "--splits-dir", splits,
               "--output-dir", run_dir / "public_predictions"]
    run(*predict, *(["--limit-per-exam", 1] if a.smoke else []))
    summary = json.loads((run_dir / "training_summary.json").read_text(encoding="utf-8"))
    print(json.dumps({"selected_variant": summary["selected_variant"], "selected_epoch": summary["selected_epoch"],
                      "gold_val_qwk": summary["selected_metrics"]["qwk"], "gold_val_mae": summary["selected_metrics"]["mae"],
                      "adapter": str(run_dir / "best_adapter"),
                      "submission": str(run_dir / "public_predictions" / "task1_predictions.json"),
                      "error_analysis": str(run_dir / "error_analysis.md")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
