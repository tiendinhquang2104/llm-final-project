"""Hướng E: execution oracle on the reference solutions (needs a compiler) and the teacher-rule mapping."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from src.task2.exec_oracle import ExecResult, function_bodies, is_missing, multi_cases, single_tests
from src.task2.exec_rules import RuleLabels, combine, rule_labels

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "exec_oracle"
EXAMS = ROOT / "data" / "raw" / "public_test_release" / "exams.json"
KIND_EXAM = {"armstrong": "Class03-Midterm-1", "dedup": "Class03-Midterm-2", "login": "Class03-Final-1",
             "generals_ll": "Class01-Test1", "generals_bst": "Class01-Test2", "battles_ll": "Class02-Test1"}


def _compiler():
    from src.task2.exec_oracle import env_compiler
    if shutil.which("g++") and Path("/proc").exists():
        return env_compiler({"backend": "native"})
    if shutil.which("docker") and subprocess.run(["docker", "info"], capture_output=True).returncode == 0:
        return env_compiler({"backend": "docker"})
    return None


@pytest.fixture(scope="module")
def run():
    if not EXAMS.exists():
        pytest.skip("no public_test_release (exam statements + CSV files)")
    comp = _compiler()
    if comp is None:
        pytest.skip("needs g++ (Linux) or a running Docker")
    from src.task2.exec_oracle import Oracle
    exams = {e["exam_id"]: e for e in json.loads(EXAMS.read_text(encoding="utf-8"))["exams"]}

    def _run(tmp_path, codes: dict[str, str]):
        samples = [NS(sample_id=k, exam_id=KIND_EXAM[k.split(":")[0]], code=c, compile_log="") for k, c in codes.items()]
        return Oracle(comp, cache_dir=tmp_path / "cache").run(samples, exams)
    return _run


def test_reference_solutions_pass_every_case(run, tmp_path):
    res = run(tmp_path, {k: (FIX / f"{k}.cpp").read_text() for k in KIND_EXAM})
    for k, r in res.items():
        assert r.harness_ok, k
        assert all(s == "pass" for s in r.statuses.values()), (k, r.statuses)
        if r.states:
            assert set(r.states.values()) == {"ok"}, (k, r.states)


def test_broken_solutions_are_caught(run, tmp_path):
    arm = (FIX / "armstrong.cpp").read_text().replace("p *= t % 10", "p = (t % 10) * (t % 10) * (t % 10)")
    gen = (FIX / "generals_ll.cpp").read_text()
    no_bc = gen.replace('int b = g.born.era == "BC" ? -g.born.year : g.born.year;', "int b = g.born.year;") \
               .replace('int d = g.death.era == "BC" ? -g.death.year : g.death.year;', "int d = g.death.year;")
    fixed = gen.replace("while (getline(f, line)) if (!line.empty()) n++;", "n = 20;")
    p4_empty = gen[:gen.index("void prob4")] + "void prob4(Node*& head, string nat) {\n}\n"
    loop = gen.replace("for (Node* p = head->next; p; p = p->next)", "for (Node* p = head->next; p; )")
    res = run(tmp_path, {"armstrong:cube": arm, "generals_ll:bc": no_bc, "generals_ll:fixed": fixed,
                         "generals_ll:p4": p4_empty, "generals_ll:loop": loop})
    assert rule_labels(res["armstrong:cube"]).labels == ["Lỗi logic"]
    assert res["generals_ll:bc"].states["P3"] in ("partial", "fail")
    assert rule_labels(res["generals_ll:bc"]).labels == ["Lỗi thuật toán"]
    assert res["generals_ll:fixed"].p1_variant_fail
    assert rule_labels(res["generals_ll:fixed"]).labels == ["Lỗi hard-code"]
    assert res["generals_ll:p4"].states["P4"] == "missing"
    assert rule_labels(res["generals_ll:p4"]).labels == []
    assert rule_labels(res["generals_ll:loop"]).labels == ["Lỗi logic", "Lỗi vòng lặp"]


def test_tests_follow_the_statement():
    arm = {inp.strip(): exp for _, inp, exp in single_tests("armstrong")}
    assert arm["1634"] == "True" and arm["123"] == "False" and arm["9474"] == "True" and arm["10"] == "False"
    login = {inp.strip(): exp for _, inp, exp in single_tests("login")}
    assert login["harry potter"] == "hap" and login["tom riddle"] == "tomr"
    dedup = [t for t in single_tests("dedup") if t[0] == "example"]
    assert dedup[0][2] == "6\n1 5 3 7 2 6" and dedup[1][2] == "1\n5"


def test_multi_cases_expected_values():
    p3 = {c["id"]: c["expected"] for c in multi_cases("generals_ll") if c["pid"] == "P3"}
    assert p3["P30"] == "Helmuth von Moltke the Elder"   # 91 years
    assert p3["P31"] == "Gaius Marius"                   # 157 BC - 86 BC: wrong without the BC rule
    assert p3["P32"] == "Alexander Suvorov" and p3["P33"] == "Gaius Marius"  # tie (71): the first one


def test_function_bodies_and_missing():
    code = "int prob1(string f, int& n) {\n  // todo\n}\nNode* prob2(General* g, int n) { return NULL; }\n" \
           "int prob3(Node* h) { int c = 0; for (Node* p = h; p; p = p->next) c++; return c; }\n"
    b = function_bodies(code)
    assert set(b) == {"P1", "P2", "P3"}
    assert is_missing(b["P1"]) and is_missing(b["P2"]) and not is_missing(b["P3"]) and is_missing(b.get("P4"))


def _res(**kw):
    base = dict(sample_id="x", kind="armstrong", compiles=True, all_commented=False)
    return ExecResult(**{**base, **kw})


def test_rules_single_and_multi():
    assert rule_labels(_res(compiles=False)).labels == ["Lỗi biên dịch"]
    assert rule_labels(_res(compiles=False), '#include "generals.csv"\n').labels == ["Lỗi biên dịch", "Lỗi hard-code"]
    assert rule_labels(_res(all_commented=True)).labels == ["Lỗi style"]
    assert rule_labels(_res(statuses={"t0": "pass", "t1": "prompt_then_pass"})).labels == []
    assert rule_labels(_res(statuses={"t0": "whitespace", "t1": "pass"})).labels == ["Lỗi nhập/xuất"]
    assert rule_labels(_res(statuses={"t0": "timeout", "t1": "fail"})).labels == ["Lỗi logic", "Lỗi vòng lặp"]
    wrong = rule_labels(_res(statuses={"t0": "fail", "t1": "pass"}))
    assert wrong.labels == ["Lỗi logic"] and not wrong.sure
    multi = dict(kind="generals_ll", statuses={"P1A": "pass"})
    st = {"P1": "fail", "P2": "ok", "P3": "ok", "P4": "ok"}
    assert rule_labels(_res(**multi, states=st, hardcode_size=True)).labels == ["Lỗi hard-code"]
    assert rule_labels(_res(**multi, states={**st, "P1": "crash"}, uses_stoi=True)).labels == ["Lỗi hàm"]
    assert rule_labels(_res(**multi, states={**st, "P1": "ok", "P2": "fail", "P4": "partial"})).labels == ["Lỗi thuật toán"]
    assert rule_labels(_res(**multi, states={**st, "P1": "ok", "P4": "partial"})).labels == ["Lỗi logic"]
    assert rule_labels(_res(**multi, states={"P1": "ok", "P2": "ok", "P3": "missing", "P4": "missing"})).labels == []
    assert rule_labels(_res(harness_ok=False)) is None


def test_combine_adds_model_causes_only_when_unsure():
    sure = RuleLabels([], True, "all pass")
    unsure = RuleLabels(["Lỗi logic"], False, "wrong values")
    model = ["Lỗi hàm", "Lỗi style", "Lỗi vòng lặp", "Lỗi thuật toán"]
    assert combine(sure, model) == []
    assert combine(unsure, model) == ["Lỗi logic", "Lỗi hàm", "Lỗi vòng lặp"]
    assert combine(unsure, None) == ["Lỗi logic"]
    assert combine(None, ["Lỗi style"]) == ["Lỗi style"] and combine(None, None) == ["Lỗi logic"]
