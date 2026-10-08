"""Create the fixed train/validation split (data/splits/train_ids.json, val_ids.json). Run once, then keep fixed.

python scripts/create_split.py [--val-frac 0.6 --seed 42]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.loader import load_task1, make_split, save_split  # noqa: E402
from src.utils.config import load_config  # noqa: E402

base = load_config(ROOT / "configs" / "task1" / "base.yaml")
ap = argparse.ArgumentParser()
ap.add_argument("--data-root", default=str(ROOT / base["data"]["root"]))
ap.add_argument("--out-dir", default=str(ROOT / base["data"]["splits_dir"]))
ap.add_argument("--val-frac", type=float, default=0.6)
ap.add_argument("--seed", type=int, default=base.get("seed", 42))
a = ap.parse_args()

split = make_split(load_task1(a.data_root).samples, a.val_frac, a.seed)
save_split(split, a.out_dir)
print(f"train={len(split['train'])} val={len(split['val'])} -> {a.out_dir}")
