"""Labels from execution signals (hướng E): the teacher conventions of docs/task2_teacher_rules.md applied to what
src/task2/exec_oracle.py observed. Returns the labels plus how sure the rule is, so a model can fill in the cause of
a wrong answer (logic / loop / function / algorithm) where execution cannot tell them apart.

single_problem (per test status):
- does not compile -> Lỗi biên dịch (G4); whole file commented -> Lỗi style (G5)
- every test right (a printed input prompt is not a fault, S211) -> [] (G5)
- a run that never ends -> Lỗi logic + Lỗi vòng lặp (S209)
- right values, wrong spacing / letter case only -> Lỗi nhập/xuất (S205)
- wrong values -> Lỗi logic (+ Lỗi nhập/xuất when the format is also off); the cause is left to the model
multi_problem (per problem state, P1 is the prerequisite, G3):
- P1 wrong: Lỗi hard-code when P1 is sized by a constant / opens a fixed file name / only reads the exam CSV right
  (S108, S112), Lỗi hàm when it crashes on a stoi/stof conversion (S113, S114), else Lỗi logic (S105, S110)
- P1 right: a problem that never ends -> Lỗi logic + Lỗi vòng lặp (S106, S107); else the first wrong problem decides:
  the data structure built wrong (P2) or the age formula (P3 of the generals list) -> Lỗi thuật toán (S102, S104),
  other wrong results -> Lỗi logic (S101). Problems left empty carry no label (G2).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.task2.exec_oracle import ExecResult

OK = ("pass", "prompt_then_pass")
FMT = ("whitespace", "case")


@dataclass
class RuleLabels:
    labels: list[str]
    sure: bool          # True: execution decides the whole label set; False: a wrong answer whose cause is unknown
    reason: str


def rule_labels(r: ExecResult, code: str = "") -> RuleLabels | None:
    """None when there is no signal (unknown exam, the harness could not be built with the submission)."""
    if not r.compiles:
        extra = ["Lỗi hard-code"] if _includes_csv(code) else []  # S103: #include of the csv file
        return RuleLabels(["Lỗi biên dịch", *extra], True, "compile error")
    if r.all_commented:
        return RuleLabels(["Lỗi style"], True, "whole file commented")
    if r.kind is None or not r.harness_ok:
        return None
    if r.states:
        return _multi(r)
    return _single(r)


def _includes_csv(code: str) -> bool:
    return bool(re.search(r'#\s*include\s*"[^"]*\.csv"', code))


def _single(r: ExecResult) -> RuleLabels:
    st = list(r.statuses.values())
    if all(s in OK for s in st):
        return RuleLabels([], True, "all tests pass")
    if "timeout" in st:
        return RuleLabels(["Lỗi logic", "Lỗi vòng lặp"], False, "timeout")
    if all(s in OK + FMT for s in st):
        return RuleLabels(["Lỗi nhập/xuất"], True, "format only")
    if any(s in FMT for s in st):
        return RuleLabels(["Lỗi nhập/xuất", "Lỗi logic"], False, "format + wrong values")
    return RuleLabels(["Lỗi logic"], False, f"wrong values ({sum(s in OK for s in st)}/{len(st)} pass)")


def _multi(r: ExecResult) -> RuleLabels:
    s = r.states
    if s["P1"] != "ok":
        if s["P1"] == "missing" and all(v == "missing" for v in s.values()):
            return RuleLabels([], False, "nothing done")
        if r.hardcode_size or r.hardcode_file or r.p1_variant_fail:
            return RuleLabels(["Lỗi hard-code"], True, "P1 hard-coded")
        if s["P1"] == "crash" and r.uses_stoi:
            return RuleLabels(["Lỗi hàm"], False, "P1 crash with stoi")
        return RuleLabels(["Lỗi logic"], False, f"P1 {s['P1']}")
    rest = {p: s[p] for p in ("P2", "P3", "P4")}
    if "timeout" in rest.values():
        return RuleLabels(["Lỗi logic", "Lỗi vòng lặp"], True, "infinite loop")
    for p, v in rest.items():
        if v in ("fail", "crash", "partial"):
            algo = p == "P2" or (p == "P3" and r.kind == "generals_ll")
            return RuleLabels(["Lỗi thuật toán" if algo else "Lỗi logic"], False, f"{p} {v}")
    return RuleLabels([], True, "all problems right or left empty")


CAUSES = ("Lỗi logic", "Lỗi vòng lặp", "Lỗi hàm", "Lỗi thuật toán", "Lỗi mảng/chuỗi")


def combine(rl: RuleLabels | None, model: list[str] | None, max_labels: int = 3) -> list[str]:
    """Final labels: the rule labels when execution decides them; a wrong answer of unknown cause gets the model's
    cause labels added (G1: at most 3); no signal -> the model's labels (Lỗi logic without a model)."""
    if rl is None:
        return list(model) if model is not None else ["Lỗi logic"]
    if rl.sure or not model:
        return list(rl.labels)
    extra = [lab for lab in model if lab in CAUSES and lab not in rl.labels]
    return (list(rl.labels) + extra)[:max_labels]
