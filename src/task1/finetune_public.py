"""CPU-only contracts for public inference with the selected Task 1 adapter."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

from src.data.loader import Dataset
from src.data.prompts import build_task1_messages
from src.task1.evaluator import validate_predictions
from src.task1.finetune import choose_variant, parse_generated_score
from src.task1.public_predict import _digest, _source_commit, _write_atomic, inspect_public


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_adapter(training_run: str | Path) -> dict:
    """Require the validation winner; never fall back to the base or last epoch."""
    root = Path(training_run).resolve()
    summary = json.loads((root / "training_summary.json").read_text(encoding="utf-8"))
    config = json.loads((root / "training_config.json").read_text(encoding="utf-8"))
    if summary.get("data", {}).get("smoke") or root.name == "smoke":
        raise ValueError("Select a completed full training run, not a smoke run")
    silver_best = summary.get("silver_then_gold_best")
    chosen = choose_variant(summary["gold_only_best"], silver_best) if silver_best else summary["gold_only_best"]
    if (summary["selected_variant"], summary["selected_epoch"]) != (chosen["variant"], chosen["epoch"]):
        raise ValueError("training_summary.json does not identify the gold-validation winner")
    adapter = root / "best_adapter"
    adapter_config = json.loads((adapter / "adapter_config.json").read_text(encoding="utf-8"))
    model = summary["model"]
    if config["model"] != model or adapter_config["base_model_name_or_path"] != model:
        raise ValueError("Adapter, training config, and summary disagree on the base model")
    weights = [p for p in (adapter / "adapter_model.safetensors", adapter / "adapter_model.bin") if p.is_file()]
    if len(weights) != 1:
        raise ValueError("best_adapter must contain exactly one adapter weight file")
    weight_hash = file_sha256(weights[0])
    # The original checkpoint may have an old /content path after copying a run.
    # Rebase its relative stage/checkpoint path to the selected run when possible.
    checkpoint = Path(chosen["checkpoint"])
    copied_checkpoint = root / chosen["variant"] / "gold" / checkpoint.name
    if copied_checkpoint.is_dir():
        checkpoint = copied_checkpoint
    original = checkpoint / weights[0].name
    if original.is_file() and file_sha256(original) != weight_hash:
        raise ValueError("best_adapter weights differ from the selected epoch checkpoint")
    return {
        "training_run": str(root), "adapter_dir": str(adapter), "model": model,
        "selected_variant": chosen["variant"], "selected_epoch": chosen["epoch"],
        "validation_metrics": chosen["metrics"], "training_config": config,
        "adapter_sha256": weight_hash, "adapter_config_sha256": file_sha256(adapter / "adapter_config.json"),
        "checkpoint_verified": original.is_file(),
    }


def public_messages(dataset: Dataset, sample) -> list[dict[str, str]]:
    """Use the fine-tuning prompt, including the same exam policy and test report."""
    exam = dataset.exams[sample.exam_id]
    context = SimpleNamespace(
        **vars(sample), exam_statement=exam["statement"], grading_policy=exam.get("grading_policy"),
        rubric=None, total_score=None,
    )
    messages, _ = build_task1_messages(context, dataset.label_space)
    return messages[:2]


def prepare_public(dataset: Dataset, tokenizer, max_length: int, max_new_tokens: int) -> tuple[dict, dict]:
    report = inspect_public(dataset)
    if max_new_tokens <= 0 or max_length <= max_new_tokens:
        raise ValueError("Invalid context/generation token budgets")
    inputs = {}
    too_long = []
    for sample in sorted(dataset.samples, key=lambda s: s.sample_id):
        ids = tokenizer.apply_chat_template(
            public_messages(dataset, sample), tokenize=True, add_generation_prompt=True,
        )
        inputs[sample.sample_id] = ids
        if len(ids) + max_new_tokens > max_length:
            too_long.append({"sample_id": sample.sample_id, "prompt_tokens": len(ids)})
    if too_long:
        raise ValueError(
            f"{len(too_long)} public prompts exceed max_length={max_length} with "
            f"max_new_tokens={max_new_tokens}; no code is truncated. Examples: {too_long[:8]}. "
            "Increase --max-length explicitly within the model context limit."
        )
    report.update({"max_prompt_tokens": max(map(len, inputs.values())),
                   "max_length": max_length, "max_new_tokens": max_new_tokens})
    return inputs, report


def predict_finetuned_public(dataset: Dataset, inputs: dict, selection: dict, generate,
                             out_root: str | Path, generation: dict, selected_ids: list[str] | None = None) -> dict:
    """Persist valid generations and export only a complete public submission.

    `generate(token_ids)` returns (raw_text, generated_token_count). No API prompt
    repair or API scoring rules are applied to the fine-tuned model's output.
    """
    inspect_public(dataset)
    expected = sorted(dataset.by_id())
    chosen = expected if selected_ids is None else selected_ids
    if not chosen or len(chosen) != len(set(chosen)) or set(chosen) - set(expected):
        raise ValueError("Selected IDs must be distinct public sample IDs")
    if set(inputs) != set(expected):
        raise ValueError("Tokenized inputs do not cover the public release")
    source_commit = _source_commit()
    release_key = _digest({"inputs": inputs})[:16]
    config_key = _digest({"selection": selection, "generation": generation,
                          "source_commit": source_commit, "release_key": release_key})
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "-", selection["model"])
    experiment = f"{Path(selection['training_run']).name}__{selection['selected_variant']}__epoch_{selection['selected_epoch']}"
    out = Path(out_root) / "public" / "peft" / safe_model / experiment / config_key[:16]
    checkpoints = out / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    _write_atomic(out / "config.json", {"selection": selection, "generation": generation,
                                        "source_commit": source_commit, "config_sha256": config_key})
    done = {}
    saved_rows = {}
    for sid in expected:
        path = checkpoints / f"{sid}.json"
        if not path.exists():
            continue
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            parsed, _, _ = parse_generated_score(saved["raw_output"])
            row = saved["submission"]
            if (saved["key"] == config_key and parsed == row["output"]
                    and not validate_predictions([row], [sid])):
                done[sid], saved_rows[sid] = row, saved
        except (KeyError, TypeError, ValueError):
            pass
    errors = []
    stopped = None
    try:
        for index, sid in enumerate(chosen, 1):
            if sid in done:
                continue
            raw, output_tokens = generate(inputs[sid])
            pred, json_ok, strict_ok = parse_generated_score(raw)
            detail = {"key": config_key, "sample_id": sid, "raw_output": raw,
                      "json_ok": json_ok, "strict_output_ok": strict_ok,
                      "input_tokens": len(inputs[sid]), "output_tokens": output_tokens}
            row = {"sample_id": sid, "output": pred}
            if pred is None or validate_predictions([row], [sid]):
                errors.append({"sample_id": sid, "error": "invalid_generated_score"})
                _write_atomic(out / "invalid_outputs" / f"{sid}.json", detail)
            else:
                detail["submission"] = row
                _write_atomic(checkpoints / f"{sid}.json", detail)
                done[sid], saved_rows[sid] = row, detail
                (out / "invalid_outputs" / f"{sid}.json").unlink(missing_ok=True)
            print(f"[{index}/{len(chosen)}] {sid}: {'OK' if sid in done else 'INVALID'} | {len(done)}/{len(expected)}", flush=True)
    except KeyboardInterrupt:
        stopped = "Interrupted; rerun to resume from valid checkpoints"
    except Exception as exc:
        stopped = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        missing = sorted(set(expected) - set(done))
        submission = out / "predictions.json"
        if not missing:
            rows = [done[sid] for sid in expected]
            problems = validate_predictions(rows, expected)
            if problems:
                raise ValueError(f"Submission validation failed: {problems[:5]}")
            _write_atomic(submission, rows)
        else:
            submission.unlink(missing_ok=True)
        report = {
            "provider": "peft", "model": selection["model"], "experiment": experiment,
            "source_commit": source_commit, "release_key": release_key,
            "selected_variant": selection["selected_variant"], "selected_epoch": selection["selected_epoch"],
            "adapter_dir": selection["adapter_dir"], "adapter_sha256": selection["adapter_sha256"],
            "config_sha256": config_key, "expected": len(expected), "completed": len(done),
            "missing_ids": missing, "errors": errors, "stopped": stopped,
            "selected_ids": selected_ids, "selected_completed": sum(sid in done for sid in chosen),
            "n_normalized_total": sum(not row["strict_output_ok"] for row in saved_rows.values()),
            "submission_path": str(submission) if not missing else None, "run_dir": str(out),
        }
        _write_atomic(out / "progress.json", report)
        _write_atomic(out / "predictions_full.json", [saved_rows[sid] for sid in sorted(saved_rows)])
        usage = "".join(json.dumps({"sample_id": sid, "input_tokens": row["input_tokens"],
                                    "output_tokens": row["output_tokens"]}) + "\n"
                        for sid, row in sorted(saved_rows.items()))
        (out / "usage.jsonl").write_text(usage, encoding="utf-8")
    return report
