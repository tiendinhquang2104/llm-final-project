"""Prepare audited Task 1 silver JSONL from the main generated dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.task1.silver_data import prepare_silver_task1  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver-root", type=Path, required=True)
    parser.add_argument("--gold-root", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare_silver_task1(args.silver_root, args.gold_root, args.public_root, args.output_dir)
    print(json.dumps({key: value for key, value in manifest.items() if key != "excluded"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
