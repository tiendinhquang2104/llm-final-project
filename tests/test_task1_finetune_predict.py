"""CPU-only checks for predicting an unlabelled release with the Task 1 adapter (no model, no GPU)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.data.prompts import build_task1_messages, build_task1_prompt
from src.data.schema import ChatMLRecord
from src.task1.finetune import fallback_score, load_unlabelled_prompts, record_exam_type

ROOT = Path(__file__).resolve().parents[1]


def prompt_sample(**kw):
    base = dict(exam_id="E1", exam_type="single_problem", language="cpp11", grading_policy=None,
                exam_statement="Viết hàm.", code="int main(){}", compile_log="", test_report=None,
                rubric={"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2, "complexity": 1,
                        "code_quality": 1}, total_score=10)
    return SimpleNamespace(**{**base, **kw})


def write_release(root: Path, input_extra: dict | None = None) -> Path:
    (root / "submissions/E1").mkdir(parents=True)
    (root / "submissions/E1/E1-S1.cpp").write_text("int main(){return 0;}", encoding="utf-8")
    (root / "exams.json").write_text(json.dumps({"exams": [
        {"exam_id": "E1", "exam_type": "single_problem", "statement": "Viết hàm.", "grading_policy": "x"}]}),
        encoding="utf-8")
    inp = {"exam_id": "E1", "exam_type": "single_problem", "language": "cpp11",
           "code_file": "submissions/E1/E1-S1.cpp", "compile_log": "", "test_report": None, **(input_extra or {})}
    (root / "task1_grading.json").write_text(json.dumps({"samples": [{"sample_id": "E1-S1", "input": inp}]}),
                                             encoding="utf-8")
    return root


def test_inference_prompt_is_the_training_prompt_without_answer():
    sample = prompt_sample()
    messages, target = build_task1_messages(sample)
    assert build_task1_prompt(sample) == messages[:2]
    assert messages[2] == {"role": "assistant", "content": target}


def test_unlabelled_release_prompts(tmp_path):
    prompts = load_unlabelled_prompts(write_release(tmp_path))
    assert [p["sample_id"] for p in prompts] == ["E1-S1"]
    sample = prompt_sample(code="int main(){return 0;}", grading_policy="x")
    assert prompts[0]["messages"] == build_task1_prompt(sample)


def test_feedback_in_input_is_refused(tmp_path):
    with pytest.raises(ValueError, match="feedback"):
        load_unlabelled_prompts(write_release(tmp_path, {"feedback": "Sai P1"}))


def gold(sample_id, exam_type, logic):
    rubric = {"compilable": 1, "io_format": 1, "logic": logic, "edge_case": 1, "complexity": 1, "code_quality": 1}
    target = json.dumps({"rubric": rubric, "total_score": sum(rubric.values())})
    return ChatMLRecord(sample_id=sample_id, task="task1", exam_id="EX", split="train", target=target, text="",
                        messages=[{"role": "system", "content": "s"},
                                  {"role": "user", "content": f"exam_id: EX\nexam_type: {exam_type}\n..."},
                                  {"role": "assistant", "content": target}])


def test_fallback_uses_same_exam_type_median():
    records = [gold("A", "multi_problem", 0), gold("B", "multi_problem", 1), gold("C", "single_problem", 4)]
    assert record_exam_type(records[0]) == "multi_problem"
    out = fallback_score(records, "multi_problem")
    assert out["rubric"]["logic"] == 0  # median_low of {0, 1}
    assert out["total_score"] == sum(out["rubric"].values())
    assert fallback_score(records, "single_problem")["rubric"]["logic"] == 4


def test_public_release_prompts_if_present():
    root = ROOT / "data/raw/public_test_release"
    if not (root / "task1_grading.json").exists():
        pytest.skip("public test release not extracted locally")
    prompts = load_unlabelled_prompts(root)
    assert len(prompts) == 328 and len({p["exam_id"] for p in prompts}) == 6  # current official release


def test_validation_error_report(tmp_path):
    from src.task1.finetune import validation_error_report

    gold_rub = {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2, "complexity": 1, "code_quality": 1}
    near = {**gold_rub, "code_quality": 0}
    far = {**gold_rub, "logic": 1, "edge_case": 0}
    details = [
        {"sample_id": "A", "exam_id": "EX01", "gold": {"rubric": gold_rub, "total_score": 10},
         "prediction": {"rubric": near, "total_score": 9}, "strict_output_ok": True},
        {"sample_id": "B", "exam_id": "EX02", "gold": {"rubric": gold_rub, "total_score": 10},
         "prediction": {"rubric": far, "total_score": 5}, "strict_output_ok": True},
        {"sample_id": "C", "exam_id": "EX02", "gold": {"rubric": gold_rub, "total_score": 10},
         "prediction": None, "strict_output_ok": False},
    ]
    (tmp_path / "gold_only/epoch_2").mkdir(parents=True)
    (tmp_path / "gold_only/epoch_2/validation_predictions.json").write_text(json.dumps(details), encoding="utf-8")
    (tmp_path / "training_summary.json").write_text(json.dumps({
        "selected_variant": "gold_only", "selected_epoch": 2,
        "selected_metrics": {"qwk": 0.5, "mae": 2.0, "n": 3}}), encoding="utf-8")
    report = validation_error_report(tmp_path)
    assert "| B |" in report and "| C |" in report and "| A |" not in report  # |10-9| < 2 is not flagged
    assert "logic 4→1" in report
    assert "2/3 samples" in report


def test_compile_log_is_cut_like_the_organizer_logs():
    from src.data.prompts import COMPILE_LOG_MAX_CHARS

    long_log = "student.cpp:1:1: error: x\n" * 5000
    user = build_task1_prompt(prompt_sample(compile_log=long_log))[1]["content"]
    assert long_log.strip()[:COMPILE_LOG_MAX_CHARS] in user
    assert long_log.strip()[:COMPILE_LOG_MAX_CHARS + 50] not in user
    assert "(không có compile log)" in build_task1_prompt(prompt_sample(compile_log="  "))[1]["content"]


def test_plain_template_scores_multi_problem_and_float_error_report():
    from src.evaluation.error_analysis import to_markdown
    from src.task1.pipeline import valid_parsed
    from src.task1.scorer import parse_output

    plain = parse_output(json.dumps({"compilable": 1, "io_format": 1, "logic": 2, "edge_case": 1,
                                     "complexity": 1, "code_quality": 1}))
    assert valid_parsed(plain, "multi_problem", "plain")  # e1 asks for six scores only
    assert not valid_parsed(plain, "multi_problem", "structured")  # structured still needs the P1 verdict
    report = {"n": 1, "threshold": 2, "n_big": 1, "by_exam": {}, "tag_counts": {}, "cases": [{
        "sample_id": "X", "gold_total": 7.5, "pred_total": 4.25, "llm_total": 4.25, "diff": -3.25,
        "dim_diff": {"logic": -2.25, "edge_case": -1.0}, "compile": "", "tests": "", "problems": {}, "tags": [],
        "rule_trace": [], "rationale": ""}]}
    text = to_markdown(report, "t")
    assert "logic-2.25" in text and "| -3.25 |" in text


def test_compile_log_keeps_errors_and_drops_warnings():
    from src.data.prompts import NO_COMPILE_ERROR, compile_errors_only

    warn = "student.cpp:6:1: warning: ISO C++ forbids declaration of 'main' with no type\n    6 | main()\n      | ^~~~\n"
    err = "student.cpp:7:1: error: 'Battle' does not name a type\n    7 | Battle battle;\n      | ^~~~~~\n"
    ctx = "student.cpp: In function 'int prob3()':\n"
    link = "/usr/bin/ld: crt1.o: in function `_start':\n(.text+0x1b): undefined reference to `main'\ncollect2: error: ld returned 1 exit status\n"
    assert compile_errors_only(warn) == ""
    assert compile_errors_only(ctx + warn + err) == err.strip()  # error kept with its source excerpt
    assert compile_errors_only(link).count("\n") == 2  # linker failure (no main) kept
    user = build_task1_prompt(prompt_sample(compile_log=warn))[1]["content"]
    assert NO_COMPILE_ERROR in user and "warning" not in user
