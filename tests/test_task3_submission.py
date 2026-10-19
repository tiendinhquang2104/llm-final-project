"""Offline submission contract tests use artificial TEST-ONLY identifiers."""

import json

import pytest

from src.synth.feedback import FEEDBACK_LEVELS
from src.synth.taxonomy import LABEL_SPACE
from src.task3.submission import load_requested_levels, validate_submission


def test_load_requested_levels_accepts_rows_and_preserves_order(tmp_path):
    path = tmp_path / "requested.json"
    path.write_text(
        json.dumps(
            {
                "requested_levels": [
                    {"sample_id": "TEST-A", "level": FEEDBACK_LEVELS[0]},
                    {"sample_id": "TEST-B", "target_feedback_level": FEEDBACK_LEVELS[2]},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_requested_levels(path) == {
        "TEST-A": FEEDBACK_LEVELS[0],
        "TEST-B": FEEDBACK_LEVELS[2],
    }


def test_load_official_numeric_requested_level_schema_and_rejects_bool(tmp_path):
    path = tmp_path / "requested.json"
    path.write_text(json.dumps([
        {"sample_id": "TEST-A", "requested_level": 1},
        {"sample_id": "TEST-B", "requested_level": 4},
    ]), encoding="utf-8")
    assert load_requested_levels(path) == {"TEST-A": FEEDBACK_LEVELS[0], "TEST-B": FEEDBACK_LEVELS[3]}

    for bad in (True, 0, 5, 1.0):
        path.write_text(json.dumps([{"sample_id": "TEST-A", "requested_level": bad}]), encoding="utf-8")
        with pytest.raises(ValueError, match="invalid"):
            load_requested_levels(path)


@pytest.mark.parametrize(
    "rows, message",
    [
        ([{"sample_id": "TEST-A", "level": FEEDBACK_LEVELS[0]}, {"sample_id": "TEST-A", "level": FEEDBACK_LEVELS[1]}], "duplicate"),
        ([{"sample_id": "TEST-A", "level": "Level 9"}], "invalid"),
        ([{"sample_id": "", "level": FEEDBACK_LEVELS[0]}], "invalid"),
    ],
)
def test_requested_levels_reject_duplicates_and_invalid_values(tmp_path, rows, message):
    path = tmp_path / "requested.json"
    path.write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_requested_levels(path)


def test_validate_submission_accepts_exact_two_field_contract(tmp_path):
    path = tmp_path / "predictions.json"
    predictions = [
        {"sample_id": "TEST-A", "output": {"taxonomy_error": [], "feedback": "Bài làm có phần cần xem lại."}},
        {"sample_id": "TEST-B", "output": {"taxonomy_error": [LABEL_SPACE[0]], "feedback": "Dòng nhập chưa được kiểm tra."}},
    ]
    path.write_text(json.dumps(predictions, ensure_ascii=False), encoding="utf-8")

    assert validate_submission(path, {"TEST-A": FEEDBACK_LEVELS[0], "TEST-B": FEEDBACK_LEVELS[1]}) == {
        "records": 2,
        "levels": {
            FEEDBACK_LEVELS[0]: 1,
            FEEDBACK_LEVELS[1]: 1,
            FEEDBACK_LEVELS[2]: 0,
            FEEDBACK_LEVELS[3]: 0,
        },
    }


@pytest.mark.parametrize(
    "predictions, message",
    [
        ([{"sample_id": "TEST-A", "output": {"taxonomy_error": [], "feedback": "ok"}}], "count"),
        ([{"sample_id": "TEST-A", "output": {"taxonomy_error": [], "feedback": "ok"}}, {"sample_id": "TEST-A", "output": {"taxonomy_error": [], "feedback": "ok"}}], "duplicate"),
        ([{"sample_id": "TEST-B", "output": {"taxonomy_error": [], "feedback": "ok"}}], "IDs"),
        ([{"sample_id": "TEST-A", "output": {"taxonomy_error": ["unknown"], "feedback": "ok"}}], "allowed labels"),
        ([{"sample_id": "TEST-A", "output": {"taxonomy_error": [], "feedback": " "}}], "nonempty"),
        ([{"sample_id": "TEST-A", "output": {"taxonomy_error": [], "feedback": "ok", "debug": True}}], "exactly"),
    ],
)
def test_validate_submission_rejects_malformed_output(tmp_path, predictions, message):
    path = tmp_path / "predictions.json"
    path.write_text(json.dumps(predictions, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        requested = {"TEST-A": FEEDBACK_LEVELS[0]}
        if message == "count":
            requested["TEST-B"] = FEEDBACK_LEVELS[1]
        validate_submission(path, requested)


