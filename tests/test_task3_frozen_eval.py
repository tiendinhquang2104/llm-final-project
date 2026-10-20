"""Offline evaluator contract tests; all inputs here are synthetic fixtures."""
import hashlib
import json

import pytest

from src.synth.taxonomy import LABEL_SPACE
from src.task3.frozen_eval import evaluate, output_digest

A, B = LABEL_SPACE[:2]


def record(sid, labels, level=1, source=None, status="defect", exam="single_problem"):
    return dict(sample_id=sid, level=level, exam_type=exam, annotation_v2=labels,
                source_reference=source, defect_status=status, findings=[])


def request(rid, sid, level=1, kind="primary"):
    return dict(request_id=rid, sample_id=sid, level=level, kind=kind)


def prediction(rid, labels, feedback="Phản hồi tiếng Việt"):
    return dict(request_id=rid, status="completed", output=dict(taxonomy_error=labels, feedback=feedback))


def snapshot(records, requests):
    return dict(records=records, requests=requests)


def review(pred, **assessments):
    return dict(request_id=pred["request_id"], prediction_sha256=output_digest(pred["output"]),
                reviewer="agent-reviewed", rationale="Reviewed against frozen findings",
                evidence=["finding:1"], assessments=assessments)


def test_full_label_space_and_numeric_metrics_include_missing_reference_fn():
    snap = snapshot([record("a", [A, B], source=[B]), record("b", [B], source=None)],
                    [request("a", "a"), request("b", "b")])
    result = evaluate(snap, [prediction("a", [A])])
    metrics = result["primary"]["annotation_v2"]
    assert len(metrics["per_label"]) == 10
    assert metrics["micro"] == dict(tp=1, fp=0, fn=2, precision=1.0, recall=1 / 3, f1=0.5)
    assert metrics["macro"]["f1"] == 0.1
    assert metrics["exact_set"] == dict(numerator=0, denominator=2, rate=0.0)
    assert result["primary"]["source_reference"]["support"] == 1
    assert result["primary"]["source_reference"]["excluded"] == 1
    assert result["primary"]["source_reference"]["micro"]["fp"] == 1
    assert result == evaluate(snap, [prediction("a", [A])])


def test_valid_empty_labels_can_match_clean_but_abstention_and_missing_cannot():
    snap = snapshot([record("c", [], status="scoped_clean")],
                    [request("good", "c"), request("abstain", "c"), request("missing", "c")])
    result = evaluate(snap, [prediction("good", []), dict(request_id="abstain", status="abstained")])["primary"]
    assert result["annotation_v2"]["exact_set"] == dict(numerator=1, denominator=3, rate=1 / 3)
    assert result["counts"]["statuses"] == dict(completed=1, unresolved=1, abstained=1, runtime_error=0, schema_error=0)
    assert result["counts"]["completion_rate"] == dict(numerator=1, denominator=3, rate=1 / 3)


@pytest.mark.parametrize("output", [None, {}, {"feedback": "x"}, {"taxonomy_error": [A, A], "feedback": "x"},
    {"taxonomy_error": ["unknown"], "feedback": "x"}, {"taxonomy_error": [], "feedback": None},
    {"taxonomy_error": "[]", "feedback": "x"}, {"taxonomy_error": [], "feedback": "x", "extra": 1}])
def test_bad_completed_outputs_are_schema_errors(output):
    snap = snapshot([record("a", [A])], [request("a", "a")])
    result = evaluate(snap, [dict(request_id="a", status="completed", output=output)])["primary"]
    assert result["counts"]["statuses"]["schema_error"] == 1
    assert result["annotation_v2"]["micro"]["fn"] == 1
    assert result["counts"]["schema_rate"] == dict(numerator=0, denominator=1, rate=0.0)


def test_json_output_and_hash_are_canonical_and_unicode_diagnostic_is_separate():
    out = {"feedback": "汉字", "taxonomy_error": [A]}
    expected = hashlib.sha256(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert output_digest(out) == expected
    snap = snapshot([record("a", [A])], [request("a", "a")])
    result = evaluate(snap, [dict(request_id="a", status="completed", raw_text=json.dumps(out))])
    assert result["primary"]["annotation_v2"]["exact_set"]["numerator"] == 1
    assert result["unicode_diagnostics"]["cjk_request_ids"] == ["a"]
    assert result["primary"]["feedback_review"]["assessments"]["cjk"]["true"] is None


def test_strata_and_counterfactual_invariance_require_requested_complete_triples():
    snap = snapshot([record("a", [A]), record("b", [B], level=2, exam="multi_problem")],
        [request("primary", "a"), *[request(f"a{i}", "a", i, "counterfactual") for i in (1, 2, 3)],
         request("b1", "b", 1, "counterfactual"), request("b2", "b", 2, "counterfactual")])
    preds = [prediction("primary", [B]), *[prediction(f"a{i}", [A]) for i in (1, 2, 3)], prediction("b1", [B])]
    result = evaluate(snap, preds)
    assert result["primary"]["annotation_v2"]["micro"]["fp"] == 1
    assert result["counterfactual"]["annotation_v2"]["micro"]["tp"] == 4
    assert result["counterfactual"]["by_level"]["2"]["counts"]["requested"] == 2
    assert result["counterfactual"]["by_exam_type"]["multi_problem"]["counts"]["requested"] == 2
    assert result["invariance"] == dict(requested_groups=2, requested_complete_triples=1,
        incomplete_requested_groups=1, completed_triples=1, incomplete_prediction_triples=0,
        exact_set=dict(numerator=1, denominator=1, rate=1.0))
    preds = [p for p in preds if p["request_id"] != "a3"]
    assert evaluate(snap, preds)["invariance"]["incomplete_prediction_triples"] == 1


@pytest.mark.parametrize("rows", [[prediction("a", []), prediction("a", [])], [prediction("unknown", [])]])
def test_duplicate_and_unknown_prediction_ids_are_rejected(rows):
    with pytest.raises(ValueError):
        evaluate(snapshot([record("a", [])], [request("a", "a")]), rows)


def test_ledger_pending_and_level_defect_denominators_are_explicit():
    records = [record("a", [A]), record("b", [A], level=2), record("c", [], level=3, status="scoped_clean")]
    snap = snapshot(records, [request("a", "a"), request("b", "b", 2), request("c", "c", 3)])
    preds = [prediction("a", [A]), prediction("b", [A]), prediction("c", [])]
    pending = evaluate(snap, preds)["primary"]["feedback_review"]
    assert pending["missing_ledger"] == 3
    assert pending["assessments"]["false_technical_claim"]["true"] is None
    ledger = [review(preds[0], l1_disclosure=False, false_clean=False),
              review(preds[1], l2_repair_leak=True, l2_location_cause_useful=True),
              review(preds[2], l3_cause_feasible_repair=True)]
    report = evaluate(snap, preds, ledger)["primary"]["feedback_review"]
    metric = report["assessments"]["l2_repair_leak"]
    assert metric == dict(requested=1, completed=1, reviewed=1, assessed=1, pending=0,
                          true=1, false=0, rate=1.0)
    assert report["assessments"]["l3_cause_feasible_repair"]["requested"] == 0
    assert report["assessments"]["false_clean"]["requested"] == 2
    assert report["assessments"]["false_clean"]["pending"] == 1


@pytest.mark.parametrize("mutation", ["duplicate", "unknown", "stale", "type", "rationale", "evidence"])
def test_invalid_review_ledger_is_rejected(mutation):
    snap = snapshot([record("a", [A])], [request("a", "a")])
    pred = prediction("a", [A])
    row = review(pred, false_clean=False)
    ledger = [row]
    if mutation == "duplicate":
        ledger.append(dict(row))
    elif mutation == "unknown":
        row["request_id"] = "unknown"
    elif mutation == "stale":
        row["prediction_sha256"] = "0" * 64
    elif mutation == "type":
        row["assessments"]["false_clean"] = 0
    else:
        row[mutation] = [] if mutation == "evidence" else ""
    with pytest.raises(ValueError):
        evaluate(snap, [pred], ledger)


def test_runtime_error_and_unresolved_rows_cannot_receive_clean_exact_credit():
    snap = snapshot([record("a", [A]), record("c", [], status="scoped_clean")],
                    [request("error", "a"), request("unknown", "c")])
    result = evaluate(snap, [dict(request_id="error", status="runtime_error"),
                             dict(request_id="unknown", status="unresolved")])["primary"]
    assert result["counts"]["statuses"]["runtime_error"] == 1
    assert result["counts"]["statuses"]["unresolved"] == 1
    assert result["annotation_v2"]["micro"]["fn"] == 1
    assert result["annotation_v2"]["exact_set"]["numerator"] == 0
    assert result["counts"]["schema_rate"] == dict(numerator=0, denominator=0, rate=None)


def test_all_ten_labels_have_independent_positive_support():
    snap = snapshot([record("a", list(LABEL_SPACE))], [request("a", "a")])
    result = evaluate(snap, [prediction("a", list(LABEL_SPACE))])["primary"]["annotation_v2"]
    assert result["micro"] == dict(tp=10, fp=0, fn=0, precision=1.0, recall=1.0, f1=1.0)
    assert result["macro"] == dict(precision=1.0, recall=1.0, f1=1.0)
    assert all(v["tp"] == 1 for v in result["per_label"].values())


def test_raw_malformed_json_is_schema_error_and_empty_request_set_has_no_fake_rates():
    snap = snapshot([record("a", [A])], [request("a", "a")])
    result = evaluate(snap, [dict(request_id="a", status="completed", raw_text="{broken")])
    assert result["primary"]["counts"]["statuses"]["schema_error"] == 1
    assert result["counterfactual"]["annotation_v2"]["exact_set"] == dict(numerator=0, denominator=0, rate=None)
    assert result["invariance"]["exact_set"]["denominator"] == 0


def test_review_template_binds_only_completed_outputs_and_remains_pending_until_filled():
    from src.task3.frozen_eval import review_template

    snap = snapshot([record("a", [A])], [request("a", "a"), request("b", "a")])
    pred = prediction("a", [A])
    rows = review_template(snap, [pred])
    assert len(rows) == 1
    assert rows[0]["request_id"] == "a"
    assert rows[0]["prediction_sha256"] == output_digest(pred["output"])
    assert rows[0]["assessments"]["l1_disclosure"] is None
    assert "l2_repair_leak" not in rows[0]["assessments"]
    with pytest.raises(ValueError):
        evaluate(snap, [pred], rows)
    rows[0].update(reviewer="agent-reviewed", rationale="Checked evidence", evidence=["finding:1"])
    report = evaluate(snap, [pred], rows)["primary"]["feedback_review"]
    assert report["reviewed"] == 1
    assert report["assessments"]["l1_disclosure"]["assessed"] == 0
    assert report["assessments"]["l1_disclosure"]["pending"] == 2


def test_primary_level_four_is_supported_but_counterfactual_level_four_is_rejected():
    snap = snapshot([record("a", [A], level=4)], [request("a", "a", level=4)])
    assert evaluate(snap, [prediction("a", [A])])["primary"]["by_level"]["4"]["counts"]["requested"] == 1
    snap["requests"][0]["kind"] = "counterfactual"
    with pytest.raises(ValueError):
        evaluate(snap, [prediction("a", [A])])


def test_disclosure_and_leak_denominators_include_clean_and_unresolved_records():
    snap = snapshot([record("clean", [], status="scoped_clean"),
                     record("unknown", [], level=2, status="unresolved")],
                    [request("clean", "clean"), request("unknown", "unknown", level=2)])
    result = evaluate(snap, [prediction("clean", []), prediction("unknown", [])])["primary"]["feedback_review"]
    assert result["assessments"]["l1_disclosure"]["requested"] == 1
    assert result["assessments"]["l2_repair_leak"]["requested"] == 1
    assert result["assessments"]["l2_location_cause_useful"]["requested"] == 0


@pytest.mark.parametrize("feedback", ["", " ", "\n\t"])
def test_blank_feedback_is_schema_error(feedback):
    snap = snapshot([record("a", [A])], [request("a", "a")])
    result = evaluate(snap, [prediction("a", [A], feedback=feedback)])["primary"]
    assert result["counts"]["statuses"]["schema_error"] == 1
    assert result["annotation_v2"]["micro"]["fn"] == 1


def test_explicit_schema_error_journal_status_is_accepted_separately():
    snap = snapshot([record("a", [A])], [request("a", "a")])
    result = evaluate(snap, [dict(request_id="a", status="schema_error")])["primary"]
    assert result["counts"]["statuses"]["schema_error"] == 1
    assert result["counts"]["statuses"]["runtime_error"] == 0
    assert result["counts"]["completion_rate"] == dict(numerator=0, denominator=1, rate=0.0)
    assert result["counts"]["schema_rate"] == dict(numerator=0, denominator=1, rate=0.0)
