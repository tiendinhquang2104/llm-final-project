"""CPU-only checks for the Task 1 QLoRA data and inference contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.schema import ChatMLRecord
from src.task1.finetune import (
    best_epoch,
    encode_inference_prompt,
    encode_training_record,
    evaluate_generations,
    load_task1_splits,
    parse_generated_score,
)

ROOT = Path(__file__).resolve().parents[1]
RUBRIC = {
    "compilable": 1, "io_format": 1, "logic": 2.25,
    "edge_case": 1.5, "complexity": 1, "code_quality": 1,
}
TARGET = json.dumps({"rubric": RUBRIC, "total_score": 7.75})


def record(sample_id="S1", split="train", task="task1", prompt="Grade C++ code"):
    return ChatMLRecord(
        sample_id=sample_id, task=task, exam_id="EX01", split=split,
        messages=[
            {"role": "system", "content": "Grade rubric"},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": TARGET},
        ],
        text="unused manual ChatML", target=TARGET,
    )


class FakeTokenizer:
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize
        text = "".join(f"<{m['role']}>{m['content']}</{m['role']}>" for m in messages)
        if add_generation_prompt:
            text += "<assistant>"
        return list(text.encode("utf-8"))


def write_fixture(tmp_path, train, val):
    processed = tmp_path / "processed"
    splits = tmp_path / "splits"
    processed.mkdir(exist_ok=True)
    splits.mkdir(exist_ok=True)
    for part, rows in (("train", train), ("val", val)):
        (processed / f"task1_{part}.jsonl").write_text(
            "\n".join(r.model_dump_json() for r in rows) + "\n", encoding="utf-8"
        )
        (splits / f"{part}_ids.json").write_text(
            json.dumps([r.sample_id for r in rows]), encoding="utf-8"
        )
    return processed, splits


def test_fixed_sample_split_if_prepared_locally():
    processed = ROOT / "data/processed"
    if not (processed / "task1_train.jsonl").exists():
        pytest.skip("Local sample dataset has not been prepared")
    train, val = load_task1_splits(processed, ROOT / "data/splits")
    assert (len(train), len(val)) == (26, 6)
    assert {r.task for r in train + val} == {"task1"}
    assert not ({r.sample_id for r in train} & {r.sample_id for r in val})


def test_reject_mixed_task_or_feedback(tmp_path):
    processed, splits = write_fixture(tmp_path, [record()], [record("S2", "val")])
    load_task1_splits(processed, splits, expected_train=1, expected_val=1)
    write_fixture(tmp_path, [record(task="task2")], [record("S2", "val")])
    with pytest.raises(ValueError, match="Unexpected task"):
        load_task1_splits(processed, splits, expected_train=1, expected_val=1)
    write_fixture(tmp_path, [record(prompt="## Feedback\nteacher answer")], [record("S2", "val")])
    with pytest.raises(AssertionError, match="Leakage"):
        load_task1_splits(processed, splits, expected_train=1, expected_val=1)


def test_compiler_log_matching_teacher_feedback_is_not_leakage(tmp_path):
    diagnostic = "student.cpp:4:3: error: expected expression\n    4 | x = ;"
    processed, splits = write_fixture(
        tmp_path, [record(prompt="Compile log\n" + diagnostic)], [record("S2", "val")]
    )
    (processed / "unified_samples.jsonl").write_text(
        json.dumps({"sample_id": "S1", "feedback": diagnostic, "compile_log": diagnostic}) + "\n",
        encoding="utf-8",
    )
    load_task1_splits(processed, splits, expected_train=1, expected_val=1)
    write_fixture(tmp_path, [record(prompt="Compile log\n" + diagnostic + "\n" + diagnostic)],
                  [record("S2", "val")])
    with pytest.raises(ValueError, match="Teacher feedback leaked"):
        load_task1_splits(processed, splits, expected_train=1, expected_val=1)


def test_completion_only_mask_and_no_silent_truncation():
    tok = FakeTokenizer()
    rec = record()
    encoded = encode_training_record(rec, tok, 1000)
    n_prompt = encoded["prompt_tokens"]
    assert all(v == -100 for v in encoded["labels"][:n_prompt])
    assert encoded["labels"][n_prompt:] == encoded["input_ids"][n_prompt:]
    assert len(encode_inference_prompt(rec, tok, 1000)) == n_prompt
    with pytest.raises(ValueError, match="exceeding max_length"):
        encode_training_record(rec, tok, n_prompt)


def test_generated_json_decimal_sum_and_metrics():
    rec = record("S2", "val")
    pred, json_ok, strict_ok = parse_generated_score(TARGET)
    assert (json_ok, strict_ok) == (True, True)
    assert pred["total_score"] == 7.75
    wrong_total = json.dumps({"rubric": RUBRIC, "total_score": 7.5})
    corrected, json_ok, strict_ok = parse_generated_score(wrong_total)
    assert json_ok and not strict_ok and corrected["total_score"] == 7.75
    assert parse_generated_score("not json") == (None, False, False)
    fenced, json_ok, strict_ok = parse_generated_score("```json\n" + TARGET + "\n```")  # instruct-model habit
    assert (json_ok, strict_ok) == (True, True) and fenced == pred
    assert parse_generated_score("```\n" + TARGET + "\n```")[0] == pred
    assert parse_generated_score("Here:\n```json\n" + TARGET + "\n```") == (None, False, False)  # extra prose
    invalid_step = json.dumps({"rubric": {**RUBRIC, "logic": 2.255}, "total_score": 7.755})
    assert parse_generated_score(invalid_step) == (None, True, False)
    metrics, details = evaluate_generations([rec], {"S2": TARGET})
    assert metrics["mae"] == 0 and metrics["valid_output_rate"] == 1
    assert details[0]["prediction"] == pred


def test_best_epoch_uses_qwk_then_mae():
    results = [
        {"epoch": 1, "metrics": {"qwk": 0.7, "mae": 1.0}},
        {"epoch": 2, "metrics": {"qwk": 0.8, "mae": 1.5}},
        {"epoch": 3, "metrics": {"qwk": 0.8, "mae": 1.2}},
    ]
    assert best_epoch(results)["epoch"] == 3
