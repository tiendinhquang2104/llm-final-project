"""Deterministic, inference-free evaluation of a frozen Task 3 request set.

``evaluate(snapshot, predictions, ledger=None)`` never reads files or runs models.
Primary and requested counterfactual rows are scored separately, including strata.
Each reference reports all ten labels, TP/FP/FN, micro/macro precision/recall/F1
(zero division is zero), and exact-set numerator/denominator. Missing, abstained,
runtime-error and malformed outputs predict no positive labels (reference FNs)
but NEVER earn an exact-set match, including on clean records. Explicit valid []
is a completed prediction, not abstention. Missing source_reference is excluded
from that reference's support, not replaced with annotation_v2.

Completion is schema-valid completed/requested. Schema rate is schema-valid /
rows declaring completed or explicit schema_error; both expose their integer denominators. Missing rows
are unresolved. Invariance compares label sets only on requested counterfactual
L1/L2/L3 triples with all three outputs schema-valid; incomplete support is shown.

Feedback semantics come exclusively from an external review ledger. Rows contain
request_id, prediction_sha256, reviewer, nonempty rationale and evidence, and an
assessments object with bool/null values. Allowed assessment keys are ASSESSMENTS.
Null/missing assessments are pending, never counted false. L1 disclosure and L2 repair-leak metrics apply to all matching-level records.
Useful L2/L3 feedback metrics apply only to matching-level defect records; false_clean and missing_core_finding
apply to defect records at any level. Other metrics apply to all records.
Rates are true/assessed (not true/requested); requested/completed/reviewed counts
and pending=requested-assessed expose review coverage. No assessed rows gives
true=false=rate=None. Unicode CJK detection is a separate diagnostic only.

``review_template`` produces pending rows for valid completions. Fill reviewer,
rationale and evidence before passing rows back to evaluate. ``output_digest``
hashes the parsed output as UTF-8 canonical JSON (ensure_ascii=False,
sort_keys=True, separators=(',', ':')); label order is preserved in the hash.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict

from src.synth.taxonomy import LABEL_SPACE

ASSESSMENTS = (
    "false_technical_claim", "false_clean", "missing_core_finding", "l1_disclosure",
    "l2_repair_leak", "l2_location_cause_useful", "l3_cause_feasible_repair", "vietnamese", "cjk",
)
_STATUSES = ("completed", "unresolved", "abstained", "runtime_error", "schema_error")
_CJK = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ffff\U00030000-\U000323af]")


def output_digest(parsed_output: dict) -> str:
    """Return the SHA-256 of canonical JSON, binding review to exact output."""
    return hashlib.sha256(json.dumps(parsed_output, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _ratio(numerator, denominator):
    return dict(numerator=numerator, denominator=denominator,
                rate=numerator / denominator if denominator else None)


def _labels(value):
    return (isinstance(value, list) and all(isinstance(v, str) and v in LABEL_SPACE for v in value)
            and len(value) == len(set(value)))


def _output(row):
    if row.get("status") != "completed":
        return None
    try:
        out = row["output"] if "output" in row else json.loads(row["raw_text"])
    except (KeyError, TypeError, ValueError):
        return None
    if (not isinstance(out, dict) or set(out) != {"taxonomy_error", "feedback"}
            or not _labels(out["taxonomy_error"]) or not isinstance(out["feedback"], str)
            or not out["feedback"].strip()):
        return None
    return out


def _index(rows, key, name):
    indexed = {}
    for row in rows:
        value = row.get(key)
        if not isinstance(value, str) or not value or value in indexed:
            raise ValueError(f"{name}: missing, invalid or duplicate {key}: {value!r}")
        indexed[value] = row
    return indexed


def _prepare(snapshot, predictions):
    records = _index(snapshot["records"], "sample_id", "records")
    requests = _index(snapshot["requests"], "request_id", "requests")
    preds = _index(predictions, "request_id", "predictions")
    if set(preds) - set(requests):
        raise ValueError("predictions contain unknown request IDs")
    for record in records.values():
        if (not _labels(record.get("annotation_v2")) or
                (record.get("source_reference") is not None and not _labels(record["source_reference"]))):
            raise ValueError("invalid snapshot reference labels")
        if record.get("defect_status") not in {"defect", "scoped_clean", "unresolved"}:
            raise ValueError("invalid snapshot defect_status")
    items = []
    cf_keys = set()
    for rid, req in sorted(requests.items()):
        if req.get("sample_id") not in records or req.get("kind") not in {"primary", "counterfactual"}:
            raise ValueError("invalid snapshot request")
        levels = (1, 2, 3, 4) if req["kind"] == "primary" else (1, 2, 3)
        if type(req.get("level")) is not int or req["level"] not in levels:
            raise ValueError("primary levels must be 1..4; counterfactual levels must be 1..3")
        if req["kind"] == "counterfactual":
            key = (req["sample_id"], req["level"])
            if key in cf_keys:
                raise ValueError("duplicate counterfactual sample/level")
            cf_keys.add(key)
        pred = preds.get(rid)
        if pred is not None and pred.get("status") not in _STATUSES:
            raise ValueError("invalid prediction status")
        out = _output(pred) if pred else None
        status = "unresolved" if pred is None else pred["status"]
        declared_completed = status in {"completed", "schema_error"}
        if status == "completed" and out is None:
            status = "schema_error"
        items.append(dict(request=req, record=records[req["sample_id"]], output=out,
                          status=status, received=pred is not None, declared_completed=declared_completed))
    return items


def _ledger(items, ledger):
    indexed = _index(ledger or [], "request_id", "ledger")
    by_id = {item["request"]["request_id"]: item for item in items}
    for rid, row in indexed.items():
        if rid not in by_id:
            raise ValueError("ledger contains unknown request ID")
        out = by_id[rid]["output"]
        if out is None or row.get("prediction_sha256") != output_digest(out):
            raise ValueError("ledger output hash is stale or output is not completed")
        if not isinstance(row.get("reviewer"), str) or not row["reviewer"].strip():
            raise ValueError("ledger reviewer is required")
        if not isinstance(row.get("rationale"), str) or not row["rationale"].strip():
            raise ValueError("ledger rationale is required")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence or any(not isinstance(e, str) or not e.strip() for e in evidence):
            raise ValueError("ledger evidence must be a nonempty list of strings")
        values = row.get("assessments")
        if (not isinstance(values, dict) or set(values) - set(ASSESSMENTS)
                or any(v is not None and type(v) is not bool for v in values.values())):
            raise ValueError("ledger assessments must contain only known bool/null values")
    return indexed


def _prf(tp, fp, fn):
    return dict(tp=tp, fp=fp, fn=fn, precision=tp / (tp + fp) if tp + fp else 0.0,
                recall=tp / (tp + fn) if tp + fn else 0.0,
                f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0)


def _taxonomy(items, reference):
    supported = [item for item in items if item["record"].get(reference) is not None]
    per_label = {}
    for label in LABEL_SPACE:
        tp = fp = fn = 0
        for item in supported:
            expected = label in item["record"][reference]
            predicted = item["output"] is not None and label in item["output"]["taxonomy_error"]
            tp += expected and predicted
            fp += not expected and predicted
            fn += expected and not predicted
        per_label[label] = _prf(tp, fp, fn)
    micro = _prf(*(sum(m[k] for m in per_label.values()) for k in ("tp", "fp", "fn")))
    macro = {k: sum(m[k] for m in per_label.values()) / len(LABEL_SPACE) for k in ("precision", "recall", "f1")}
    exact = sum(item["output"] is not None and
                set(item["output"]["taxonomy_error"]) == set(item["record"][reference]) for item in supported)
    return dict(support=len(supported), excluded=len(items) - len(supported), per_label=per_label,
                micro=micro, macro=macro, exact_set=_ratio(exact, len(supported)))


def _relevant(item, assessment):
    level = {"l1_disclosure": 1, "l2_repair_leak": 2, "l2_location_cause_useful": 2,
             "l3_cause_feasible_repair": 3}.get(assessment)
    if level is not None and item["request"]["level"] != level:
        return False
    if assessment in {"l2_location_cause_useful", "l3_cause_feasible_repair", "false_clean", "missing_core_finding"}:
        return item["record"]["defect_status"] == "defect"
    return True


def _feedback(items, ledger):
    completed = sum(item["output"] is not None for item in items)
    reviewed = sum(item["request"]["request_id"] in ledger for item in items)
    report = dict(requested=len(items), completed=completed, reviewed=reviewed,
                  missing_ledger=completed - reviewed, pending_requests=len(items) - reviewed, assessments={})
    for assessment in ASSESSMENTS:
        relevant = [item for item in items if _relevant(item, assessment)]
        values = [ledger[item["request"]["request_id"]]["assessments"].get(assessment)
                  for item in relevant if item["request"]["request_id"] in ledger]
        assessed = [v for v in values if v is not None]
        report["assessments"][assessment] = dict(
            requested=len(relevant), completed=sum(item["output"] is not None for item in relevant),
            reviewed=len(values), assessed=len(assessed), pending=len(relevant) - len(assessed),
            true=sum(assessed) if assessed else None,
            false=len(assessed) - sum(assessed) if assessed else None,
            rate=sum(assessed) / len(assessed) if assessed else None)
    return report


def _summary(items, ledger):
    statuses = Counter(item["status"] for item in items)
    completed = statuses["completed"]
    counts = dict(requested=len(items), received=sum(item["received"] for item in items),
                  declared_completed=sum(item["declared_completed"] for item in items),
                  statuses={s: statuses[s] for s in _STATUSES},
                  completion_rate=_ratio(completed, len(items)),
                  schema_rate=_ratio(completed, sum(item["declared_completed"] for item in items)))
    return dict(counts=counts, annotation_v2=_taxonomy(items, "annotation_v2"),
                source_reference=_taxonomy(items, "source_reference"), feedback_review=_feedback(items, ledger))


def _invariance(items):
    groups = defaultdict(list)
    for item in items:
        if item["request"]["kind"] == "counterfactual":
            groups[item["request"]["sample_id"]].append(item)
    triples = [group for group in groups.values() if {i["request"]["level"] for i in group} == {1, 2, 3}]
    complete = [group for group in triples if all(i["output"] is not None for i in group)]
    same = sum(len({frozenset(i["output"]["taxonomy_error"]) for i in group}) == 1 for group in complete)
    return dict(requested_groups=len(groups), requested_complete_triples=len(triples),
                incomplete_requested_groups=len(groups) - len(triples), completed_triples=len(complete),
                incomplete_prediction_triples=len(triples) - len(complete), exact_set=_ratio(same, len(complete)))


def evaluate(snapshot: dict, predictions: list[dict], ledger: list[dict] | None = None) -> dict:
    """Evaluate supplied in-memory data; reject ambiguous IDs and invalid ledgers."""
    items = _prepare(snapshot, predictions)
    reviews = _ledger(items, ledger)
    result = {}
    for kind in ("primary", "counterfactual"):
        group = [item for item in items if item["request"]["kind"] == kind]
        report = _summary(group, reviews)
        for key, source in (("by_level", lambda i: str(i["request"]["level"])),
                            ("by_exam_type", lambda i: i["record"]["exam_type"])):
            report[key] = {value: _summary([item for item in group if source(item) == value], reviews)
                           for value in sorted({source(item) for item in group})}
        result[kind] = report
    result["invariance"] = _invariance(items)
    result["unicode_diagnostics"] = dict(cjk_request_ids=[item["request"]["request_id"] for item in items
        if item["output"] is not None and _CJK.search(item["output"]["feedback"])], semantic_judgment=False)
    return result


def review_template(snapshot: dict, predictions: list[dict]) -> list[dict]:
    """Create hash-bound pending ledger rows; fill provenance fields before use."""
    return [dict(request_id=item["request"]["request_id"], prediction_sha256=output_digest(item["output"]),
                 reviewer="", rationale="", evidence=[],
                 assessments={key: None for key in ASSESSMENTS if _relevant(item, key)})
            for item in _prepare(snapshot, predictions) if item["output"] is not None]
