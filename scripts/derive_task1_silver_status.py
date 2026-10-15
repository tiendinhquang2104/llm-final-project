"""Rebuild the per-problem run states (P1..P4) of the silver Task 1 set, missing from generate-dataset.zip.

The generator labels every multi_problem record by running the Rec-schema harness (src/synth/multi.py) on its
code with the reference solution of the problem bank (src/synth/problems/). This script re-runs exactly that,
then re-derives the rubric from the observed states (src/synth/labeler.label_multi) and keeps the states only
when that rubric equals the stored label, so no status is ever taught that disagrees with its own rubric.

    python scripts/derive_task1_silver_status.py --silver-root <generate-dataset> --out <silver_status.jsonl>

Needs g++ (Linux / Kaggle / macOS). Output rows: sample_id, exam_id, observed_states | null, rubric_match.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loader import load_code, resolve_dataset_root  # noqa: E402
from src.synth.labeler import label_multi  # noqa: E402
from src.synth.multi import is_rec_schema, reference_rec_outputs, run_multi_datasets  # noqa: E402
from src.synth.problems import load_problems  # noqa: E402
from src.synth.verify import make_runner  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--silver-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--problems-dir", type=Path, default=ROOT / "src/synth/problems")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--min-match", type=float, default=0.9,
                    help="abort (write nothing) if fewer multi records than this reproduce their stored rubric")
    a = ap.parse_args()
    root = resolve_dataset_root(a.silver_root)
    runner = make_runner("auto")
    if runner is None:
        sys.exit("g++ not found: run this on Linux / Kaggle")
    problems = load_problems(a.problems_dir)
    exams = {e["exam_id"]: e for e in json.loads((root / "exams.json").read_text(encoding="utf-8"))["exams"]}
    samples = json.loads((root / "task1_grading.json").read_text(encoding="utf-8"))["samples"]
    multi_exams = {s["input"]["exam_id"] for s in samples if exams[s["input"]["exam_id"]]["exam_type"] == "multi_problem"}
    missing = sorted(multi_exams - set(problems))
    if missing:
        sys.exit(f"problem bank has no definition for {missing}")
    for eid in sorted(multi_exams):
        if not is_rec_schema(problems[eid]):
            sys.exit(f"{eid} is not a Rec-schema problem: this script only reproduces run_multi_datasets")
        reference_rec_outputs(runner, problems[eid])  # fill the reference cache once per exam (not thread-safe)

    def derive(s: dict) -> dict | None:
        inp = s["input"]
        if exams[inp["exam_id"]]["exam_type"] != "multi_problem":
            return None
        rep = run_multi_datasets(runner, load_code(root, inp["code_file"]), problems[inp["exam_id"]])
        match = label_multi(rep.signals).rubric == s["output"]["rubric"]
        return {"sample_id": s["sample_id"], "exam_id": inp["exam_id"],
                "observed_states": rep.states if match else None, "rubric_match": match}

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        rows = [r for r in pool.map(derive, samples) if r is not None]
    matched = sum(r["rubric_match"] for r in rows)
    rate = matched / max(1, len(rows))
    print(f"runner {getattr(runner, 'runner_id', '?')} | multi records {len(rows)} | rubric reproduced {matched} "
          f"({rate:.1%}) | {time.time() - t0:.0f}s")
    print("P1 states:", dict(Counter((r["observed_states"] or {}).get("P1", "not reproduced") for r in rows)))
    if rate < a.min_match:
        sys.exit(f"only {rate:.1%} of multi records reproduce their rubric (< {a.min_match:.0%}): the harness or "
                 "compiler differs from the generator's. Nothing written.")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"-> {a.out}")
    if hasattr(runner, "close"):
        runner.close()


if __name__ == "__main__":
    main()
