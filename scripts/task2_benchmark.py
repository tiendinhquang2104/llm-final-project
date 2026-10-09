"""Collect every Task 2 run (outputs/task2/*/) into benchmark.json + benchmark.md (Local CLM vs API)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.task2.benchmark import collect_rows, to_markdown  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*", help="run directories (default: every outputs/task2/*/ with metrics.json)")
    ap.add_argument("--out", default=str(ROOT / "outputs" / "task2"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    runs = [Path(r) for r in a.runs] or sorted(p.parent for p in out.glob("*/metrics.json"))
    rows = collect_rows(runs)
    (out / "benchmark.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    md = to_markdown(rows)
    (out / "benchmark.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
