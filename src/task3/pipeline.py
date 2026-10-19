"""Taxonomy routing, bounded generation retries and strict public export."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from src.synth.compliance import level_of
from src.task3.compliance import check, fallback
from src.task3.dataset import read_json, write_json
from src.task3.diagnosis import parse_taxonomy_diagnosis, untrusted_diagnosis_message
from src.task3.generation_audit import inspect_generation
from src.task3.inference import tokenizer_metadata
from src.task3.prompts import RETRY_HINT, ContextTooLong, budget_prompt, exemplar_feedback, retry_hint, select_exemplars
from src.task3.quality_review import quality_review_flags
from src.task3.schema import validate_taxonomy
from src.task3.strategy import (
    FINAL_PLAN_POLICY,
    QUALITY_V2_FINAL_POLICY,
    _parse_plan_json,
    budget_plan_prompt,
    plan_reserve_message,
    untrusted_plan_message,
    validate_plan_text,
    validate_strategy,
)


def load_taxonomy_predictions(path, expected_ids, *, return_audit=False, allow_unverified=False):
    data = read_json(path)
    expected_order = list(expected_ids)
    if any(not isinstance(sid, str) or not sid for sid in expected_order):
        raise ValueError("required Task2 prediction IDs must be nonempty strings")
    if len(set(expected_order)) != len(expected_order):
        raise ValueError("required Task2 prediction IDs must be unique")
    expected = set(expected_order)

    if isinstance(data, list):
        rows = {}
        for row in data:
            if not isinstance(row, dict):
                raise ValueError("taxonomy prediction item must be an object")
            sid = row.get("sample_id")
            if not isinstance(sid, str) or not sid:
                raise ValueError("taxonomy prediction item has an invalid sample_id")
            if sid in rows:
                raise ValueError("invalid or duplicate taxonomy prediction ID")
            rows[sid] = row
    elif isinstance(data, dict):
        if any(not isinstance(sid, str) or not sid for sid in data):
            raise ValueError("taxonomy prediction map contains an invalid sample_id")
        rows = data
    else:
        raise ValueError("taxonomy JSON must be keyed by sample_id or a Task2 prediction array")
    missing = expected - set(rows)
    if missing:
        raise ValueError(f"Task2 taxonomy predictions are missing {len(missing)} required sample IDs")

    projected = {}
    unknown_provenance = 0
    for sid in expected_order:
        value = rows[sid]
        if not isinstance(value, dict):
            labels = value
            parse_ok = None
        else:
            parse_ok = value.get("parse_ok") if "parse_ok" in value else None
            if parse_ok is not None and not isinstance(parse_ok, bool):
                raise ValueError(f"{sid}: invalid Task2 parse_ok metadata")
            if parse_ok is False:
                raise ValueError(f"{sid}: Task2 parsing failed; [] cannot mean predicted clean")
            output = value.get("output", value)
            if not isinstance(output, dict):
                raise ValueError(f"{sid}: Task2 prediction output must be an object")
            labels = output.get("taxonomy_error", output.get("labels"))
            if labels is None and "taxonomy_error" not in output and "labels" not in output:
                raise ValueError(f"{sid}: Task2 prediction has no taxonomy labels")
        if parse_ok is None:
            unknown_provenance += 1
            if not allow_unverified:
                raise ValueError(
                    f"{sid}: Task2 parse provenance is unknown; pass "
                    "--allow-unverified-task2-export to use a legacy label-only export"
                )
        projected[sid] = validate_taxonomy(labels)

    extras = sorted(set(rows) - expected)
    audit = {
        "required_id_count": len(expected_order),
        "ignored_extra_id_count": len(extras),
        "ignored_extra_ids_sha256": hashlib.sha256("\n".join(extras).encode()).hexdigest() if extras else None,
        "provenance_status": "provenance_unknown" if unknown_provenance else "verified",
        "provenance_unknown_required_count": unknown_provenance,
        "allow_unverified_task2_export": bool(allow_unverified),
    }
    return (projected, audit) if return_audit else projected


def taxonomy_for(record, source, predicted=None):
    if source == "gold":
        if record.source == "public" or record.gold_taxonomy is None:
            raise ValueError(
                f"{record.sample_id}: oracle mode requires supplied gold taxonomy; public gold is unavailable"
            )
        return validate_taxonomy(record.gold_taxonomy)
    if source not in {"task2-json", "self-diagnosis"} or predicted is None or record.sample_id not in predicted:
        raise ValueError(f"{record.sample_id}: missing predicted taxonomy; no empty-label fallback")
    return validate_taxonomy(predicted[record.sample_id])


def audit_prompts(records, tokenizer, config, taxonomy_source="gold", predicted=None, demo_pool=(), diagnoses=None):
    """Measure selected prompts and both CoT stages before inference."""
    strategy = validate_strategy(
        config.get("prompt_strategy", "few_shot" if config.get("few_shot_k", 0) else "zero_shot")
    )
    structured = strategy in {"structured_cot", "few_shot_structured_cot"}
    if taxonomy_source == "self-diagnosis" and diagnoses is None:
        raise ValueError("self-diagnosis requires validated diagnosis details")
    quality_version = config.get("cot_quality_version", 1)
    if isinstance(quality_version, bool) or quality_version not in {1, 2, 3, 4}:
        raise ValueError("cot_quality_version must be 1, 2, 3 or 4")
    grounded_v2 = quality_version == 2
    compact_v3 = quality_version in (3, 4)
    substantive_v4 = quality_version == 4
    if (grounded_v2 or compact_v3) and not structured:
        raise ValueError("cot_quality_version 2/3 requires a structured CoT strategy")
    level_policy = config.get("prompt_policy_version", 1)
    plan_retries = config.get("cot_plan_max_retries", 1)
    plan_reserve = config.get("cot_plan_max_new_tokens", 256)
    measurements, blocked_initial, blocked_retry, blocked_plan = [], [], [], []
    for record in records:
        try:
            taxonomy = taxonomy_for(record, taxonomy_source, predicted)
            diagnostic_context = [untrusted_diagnosis_message(diagnoses[record.sample_id]["diagnosis"])] if diagnoses else []
            demos = select_exemplars(
                demo_pool,
                record,
                config.get("few_shot_k", 0),
                forbidden=records,
                source_allowlist=config.get("few_shot_source_allowlist"),
                excluded_ids=config.get("few_shot_excluded_ids", ()),
                same_level_only=config.get("few_shot_same_level_only", False),
            )
            plan_prompts = []
            if structured:
                if not isinstance(plan_retries, int) or not 0 <= plan_retries <= 2:
                    raise ValueError("cot_plan_max_retries must be an integer from 0 to 2")
                if not isinstance(plan_reserve, int) or not 32 <= plan_reserve <= 512:
                    raise ValueError("cot_plan_max_new_tokens must be an integer from 32 to 512")
                for retry_index in range(plan_retries + 1):
                    try:
                        plan_prompts.append(
                            budget_plan_prompt(
                                record, taxonomy, tokenizer, config.get("context_limit", 4096), plan_reserve,
                                strict_retry=retry_index > 0, grounded_v2=grounded_v2, compact_v3=compact_v3, substantive_v4=substantive_v4,
                            )
                        )
                    except ContextTooLong:
                        plan_prompts.append(None)
                        if retry_index == 0:
                            blocked_plan.append(record.sample_id)
                if plan_prompts[0] is None:
                    blocked_initial.append(record.sample_id)
                    continue
                reserve = plan_reserve_message(compact_v3=compact_v3, level=level_of(record.target_feedback_level))
                additional_messages = [reserve] if reserve else []
                system_addendum = ("" if compact_v3 and level_of(record.target_feedback_level) == 1 else FINAL_PLAN_POLICY + ("\n" + QUALITY_V2_FINAL_POLICY if grounded_v2 else ""))
            else:
                additional_messages = []
                system_addendum = ""
            initial_prompt = budget_prompt(
                record,
                taxonomy,
                tokenizer,
                config.get("context_limit", 4096),
                config.get("max_new_tokens", 512),
                demos,
                additional_messages=[*additional_messages, *diagnostic_context],
                system_addendum=system_addendum,
                prompt_policy_version=level_policy,
            )
        except ContextTooLong:
            blocked_initial.append(record.sample_id)
            continue
        retry_prompt = None
        if config.get("max_retries", 2):
            try:
                retry_prompt = budget_prompt(
                    record,
                    taxonomy,
                    tokenizer,
                    config.get("context_limit", 4096),
                    config.get("max_new_tokens", 512),
                    demos,
                    strict_hint=retry_hint(["incomplete_response", "level3_direction_candidate", "specific_diagnosis"], level_of(record.target_feedback_level), config["retry_policy_version"]) if config.get("retry_policy_version") in (3, 4) else RETRY_HINT,
                    additional_messages=[*additional_messages, *diagnostic_context],
                    system_addendum=system_addendum,
                    prompt_policy_version=level_policy,
                )
            except ContextTooLong:
                blocked_retry.append(record.sample_id)
        required_prompt_tokens = max(
            initial_prompt.input_tokens,
            retry_prompt.input_tokens if retry_prompt is not None else 0,
        )
        measurements.append(
            {
                "sample_id": record.sample_id,
                "prompt_strategy": strategy,
                "input_tokens": initial_prompt.input_tokens,
                "worst_case_retry_input_tokens": retry_prompt.input_tokens if retry_prompt is not None else None,
                "required_context_tokens": required_prompt_tokens + config.get("max_new_tokens", 512),
                "completion_reserve": config.get("max_new_tokens", 512),
                "context_limit": config.get("context_limit", 4096),
                "log_budget_chars": initial_prompt.log_budget,
                "retry_log_budget_chars": retry_prompt.log_budget if retry_prompt is not None else None,
                "examples_used": initial_prompt.examples_used,
                "examples_requested": config.get("few_shot_k", 0),
                "examples_selected_before_budget": len(demos),
                "retry_examples_used": retry_prompt.examples_used if retry_prompt is not None else None,
                "cot_plan_input_tokens": [p.input_tokens if p is not None else None for p in plan_prompts],
                "cot_plan_context_limit": config.get("context_limit", 4096) if structured else None,
                "cot_plan_completion_reserve": plan_reserve if structured else None,
                "cot_plan_retry_blocked": bool(structured and len(plan_prompts) > 1 and plan_prompts[1] is None),
                "stage2_plan_reserve_chars": len(reserve["content"]) if structured and reserve else 0,
            }
        )
    counts = sorted(item["input_tokens"] for item in measurements)

    def percentile(values, fraction):
        if not values:
            return None
        return values[max(0, math.ceil(fraction * len(values)) - 1)]

    status = (
        "blocked"
        if blocked_initial
        else "passed_with_retry_fallback"
        if blocked_retry
        else "passed"
    )
    return {
        "status": status,
        "n_samples": len(records),
        "n_measured": len(measurements),
        "blocked_count": len(blocked_initial),
        "blocked_ids": blocked_initial,
        "blocked_initial_count": len(blocked_initial),
        "blocked_initial_ids": blocked_initial,
        "retry_context_blocked_count": len(blocked_retry),
        "retry_context_blocked_ids": blocked_retry,
        "plan_context_blocked_count": len(blocked_plan),
        "plan_context_blocked_ids": blocked_plan,
        "prompt_strategy": strategy,
        "input_token_percentiles": {
            "p50": percentile(counts, 0.50),
            "p90": percentile(counts, 0.90),
            "p95": percentile(counts, 0.95),
            "max": max(counts, default=None),
        },
        "completion_reserve": config.get("max_new_tokens", 512),
        "retry_hint_reserved": bool(config.get("max_retries", 2)),
        "retry_hint_policy": ("violation_specific_v2" if config.get("retry_policy_version", 1) == 2 else RETRY_HINT) if config.get("max_retries", 2) else None,
        "measurement_kind": (
            "TEST ONLY — byte mock, not official feasibility"
            if getattr(tokenizer, "_task3_test_only_mock", False) or tokenizer.__class__.__name__ == "MockTokenizer"
            else "tokenizer measured"
        ),
        "log_budget_chars": dict(
            (str(value), sum(item["log_budget_chars"] == value for item in measurements))
            for value in sorted({item["log_budget_chars"] for item in measurements})
        ),
        "tokenizer": tokenizer.__class__.__name__,
        "measurements": measurements,
    }


def _adapter_hash(config):
    adapter = config.get("adapter")
    if not adapter:
        return None
    if adapter:
        adapter_path = Path(adapter)
        if adapter_path.is_file():
            return hashlib.sha256(adapter_path.read_bytes()).hexdigest()
        elif adapter_path.is_dir():
            digest = hashlib.sha256()
            for path in sorted(adapter_path.rglob("*")):
                if path.is_file():
                    digest.update(path.relative_to(adapter_path).as_posix().encode())
                    digest.update(hashlib.sha256(path.read_bytes()).digest())
            return digest.hexdigest()
        raise FileNotFoundError(f"adapter path does not exist: {adapter_path}")


def implementation_digest():
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _prompt_digest(prompt, tokenizer_identity, config):
    payload = {
        "messages": prompt.messages,
        "tokenizer": tokenizer_identity,
        "retry_policy": {
            "hint": RETRY_HINT if config.get("max_retries", 2) else None,
            "max_retries": config.get("max_retries", 2),
            "context_limit": config.get("context_limit", 4096),
            "max_new_tokens": config.get("max_new_tokens", 512),
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _cache_key(record, taxonomy, config, adapter_hash, cache_context, prompt_digest, tokenizer_identity):
    payload = {
        "model_id": config.get("model_id"),
        "revision": config.get("revision"),
        "adapter_sha256": adapter_hash,
        "tokenizer": tokenizer_identity,
        "prompt_sha256": prompt_digest,
        "config": {k: v for k, v in config.items() if k not in {"output_dir", "adapter"}},
        "taxonomy": taxonomy,
        "sample_id": record.sample_id,
        "input_sha256": hashlib.sha256(
            json.dumps(
                [
                    record.statement,
                    record.grading_policy,
                    record.problems,
                    record.code,
                    record.compile_log,
                    record.test_report,
                    record.target_feedback_level,
                    record.level_definitions,
                ],
                ensure_ascii=False,
            ).encode()
        ).hexdigest(),
        "cache_context": cache_context,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _read_progress(path, records):
    cached, seen = {}, set()
    if not path.exists():
        return cached, {"ignored_partial_final_line": False}
    expected = {r.sample_id for r in records}
    ignored_partial = False
    with path.open(encoding="utf-8") as stream:
        lines = stream.readlines()
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError
                prediction, trace = row.get("prediction"), row.get("trace")
                if not isinstance(prediction, dict) or not isinstance(trace, dict):
                    raise ValueError
                sid = prediction.get("sample_id")
                if sid not in expected or sid in seen or trace.get("sample_id") != sid:
                    raise ValueError
                validate_predictions([prediction], [sid])
                guard = trace.get("final_guard")
                attempts = trace.get("attempts")
                plan_fallback = (
                    trace.get("fallback") is True
                    and isinstance(trace.get("cot_plan_audit"), dict)
                    and trace["cot_plan_audit"].get("status")
                    in {"parse_failed", "generation_failed", "stage2_context_blocked"}
                )
                feedback_failure = (
                    trace.get("fallback") is True
                    and trace.get("fallback_reason") == "feedback_generation_failed"
                    and isinstance(attempts, list)
                    and all(isinstance(a, dict) for a in attempts)
                    and any(a.get("failure_type") and a.get("model_generated") is False for a in attempts or [])
                )
                if (
                    row.get("status") != "complete"
                    or not isinstance(row.get("cache_key"), str)
                    or len(row["cache_key"]) != 64
                    or trace.get("completed") is not True
                    or not isinstance(trace.get("prompt_sha256"), str)
                    or len(trace["prompt_sha256"]) != 64
                    or not isinstance(attempts, list)
                    or not attempts
                    or not all(isinstance(attempt, dict) for attempt in attempts)
                    or (not any(attempt.get("model_generated") is True for attempt in attempts) and not plan_fallback and not feedback_failure)
                    or not isinstance(guard, dict)
                    or guard.get("ok") is not True
                    or not isinstance(trace.get("fallback"), bool)
                ):
                    raise ValueError
                seen.add(sid)
                cached[sid] = row
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                if line_number == len(lines) and not line.endswith("\n"):
                    ignored_partial = True
                    break
                raise ValueError(f"invalid inference progress record at line {line_number}") from exc
    return cached, {"ignored_partial_final_line": ignored_partial}


def _write_progress_snapshot(path, retained, records):
    fd, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            for record in records:
                if record.sample_id in retained:
                    stream.write(json.dumps(retained[record.sample_id], ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise


def _append_progress(path, row):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _generate_structured_plan(record, backend, config, plan_prompts, *, grounded_v2=False, compact_v3=False, attempt_sink=None):
    """Run bounded planning calls and retain raw attempts for private review."""
    attempt_rows = []
    def retain(row):
        row.update(sample_id=record.sample_id, split=record.split, method=config.get("experiment_id"), stage="structured_plan", feedback_examples_requested=config.get("few_shot_k", 0), examples_requested=0, examples_selected_before_budget=0, effective_k=0, effective_exemplar_ids=[])
        if config.get("guard_policy_version", 1) >= 2 and row.get("attempt_index"):
            plan_prompt = plan_prompts[row["attempt_index"] - 1]
            row["prompt_messages"] = plan_prompt.messages if plan_prompt is not None else None
        attempt_rows.append(row)
        if attempt_sink is not None:
            attempt_sink("structured_plan", row)

    plan = None
    for attempt_index, prompt in enumerate(plan_prompts, 1):
        if prompt is None:
            retain({"attempt_index": attempt_index, "status": "context_blocked", "error_type": "ContextTooLong"})
            continue
        stage_config = {**config, "do_sample": False, "max_new_tokens": config.get("cot_plan_max_new_tokens", 256)}
        started = time.perf_counter()
        try:
            generated = backend.generate(prompt.messages, stage_config)
        except (RuntimeError, ValueError, OSError) as exc:
            retain({
                "attempt_index": attempt_index,
                "status": "generation_failed",
                "error_type": type(exc).__name__,
                "input_tokens": prompt.input_tokens,
                "output_tokens": 0,
                "latency_s": time.perf_counter() - started,
                "raw_text": None,
                "text_available": False,
                "error_message": str(exc)[:500],
            })
            continue
        try:
            plan = validate_plan_text(generated.text, record, grounded_v2=grounded_v2, compact_v3=compact_v3)
        except ValueError as exc:
            message = str(exc)
            try:
                _parse_plan_json(generated.text)
                json_valid = True
            except (ValueError, TypeError):
                json_valid = False
            if "JSON" in message or "character bound" in message:
                category = "json_parse_or_text_invalid"
            elif "source_span" in message or "function_name" in message or "quote" in message:
                category = "source_grounding_failed"
            elif "problem ID" in message:
                category = "problem_linkage_failed"
            elif "CJK" in message:
                category = "language_validation_failed"
            else:
                category = "schema_validation_failed"
            retain({
                "attempt_index": attempt_index,
                "status": "validation_failed",
                "failure_category": category,
                "validation_reason": message,
                "error_type": "ValueError",
                "input_tokens": prompt.input_tokens,
                "output_tokens": generated.output_tokens,
                "latency_s": generated.latency_s,
                "raw_text": generated.text,
                "text_available": True,
                "generation_audit": inspect_generation(generated.text, output_tokens=generated.output_tokens, max_new_tokens=stage_config["max_new_tokens"], finish_reason=generated.finish_reason, eos_reached=generated.eos_reached),
                "json_valid": json_valid,
                "quote_valid": False if category == "source_grounding_failed" or "quote" in message else None,
                "semantic_support": "not_verified",
            })
            continue
        retain({
            "attempt_index": attempt_index,
            "status": "validated",
            "input_tokens": prompt.input_tokens,
            "output_tokens": generated.output_tokens,
            "latency_s": generated.latency_s,
            "raw_text": generated.text,
            "text_available": True,
            "json_valid": True,
            "quote_valid": True if (grounded_v2 or compact_v3) else None,
            "semantic_support": "not_verified",
            "finding_count": len(plan.get("findings", plan.get("problem_findings", []))),
            "plan_submission_status": plan.get("status", plan.get("submission_status")),
            "generation_audit": inspect_generation(generated.text, output_tokens=generated.output_tokens, max_new_tokens=stage_config["max_new_tokens"], finish_reason=generated.finish_reason, eos_reached=generated.eos_reached),
        })
        break
    plan_output_tokens = sum(int(row.get("output_tokens", 0)) for row in attempt_rows)
    plan_latency_s = sum(float(row.get("latency_s", 0.0)) for row in attempt_rows)
    plan_input_tokens = sum(int(row.get("input_tokens", 0)) for row in attempt_rows)
    statuses = {row["status"] for row in attempt_rows}
    if plan is not None:
        status = "validated"
    elif "context_blocked" in statuses and statuses <= {"context_blocked"}:
        status = "context_blocked"
    elif "generation_failed" in statuses:
        status = "generation_failed"
    else:
        status = "parse_failed"
    return plan, {
        "status": status,
        "attempts": attempt_rows,
        "attempt_count": len(attempt_rows),
        "retry_count": max(0, len(attempt_rows) - 1),
        "input_tokens_total": plan_input_tokens,
        "output_tokens_total": plan_output_tokens,
        "latency_s_total": plan_latency_s,
        "validated_plan": plan,
        "finding_count": len(plan.get("findings", plan.get("problem_findings", []))) if plan is not None else None,
        "plan_submission_status": plan.get("status", plan.get("submission_status")) if plan is not None else None,
        "plan_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest() if plan is not None else None,
        "raw_invalid_plan_text": [row["raw_text"] for row in attempt_rows if row.get("status") == "validation_failed"],
    }


def infer(
    records,
    backend,
    config,
    taxonomy_source="gold",
    predicted=None,
    demo_pool=(),
    *,
    progress_path=None,
    resume=False,
    cache_context=None,
    attempt_journal_path=None,
    diagnoses=None,
):
    outputs, traces = [], []
    guard_policy = config.get("guard_policy_version", 1)
    completion_policy = config.get("completion_policy_version", 0)
    adequacy_policy = config.get("adequacy_retry_policy_version", 0)
    if isinstance(guard_policy, bool) or guard_policy not in (1, 2, 3):
        raise ValueError("guard_policy_version must be 1, 2 or 3")
    if any(isinstance(v, bool) or v not in (0, 1) for v in (completion_policy, adequacy_policy)):
        raise ValueError("completion/adequacy policies must be 0 or 1")
    if guard_policy >= 2:
        config = {**config, "runtime_implementation_sha256": implementation_digest()}
    if not isinstance(config.get("max_retries", 2), int) or not 0 <= config.get("max_retries", 2) <= 5:
        raise ValueError("max_retries must be an integer from 0 to 5")
    strategy = validate_strategy(
        config.get("prompt_strategy", "few_shot" if config.get("few_shot_k", 0) else "zero_shot")
    )
    structured = strategy in {"structured_cot", "few_shot_structured_cot"}
    if taxonomy_source == "self-diagnosis" and diagnoses is None:
        raise ValueError("self-diagnosis requires validated diagnosis details")
    if diagnoses is not None:
        if set(diagnoses) != {record.sample_id for record in records}:
            raise ValueError("taxonomy diagnosis details must exactly cover inference IDs")
        for record in records:
            detail = diagnoses[record.sample_id]
            if not isinstance(detail, dict) or not isinstance(detail.get("diagnosis"), dict):
                raise ValueError(f"{record.sample_id}: missing validated self-diagnosis details")
            parsed = parse_taxonomy_diagnosis(json.dumps(detail["diagnosis"], ensure_ascii=False), record)
            if taxonomy_source == "self-diagnosis" and parsed["taxonomy_error"] != taxonomy_for(record, taxonomy_source, predicted):
                raise ValueError(f"{record.sample_id}: diagnosis and predicted taxonomy disagree")
    quality_version = config.get("cot_quality_version", 1)
    if isinstance(quality_version, bool) or quality_version not in {1, 2, 3, 4}:
        raise ValueError("cot_quality_version must be 1, 2, 3 or 4")
    grounded_v2 = quality_version == 2
    compact_v3 = quality_version in (3, 4)
    substantive_v4 = quality_version == 4
    if (grounded_v2 or compact_v3) and not structured:
        raise ValueError("cot_quality_version 2/3 requires a structured CoT strategy")
    level_policy = config.get("prompt_policy_version", 1)
    plan_retries = config.get("cot_plan_max_retries", 1)
    plan_reserve = config.get("cot_plan_max_new_tokens", 256)
    if structured and (not isinstance(plan_retries, int) or not 0 <= plan_retries <= 2):
        raise ValueError("cot_plan_max_retries must be an integer from 0 to 2")
    if structured and (not isinstance(plan_reserve, int) or not 32 <= plan_reserve <= 512):
        raise ValueError("cot_plan_max_new_tokens must be an integer from 32 to 512")
    # Validate the entire taxonomy input before running any generation.
    for record in records:
        taxonomy_for(record, taxonomy_source, predicted)
    if len({record.sample_id for record in records}) != len(records):
        raise ValueError("inference records must have unique sample IDs")
    progress = Path(progress_path) if progress_path else None
    journal = Path(attempt_journal_path) if attempt_journal_path else None
    if journal:
        journal.parent.mkdir(parents=True, exist_ok=True)
    cached, progress_audit = (
        _read_progress(progress, records)
        if progress and resume
        else ({}, {"ignored_partial_final_line": False})
    )
    adapter_hash = _adapter_hash(config)
    tokenizer_identity = tokenizer_metadata(backend.tokenizer)
    prepared = {}
    for record in records:
        taxonomy = taxonomy_for(record, taxonomy_source, predicted)
        diagnostic_context = [untrusted_diagnosis_message(diagnoses[record.sample_id]["diagnosis"])] if diagnoses else []
        demos = select_exemplars(
            demo_pool,
            record,
            config.get("few_shot_k", 0),
            forbidden=records,
            source_allowlist=config.get("few_shot_source_allowlist"),
            excluded_ids=config.get("few_shot_excluded_ids", ()),
            same_level_only=config.get("few_shot_same_level_only", False),
        )
        plan_prompts = []
        if structured:
            for retry_index in range(plan_retries + 1):
                try:
                    plan_prompts.append(
                        budget_plan_prompt(
                            record, taxonomy, backend.tokenizer, config.get("context_limit", 4096), plan_reserve,
                            strict_retry=retry_index > 0, grounded_v2=grounded_v2, compact_v3=compact_v3, substantive_v4=substantive_v4,
                        )
                    )
                except ContextTooLong:
                    plan_prompts.append(None)
            reserve = plan_reserve_message(compact_v3=compact_v3, level=level_of(record.target_feedback_level))
            additional_messages = [reserve] if reserve else []
            system_addendum = ("" if compact_v3 and level_of(record.target_feedback_level) == 1 else FINAL_PLAN_POLICY + ("\n" + QUALITY_V2_FINAL_POLICY if grounded_v2 else ""))
        else:
            additional_messages = []
            system_addendum = ""
        additional_messages.extend(diagnostic_context)
        prompt = budget_prompt(
            record,
            taxonomy,
            backend.tokenizer,
            config.get("context_limit", 4096),
            config.get("max_new_tokens", 512),
            demos,
            additional_messages=additional_messages,
            system_addendum=system_addendum,
            prompt_policy_version=level_policy,
        )
        stage2_digest = _prompt_digest(prompt, tokenizer_identity, config)
        if structured:
            plan_digests = [
                hashlib.sha256(json.dumps(item.messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                for item in plan_prompts if item is not None
            ]
            prompt_digest = hashlib.sha256(
                json.dumps(
                    {"strategy": strategy, "stage1_prompt_hashes": plan_digests, "stage2_template_hash": stage2_digest},
                    sort_keys=True,
                ).encode()
            ).hexdigest()
        else:
            prompt_digest = stage2_digest
        cache_key = _cache_key(
            record,
            taxonomy,
            config,
            adapter_hash,
            cache_context,
            prompt_digest,
            tokenizer_identity,
        )
        prepared[record.sample_id] = {
            "taxonomy": taxonomy,
            "demos": demos,
            "prompt": prompt,
            "prompt_digest": prompt_digest,
            "cache_key": cache_key,
            "plan_prompts": plan_prompts,
            "additional_messages": additional_messages,
            "system_addendum": system_addendum,
        }
    if progress:
        progress.parent.mkdir(parents=True, exist_ok=True)
        retained = {}
        if resume:
            for record in records:
                previous = cached.get(record.sample_id)
                if previous and previous["cache_key"] == prepared[record.sample_id]["cache_key"]:
                    retained[record.sample_id] = previous
        if progress_audit["ignored_partial_final_line"]:
            for sid, previous in retained.items():
                retained[sid] = {
                    **previous,
                    "trace": {
                        **previous["trace"],
                        "progress_recovery": progress_audit,
                    },
                }
        _write_progress_snapshot(progress, retained, records)
        cached = retained
    for record in records:
        item = prepared[record.sample_id]
        taxonomy = item["taxonomy"]
        demos = item["demos"]
        prompt = item["prompt"]
        cache_prompt_digest = item["prompt_digest"]
        key = item["cache_key"]
        previous = cached.get(record.sample_id)
        if previous and previous["cache_key"] == key:
            outputs.append(previous["prediction"])
            trace = dict(previous["trace"])
            if progress_audit["ignored_partial_final_line"]:
                trace["progress_recovery"] = progress_audit
            traces.append(trace)
            continue
        attempts, feedback_latency, feedback_tokens, feedback_calls = [], 0.0, 0, 0
        feedback_input_tokens = 0
        result, generated = None, None
        retry_context_blocked = False
        feedback_generation_failed = False
        plan_failure = False
        cot_plan_audit = None
        retry_reasons = []
        completion_incomplete = False
        generation_audit = {}
        quality_flags = {}
        active_retry_instruction = None
        def attempt_sink(stage, row):
            if journal:
                _append_progress(journal, {"sample_id": record.sample_id, "cache_key": key, "stage": stage, "attempt": row})

        def retain_feedback(row):
            row.update(sample_id=record.sample_id, split=record.split, method=config.get("experiment_id"), attempt_index=len(attempts) + 1, examples_requested=config.get("few_shot_k", 0), examples_selected_before_budget=len(demos), effective_k=len(row.get("effective_exemplar_ids", [])))
            if level_policy in (4, 5, 6):
                row["retry_instruction"] = active_retry_instruction
                presentation_policy = 3 if level_policy in (5, 6) and level_of(record.target_feedback_level) != 1 else level_policy
                row["effective_exemplars"] = [exemplar_feedback(d, prompt_policy_version=presentation_policy) for d in demos[:row["effective_k"]]]
                if level_policy in (5, 6):
                    row["prompt_policy_version"] = level_policy
            if guard_policy >= 2:
                row["prompt_messages"] = prompt.messages if not plan_failure else None
            attempts.append(row)
            attempt_sink("final_feedback", row)

        if structured:
            plan, cot_plan_audit = _generate_structured_plan(
                record, backend, config, item["plan_prompts"], grounded_v2=grounded_v2, compact_v3=compact_v3, attempt_sink=attempt_sink
            )
            if plan is None:
                plan_failure = True
                retain_feedback(
                    {
                        "stage": "structured_plan",
                        "violations": ["structured_plan_invalid"],
                        "model_generated": False,
                        "severe": False,
                        "heuristic_compliance": None,
                    }
                )
            else:
                try:
                    prompt = budget_prompt(
                        record,
                        taxonomy,
                        backend.tokenizer,
                        config.get("context_limit", 4096),
                        config.get("max_new_tokens", 512),
                        demos,
                        additional_messages=[] if compact_v3 and level_of(record.target_feedback_level) == 1 else [untrusted_plan_message(plan, compact_v3=compact_v3)],
                        system_addendum=item["system_addendum"],
                        prompt_policy_version=level_policy,
                    )
                except ContextTooLong:
                    plan_failure = True
                    cot_plan_audit["status"] = "stage2_context_blocked"
                    retain_feedback(
                        {
                            "stage": "final_feedback",
                            "violations": ["structured_stage2_context_too_long"],
                            "model_generated": False,
                            "severe": False,
                            "heuristic_compliance": None,
                        }
                    )
        for retry in range(0 if plan_failure else config.get("max_retries", 2) + 1):
            if retry:
                active_retry_instruction = retry_hint(retry_reasons, level_of(record.target_feedback_level), config.get("retry_policy_version", 1))
                try:
                    prompt = budget_prompt(
                        record,
                        taxonomy,
                        backend.tokenizer,
                        config.get("context_limit", 4096),
                        config.get("max_new_tokens", 512),
                        demos,
                        strict_hint=active_retry_instruction,
                        additional_messages=([] if compact_v3 and level_of(record.target_feedback_level) == 1 else [untrusted_plan_message(cot_plan_audit["validated_plan"], compact_v3=compact_v3)]) if structured else (),
                        system_addendum=item["system_addendum"],
                        prompt_policy_version=level_policy,
                    )
                except ContextTooLong:
                    retry_context_blocked = True
                    retain_feedback(
                        {
                            "stage": "final_feedback",
                            "violations": ["retry_context_too_long"],
                            "model_generated": False,
                            "severe": False,
                            "heuristic_compliance": None,
                        }
                    )
                    break
            feedback_calls += 1
            feedback_input_tokens += prompt.input_tokens
            call_started = time.perf_counter()
            try:
                generated = backend.generate(prompt.messages, config)
            except (RuntimeError, ValueError) as exc:
                failed_latency = time.perf_counter() - call_started
                feedback_latency += failed_latency
                retain_feedback({
                    "stage": "final_feedback", "violations": ["feedback_generation_failed"],
                    "model_generated": False, "severe": False, "heuristic_compliance": None,
                    "failure_type": type(exc).__name__,
                    "latency_s": failed_latency,
                    "input_tokens": prompt.input_tokens,
                    "output_tokens": 0,
                    "raw_text": None,
                    "text_available": False,
                    "error_message": str(exc)[:500],
                    "effective_exemplar_ids": [d.sample_id for d in demos[:prompt.examples_used]],
                })
                feedback_generation_failed = True
                break
            result = check(generated.text, record.target_feedback_level, version=guard_policy)
            generation_audit = inspect_generation(generated.text, output_tokens=generated.output_tokens, max_new_tokens=config.get("max_new_tokens", 512), finish_reason=generated.finish_reason, eos_reached=generated.eos_reached)
            completion_incomplete = bool(completion_policy and not generation_audit["mechanically_complete"])
            quality_flags = quality_review_flags(record, generated.text, version=3 if guard_policy == 3 else 2 if guard_policy == 2 else 1)
            retry_reasons = list(result.violations)
            if completion_incomplete:
                retry_reasons.append("incomplete_response")
            if adequacy_policy and result.ok and set(quality_flags["flags"]) & {
                "LEVEL3_ACTIONABILITY_REVIEW_CANDIDATE",
                "LEVEL3_DIAGNOSIS_REVIEW_CANDIDATE",
                "LEVEL3_DIRECTION_REVIEW_CANDIDATE",
            }:
                retry_reasons.append("level3_direction_candidate")
            if config.get("retry_policy_version") == 4 and guard_policy == 3 and "LEVEL1_PRAISE_EVIDENCE_REVIEW_CANDIDATE" in quality_flags["flags"]:
                retry_reasons.append("level1_praise_review_candidate")
            retain_feedback(
                {
                    "stage": "final_feedback",
                    "violations": list(result.violations),
                    "model_generated": True,
                    "severe": result.severe,
                    "heuristic_compliance": result.heuristic_compliance,
                    "raw_text": generated.text,
                    "text_available": True,
                    "output_tokens": generated.output_tokens,
                    "latency_s": generated.latency_s,
                    "input_tokens": prompt.input_tokens,
                    "effective_exemplar_ids": [d.sample_id for d in demos[:prompt.examples_used]],
                    "generation_audit": generation_audit,
                    "quality_review_candidates": quality_flags,
                    "retry_reasons": retry_reasons,
                    "mechanically_complete": generation_audit["mechanically_complete"],
                }
            )
            feedback_latency += generated.latency_s
            feedback_tokens += generated.output_tokens
            if result.ok and not retry_reasons:
                break
        adequacy_retry_exhausted = bool(adequacy_policy and "level3_direction_candidate" in retry_reasons)
        used_fallback = plan_failure or retry_context_blocked or result is None or not result.ok or feedback_generation_failed or completion_incomplete or adequacy_retry_exhausted
        feedback = fallback(record.target_feedback_level) if used_fallback else generated.text.strip()
        final = check(feedback, record.target_feedback_level, version=guard_policy)
        if not final.ok and not used_fallback:
            raise RuntimeError("internal fallback failed guard")
        prediction = {"sample_id": record.sample_id, "output": {"taxonomy_error": taxonomy, "feedback": feedback}}
        plan_tokens = cot_plan_audit["output_tokens_total"] if cot_plan_audit else 0
        plan_latency = cot_plan_audit["latency_s_total"] if cot_plan_audit else 0.0
        plan_input_tokens = cot_plan_audit["input_tokens_total"] if cot_plan_audit else 0
        first_feedback_attempt = next((attempt for attempt in attempts if attempt.get("model_generated")), None)
        if plan_failure:
            fallback_reason = "structured_stage2_context_too_long" if cot_plan_audit["status"] == "stage2_context_blocked" else "structured_plan_invalid"
        elif retry_context_blocked:
            fallback_reason = "retry_context_too_long"
        elif feedback_generation_failed:
            fallback_reason = "feedback_generation_failed"
        elif completion_incomplete:
            fallback_reason = "feedback_incomplete"
        elif adequacy_retry_exhausted:
            fallback_reason = "level3_adequacy_retries_exhausted"
        elif used_fallback:
            fallback_reason = "guard_retries_exhausted"
        else:
            fallback_reason = None
        if used_fallback and record.target_feedback_level == "Level 3 - Gợi ý sửa":
            raise RuntimeError(
                f"{record.sample_id}: Level 3 failed diagnosis/direction review; refusing generic fallback ({fallback_reason})"
            )
        trace_prompt_digest = _prompt_digest(prompt, tokenizer_identity, config) if not plan_failure else cache_prompt_digest
        trace = {
            "sample_id": record.sample_id,
            "taxonomy_source": taxonomy_source,
            "taxonomy_error": taxonomy,
            "level": result.level if result is not None else level_of(record.target_feedback_level),
            "prompt_strategy": strategy,
            "attempts": attempts,
            "raw_first_attempt_compliance": first_feedback_attempt.get("heuristic_compliance") if first_feedback_attempt else None,
            "raw_first_attempt_severe_solution_leak": first_feedback_attempt.get("severe") if first_feedback_attempt else None,
            "heuristic_compliance": final.heuristic_compliance,
            "semantic_compliance": final.semantic_compliance,
            "severe_solution_leak": final.severe,
            "diagnosis_quality_status": "unknown_or_inadequate_fallback" if used_fallback else "not_measured",
            "fallback": used_fallback,
            "fallback_used": used_fallback,
            "fallback_reason": fallback_reason,
            "guard_policy_version": guard_policy,
            "completion_policy_version": completion_policy,
            "adequacy_retry_policy_version": adequacy_policy,
            "runtime_implementation_sha256": config.get("runtime_implementation_sha256"),
            "model_response_complete": bool(not used_fallback and generation_audit.get("mechanically_complete", False)),
            "completion_retry_rescued": bool(first_feedback_attempt and not first_feedback_attempt.get("mechanically_complete", True) and not used_fallback and generation_audit.get("mechanically_complete")),
            "adequacy_retry_rescued": bool(first_feedback_attempt and "level3_direction_candidate" in first_feedback_attempt.get("retry_reasons", []) and not used_fallback and "LEVEL3_ACTIONABILITY_REVIEW_CANDIDATE" not in quality_flags.get("flags", [])),
            "quality_review_candidates": quality_review_flags(record, feedback, fallback_used=used_fallback, version=3 if guard_policy == 3 else 2 if guard_policy == 2 else 1),
            "semantic_quality": "NOT_MEASURED",
            "final_guard": asdict(final),
            "input_tokens": prompt.input_tokens,
            "input_tokens_total": plan_input_tokens + feedback_input_tokens,
            "output_tokens": plan_tokens + feedback_tokens,
            "feedback_output_tokens": feedback_tokens,
            "cot_plan_output_tokens": plan_tokens,
            "latency_s": plan_latency + feedback_latency,
            "feedback_latency_s": feedback_latency,
            "cot_plan_latency_s": plan_latency,
            "retry_count": (cot_plan_audit["retry_count"] if cot_plan_audit else 0) + max(0, feedback_calls - 1),
            "feedback_retry_count": max(0, feedback_calls - 1),
            "generation_attempt_count": (cot_plan_audit["attempt_count"] if cot_plan_audit else 0) + feedback_calls,
            "feedback_generation_attempt_count": feedback_calls,
            "feedback_generation_failure_count": sum(a.get("failure_type") is not None for a in attempts),
            "cot_plan_audit": cot_plan_audit,
            "retry_context_blocked": retry_context_blocked,
            "prompt_sha256": trace_prompt_digest,
            "completed": True,
            "examples_used": prompt.examples_used,
            "examples_requested": config.get("few_shot_k", 0),
            "examples_selected_before_budget": len(demos),
            "selected_exemplars": [{"sample_id": d.sample_id, "source": d.source, "split": d.split} for d in demos],
            "prompt_policy_version": level_policy,
            "retry_policy_version": config.get("retry_policy_version", 1),
            "fallback_policy_version": 2 if completion_policy else 1,
            "fallback_text_policy_version": 1,
            "log_budget": prompt.log_budget,
        }
        if diagnoses is not None:
            trace["taxonomy_diagnosis_audit"] = diagnoses[record.sample_id]
            trace["taxonomy_diagnosis_status"] = diagnoses[record.sample_id].get("status", "unknown")
            trace["taxonomy_diagnosis_failure_reason"] = diagnoses[record.sample_id].get("failure_reason")
        if progress_audit["ignored_partial_final_line"]:
            trace["progress_recovery"] = progress_audit
        outputs.append(prediction)
        if level_policy == 4:
            first_praise_candidate = bool(first_feedback_attempt and "level1_praise_review_candidate" in first_feedback_attempt.get("retry_reasons", []))
            final_praise_candidate = "LEVEL1_PRAISE_EVIDENCE_REVIEW_CANDIDATE" in quality_flags.get("flags", [])
            trace.update(
                level1_praise_candidate_cleared_after_retry=bool(first_praise_candidate and not used_fallback and not final_praise_candidate),
                level1_praise_candidate_persisted=bool(not used_fallback and final_praise_candidate),
                candidate_policy_note="Warning-only; no semantic failure assigned; fallback v2 and text v1 unchanged",
            )
        traces.append(trace)
        if progress:
            _append_progress(
                progress,
                {"status": "complete", "cache_key": key, "prediction": prediction, "trace": trace},
            )
    return outputs, traces


def validate_predictions(predictions, expected_ids):
    if not isinstance(predictions, list) or len(predictions) != len(expected_ids):
        raise ValueError("predictions must have exactly one item per input")
    ids = []
    for row in predictions:
        if not isinstance(row, dict) or set(row) != {"sample_id", "output"}:
            raise ValueError("invalid prediction item schema")
        if not isinstance(row["sample_id"], str):
            raise ValueError("sample_id must be a string")
        ids.append(row["sample_id"])
        o = row["output"]
        if not isinstance(o, dict) or set(o) != {"taxonomy_error", "feedback"}:
            raise ValueError("output requires exactly taxonomy_error and feedback")
        validate_taxonomy(o["taxonomy_error"])
        if not isinstance(o["feedback"], str) or not o["feedback"].strip():
            raise ValueError("feedback must be nonempty text")
    if ids != list(expected_ids) or len(set(ids)) != len(ids):
        raise ValueError("prediction order/IDs must exactly match original input")
    return True


def export_predictions(path, predictions, records, mock=False):
    validate_predictions(predictions, [r.sample_id for r in records])
    path = Path(path)
    if mock and "mock" not in path.stem.lower():
        raise ValueError("TEST-ONLY mock output filename must contain 'mock'; never submit it")
    write_json(path, predictions)
