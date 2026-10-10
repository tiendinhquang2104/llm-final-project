"""Offline contract tests for the public submission and resumable prediction."""

from __future__ import annotations

import json
from pathlib import Path

from src.data.loader import DIMENSIONS, Dataset, Sample
from src.llm.api_client import QuotaExhausted
from src.task1.evaluator import validate_predictions
from src.task1.pipeline import Task1Pipeline
from src.task1.public_predict import PUBLIC_EXAMS, inspect_public, predict_public
from src.utils.config import load_config


def row(sample_id="Class03-Final-1-S01", **scores):
    rubric = {d: 0 for d in DIMENSIONS}
    rubric.update(scores)
    return {"sample_id": sample_id, "output": {"rubric": rubric, "total_score": sum(rubric.values())}}


def test_submission_hundredths_and_invalid_values():
    valid = row(logic=3.75, io_format=0.01)
    assert not validate_predictions([valid], [valid["sample_id"]])
    for bad in (0.001, 4.01, float("nan"), True):
        broken = row(logic=bad)
        assert validate_predictions([broken], [broken["sample_id"]])
    broken = row()
    del broken["output"]["rubric"]["logic"]
    assert validate_predictions([broken])
    broken = row(logic=3.75)
    broken["output"]["total_score"] = 3.74
    assert validate_predictions([broken])
    assert validate_predictions([row(), row()])
    assert validate_predictions([row()], ["different-id"])


def test_structured_pipeline_preserves_hundredths(tmp_path):
    ds = synthetic_public(tmp_path / "data")
    cfg = load_config(Path(__file__).parents[1] / "configs" / "task1" / "e2_zero_shot_structured.yaml")

    class FractionalBackend(FakeBackend):
        def generate(self, requests, gen):
            self.calls += 1
            return [[json.dumps({"problems": [{"pid": "P1", "status": "correct"}],
                                 "rubric": {**{d: 0 for d in DIMENSIONS}, "compilable": 1, "logic": 3.75,
                                            "io_format": 0.01}})]]

    sample = next(s for s in ds.samples if s.exam_type == "single_problem")
    _, preds = Task1Pipeline(ds, FractionalBackend(), cfg).run([sample])
    assert preds[0]["parse_ok"]
    assert preds[0]["rubric"]["logic"] == 3.75
    assert preds[0]["total_score"] == 4.76


def synthetic_public(root: Path) -> Dataset:
    data_files = root / "data_files"
    data_files.mkdir(parents=True)
    (data_files / "50-best-european-generals-cleaned-first-20.csv").write_text(
        "Name,Nationality\n", encoding="utf-8")
    (data_files / "50-european-battles-first-20.csv").write_text(
        "BattleName,Location\n", encoding="utf-8")
    exams = {}
    samples = []
    for exam_id in sorted(PUBLIC_EXAMS):
        exam_type = "single_problem" if exam_id.startswith("Class03") else "multi_problem"
        exams[exam_id] = {"exam_id": exam_id, "exam_type": exam_type, "statement": "Test",
                          "problems": [{"pid": "P1", "max_score": 10}] if exam_type == "single_problem"
                          else [{"pid": "P1", "max_score": 1,
                                 "is_prerequisite_for": ["P2", "P3", "P4"]},
                                {"pid": "P2", "max_score": 4}, {"pid": "P3", "max_score": 2},
                                {"pid": "P4", "max_score": 3}]}
        for n in range(60):
            sid = f"{exam_id}-S{n:02d}"
            samples.append(Sample(sid, exam_id, exam_type, "cpp11", f"{sid}.cpp",
                                  "int main() {}", "", None))
    return Dataset(root, exams, {}, samples)


class FakeBackend:
    name = "gemini"

    def __init__(self, cap=999):
        self.model = "fake-model"
        self.cap = cap
        self.calls = 0
        self.ledger = []

    def info(self):
        return {"backend": self.name, "model": self.model,
                "usage": {"requests": self.calls, "prompt_tokens": self.calls * 10}, "price": None}

    def generate(self, requests, gen):
        if self.calls >= self.cap:
            raise QuotaExhausted("offline cap")
        self.calls += 1
        self.ledger.append({"sample_id": requests[0]["sample"].sample_id, "input_tokens": 10})
        return [[json.dumps({"problems": [{"pid": "P1", "status": "correct"}],
                             "rubric": {d: 0 for d in DIMENSIONS}})]]


def test_public_resume_and_exact_submission(tmp_path):
    ds = synthetic_public(tmp_path / "data")
    summary = inspect_public(ds)
    assert summary["samples"] == 360 and len(summary["exams"]) == 6
    cfg = load_config(Path(__file__).parents[1] / "configs" / "task1" / "e2_zero_shot_structured.yaml")
    cfg["retry_on_parse_fail"] = 0
    pipe = Task1Pipeline(ds, None, cfg)
    assert "Name,Nationality" in pipe.build_request(ds.samples[0])["messages"][1]["content"] or any(
        "Name,Nationality" in pipe.build_request(s)["messages"][1]["content"] for s in ds.samples if s.exam_id == "Class01-Test1")
    first = FakeBackend(cap=5)
    partial = predict_public(ds, cfg, first, tmp_path / "out")
    assert partial["completed"] == 5 and partial["submission_path"] is None
    second = FakeBackend()
    complete = predict_public(ds, cfg, second, tmp_path / "out")
    assert complete["completed"] == 360 and second.calls == 355
    assert complete["usage_total"]["api_calls"] == 360
    submission = json.loads(Path(complete["submission_path"]).read_text(encoding="utf-8"))
    assert not validate_predictions(submission, [s.sample_id for s in ds.samples])
    third = FakeBackend()
    predict_public(ds, cfg, third, tmp_path / "out")
    assert third.calls == 0


def test_invalid_public_grade_is_not_checkpointed(tmp_path):
    ds = synthetic_public(tmp_path / "data")
    cfg = load_config(Path(__file__).parents[1] / "configs" / "task1" / "e2_zero_shot_structured.yaml")
    cfg["retry_on_parse_fail"] = 0

    class InvalidBackend(FakeBackend):
        def generate(self, requests, gen):
            self.calls += 1
            return [["not JSON"]]

    sid = ds.samples[0].sample_id
    bad = predict_public(ds, cfg, InvalidBackend(), tmp_path / "out", selected_ids=[sid])
    assert bad["completed"] == 0 and bad["submission_path"] is None
    good_backend = FakeBackend()
    good = predict_public(ds, cfg, good_backend, tmp_path / "out", selected_ids=[sid])
    assert good["completed"] == 1 and good_backend.calls == 1
