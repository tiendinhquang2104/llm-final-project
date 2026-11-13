"""Task 1 output scoring: raw model text -> rubric + per-problem statuses, and self-consistency aggregation."""
from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field

from src.data.loader import DIM_MAX, DIMENSIONS
from src.task1.prerequisite_rules import STATUSES, normalize_status
from src.task1.score import from_cents, to_cents
from src.utils.json_extractor import extract_json_objects, strip_thinking


@dataclass
class ParsedOutput:
    ok: bool
    rubric: dict[str, int | float] | None = None
    problems: dict[str, str] = field(default_factory=dict)
    problem_notes: dict[str, str] = field(default_factory=dict)
    rationale: str = ""
    error: str = ""
    partial: bool = False  # rubric recovered by regex, not by JSON


def _score(v):
    if isinstance(v, dict):
        v = v.get("score", v.get("value"))
    if isinstance(v, str):
        m = re.search(r"-?\d+(?:\.\d+)?", v)
        v = float(m.group()) if m else None
    return v


def _from_obj(obj: dict) -> ParsedOutput | None:
    rub_src = obj.get("rubric") if isinstance(obj.get("rubric"), dict) else obj
    rubric = {}
    for d in DIMENSIONS:
        if d in rub_src:
            v = _score(rub_src[d])
            if v is not None:
                rubric[d] = v
    if len(rubric) < len(DIMENSIONS):
        return None
    problems, notes = {}, {}
    raw = obj.get("problems")
    if isinstance(raw, dict):
        raw = [{"pid": k, **(v if isinstance(v, dict) else {"status": v})} for k, v in raw.items()]
    if isinstance(raw, list):
        for p in raw:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("pid") or p.get("id") or "").strip().upper()
            if not pid:
                continue
            if not pid.startswith("P"):
                pid = f"P{pid}"
            problems[pid] = normalize_status(p.get("status"))
            if p.get("note") or p.get("reason"):
                notes[pid] = str(p.get("note") or p.get("reason"))
    rationale = obj.get("rationale") or obj.get("analysis") or obj.get("reasoning") or ""
    return ParsedOutput(ok=True, rubric=rubric, problems=problems, problem_notes=notes,
                        rationale=str(rationale))


def parse_output(text: str) -> ParsedOutput:
    for obj in extract_json_objects(text):
        parsed = _from_obj(obj)
        if parsed:
            return parsed
    # Fallback: regex "dim": number pairs anywhere in the text.
    body = strip_thinking(text or "")
    rubric = {}
    for d in DIMENSIONS:
        m = re.findall(rf'"?{d}"?\s*[:=]\s*(?:\{{\s*"score"\s*:\s*)?(\d+(?:\.\d+)?)', body)
        if m:
            rubric[d] = float(m[-1])
    if len(rubric) == len(DIMENSIONS):
        return ParsedOutput(ok=True, rubric=rubric, partial=True, error="regex_fallback")
    return ParsedOutput(ok=False, error="no_valid_json")


def round_half_up(x: float) -> int:
    return int(x + 0.5)


def aggregate(parsed: list[ParsedOutput]) -> tuple[dict | None, dict[str, str], str]:
    """Self-consistency aggregation: per-dimension median, per-problem majority status."""
    good = [p for p in parsed if p.ok and p.rubric]
    if not good:
        return None, {}, ""
    # Median on integer cents preserves valid fractional scores. A half-cent
    # median is rounded half-up to the nearest allowed hundredth.
    rubric = {d: from_cents(round_half_up(statistics.median(to_cents(p.rubric[d], DIM_MAX[d])
                                                             for p in good))) for d in DIMENSIONS}
    statuses: dict[str, str] = {}
    pids = sorted({pid for p in good for pid in p.problems})
    for pid in pids:
        votes = Counter(p.problems.get(pid) for p in good if p.problems.get(pid))
        if votes:
            top = max(votes.values())
            # Tie-break deterministically by STATUSES order (correct first).
            statuses[pid] = next(s for s in STATUSES if votes.get(s) == top)
    return rubric, statuses, good[0].rationale
