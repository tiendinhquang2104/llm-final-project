"""Task 1 follows the six label-space dimensions and equal problem weights."""

from types import SimpleNamespace

import pytest

from src.data.prompts import build_task1_messages
from src.data.task1_rubric import rubric_guide, statement_without_p1_gate
from src.task1.pipeline import valid_parsed
from src.task1.prerequisite_rules import ExamPolicy, apply_rules
from src.task1.prompts import exam_block
from src.task1.scorer import parse_output


LABEL_SPACE = {"rubric": {"dimensions": [
    {"name": name, "range": [0, maximum], "vi": description}
    for name, maximum, description in (
        ("compilable", 1, "Biên dịch được"),
        ("io_format", 1, "Đúng định dạng input/output"),
        ("logic", 4, "Đúng logic"),
        ("edge_case", 2, "Đúng edge case"),
        ("complexity", 1, "Độ phức tạp / hiệu năng"),
        ("code_quality", 1, "Code quality"),
    )
]}}


def test_rubric_comes_from_label_space():
    guide = rubric_guide(LABEL_SPACE)
    for dimension in LABEL_SPACE["rubric"]["dimensions"]:
        assert dimension["name"] in guide
        assert dimension["vi"] in guide
    bad = {"rubric": {"dimensions": LABEL_SPACE["rubric"]["dimensions"][:-1]}}
    with pytest.raises(ValueError, match="exactly the six"):
        rubric_guide(bad)
    with pytest.raises(ValueError, match="rubric.dimensions"):
        rubric_guide({})


def test_task1_prompt_ignores_p1_gate_and_cross_submission_comparison():
    statement = (
        "P1: đọc file. P2: xử lý danh sách.\n"
        "Lưu ý: nếu không đọc được file thì các câu còn lại **không** được chấm.\n"
        "If you fail to read the file, the remaining problems will **not** be graded.\n"
        "- SIMILAR to others,\n"
    )
    sample = SimpleNamespace(
        exam_id="EX01", exam_type="multi_problem", language="cpp11",
        exam_statement=statement,
        grading_policy="Nếu P1 (đọc file) sai thì các câu P2–P4 không được chấm.",
        code="int prob2() { return 1; }", compile_log=None, test_report=None,
        rubric={"compilable": 1, "io_format": 1, "logic": 2, "edge_case": 1,
                "complexity": 1, "code_quality": 1}, total_score=7,
    )
    messages, target = build_task1_messages(sample, LABEL_SPACE)
    prompt = messages[0]["content"] + messages[1]["content"]
    assert "trọng số bằng nhau" in prompt
    assert "Đúng logic" in prompt
    assert "P2: xử lý danh sách" in prompt
    assert "not** be graded" not in prompt
    assert "không** được chấm" not in prompt
    assert "SIMILAR to others" not in prompt
    assert "P1 (đọc file) sai" not in prompt
    assert "feedback" not in prompt.lower()
    assert '"total_score":7' in target


def test_api_prompt_omits_conflicting_problem_weights():
    exam = {
        "exam_id": "EX01", "exam_type": "multi_problem", "statement":
        "P1 đọc file. Nếu P1 (đọc file) sai thì các câu P2–P4 không được chấm.",
        "grading_policy": "Nếu P1 (đọc file) sai thì các câu P2–P4 không được chấm.",
        "problems": [
            {"pid": "P1", "max_score": 1, "is_prerequisite_for": ["P2"]},
            {"pid": "P2", "max_score": 4},
        ],
    }
    block = exam_block(exam, policy_in_prompt=False)
    assert "P1 đọc file" in block
    assert "trọng số 1" not in block
    assert "trọng số 4" not in block
    assert "câu tiên quyết" not in block
    assert "không được chấm" not in block


def test_valid_six_dimension_score_needs_no_p1_status_or_hard_gate():
    parsed = parse_output(
        '{"rubric":{"compilable":0,"io_format":1,"logic":2.5,'
        '"edge_case":1.25,"complexity":1,"code_quality":1}}'
    )
    assert valid_parsed(parsed, "multi_problem")
    policy = ExamPolicy("EX01", "multi_problem", prerequisites={"P1": ("P2",)})
    rubric, total, trace = apply_rules(parsed.rubric, {"P1": "wrong"}, policy)
    assert rubric == parsed.rubric
    assert total == 6.75
    assert trace == []


def test_statement_sanitizer_preserves_problem_content():
    text = "P1: input\nIf you fail to read the file, the remaining problems will **not** be graded.\nP2: output"
    clean = statement_without_p1_gate(text)
    assert "P1: input" in clean and "P2: output" in clean
    assert "not** be graded" not in clean
