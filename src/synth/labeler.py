"""Deterministic rubric/taxonomy labeler — implementation of docs/task1_rulebook.md.

Rules are applied top-down and the first match wins (rulebook sections 1 and 2). The labeler is
pure: it consumes code-behaviour *signals* (produced by ``src/synth/verify.py``) and returns a
rubric, a total and a taxonomy. No LLM judgement is involved, so the same signals always label
the same way.

Agreed resolutions (2026-10-13):

* multi_problem per-question weight is 2.5 (``exams.json`` / decision Q3); the total is
  ``round_half_down(sum of per-question points)``.
* The rulebook's T-split row ``T=3 = "chỉ P1 đúng"`` is inconsistent with 2.5 points per
  question (2.5 rounds to 2 under round-half-down, as the S102 example confirms). The practical
  equivalent is handled by the ``total == 2`` row below; the discrepancy is recorded as a data
  finding. ``total`` always equals the sum of the six dimensions (rulebook G1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil

RUBRIC_DIMS = ("compilable", "io_format", "logic", "edge_case", "complexity", "code_quality")
DIM_MAX = {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2, "complexity": 1, "code_quality": 1}
TOTAL_MAX = sum(DIM_MAX.values())

SINGLE_POINTS = {"ok": 2.5, "edge": 2.0, "partial": 1.25, "fail": 0.0, "missing": 0.0, "crash": 0.0}


@dataclass(frozen=True)
class Label:
    rule_id: str
    rubric: dict[str, int]
    total: int
    taxonomy: list[str]

    def __post_init__(self) -> None:
        if set(self.rubric) != set(RUBRIC_DIMS):
            raise ValueError(f"rubric must have exactly {RUBRIC_DIMS}")
        for d, v in self.rubric.items():
            if not 0 <= v <= DIM_MAX[d]:
                raise ValueError(f"{d}={v} out of range 0..{DIM_MAX[d]}")
        if self.total != sum(self.rubric.values()):
            raise ValueError(f"total={self.total} != sum(rubric)={sum(self.rubric.values())}")


@dataclass(frozen=True)
class SingleSignals:
    """Behaviour signals for a single_problem submission (EX02-style, stdin/stdout)."""

    has_code: bool = True
    compiles: bool = True
    terminates: bool = True
    core_incomplete: bool = False
    examples_only_pass: bool = False
    token_exact: bool = True
    token_normalized: bool = True
    normal_pass_ratio: float = 1.0
    edge_groups_failed: int = 0
    perf_ok: bool = True
    style_very_bad: bool = False
    taxonomy_hint: tuple[str, ...] = ()


@dataclass(frozen=True)
class MultiSignals:
    """Behaviour signals for a multi_problem submission (EX01-style, functions only)."""

    has_code: bool = True
    compiles: bool = True
    infinite_loop_any: bool = False
    p1_ok: bool = True
    problem_states: tuple[str, ...] = ("ok", "ok", "ok", "ok")
    taxonomy_hint: tuple[str, ...] = field(default_factory=tuple)


_SINGLE_RULES: dict[str, tuple[tuple[int, int, int, int, int, int], tuple[str, ...]]] = {
    "S0": ((0, 0, 0, 0, 0, 0), ("Lỗi biên dịch", "Lỗi style")),
    "S1": ((0, 0, 0, 0, 0, 1), ("Lỗi biên dịch",)),
    "S2": ((1, 0, 0, 0, 0, 1), ("Lỗi logic", "Lỗi vòng lặp")),
    "S3": ((1, 0, 0, 0, 1, 1), ("Lỗi nhập/xuất", "Lỗi logic")),
    "S7": ((1, 1, 1, 0, 0, 1), ("Lỗi hard-code",)),
    "S8": ((1, 1, 2, 0, 0, 1), ("Lỗi thuật toán", "Lỗi edge case")),
    "S9": ((1, 0, 2, 1, 1, 1), ("Lỗi nhập/xuất", "Lỗi logic")),
    "S4": ((1, 1, 2, 1, 1, 1), ("Lỗi logic",)),
    "S10": ((1, 1, 4, 0, 1, 1), ("Lỗi edge case",)),
    "S11": ((1, 1, 4, 1, 1, 1), ("Lỗi edge case",)),
    "S12": ((1, 1, 4, 2, 1, 0), ("Lỗi style",)),
    "S5": ((1, 0, 4, 2, 1, 1), ("Lỗi nhập/xuất",)),
    "S6": ((1, 1, 4, 2, 1, 1), ()),
}

_S4_KIND_TAXONOMY = {
    "logic": ("Lỗi logic",),
    "algorithm": ("Lỗi thuật toán",),
    "function": ("Lỗi hàm",),
    "loop": ("Lỗi vòng lặp",),
    "string": ("Lỗi mảng/chuỗi",),
}


def round_half_down(x: float) -> int:
    """Round to nearest integer, ties go down (rulebook M4: 8.75 -> 9, 9.5 -> 9, 2.5 -> 2)."""
    return int(ceil(x - 0.5))


def _label(rule_id: str, rubric: tuple[int, ...], taxonomy: tuple[str, ...]) -> Label:
    return Label(rule_id, dict(zip(RUBRIC_DIMS, rubric)), sum(rubric), list(taxonomy))


def label_single(s: SingleSignals) -> Label:
    """Apply the rulebook section 1 decision list (first match wins)."""
    format_ok = s.token_normalized
    ratio = s.normal_pass_ratio
    if not s.has_code:
        return _label("S0", *_rule("S0", s))
    if not s.compiles:
        return _label("S1", *_rule("S1", s))
    if not s.terminates or s.core_incomplete:
        return _label("S2", *_rule("S2", s))
    if not format_ok and ratio == 0:
        return _label("S3", *_rule("S3", s))
    if s.examples_only_pass and format_ok and ratio < 1:
        return _label("S7", *_rule("S7", s))
    if not s.perf_ok and s.edge_groups_failed >= 2 and 0 < ratio < 1 and format_ok:
        return _label("S8", *_rule("S8", s))
    if not format_ok and 0 < ratio < 1:
        return _label("S9", *_rule("S9", s))
    if format_ok and ratio < 1:
        return _label("S4", *_rule("S4", s))
    if s.edge_groups_failed >= 2:
        return _label("S10", *_rule("S10", s))
    if s.edge_groups_failed == 1:
        return _label("S11", *_rule("S11", s))
    if s.style_very_bad:
        return _label("S12", *_rule("S12", s))
    if not s.token_exact and ratio == 1:
        return _label("S5", *_rule("S5", s))
    return _label("S6", *_rule("S6", s))


def _rule(rule_id: str, s: SingleSignals) -> tuple[tuple[int, ...], tuple[str, ...]]:
    rubric, taxonomy = _SINGLE_RULES[rule_id]
    if rule_id == "S4" and s.taxonomy_hint:
        taxonomy = _S4_KIND_TAXONOMY.get(s.taxonomy_hint[0], taxonomy)
    elif s.taxonomy_hint and rule_id in ("S1", "S3", "S9"):
        taxonomy = tuple(dict.fromkeys((*taxonomy, *s.taxonomy_hint)))
    return rubric, taxonomy


def label_multi(m: MultiSignals) -> Label:
    """Apply the rulebook section 2 decision list (M0/M1/M2/M3 then M4)."""
    if not m.has_code:
        return _label("M0", (0, 0, 0, 0, 0, 0), ("Lỗi biên dịch", "Lỗi style"))
    if not m.compiles:
        return _label("M1", (0, 0, 0, 0, 0, 0), ("Lỗi biên dịch",))
    if m.infinite_loop_any:
        return _label("M2", (1, 1, 0, 0, 0, 0), ("Lỗi logic", "Lỗi vòng lặp"))
    if not m.p1_ok:
        return _label("M3", (1, 0, 0, 0, 0, 0), ("Lỗi hard-code",))
    states = tuple(m.problem_states)
    if not states:
        raise ValueError("problem_states must include at least P1")
    points = sum(SINGLE_POINTS.get(st, 0.0) for st in states)
    total = round_half_down(points)
    rubric = split_multi_total(total, states)
    taxonomy = tuple(dict.fromkeys((*_multi_taxonomy(states), *m.taxonomy_hint)))
    return _label("M4", rubric, taxonomy)


def split_multi_total(total: int, states: tuple[str, ...]) -> tuple[int, ...]:
    """Map a multi_problem total (P1 ok) to the six rubric dims (rulebook M4 table by composition).

    Keeps ``sum(dims) == total`` (G1); the documented ``T=3`` row is represented by ``total == 2``
    for the same composition (see module docstring)."""
    n_partial = sum(st == "partial" for st in states[1:])
    n_edge = sum(st == "edge" for st in states[1:])
    n_zero = sum(st in ("missing", "fail", "crash") for st in states[1:])
    if total >= 10:
        return (1, 1, 4, 2, 1, 1)
    if total == 9:
        if n_edge >= 1 and n_partial == 0:
            return (1, 1, 4, 1, 1, 1)
        return (1, 1, 3, 2, 1, 1)
    if total == 8:
        if n_zero >= 1 and n_partial == 0 and n_edge == 0:
            return (1, 1, 2, 2, 1, 1)
        return (1, 1, 3, 1, 1, 1)
    if total == 7:
        return (1, 1, 2, 1, 1, 1)
    if total == 6:
        return (1, 1, 1, 1, 1, 1)
    if total == 5:
        return (1, 1, 1, 0, 1, 1)
    if total == 4:
        return (1, 1, 1, 0, 0, 1)
    if total == 3:
        return (1, 1, 0, 0, 0, 1)
    if total == 2:
        return (1, 1, 0, 0, 0, 0)
    if total == 1:
        return (1, 0, 0, 0, 0, 0)
    return (0, 0, 0, 0, 0, 0)


def _multi_taxonomy(states: tuple[str, ...]) -> tuple[str, ...]:
    labels: list[str] = []
    if any(st == "edge" for st in states):
        labels.append("Lỗi edge case")
    if any(st == "partial" for st in states):
        labels.append("Lỗi logic")
    return tuple(labels)


def label(exam_type: str, signals: SingleSignals | MultiSignals) -> Label:
    if exam_type == "single_problem":
        if not isinstance(signals, SingleSignals):
            raise TypeError("single_problem expects SingleSignals")
        return label_single(signals)
    if exam_type == "multi_problem":
        if not isinstance(signals, MultiSignals):
            raise TypeError("multi_problem expects MultiSignals")
        return label_multi(signals)
    raise ValueError(f"unknown exam_type {exam_type!r}")


_MULTI_FIXED = {
    "M0": ((0, 0, 0, 0, 0, 0), ("Lỗi biên dịch", "Lỗi style")),
    "M1": ((0, 0, 0, 0, 0, 0), ("Lỗi biên dịch",)),
    "M2": ((1, 1, 0, 0, 0, 0), ("Lỗi logic", "Lỗi vòng lặp")),
    "M3": ((1, 0, 0, 0, 0, 0), ("Lỗi hard-code",)),
}


def label_from_rule(rule_id: str, taxonomy=(), total: int | None = None,
                    states: tuple[str, ...] | None = None) -> Label:
    """Build a Label for a known rule id (used when the defect is injected on purpose).

    For M4 pass either ``states`` (per-question statuses) or ``total``. Taxonomy overrides the
    rule default when provided.
    """
    tax = tuple(taxonomy)
    if rule_id in _SINGLE_RULES:
        dims, default = _SINGLE_RULES[rule_id]
        return _label(rule_id, dims, tax or default)
    if rule_id in _MULTI_FIXED:
        dims, default = _MULTI_FIXED[rule_id]
        return _label(rule_id, dims, tax or default)
    if rule_id == "M4":
        if states is None and total is None:
            raise ValueError("M4 needs states or total")
        if states is not None:
            points = sum(SINGLE_POINTS.get(st, 0.0) for st in states)
            total = round_half_down(points) if total is None else total
            dims = split_multi_total(total, states)
        else:
            dims = split_multi_total(total, ("ok", "missing", "missing", "missing"))
        return _label(rule_id, dims, tax or _multi_taxonomy(states or ()))
    raise KeyError(f"unknown rule_id {rule_id!r}")
