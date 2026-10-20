"""Shared CLI implementation; script entry points remain tiny."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.task3.dataset import load_prepared, prepare, read_json, write_json
from src.task3.diagnosis import (
    attach_compiler_evidence,
    audit_taxonomy_prompts,
    diagnose_taxonomies,
    load_taxonomy_diagnosis_audit,
)
from src.task3.evaluator import evaluate, write_benchmark, write_review_csv
from src.task3.inference import HFBackend, MockBackend, MockTokenizer, load_tokenizer, tokenizer_metadata
from src.task3.pipeline import (
    _adapter_hash,
    audit_prompts,
    export_predictions,
    implementation_digest,
    infer,
    load_taxonomy_predictions,
)
from src.task3.runtime import runtime_manifest
from src.task3.submission import load_requested_levels
from src.task3.strategy import PROMPT_STRATEGIES, resolve_strategy_config
from src.utils.config import load_config


def prepare_main(argv=None):
    p = argparse.ArgumentParser(description="Normalize and audit Task3 locally; never changes fixed split IDs")
    for flag, default in (
        ("real", "data/raw/sample_dataset"),
        ("synthetic", "data/synth/generate-dataset"),
        ("synthetic-heldout", "data/synth/generate-dataset/heldout"),
        ("public", "data/raw/public_test_release"),
    ):
        p.add_argument(f"--{flag}", default=default)
    p.add_argument("--output", default="data/processed/task3")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--filter-synthetic", choices=["none", "strict"], default="strict")
    args = p.parse_args(argv)
    roots = {s: getattr(args, s.replace("-", "_")) for s in ("real", "synthetic", "synthetic-heldout", "public")}
    result = prepare(roots, args.output, Path(__file__).resolve().parents[2], args.seed, args.filter_synthetic)
    print(
        json.dumps(
            {
                "manifest": str(Path(args.output) / "manifest.json"),
                "partitions": result["partitions"],
                "excluded": len(result["excluded"]),
            },
            ensure_ascii=False,
        )
    )


def verify_prepared(root):
    manifest_path = Path(root) / "manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("dataset_version") != "task3-v1":
        raise ValueError("unsupported or missing prepared dataset manifest version")
    for name, expected in manifest["processed_sha256"].items():
        path = Path(root) / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("prepared data does not match manifest; prepare again")
    from src.task3.dataset import fixed_splits

    fixed, metadata = fixed_splits(Path(__file__).resolve().parents[2])
    for split in ("train", "val"):
        declared = manifest.get("fixed_splits", {}).get(split, {})
        if declared.get("sha256") != metadata[split]["sha256"] or declared.get("count") != len(fixed[split]):
            raise ValueError("prepared manifest does not match the checked-in official split IDs")
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def select_sample_records(records, path):
    ids = read_json(path)
    if not isinstance(ids, list) or not ids or any(not isinstance(sid, str) or not sid for sid in ids) or len(set(ids)) != len(ids):
        raise ValueError("pilot sample IDs must be a nonempty unique string list")
    selected = [r for r in records if r.sample_id in set(ids)]
    if set(ids) != {r.sample_id for r in selected}:
        raise ValueError("pilot sample IDs are missing from the selected split")
    if ids != [r.sample_id for r in selected]:
        raise ValueError("pilot sample IDs must preserve prepared split order")
    return selected


def run_main(argv=None):
    p = argparse.ArgumentParser(
        description="Local Task3 oracle/public inference; --dry-run uses TEST-ONLY mocks, no downloads"
    )
    p.add_argument("--config", default="configs/task3/baseline.yaml")
    p.add_argument("--split", choices=["real-val", "synthetic-heldout", "public", "synthetic-train"], default="real-val")
    p.add_argument("--taxonomy-source", choices=["gold", "task2-json", "self-diagnosis"], default="gold")
    p.add_argument("--taxonomy-json")
    p.add_argument("--requested-levels", help="required public ID/Level input used to order and validate inference")
    p.add_argument("--diagnosis-audit", help="validated local diagnosis audit to share across paired experiments")
    p.add_argument(
        "--allow-unverified-task2-export",
        action="store_true",
        help="allow legacy Task2 label-only files whose parse_ok provenance is unknowable",
    )
    p.add_argument("--adapter")
    p.add_argument("--output")
    p.add_argument("--force-review-template", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume-progress", action="store_true")
    p.add_argument("--progress-file")
    p.add_argument("--audit-tokenizer", action="store_true")
    p.add_argument("--sample-ids", help="declared ordered subset for a mechanical pilot; never modifies data")
    p.add_argument("--seed", type=int)
    p.add_argument(
        "--prompt-strategy",
        choices=sorted(PROMPT_STRATEGIES),
        help="override the configured prompting method; default preserves legacy zero/few-shot behavior",
    )
    args = p.parse_args(argv)
    if args.split == "synthetic-train" and not args.sample_ids:
        p.error("synthetic-train requires --sample-ids for an explicitly declared train pilot")
    config = load_config(args.config)
    config = resolve_strategy_config(config, args.prompt_strategy)
    if args.adapter:
        config["adapter"] = args.adapter
    if args.seed is not None:
        config["seed"] = args.seed
    if args.split == "public" and args.taxonomy_source == "gold":
        p.error("public mode requires a predicted taxonomy source; gold is unavailable")
    if args.taxonomy_source == "task2-json" and not args.taxonomy_json:
        p.error("--taxonomy-json is required; missing predictions cannot default to []")
    if args.split == "public" and not args.requested_levels:
        p.error("--requested-levels is required for public mode; public IDs/Levels are not inferred from feedback metadata")
    if args.requested_levels and args.split != "public":
        p.error("--requested-levels is only valid for the public split")
    if args.split == "public" and args.sample_ids:
        p.error("public inference must cover the complete requested-level ID set")
    if args.taxonomy_source == "self-diagnosis" and args.taxonomy_json:
        p.error("--taxonomy-json is only valid with --taxonomy-source task2-json")
    root = config.get("data_dir", "data/processed/task3")
    manifest_hash = verify_prepared(root)
    records = load_prepared(root, args.split)
    requested_levels = None
    requested_levels_sha256 = None
    if args.split == "public":
        requested_levels = load_requested_levels(args.requested_levels)
        requested_levels_sha256 = hashlib.sha256(Path(args.requested_levels).read_bytes()).hexdigest()
        records_by_id = {record.sample_id: record for record in records}
        if len(records_by_id) != len(records) or set(records_by_id) != set(requested_levels):
            raise ValueError("prepared public IDs do not exactly match requested-level IDs")
        if any(records_by_id[sid].target_feedback_level != level for sid, level in requested_levels.items()):
            raise ValueError("prepared public Level does not match requested-level file")
        records = [records_by_id[sid] for sid in requested_levels]
    records = attach_compiler_evidence(records, config)
    if args.sample_ids:
        records = select_sample_records(records, args.sample_ids)
    if not records:
        raise ValueError("selected split is empty")
    if config.get("guard_policy_version", 1) >= 2:
        config["runtime_implementation_sha256"] = implementation_digest()
    if args.taxonomy_json:
        predicted, taxonomy_audit = load_taxonomy_predictions(
            args.taxonomy_json,
            [r.sample_id for r in records],
            return_audit=True,
            allow_unverified=args.allow_unverified_task2_export,
        )
    else:
        predicted, taxonomy_audit = None, None
    if args.dry_run:
        # Mock UTF8 counts are larger than real tokenizer counts; this budget is TEST ONLY.
        config = {**config, "context_limit": 65536}
    demos = []
    if config.get("few_shot_k", 0):
        demos = load_prepared(root, "real-train") + load_prepared(root, "synthetic-train")
    output = Path(args.output or f"outputs/task3/{args.split}{'.mock' if args.dry_run else ''}.predictions.json")
    # Acceptance --output predictions.json --dry-run gets a clearly separate mock file.
    if args.dry_run and "mock" not in output.stem.lower():
        output = output.with_name(output.stem + ".mock" + output.suffix)
    if args.audit_tokenizer and args.dry_run:
        p.error("--audit-tokenizer requires the pinned real Qwen tokenizer; it cannot use --dry-run")
    tokenizer = MockTokenizer() if args.dry_run else load_tokenizer(config)
    diagnoses = None
    backend = None
    diagnosis_audit = None
    diagnosis_run_path = None
    if args.diagnosis_audit:
        diagnosis_run_path = Path(args.diagnosis_audit).with_suffix(".run.json")
        diagnosis_predictions, diagnosis_audit = load_taxonomy_diagnosis_audit(args.diagnosis_audit, records)
        if args.taxonomy_source == "self-diagnosis":
            predicted = diagnosis_predictions
        if args.taxonomy_source == "self-diagnosis":
            taxonomy_audit = {
                "provenance_status": "loaded_local_self_diagnosis",
                "required_id_count": len(records),
                "validated_id_count": len(predicted),
                "taxonomy_diagnosis_sha256": hashlib.sha256(
                    json.dumps(diagnosis_audit, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest(),
            }
    elif args.taxonomy_source == "self-diagnosis":
        diagnosis_prompt_audit = audit_taxonomy_prompts(records, tokenizer, config)
        diagnosis_audit_path = output.with_suffix(".taxonomy-tokenizer-audit.json")
        diagnosis_prompt_audit["tokenizer_metadata"] = tokenizer_metadata(tokenizer)
        write_json(diagnosis_audit_path, diagnosis_prompt_audit)
        if diagnosis_prompt_audit["blocked_count"]:
            raise ValueError(
                f"taxonomy tokenizer preflight blocked {diagnosis_prompt_audit['blocked_count']} samples; see ID-only report {diagnosis_audit_path}"
            )
        if args.audit_tokenizer:
            print(json.dumps({"status": diagnosis_prompt_audit["status"], "stage": "taxonomy_diagnosis", "records": len(records), "audit": str(diagnosis_audit_path)}, ensure_ascii=False))
            return
        backend = MockBackend() if args.dry_run else HFBackend(config, tokenizer)
        predicted, diagnosis_audit = diagnose_taxonomies(
            records,
            backend,
            config,
            attempt_journal_path=output.with_suffix(".taxonomy-diagnosis.attempts.jsonl"),
        )
        write_json(output.with_suffix(".taxonomy-diagnosis.json"), diagnosis_audit)
        diagnosis_run_path = output.with_suffix(".taxonomy-diagnosis.run.json")
        diagnosis_provenance = runtime_manifest(config, backend.tokenizer, backend=backend)
        diagnosis_provenance.update(
            stage="taxonomy_diagnosis",
            status="TEST-ONLY MOCK" if args.dry_run else "GENERATED",
            split=args.split,
            data_manifest_sha256=manifest_hash,
            selected_ordered_ids=[r.sample_id for r in records],
            adapter_sha256=_adapter_hash(config),
            diagnosis_audit_sha256=hashlib.sha256(
                output.with_suffix(".taxonomy-diagnosis.json").read_bytes()
            ).hexdigest(),
        )
        write_json(diagnosis_run_path, diagnosis_provenance)
        taxonomy_audit = {
            "provenance_status": "test_only_mock" if args.dry_run else "local_self_diagnosis",
            "required_id_count": len(records),
            "validated_id_count": len(predicted),
            "taxonomy_diagnosis_sha256": hashlib.sha256(
                json.dumps(diagnosis_audit, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
        }
    prompt_audit = audit_prompts(records, tokenizer, config, args.taxonomy_source, predicted, demos, diagnoses=diagnosis_audit)
    prompt_audit["tokenizer_metadata"] = tokenizer_metadata(tokenizer)
    audit_path = output.with_suffix(".tokenizer-audit.json")
    write_json(audit_path, prompt_audit)
    if args.audit_tokenizer:
        print(
            json.dumps(
                {
                    "status": prompt_audit["status"],
                    "records": prompt_audit["n_samples"],
                    "blocked": prompt_audit["blocked_count"],
                    "audit": str(audit_path),
                },
                ensure_ascii=False,
            )
        )
        return
    if prompt_audit["blocked_count"]:
        raise ValueError(
            f"tokenizer preflight blocked {prompt_audit['blocked_count']} samples; see ID-only report {audit_path}"
        )
    if backend is None:
        backend = MockBackend() if args.dry_run else HFBackend(config, tokenizer)
    progress_path = Path(args.progress_file) if args.progress_file else output.with_suffix(".progress.jsonl")
    try:
        predictions, traces = infer(
            records,
            backend,
            config,
            args.taxonomy_source,
            predicted,
            demos,
            progress_path=progress_path,
            resume=args.resume_progress,
            cache_context=manifest_hash,
            attempt_journal_path=progress_path.with_suffix(".attempts.jsonl"),
            diagnoses=diagnosis_audit,
        )
    except (RuntimeError, ValueError):
        failed = runtime_manifest(config, backend.tokenizer, backend=backend)
        failed.update(
            status="failed_inference_no_predictions_exported",
            prediction_exported=False,
            split=args.split,
            taxonomy_source=args.taxonomy_source,
            data_manifest_sha256=manifest_hash,
            selected_ordered_ids=[record.sample_id for record in records],
            progress_file=str(progress_path),
        )
        write_json(output.with_suffix(".run.json"), failed)
        raise
    export_predictions(output, predictions, records, mock=args.dry_run)
    metrics = evaluate(records, predictions, traces, args.taxonomy_source)
    metrics["test_only_mock"] = args.dry_run
    metrics["taxonomy_projection"] = taxonomy_audit
    provenance = runtime_manifest(config, backend.tokenizer, backend=backend)
    provenance.update(
        status="TEST-ONLY MOCK" if args.dry_run else "GENERATED",
        split=args.split,
        taxonomy_source=args.taxonomy_source,
        data_manifest_sha256=manifest_hash,
        taxonomy_predictions_sha256=hashlib.sha256(Path(args.taxonomy_json).read_bytes()).hexdigest()
        if args.taxonomy_json
        else None,
        taxonomy_diagnosis_sha256=(
            hashlib.sha256(json.dumps(diagnosis_audit, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if diagnosis_audit is not None else None
        ),
        taxonomy_projection=taxonomy_audit,
        tokenizer_preflight=prompt_audit["status"],
        tokenizer_preflight_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        progress_file=str(progress_path),
        adapter_sha256=_adapter_hash(config),
        feedback_model={"model_id": config.get("model_id"), "revision": config.get("revision"), "adapter_sha256": _adapter_hash(config)},
        taxonomy_model=(
            {"kind": "self-diagnosis", "run_manifest": str(diagnosis_run_path) if diagnosis_run_path else None,
             "model_id": (read_json(diagnosis_run_path).get("model_id") if diagnosis_run_path and diagnosis_run_path.exists() else None),
             "revision": (read_json(diagnosis_run_path).get("revision") if diagnosis_run_path and diagnosis_run_path.exists() else None),
             "adapter_sha256": (read_json(diagnosis_run_path).get("adapter_sha256") if diagnosis_run_path and diagnosis_run_path.exists() else None)}
            if args.taxonomy_source == "self-diagnosis" else {"kind": args.taxonomy_source}
        ),
        official_validator="not supplied; strict local schema validation only",
        selected_ordered_ids=[r.sample_id for r in records],
        requested_levels_sha256=requested_levels_sha256,
        pilot_sample_ids_sha256=hashlib.sha256(Path(args.sample_ids).read_bytes()).hexdigest() if args.sample_ids else None,
    )
    write_json(output.with_suffix(".run.json"), provenance)
    write_json(output.with_suffix(".traces.json"), traces)
    write_json(output.with_suffix(".metrics.json"), metrics)
    review_template = write_review_csv(
        output.with_suffix(".review-template.csv"),
        records,
        traces,
        predictions=predictions,
        run_manifest=provenance,
        force=args.force_review_template,
    )
    print(
        json.dumps(
            {
                "status": provenance["status"],
                "records": len(records),
                "output": str(output),
                "diagnosis_quality": "not automatically measured",
                "gpu_training": "NOT RUN",
                "review_template": review_template["status"],
            },
            ensure_ascii=False,
        )
    )


def train_main(argv=None):
    p = argparse.ArgumentParser(
        description="Explicit Task3 CUDA QLoRA training; dry-run does not download/load a model"
    )
    p.add_argument("--config", default="configs/task3/qlora.yaml")
    p.add_argument(
        "--experiment",
        choices=["synthetic", "real", "mixed", "mixed_uniform", "mixed_balanced", "staged"],
    )
    p.add_argument("--output-dir")
    p.add_argument("--max-steps", type=int)
    p.add_argument("--resume-from-checkpoint")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true")
    group.add_argument(
        "--audit-tokenizer",
        action="store_true",
        help="download only pinned tokenizer and measure 2048/4096 fit; no training",
    )
    group.add_argument("--smoke-test", action="store_true", help="run only a 10-20 optimizer-step GPU validation")
    args = p.parse_args(argv)
    config = load_config(args.config)
    if args.experiment:
        config["experiment"] = args.experiment
    if args.output_dir:
        config["output_dir"] = args.output_dir
    if args.max_steps is not None and args.max_steps <= 0:
        p.error("--max-steps must be a positive optimizer-step count")
    from src.task3.train import run_training

    result = run_training(
        config,
        args.dry_run,
        args.audit_tokenizer,
        max_steps=args.max_steps,
        resume_from_checkpoint=args.resume_from_checkpoint,
        smoke_test=args.smoke_test,
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "train_records",
                    "val_records",
                    "optimizer_steps",
                    "peak_gpu_memory_allocated_bytes",
                    "step_time_mean_s",
                    "adapter_reload_smoke",
                )
                if key in result
            },
            ensure_ascii=False,
        )
    )


def evaluate_main(argv=None):
    p = argparse.ArgumentParser(description="Task3 local guard metrics and ID-only human diagnosis review worklist")
    p.add_argument("--data-dir", default="data/processed/task3")
    p.add_argument("--split", choices=["real-val", "synthetic-heldout", "public"])
    p.add_argument("--predictions")
    p.add_argument("--traces")
    p.add_argument("--taxonomy-source", choices=["gold", "task2-json"])
    p.add_argument("--annotations")
    p.add_argument("--run-manifest")
    p.add_argument("--output", default="outputs/task3/evaluation.json")
    p.add_argument("--init-benchmark-template", action="store_true")
    p.add_argument("--force-review-template", action="store_true")
    args = p.parse_args(argv)
    if args.init_benchmark_template:
        from src.task3.schema import MODEL_ID

        config = load_config("configs/task3/baseline.yaml")
        write_benchmark(Path(args.output).parent, MODEL_ID, config["revision"])
        return
    if not args.split or not args.predictions or not args.taxonomy_source:
        p.error("--split, --predictions and --taxonomy-source are required unless initializing a benchmark template")
    verify_prepared(args.data_dir)
    records = load_prepared(args.data_dir, args.split)
    predictions = read_json(args.predictions)
    run_manifest_path = Path(args.run_manifest) if args.run_manifest else Path(args.predictions).with_suffix(".run.json")
    run_manifest = read_json(run_manifest_path) if run_manifest_path.is_file() else None
    if args.annotations and run_manifest is None:
        raise ValueError("human annotations require --run-manifest matching the predictions")
    metrics = evaluate(
        records,
        predictions,
        read_json(args.traces) if args.traces else (),
        args.taxonomy_source,
        annotations=args.annotations,
        run_manifest=run_manifest,
    )
    metrics["test_only_mock"] = "mock" in Path(args.predictions).stem.lower()
    review_template = write_review_csv(
        Path(args.output).with_suffix(".review-template.csv"),
        records,
        read_json(args.traces) if args.traces else (),
        predictions=predictions,
        run_manifest=run_manifest,
        force=args.force_review_template,
    )
    metrics["review_template"] = review_template["status"]
    write_json(args.output, metrics)
    print(json.dumps(metrics, ensure_ascii=False))
