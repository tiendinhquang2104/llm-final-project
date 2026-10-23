"""Train Task 2 QLoRA adapter on Qwen2.5-Coder-7B-Instruct using completion-only SFT.

Takes data/processed/task2_sft_train.jsonl and saves fine-tuned LoRA adapter.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.prepare_task2_sft import truncate_middle

# Prevent multi-GPU pipeline memory imbalance on T4 x2 & eliminate fragmentation
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)


class TimeBudget(TrainerCallback):
    """Stop training once the time budget is used up, so the adapter is still saved and inference
    fits inside Kaggle's 12-hour session limit."""

    def __init__(self, hours):
        self.deadline = time.time() + hours * 3600

    def on_step_end(self, args, state, control, **kwargs):
        if time.time() > self.deadline:
            print(f"==> Time budget reached at step {state.global_step}/{state.max_steps}, stopping early.")
            control.should_training_stop = True


def encode_row(tokenizer, messages, max_length=2048):
    prompt = messages[:-1]
    prefix = tokenizer.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
    answer = full[len(prefix) :]
    prefix = truncate_middle(prefix, max_length - len(answer))
    full = prefix + answer
    labels = [-100] * len(prefix) + answer
    return {"input_ids": full, "attention_mask": [1] * len(full), "labels": labels}


class CompletionCollator:
    def __init__(self, pad_token_id):
        self.pad_token_id = pad_token_id

    def __call__(self, rows):
        size = max(len(r["input_ids"]) for r in rows)
        return {
            key: torch.tensor([r[key] + [pad] * (size - len(r[key])) for r in rows], dtype=torch.long)
            for key, pad in (("input_ids", self.pad_token_id), ("attention_mask", 0), ("labels", -100))
        }


class JsonlDataset(torch.utils.data.Dataset):
    def __init__(self, path: Path, tokenizer, max_length=2048):
        self.rows = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                self.rows.append(encode_row(tokenizer, rec["messages"], max_length))

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        return self.rows[idx]


def train(args):
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    device_map = {"": 0} if torch.cuda.is_available() else None

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        quantization_config=bnb_config,
        device_map=device_map,
        attn_implementation="sdpa",
        trust_remote_code=True,
    )
    model.config.pad_token_id = tokenizer.pad_token_id
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    dataset = JsonlDataset(Path(args.data_path), tokenizer, args.max_seq_len)
    collator = CompletionCollator(tokenizer.pad_token_id)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=10,
        logging_steps=10,
        save_strategy="steps",
        save_steps=50,
        save_total_limit=1,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        optim="paged_adamw_8bit",
        dataloader_pin_memory=False,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collator,
        callbacks=[TimeBudget(args.max_train_hours)],
    )

    print("==> Starting QLoRA training on Task 2...")
    trainer.train()

    print(f"==> Saving LoRA adapter to {args.output_dir}...")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print("[SUCCESS] Training finished successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_id", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--data_path", default="data/processed/task2_sft_train.jsonl")
    parser.add_argument("--output_dir", default="outputs/task2/qlora_adapter")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--max_train_hours", type=float, default=7.0)
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--grad_accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--max_seq_len", type=int, default=2048)
    args = parser.parse_args()
    train(args)
