"""Execution summary block of the F-cls prompt and its training-time dropout."""
from __future__ import annotations

from types import SimpleNamespace as NS

from src.task2.cls_data import record, signal_dropout
from src.task2.exec_oracle import ExecResult
from src.task2.exec_summary import bank_suites, summary_text

ROOT_BANK = "src/synth/problems"


def _res(**kw):
    return ExecResult(**{"sample_id": "x", "kind": "single_problem", "compiles": True, "all_commented": False, **kw})


def test_single_summary_counts_per_group():
    r = _res(statuses={"t0": "pass", "t1": "fail", "t2": "timeout", "t3": "pass"},
             groups={"t0": "example", "t1": "edge", "t2": "edge", "t3": "normal"})
    text = summary_text(r, "en")
    assert "Total: 2/4 tests right." in text
    assert "- group example: 1/1 right" in text and "- group edge: 0/2 right (fail 1, timeout 1)" in text
    assert text.index("group example") < text.index("group edge") < text.index("group normal")


def test_multi_and_no_signal_summaries():
    r = _res(kind="multi_problem", states={"P1": "ok", "P2": "fail", "P3": "missing"}, prereq={"P1": ["P2", "P3"]},
             p1_variant_fail=True, hardcode_size=True)
    text = summary_text(r, "vi")
    assert "Câu tiên quyết: P1" in text and "- P2: fail" in text and "mảng kích thước hằng số" in text
    assert "Không có bộ test" in summary_text(None, "vi")
    assert "does not compile" in summary_text(_res(compiles=False), "en")
    assert "No runnable test suite" in summary_text(_res(kind=None), "en")


def test_bank_suites_use_the_bank_tests():
    suites = bank_suites(ROOT_BANK)
    s = suites["SYN-PERFECT"]
    assert s.exam_type == "single_problem" and s.tests[0]["stdin"].endswith("\n")
    assert {t["group"] for t in s.tests} <= {"example", "edge", "normal"}
    assert all(e.startswith("SYN-") for e in suites)            # synthetic exams only


def test_record_keeps_a_no_signal_prompt_and_dropout_is_deterministic():
    exam = {"exam_id": "E", "exam_type": "single_problem", "statement": "Print 1.", "problems": []}
    rows = []
    for i in range(200):
        s = NS(sample_id=f"s{i}", exam_id="E", exam_type="single_problem", code="int main(){}", compile_log="",
               test_report=None, labels=[])
        rows.append(record(exam, s, "synth", {"lang": "en"}, None, exec_text="### R\nTotal: 1/1\n",
                           no_signal_text="### R\nnone\n"))
    assert "Total: 1/1" in rows[0]["messages"][-1]["content"] and "none" in rows[0]["messages_nosig"][-1]["content"]
    a, b = signal_dropout(rows, 0.25), signal_dropout(rows, 0.25)
    dropped = [r["id"] for r in a if "none" in r["messages"][-1]["content"]]
    assert dropped == [r["id"] for r in b if "none" in r["messages"][-1]["content"]]
    assert 25 <= len(dropped) <= 75
    assert signal_dropout(rows, 0.0) is rows
