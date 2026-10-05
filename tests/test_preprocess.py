"""Unit tests for ChatML preprocess + leakage guard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.leakage_guard import DataLeakageError, assert_no_feedback_leakage
from src.data.loader import load_dataset, resolve_dataset_root
from src.data.preprocess import build_unified_jsonl, make_split
from src.data.prompts import build_chatml_record
from src.data.schema import RubricScores

SAMPLE_CANDIDATES = [
    Path(__file__).resolve().parents[1].parent / "sample_dataset" / "sample_dataset",
    Path(__file__).resolve().parents[1].parent / "sample_dataset",
]


def _sample_root() -> Path:
    for c in SAMPLE_CANDIDATES:
        try:
            return resolve_dataset_root(c)
        except FileNotFoundError:
            continue
    pytest.skip("sample_dataset not found next to the project")


@pytest.fixture(scope="module")
def samples():
    return load_dataset(_sample_root())


def test_load_joins_32_samples(samples):
    assert len(samples) == 32
    assert {s.exam_id for s in samples} == {"EX01", "EX02"}
    assert all(s.code.strip() for s in samples)
    assert all(s.feedback.strip() for s in samples)


def test_split_deterministic():
    ids = [f"S{i:03d}" for i in range(32)]
    a = make_split(ids, val_ratio=0.2, seed=42)
    b = make_split(ids, val_ratio=0.2, seed=42)
    assert a == b
    train, val = a
    assert set(train).isdisjoint(val)
    assert len(train) + len(val) == 32


def test_task1_task2_never_contain_feedback(samples):
    sample = samples[0]
    for task in ("task1", "task2"):
        rec = build_chatml_record(sample, task)
        user = next(m["content"] for m in rec.messages if m["role"] == "user")
        assert sample.feedback not in user
        assert "target_feedback_level" not in user
        assert_no_feedback_leakage([rec], {sample.sample_id: sample})


def test_leakage_guard_catches_injected_feedback(samples):
    sample = samples[0]
    rec = build_chatml_record(sample, "task1")
    # Inject gold feedback into user prompt
    for m in rec.messages:
        if m["role"] == "user":
            m["content"] += "\n## Feedback\n" + sample.feedback
            break
    with pytest.raises(DataLeakageError):
        assert_no_feedback_leakage([rec], {sample.sample_id: sample})


def test_build_unified_jsonl(tmp_path, samples):
    root = _sample_root()
    out = tmp_path / "processed"
    paths = build_unified_jsonl(root, out, val_ratio=0.2, seed=42)
    assert paths["train_unified"].exists()
    assert paths["val_unified"].exists()
    train_lines = paths["train_unified"].read_text(encoding="utf-8").strip().splitlines()
    val_lines = paths["val_unified"].read_text(encoding="utf-8").strip().splitlines()
    # 32 samples * 3 tasks
    assert len(train_lines) + len(val_lines) == 32 * 3
    # each record has chatml text
    row = json.loads(train_lines[0])
    assert "<|im_start|>" in row["text"]
    assert row["task"] in {"task1", "task2", "task3"}
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest["leakage_checked"] is True


def test_task_targets_shapes(samples):
    s = next(x for x in samples if x.taxonomy_error == [])
    r2 = build_chatml_record(s, "task2")
    assert r2.target == '{"taxonomy_error":[]}'
    r1 = build_chatml_record(s, "task1")
    obj = json.loads(r1.target)
    RubricScores(**obj["rubric"])
    assert "total_score" in obj
