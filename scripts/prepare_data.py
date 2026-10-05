"""CLI: convert sample_dataset → ChatML jsonl for unified multi-task training."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/prepare_data.py` without install
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.preprocess import build_unified_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Preprocess challenge dataset into ChatML jsonl for Task1/2/3 training."
    )
    p.add_argument(
        "--data_dir",
        type=str,
        default=None,
        help="Folder containing exams.json / task*.json / submissions/ "
        "(default: ../sample_dataset or data/raw)",
    )
    p.add_argument(
        "--input_dir",
        type=str,
        default=None,
        help="Alias of --data_dir (kept for README compatibility).",
    )
    p.add_argument(
        "--output_dir",
        type=str,
        default="data/processed",
        help="Where to write train_unified.jsonl / per-task jsonl (default: data/processed)",
    )
    p.add_argument(
        "--splits_dir",
        type=str,
        default=None,
        help="Where to write train_ids.json / val_ids.json (default: sibling data/splits)",
    )
    p.add_argument("--val_ratio", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--skip_leakage_check", action="store_true")
    return p.parse_args()


def default_data_dir() -> Path:
    candidates = [
        ROOT / "data" / "raw",
        ROOT.parent / "sample_dataset" / "sample_dataset",
        ROOT.parent / "sample_dataset",
    ]
    for c in candidates:
        if (c / "exams.json").exists() or (c / "sample_dataset" / "exams.json").exists():
            return c
    raise FileNotFoundError(
        "Cannot auto-detect dataset. Pass --data_dir pointing at the folder with exams.json."
    )


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir or args.input_dir or default_data_dir())
    paths = build_unified_jsonl(
        data_dir=data_dir,
        output_dir=args.output_dir,
        splits_dir=args.splits_dir,
        val_ratio=args.val_ratio,
        seed=args.seed,
        check_leakage=not args.skip_leakage_check,
    )
    print(f"data_dir : {data_dir}")
    print(f"output   : {args.output_dir}")
    for name, path in paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
