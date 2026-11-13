"""Compile verdict decided in code from the g++ log (API experiment e7)."""

from __future__ import annotations

from src.data.loader import DIMENSIONS
from src.task1.compile_signal import ERROR, OK, UNKNOWN, compile_section, compile_verdict
from src.task1.prerequisite_rules import RuleConfig, apply_rules, policy_from_exam

WARN = "/tmp/tmpab12/student.cpp:10:1: warning: no return statement in function returning non-void [-Wreturn-type]\n"
ERR = "/tmp/tmpab12/student.cpp:25:38: error: 'cnt' was not declared in this scope\n   25 | cnt++;\n"
NO_MAIN = ("/usr/bin/ld: Scrt1.o: in function `_start':\n(.text+0x1b): undefined reference to `main'\n"
           "collect2: error: ld returned 1 exit status")
NO_BODY = "/usr/bin/ld: a.o: in function `main':\n(.text+0x1b): undefined reference to `prob2(int)'\ncollect2: error: ld returned 1 exit status"
ENGLISH = ("- There are NO scores for ideas, only executable programs will be evaluated,\n"
           "- The following submissions will be marked with a 0 score:\n  - UNCOMPILABLE submission,\n  - Copied code.")
FULL = {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2, "complexity": 1, "code_quality": 1}
RULES = RuleConfig(compile_from_log=True, quality_point_when_not_compilable=True)


def exam(statement):
    return {"exam_id": "E", "exam_type": "single_problem", "statement": statement, "problems": [{"pid": "P1"}]}


def test_verdict_from_log():
    assert compile_verdict(ERR, True) == ERROR and compile_verdict(WARN + ERR, True) == ERROR
    assert compile_verdict(WARN, True) == OK and compile_verdict(NO_MAIN, True) == OK
    assert compile_verdict(NO_BODY, True) == ERROR  # a function without a body is a real build failure
    assert compile_verdict("", True) == OK and compile_verdict(None, False) == UNKNOWN


def test_empty_file_gets_no_verdict():
    from types import SimpleNamespace

    from src.task1.compile_signal import sample_log

    assert compile_verdict(*sample_log(SimpleNamespace(code="  ", compile_log=NO_MAIN), True)) == UNKNOWN
    assert compile_verdict(*sample_log(SimpleNamespace(code="int f(){}", compile_log=NO_MAIN), True)) == OK


def test_prompt_section_states_the_verdict():
    assert "compilable = 0" in compile_section(ERR, True) and "tmpab12" not in compile_section(ERR, True)
    warn = compile_section(WARN, True)
    assert "compilable = 1" in warn and "no return statement" in warn
    assert "KHÔNG phải lỗi biên dịch" in compile_section(NO_MAIN, True)
    assert compile_section("", False) == "(không có thông tin biên dịch)"


def test_english_zero_score_clause_zeroes_everything():
    assert policy_from_exam(exam(ENGLISH)).zero_on_not_compilable == tuple(DIMENSIONS)
    assert "code_quality" not in policy_from_exam(exam("Print True or False.")).zero_on_not_compilable
    assert "code_quality" not in policy_from_exam(exam("Programs score 0 scores if slow.")).zero_on_not_compilable


def test_rules_follow_the_log_not_the_model():
    silent, strict = policy_from_exam(exam("Print True or False.")), policy_from_exam(exam(ENGLISH))
    r, total, trace = apply_rules(FULL, {"P1": "correct"}, silent, RULES, compile_ok=False)
    assert total == 1 and r["code_quality"] == 1 and trace[0].startswith("compile_log:")  # EX02: 3/3 samples
    assert apply_rules(FULL, {"P1": "correct"}, strict, RULES, compile_ok=False)[1] == 0  # statement: 0 score
    zero = {**FULL, "compilable": 0}
    assert apply_rules(zero, {"P1": "correct"}, silent, RULES, compile_ok=True)[1] == 10  # log says it compiles
    assert apply_rules(zero, {"P1": "correct"}, silent, RULES, compile_ok=None)[1] == 1  # no log: model's verdict
    assert apply_rules(zero, {"P1": "correct"}, silent, RuleConfig(), compile_ok=True)[1] == 1  # e2: unchanged
