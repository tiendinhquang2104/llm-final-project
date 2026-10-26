"""One opt-in QLoRA trajectory with completion-only loss and exact recovery."""
from __future__ import annotations

from collections import Counter
import math
import os
from pathlib import Path
import random
import shutil
import time
import traceback

from src.task3.direct_sft_training import encode_direct_examples, audit_unadapted_base, evaluate_internal
from src.task3.pilot_training import (WeightedCompletionCollator, weighted_completion_loss,
                                      claim_optimizer_start, _model_precision_audit)
from src.task3.r15_abc_experiment import (execution_identity, read_json, write_json, sha_file,
                                         verify_file_hashes, adapter_identity, historical_module, append_event, jsonl)


def encode_train_rows(tokenizer, examples, max_length):
    return encode_direct_examples(tokenizer, examples, max_length)


def audit_trainable(model):
    trainable = {n: p for n, p in model.named_parameters() if p.requires_grad}
    if not trainable or any("lora_" not in n for n in trainable):
        raise ValueError("only LoRA may be trainable; base must remain frozen")
    return {"trainable_parameters": sum(p.numel() for p in trainable.values()),
            "trainable_tensors": len(trainable),
            "trainable_dtype_elements": dict(Counter({dtype: sum(p.numel() for p in trainable.values() if str(p.dtype) == dtype)
                                                       for dtype in {str(p.dtype) for p in trainable.values()}})),
            "norm_dtypes": sorted({str(p.dtype) for n, p in model.named_parameters() if "norm" in n}),
            "base_frozen": True}


def step_budget(examples, accumulation=4):
    if type(examples) is not int or examples <= 0 or type(accumulation) is not int or accumulation <= 0:
        raise ValueError("positive example and accumulation counts required")
    total = math.ceil(examples / accumulation)
    return {"optimizer_steps": total, "checkpoint_steps": sorted({math.ceil(total / 2), total})}


def validate_recovery(state, identity):
    required = {"identity", "step", "cursor", "order", "adapter", "optimizer", "scheduler", "rng"}
    if not required <= set(state) or state["identity"] != identity:
        raise ValueError("recovery identity or complete state mismatch")
    if not {"python", "numpy", "torch", "cuda"} <= set(state["rng"]):
        raise ValueError("recovery requires every RNG state")
    if type(state["step"]) is not int or not 0 < state["step"] or not 0 < state["cursor"] <= len(state["order"]):
        raise ValueError("invalid recovery step/cursor")
    return state


def require_recovery_boundary(metadata, intent):
    if intent != {"identity": metadata["identity"], "step": metadata["step"]}:
        raise ValueError("optimizer step may have advanced beyond exact recovery; C incomplete")


def aggregate_training_costs(events):
    return {"invocations": len(events), "wall_s": sum(e["wall_s"] for e in events),
            "peak_allocated": max((e["peak_allocated"] for e in events), default=0),
            "peak_reserved": max((e["peak_reserved"] for e in events), default=0)}


def rng_state():
    import numpy as np
    import torch
    return dict(python=random.getstate(), numpy=np.random.get_state(), torch=torch.get_rng_state(),
                cuda=torch.cuda.get_rng_state_all())


def restore_rng(state):
    import numpy as np
    import torch
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"].cpu())
    torch.cuda.set_rng_state_all([s.cpu() for s in state["cuda"]])


def train_c(freeze: dict, train_rows: list[dict], out: Path) -> dict:
    """No v1/v2 trainer or validator is invoked. No implicit restart is allowed."""
    out = Path(out)
    config = freeze["config"]
    if freeze.get("arm_data", {}).get("C", {}).get("status", "ready") != "ready":
        result = {"status": "data_blocked", "reason": freeze["arm_data"]["C"]["reason"], "optimizer_started": False}
        write_json(out / "training-result.json", result)
        return result
    recipe = config["training"]
    if (recipe["epochs"] != 1 or recipe["learning_rate"] != 2e-5 or recipe["lora_r"] != 16
            or recipe["gradient_accumulation_steps"] != 4 or recipe["max_seq_length"] != 8192):
        raise ValueError("ABC frozen recipe mismatch")
    verify_file_hashes(freeze["files"])
    if execution_identity(train_rows) != freeze["train_examples_identity"]:
        raise ValueError("frozen training examples identity mismatch")
    marker = out / "optimizer-started.json"
    result_path = out / "training-result.json"
    identity = freeze["identity"]
    if result_path.exists() and read_json(result_path)["status"] == "complete":
        result = read_json(result_path)
        if result["identity"] != identity:
            raise ValueError("completed optimizer identity mismatch")
        for c in result["checkpoints"]:
            if adapter_identity(c["adapter_path"]) != c["adapter_identity"]:
                raise ValueError("completed adapter tensor identity mismatch")
        return result
    if marker.exists() and (not (out / "recovery.pt").exists() or not (out / "recovery.json").exists()):
        raise ValueError("optimizer already started; exact recovery state unavailable; C incomplete")
    os.environ["HF_HOME"] = config["hf_cache"]
    os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, get_cosine_schedule_with_warmup, set_seed
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1 or not torch.cuda.is_bf16_supported():
        raise RuntimeError("C requires exactly one BF16-capable CUDA GPU")
    set_seed(42)
    tokenizer = historical_module(config["runtime_out"], "task3.inference").load_tokenizer(config)
    rows, audit = encode_train_rows(tokenizer, train_rows, recipe["max_seq_length"])
    val_examples = read_json(Path(config["runtime_out"]) / "checkpoint-examples.private.json")
    val_rows, val_audit = encode_train_rows(tokenizer, val_examples, recipe["max_seq_length"])
    if {r["sample_id"] for r in rows} & {r["sample_id"] for r in val_rows}:
        raise ValueError("training/checkpoint source overlap")
    if audit != freeze["token_audit"]["train"] or val_audit != freeze["token_audit"]["validation"]:
        raise ValueError("frozen tokenizer/encoded tensor identity drift")
    budget = step_budget(len(rows))
    out.mkdir(parents=True, exist_ok=True)
    result = {"identity": identity, "status": "setup", "recipe": recipe, **budget,
              "token_audit": {"train": audit, "validation": val_audit}, "checkpoints": []}
    started = time.perf_counter()
    try:
        torch.cuda.reset_peak_memory_stats()
        base = AutoModelForCausalLM.from_pretrained(config["model_id"], revision=config["revision"],
            trust_remote_code=False, local_files_only=True, torch_dtype=torch.bfloat16,
            device_map={"": torch.cuda.current_device()},
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                   bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16))
        result["base_audit"] = audit_unadapted_base(base)
        result["precision"] = _model_precision_audit(base, config["revision"])
        base.config.use_cache = False
        base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True,
                                               gradient_checkpointing_kwargs={"use_reentrant": False})
        model = get_peft_model(base, LoraConfig(r=16, lora_alpha=32, lora_dropout=.05,
            target_modules=recipe["target_modules"], bias="none", task_type="CAUSAL_LM"))
        model.train()
        result["trainable_audit"] = audit_trainable(model)
        parameters = {n: p for n, p in model.named_parameters() if p.requires_grad}
        initial = {n: p.detach().cpu().clone() for n, p in parameters.items()}
        optimizer = torch.optim.AdamW(parameters.values(), lr=2e-5, weight_decay=0.)
        scheduler = get_cosine_schedule_with_warmup(optimizer, math.ceil(.03 * budget["optimizer_steps"]), budget["optimizer_steps"])
        collator = WeightedCompletionCollator(tokenizer.pad_token_id)
        order = list(range(len(rows)))
        random.Random(42).shuffle(order)
        cursor = step = 0
        exposures, losses = Counter(), []
        if marker.exists():
            metadata = read_json(out / "recovery.json")
            if metadata["sha256"] != sha_file(out / "recovery.pt") or read_json(marker)["identity"] != identity:
                raise ValueError("recovery file/optimizer marker identity mismatch")
            intent = read_json(out / "optimizer-step-intent.json")
            require_recovery_boundary(metadata, intent)
            state = validate_recovery(torch.load(out / "recovery.pt", map_location="cpu", weights_only=False), identity)
            if state["order"] != order or state["cursor"] != min(state["step"] * 4, len(rows)):
                raise ValueError("recovery exposure/order mismatch")
            with torch.no_grad():
                for name, p in parameters.items():
                    p.copy_(state["adapter"][name])
            optimizer.load_state_dict(state["optimizer"])
            scheduler.load_state_dict(state["scheduler"])
            cursor, step = state["cursor"], state["step"]
            exposures.update(state["exposures"])
            losses = state["losses"]
            result["checkpoints"] = state["checkpoints"]
            restore_rng(state["rng"])
        else:
            smoke_rng = rng_state()
            batch = collator([rows[0]])
            append_event(out / "forward-exposures.jsonl", {"kind": "smoke_not_optimizer", "example_id": rows[0]["example_id"],
                         "input_tokens": len(rows[0]["input_ids"]), "supervised_tokens": sum(v != -100 for v in rows[0]["labels"])})
            with torch.autocast("cuda", dtype=torch.bfloat16):
                output = model(input_ids=batch["input_ids"].cuda(), attention_mask=batch["attention_mask"].cuda(), use_cache=False)
                loss = weighted_completion_loss(output.logits, batch["labels"].cuda(), batch["loss_weight"].cuda())
            if not torch.isfinite(loss):
                raise RuntimeError("nonfinite smoke loss")
            loss.backward()
            grads = [p.grad for p in parameters.values() if p.grad is not None]
            if not grads or not all(bool(torch.isfinite(g).all()) for g in grads) or not any(bool(torch.count_nonzero(g)) for g in grads):
                raise RuntimeError("invalid smoke gradients")
            result["smoke"] = {"loss": float(loss.detach()), "optimizer_steps": 0,
                               "finite_nonzero_gradient": True, "rng_restored": True}
            optimizer.zero_grad(set_to_none=True)
            del output, loss, batch, grads
            restore_rng(smoke_rng)
            verify_file_hashes(freeze["files"])
            write_json(out / "smoke.json", result["smoke"])
            claim_optimizer_start(marker, {"identity": identity, "budget": budget})
        while cursor < len(order):
            subset = order[cursor:cursor + 4]
            optimizer.zero_grad(set_to_none=True)
            batch_losses = []
            for i in subset:
                batch = collator([rows[i]])
                append_event(out / "forward-exposures.jsonl", {"kind": "optimizer_microbatch_reserved", "step": step + 1,
                             "example_id": rows[i]["example_id"], "input_tokens": len(rows[i]["input_ids"]),
                             "supervised_tokens": sum(v != -100 for v in rows[i]["labels"])})
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    output = model(input_ids=batch["input_ids"].cuda(), attention_mask=batch["attention_mask"].cuda(), use_cache=False)
                    loss = weighted_completion_loss(output.logits, batch["labels"].cuda(), batch["loss_weight"].cuda())
                if not torch.isfinite(loss):
                    raise RuntimeError("training NaN/nonfinite loss")
                (loss / len(subset)).backward()
                batch_losses.append(float(loss.detach()))
                exposures[rows[i]["example_id"]] += 1
                del output, loss, batch
            grads = [p.grad for p in parameters.values() if p.grad is not None]
            if not grads or not all(bool(torch.isfinite(g).all()) for g in grads) or not any(bool(torch.count_nonzero(g)) for g in grads):
                raise RuntimeError("training nonfinite or zero gradients")
            norm = torch.nn.utils.clip_grad_norm_(list(parameters.values()), 1.)
            if not torch.isfinite(norm):
                raise RuntimeError("nonfinite gradient norm")
            write_json(out / "optimizer-step-intent.json", {"identity": identity, "step": step + 1})
            optimizer.step()
            scheduler.step()
            step += 1
            cursor += len(subset)
            losses.append({"step": step, "loss": sum(batch_losses) / len(batch_losses), "lr": scheduler.get_last_lr()[0]})
            if step in budget["checkpoint_steps"]:
                name = "final" if step == budget["optimizer_steps"] else "half"
                adapter = out / name / "adapter"
                model.save_pretrained(adapter, safe_serialization=True)
                tokenizer.save_pretrained(adapter)
                validation = evaluate_internal(model, val_rows, collator)
                result["checkpoints"].append({"name": name, "step": step, "adapter_path": str(adapter.resolve()),
                                               "adapter_identity": adapter_identity(adapter), "validation_loss": validation})
            recovery = dict(identity=identity, step=step, cursor=cursor, order=order,
                            adapter={n: p.detach().cpu() for n, p in parameters.items()},
                            optimizer=optimizer.state_dict(), scheduler=scheduler.state_dict(), rng=rng_state(),
                            exposures=dict(exposures), losses=losses, checkpoints=result["checkpoints"])
            temporary = out / "recovery.tmp.pt"
            torch.save(recovery, temporary)
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            temporary.replace(out / "recovery.pt")
            write_json(out / "recovery.json", {"identity": identity, "step": step, "sha256": sha_file(out / "recovery.pt")})
            if step in budget["checkpoint_steps"]:
                checkpoint = out / ("final" if step == budget["optimizer_steps"] else "half")
                shutil.copy2(out / "recovery.pt", checkpoint / "recovery.pt")
            print({"C_optimizer_step": step, "total": budget["optimizer_steps"], "loss": losses[-1]["loss"]}, flush=True)
        if exposures != Counter({r["example_id"]: 1 for r in rows}):
            raise RuntimeError("not exactly one exposure per frozen example")
        deltas = {n: float((p.detach().cpu() - initial[n]).abs().max()) for n, p in parameters.items()}
        if not all(math.isfinite(d) for d in deltas.values()) or not any(d > 0 for d in deltas.values()):
            raise RuntimeError("LoRA delta must be finite and nonzero")
        result.update(status="complete", actual_optimizer_steps=step, actual_example_exposures=dict(exposures),
                      loss_history=losses, max_abs_tensor_deltas=deltas)
    except Exception as exc:
        result.update(status="incomplete" if marker.exists() else "setup_failed", error=str(exc), traceback=traceback.format_exc())
        raise
    finally:
        event = {"identity": identity, "wall_s": time.perf_counter() - started, "status": result["status"],
                 "peak_allocated": torch.cuda.max_memory_allocated(), "peak_reserved": torch.cuda.max_memory_reserved()}
        append_event(out / "invocation-costs.jsonl", event)
        result.update(aggregate_training_costs(jsonl(out / "invocation-costs.jsonl")))
        result["forward_exposure_reservations"] = jsonl(out / "forward-exposures.jsonl")
        write_json(result_path, result)
    return result
