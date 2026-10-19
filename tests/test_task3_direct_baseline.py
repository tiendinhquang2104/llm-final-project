import json

import pytest

from src.task3.direct_baseline import (
    DirectBaselineError,
    apply_json_output_constraint,
    build_direct_messages,
    direct_retry_instruction,
    parse_and_validate_direct_output,
    run_direct_baseline,
)
from src.task3.inference import Generation, MockTokenizer
from src.task3.schema import Task3Record


def record(level="Level 3 - Gợi ý sửa"):
    return Task3Record(
        source="real", sample_id="EX02-S212", original_submission_id="EX02-S212",
        exam_id="EX02", exam_type="single_problem", statement="Print the result.",
        grading_policy=None, code_path="answer.cpp", code="int main(){ return 0; }",
        target_feedback_level=level, gold_taxonomy=["Lỗi biên dịch"],
        gold_feedback="reference feedback must not be prompted", level_definitions=[
            {"level": "Level 1 - Gợi ý nhẹ", "description": "Encouragement only"},
            {"level": "Level 2 - Chẩn đoán", "description": "Diagnosis only"},
            {"level": "Level 3 - Gợi ý sửa", "description": "Diagnosis and direction"},
            {"level": "Level 4 - Lời giải mẫu", "description": "Full solution"},
        ],
    )


def test_direct_prompt_has_required_inputs_but_excludes_gold_targets():
    prompt = build_direct_messages(record(), {"status": "unavailable", "diagnostic": ""})
    joined = "\n".join(message["content"] for message in prompt)
    assert "student_code" in joined
    assert "target_feedback_level" in joined
    assert "compiler unavailable" in joined
    assert "allowed_taxonomy_labels" in joined
    assert "reference feedback must not be prompted" not in joined
    assert '"taxonomy_error": ["Lỗi biên dịch"]' not in joined


def test_direct_json_constraint_prevents_markdown_fences_only_when_level_allows():
    tokenizer = MockTokenizer()
    config = {"do_sample": False}
    constrained = apply_json_output_constraint(config, tokenizer, ["Level 2 - Chẩn đoán"])
    assert constrained["bad_words_ids"] == [tokenizer.encode("```")]
    assert apply_json_output_constraint(config, tokenizer, ["Level 4 - Lời giải mẫu"]) == config


def test_level1_retry_repeats_no_technical_disclosure_contract():
    instruction = direct_retry_instruction("feedback violates requested Level: specific_diagnosis", record("Level 1 - Gợi ý nhẹ").target_feedback_level)
    assert "không nhắc chi tiết bài" in instruction
    assert "taxonomy_error" in instruction


def test_direct_output_accepts_exact_public_schema_and_level3_direction():
    result = parse_and_validate_direct_output(
        json.dumps({"taxonomy_error": ["Lỗi biên dịch"], "feedback": "Biến `cnt` chưa được khai báo. Hướng sửa: hãy khai báo biến trước khi sử dụng."}, ensure_ascii=False),
        record(),
    )
    assert result == {
        "taxonomy_error": ["Lỗi biên dịch"],
        "feedback": "Biến `cnt` chưa được khai báo. Hướng sửa: hãy khai báo biến trước khi sử dụng.",
    }


@pytest.mark.parametrize("text", [
    '{"taxonomy_error": [], "feedback": "Chưa đủ cơ sở."}',
    '{"taxonomy_error": ["wrong"], "feedback": "Biến `cnt` chưa được khai báo. Hướng sửa: hãy khai báo biến trước khi sử dụng."}',
    '{"taxonomy_error": [], "feedback": "Biến `cnt` chưa được khai báo."}',
])
def test_invalid_taxonomy_or_level3_contract_is_rejected(text):
    with pytest.raises(ValueError):
        parse_and_validate_direct_output(text, record())


def test_level1_cannot_disclose_taxonomy_or_specific_computation():
    with pytest.raises(ValueError):
        parse_and_validate_direct_output(
            '{"taxonomy_error": ["Lỗi biên dịch"], "feedback": "Biến cnt chưa được khai báo."}',
            record("Level 1 - Gợi ý nhẹ"),
        )


def test_level1_rejects_discussion_of_digit_exponent_details():
    with pytest.raises(ValueError, match="Level 1"):
        parse_and_validate_direct_output(
            json.dumps({"taxonomy_error": ["Lỗi logic"], "feedback": "Hãy kiểm tra lại số mũ của từng chữ số."}, ensure_ascii=False),
            record("Level 1 - Gợi ý nhẹ"),
        )


def test_failed_bounded_run_names_sample_id_without_returning_fallback():
    error = DirectBaselineError("EX02-S212", attempts=3)
    assert "EX02-S212" in str(error)
    assert error.attempts == 3
    assert "fallback" in str(error).lower() or "failed" in str(error).lower()


def test_failed_attempts_are_journaled_and_never_export_empty_prediction(tmp_path):
    class InvalidBackend:
        tokenizer = MockTokenizer()

        def generate(self, messages, config):
            return Generation("```json\n{}\n```", 5, 0.01, "eos", True)

    attempts = tmp_path / "private-attempts.jsonl"
    with pytest.raises(DirectBaselineError, match="EX02-S212"):
        run_direct_baseline(
            [record()], InvalidBackend(),
            {"context_limit": 10000, "max_new_tokens": 32, "max_retries": 2},
            attempts_path=attempts,
        )
    rows = [json.loads(line) for line in attempts.read_text().splitlines()]
    assert len(rows) == 3
    assert all(row["raw_text"] == "```json\n{}\n```" for row in rows)
    assert attempts.stat().st_mode & 0o777 == 0o600
