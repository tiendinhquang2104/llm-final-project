"""Quota scheduler (synth_plan.md "Phân bổ 500 record train").

Each slot names the *rule* the plan asks for and the defects that may produce it. The build script
tries those defects on different exams / base variants / injection positions and keeps a record
only when the rule **observed by running the code** equals the slot's rule (labels are never taken
from the intention). Slots that cannot be filled are reported as a shortfall, not faked.

Multi-problem totals are reached by searching combinations of per-question defects; the label is
whatever the dataset harness observes.

Deviation from the plan, recorded in stats and docs: a multi_problem total of 3 is unreachable
under the rulebook's scoring (2.5 points per question, round-half-down: P1 alone = 2.5 -> 2, the
next possible sum is 3.75 -> 4), so its 15 slots go to totals 4, 5 and 6.
"""

from __future__ import annotations

_L1 = "Level 1 - Gợi ý nhẹ"
_L2 = "Level 2 - Chẩn đoán"
_L3 = "Level 3 - Gợi ý sửa"
_L4 = "Level 4 - Lời giải mẫu"
# 30% L1, 40% L2, 20% L3, 10% L4 (plan T3.1); re-balanced again after Task 3 duplication
LEVEL_CYCLE = (_L1, _L1, _L1, _L2, _L2, _L2, _L2, _L3, _L3, _L4)

EDGE_DEFECTS = ("D16b", "D14", "D14b", "D13", "D16a", "D14c", "D14d")

# (rule, count, candidate defect combos) -- single_problem, sums to 300 (plan table)
SINGLE_BUCKETS = [
    ("S6", 45, [()]),
    ("S5", 20, [("D07",)]),
    ("S11", 20, [(d,) for d in EDGE_DEFECTS]),
    ("S12", 20, [("D23",)]),
    ("S10", 25, [("D16a",), *[(d,) for d in EDGE_DEFECTS], ("D14", "D16b"), ("D14b", "D16b")]),
    ("S4", 8, [("D08",)]),
    ("S4", 16, [("D20",)]),
    ("S4", 12, [("D21",)]),
    ("S4", 14, [("D15s",)]),
    ("S9", 15, [("D19", "D08"), ("D19", "D20"), ("D19", "D21"), ("D19", "D16b")]),
    ("S8", 20, [("D18",), ("D18", "D16b"), ("D08", "D16a"), ("D20", "D16b")]),
    ("S7", 20, [("D17",)]),
    ("S3", 15, [("D06",), ("D19", "D08", "D20")]),
    ("S2", 20, [("D04",), ("D05",)]),
    ("S1", 25, [("D01",), ("D02",)]),
    ("S0", 5, [("D00",)]),
]

# (total, count) -- multi_problem, sums to 200
MULTI_BUCKETS = [(10, 25), (9, 25), (8, 20), (7, 15), (6, 20), (5, 25), (4, 20),
                 (2, 15), (1, 20), (0, 15)]
UNREACHABLE_MULTI_TOTALS = {3: 15}

# per-question defects tried when searching for a multi_problem total (None = leave correct)
MULTI_QUESTION_DEFECTS = (None, None, "D12", "D13", "D14", "D14b", "D16b", "D08", "D20")

# Which defects tend to produce each observed per-question state (measured on the bank, 2026-10-14).
# Used only to steer the search; the label is always the state the harness observes.
STATE_DEFECTS = {"ok": (None,), "edge": ("D14", "D16b", "D14b", "D14c", "D14d"), "partial": ("D20", "D14b"),
                 "missing": ("D12",), "fail": ("D08", "D20", "D13", "D21")}

# P2..P4 state combinations whose points (P1 ok = 2.5) round to each total. P4 usually prints P2's
# result, so P2 and P4 tend to share a state. Edge states are only planned where a total needs them
# (8, 9): the "Lỗi edge case" label is already well covered by S8/S10/S11.
MULTI_STATE_PLANS = {
    9: [("ok", "ok", "partial"), ("ok", "ok", "partial"), ("ok", "ok", "edge")],
    8: [("edge", "edge", "edge"), ("edge", "partial", "edge"), ("ok", "edge", "partial")],
    7: [("ok", "ok", "missing"), ("ok", "ok", "fail")],
    6: [("ok", "partial", "missing"), ("ok", "partial", "fail")],
    5: [("ok", "missing", "missing"), ("ok", "fail", "missing"), ("partial", "partial", "missing")],
    4: [("partial", "missing", "missing"), ("partial", "fail", "fail")],
}

# buckets only some exams can produce (need True/False output, a slow loop, extra edge groups):
# their per-exam cap is doubled in the build (balance vs. not losing them)
RARE_BUCKETS = {"single:S8", "single:S10", "single:S3", "single:S9"}

N_TRAPS_TEN = (20, 10)      # traps inside 10-point buckets (single, multi)
N_TRAPS_OTHER = 20          # traps stacked on defective records
N_STYLE_STACK = 45          # D22 stacked on wrong answers (rare label "Lỗi style")

TOTAL_SINGLE = sum(b[1] for b in SINGLE_BUCKETS)
TOTAL_MULTI = sum(b[1] for b in MULTI_BUCKETS)
TOTAL = TOTAL_SINGLE + TOTAL_MULTI


def level_for(i: int) -> str:
    return LEVEL_CYCLE[i % len(LEVEL_CYCLE)]


def single_slots(scale: float = 1.0) -> list[dict]:
    out = []
    for rule, count, combos in SINGLE_BUCKETS:
        n = count if scale == 1.0 else max(1, round(count * scale))
        out += [{"exam_type": "single_problem", "rule": rule, "combos": combos} for _ in range(n)]
    return out


def multi_slots(scale: float = 1.0) -> list[dict]:
    out = []
    for total, count in MULTI_BUCKETS:
        n = count if scale == 1.0 else max(1, round(count * scale))
        out += [{"exam_type": "multi_problem", "total": total} for _ in range(n)]
    return out


def bucket_summary() -> dict:
    return {"single": TOTAL_SINGLE, "multi": TOTAL_MULTI, "total": TOTAL,
            "multi_unreachable_moved": UNREACHABLE_MULTI_TOTALS}
