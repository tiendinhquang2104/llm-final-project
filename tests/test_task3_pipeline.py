import csv
import json

import pytest

from src.synth.feedback import FEEDBACK_LEVELS
from src.task3.dataset import write_json
from src.task3.evaluator import aggregate_annotations, evaluate, write_benchmark, write_review_csv
from src.task3.inference import Generation, MockBackend
from src.task3.pipeline import export_predictions, infer, load_taxonomy_predictions, taxonomy_for, validate_predictions
from tests.test_task3_dataset import record


def test_public_missing_vs_predicted_empty():
    r = record(source="public")
    with pytest.raises(ValueError, match="public gold"):
        taxonomy_for(r, "gold")
    with pytest.raises(ValueError, match="missing"):
        taxonomy_for(r, "task2-json", {})
    assert taxonomy_for(r, "task2-json", {r.sample_id: []}) == []


@pytest.mark.parametrize("form", ["map", "official", "internal", "internal-map"])
def test_task2_json_formats(tmp_path, form):
    data = {
        "map": {"TEST": []},
        "official": [{"sample_id": "TEST", "output": {"taxonomy_error": []}}],
        "internal": [{"sample_id": "TEST", "labels": [], "parse_ok": True}],
        "internal-map": {"TEST": {"labels": [], "parse_ok": True}},
    }[form]
    path = tmp_path / "taxonomy.json"
    write_json(path, data)
    assert load_taxonomy_predictions(path, ["TEST"]) == {"TEST": []}


def test_task2_extra_ids_are_audited_projection_not_a_task3_failure(tmp_path):
    path = tmp_path / "taxonomy.json"
    write_json(path, {"TEST": [], "EXTRA": ["Lỗi logic"]})
    predictions, audit = load_taxonomy_predictions(path, ["TEST"], return_audit=True)
    assert predictions == {"TEST": []}
    assert audit["ignored_extra_id_count"] == 1
    assert audit["ignored_extra_ids_sha256"]
    write_json(path, {"EXTRA": []})
    with pytest.raises(ValueError, match="missing 1 required"):
        load_taxonomy_predictions(path, ["TEST"])


def test_task2_write_submission_fixture_integrates_with_task3_projection(tmp_path):
    from src.task2.evaluator import write_submission

    path = tmp_path / "task2-predictions.json"
    write_submission(path, {"TEST": ["Lỗi logic"], "EXTRA": []}, ["TEST", "EXTRA"])
    projected, audit = load_taxonomy_predictions(path, ["TEST"], return_audit=True)
    assert projected == {"TEST": ["Lỗi logic"]}
    assert audit["ignored_extra_id_count"] == 1


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"TEST": None},
        {"TEST": ["unknown"]},
        [
            {"sample_id": "TEST", "output": {"taxonomy_error": []}},
            {"sample_id": "TEST", "output": {"taxonomy_error": []}},
        ],
        [{"sample_id": "TEST", "labels": [], "parse_ok": False}],
        {"TEST": {"labels": [], "parse_ok": False}},
    ],
)
def test_missing_invalid_failed_predictions_rejected(tmp_path, data):
    path = tmp_path / "taxonomy.json"
    write_json(path, data)
    with pytest.raises(ValueError):
        load_taxonomy_predictions(path, ["TEST"])


def test_mock_public_export_order_and_no_completion(tmp_path):
    records = [record("B", source="public"), record("A", source="public")]
    preds, traces = infer(records, MockBackend(), {"context_limit": 10000}, "task2-json", {"B": [], "A": ["Lỗi logic"]})
    export_predictions(tmp_path / "TEST.mock.json", preds, records, mock=True)
    assert [p["sample_id"] for p in preds] == ["B", "A"]
    assert set(preds[0]["output"]) == {"taxonomy_error", "feedback"}
    with pytest.raises(ValueError, match="order"):
        validate_predictions(list(reversed(preds)), ["B", "A"])
    with pytest.raises(ValueError, match="mock"):
        export_predictions(tmp_path / "predictions.json", preds, records, mock=True)


def test_regeneration_is_bounded_and_fallback_reported():
    class BadBackend(MockBackend):
        calls = 0

        def generate(self, messages, config):
            self.calls += 1
            return Generation("```cpp\nreturn 0;\n```", 10, 0.1)

    backend = BadBackend()
    preds, traces = infer([record()], backend, {"context_limit": 10000, "max_retries": 2})
    assert backend.calls == 3
    assert traces[0]["fallback"]
    assert len(traces[0]["attempts"]) == 3
    metrics = evaluate([record()], preds, traces)
    assert metrics["compliance"] == 1
    assert metrics["raw_first_attempt_compliance"] == 0
    assert metrics["raw_first_attempt_severe_leak_rate_level12"] == 1
    assert metrics["fallback_rate"] == 1
    assert metrics["diagnosis_quality"] == "not_measured"
    assert traces[0]["raw_first_attempt_compliance"] is False
    assert traces[0]["fallback_used"] is True
    assert traces[0]["diagnosis_quality_status"] == "unknown_or_inadequate_fallback"


def test_inference_progress_resumes_only_matching_valid_rows(tmp_path):
    class InterruptedBackend(MockBackend):
        def __init__(self, fail_at=None):
            self.calls = 0
            self.fail_at = fail_at

        def generate(self, messages, config):
            self.calls += 1
            if self.calls == self.fail_at:
                raise OSError("TEST interruption")
            return super().generate(messages, config)

    records = [record("TEST-1"), record("TEST-2", code="int main(){return 24;}")]
    progress = tmp_path / "inference.progress.jsonl"
    with pytest.raises(OSError, match="TEST interruption"):
        infer(
            records,
            InterruptedBackend(fail_at=2),
            {"context_limit": 10000},
            progress_path=progress,
            cache_context="manifest-v1",
        )
    assert len(progress.read_text().splitlines()) == 1
    resumed = InterruptedBackend()
    predictions, traces = infer(
        records,
        resumed,
        {"context_limit": 10000},
        progress_path=progress,
        resume=True,
        cache_context="manifest-v1",
    )
    assert resumed.calls == 1
    assert [item["sample_id"] for item in predictions] == ["TEST-1", "TEST-2"]
    assert len(traces) == 2
    changed = InterruptedBackend()
    infer(
        records,
        changed,
        {"context_limit": 10000, "max_new_tokens": 123},
        progress_path=progress,
        resume=True,
        cache_context="manifest-v1",
    )
    assert changed.calls == 2
    assert len(progress.read_text().splitlines()) == 2


def test_level_swap_backend_contract_changes_disclosure_preserves_core_diagnosis():
    """Scripted fixture checks plumbing; this is NOT evidence of Qwen semantic consistency."""

    class ScriptedBackend(MockBackend):
        responses = [
            "Em kiểm tra lại kết quả nhé.",
            "Phép tính tổng đang sai.",
            "Phép tính tổng đang sai; em cần đối chiếu phép cộng với yêu cầu đề.",
            "Phép tính tổng đang sai. Với đề TEST-ONLY này, sửa phép tính: `sum = a + b;`.",
        ]

        def generate(self, messages, config):
            payload = json.loads(messages[-1]["content"].split("\n")[1])
            assert payload["taxonomy_error"] == ["Lỗi logic"]
            level = int(payload["target_feedback_level"][6])
            text = self.responses[level - 1]
            return Generation(text, len(text), 0)

    rows = [record(str(i), target_feedback_level=level) for i, level in enumerate(FEEDBACK_LEVELS)]
    assert len({(row.statement, row.code, tuple(row.gold_taxonomy)) for row in rows}) == 1
    preds, traces = infer(rows, ScriptedBackend(), {"context_limit": 10000})
    assert all(not t["fallback"] for t in traces)
    assert all(t["final_guard"]["ok"] for t in traces)
    assert traces[0]["diagnosis_quality_status"] == "not_measured"
    assert all("Phép tính tổng đang sai" in p["output"]["feedback"] for p in preds[1:])
    assert len(set(p["output"]["feedback"] for p in preds)) == 4


def test_human_review_worklist_does_not_copy_private_text(tmp_path):
    r = record(source="real", split="real-val", gold_feedback="PRIVATE_TARGET", code="PRIVATE_CODE")
    path = tmp_path / "review.csv"
    write_review_csv(path, [r])
    text = path.read_text()
    assert "PRIVATE_TARGET" not in text and "PRIVATE_CODE" not in text
    assert r.sample_id in text


def test_human_annotation_aggregation_and_explicit_missingness(tmp_path):
    r = record(source="real", split="real-val", exam_type="single_problem")
    path = tmp_path / "review.csv"
    write_review_csv(path, [r])
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = reader.fieldnames
    row = rows[0]
    for reviewer, name in ((1, "reviewer-a"), (2, "reviewer-b")):
        row[f"reviewer{reviewer}_id"] = name
        row[f"reviewer{reviewer}_diagnosis_correctness"] = "2"
        row[f"reviewer{reviewer}_code_evidence_support"] = "1"
        row[f"reviewer{reviewer}_hallucinated_error"] = "no"
        row[f"reviewer{reviewer}_prerequisite_reasoning"] = "na"
        row[f"reviewer{reviewer}_level_violation"] = "no"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
    summary = aggregate_annotations(path, [r])
    assert summary["status"] == "measured"
    assert summary["per_exam_type"]["single_problem"]["scores"]["diagnosis_correctness"]["mean"] == 2
    assert summary["pairwise_agreement"]["diagnosis_correctness"]["exact_agreement"] == 1
    assert summary["coverage"] == 1
    row["reviewer1_diagnosis_correctness"] = ""
    row["reviewer2_diagnosis_correctness"] = ""
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
    missing = aggregate_annotations(path, [r])
    assert missing["status"] == "not_measured"
    assert missing["per_level"][r.target_feedback_level]["scores"]["diagnosis_correctness"] == {
        "n": 0,
        "mean": None,
    }


def test_human_annotations_reject_invalid_scores_duplicate_ids_and_wrong_split(tmp_path):
    r = record(source="real", split="real-val")
    path = tmp_path / "review.json"
    row = {
        "sample_id": r.sample_id,
        "source": r.source,
        "split": "real-val",
        "exam_id": r.exam_id,
        "exam_type": r.exam_type,
        "level": r.target_feedback_level,
        "reviewer1_id": "reviewer-a",
        "reviewer1_diagnosis_correctness": 3,
    }
    path.write_text(json.dumps({"annotations": [row]}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid diagnosis"):
        aggregate_annotations(path, [r])
    row["reviewer1_diagnosis_correctness"] = 2
    row["split"] = "real-train"
    path.write_text(json.dumps({"annotations": [row]}), encoding="utf-8")
    with pytest.raises(ValueError, match="split"):
        aggregate_annotations(path, [r])
    row["split"] = "real-val"
    path.write_text(json.dumps({"annotations": [row, row]}), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        aggregate_annotations(path, [r])


def test_benchmark_template_marks_every_unrun_mode_explicitly(tmp_path):
    write_benchmark(tmp_path, "TEST-model", "TEST-revision")
    benchmark = json.loads((tmp_path / "benchmark.json").read_text())
    assert len(benchmark["runs"]) == 8
    assert {row["status"] for row in benchmark["runs"]} == {"NOT RUN"}
    assert "mixed_balanced" in (tmp_path / "benchmark.md").read_text()


def test_taxonomy_agreement_only_for_prediction_mode():
    r = record()
    preds, traces = infer([r], MockBackend(), {"context_limit": 10000})
    assert evaluate([r], preds)["taxonomy_agreement"].startswith("not applicable")
    assert evaluate([r], preds, taxonomy_source="task2-json")["taxonomy_agreement"]["exact_match"] == 1


@pytest.mark.parametrize("data", [[None], [{"sample_id": "TEST", "output": None}], {"TEST": {"output": None}}])
def test_malformed_taxonomy_envelope_fails_cleanly(tmp_path, data):
    path = tmp_path / "bad.json"
    write_json(path, data)
    with pytest.raises(ValueError):
        load_taxonomy_predictions(path, ["TEST"])


def test_all_taxonomy_inputs_validated_before_first_generation():
    class CountingBackend(MockBackend):
        calls = 0

        def generate(self, messages, config):
            self.calls += 1
            return super().generate(messages, config)

    backend = CountingBackend()
    rows = [record("TEST-1", source="public"), record("TEST-2", source="public")]
    with pytest.raises(ValueError):
        infer(rows, backend, {"context_limit": 10000}, "task2-json", {"TEST-1": []})
    assert backend.calls == 0
