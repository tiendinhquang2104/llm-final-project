import csv
import json
from pathlib import Path

import pytest

from src.synth.feedback import FEEDBACK_LEVELS
from src.task3.dataset import write_json
from src.task3.evaluator import aggregate_annotations, evaluate, write_benchmark, write_review_csv
from src.task3.inference import Generation, MockBackend
from src.task3.pipeline import (
    audit_prompts,
    export_predictions,
    infer,
    load_taxonomy_predictions,
    taxonomy_for,
    validate_predictions,
)
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
    assert load_taxonomy_predictions(path, ["TEST"], allow_unverified=True) == {"TEST": []}


def test_task2_extra_ids_are_audited_projection_not_a_task3_failure(tmp_path):
    path = tmp_path / "taxonomy.json"
    write_json(path, {"TEST": [], "EXTRA": ["Lỗi logic"]})
    predictions, audit = load_taxonomy_predictions(
        path, ["TEST"], return_audit=True, allow_unverified=True
    )
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
    projected, audit = load_taxonomy_predictions(
        path, ["TEST"], return_audit=True, allow_unverified=True
    )
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


def test_taxonomy_projection_requires_provenance_unless_explicitly_allowed(tmp_path):
    path = tmp_path / "taxonomy.json"
    write_json(path, [{"sample_id": "TEST", "output": {"taxonomy_error": []}}])

    with pytest.raises(ValueError, match="provenance is unknown"):
        load_taxonomy_predictions(path, ["TEST"])

    projected, audit = load_taxonomy_predictions(
        path, ["TEST"], return_audit=True, allow_unverified=True
    )
    assert projected == {"TEST": []}
    assert audit["provenance_status"] == "provenance_unknown"
    assert audit["provenance_unknown_required_count"] == 1


@pytest.mark.parametrize(
    "data",
    [
        [
            {"sample_id": "TEST", "labels": [], "parse_ok": True},
            {"sample_id": "EXTRA", "labels": ["NOT A TAXONOMY"], "parse_ok": False},
        ],
        [
            {"sample_id": "TEST", "output": {"taxonomy_error": []}, "parse_ok": True},
            {"sample_id": "EXTRA", "output": None, "parse_ok": False},
        ],
    ],
)
def test_failed_or_malformed_extra_predictions_do_not_block_requested_ids(tmp_path, data):
    path = tmp_path / "taxonomy.json"
    write_json(path, data)
    projected, audit = load_taxonomy_predictions(path, ["TEST"], return_audit=True)
    assert projected == {"TEST": []}
    assert audit["ignored_extra_id_count"] == 1


def test_duplicate_extra_ids_fail_before_projection(tmp_path):
    path = tmp_path / "taxonomy.json"
    write_json(
        path,
        [
            {"sample_id": "TEST", "labels": [], "parse_ok": True},
            {"sample_id": "EXTRA", "labels": [], "parse_ok": True},
            {"sample_id": "EXTRA", "parse_ok": False},
        ],
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_taxonomy_predictions(path, ["TEST"])


def test_rich_task2_full_export_with_parse_status(tmp_path):
    path = tmp_path / "predictions_full.json"
    write_json(
        path,
        [
            {
                "sample_id": "TEST",
                "labels": [],
                "probs": {"Lỗi logic": 0.0},
                "parse_ok": True,
            }
        ],
    )
    assert load_taxonomy_predictions(path, ["TEST"]) == {"TEST": []}


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


def test_cache_identity_tracks_system_and_selected_demonstrations(tmp_path, monkeypatch):
    from dataclasses import replace

    import src.task3.prompts as prompts

    target = record(
        "TEST-TARGET",
        source="real",
        split="real-val",
        group_key="eval",
        code="int main(){return 12;}",
    )
    demo = record(
        "TEST-DEMO",
        source="real",
        split="real-train",
        group_key="demo",
        code="int main(){return 13;}",
        gold_feedback="TEST demonstration A",
    )

    class CountingBackend(MockBackend):
        calls = 0

        def generate(self, messages, config):
            self.calls += 1
            return super().generate(messages, config)

    def count_calls(path, demo_pool):
        backend = CountingBackend()
        infer(
            [target],
            backend,
            {"context_limit": 10000, "max_retries": 0, "few_shot_k": 1},
            progress_path=path,
            resume=True,
            cache_context="TEST-manifest",
            demo_pool=demo_pool,
        )
        return backend.calls

    progress = tmp_path / "system.progress.jsonl"
    first = CountingBackend()
    infer(
        [target],
        first,
        {"context_limit": 10000, "max_retries": 0, "few_shot_k": 1},
        progress_path=progress,
        cache_context="TEST-manifest",
        demo_pool=[demo],
    )
    assert count_calls(progress, [demo]) == 0

    original_system = prompts.SYSTEM
    monkeypatch.setattr(prompts, "SYSTEM", original_system + " TEST policy revision")
    assert count_calls(progress, [demo]) == 1

    demo_progress = tmp_path / "demo.progress.jsonl"
    baseline = CountingBackend()
    monkeypatch.setattr(prompts, "SYSTEM", original_system)
    infer(
        [target],
        baseline,
        {"context_limit": 10000, "max_retries": 0, "few_shot_k": 1},
        progress_path=demo_progress,
        cache_context="TEST-manifest",
        demo_pool=[demo],
    )
    updated_demo = replace(demo, gold_feedback="TEST demonstration B")
    assert count_calls(demo_progress, [updated_demo]) == 1


def test_cache_invalidates_for_adapter_config_input_taxonomy_and_manifest(tmp_path):
    from dataclasses import replace

    class CountingBackend(MockBackend):
        calls = 0

        def generate(self, messages, config):
            self.calls += 1
            return super().generate(messages, config)

    r = record("TEST-CACHE", source="public")
    adapter = tmp_path / "adapter.bin"
    adapter.write_bytes(b"TEST adapter A")
    config = {"context_limit": 10000, "max_retries": 0, "adapter": str(adapter)}
    progress = tmp_path / "cache.progress.jsonl"

    def call(rows, run_config, taxonomy, context):
        backend = CountingBackend()
        infer(
            rows,
            backend,
            run_config,
            "task2-json",
            taxonomy,
            progress_path=progress,
            resume=True,
            cache_context=context,
        )
        return backend.calls

    assert call([r], config, {r.sample_id: []}, "TEST-manifest") == 1
    assert call([r], config, {r.sample_id: []}, "TEST-manifest") == 0
    assert call([r], {**config, "max_new_tokens": 123}, {r.sample_id: []}, "TEST-manifest") == 1
    assert call([replace(r, code="TEST changed input")], config, {r.sample_id: []}, "TEST-manifest") == 1
    assert call([r], config, {r.sample_id: ["Lỗi logic"]}, "TEST-manifest") == 1
    adapter.write_bytes(b"TEST adapter B")
    assert call([r], config, {r.sample_id: []}, "TEST-manifest") == 1
    assert call([r], config, {r.sample_id: []}, "TEST-manifest-changed") == 1


def test_retry_context_overflow_uses_conservative_fallback_and_is_audited():
    from src.task3.prompts import RETRY_HINT, budget_prompt

    r = record()
    tokenizer = MockBackend.tokenizer
    initial = budget_prompt(r, r.gold_taxonomy, tokenizer, 10000, 100)
    retry = budget_prompt(r, r.gold_taxonomy, tokenizer, 10000, 100, strict_hint=RETRY_HINT)
    context_limit = retry.input_tokens + 99
    assert initial.input_tokens + 100 <= context_limit

    config = {"context_limit": context_limit, "max_new_tokens": 100, "max_retries": 1}
    audit = audit_prompts([r], tokenizer, config)
    assert audit["blocked_initial_count"] == 0
    assert audit["retry_context_blocked_count"] == 1
    assert audit["status"] == "passed_with_retry_fallback"

    class BadBackend(MockBackend):
        calls = 0

        def generate(self, messages, config):
            self.calls += 1
            return Generation("```cpp\nreturn 0;\n```", 10, 0.1)

    backend = BadBackend()
    predictions, traces = infer([r], backend, config)
    assert backend.calls == 1
    assert predictions[0]["output"]["feedback"] != "```cpp\nreturn 0;\n```"
    assert traces[0]["retry_context_blocked"] is True
    assert traces[0]["fallback_reason"] == "retry_context_too_long"


def test_partial_final_progress_line_is_ignored_and_audited(tmp_path):
    r = record()
    progress = tmp_path / "recover.progress.jsonl"
    infer([r], MockBackend(), {"context_limit": 10000}, progress_path=progress)
    with progress.open("a", encoding="utf-8") as stream:
        stream.write('{"status":"partial"')

    class CountingBackend(MockBackend):
        calls = 0

        def generate(self, messages, config):
            self.calls += 1
            return super().generate(messages, config)

    backend = CountingBackend()
    _, traces = infer(
        [r],
        backend,
        {"context_limit": 10000},
        progress_path=progress,
        resume=True,
    )
    assert backend.calls == 0
    assert traces[0]["progress_recovery"] == {"ignored_partial_final_line": True}
    assert progress.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("corruption", ["malformed_complete", "duplicate_id"])
def test_complete_corrupt_or_duplicate_progress_rows_fail_closed(tmp_path, corruption):
    r = record()
    progress = tmp_path / f"{corruption}.progress.jsonl"
    infer([r], MockBackend(), {"context_limit": 10000}, progress_path=progress)
    if corruption == "malformed_complete":
        with progress.open("a", encoding="utf-8") as stream:
            stream.write('{"status":"failed"}\n')
    else:
        with progress.open("a", encoding="utf-8") as stream:
            stream.write(progress.read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="invalid inference progress record"):
        infer(
            [r],
            MockBackend(),
            {"context_limit": 10000},
            progress_path=progress,
            resume=True,
        )


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


def test_review_template_preserves_existing_file_and_backs_up_forced_replacement(tmp_path):
    r = record(source="real", split="real-val")
    path = tmp_path / "review-template.csv"
    assert write_review_csv(path, [r])["status"] == "created"
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "TEST reviewer edit\n", encoding="utf-8")

    preserved = write_review_csv(path, [r])
    assert preserved["status"] == "preserved_existing"
    assert path.read_text(encoding="utf-8") == original + "TEST reviewer edit\n"

    replaced = write_review_csv(path, [r], force=True)
    assert replaced["status"] == "created"
    assert replaced["backup"]
    assert Path(replaced["backup"]).read_text(encoding="utf-8") == original + "TEST reviewer edit\n"
    assert "TEST reviewer edit" not in path.read_text(encoding="utf-8")


def test_review_annotations_are_bound_to_exact_predictions_and_run(tmp_path):
    r = record(source="real", split="real-val")
    predictions, traces = infer([r], MockBackend(), {"context_limit": 10000})
    run_manifest = {
        "config": {"model_id": "TEST-model", "revision": "TEST-revision"},
        "split": "real-val",
        "taxonomy_source": "gold",
        "data_manifest_sha256": "TEST-data-hash",
    }
    path = tmp_path / "annotations.csv"
    write_review_csv(
        path,
        [r],
        traces,
        predictions=predictions,
        run_manifest=run_manifest,
    )
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        row = next(reader)
    row["reviewer1_id"] = "reviewer-a"
    row["reviewer1_diagnosis_correctness"] = "2"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)

    result = evaluate(
        [r],
        predictions,
        traces,
        annotations=path,
        run_manifest=run_manifest,
    )
    human = result["human_diagnosis_assessment"]
    assert human["n_template_rows"] == 1
    assert human["n_reviewed_ids"] == 1
    assert human["n_empty_annotation_records"] == 0
    assert human["n_reviewer_ratings"] == 1

    changed_predictions = [
        {
            **predictions[0],
            "output": {**predictions[0]["output"], "feedback": "TEST altered prediction"},
        }
    ]
    with pytest.raises(ValueError, match="predictions_sha256"):
        evaluate(
            [r],
            changed_predictions,
            traces,
            annotations=path,
            run_manifest=run_manifest,
        )
    changed_run = {**run_manifest, "config": {**run_manifest["config"], "revision": "TEST-other-revision"}}
    with pytest.raises(ValueError, match="run_identity_sha256"):
        evaluate([r], predictions, traces, annotations=path, run_manifest=changed_run)


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


def test_oracle_evaluation_rejects_prediction_taxonomy_that_differs_from_gold():
    r = record(gold_taxonomy=[])
    predictions, _ = infer([r], MockBackend(), {"context_limit": 10000})
    predictions[0]["output"]["taxonomy_error"] = ["Lỗi logic"]
    with pytest.raises(ValueError, match="oracle prediction taxonomy"):
        evaluate([r], predictions, taxonomy_source="gold")


def test_predicted_taxonomy_reports_multilabel_metrics_and_empty_sets():
    rows = [
        record("TEST-METRIC-1", gold_taxonomy=["Lỗi logic"]),
        record("TEST-METRIC-2", gold_taxonomy=[]),
    ]
    predictions = [
        {"sample_id": "TEST-METRIC-1", "output": {"taxonomy_error": ["Lỗi logic"], "feedback": "đủ"}},
        {"sample_id": "TEST-METRIC-2", "output": {"taxonomy_error": ["Lỗi hàm"], "feedback": "đủ"}},
    ]

    metrics = evaluate(rows, predictions, taxonomy_source="task2-json")["taxonomy_prediction_metrics"]

    assert metrics["n"] == 2
    assert metrics["macro_f1"] == pytest.approx(0.1)
    assert metrics["micro_f1"] == pytest.approx(2 / 3)
    assert metrics["per_label"]["Lỗi logic"]["precision"] == 1
    assert metrics["per_label"]["Lỗi logic"]["recall"] == 1
    assert metrics["per_label"]["Lỗi hàm"]["precision"] == 0
    assert metrics["per_label"]["Lỗi hàm"]["recall"] is None
    assert metrics["empty_reference_count"] == 1
    assert metrics["empty_prediction_count"] == 0
    assert metrics["empty_exact_match_count"] == 0


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
