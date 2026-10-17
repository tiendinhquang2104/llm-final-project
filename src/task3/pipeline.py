"""Taxonomy routing, bounded generation retries and strict public export."""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict
from pathlib import Path

from src.task3.compliance import check, fallback
from src.task3.dataset import read_json, write_json
from src.task3.prompts import ContextTooLong, budget_prompt, select_exemplars
from src.task3.schema import validate_taxonomy


def load_taxonomy_predictions(path, expected_ids, *, return_audit=False):
    data = read_json(path)
    result = {}
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                raise ValueError("taxonomy prediction item must be an object")
            sid = row.get("sample_id")
            if not isinstance(sid, str) or sid in result:
                raise ValueError("invalid or duplicate taxonomy prediction ID")
            # Official Task2 export and internal Task2 pipeline format supported.
            if row.get("parse_ok") is False:
                raise ValueError(f"{sid}: Task2 parsing failed; [] cannot mean predicted clean")
            output = row.get("output", row)
            if not isinstance(output, dict):
                raise ValueError("taxonomy prediction output must be an object")
            result[sid] = validate_taxonomy(output.get("taxonomy_error", output.get("labels")))
    elif isinstance(data, dict):
        for sid, value in data.items():
            if isinstance(value, dict) and value.get("parse_ok") is False:
                raise ValueError(f"{sid}: Task2 parsing failed")
            if isinstance(value, dict):
                value = value.get("output", value)
                if not isinstance(value, dict):
                    raise ValueError("taxonomy prediction output must be an object")
                value = value.get("taxonomy_error", value.get("labels"))
            result[sid] = validate_taxonomy(value)
    else:
        raise ValueError("taxonomy JSON must be keyed by sample_id or a Task2 prediction array")
    missing = set(expected_ids) - set(result)
    if missing:
        raise ValueError(f"Task2 taxonomy predictions are missing {len(missing)} required sample IDs")
    extras = sorted(set(result) - set(expected_ids))
    audit = {
        "required_id_count": len(expected_ids),
        "ignored_extra_id_count": len(extras),
        "ignored_extra_ids_sha256": hashlib.sha256("\n".join(extras).encode()).hexdigest() if extras else None,
    }
    projected = {sid: result[sid] for sid in expected_ids}
    return (projected, audit) if return_audit else projected


def taxonomy_for(record, source, predicted=None):
    if source == "gold":
        if record.source == "public" or record.gold_taxonomy is None:
            raise ValueError(
                f"{record.sample_id}: oracle mode requires supplied gold taxonomy; public gold is unavailable"
            )
        return validate_taxonomy(record.gold_taxonomy)
    if source != "task2-json" or predicted is None or record.sample_id not in predicted:
        raise ValueError(f"{record.sample_id}: missing Task2 taxonomy predictions; no empty-label fallback")
    return validate_taxonomy(predicted[record.sample_id])


def audit_prompts(records, tokenizer, config, taxonomy_source="gold", predicted=None, demo_pool=()):
    """Measure every selected prompt before inference; never crop essential fields."""
    measurements, blocked = [], []
    for record in records:
        try:
            taxonomy = taxonomy_for(record, taxonomy_source, predicted)
            demos = select_exemplars(demo_pool, record, config.get("few_shot_k", 0), forbidden=records)
            prompt = budget_prompt(
                record,
                taxonomy,
                tokenizer,
                config.get("context_limit", 4096),
                config.get("max_new_tokens", 512),
                demos,
            )
            measurements.append(
                {
                    "sample_id": record.sample_id,
                    "input_tokens": prompt.input_tokens,
                    "completion_reserve": config.get("max_new_tokens", 512),
                    "context_limit": config.get("context_limit", 4096),
                    "log_budget_chars": prompt.log_budget,
                    "examples_used": prompt.examples_used,
                }
            )
        except ContextTooLong:
            blocked.append(record.sample_id)
    counts = sorted(item["input_tokens"] for item in measurements)

    def percentile(values, fraction):
        if not values:
            return None
        return values[max(0, math.ceil(fraction * len(values)) - 1)]

    return {
        "status": "blocked" if blocked else "passed",
        "n_samples": len(records),
        "n_measured": len(measurements),
        "blocked_count": len(blocked),
        "blocked_ids": blocked,
        "input_token_percentiles": {
            "p50": percentile(counts, 0.50),
            "p90": percentile(counts, 0.90),
            "p95": percentile(counts, 0.95),
            "max": max(counts, default=None),
        },
        "completion_reserve": config.get("max_new_tokens", 512),
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


def _cache_key(record, taxonomy, config, adapter_hash, cache_context):
    payload = {
        "model_id": config.get("model_id"),
        "revision": config.get("revision"),
        "adapter_sha256": adapter_hash,
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
        "prompt_version": "task3-prompt-v2",
        "cache_context": cache_context,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _read_progress(path, records):
    cached, seen = {}, set()
    if not path.exists():
        return cached
    expected = {r.sample_id for r in records}
    with path.open(encoding="utf-8") as stream:
        lines = stream.readlines()
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                sid = row["prediction"]["sample_id"]
                prediction, trace = row["prediction"], row["trace"]
                if sid not in expected or sid in seen or trace.get("sample_id") != sid:
                    raise ValueError
                validate_predictions([prediction], [sid])
                if not isinstance(row.get("cache_key"), str) or not isinstance(trace.get("attempts"), list):
                    raise ValueError
                seen.add(sid)
                cached[sid] = row
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                if line_number == len(lines) and not line.endswith("\n"):
                    break
                raise ValueError(f"invalid inference progress record at line {line_number}") from exc
    return cached


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
):
    outputs, traces = [], []
    if not isinstance(config.get("max_retries", 2), int) or not 0 <= config.get("max_retries", 2) <= 5:
        raise ValueError("max_retries must be an integer from 0 to 5")
    # Validate the entire taxonomy input before running any generation.
    for record in records:
        taxonomy_for(record, taxonomy_source, predicted)
    progress = Path(progress_path) if progress_path else None
    cached = _read_progress(progress, records) if progress and resume else {}
    adapter_hash = _adapter_hash(config)
    if progress:
        progress.parent.mkdir(parents=True, exist_ok=True)
        retained = {}
        if resume:
            for record in records:
                previous = cached.get(record.sample_id)
                if previous and previous["cache_key"] == _cache_key(
                    record,
                    taxonomy_for(record, taxonomy_source, predicted),
                    config,
                    adapter_hash,
                    cache_context,
                ):
                    retained[record.sample_id] = previous
        with progress.open("w", encoding="utf-8") as stream:
            for record in records:
                if record.sample_id in retained:
                    stream.write(json.dumps(retained[record.sample_id], ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        progress.chmod(0o600)
        cached = retained
    for record in records:
        taxonomy = taxonomy_for(record, taxonomy_source, predicted)
        key = _cache_key(record, taxonomy, config, adapter_hash, cache_context)
        previous = cached.get(record.sample_id)
        if previous and previous["cache_key"] == key:
            outputs.append(previous["prediction"])
            traces.append(previous["trace"])
            continue
        demos = select_exemplars(demo_pool, record, config.get("few_shot_k", 0), forbidden=records)
        attempts, elapsed, tokens = [], 0.0, 0
        for retry in range(config.get("max_retries", 2) + 1):
            hint = (
                ""
                if retry == 0
                else "Vi phạm ở lần trước: "
                + ", ".join(attempts[-1]["violations"])
                + ". Hãy tuân thủ chặt mức phản hồi."
            )
            prompt = budget_prompt(
                record,
                taxonomy,
                backend.tokenizer,
                config.get("context_limit", 4096),
                config.get("max_new_tokens", 512),
                demos,
                strict_hint=hint,
            )
            generated = backend.generate(prompt.messages, config)
            result = check(generated.text, record.target_feedback_level)
            attempts.append(
                {
                    "violations": list(result.violations),
                    "severe": result.severe,
                    "heuristic_compliance": result.heuristic_compliance,
                }
            )
            elapsed += generated.latency_s
            tokens += generated.output_tokens
            if result.ok:
                break
        used_fallback = not result.ok
        feedback = fallback(record.target_feedback_level) if used_fallback else generated.text.strip()
        final = check(feedback, record.target_feedback_level)
        if not final.ok:
            raise RuntimeError("internal fallback failed guard")
        prediction = {"sample_id": record.sample_id, "output": {"taxonomy_error": taxonomy, "feedback": feedback}}
        trace = {
            "sample_id": record.sample_id,
            "taxonomy_source": taxonomy_source,
            "level": result.level,
            "attempts": attempts,
            "raw_first_attempt_compliance": attempts[0]["heuristic_compliance"],
            "raw_first_attempt_severe_solution_leak": attempts[0]["severe"],
            "heuristic_compliance": final.heuristic_compliance,
            "semantic_compliance": final.semantic_compliance,
            "severe_solution_leak": final.severe,
            "diagnosis_quality_status": "unknown_or_inadequate_fallback" if used_fallback else "not_measured",
            "fallback": used_fallback,
            "fallback_used": used_fallback,
            "final_guard": asdict(final),
            "input_tokens": prompt.input_tokens,
            "output_tokens": tokens,
            "latency_s": elapsed,
            "retry_count": max(0, len(attempts) - 1),
            "examples_used": prompt.examples_used,
            "log_budget": prompt.log_budget,
        }
        outputs.append(prediction)
        traces.append(trace)
        if progress:
            with progress.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {"cache_key": key, "prediction": prediction, "trace": trace},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                stream.flush()
                os.fsync(stream.fileno())
            progress.chmod(0o600)
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
