"""Task 2 CoT + RAG few-shot with a local Qwen2.5-Coder-7B-Instruct (MLX on Mac, transformers on Kaggle).

Same teacher prompt as scripts/run_task2_cot.py plus the 3 most similar graded submissions as examples
(configs/task2/cot_fewshot.yaml): gold first (code similarity >= 0.3), silver to fill; never public samples, never
the graded sample itself. After the gold run it compares with the zero-shot CoT run (compare.json).
Few-shot + self-consistency: --experiment cot_fewshot_sc. Options: see --help or src/task2/cot_cli.py."""
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
    main(ROOT, experiment="cot_fewshot", baseline="cot_zero_shot", doc=__doc__)
