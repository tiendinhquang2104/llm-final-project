#!/usr/bin/env python3
"""Run the independent one-turn Task 3 baseline on prepared non-public splits."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.task3.compiler import check_cpp_syntax
from src.task3.dataset import load_prepared, write_json
from src.task3.direct_baseline import DirectBaselineError, apply_json_output_constraint, build_direct_messages, run_direct_baseline
from src.task3.evaluator import evaluate
from src.task3.inference import HFBackend, load_tokenizer
from src.task3.runtime import runtime_manifest
from src.task3.submission import validate_submission
from src.task3.cli import verify_prepared
from src.utils.config import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/task3/self_diagnosis_zero_shot.yaml")
    parser.add_argument("--split", choices=("real-val", "real-train", "synthetic-heldout"), default="real-val")
    parser.add_argument("--output", required=True)
    parser.add_argument("--attempts-output")
    args = parser.parse_args(argv)
    output_path = Path(args.output)
    attempt_path = Path(args.attempts_output) if args.attempts_output else output_path.with_suffix(".attempts.jsonl")
    audit_path = output_path.with_suffix(".tokenizer-audit.json")
    for artifact in (
        output_path,
        output_path.with_suffix(".run.json"),
        output_path.with_suffix(".traces.json"),
        output_path.with_suffix(".metrics.json"),
        attempt_path,
        audit_path,
    ):
        if artifact.exists():
            raise ValueError(f"output already exists; refusing to risk stale or overwritten artifacts: {artifact}")
    config = load_config(args.config)
    root = Path(config.get("data_dir", "data/processed/task3"))
    manifest_hash = verify_prepared(root)
    records = load_prepared(root, args.split)
    if not records:
        raise ValueError("selected direct-baseline split is empty")

    # This branch uses C++11 syntax-only checks, never executes student programs.
    compiler = config.get("cpp_compiler")
    enriched = []
    from dataclasses import replace

    for record in records:
        evidence = check_cpp_syntax(
            record.code,
            compiler=compiler,
            timeout_s=config.get("compiler_timeout_s", 5.0),
            standard="c++11",
        )
        enriched.append(replace(
            record,
            compile_log=evidence["diagnostic"] if evidence["status"] == "compile_error" else record.compile_log,
            provenance={**record.provenance, "_task3_compile_check": evidence},
        ))
    records = enriched

    tokenizer = load_tokenizer(config)
    config = apply_json_output_constraint(
        config, tokenizer, [record.target_feedback_level for record in records]
    )
    prompt_budget = []
    for record in records:
        messages = build_direct_messages(record, record.provenance["_task3_compile_check"])
        ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        prompt_tokens = int(ids.shape[-1]) if hasattr(ids, "shape") else len(ids)
        prompt_budget.append({
            "sample_id": record.sample_id,
            "input_tokens": prompt_tokens,
            "completion_reserve": config.get("max_new_tokens", 512),
            "context_limit": config.get("context_limit", 4096),
            "fits": prompt_tokens + config.get("max_new_tokens", 512) <= config.get("context_limit", 4096),
        })
    blocked = [row["sample_id"] for row in prompt_budget if not row["fits"]]
    write_json(audit_path, {
        "status": "blocked" if blocked else "passed",
        "model_id": config["model_id"],
        "revision": config["revision"],
        "records": prompt_budget,
        "blocked_ids": blocked,
    })
    if blocked:
        raise ValueError(f"direct baseline tokenizer budget blocked IDs: {', '.join(blocked)}")

    backend = HFBackend(config, tokenizer)
    try:
        predictions, traces = run_direct_baseline(records, backend, config, attempts_path=attempt_path)
    except DirectBaselineError as exc:
        attempt_rows = [json.loads(line) for line in attempt_path.read_text(encoding="utf-8").splitlines() if line]
        metadata = runtime_manifest(config, backend.tokenizer)
        metadata.update({
            "experiment_id": "TASK3-DIRECT-ZERO-SHOT-ONE-TURN",
            "branch": "direct_self_prediction_and_feedback",
            "status": "failed_validation_no_predictions_exported",
            "failure_sample_id": exc.sample_id,
            "failure_attempt_count": exc.attempts,
            "split": args.split,
            "data_manifest_sha256": manifest_hash,
            "selected_sample_ids": [record.sample_id for record in records],
            "attempts_path": str(attempt_path),
            "prompt_tokenizer_audit": str(audit_path),
            "compiler_standard": "c++11",
            "programs_executed": False,
            "input_tokens_total": sum(row["input_tokens"] for row in attempt_rows),
            "output_tokens_total": sum(row["output_tokens"] for row in attempt_rows),
            "latency_s_total": sum(row["latency_s"] for row in attempt_rows),
            "fallback_count": 0,
            "prediction_exported": False,
        })
        write_json(output_path.with_suffix(".run.json"), metadata)
        raise
    temporary = _write_temp_for_validation(output_path, predictions)
    validate_submission(temporary, {record.sample_id: record.target_feedback_level for record in records})
    temporary.unlink(missing_ok=True)
    write_json(output_path, predictions)
    write_json(output_path.with_suffix(".traces.json"), traces)
    metadata = runtime_manifest(config, backend.tokenizer)
    metadata.update({
        "experiment_id": "TASK3-DIRECT-ZERO-SHOT-ONE-TURN",
        "branch": "direct_self_prediction_and_feedback",
        "status": "complete",
        "split": args.split,
        "data_manifest_sha256": manifest_hash,
        "selected_sample_ids": [record.sample_id for record in records],
        "prediction_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "attempts_path": str(attempt_path),
        "prompt_tokenizer_audit": str(audit_path),
        "compiler_standard": "c++11",
        "json_markdown_fence_constraint": config.get("bad_words_ids"),
        "programs_executed": False,
        "input_tokens_total": sum(row["input_tokens_total"] for row in traces),
        "output_tokens_total": sum(row["output_tokens_total"] for row in traces),
        "latency_s_total": sum(row["latency_s_total"] for row in traces),
        "fallback_count": 0,
        "prediction_exported": True,
    })
    metrics = evaluate(
        records,
        predictions,
        taxonomy_source="direct-one-turn-zero-shot",
        run_manifest={"config": {"guard_policy_version": config.get("guard_policy_version", 2)}},
    )
    write_json(output_path.with_suffix(".metrics.json"), metrics)
    write_json(output_path.with_suffix(".run.json"), metadata)
    print(json.dumps({
        "status": "complete",
        "records": len(predictions),
        "predictions": str(output_path),
        "attempts": str(attempt_path),
        "manifest": str(output_path.with_suffix(".run.json")),
    }, ensure_ascii=False))


def _write_temp_for_validation(path, predictions):
    from src.task3.dataset import write_json

    temporary = path.with_name(path.name + ".validation-tmp")
    write_json(temporary, predictions)
    return temporary


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None
