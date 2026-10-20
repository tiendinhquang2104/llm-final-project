from types import SimpleNamespace

from src.task3.direct_baseline import build_direct_messages
from src.task3.prompts import build_messages


def _record(level):
    return SimpleNamespace(
        sample_id="TRAIN-FIXTURE",
        exam_id="TRAIN",
        exam_type="single_problem",
        target_feedback_level=level,
        statement="Statement fixture",
        grading_policy="",
        problems=[],
        code="int main() { return 0; }",
        level_definitions=[],
        compile_log=None,
        test_report=None,
        provenance={},
        source="real",
        split="real-train",
        gold_taxonomy=[],
        gold_feedback="",
        original_submission_id="TRAIN-FIXTURE",
        group_key="TRAIN-FIXTURE",
        code_hash="0" * 64,
        code_tokens_hash="1" * 64,
        normalized_code_hash="2" * 64,
        code_path=None,
        raw={"sample_id": "TRAIN-FIXTURE"},
    )


def test_round10_level_contract_matches_public_level_definitions():
    for level, required, forbidden in (
        ("Level 1 - Gợi ý nhẹ", "cần được rà soát", "nguyên nhân"),
        ("Level 2 - Chẩn đoán", "nguyên nhân", "cách làm tiếp theo"),
        ("Level 3 - Gợi ý sửa", "Hướng sửa:", "lời giải hoàn chỉnh"),
    ):
        record = _record(level)
        direct = "\n".join(message["content"] for message in build_direct_messages(record))
        pipeline = build_messages(record, [], prompt_policy_version=7)[0]["content"]
        assert required in direct
        assert forbidden in direct
        assert required in pipeline
        assert forbidden in pipeline
