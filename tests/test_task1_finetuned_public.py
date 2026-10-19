"""Offline tests of best-epoch selection, train-compatible prompts and resume."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.data.loader import DIMENSIONS, Dataset, Sample
from src.data.prompts import build_task1_messages
from src.task1.evaluator import validate_predictions
from src.task1.finetune_public import (
    predict_finetuned_public,
    prepare_public,
    public_messages,
    select_adapter,
)
from src.task1.public_predict import PUBLIC_EXAMS


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def training_run(root):
    chosen = {"variant": "silver_then_gold", "epoch": 2,
              "metrics": {"qwk": 0.8, "mae": 1},
              "checkpoint": "/old/runtime/silver_then_gold/gold/checkpoint-14"}
    baseline = {"variant": "gold_only", "epoch": 1, "metrics": {"qwk": 0.5, "mae": 2}}
    write_json(root / "training_summary.json", {
        "model": "test-model", "selected_variant": chosen["variant"], "selected_epoch": 2,
        "gold_only_best": baseline, "silver_then_gold_best": chosen,
    })
    write_json(root / "training_config.json", {"model": "test-model"})
    write_json(root / "best_adapter/adapter_config.json", {"base_model_name_or_path": "test-model"})
    (root / "best_adapter/adapter_model.safetensors").write_bytes(b"best epoch two")
    checkpoint = root / "silver_then_gold/gold/checkpoint-14"
    checkpoint.mkdir(parents=True)
    (checkpoint / "adapter_model.safetensors").write_bytes(b"best epoch two")
    return root


def public_dataset(root):
    exams, samples = {}, []
    for exam_id in sorted(PUBLIC_EXAMS):
        exam_type = "single_problem" if exam_id.startswith("Class03") else "multi_problem"
        exams[exam_id] = {"statement": "A C++ problem", "exam_type": exam_type,
                          "grading_policy": "P1 prerequisite"}
        for index in range(60):
            samples.append(Sample(f"{exam_id}-S{index:02}", exam_id, exam_type,
                                  "cpp11", "code.cpp", "int main() {}", None, None))
    return Dataset(root, exams, {}, samples)


TARGET = json.dumps({"rubric": {d: 0 for d in DIMENSIONS}, "total_score": 0})


def test_selects_best_epoch_and_verifies_copied_weights(tmp_path):
    root = training_run(tmp_path / "run")
    selected = select_adapter(root)
    assert (selected["selected_variant"], selected["selected_epoch"]) == ("silver_then_gold", 2)
    assert selected["checkpoint_verified"]
    (root / "best_adapter/adapter_model.safetensors").write_bytes(b"wrong last epoch")
    with pytest.raises(ValueError, match="differ from the selected epoch"):
        select_adapter(root)


def test_selection_rejects_base_mismatch_and_wrong_epoch(tmp_path):
    root = training_run(tmp_path / "run")
    write_json(root / "best_adapter/adapter_config.json", {"base_model_name_or_path": "wrong-base"})
    with pytest.raises(ValueError, match="disagree on the base model"):
        select_adapter(root)
    write_json(root / "best_adapter/adapter_config.json", {"base_model_name_or_path": "test-model"})
    summary = json.loads((root / "training_summary.json").read_text())
    summary["selected_epoch"] = 3
    write_json(root / "training_summary.json", summary)
    with pytest.raises(ValueError, match="gold-validation winner"):
        select_adapter(root)
    summary["selected_epoch"] = 2
    summary["data"] = {"smoke": True}
    write_json(root / "training_summary.json", summary)
    with pytest.raises(ValueError, match="not a smoke run"):
        select_adapter(root)


def test_prompt_matches_training_and_does_not_include_assistant(tmp_path):
    ds = public_dataset(tmp_path)
    sample = ds.samples[0]
    context = SimpleNamespace(**vars(sample), exam_statement="A C++ problem",
                              grading_policy="P1 prerequisite", rubric={d: 0 for d in DIMENSIONS},
                              total_score=0)
    training_messages, _ = build_task1_messages(context)
    assert public_messages(ds, sample) == training_messages[:2]
    assert [m["role"] for m in public_messages(ds, sample)] == ["system", "user"]


def test_preflight_checks_all_prompts_without_truncation(tmp_path):
    ds = public_dataset(tmp_path)

    class Tokenizer:
        def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
            assert tokenize and add_generation_prompt
            assert [m["role"] for m in messages] == ["system", "user"]
            return [1] * 20

    inputs, report = prepare_public(ds, Tokenizer(), 30, 10)
    assert len(inputs) == report["samples"] == 360
    with pytest.raises(ValueError, match="360 public prompts exceed"):
        prepare_public(ds, Tokenizer(), 29, 10)


def test_resume_invalid_output_and_exact_submission(tmp_path):
    ds = public_dataset(tmp_path / "data")
    selection = select_adapter(training_run(tmp_path / "training"))
    inputs = {s.sample_id: [1, 2, 3] for s in ds.samples}
    selected = sorted(inputs)[:3]
    calls = []

    def valid(ids):
        calls.append(ids)
        return TARGET, 50

    partial = predict_finetuned_public(ds, inputs, selection, valid, tmp_path / "out", {}, selected)
    assert partial["completed"] == 3 and partial["submission_path"] is None
    assert len(calls) == 3
    predict_finetuned_public(ds, inputs, selection, valid, tmp_path / "out", {}, selected)
    assert len(calls) == 3  # Same adapter/config/inputs: no regeneration.
    # Invalid JSON must remain missing, with raw output available for inspection.
    invalid = predict_finetuned_public(ds, inputs, selection, lambda ids: ("not json", 2),
                                       tmp_path / "out", {}, [sorted(inputs)[3]])
    assert invalid["completed"] == 3 and invalid["errors"]
    complete = predict_finetuned_public(ds, inputs, selection, valid, tmp_path / "out", {})
    assert len(calls) == 360
    rows = json.loads(Path(complete["submission_path"]).read_text())
    assert not validate_predictions(rows, sorted(inputs))
    assert complete["completed"] == 360
    # A new generation configuration must not reuse the completed submission.
    changed = predict_finetuned_public(ds, inputs, selection, valid, tmp_path / "out",
                                       {"max_new_tokens": 512}, selected[:1])
    assert changed["completed"] == 1 and changed["submission_path"] is None
    assert changed["run_dir"] != complete["run_dir"]


def test_gpu_error_preserves_completed_checkpoints_and_progress(tmp_path):
    ds = public_dataset(tmp_path / "data")
    selection = select_adapter(training_run(tmp_path / "training"))
    inputs = {s.sample_id: [1] for s in ds.samples}
    calls = 0

    def failing(ids):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("GPU out of memory")
        return TARGET, 50

    out = tmp_path / "out"
    with pytest.raises(RuntimeError, match="GPU out of memory"):
        predict_finetuned_public(ds, inputs, selection, failing, out, {}, sorted(inputs)[:3])
    path = next(out.glob("public/**/progress.json"))
    progress = json.loads(path.read_text())
    assert progress["completed"] == 1 and "GPU out of memory" in progress["stopped"]
    assert not (path.parent / "predictions.json").exists()
