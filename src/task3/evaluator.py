"""Heuristic feedback checks and auditable human diagnosis assessment."""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from src.task3.compliance import check
from src.task3.dataset import write_json
from src.task3.pipeline import validate_predictions

_REVIEWABLE_SPLITS = {"real-val", "synthetic-heldout"}
_RUBRIC = {
    "diagnosis_correctness": {"0", "1", "2"},
    "code_evidence_support": {"0", "1", "2"},
    "hallucinated_error": {"yes", "no"},
    "prerequisite_reasoning": {"yes", "no", "na"},
    "level_violation": {"yes", "no"},
}
_AGREEMENT_FIELDS = tuple(_RUBRIC)


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
    numeric = ("diagnosis_correctness", "code_evidence_support")
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
        for field in ("hallucinated_error", "prerequisite_reasoning", "level_violation"):
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
    per_level = defaultdict(list)
    for record, pred in zip(records, predictions):
        result = check(pred["output"]["feedback"], record.target_feedback_level)
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
        "severe_solution_leak_rate_level12": rate([item.severe for item in low]),
        "severe_solution_leak": rate([item.severe for item in low]),
        "empty_response_rate": rate([not prediction["output"]["feedback"].strip() for prediction in predictions]),
        "mean_response_chars": rate([len(prediction["output"]["feedback"]) for prediction in predictions]),
        "diagnosis_quality": "not_measured",
        "diagnosis_quality_status": "not_measured",
        "taxonomy_agreement": "not applicable: oracle labels" if taxonomy_source == "gold" else "no gold available",
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
        )
    if taxonomy_source != "gold":
        if paired:
            result["taxonomy_agreement"] = {
                "n": len(paired),
                "exact_match": rate([set(gold) == set(predicted) for gold, predicted in paired]),
            }
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
