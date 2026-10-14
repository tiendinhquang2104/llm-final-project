"""Fine-tune Qwen2.5-Coder-7B-Instruct for Task 1 with 4-bit QLoRA.

The default run trains on the fixed 26/6 sample split. Use --smoke for a
single optimizer step and one validation generation before the full Colab run.
"""

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

from src.task1.finetune import (  # noqa: E402
    best_epoch,
    encode_inference_prompt,
    encode_training_record,
    evaluate_generations,
    load_task1_splits,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/task1/lora_7b.yaml")
    parser.add_argument("--processed-dir", type=Path, default=None)
    parser.add_argument("--splits-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--preflight", action="store_true", help="check data and token lengths without a GPU")
    parser.add_argument("--smoke", action="store_true", help="one optimizer step and one validation sample")
    return parser.parse_args()


def _json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _checkpoint_paths(output_dir: Path) -> list[Path]:
    return sorted(
        (p for p in output_dir.glob("checkpoint-*") if p.is_dir()),
        key=lambda p: int(p.name.rsplit("-", 1)[1]),
    )


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

    train, val = load_task1_splits(
        processed, splits,
        expected_train=cfg["data"]["expected_train"],
        expected_val=cfg["data"]["expected_val"],
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    max_length = int(cfg["training"]["max_length"])
    max_new_tokens = int(cfg["generation"]["max_new_tokens"])
    encoded = [encode_training_record(rec, tokenizer, max_length) for rec in train]
    prompt_sizes = [len(encode_inference_prompt(rec, tokenizer, max_length)) for rec in val]
    if max(prompt_sizes) + max_new_tokens > max_length:
        raise ValueError(
            f"Longest validation prompt ({max(prompt_sizes)}) plus max_new_tokens "
            f"({max_new_tokens}) exceeds max_length={max_length}"
        )
    preflight = {
        "model": model_name,
        "train_records": len(train), "val_records": len(val),
        "max_train_tokens": max(row["total_tokens"] for row in encoded),
        "max_val_prompt_tokens": max(prompt_sizes),
        "max_length": max_length,
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
        raise RuntimeError("QLoRA training requires a CUDA GPU; select a Colab GPU runtime")
    torch.manual_seed(int(cfg["seed"]))
    torch.cuda.manual_seed_all(int(cfg["seed"]))
    output.mkdir(parents=True, exist_ok=True)

    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )

    def load_base():
        return AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=quantization,
            device_map="auto",
            torch_dtype=torch.float16,
        )

    base = load_base()
    base.config.use_cache = False
    base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True)
    model = get_peft_model(
        base,
        LoraConfig(
            r=int(cfg["training"]["lora_r"]),
            lora_alpha=int(cfg["training"]["lora_alpha"]),
            lora_dropout=float(cfg["training"]["lora_dropout"]),
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        ),
    )

    class TrainingDataset:
        def __init__(self, rows):
            self.rows = rows

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, index):
            return {k: self.rows[index][k] for k in ("input_ids", "attention_mask", "labels")}

    def collate(rows):
        width = max(len(row["input_ids"]) for row in rows)
        pad = tokenizer.pad_token_id
        return {
            "input_ids": torch.tensor([r["input_ids"] + [pad] * (width - len(r["input_ids"])) for r in rows]),
            "attention_mask": torch.tensor([r["attention_mask"] + [0] * (width - len(r["attention_mask"])) for r in rows]),
            "labels": torch.tensor([r["labels"] + [-100] * (width - len(r["labels"])) for r in rows]),
        }

    training = cfg["training"]
    train_rows = encoded[:2] if args.smoke else encoded
    train_args = TrainingArguments(
        output_dir=str(output),
        num_train_epochs=int(training["epochs"]),
        max_steps=1 if args.smoke else -1,
        per_device_train_batch_size=int(training["batch_size"]),
        gradient_accumulation_steps=1 if args.smoke else int(training["gradient_accumulation_steps"]),
        learning_rate=float(training["learning_rate"]),
        warmup_ratio=float(training["warmup_ratio"]),
        lr_scheduler_type="cosine",
        optim="paged_adamw_8bit",
        fp16=True,
        bf16=False,
        gradient_checkpointing=True,
        save_strategy="steps" if args.smoke else "epoch",
        save_steps=1 if args.smoke else 500,
        save_total_limit=1 if args.smoke else int(training["epochs"]),
        logging_steps=1,
        report_to="none",
        remove_unused_columns=False,
        dataloader_num_workers=0,
        seed=int(cfg["seed"]),
        data_seed=int(cfg["seed"]),
    )
    trainer = Trainer(model=model, args=train_args, train_dataset=TrainingDataset(train_rows), data_collator=collate)
    trainer.train()
    checkpoints = _checkpoint_paths(output)
    if len(checkpoints) != (1 if args.smoke else int(training["epochs"])):
        raise RuntimeError(f"Expected epoch checkpoints; found {[p.name for p in checkpoints]}")
    del trainer, model, base
    gc.collect()
    torch.cuda.empty_cache()

    # Reload the quantized base once, then switch small per-epoch adapters.
    eval_base = load_base()
    eval_base.config.use_cache = True
    eval_model = None
    eval_records = val[:1] if args.smoke else val
    results = []
    for epoch, checkpoint in enumerate(checkpoints, 1):
        adapter_name = f"epoch_{epoch}"
        if eval_model is None:
            eval_model = PeftModel.from_pretrained(
                eval_base, str(checkpoint), is_trainable=False, adapter_name=adapter_name
            )
        else:
            eval_model.load_adapter(str(checkpoint), adapter_name=adapter_name, is_trainable=False)
        eval_model.set_adapter(adapter_name)
        eval_model.eval()
        raw_by_id = {}
        for rec in eval_records:
            ids = encode_inference_prompt(rec, tokenizer, max_length)
            input_ids = torch.tensor([ids], device="cuda")
            with torch.inference_mode():
                generated = eval_model.generate(
                    input_ids=input_ids,
                    attention_mask=torch.ones_like(input_ids),
                    do_sample=False,
                    max_new_tokens=max_new_tokens,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            raw_by_id[rec.sample_id] = tokenizer.decode(generated[0][len(ids) :], skip_special_tokens=True)
        metrics, details = evaluate_generations(eval_records, raw_by_id)
        epoch_dir = output / f"epoch_{epoch}"
        _json_write(epoch_dir / "metrics.json", metrics)
        _json_write(epoch_dir / "validation_predictions.json", details)
        results.append({"epoch": epoch, "checkpoint": str(checkpoint), "metrics": metrics})
        print(f"Epoch {epoch}: QWK={metrics['qwk']:.4f}, MAE={metrics['mae']:.4f}, "
              f"valid={metrics['valid_output_rate']:.2%}", flush=True)

    selected = best_epoch(results)
    best_dir = output / "best_adapter"
    best_dir.mkdir(parents=True, exist_ok=True)
    for name in ("adapter_config.json", "adapter_model.safetensors", "adapter_model.bin"):
        source = Path(selected["checkpoint"]) / name
        if source.is_file():
            shutil.copy2(source, best_dir / name)
    if not (best_dir / "adapter_config.json").is_file() or not any(best_dir.glob("adapter_model.*")):
        raise RuntimeError("Selected checkpoint did not contain LoRA adapter weights")
    tokenizer.save_pretrained(best_dir)
    summary = {
        "model": model_name, "seed": cfg["seed"], "selected_epoch": selected["epoch"],
        "selected_metrics": selected["metrics"], "all_epochs": results,
        "data": preflight,
        "versions": {"torch": torch.__version__, "transformers": transformers.__version__, "peft": peft.__version__},
    }
    _json_write(output / "training_summary.json", summary)
    _json_write(output / "training_config.json", cfg)
    return summary


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
