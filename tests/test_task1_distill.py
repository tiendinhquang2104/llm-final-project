"""Offline checks for relabelling the silver set with the API grader (QLoRA v3), with a fake backend."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.data.loader import DIMENSIONS
from tests.test_task1_public import FakeBackend

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("distill", ROOT / "scripts/distill_task1_silver.py")
distill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distill)


def silver(root: Path, exam_prefix: str = "SYN") -> Path:
    exams = []
    rows = []
    for e in range(2):
        exam_id = f"{exam_prefix}-E{e}"
        exams.append({"exam_id": exam_id, "exam_type": "single_problem", "statement": "Viết hàm.",
                      "problems": [{"pid": "P1", "max_score": 10}]})
        (root / "submissions" / exam_id).mkdir(parents=True)
        for n in range(3):
            sid = f"{exam_id}-{n:04d}"
            (root / "submissions" / exam_id / f"{sid}.cpp").write_text(f"int main(){{return {n};}}", encoding="utf-8")
            rubric = {d: 1 for d in DIMENSIONS}
            rows.append({"sample_id": sid, "input": {"exam_id": exam_id, "exam_type": "single_problem",
                                                     "language": "cpp11", "code_file": f"submissions/{exam_id}/{sid}.cpp",
                                                     "compile_log": "", "test_report": None, "exec_report": "compile: OK"},
                         "output": {"rubric": rubric, "total_score": 6}})
    (root / "heldout").mkdir()
    (root / "heldout" / "task1_grading.json").write_text('{"samples": []}', encoding="utf-8")
    (root / "exams.json").write_text(json.dumps({"exams": exams}), encoding="utf-8")
    (root / "label_space.json").write_text("{}", encoding="utf-8")
    (root / "task1_grading.json").write_text(json.dumps({"samples": rows}), encoding="utf-8")
    return root


fake_api_cap: list[int] = []


@pytest.fixture
def fake_api(monkeypatch):
    backends = []

    def make(**_):  # a new backend per run, like a new process; the first run stops on quota after `cap` calls
        backends.append(FakeBackend(cap=fake_api_cap.pop(0) if fake_api_cap else 999))
        return backends[-1]

    monkeypatch.setattr(distill, "GeminiBackend", make)
    monkeypatch.setattr(distill, "load_dotenv", lambda: None)
    return backends


def test_distill_resumes_and_writes_api_labels(tmp_path, fake_api):
    src, out, api = silver(tmp_path / "silver"), tmp_path / "v1_api", tmp_path / "api"
    args = ["--silver-root", str(src), "--output-dir", str(out), "--api-dir", str(api), "--provider", "gemini"]
    fake_api_cap[:] = [4]
    distill.main(args)  # quota stop after 4 samples: nothing written for training
    assert not out.exists()
    distill.main(args)  # resume: only the last 2 samples call the API
    assert sum(b.calls for b in fake_api) == 6
    rows = json.loads((out / "task1_grading.json").read_text(encoding="utf-8"))["samples"]
    assert len(rows) == 6 and all(r["output"]["total_score"] == 0 for r in rows)  # the fake grader gives 0
    assert rows[0]["input"]["exec_report"] == "compile: OK"
    manifest = json.loads((out / distill.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["labels"] == "api_teacher" and manifest["cost"]["api_calls"] == 6
    assert manifest["agreement_with_generator_labels"]["exact_total"] == 0
    assert (out / "heldout" / "task1_grading.json").exists() and (out / "submissions").is_dir()


def test_silver_manifest_records_label_source(tmp_path, fake_api):
    from src.task1.silver_data import prepare_silver_task1

    src = silver(tmp_path / "silver")
    out = tmp_path / "v1_api"
    distill.main(["--silver-root", str(src), "--output-dir", str(out), "--api-dir", str(tmp_path / "api")])
    other = silver(tmp_path / "gold", exam_prefix="EX")
    for f in (other / "submissions").rglob("*.cpp"):
        f.write_text(f.read_text(encoding="utf-8") + "// gold", encoding="utf-8")
    manifest = prepare_silver_task1(out, other, other, tmp_path / "processed")
    assert manifest["labels"]["source"] == "api_teacher"
    assert prepare_silver_task1(src, other, other, tmp_path / "processed2")["labels"] == {"source": "generator"}


def test_refuses_non_synthetic_exams(tmp_path, fake_api):
    src = silver(tmp_path / "silver", exam_prefix="Class03")
    with pytest.raises(SystemExit, match="only synthetic"):
        distill.main(["--silver-root", str(src), "--output-dir", str(tmp_path / "o"), "--preflight"])
    assert not fake_api


def test_spread_ids_covers_exams():
    from types import SimpleNamespace

    samples = [SimpleNamespace(sample_id=f"{e}-{n}", exam_id=e) for e in ("A", "B", "C") for n in range(5)]
    assert {s.split("-")[0] for s in distill.spread_ids(samples, 3)} == {"A", "B", "C"}
    assert len(distill.spread_ids(samples, None)) == 15
