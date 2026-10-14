"""Task 2 zero-shot CoT with a local Qwen2.5-Coder-7B-Instruct (MLX on Mac, transformers on Kaggle).

One greedy answer per sample (configs/task2/cot_zero_shot.yaml). Options: see --help or src/task2/cot_cli.py.
Self-consistency (5 sampled answers + majority vote) is scripts/run_task2_cot_sc.py."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.task2.cot_cli import main  # noqa: E402

if __name__ == "__main__":
    main(ROOT, experiment="cot_zero_shot", doc=__doc__)
