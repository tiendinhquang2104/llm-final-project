"""Heuristic feedback checks and auditable human diagnosis assessment."""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from src.synth.taxonomy import LABEL_SPACE
from src.task3.compliance import check
from src.task3.dataset import write_json
from src.task3.pipeline import validate_predictions
from src.task3.quality_review import quality_review_flags

_REVIEWABLE_SPLITS = {"real-val", "synthetic-heldout"}
_RUBRIC = {
    "diagnosis_correctness": {"0", "1", "2"},
    "code_evidence_support": {"0", "1", "2"},
    "hallucinated_error": {"yes", "no"},
    "prerequisite_reasoning": {"yes", "no", "na"},
    "level_violation": {"yes", "no"},
    "level_adequacy": {"0", "1", "2"},
    "vietnamese_naturalness": {"0", "1", "2"},
    "repair_solution_quality": {"0", "1", "2", "na"},
    "false_praise": {"yes", "no", "na"},
}
_AGREEMENT_FIELDS = tuple(_RUBRIC)


def _taxonomy_prediction_metrics(pairs):
    """Score predicted multi-label taxonomy only where reference labels exist."""
    if not pairs:
        return {"n": 0, "status": "no gold taxonomy available"}
    per_label = {}
    total_tp = total_fp = total_fn = 0
    for label in LABEL_SPACE:
        tp = fp = fn = 0
        for gold, predicted in pairs:
            is_gold, is_predicted = label in gold, label in predicted
            tp += is_gold and is_predicted
            fp += is_predicted and not is_gold
            fn += is_gold and not is_predicted
        precision_denominator = tp + fp
        recall_denominator = tp + fn
        f1_denominator = 2 * tp + fp + fn
        per_label[label] = {
            "precision": tp / precision_denominator if precision_denominator else None,
            "recall": tp / recall_denominator if recall_denominator else None,
            "f1": 2 * tp / f1_denominator if f1_denominator else None,
            "support": tp + fn,
            "n_predicted": tp + fp,
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn
    present_f1 = [row["f1"] for row in per_label.values() if row["f1"] is not None]
    micro_denominator = 2 * total_tp + total_fp + total_fn
    empty_gold = sum(not gold for gold, _ in pairs)
    empty_predicted = sum(not predicted for _, predicted in pairs)
    empty_both = sum(not gold and not predicted for gold, predicted in pairs)
    return {
        "n": len(pairs),
        "status": "scored against available gold taxonomy",
        "macro_f1": sum(row["f1"] or 0.0 for row in per_label.values()) / len(LABEL_SPACE),
        "macro_f1_skip_absent": sum(present_f1) / len(present_f1) if present_f1 else None,
        "micro_f1": 2 * total_tp / micro_denominator if micro_denominator else None,
        "exact_match": sum(set(gold) == set(predicted) for gold, predicted in pairs) / len(pairs),
        "empty_reference_count": empty_gold,
        "empty_reference_rate": empty_gold / len(pairs),
        "empty_prediction_count": empty_predicted,
        "empty_prediction_rate": empty_predicted / len(pairs),
        "empty_exact_match_count": empty_both,
        "per_label": per_label,
    }


def _review_fields():
    fields = [
        "sample_id",
        "source",
        "split",
        "exam_id",
        "exam_type",
        "level",
        "fallback_used",
        "predictions_sha256",
        "run_identity_sha256",
        "sample_order_sha256",
        "annotation_bundle_sha256",
    ]
    for reviewer in (1, 2):
        prefix = f"reviewer{reviewer}"
        fields.append(f"{prefix}_id")
        fields.extend(f"{prefix}_{name}" for name in _RUBRIC)
        fields.extend((f"{prefix}_level_violation_type", f"{prefix}_notes_no_student_text"))
    return fields


def _canonical_sha256(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _annotation_bundle(records, predictions, run_manifest):
    if predictions is None or run_manifest is None:
        return {}
    config = run_manifest.get("config", {})
    model_id = run_manifest.get("model_id") or config.get("model_id")
    revision = run_manifest.get("model_revision") or config.get("revision")
    adapter_sha256 = run_manifest.get("adapter_sha256")
    if adapter_sha256 is None and config.get("adapter"):
        from src.task3.pipeline import _adapter_hash

        adapter_sha256 = _adapter_hash(config)
    stable_config = {key: value for key, value in config.items() if key not in {"output_dir", "adapter"}}
    config_sha256 = run_manifest.get("config_sha256") or _canonical_sha256(
        {"config": stable_config, "adapter_sha256": adapter_sha256}
    )
    sample_ids = [record.sample_id for record in records]
    identity = {
        "model_id": model_id,
        "model_revision": revision,
        "adapter_sha256": adapter_sha256,
        "config_sha256": config_sha256,
        "split": run_manifest.get("split"),
        "taxonomy_source": run_manifest.get("taxonomy_source"),
        "data_manifest_sha256": run_manifest.get("data_manifest_sha256"),
    }
    run_identity_sha256 = _canonical_sha256(identity)
    order_sha256 = _canonical_sha256(sample_ids)
    prediction_sha256 = _canonical_sha256(predictions)
    bundle = {
        **identity,
        "run_identity_sha256": run_identity_sha256,
        "sample_order_sha256": order_sha256,
        "predictions_sha256": prediction_sha256,
    }
    bundle["annotation_bundle_sha256"] = _canonical_sha256(bundle)
    return bundle


def write_review_csv(path, records, traces=(), *, predictions=None, run_manifest=None, force=False):
    """Write an ID-only two-reviewer worklist; never copy code or target feedback."""
    fields = _review_fields()
    trace_map = {row["sample_id"]: row for row in traces}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if path.exists():
        if path.stat().st_size:
            if not force:
                return {"status": "preserved_existing", "path": str(path)}
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup_path = path.with_name(f"{path.name}.{stamp}.bak")
            if backup_path.exists():
                raise FileExistsError(f"review template backup already exists: {backup_path}")
            path.replace(backup_path)
        else:
            path.unlink()

    bundle = _annotation_bundle(records, predictions, run_manifest)
    try:
        with path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fields)
            writer.writeheader()
            for record in records:
                if record.split not in _REVIEWABLE_SPLITS:
                    continue
                row = {
                    "sample_id": record.sample_id,
                    "source": record.source,
                    "split": record.split,
                    "exam_id": record.exam_id,
                    "exam_type": record.exam_type,
                    "level": record.target_feedback_level,
                    "fallback_used": (
                        str(bool(trace_map[record.sample_id].get("fallback_used", trace_map[record.sample_id].get("fallback")))).lower()
                        if record.sample_id in trace_map
                        else ""
                    ),
                    **{
                        field: bundle.get(field, "")
                        for field in (
                            "predictions_sha256",
                            "run_identity_sha256",
                            "sample_order_sha256",
                            "annotation_bundle_sha256",
                        )
                    },
                }
                writer.writerow(row)
        path.chmod(0o600)
    except Exception:
        if backup_path is not None:
            path.unlink(missing_ok=True)
            backup_path.replace(path)
        raise
    return {"status": "created", "path": str(path), "backup": str(backup_path) if backup_path else None}


def _load_annotations(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("annotations")
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise ValueError("annotations must be a JSON array or an object with an annotations array")
    return payload


def _clean_value(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def aggregate_annotations(path, records, *, expected_bundle=None):
    """Validate and summarize reviewer entries without returning notes or per-example judgments."""
    expected = {
        record.sample_id: record for record in records if record.split in _REVIEWABLE_SPLITS
    }
    rows = _load_annotations(path)
    seen = set()
    reviewed_ids = set()
    empty_annotation_records = 0
    observations = []
    for row in rows:
        sid = row.get("sample_id")
        if not isinstance(sid, str) or sid not in expected or sid in seen:
            raise ValueError("annotation IDs must be unique and belong to the supplied evaluation splits")
        seen.add(sid)
        record = expected[sid]
        if row.get("source") != record.source:
            raise ValueError("annotation source does not match split provenance")
        if row.get("split") != record.split:
            raise ValueError("annotation split does not match split provenance")
        if row.get("exam_id") != record.exam_id:
            raise ValueError("annotation exam ID does not match source record")
        if row.get("exam_type") != record.exam_type:
            raise ValueError("annotation exam type does not match source record")
        if row.get("level") != record.target_feedback_level:
            raise ValueError("annotation level does not match source record")
        if expected_bundle is not None:
            for field in (
                "predictions_sha256",
                "run_identity_sha256",
                "sample_order_sha256",
                "annotation_bundle_sha256",
            ):
                if _clean_value(row.get(field)) != _clean_value(expected_bundle.get(field)):
                    raise ValueError(f"annotation {field} does not match the current prediction run")
        fallback_used = _clean_value(row.get("fallback_used"))
        if fallback_used not in {"", "true", "false"}:
            raise ValueError("fallback_used must be true, false or blank")
        has_reviewer = False
        for reviewer in (1, 2):
            prefix = f"reviewer{reviewer}"
            rater = _clean_value(row.get(f"{prefix}_id"))
            values = {name: _clean_value(row.get(f"{prefix}_{name}")) for name in _RUBRIC}
            violation_type = str(row.get(f"{prefix}_level_violation_type") or "").strip()
            notes = str(row.get(f"{prefix}_notes_no_student_text") or "").strip()
            if not rater and (any(values.values()) or violation_type or notes):
                raise ValueError("reviewer ID is required when reviewer fields are filled")
            if not rater:
                continue
            has_reviewer = True
            if reviewer == 2 and rater == _clean_value(row.get("reviewer1_id")):
                raise ValueError("reviewer IDs must be independent")
            for name, value in values.items():
                if value and value not in _RUBRIC[name]:
                    raise ValueError(f"invalid {name} rubric value")
            if values["level_violation"] == "yes" and not violation_type:
                raise ValueError("level_violation_type is required when a violation is marked yes")
            if len(record.code) >= 20 and record.code in notes:
                raise ValueError("review notes contain student source text")
            if record.gold_feedback and len(record.gold_feedback) >= 20 and record.gold_feedback in notes:
                raise ValueError("review notes contain instructor target text")
            observations.append(
                {
                    "sample_id": sid,
                    "reviewer": reviewer,
                    "rater_id": rater,
                    "level": record.target_feedback_level,
                    "exam_type": record.exam_type,
                    "fallback_used": fallback_used or "unknown",
                    **values,
                }
            )
        if has_reviewer:
            reviewed_ids.add(sid)
        else:
            empty_annotation_records += 1
    by_key = defaultdict(list)
    numeric = ("diagnosis_correctness", "code_evidence_support", "level_adequacy", "vietnamese_naturalness")
    for observation in observations:
        by_key[("level", observation["level"])].append(observation)
        by_key[("exam_type", observation["exam_type"])].append(observation)
        by_key[("fallback_used", observation["fallback_used"])].append(observation)

    def summarize(values):
        summary = {"n_ratings": len(values), "scores": {}}
        for field in numeric:
            present = [int(item[field]) for item in values if item[field]]
            summary["scores"][field] = {
                "n": len(present),
                "mean": statistics.mean(present) if present else None,
            }
        for field in ("hallucinated_error", "prerequisite_reasoning", "level_violation", "false_praise", "repair_solution_quality"):
            present = [item[field] for item in values if item[field]]
            summary[field] = {
                "n": len(present),
                "counts": {value: present.count(value) for value in sorted(set(present))},
            }
        return summary

    agreements = {}
    indexed = {row["sample_id"]: row for row in rows}
    for field in _AGREEMENT_FIELDS:
        pairs = []
        for sid, row in indexed.items():
            left = _clean_value(row.get(f"reviewer1_{field}"))
            right = _clean_value(row.get(f"reviewer2_{field}"))
            if left and right:
                pairs.append((left, right))
        item = {"n_pairs": len(pairs), "exact_agreement": None}
        if pairs:
            item["exact_agreement"] = sum(left == right for left, right in pairs) / len(pairs)
        if field in numeric:
            item["mean_absolute_difference"] = (
                statistics.mean(abs(int(left) - int(right)) for left, right in pairs) if pairs else None
            )
        agreements[field] = item
    diagnosis_n = sum(bool(item["diagnosis_correctness"]) for item in observations)
    return {
        "status": "measured" if diagnosis_n else "not_measured",
        "n_annotated_ids": len(seen),
        "n_template_rows": len(rows),
        "n_reviewed_ids": len(reviewed_ids),
        "n_empty_annotation_records": empty_annotation_records,
        "n_expected_ids": len(expected),
        "coverage": len(reviewed_ids) / len(expected) if expected else None,
        "n_reviewer_ratings": len(observations),
        "per_level": {key[1]: summarize(value) for key, value in by_key.items() if key[0] == "level"},
        "per_exam_type": {key[1]: summarize(value) for key, value in by_key.items() if key[0] == "exam_type"},
        "fallback_stratified": {
            key[1]: summarize(value) for key, value in by_key.items() if key[0] == "fallback_used"
        },
        "pairwise_agreement": agreements,
        "missingness_policy": "blank scores are missing, not zero; unreviewed IDs are excluded from score denominators",
        "confidence_caveat": "report coverage and counts; six real validation examples do not support precise population confidence",
    }


def evaluate(records, predictions, traces=(), taxonomy_source="gold", annotations=None, *, run_manifest=None):
    validate_predictions(predictions, [r.sample_id for r in records])
    trace_map = {r["sample_id"]: r for r in traces}
    guard_versions = {t.get("guard_policy_version", 1) for t in traces}
    if len(guard_versions) > 1:
        raise ValueError("evaluation cannot mix guard policy versions")
    manifest_config = (run_manifest or {}).get("config", {})
    manifest_guard = manifest_config.get("guard_policy_version", 1) if run_manifest is not None else None
    if manifest_guard is not None and guard_versions and manifest_guard not in guard_versions:
        raise ValueError("manifest and traces disagree on guard policy version")
    guard_version = next(iter(guard_versions), manifest_guard if manifest_guard is not None else 1)
    if isinstance(guard_version, bool) or guard_version not in (1, 2, 3):
        raise ValueError("unsupported guard policy version")
    per_level = defaultdict(list)
    for record, pred in zip(records, predictions):
        result = check(pred["output"]["feedback"], record.target_feedback_level, version=guard_version)
        per_level[result.level].append(result)
    all_results = [item for values in per_level.values() for item in values]
    low = [item for item in all_results if item.level <= 2]

    def rate(values):
        return statistics.mean(values) if values else None

    result = {
        "n": len(records),
        "taxonomy_source": taxonomy_source,
        "heuristic_compliance": rate([item.heuristic_compliance for item in all_results]),
        "semantic_compliance": "not_measured",
        "compliance": rate([item.ok for item in all_results]),
        "compliance_per_level": {
            str(level): {"n": len(values), "rate": rate([item.ok for item in values])}
            for level, values in sorted(per_level.items())
        },
        "guard_method": "rule-based heuristic; not a semantic correctness guarantee",
        "guard_policy_version": guard_version,
        "severe_solution_leak_rate_level12": rate([item.severe for item in low]),
        "severe_solution_leak": rate([item.severe for item in low]),
        "empty_response_rate": rate([not prediction["output"]["feedback"].strip() for prediction in predictions]),
        "mean_response_chars": rate([len(prediction["output"]["feedback"]) for prediction in predictions]),
        "diagnosis_quality": "not_measured",
        "diagnosis_quality_status": "not_measured",
        "taxonomy_agreement": "not applicable: oracle labels" if taxonomy_source == "gold" else "no gold available",
        "semantic_dimensions": {
            "level_disclosure": "heuristic_only",
            "level_adequacy": "not_measured",
            "natural_vietnamese": "not_measured",
            "evidence_supported_diagnosis": "not_measured",
            "hallucination_and_false_praise": "not_measured",
            "repair_and_solution_quality": "not_measured",
            "fallback_latency_tokens": "measured_if_traces_present",
        },
    }
    review_rows = [
        quality_review_flags(record, pred["output"]["feedback"], fallback_used=trace_map.get(record.sample_id, {}).get("fallback_used", False), version=3 if guard_version == 3 else 2 if guard_version == 2 else 1)
        for record, pred in zip(records, predictions)
    ]
    result["quality_review_candidates"] = {
        "warning_only": True,
        "n_flagged": sum(bool(row["flags"]) for row in review_rows),
        "flag_counts": dict(sorted({flag: sum(flag in row["flags"] for row in review_rows) for row in review_rows for flag in row["flags"]}.items())),
        "semantic_quality": "NOT_MEASURED",
    }
    paired = [
        (record.gold_taxonomy, prediction["output"]["taxonomy_error"])
        for record, prediction in zip(records, predictions)
        if record.gold_taxonomy is not None
    ]
    if taxonomy_source == "gold":
        if len(paired) != len(records):
            raise ValueError("oracle evaluation requires gold taxonomy for every record")
        if any(list(gold) != list(predicted) for gold, predicted in paired):
            raise ValueError("oracle prediction taxonomy does not match supplied gold taxonomy")
    if paired:
        result["predicted_taxonomy_agreement"] = {
            "n": len(paired),
            "exact_match": rate([set(gold) == set(predicted) for gold, predicted in paired]),
        }
    if traces:
        if set(trace_map) != {record.sample_id for record in records} or len(trace_map) != len(traces):
            raise ValueError("trace IDs must exactly match evaluation records")
        first_attempts = [
            next(
                (attempt for attempt in trace_map[record.sample_id]["attempts"] if attempt.get("model_generated") is True),
                None,
            )
            for record in records
        ]
        first_generated = [attempt for attempt in first_attempts if attempt is not None]
        first_low = [
            attempt
            for record, attempt in zip(records, first_attempts)
            if attempt is not None and record.target_feedback_level.startswith(("Level 1", "Level 2"))
        ]
        fallback_flags = [trace_map[record.sample_id].get("fallback_used", False) for record in records]
        plans = [trace_map[record.sample_id].get("cot_plan_audit") for record in records]
        applicable_plans = [plan for plan in plans if isinstance(plan, dict)]
        rejected_first = [attempt for attempt in first_generated if attempt.get("heuristic_compliance") is False]
        rescued = [trace for trace in traces if trace.get("raw_first_attempt_compliance") is False and not trace.get("fallback_used")]
        model_success = [not flag and any(a.get("model_generated") and a.get("heuristic_compliance") is True for a in trace_map[record.sample_id]["attempts"]) for record, flag in zip(records, fallback_flags)]
        per_level_outcomes = {}
        for level in sorted(per_level):
            subset = [(record, trace_map[record.sample_id]) for record in records if int(record.target_feedback_level[6]) == level]
            per_level_outcomes[str(level)] = {
                "n": len(subset),
                "first_model_pass": sum(t.get("raw_first_attempt_compliance") is True for _, t in subset),
                "first_model_missing": sum(t.get("raw_first_attempt_compliance") is None for _, t in subset),
                "retry_rescued": sum(t.get("raw_first_attempt_compliance") is False and not t.get("fallback_used") for _, t in subset),
                "fallback": sum(bool(t.get("fallback_used")) for _, t in subset),
            }
        result.update(
            raw_first_attempt_compliance=rate([attempt["heuristic_compliance"] for attempt in first_generated]),
            raw_first_attempt_compliance_n=len(first_generated),
            raw_first_attempt_severe_leak_rate_level12=rate([attempt["severe"] for attempt in first_low]),
            raw_first_attempt_severe_leak_level12_n=len(first_low),
            post_guard_compliance=result["heuristic_compliance"],
            fallback_rate=rate(fallback_flags),
            retry_count=sum(trace_map[record.sample_id].get("retry_count", 0) for record in records),
            mean_latency_s=rate([trace_map[record.sample_id]["latency_s"] for record in records]),
            generated_tokens=sum(trace_map[record.sample_id]["output_tokens"] for record in records),
            first_attempt_model_compliance_all_cases=rate([attempt is not None and attempt.get("heuristic_compliance") is True for attempt in first_attempts]),
            plan_validation_success_rate=rate([plan.get("status") == "validated" for plan in applicable_plans]),
            plan_validation_n=len(applicable_plans),
            retry_rescue_rate=(len(rescued) / len(rejected_first)) if rejected_first else None,
            retry_rescued_count=len(rescued),
            fallback_reasons=dict(sorted({reason: sum(t.get("fallback_reason") == reason for t in traces) for reason in {t.get("fallback_reason") for t in traces if t.get("fallback_reason")}}.items())),
            model_generated_feedback_success_rate=rate(model_success),
            per_level_outcomes=per_level_outcomes,
            feedback_tokens=sum(t.get("feedback_output_tokens", 0) for t in traces),
            plan_tokens=sum(t.get("cot_plan_output_tokens", 0) for t in traces),
            completion_retry_rescued_count=sum(bool(t.get("completion_retry_rescued")) for t in traces),
            adequacy_retry_rescued_count=sum(bool(t.get("adequacy_retry_rescued")) for t in traces),
            incomplete_feedback_attempt_count=sum(not a.get("mechanically_complete", True) for t in traces for a in t["attempts"] if a.get("model_generated")),
            nonempty_validated_plan_count=sum(bool(p.get("finding_count")) for p in applicable_plans if p.get("status") == "validated"),
        )
    if taxonomy_source != "gold":
        if paired:
            result["taxonomy_agreement"] = {
                "n": len(paired),
                "exact_match": rate([set(gold) == set(predicted) for gold, predicted in paired]),
            }
        result["taxonomy_prediction_metrics"] = _taxonomy_prediction_metrics(paired)
    if annotations is not None:
        if run_manifest is None:
            raise ValueError("a matching run manifest is required to evaluate bound human annotations")
        expected_bundle = _annotation_bundle(records, predictions, run_manifest)
        human = aggregate_annotations(annotations, records, expected_bundle=expected_bundle)
        result["human_diagnosis_assessment"] = human
        result["diagnosis_quality_status"] = human["status"]
    return result


def benchmark_template(model_id, revision):
    modes = (
        "zero_shot",
        "few_shot",
        "synthetic_only",
        "real_only",
        "mixed_uniform",
        "mixed_balanced",
        "staged",
        "guarded",
    )
    return {
        "model_id": model_id,
        "model_revision": revision,
        "runs": [{"mode": mode, "status": "NOT RUN", "metrics": None} for mode in modes],
    }


def write_benchmark(directory, model_id, revision):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    benchmark = benchmark_template(model_id, revision)
    write_json(directory / "benchmark.json", benchmark)
    with (directory / "benchmark.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, ("mode", "status", "metrics"))
        writer.writeheader()
        writer.writerows(
            {"mode": row["mode"], "status": row["status"], "metrics": ""}
            for row in benchmark["runs"]
        )
    lines = ["# Task 3 benchmark status", "", f"Model: `{model_id}`", f"Revision: `{revision}`", "", "| Mode | Status |", "|---|---|"]
    lines.extend(f"| {row['mode']} | {row['status']} |" for row in benchmark["runs"])
    (directory / "benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
