"""Defect -> taxonomy map (synth_plan.md section T2.1) and defect registry.

Each synthetic record is created by injecting a known defect into a known base solution, so the
Task 2 labels are derived deterministically from the defect instead of being guessed. A defect
has a *primary* label (always attached) and *secondary* labels (attached only when the caller
confirms the condition, e.g. the compile error sits inside a loop).

The registry also records the Task 1 rulebook rule id a defect produces, so mutators and the
labeler stay in sync (see src/synth/labeler.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

LABEL_SPACE = (
    "Lỗi biên dịch",
    "Lỗi nhập/xuất",
    "Lỗi logic",
    "Lỗi vòng lặp",
    "Lỗi mảng/chuỗi",
    "Lỗi hàm",
    "Lỗi edge case",
    "Lỗi thuật toán",
    "Lỗi hard-code",
    "Lỗi style",
)
_LABEL_ORDER = {label: i for i, label in enumerate(LABEL_SPACE)}


@dataclass(frozen=True)
class Defect:
    id: str
    name: str
    primary: tuple[str, ...]
    secondary: tuple[str, ...] = ()
    rules: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for label in (*self.primary, *self.secondary):
            if label not in _LABEL_ORDER:
                raise ValueError(f"{self.id}: unknown label {label!r}")


def _d(id_, name, primary=(), secondary=(), **rules) -> Defect:
    return Defect(id_, name, tuple(primary), tuple(secondary), rules)


DEFECTS: dict[str, Defect] = {
    d.id: d
    for d in (
        _d("D00", "comment toàn bộ / file rỗng", ["Lỗi biên dịch"], ["Lỗi style"], single="S0", multi="M0"),
        _d("D01", "lỗi cú pháp", ["Lỗi biên dịch"], ["Lỗi vòng lặp", "Lỗi logic"], single="S1", multi="M1"),
        _d("D02", "biến/hàm chưa khai báo", ["Lỗi biên dịch"], ["Lỗi vòng lặp", "Lỗi logic"], single="S1", multi="M1"),
        _d("D03", 'include "x.csv"', ["Lỗi biên dịch", "Lỗi hard-code"], [], single="S1", multi="M1"),
        _d("D04", "vòng lặp vô hạn", ["Lỗi vòng lặp"], ["Lỗi logic"], single="S2", multi="M2"),
        _d("D05", "lõi bỏ dở", ["Lỗi logic"], [], single="S2"),
        _d("D06", "sai token + logic sai hẳn", ["Lỗi nhập/xuất"], ["Lỗi logic"], single="S3"),
        _d("D07", "thừa ký tự trước đáp án", ["Lỗi nhập/xuất"], [], single="S5"),
        _d("D08", "sai lõi thuật toán (công thức/toán tử)", ["Lỗi thuật toán"], ["Lỗi vòng lặp"], single="S4"),
        _d("D09", "hàm phụ sai", ["Lỗi hàm"], ["Lỗi logic"], single="S4"),
        _d("D10", "stoi/stof crash", ["Lỗi hàm"], [], multi="M3"),
        _d("D11", "trả về mảng tĩnh cục bộ", ["Lỗi mảng/chuỗi"], ["Lỗi logic"], multi="M3"),
        _d("D12", "hàm chưa cài đặt (thân rỗng)", ["Lỗi hàm"], []),
        _d("D13", "sai công thức một câu", ["Lỗi thuật toán"], []),
        _d("D14", "sai biên một câu", ["Lỗi edge case"], []),
        _d("D14b", "bỏ sót phần tử cuối", ["Lỗi edge case"], ["Lỗi vòng lặp"], single="S11"),
        _d("D14c", "bỏ qua giá trị âm", ["Lỗi edge case"], [], single="S11"),
        _d("D14d", "sai khi chỉ có 1 phần tử", ["Lỗi edge case"], [], single="S11"),
        _d("D15s", "gán cứng kích thước vòng lặp", ["Lỗi hard-code"], ["Lỗi vòng lặp"], single="S4"),
        _d("D15", "hard-code tên file / kích thước (P1)", ["Lỗi hard-code"], [], multi="M3"),
        _d("D16a", "lỗi biên nhiều nhóm", ["Lỗi edge case"], [], single="S10"),
        _d("D16b", "lỗi biên đúng 1 nhóm", ["Lỗi edge case"], [], single="S11"),
        _d("D17", "hard-code đáp án", ["Lỗi hard-code"], [], single="S7"),
        _d("D18", "brute force sai biên", ["Lỗi thuật toán"], ["Lỗi edge case"], single="S8"),
        _d("D19", "sai token + logic sai một phần", ["Lỗi nhập/xuất"], ["Lỗi logic"], single="S9"),
        _d("D20", "mảng/chuỗi", ["Lỗi mảng/chuỗi"], [], single="S4"),
        _d("D21", "hàm", ["Lỗi hàm"], [], single="S4"),
        _d("D22", "style trên bài sai", ["Lỗi style"], []),
        _d("D23", "style trên bài đúng", ["Lỗi style"], [], single="S12"),
    )
}


def defect_taxonomy(defect_id: str, extra_secondary: tuple[str, ...] = ()) -> list[str]:
    """Labels for one defect: primary + the secondary conditions the caller confirms."""
    if defect_id not in DEFECTS:
        raise KeyError(f"unknown defect {defect_id!r}")
    d = DEFECTS[defect_id]
    return list(dict.fromkeys((*d.primary, *(extra_secondary or ()))))


def taxonomy_for(defect_ids, extra: tuple[str, ...] = (), extra_secondary: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    """Combine labels of several defects (overlapping/stacked defects), dedup, order by label space."""
    extra_secondary = extra_secondary or {}
    labels: list[str] = []
    for did in defect_ids:
        labels.extend(defect_taxonomy(did, extra_secondary.get(did, ())))
    labels.extend(extra)
    return sorted(dict.fromkeys(labels), key=lambda l: _LABEL_ORDER[l])


def defect_for_rule(rule_id: str, exam_type: str) -> str:
    """Reverse lookup: the defect a given Task 1 rule id corresponds to (best effort)."""
    key = "single" if exam_type == "single_problem" else "multi"
    matches = [d.id for d in DEFECTS.values() if d.rules.get(key) == rule_id]
    if matches:
        return matches[0]
    raise KeyError(f"no defect maps to rule {rule_id!r} for {exam_type!r}")
