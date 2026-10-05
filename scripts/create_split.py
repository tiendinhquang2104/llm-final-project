"""CLI: (re)create train/val sample_id splits. Prefer prepare_data.py for full pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loader import load_dataset  # noqa: E402
from src.data.preprocess import make_split  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create deterministic train/val sample_id splits.")
    p.add_argument("--data_dir", type=str, required=True, help="Dataset root with exams.json")
    p.add_argument("--output_dir", type=str, default="data/splits")
    p.add_argument("--ratio", type=float, default=0.2, help="Validation ratio (default 0.2)")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    samples = load_dataset(args.data_dir)
    train_ids, val_ids = make_split(
        [s.sample_id for s in samples],
        val_ratio=args.ratio,
        seed=args.seed,
    )
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "train_ids.json").write_text(json.dumps(train_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "val_ids.json").write_text(json.dumps(val_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"train={len(train_ids)} val={len(val_ids)} -> {out}")


if __name__ == "__main__":
    main()
