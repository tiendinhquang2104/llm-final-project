"""Labels from execution signals (hướng E): the teacher conventions of docs/task2_teacher_rules.md applied to what
src/task2/exec_oracle.py observed. Returns the labels plus how sure the rule is, so a model can fill in the cause of
a wrong answer (logic / loop / function / algorithm) where execution cannot tell them apart.

single_problem (per test status):
- does not compile -> Lỗi biên dịch (G4); whole file commented -> Lỗi style (G5)
- every test right (a printed input prompt is not a fault, S211) -> [] (G5)
- a run that never ends -> Lỗi logic + Lỗi vòng lặp (S209)
- right values, wrong spacing / letter case only -> Lỗi nhập/xuất (S205)
- wrong values -> Lỗi logic (+ Lỗi nhập/xuất when the format is also off); the cause is left to the model
multi_problem (per problem state; the prerequisite problem of the grading_policy, G3, is the one the exam marks
with is_prerequisite_for):
- prerequisite wrong: Lỗi hard-code when it is sized by a constant / opens a fixed file name / only reads the exam
  data file right (S108, S112), Lỗi hàm when it crashes on a stoi/stof conversion (S113, S114), else Lỗi logic
  (S105, S110); the problems after it are not graded
- prerequisite right: a problem that never ends -> Lỗi logic + Lỗi vòng lặp (S106, S107); else the first wrong
  problem decides: the one building the data structure (right after the prerequisite) -> Lỗi thuật toán (S102),
  later ones -> Lỗi logic (S101, S104). Problems left empty carry no label (G2).
- every run dies of a memory fault (SIGSEGV) -> + Lỗi mảng/chuỗi (S105; a fault on only some runs is not, S101 S104
  S106 S112)
- probe suites (no agreed answers, src/task2/test_gen.py): the prerequisite is judged by its record count on the
  data file and its resized copies, later problems only by crashes and endless runs; when nothing goes wrong the
  rules say nothing (None) and the model decides
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
    rl = _multi(r) if r.states else _single(r)
    if rl is not None and r.all_segfault and "Lỗi mảng/chuỗi" not in rl.labels:
        # every run dies of a memory fault: an array / string index or pointer error (S105); the run-based labels
        # stay, the cause is still open for the model
        rl = RuleLabels(rl.labels + ["Lỗi mảng/chuỗi"], False, rl.reason + " + memory fault on every run")
    return rl


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
    pids = list(s)
    # grading_policy: a prerequisite problem that is wrong means the problems after it are not graded (G3), so its
    # own state decides the labels; the exam marks it with is_prerequisite_for (the first problem if it does not)
    pre = next((p for p in pids if r.prereq.get(p)), pids[0])
    if s[pre] != "ok":
        if all(v == "missing" for v in s.values()):
            return RuleLabels([], False, "nothing done")
        if r.hardcode_size or r.hardcode_file or r.p1_variant_fail:
            return RuleLabels(["Lỗi hard-code"], True, f"{pre} hard-coded")
        if s[pre] == "crash" and r.uses_stoi:
            return RuleLabels(["Lỗi hàm"], False, f"{pre} crash with stoi")
        return RuleLabels(["Lỗi logic"], False, f"{pre} {s[pre]}")
    rest = {p: s[p] for p in pids if p != pre}
    if "timeout" in rest.values():
        return RuleLabels(["Lỗi logic", "Lỗi vòng lặp"], True, "infinite loop")
    for k, (p, v) in enumerate(rest.items()):
        if v in ("fail", "crash", "partial"):
            if r.probe:  # no expected outputs: a crash says the problem is wrong, not which way
                return RuleLabels(["Lỗi logic"], False, f"{p} {v} (probe)")
            # the problem right after the prerequisite builds the data structure (S102): a wrong one is an
            # algorithm fault; later ones are logic faults whose cause the model adds
            return RuleLabels(["Lỗi thuật toán" if k == 0 else "Lỗi logic"], False, f"{p} {v}")
    if r.probe:  # the later problems ran without a fault, but nothing says their answers are right
        return None
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
