"""Task 2 CoT + self-consistency with a local Qwen2.5-Coder-7B-Instruct (MLX on Mac, transformers on Kaggle).

Same teacher prompt as scripts/run_task2_cot.py, but each sample is graded n=5 times with temperature 0.7 and a
label is kept when at least half of the parsed answers name it (configs/task2/cot_self_consistency.yaml). The vote
share per label is in predictions_full.json / debug.jsonl / report.html ("Phiếu chia rẽ" filter).
After the gold run it prints and saves (compare.json) the comparison with the zero-shot CoT run, if that exists.

5 answers per sample cost ~1.3-2x the zero-shot time on the HF backend (one batched generate call per sample) and
5x on MLX. For the 360 public samples on Kaggle, --public-shard K/N splits the work over sessions (see
kaggle/task2_cot_sc.ipynb). Options: see --help or src/task2/cot_cli.py."""
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
    main(ROOT, experiment="cot_self_consistency", baseline="cot_zero_shot", doc=__doc__)
