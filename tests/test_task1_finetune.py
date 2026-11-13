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
    split_silver_validation,
)

ROOT = Path(__file__).resolve().parents[1]
RUBRIC = {
    "compilable": 1, "io_format": 1, "logic": 2,
    "edge_case": 1, "complexity": 1, "code_quality": 1,
}
TARGET = json.dumps({"rubric": RUBRIC, "total_score": 7})


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
    assert pred["total_score"] == 7
    wrong_total = json.dumps({"rubric": RUBRIC, "total_score": 6})
    corrected, json_ok, strict_ok = parse_generated_score(wrong_total)
    assert json_ok and not strict_ok and corrected["total_score"] == 7
    # A fractional answer is rounded half up (gold labels and the submission validator are integer-only) and counted
    # as non-strict, instead of failing the whole submission.
    fractional = json.dumps({"rubric": {**RUBRIC, "logic": 2.5, "edge_case": 1.49}, "total_score": 7.99})
    rounded, json_ok, strict_ok = parse_generated_score(fractional)
    assert json_ok and not strict_ok
    assert rounded["rubric"]["logic"] == 3 and rounded["rubric"]["edge_case"] == 1 and rounded["total_score"] == 8
    assert parse_generated_score("not json") == (None, False, False)
    fenced, json_ok, strict_ok = parse_generated_score("```json\n" + TARGET + "\n```")  # instruct-model habit
    assert (json_ok, strict_ok) == (True, True) and fenced == pred
    assert parse_generated_score("```\n" + TARGET + "\n```")[0] == pred
    assert parse_generated_score("Here:\n```json\n" + TARGET + "\n```") == (None, False, False)  # extra prose
    invalid_step = json.dumps({"rubric": {**RUBRIC, "logic": 2.255}, "total_score": 7.255})
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


def test_best_epoch_prefers_selection_metrics_over_gold_only():
    results = [
        {"epoch": 1, "metrics": {"qwk": 0.9, "mae": 1.0}, "selection_metrics": {"qwk": 0.5, "mae": 2.0}},
        {"epoch": 2, "metrics": {"qwk": 0.4, "mae": 3.0}, "selection_metrics": {"qwk": 0.7, "mae": 1.5}},
    ]
    assert best_epoch(results)["epoch"] == 2


def _silver(sample_id, exam_id):
    rec = record(sample_id=sample_id, split="silver")
    return rec.model_copy(update={"exam_id": exam_id})


def test_split_silver_validation_is_per_exam_deterministic_and_disjoint():
    recs = [_silver(f"SYN-A-{i:04d}", "SYN-A") for i in range(20)]
    recs += [_silver(f"SYN-B-{i:04d}", "SYN-B") for i in range(3)]
    recs += [_silver("SYN-C-0000", "SYN-C")]
    train, val = split_silver_validation(recs, 0.1, seed=42)
    again_train, again_val = split_silver_validation(recs, 0.1, seed=42)
    assert [r.sample_id for r in val] == [r.sample_id for r in again_val]
    assert {r.sample_id for r in train}.isdisjoint(r.sample_id for r in val)
    assert len(train) + len(val) == len(recs)
    held = {}
    for r in val:
        held[r.exam_id] = held.get(r.exam_id, 0) + 1
    assert held == {"SYN-A": 2, "SYN-B": 1}  # single-sample exam stays in training
    assert split_silver_validation(recs, 0.0, seed=42) == (recs, [])
