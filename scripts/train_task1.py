"""Train Task 1 QLoRA on gold by default; retain optional silver comparison."""

from __future__ import annotations

import argparse
import gc
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.task1.finetune import (
    best_epoch, choose_variant, encode_inference_prompt, encode_training_record,
    evaluate_generations, load_silver_records, load_task1_splits,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/task1/lora_7b.yaml")
    parser.add_argument("--processed-dir", type=Path)
    parser.add_argument("--splits-dir", type=Path)
    parser.add_argument("--silver-processed-dir", type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument(
        "--stage", choices=("gold_only_complete", "all", "gold_only", "silver_then_gold", "select"),
        default="gold_only_complete",
        help="gold_only_complete = train/evaluate gold and save the best adapter (default); "
             "all = both arms + selection. On a 16 GB GPU run gold_only, "
             "silver_then_gold and select as separate processes so each arm's GPU memory is fully released.",
    )
    return parser.parse_args()


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _checkpoints(path: Path) -> list[Path]:
    return sorted(path.glob("checkpoint-*"), key=lambda p: int(p.name.rsplit("-", 1)[1]))


def run(args: argparse.Namespace) -> dict:
    import yaml
    from transformers import AutoTokenizer

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    model_name = cfg["model"]
    processed = args.processed_dir or Path(cfg["data"]["processed_dir"])
    splits = args.splits_dir or Path(cfg["data"]["splits_dir"])
    output = args.output_dir or Path(cfg["output_dir"])
    if args.smoke:
        output = output / "smoke"
    gold_train, gold_val = load_task1_splits(
        processed, splits, expected_train=cfg["data"]["expected_train"],
        expected_val=cfg["data"]["expected_val"],
    )
    use_silver = args.stage in ("all", "silver_then_gold", "select")
    silver_manifest = None
    silver = []
    if use_silver:
        if args.silver_processed_dir is None:
            raise ValueError("--silver-processed-dir is required for silver comparison stages")
        silver_manifest = json.loads(
            (args.silver_processed_dir / "silver_manifest.json").read_text(encoding="utf-8")
        )
        silver = load_silver_records(
            args.silver_processed_dir / "task1_silver_train.jsonl", gold_train + gold_val,
            expected=silver_manifest["n_accepted"],
        )
        if not silver_manifest.get("gold_public_overlap_checked"):
            raise ValueError("Silver source was not checked against gold/public")

    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    training = cfg["training"]
    max_length = int(training["max_length"])
    max_new_tokens = int(cfg["generation"]["max_new_tokens"])
    gold_rows = [encode_training_record(rec, tokenizer, max_length) for rec in gold_train]
    silver_rows = [encode_training_record(rec, tokenizer, max_length) for rec in silver]
    prompt_sizes = [len(encode_inference_prompt(rec, tokenizer, max_length)) for rec in gold_val]
    if max(prompt_sizes) + max_new_tokens > max_length:
        raise ValueError("Gold validation prompt plus generation budget exceeds max_length")
    preflight = {
        "model": model_name, "gold_train_records": len(gold_train),
        "gold_val_records": len(gold_val), "silver_train_records": len(silver),
        "max_gold_tokens": max(row["total_tokens"] for row in gold_rows),
        "max_silver_tokens": max((row["total_tokens"] for row in silver_rows), default=None),
        "max_val_prompt_tokens": max(prompt_sizes), "max_length": max_length,
        "smoke": args.smoke,
    }
    print(json.dumps(preflight, ensure_ascii=False, indent=2), flush=True)
    if args.preflight:
        return preflight

    import peft
    import torch
    import transformers
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, Trainer, TrainingArguments

    if not torch.cuda.is_available():
        raise RuntimeError("QLoRA training requires a Colab CUDA GPU")
    done = {p.name for p in output.iterdir()} - {"smoke"} if output.exists() else set()
    clash = {"gold_only_complete": done - {"training_config.json", "source_manifest.json"},
             "all": done - {"training_config.json", "silver_manifest.json", "source_manifest.json"},
             "gold_only": done & {"gold_only"}, "silver_then_gold": done & {"silver_then_gold"},
             "select": done & {"best_adapter", "training_summary.json"}}[args.stage]
    if clash:
        raise FileExistsError(f"Output already contains {sorted(clash)}: {output}; use a fresh directory")
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "training_config.json", cfg)
    if silver_manifest is not None:
        _write(output / "silver_manifest.json", silver_manifest)
    if args.source_manifest:
        shutil.copy2(args.source_manifest, output / "source_manifest.json")

    quantization = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )

    def clear_gpu():
        gc.collect()
        torch.cuda.empty_cache()

    def load_base():
        return AutoModelForCausalLM.from_pretrained(
            model_name, quantization_config=quantization, device_map="auto",
            torch_dtype=torch.float16,
        )

    def fresh_model():
        torch.manual_seed(int(cfg["seed"]))
        torch.cuda.manual_seed_all(int(cfg["seed"]))
        base = load_base()
        base.config.use_cache = False
        base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True)
        return get_peft_model(base, LoraConfig(
            r=int(training["lora_r"]), lora_alpha=int(training["lora_alpha"]),
            lora_dropout=float(training["lora_dropout"]), bias="none", task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        ))

    class TrainingDataset:
        def __init__(self, rows):
            self.rows = rows[:1] if args.smoke else rows

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, index):
            return {key: self.rows[index][key] for key in ("input_ids", "attention_mask", "labels")}

    def collate(rows):
        width = max(len(row["input_ids"]) for row in rows)
        pad = tokenizer.pad_token_id
        return {
            "input_ids": torch.tensor(
                [row["input_ids"] + [pad] * (width - len(row["input_ids"])) for row in rows]
            ),
            "attention_mask": torch.tensor(
                [row["attention_mask"] + [0] * (width - len(row["attention_mask"])) for row in rows]
            ),
            "labels": torch.tensor(
                [row["labels"] + [-100] * (width - len(row["labels"])) for row in rows]
            ),
        }

    def train_stage(model, rows, stage_dir: Path, *, epochs: int, lr: float) -> list[Path]:
        stage_dir.mkdir(parents=True, exist_ok=False)
        stage_args = TrainingArguments(
            output_dir=str(stage_dir), num_train_epochs=epochs,
            max_steps=1 if args.smoke else -1,
            per_device_train_batch_size=int(training["batch_size"]),
            gradient_accumulation_steps=1 if args.smoke else int(training["gradient_accumulation_steps"]),
            learning_rate=lr, warmup_ratio=float(training["warmup_ratio"]),
            lr_scheduler_type="cosine", optim="paged_adamw_8bit", fp16=True, bf16=False,
            gradient_checkpointing=True, save_strategy="steps" if args.smoke else "epoch",
            save_steps=1 if args.smoke else 500, save_total_limit=1 if args.smoke else epochs,
            logging_steps=1, report_to="none", remove_unused_columns=False,
            dataloader_num_workers=0, seed=int(cfg["seed"]), data_seed=int(cfg["seed"]),
        )
        trainer = Trainer(
            model=model, args=stage_args, train_dataset=TrainingDataset(rows), data_collator=collate
        )
        trainer.train()
        paths = _checkpoints(stage_dir)
        if len(paths) != (1 if args.smoke else epochs):
            raise RuntimeError(f"Expected {epochs} checkpoint(s) at {stage_dir}; found {paths}")
        del trainer  # New Trainer at the stage boundary creates a fresh optimizer.
        clear_gpu()
        return paths

    # Comparison arms begin from the same base weights and random seed.
    if args.stage in ("gold_only_complete", "all", "gold_only"):
        baseline_model = fresh_model()
        baseline_ckpts = train_stage(
            baseline_model, gold_rows, output / "gold_only" / "gold",
            epochs=int(training["epochs"]), lr=float(training["learning_rate"]),
        )
        del baseline_model
        clear_gpu()

    if args.stage in ("all", "silver_then_gold"):
        silver_model = fresh_model()
        silver_ckpts = train_stage(
            silver_model, silver_rows, output / "silver_then_gold" / "silver",
            epochs=int(training["silver_epochs"]), lr=float(training["silver_learning_rate"]),
        )
        silver_gold_ckpts = train_stage(
            silver_model, gold_rows, output / "silver_then_gold" / "gold",
            epochs=int(training["epochs"]), lr=float(training["learning_rate"]),
        )
        del silver_model
        clear_gpu()

    if args.stage in ("gold_only", "silver_then_gold"):
        return {"stage": args.stage, "output": str(output), "data": preflight}
    if args.stage == "select":  # arms were trained by earlier processes: read their checkpoints from disk
        n_gold, n_silver = (1, 1) if args.smoke else (int(training["epochs"]), int(training["silver_epochs"]))
        baseline_ckpts = _checkpoints(output / "gold_only" / "gold")
        silver_ckpts = _checkpoints(output / "silver_then_gold" / "silver")
        silver_gold_ckpts = _checkpoints(output / "silver_then_gold" / "gold")
        if (len(baseline_ckpts), len(silver_ckpts), len(silver_gold_ckpts)) != (n_gold, n_silver, n_gold):
            raise RuntimeError("--stage select needs both arms trained first (gold_only, silver_then_gold)")

    eval_records = gold_val[:1] if args.smoke else gold_val
    eval_base = load_base()
    eval_base.config.use_cache = True
    eval_model = None
    previous_adapter = None

    def evaluate_arm(name: str, checkpoints: list[Path]) -> dict:
        nonlocal eval_model, previous_adapter
        results = []
        for epoch, checkpoint in enumerate(checkpoints, 1):
            adapter_name = f"{name}_{epoch}"
            if eval_model is None:
                eval_model = PeftModel.from_pretrained(
                    eval_base, str(checkpoint), is_trainable=False, adapter_name=adapter_name
                )
            else:
                eval_model.load_adapter(str(checkpoint), adapter_name=adapter_name, is_trainable=False)
            eval_model.set_adapter(adapter_name)
            if previous_adapter:
                eval_model.delete_adapter(previous_adapter)
            previous_adapter = adapter_name
            eval_model.eval()
            raw_by_id = {}
            for rec in eval_records:
                ids = encode_inference_prompt(rec, tokenizer, max_length)
                input_ids = torch.tensor([ids], device="cuda")
                with torch.inference_mode():
                    generated = eval_model.generate(
                        input_ids=input_ids, attention_mask=torch.ones_like(input_ids),
                        do_sample=False, max_new_tokens=max_new_tokens,
                        pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id,
                    )
                raw_by_id[rec.sample_id] = tokenizer.decode(
                    generated[0][len(ids):], skip_special_tokens=True
                )
            metrics, details = evaluate_generations(eval_records, raw_by_id)
            epoch_dir = output / name / f"epoch_{epoch}"
            _write(epoch_dir / "metrics.json", metrics)
            _write(epoch_dir / "validation_predictions.json", details)
            results.append({
                "variant": name, "epoch": epoch, "checkpoint": str(checkpoint), "metrics": metrics
            })
            print(f"{name} epoch {epoch}: QWK={metrics['qwk']:.4f} MAE={metrics['mae']:.4f}", flush=True)
        selected = best_epoch(results)
        _write(output / name / "validation_report.json", {
            "selected": selected, "all_epochs": results
        })
        return selected

    baseline_best = evaluate_arm("gold_only", baseline_ckpts)
    silver_best = evaluate_arm("silver_then_gold", silver_gold_ckpts) if use_silver else None
    chosen = choose_variant(baseline_best, silver_best) if silver_best else baseline_best
    del eval_model, eval_base
    clear_gpu()

    best_dir = output / "best_adapter"
    best_dir.mkdir()
    for name in ("adapter_config.json", "adapter_model.safetensors", "adapter_model.bin"):
        source = Path(chosen["checkpoint"]) / name
        if source.is_file():
            shutil.copy2(source, best_dir / name)
    if not (best_dir / "adapter_config.json").is_file() or not any(best_dir.glob("adapter_model.*")):
        raise RuntimeError("Selected checkpoint lacks LoRA adapter weights")
    tokenizer.save_pretrained(best_dir)
    summary = {
        "model": model_name, "seed": cfg["seed"], "selected_variant": chosen["variant"],
        "selected_epoch": chosen["epoch"], "selected_metrics": chosen["metrics"],
        "gold_only_best": baseline_best, "silver_then_gold_best": silver_best,
        "silver_stage_checkpoint": str(silver_ckpts[-1]) if silver_best else None,
        "data": preflight,
        "versions": {
            "torch": torch.__version__, "transformers": transformers.__version__,
            "peft": peft.__version__,
        },
    }
    _write(output / "training_summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), ensure_ascii=False, indent=2), flush=True)
