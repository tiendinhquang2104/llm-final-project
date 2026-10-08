"""Deterministic grading-policy rules, applied AFTER the LLM, independent of any prompt.

The LLM is asked to judge every problem on its own merits (status per problem + 6 rubric scores).
This module then enforces the exam's grading policy in code, so the policy can never be "forgotten"
by the model and can be ablated on/off without re-running inference:

1. clamp      — every dimension is an int inside its range.
2. derive     — (optional) recompute `logic` from per-problem statuses and problem weights.
3. prereq     — if a prerequisite problem fails, the problems depending on it get no credit:
                the dimensions in `zero_on_prereq_fail` are set to 0.
4. compile    — if `compilable == 0`, the dimensions in `zero_on_not_compilable` are set to 0.
5. total      — total_score = sum of the 6 dimensions (never trusted from the model).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from src.data.loader import DIM_MAX, DIMENSIONS

STATUSES = ("correct", "partial", "wrong", "runtime_error", "not_attempted")
STATUS_CREDIT = {"correct": 1.0, "partial": 0.5, "wrong": 0.0, "runtime_error": 0.0, "not_attempted": 0.0}
PREREQ_FAIL = frozenset({"wrong", "runtime_error", "not_attempted"})
PREREQ_FAIL_STRICT = PREREQ_FAIL | {"partial"}

# Observed in the labelled data: when P1 (prerequisite) fails, the teacher keeps compilable/io_format
# and gives 0 for the rest.
DEFAULT_ZERO_ON_PREREQ_FAIL = ("logic", "edge_case", "complexity", "code_quality")
# Default when the statement does not say "0 điểm nếu không biên dịch được": code_quality is still judged.
DEFAULT_ZERO_ON_NOT_COMPILABLE = ("io_format", "logic", "edge_case", "complexity")


@dataclass(frozen=True)
class ExamPolicy:
    exam_id: str
    exam_type: str
    prerequisites: dict[str, tuple[str, ...]] = field(default_factory=dict)  # pid -> dependent pids
    problem_weights: dict[str, float] = field(default_factory=dict)
    zero_on_prereq_fail: tuple[str, ...] = DEFAULT_ZERO_ON_PREREQ_FAIL
    zero_on_not_compilable: tuple[str, ...] = DEFAULT_ZERO_ON_NOT_COMPILABLE


@dataclass
class RuleConfig:
    clamp: bool = True
    derive_logic: bool = False
    prerequisite: bool = True
    prereq_strict: bool = False  # treat "partial" on a prerequisite as a failure
    compile_gate: bool = True

    @classmethod
    def from_dict(cls, d: dict | None) -> "RuleConfig":
        d = d or {}
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _statement_zeroes_on_compile_error(statement: str) -> bool:
    """True when the statement says a non-compiling submission gets 0 points overall."""
    for line in statement.splitlines():
        low = line.lower()
        if "0 điểm" in low and "không biên dịch" in low:
            return True
    return False


def policy_from_exam(exam: dict, overrides: dict | None = None) -> ExamPolicy:
    prereq = {
        p["pid"]: tuple(p["is_prerequisite_for"])
        for p in exam.get("problems", [])
        if p.get("is_prerequisite_for")
    }
    weights = {p["pid"]: float(p.get("max_score", 1.0)) for p in exam.get("problems", [])}
    zero_compile = (
        tuple(DIMENSIONS)
        if _statement_zeroes_on_compile_error(exam.get("statement", ""))
        else DEFAULT_ZERO_ON_NOT_COMPILABLE
    )
    kw = dict(
        exam_id=exam["exam_id"],
        exam_type=exam.get("exam_type", "single_problem"),
        prerequisites=prereq,
        problem_weights=weights,
        zero_on_not_compilable=zero_compile,
    )
    if overrides:
        kw.update({k: tuple(v) if isinstance(v, list) else v for k, v in overrides.items()})
    return ExamPolicy(**kw)


def normalize_status(value: object) -> str | None:
    """Map free-form model output for a problem status onto STATUSES (None if unknown)."""
    if value is None:
        return None
    s = re.sub(r"[\s\-]+", "_", str(value).strip().lower())
    aliases = {
        "correct": "correct", "pass": "correct", "passed": "correct", "ok": "correct", "dung": "correct",
        "đúng": "correct", "full": "correct",
        "partial": "partial", "partially_correct": "partial", "partly_correct": "partial",
        "mot_phan": "partial", "một_phần": "partial",
        "wrong": "wrong", "incorrect": "wrong", "fail": "wrong", "failed": "wrong", "sai": "wrong",
        "runtime_error": "runtime_error", "crash": "runtime_error", "infinite_loop": "runtime_error",
        "timeout": "runtime_error", "segfault": "runtime_error", "error": "runtime_error",
        "not_attempted": "not_attempted", "empty": "not_attempted", "missing": "not_attempted",
        "not_implemented": "not_attempted", "none": "not_attempted", "khong_lam": "not_attempted",
        "không_làm": "not_attempted", "skipped": "not_attempted",
    }
    return aliases.get(s)


def clamp_rubric(rubric: dict) -> dict[str, int]:
    out = {}
    for dim in DIMENSIONS:
        v = rubric.get(dim, 0)
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = 0.0
        if math.isnan(v):
            v = 0.0
        out[dim] = int(min(max(math.floor(v + 0.5), 0), DIM_MAX[dim]))
    return out


def derive_logic(statuses: dict[str, str], weights: dict[str, float]) -> int | None:
    """logic (0-4) = 4 * weighted credit over problems, rounded half-up. None if statuses incomplete."""
    if not weights or any(statuses.get(pid) not in STATUS_CREDIT for pid in weights):
        return None
    total_w = sum(weights.values())
    credit = sum(weights[pid] * STATUS_CREDIT[statuses[pid]] for pid in weights)
    return int(math.floor(4 * credit / total_w + 0.5))


def apply_rules(
    rubric: dict,
    problem_status: dict[str, str] | None,
    policy: ExamPolicy,
    cfg: RuleConfig | None = None,
) -> tuple[dict[str, int], int, list[str]]:
    """Return (final_rubric, total_score, trace). Pure function — no I/O, no model calls."""
    cfg = cfg or RuleConfig()
    trace: list[str] = []
    r = clamp_rubric(rubric) if cfg.clamp else {d: int(rubric.get(d, 0)) for d in DIMENSIONS}
    statuses = {pid: s for pid, s in (problem_status or {}).items() if s is not None}

    if cfg.prerequisite and policy.prerequisites:
        fail_set = PREREQ_FAIL_STRICT if cfg.prereq_strict else PREREQ_FAIL
        for pid, dependents in policy.prerequisites.items():
            st = statuses.get(pid)
            if st is None:
                trace.append(f"prereq:{pid}:status_unknown->no_op")
                continue
            if st in fail_set:
                for dep in dependents:
                    if statuses.get(dep) not in (None, "not_attempted"):
                        trace.append(f"prereq:{pid}={st}->{dep}:not_graded(was {statuses[dep]})")
                    statuses[dep] = "not_attempted"

    prereq_failed = [
        pid for pid in policy.prerequisites
        if cfg.prerequisite
        and statuses.get(pid) in (PREREQ_FAIL_STRICT if cfg.prereq_strict else PREREQ_FAIL)
    ]

    if cfg.derive_logic and policy.exam_type == "multi_problem":
        new_logic = derive_logic(statuses, policy.problem_weights)
        if new_logic is not None and new_logic != r["logic"]:
            trace.append(f"derive_logic:{r['logic']}->{new_logic}")
            r["logic"] = new_logic

    if prereq_failed:
        for dim in policy.zero_on_prereq_fail:
            if r[dim] != 0:
                trace.append(f"prereq_zero:{dim}:{r[dim]}->0")
                r[dim] = 0

    if cfg.compile_gate and r["compilable"] == 0:
        for dim in policy.zero_on_not_compilable:
            if r[dim] != 0:
                trace.append(f"compile_zero:{dim}:{r[dim]}->0")
                r[dim] = 0

    return r, sum(r.values()), trace
