"""Explicit CUDA QLoRA SFT with verified completion-only labels, no template markers assumed."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import time
from collections import Counter
from pathlib import Path

from src.task3.dataset import load_prepared, read_json, write_json
from src.task3.inference import MockTokenizer, load_tokenizer, tokenizer_metadata
from src.task3.prompts import ContextTooLong, budget_prompt
from src.task3.runtime import runtime_manifest


def encode_completion(tokenizer, prompt, completion, max_length):
    """Require exact prefix stability in the tokenizer's actual conversational template.

    Labels mask the entire system/user/prompt and assistant header. The target and end-of-turn
    tokens remain supervised. Fail rather than silently mask an incompatible template or crop
    targets. This works without Jinja generation markers and does not use assistant_only_loss.
    """
    if not completion or not completion.strip():
        raise ValueError("empty completion")
    prefix = tokenizer.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(
        prompt + [{"role": "assistant", "content": completion}], tokenize=True, add_generation_prompt=False
    )
    if full[: len(prefix)] != prefix:
        raise ValueError("chat template is not prefix-stable; completion mask cannot be verified")
    if len(full) <= len(prefix):
        raise ValueError("completion produced no target tokens")
    if len(full) > max_length:
        raise ContextTooLong(f"training target would be truncated: {len(full)} > {max_length}")
    labels = [-100] * len(prefix) + full[len(prefix) :]
    return {"input_ids": full, "attention_mask": [1] * len(full), "labels": labels}


class CompletionCollator:
    def __init__(self, pad_token_id):
        self.pad_token_id = pad_token_id

    def __call__(self, rows):
        import torch

        size = max(len(r["input_ids"]) for r in rows)
        return {
            key: torch.tensor([r[key] + [pad] * (size - len(r[key])) for r in rows], dtype=torch.long)
            for key, pad in (("input_ids", self.pad_token_id), ("attention_mask", 0), ("labels", -100))
        }


def training_records(root, experiment):
    names = {
        "synthetic": ["synthetic-train"],
        "real": ["real-train"],
        "mixed": ["real-train", "synthetic-train"],
        "mixed_uniform": ["real-train", "synthetic-train"],
        "mixed_balanced": ["real-train", "synthetic-train"],
        "staged": ["synthetic-train"],
    }
    if experiment not in names:
        raise ValueError("experiment must be synthetic, real or mixed")
    train = [r for split in names[experiment] for r in load_prepared(root, split)]
    val = load_prepared(root, "real-val")
    heldout = load_prepared(root, "synthetic-heldout")
    if not train or not val:
        raise ValueError("training and fixed real validation must be nonempty")
    train_groups = {r.group_key for r in train}
    if "" in train_groups or train_groups & {r.group_key for r in val + heldout}:
        raise ValueError("missing or overlapping train/evaluation groups")
    return train, val


def sample_training_rows(rows, records, weights, seed=42, *, return_records=False):
    """Deterministically resample mixed examples to the requested source proportions."""
    if len(rows) != len(records):
        raise ValueError("training rows and source records must stay aligned")
    source_counts = Counter(record.source for record in records)
    active_weights = {
        source: float(weights.get(source, 0))
        for source, count in source_counts.items()
        if count
    }
    if not active_weights or any(weight < 0 for weight in active_weights.values()) or sum(active_weights.values()) <= 0:
        raise ValueError("source weights must include a positive nonnegative weight for every selected source")
    total = sum(active_weights.values())
    per_row_weights = [
        active_weights.get(record.source, 0) / total / source_counts[record.source] for record in records
    ]
    rng = random.Random(seed)
    sampled = rng.choices(range(len(rows)), weights=per_row_weights, k=len(rows))
    sampled_rows = [rows[index] for index in sampled]
    exposures = dict(Counter(records[index].source for index in sampled))
    if return_records:
        return sampled_rows, exposures, [records[index] for index in sampled]
    return sampled_rows, exposures


def _histograms(records):
    per_source = Counter(record.source for record in records)
    per_level = Counter(record.target_feedback_level for record in records)
    source_level = Counter((record.source, record.target_feedback_level) for record in records)
    return {
        "per_source": dict(per_source),
        "per_level": dict(per_level),
        "per_source_level": {f"{source}|{level}": count for (source, level), count in source_level.items()},
    }


def _checkpoint_metadata(config, data_manifest_sha256):
    stable_config = {key: value for key, value in config.items() if key not in {"output_dir", "adapter"}}
    config_hash = hashlib.sha256(
        json.dumps(stable_config, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return {
        "model_id": config["model_id"],
        "model_revision": config["revision"],
        "config_sha256": config_hash,
        "data_manifest_sha256": data_manifest_sha256,
    }


def validate_resume_checkpoint(path, metadata):
    path = Path(path).resolve()
    required = ("optimizer.pt", "scheduler.pt", "trainer_state.json", "rng_state.pth")
    if not path.is_dir() or any(not (path / name).is_file() for name in required):
        raise ValueError("resume requires a complete Trainer checkpoint with optimizer, scheduler, trainer and RNG state")
    model_state_names = (
        "model.safetensors",
        "pytorch_model.bin",
        "adapter_model.safetensors",
        "adapter_model.bin",
    )
    if not any((path / name).is_file() for name in model_state_names):
        raise ValueError("resume checkpoint has no model or adapter weights")
    stored_path = path / "task3_resume_metadata.json"
    if not stored_path.is_file():
        raise ValueError("resume checkpoint has no Task 3 compatibility metadata")
    stored = read_json(stored_path)
    if stored != metadata:
        raise ValueError("resume checkpoint model, config or data manifest is incompatible")
    trainer_state = read_json(path / "trainer_state.json")
    if not isinstance(trainer_state.get("global_step"), int) or trainer_state["global_step"] < 0:
        raise ValueError("resume checkpoint has an invalid optimizer step")
    return trainer_state["global_step"]


def tokenize_records(records, tokenizer, max_length):
    rows, audit = [], []
    for r in records:
        # Reserve the full target (including template ending), measured before trimming logs.
        target_budget = len(tokenizer.encode(r.gold_feedback, add_special_tokens=False)) + 32
        if target_budget >= max_length:
            raise ContextTooLong(f"{r.sample_id}: complete target alone exceeds sequence budget")
        prompt = budget_prompt(r, r.gold_taxonomy, tokenizer, max_length, target_budget)
        row = encode_completion(tokenizer, prompt.messages, r.gold_feedback, max_length)
        rows.append(row)
        audit.append(
            {
                "sample_id": r.sample_id,
                "tokens": len(row["input_ids"]),
                "completion_tokens": sum(v != -100 for v in row["labels"]),
                "log_budget": prompt.log_budget,
            }
        )
    return rows, audit


def sequence_audit(records, tokenizer):
    """Measure both supported budgets. Exclusions are explicit and never automatic."""
    trials = {}
    for size in (2048, 4096):
        counts, overlength = [], []
        for record in records:
            try:
                _, audit = tokenize_records([record], tokenizer, size)
                counts.append(audit[0]["tokens"])
            except ContextTooLong:
                overlength.append(record.sample_id)
        trials[str(size)] = {"fits": len(counts), "overlength_ids": overlength, "max_tokens": max(counts, default=0)}
    chosen = next((size for size in (2048, 4096) if not trials[str(size)]["overlength_ids"]), None)
    return {"tokenizer": tokenizer_metadata(tokenizer), "candidates": trials, "selected": chosen}


def _validate_execution_modes(dry_run, audit_only, smoke_test, max_steps):
    if sum((bool(dry_run), bool(audit_only), bool(smoke_test))) > 1:
        raise ValueError("dry-run, tokenizer audit, and GPU smoke test are mutually exclusive")
    if max_steps is not None and (not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps <= 0):
        raise ValueError("max_steps must be a positive optimizer-step count")


def _validate_prepared_manifest(root, manifest):
    for name, expected_hash in manifest["processed_sha256"].items():
        file = root / name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != expected_hash:
            raise ValueError("prepared data changed after manifest creation; prepare again")
    return hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()


def _validate_experiment_data(root, manifest, experiment):
    if experiment in {"mixed", "mixed_uniform", "mixed_balanced", "synthetic"} and manifest["filter_synthetic"] != "strict":
        raise ValueError("synthetic/mixed training requires preparation with --filter-synthetic strict")
    return training_records(root, experiment)


def _training_gpu_preflight(torch, config):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable: QLoRA training NOT RUN; use --dry-run")
    device_count = torch.cuda.device_count()
    if device_count < 1 or config.get("single_gpu", False) and device_count != 1:
        raise RuntimeError("configured single-GPU training requires exactly one visible CUDA device")
    device = torch.cuda.current_device()
    device_name = torch.cuda.get_device_name(device)
    expected_name = config.get("expected_gpu_name")
    if expected_name and expected_name not in device_name:
        raise RuntimeError("selected CUDA device does not match expected_gpu_name")
    bf16_supported = bool(torch.cuda.is_bf16_supported())
    if config.get("require_bf16", False) and not bf16_supported:
        raise RuntimeError("selected CUDA device does not support required BF16 training")
    free_bytes, total_bytes = torch.cuda.mem_get_info(device)
    from src.task3.gpu_preflight import gpu_workload_status

    workload = gpu_workload_status()
    if workload["status"] != "available":
        raise RuntimeError("cannot verify competing GPU workloads; training stopped safely")
    if not config.get("ignore_competing_gpu_workload", False) and workload["external_process_count"]:
        raise RuntimeError("another GPU workload is active; training stopped without disturbing it")
    try:
        minimum_free_gib = float(config.get("min_free_vram_gib", 10))
    except (TypeError, ValueError) as exc:
        raise ValueError("min_free_vram_gib must be a positive number") from exc
    if not math.isfinite(minimum_free_gib) or minimum_free_gib <= 0:
        raise ValueError("min_free_vram_gib must be a positive number")
    minimum_free_bytes = int(minimum_free_gib * 1024**3)
    if free_bytes < minimum_free_bytes:
        raise RuntimeError("insufficient free VRAM for configured QLoRA training; training stopped safely")
    return {
        "device_count": device_count,
        "selected_device": device,
        "selected_device_name": device_name,
        "bf16_supported": bf16_supported,
        "free_vram_bytes": int(free_bytes),
        "total_vram_bytes": int(total_bytes),
        "minimum_free_vram_bytes": minimum_free_bytes,
        "external_gpu_process_count": workload["external_process_count"],
        "external_gpu_memory_mib": workload["external_memory_mib"],
    }


def _session_throughput(final_step, resume_start_step, step_times, samples_per_step, tokens_per_sample):
    start_step = resume_start_step or 0
    session_steps = final_step - start_step
    if session_steps < 0:
        raise ValueError("final optimizer step is below the resume checkpoint step")
    duration = sum(step_times)
    return {
        "cumulative_optimizer_steps": final_step,
        "session_optimizer_steps": session_steps,
        "session_samples_per_second": (
            session_steps * samples_per_step / duration if duration and session_steps else None
        ),
        "session_supervised_tokens_per_second": (
            session_steps * samples_per_step * tokens_per_sample / duration
            if duration and session_steps
            else None
        ),
        "session_optimizer_step_wall_time_s": duration,
    }


def _free_vram_or_none(torch):
    try:
        if torch.cuda.is_available():
            return int(torch.cuda.mem_get_info()[0])
    except (RuntimeError, OSError):
        return None
    return None


def run_training(
    config,
    dry_run=False,
    audit_only=False,
    *,
    max_steps=None,
    resume_from_checkpoint=None,
    smoke_test=False,
):
    _validate_execution_modes(dry_run, audit_only, smoke_test, max_steps)
    experiment = config.get("experiment", "mixed_uniform")
    if experiment == "staged" and resume_from_checkpoint:
        raise ValueError("staged training uses a fresh stage-2 optimizer; staged checkpoint resume is unsupported")
    if experiment == "staged" and smoke_test:
        raise ValueError("staged GPU smoke test is unsupported; run a single-stage smoke test")

    root = Path(config.get("data_dir", "data/processed/task3"))
    manifest = read_json(root / "manifest.json")
    if experiment == "staged":
        total_steps = max_steps if max_steps is not None else config.get("max_steps")
        if not isinstance(total_steps, int) or isinstance(total_steps, bool) or total_steps < 2:
            raise ValueError("staged experiment requires an explicit total --max-steps of at least 2")
        try:
            stage1_fraction = float(config.get("stage1_fraction", 0.75))
        except (TypeError, ValueError) as exc:
            raise ValueError("stage1_fraction must be a number strictly between 0 and 1") from exc
        if not math.isfinite(stage1_fraction) or not 0 < stage1_fraction < 1:
            raise ValueError("stage1_fraction must be strictly between 0 and 1")
        first_steps = int(stage1_fraction * total_steps)
        if not 1 <= first_steps < total_steps:
            raise ValueError("stage1_fraction must allocate at least one optimizer step to each stage")
        try:
            stage2_learning_rate = float(config.get("stage2_learning_rate", 2e-5))
        except (TypeError, ValueError) as exc:
            raise ValueError("stage2_learning_rate must be a positive number") from exc
        if not math.isfinite(stage2_learning_rate) or stage2_learning_rate <= 0:
            raise ValueError("stage2_learning_rate must be a positive number")

        synthetic_train, val = _validate_experiment_data(root, manifest, "synthetic")
        real_train, _ = _validate_experiment_data(root, manifest, "real")
        data_manifest_sha256 = _validate_prepared_manifest(root, manifest)
        output = Path(config.get("output_dir", "checkpoints/task3/qlora"))
        stage1_output = output / "stage-synthetic"
        stage2_output = output / "stage-real"
        if stage1_output.resolve() == stage2_output.resolve():
            raise ValueError("staged training requires separate stage output directories")
        if stage1_output.exists() or stage2_output.exists():
            raise ValueError("staged output directory already exists; choose a new output directory to avoid overwrite")

        if dry_run:
            result = runtime_manifest(config)
            result.update(
                status="DRY RUN — GPU training NOT RUN",
                training_succeeded=False,
                experiment="staged",
                data_manifest_sha256=data_manifest_sha256,
                requested_max_optimizer_steps=total_steps,
                stage1_optimizer_steps=first_steps,
                stage2_optimizer_steps=total_steps - first_steps,
                stages={
                    "stage-synthetic": {"train_records": len(synthetic_train), "val_records": len(val)},
                    "stage-real": {"train_records": len(real_train), "val_records": len(val)},
                },
                tokenizer_audit="NOT RUN: use --audit-tokenizer for the pinned tokenizer",
            )
            write_json(output / "staged-dry-run.json", result)
            return result

        if audit_only:
            tokenizer = load_tokenizer(config)
            audit = {
                "status": "AUDIT ONLY — GPU training NOT RUN",
                "experiment": "staged",
                "data_manifest_sha256": data_manifest_sha256,
                "tokenizer": tokenizer_metadata(tokenizer),
                "stages": {
                    "stage-synthetic": sequence_audit(synthetic_train + val, tokenizer),
                    "stage-real": sequence_audit(real_train + val, tokenizer),
                },
                "training_succeeded": False,
            }
            write_json(output / "staged-tokenizer-audit.json", audit)
            return {
                **runtime_manifest(config, tokenizer),
                **audit,
                "audit_path": str(output / "staged-tokenizer-audit.json"),
            }

        first_config = {
            **config,
            "experiment": "synthetic",
            "output_dir": str(stage1_output),
        }
        first = run_training(first_config, max_steps=first_steps)
        second_config = {
            **config,
            "experiment": "real",
            "output_dir": str(stage2_output),
            "staged_adapter": first["checkpoint_path"],
            "stage_name": "real-adaptation-fresh-optimizer",
            "learning_rate": stage2_learning_rate,
        }
        second = run_training(second_config, max_steps=total_steps - first_steps)
        completed_steps = first.get("optimizer_steps", 0) + second.get("optimizer_steps", 0)
        stages_complete = (
            first.get("status") == "COMPLETE"
            and second.get("status") == "COMPLETE"
            and first.get("optimizer_steps") == first_steps
            and second.get("optimizer_steps") == total_steps - first_steps
        )
        return {
            "status": "COMPLETE" if stages_complete else "FAILED",
            "training_succeeded": stages_complete,
            "experiment": "staged",
            "stage1": first,
            "stage2": second,
            "requested_optimizer_steps": total_steps,
            "stage1_requested_optimizer_steps": first_steps,
            "stage2_requested_optimizer_steps": total_steps - first_steps,
            "optimizer_steps": completed_steps,
            "checkpoint_path": second.get("checkpoint_path"),
            "data_manifest_sha256": data_manifest_sha256,
        }
    if smoke_test and (max_steps is None or not 10 <= max_steps <= 20):
        raise ValueError("GPU smoke test requires --max-steps between 10 and 20")
    train, val = _validate_experiment_data(root, manifest, experiment)
    data_manifest_sha256 = _validate_prepared_manifest(root, manifest)
    checkpoint_metadata = _checkpoint_metadata(
        {
            **config,
            "experiment": experiment,
            "max_steps": max_steps,
        },
        data_manifest_sha256,
    )
    resume_step = None
    if resume_from_checkpoint:
        resume_step = validate_resume_checkpoint(resume_from_checkpoint, checkpoint_metadata)
        if max_steps is not None and resume_step >= max_steps:
            raise ValueError("resume checkpoint already reached the requested total optimizer steps")
    result = runtime_manifest(config)
    result.update(
        status="DRY RUN — GPU training NOT RUN" if dry_run else "AUDIT ONLY" if audit_only else "STARTING",
        train_records=len(train),
        val_records=len(val),
        experiment=experiment,
        data_manifest_sha256=data_manifest_sha256,
        train_histograms=_histograms(train),
        val_histograms=_histograms(val),
        requested_max_optimizer_steps=max_steps,
        resume_from_checkpoint=str(resume_from_checkpoint) if resume_from_checkpoint else None,
        resume_start_optimizer_step=resume_step,
        stage_name=config.get("stage_name", "single-stage"),
        learning_rate=config.get("learning_rate", 1e-4),
    )
    output = Path(config.get("output_dir", "checkpoints/task3/qlora"))
    if dry_run:
        # Exercise actual masking on a small TEST-ONLY fixture. Do not invent Qwen token lengths.
        tokenizer = MockTokenizer()
        fixture = encode_completion(tokenizer, [{"role": "user", "content": "TEST-ONLY"}], "Phản hồi thử nghiệm.", 2048)
        result.update(
            mask_smoke_test=any(x == -100 for x in fixture["labels"]),
            tokenizer_audit="NOT RUN: use --audit-tokenizer to measure the real Qwen tokenizer",
            training_succeeded=False,
        )
        write_json(output / "dry-run.json", result)
        return result
    gpu_audit = None
    if not audit_only:
        import torch

        try:
            gpu_audit = _training_gpu_preflight(torch, config)
        except (RuntimeError, ValueError) as exc:
            result.update(
                status="FAILED",
                training_succeeded=False,
                error_type=type(exc).__name__,
                failed_optimizer_step=resume_step or 0,
                failure_config_sha256=checkpoint_metadata["config_sha256"],
                failure_data_manifest_sha256=data_manifest_sha256,
                free_vram_at_failure_bytes=_free_vram_or_none(torch),
            )
            write_json(output / "run.json", result)
            raise
    tokenizer = load_tokenizer(config)
    audit = sequence_audit(train + val, tokenizer)
    write_json(output / "tokenizer-audit.json", audit)
    if audit_only:
        return {**result, "audit": audit, "gpu_training": "NOT RUN"}
    max_length = config.get("max_seq_length", "auto")
    if max_length == "auto":
        max_length = audit["selected"]
    if max_length not in (2048, 4096) or audit["candidates"][str(max_length)]["overlength_ids"]:
        raise ValueError("overlength training/validation examples: inspect tokenizer-audit.json; no targets truncated")
    import numpy as np
    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        BitsAndBytesConfig,
        Trainer,
        TrainerCallback,
        TrainingArguments,
        set_seed,
    )

    set_seed(config.get("seed", 42))
    bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if bf16 else torch.float16
    tokenization_start = time.perf_counter()
    train_rows, train_audit = tokenize_records(train, tokenizer, max_length)
    val_rows, val_audit = tokenize_records(val, tokenizer, max_length)
    tokenization_time = time.perf_counter() - tokenization_start
    sampled_exposures = dict(Counter(record.source for record in train))
    sampled_records = train
    if experiment == "mixed_balanced":
        train_rows, sampled_exposures, sampled_records = sample_training_rows(
            train_rows,
            train,
            config.get("source_weights", {"real": 0.5, "synthetic": 0.5}),
            config.get("seed", 42),
            return_records=True,
        )
    source_level_counts = _histograms(train)
    if experiment == "mixed_balanced":
        source_level_counts["sampled"] = _histograms(sampled_records)
    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=dtype,
    )
    model_load_start = time.perf_counter()
    try:
        device_map = config.get("device_map")
        if device_map is None:
            device_map = "auto" if torch.cuda.device_count() > 1 else {"": torch.cuda.current_device()}
        model_kwargs = {
            "revision": config["revision"],
            "trust_remote_code": False,
            "quantization_config": quant,
            "device_map": device_map,
            "dtype": dtype,
        }
        if config.get("attn_implementation") or getattr(torch.nn.functional, "scaled_dot_product_attention", None) is not None:
            model_kwargs["attn_implementation"] = config.get("attn_implementation", "sdpa")
        model = AutoModelForCausalLM.from_pretrained(
            config["model_id"],
            **model_kwargs,
        )
    except Exception as exc:
        result.update(
            status="FAILED",
            training_succeeded=False,
            error_type=type(exc).__name__,
            failed_optimizer_step=resume_step or 0,
            failure_config_sha256=checkpoint_metadata["config_sha256"],
            failure_data_manifest_sha256=data_manifest_sha256,
            free_vram_at_failure_bytes=_free_vram_or_none(torch),
        )
        write_json(output / "run.json", result)
        raise
    model_load_time = time.perf_counter() - model_load_start
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    if config.get("staged_adapter"):
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, config["staged_adapter"], is_trainable=True)
    else:
        lora = LoraConfig(
            r=config.get("lora_r", 16),
            lora_alpha=config.get("lora_alpha", 32),
            lora_dropout=config.get("lora_dropout", 0.05),
            target_modules=config.get(
                "target_modules", ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
            ),
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora)

    trainable_parameters = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    unfrozen_base = [
        name for name, parameter in model.named_parameters() if parameter.requires_grad and "lora_" not in name
    ]
    if unfrozen_base:
        raise RuntimeError("QLoRA expected frozen base weights and LoRA-only trainable parameters")
    frozen_base_parameters = sum(
        parameter.numel() for name, parameter in model.named_parameters()
        if not parameter.requires_grad and "lora_" not in name
    )
    initial_free_vram = torch.cuda.mem_get_info()[0]
    step_times = []

    class Task3TrainingCallback(TrainerCallback):
        def __init__(self):
            self.started = None
            self.gradient_audit = {"checked": False, "finite_nonzero_lora_gradient": False}
            self.lora_before_step = None
            self.parameter_update_audit = {
                "checked": False,
                "finite_nonzero_lora_update": False,
                "max_abs_delta": None,
            }

        def on_step_begin(self, args, state, control, **kwargs):
            torch.cuda.synchronize()
            self.started = time.perf_counter()

        def on_step_end(self, args, state, control, **kwargs):
            torch.cuda.synchronize()
            if self.started is not None:
                step_times.append(time.perf_counter() - self.started)
            torch.cuda.empty_cache()
            if self.lora_before_step is not None and not self.parameter_update_audit["checked"]:
                current = dict(model.named_parameters())
                deltas = [
                    (current[name].detach() - before).abs()
                    for name, before in self.lora_before_step.items()
                    if name in current
                ]
                finite = bool(deltas) and all(bool(torch.isfinite(delta).all()) for delta in deltas)
                nonzero = finite and any(bool(torch.count_nonzero(delta)) for delta in deltas)
                maximum_delta = max((float(delta.max().item()) for delta in deltas), default=0.0)
                self.parameter_update_audit = {
                    "checked": True,
                    "finite_nonzero_lora_update": bool(nonzero),
                    "max_abs_delta": maximum_delta,
                }
            return control

        def on_pre_optimizer_step(self, args, state, control, model=None, **kwargs):
            gradients = [
                parameter.grad
                for name, parameter in model.named_parameters()
                if "lora_" in name and parameter.requires_grad and parameter.grad is not None
            ]
            finite_nonzero = any(
                bool(torch.isfinite(gradient).all()) and bool(torch.count_nonzero(gradient))
                for gradient in gradients
            )
            self.gradient_audit = {
                "checked": True,
                "finite_nonzero_lora_gradient": finite_nonzero,
                "trainable_lora_tensors_with_gradient": len(gradients),
            }
            if smoke_test and self.lora_before_step is None:
                self.lora_before_step = {
                    name: parameter.detach().clone()
                    for name, parameter in model.named_parameters()
                    if "lora_" in name and parameter.requires_grad
                }
            if smoke_test and not finite_nonzero:
                raise RuntimeError("GPU smoke test found no finite nonzero LoRA gradient")
            return control

        def on_save(self, args, state, control, **kwargs):
            checkpoint_path = Path(args.output_dir) / f"checkpoint-{state.global_step}"
            if checkpoint_path.is_dir():
                write_json(checkpoint_path / "task3_resume_metadata.json", checkpoint_metadata)
            return control

    arguments = {
        "output_dir": str(output),
        "seed": config.get("seed", 42),
        "data_seed": config.get("seed", 42),
        "learning_rate": config.get("learning_rate", 1e-4),
        "lr_scheduler_type": config.get("lr_scheduler_type", "linear"),
        "warmup_ratio": config.get("warmup_ratio", 0.0),
        "warmup_steps": config.get("warmup_steps", 0),
        "num_train_epochs": config.get("epochs", 3),
        "max_steps": max_steps if max_steps is not None else -1,
        "per_device_train_batch_size": config.get("per_device_train_batch_size", 1),
        "per_device_eval_batch_size": config.get("per_device_eval_batch_size", 1),
        "gradient_accumulation_steps": config.get("gradient_accumulation_steps", 4),
        "gradient_checkpointing": True,
        "gradient_checkpointing_kwargs": {"use_reentrant": False},
        "bf16": bf16,
        "fp16": not bf16,
        "optim": config.get("optim", "paged_adamw_8bit"),
        "eval_strategy": config.get("eval_strategy", "epoch"),
        "save_strategy": config.get("save_strategy", "epoch"),
        "logging_steps": config.get("logging_steps", 1),
        "save_total_limit": config.get("save_total_limit", 2),
        "report_to": [],
        "load_best_model_at_end": config.get("load_best_model_at_end", True),
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
        "push_to_hub": False,
    }
    if arguments["eval_strategy"] == "steps" or arguments["save_strategy"] == "steps":
        arguments["eval_steps"] = config.get("eval_steps", 20)
        arguments["save_steps"] = config.get("save_steps", arguments["eval_steps"])
    args = TrainingArguments(**arguments)
    callback = Task3TrainingCallback()
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=Dataset.from_list(train_rows),
        eval_dataset=Dataset.from_list(val_rows),
        data_collator=CompletionCollator(tokenizer.pad_token_id),
        processing_class=tokenizer,
        callbacks=[callback],
    )
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    result.update(
        tokenizer=tokenizer_metadata(tokenizer),
        gpu_preflight=gpu_audit,
        max_seq_length=max_length,
        token_audit={"train": train_audit, "val": val_audit},
        precision="bf16" if bf16 else "fp16",
        tokenization_time_s=tokenization_time,
        model_load_time_s=model_load_time,
        sampled_source_exposures=sampled_exposures,
        sampled_histograms=source_level_counts,
        effective_samples_per_epoch=len(train_rows),
        effective_optimizer_steps=max_steps
        or math.ceil(
            len(train_rows)
            / (arguments["per_device_train_batch_size"] * arguments["gradient_accumulation_steps"])
        )
        * arguments["num_train_epochs"],
        trainable_parameters=trainable_parameters,
        frozen_base_parameters=frozen_base_parameters,
        free_vram_at_start_bytes=initial_free_vram,
    )
    write_json(output / "run-start.json", result)
    try:
        trained = trainer.train(resume_from_checkpoint=str(resume_from_checkpoint) if resume_from_checkpoint else None)
        metrics = trainer.evaluate()
        trainer.save_model(str(output / "adapter"))
        tokenizer.save_pretrained(output / "adapter")
        torch.cuda.synchronize()
        steps_completed = int(trainer.state.global_step)
        mean_step = statistics.mean(step_times) if step_times else None
        p50_step = statistics.median(step_times) if step_times else None
        p95_step = float(np.percentile(step_times, 95)) if step_times else None
        supervised_tokens_per_epoch = sum(
            sum(label != -100 for label in row["labels"]) for row in train_rows
        )
        duration = sum(step_times)
        samples_per_step = (
            arguments["per_device_train_batch_size"] * arguments["gradient_accumulation_steps"]
        )
        average_supervised_tokens_per_sample = supervised_tokens_per_epoch / len(train_rows)
        throughput = _session_throughput(
            steps_completed,
            resume_step,
            step_times,
            samples_per_step,
            average_supervised_tokens_per_sample,
        )
        result.update(
            status="COMPLETE",
            training_succeeded=True,
            stage_name=config.get("stage_name", "single-stage"),
            learning_rate=config.get("learning_rate", 1e-4),
            train_metrics=trained.metrics,
            validation_metrics=metrics,
            loss_history=trainer.state.log_history,
            checkpoint_path=str(output / "adapter"),
            optimizer_steps=steps_completed,
            **throughput,
            step_time_mean_s=mean_step,
            step_time_p50_s=p50_step,
            step_time_p95_s=p95_step,
            samples_per_second=throughput["session_samples_per_second"],
            supervised_tokens_per_second=throughput["session_supervised_tokens_per_second"],
            optimizer_step_wall_time_s=duration,
            peak_gpu_memory_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_gpu_memory_reserved_bytes=torch.cuda.max_memory_reserved(),
            gradient_audit=callback.gradient_audit,
            parameter_update_audit=callback.parameter_update_audit,
        )
        if smoke_test:
            if steps_completed != max_steps:
                raise RuntimeError("GPU smoke stopped before the requested optimizer-step limit")
            if not callback.gradient_audit["checked"] or not callback.gradient_audit["finite_nonzero_lora_gradient"]:
                raise RuntimeError("GPU smoke did not verify a finite nonzero LoRA gradient")
            if (
                not callback.parameter_update_audit["checked"]
                or not callback.parameter_update_audit["finite_nonzero_lora_update"]
            ):
                raise RuntimeError("GPU smoke did not verify a finite nonzero LoRA parameter update")
            if not math.isfinite(float(trained.metrics["train_loss"])):
                raise RuntimeError("GPU smoke produced a non-finite training loss")
            train_peak_allocated = result["peak_gpu_memory_allocated_bytes"]
            train_peak_reserved = result["peak_gpu_memory_reserved_bytes"]
            del trainer, model
            import gc

            gc.collect()
            torch.cuda.empty_cache()
            result["adapter_reload_smoke"] = _adapter_reload_smoke(
                config, quant, tokenizer, val[0], PeftModel
            )
            torch.cuda.synchronize()
            result["peak_gpu_memory_allocated_bytes"] = max(
                train_peak_allocated, torch.cuda.max_memory_allocated()
            )
            result["peak_gpu_memory_reserved_bytes"] = max(
                train_peak_reserved, torch.cuda.max_memory_reserved()
            )
    except Exception as exc:
        failed_step = steps_completed if "steps_completed" in locals() else int(trainer.state.global_step)
        result.update(
            status="FAILED",
            training_succeeded=False,
            error_type=type(exc).__name__,
            failed_optimizer_step=failed_step,
            failure_config_sha256=checkpoint_metadata["config_sha256"],
            failure_data_manifest_sha256=data_manifest_sha256,
            free_vram_at_failure_bytes=_free_vram_or_none(torch),
        )
        raise
    finally:
        result["wall_time_s"] = time.perf_counter() - start
        if torch.cuda.is_available():
            result.setdefault("peak_gpu_memory_allocated_bytes", torch.cuda.max_memory_allocated())
            result.setdefault("peak_gpu_memory_reserved_bytes", torch.cuda.max_memory_reserved())
        write_json(output / "run.json", result)
    return result


def _adapter_reload_smoke(config, quant, tokenizer, record, peft_model_class):
    import torch
    from transformers import AutoModelForCausalLM

    torch.cuda.synchronize()
    adapter_dir = Path(config.get("output_dir", "checkpoints/task3/qlora")) / "adapter"
    device_map = config.get("device_map")
    if device_map is None:
        device_map = "auto" if torch.cuda.device_count() > 1 else {"": torch.cuda.current_device()}
    base = AutoModelForCausalLM.from_pretrained(
        config["model_id"],
        revision=config["revision"],
        trust_remote_code=False,
        quantization_config=quant,
        device_map=device_map,
        dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    )
    model = peft_model_class.from_pretrained(base, adapter_dir, is_trainable=False)
    model.eval()
    prompt = budget_prompt(
        record,
        record.gold_taxonomy,
        tokenizer,
        config.get("context_limit", 4096),
        8,
    )
    inputs = tokenizer.apply_chat_template(
        prompt.messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    ).to(model.device)
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=8, do_sample=False)
    torch.cuda.synchronize()
    return {
        "status": "PASS",
        "generated_tokens": int(output.shape[-1] - inputs["input_ids"].shape[-1]),
        "peak_gpu_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
    }
