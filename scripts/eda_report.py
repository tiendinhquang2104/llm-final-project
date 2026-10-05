"""Quick EDA over sample_dataset (console report + optional JSON summary)."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loader import load_dataset, resolve_dataset_root  # noqa: E402
from src.data.schema import RUBRIC_DIMS, TAXONOMY_LABELS  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="EDA for challenge sample/full dataset.")
    p.add_argument("--data_dir", type=str, required=True)
    p.add_argument("--out", type=str, default="outputs/eda_summary.json")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = resolve_dataset_root(args.data_dir)
    samples = load_dataset(root)

    scores = Counter(s.total_score for s in samples)
    exam_types = Counter(s.exam_type for s in samples)
    levels = Counter(s.target_feedback_level for s in samples)
    label_counts = Counter()
    empty_tax = 0
    for s in samples:
        if not s.taxonomy_error:
            empty_tax += 1
        for lab in s.taxonomy_error:
            label_counts[lab] += 1

    code_lens = [len(s.code) for s in samples]
    stmt_lens = [len(s.exam_statement) for s in samples]
    rubric_dist = {
        dim: dict(Counter(getattr(s.rubric, dim) for s in samples)) for dim in RUBRIC_DIMS
    }

    summary = {
        "n_samples": len(samples),
        "exam_type": dict(exam_types),
        "total_score_dist": {str(k): v for k, v in sorted(scores.items())},
        "rubric_dist": rubric_dist,
        "taxonomy_empty": empty_tax,
        "taxonomy_counts": {lab: label_counts.get(lab, 0) for lab in TAXONOMY_LABELS},
        "feedback_levels": dict(levels),
        "code_chars": {
            "min": min(code_lens),
            "max": max(code_lens),
            "mean": round(sum(code_lens) / len(code_lens), 1),
        },
        "statement_chars_mean": round(sum(stmt_lens) / len(stmt_lens), 1),
        "nonempty_compile_log": sum(1 for s in samples if s.compile_log),
        "nonempty_test_report": sum(1 for s in samples if s.test_report),
        "data_root": str(root),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"n_samples={summary['n_samples']} root={root}")
    print(f"exam_type={summary['exam_type']}")
    print(f"total_score={summary['total_score_dist']}")
    print(f"taxonomy_empty={empty_tax} counts={summary['taxonomy_counts']}")
    print(f"levels={summary['feedback_levels']}")
    print(f"code_chars={summary['code_chars']}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
