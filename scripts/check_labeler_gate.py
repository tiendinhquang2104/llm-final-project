"""Labeler gate on the 32 real samples (synth_plan.md "Cổng chất lượng").

Offline, single_problem signals are reconstructed from the shipped ``compile_log`` and
``test_report`` (``actual`` outputs), so no compiler is needed. This is deliberately partial:
the report compares outputs strictly, so it cannot see the teacher's *format* judgements
(extra characters, printed prompts) or the perf signal; those need the hand-written standard
tests. Multi_problem samples need a per-question harness and are reported as skipped.

Known noise the rulebook documents is excluded from the score; ``EX02-S209`` is reported as an
extra data finding (all timeouts but the teacher scored it 7, not the S2 value).

    python scripts/check_labeler_gate.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.synth.labeler import SingleSignals, label_single  # noqa: E402
from src.synth.verify import normalize  # noqa: E402

ERROR_RE = re.compile(r"^\S+:\d+:\d+: (?:fatal )?error:", re.MULTILINE)
PROMPT_RE = re.compile(r"^(?:input|nhap|nhập|n)\b[^:]*:\s*", re.IGNORECASE)
TIMEOUT = "<TIMEOUT>"

# rulebook noise (N2 prereq-inconsistent examples + N5 loop label); S214 relabelled to 0
EXCLUDED = {"EX01-S108", "EX01-S110", "EX01-S112", "EX01-S102"}
EXTRA_FINDINGS = {"EX02-S209"}  # all timeouts but teacher scored 7 -> data finding, not S2
# format-token edges the shipped report cannot expose (it compares outputs strictly, prompts
# stripped): they need the hand-written standard tests + prompt handling.
NEEDS_TESTS = {"EX02-S205", "EX02-S206"}
S214_TOTAL = 0


def _clean(text: str) -> str:
    return normalize(PROMPT_RE.sub("", (text or "").strip()))


def signals_from_sample(sample: dict) -> SingleSignals | None:
    """Best-effort single_problem signals from compile_log + test_report; None when unavailable."""
    inp = sample["input"]
    if ERROR_RE.search(inp.get("compile_log") or ""):
        return SingleSignals(compiles=False)
    report = inp.get("test_report")
    if not report:
        return None
    actuals = [(r.get("actual") or "").strip() for r in report]
    if actuals and all(a == TIMEOUT for a in actuals):
        return SingleSignals(terminates=False)
    if actuals and all(a == "" for a in actuals):
        return SingleSignals(core_incomplete=True)
    correct = [a != TIMEOUT and _clean(a) == _clean(r.get("expected", ""))
               for a, r in zip(actuals, report)]
    ratio = sum(correct) / len(correct) if correct else 1.0
    return SingleSignals(compiles=True, terminates=True, token_exact=True, token_normalized=True,
                         normal_pass_ratio=ratio, edge_groups_failed=0, perf_ok=True,
                         examples_only_pass=False)


def _reason(sid: str) -> str | None:
    if sid in EXCLUDED:
        return "noise (rulebook)"
    if sid in EXTRA_FINDINGS:
        return "data finding"
    if sid in NEEDS_TESTS:
        return "needs hand-written tests"
    return None


def run_gate(root: str | Path) -> dict:
    root = Path(root)
    t1 = json.loads((root / "task1_grading.json").read_text(encoding="utf-8"))["samples"]
    rows, skipped = [], []
    for sample in t1:
        sid = sample["sample_id"]
        gold = S214_TOTAL if sid == "EX02-S214" else sample["output"]["total_score"]
        if sample["input"]["exam_type"] != "single_problem":
            skipped.append((sid, "multi_problem needs a per-question harness"))
            continue
        signals = signals_from_sample(sample)
        if signals is None:
            skipped.append((sid, "no test_report"))
            continue
        pred = label_single(signals)
        rows.append({"sample_id": sid, "gold": gold, "pred": pred.total, "rule": pred.rule_id,
                     "match": pred.total == gold, "reason": _reason(sid)})
    counted = [r for r in rows if r["reason"] is None]
    return {"rows": rows, "skipped": skipped, "matched": sum(r["match"] for r in counted),
            "n_counted": len(counted), "n_single": len(rows)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=str(ROOT / "data" / "raw" / "sample_dataset"))
    ap.add_argument("--min-match", type=int, default=None,
                    help="required matches among counted single samples (default: all counted)")
    a = ap.parse_args()
    result = run_gate(a.data)
    for r in result["rows"]:
        if r["reason"]:
            mark = f" ({r['reason']}, excluded)"
        else:
            mark = "" if r["match"] else "  <-- MISMATCH"
        print(f"{r['sample_id']:12s} gold={r['gold']:2d} pred={r['pred']:2d} rule={r['rule']:3s}{mark}")
    if result["skipped"]:
        print(f"skipped {len(result['skipped'])} samples (multi_problem / no report)")
    target = a.min_match if a.min_match is not None else result["n_counted"]
    print(f"single_problem match: {result['matched']}/{result['n_counted']} (target >= {target}); "
          f"{len(result['skipped'])} need the multi harness / hand-written tests")
    sys.exit(0 if result["matched"] >= target else 1)


if __name__ == "__main__":
    main()
