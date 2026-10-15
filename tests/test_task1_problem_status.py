"""P1..Pn verdicts in the Task 1 adapter: target format, parsing, exam policy (no GPU, no compiler)."""

import json
from types import SimpleNamespace

import pytest

from src.data.prompts import build_task1_messages, build_task1_prompt
from src.data.schema import ChatMLRecord
from src.task1.finetune import _validate_target, apply_policy, evaluate_generations, parse_generated
from src.task1.silver_data import load_status_file

RUBRIC = {"compilable": 1, "io_format": 1, "logic": 3, "edge_case": 2, "complexity": 1, "code_quality": 1}
MULTI = {"exam_id": "M", "exam_type": "multi_problem", "statement": "x",
         "problems": [{"pid": "P1", "max_score": 1, "is_prerequisite_for": ["P2", "P3", "P4"]},
                      {"pid": "P2"}, {"pid": "P3"}, {"pid": "P4"}]}


def sample(exam_type="multi_problem", status=None):
    return SimpleNamespace(exam_id="M", exam_type=exam_type, language="cpp11", grading_policy=None,
                           exam_statement="x", code="int main(){}", compile_log="", test_report=None,
                           rubric=RUBRIC, total_score=9, problem_status=status)


def test_prompt_asks_verdicts_only_for_multi_problem():
    assert '"problems"' in build_task1_prompt(sample())[1]["content"]
    assert '"problems"' not in build_task1_prompt(sample("single_problem"))[1]["content"]


def test_target_with_statuses_is_valid():
    _, target = build_task1_messages(sample(status={"P1": "wrong", "P2": "correct"}))
    obj = json.loads(target)
    assert list(obj) == ["problems", "rubric", "total_score"]
    _validate_target(target, "S")
    with pytest.raises(ValueError):
        _validate_target(json.dumps({**obj, "problems": [{"pid": "P1", "status": "great"}]}), "S")
    assert "problems" not in json.loads(build_task1_messages(sample())[1])  # unknown statuses -> rubric only


def test_parse_and_prerequisite_policy():
    text = json.dumps({"problems": [{"pid": "P1", "status": "wrong"}], "rubric": RUBRIC, "total_score": 9})
    pred, statuses, json_ok, strict_ok = parse_generated("```json\n" + text + "\n```")
    assert statuses == {"P1": "wrong"} and json_ok and strict_ok
    after, trace = apply_policy(pred, statuses, MULTI)
    assert after["rubric"] == {"compilable": 1, "io_format": 1, "logic": 0, "edge_case": 0, "complexity": 0,
                               "code_quality": 0} and after["total_score"] == 2
    assert any("prereq" in t for t in trace)
    bad = json.dumps({"problems": "P1 wrong", "rubric": RUBRIC, "total_score": 9})
    pred2, statuses2, _, strict2 = parse_generated(bad)
    assert pred2 is not None and statuses2 == {} and not strict2  # rubric kept, rule cannot fire


def test_evaluation_reports_before_and_after_rules():
    gold = json.dumps({"rubric": {**RUBRIC, "logic": 0, "edge_case": 0, "complexity": 0, "code_quality": 0},
                       "total_score": 2})
    rec = ChatMLRecord(sample_id="S", task="task1", exam_id="M", split="val", target=gold, text="",
                       messages=[{"role": "system", "content": "s"}, {"role": "user", "content": "u"},
                                 {"role": "assistant", "content": gold}])
    out = json.dumps({"problems": [{"pid": "P1", "status": "wrong"}], "rubric": RUBRIC, "total_score": 9})
    metrics, details = evaluate_generations([rec], {"S": out}, {"M": MULTI})
    assert metrics["mae"] == 0 and metrics["before_rules"]["mae"] == 7 and metrics["rules_applied"]
    assert details[0]["prediction_before_rules"]["total_score"] == 9


def test_status_file_mapping(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(json.dumps({"sample_id": "A", "observed_states": {"P2": "edge", "P1": "fail"}}) + "\n"
                 + json.dumps({"sample_id": "B", "observed_states": None}) + "\n", encoding="utf-8")
    assert load_status_file(f) == {"A": {"P1": "wrong", "P2": "partial"}}
