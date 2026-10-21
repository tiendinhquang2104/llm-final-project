"""Train Task 2 QLoRA adapter on Qwen2.5-Coder-7B-Instruct using completion-only SFT.

Takes data/processed/task2_sft_train.jsonl and saves fine-tuned LoRA adapter.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


def encode_row(tokenizer, messages, max_length=2048):
    prompt = messages[:-1]
    prefix = tokenizer.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
    labels = [-100] * len(prefix) + full[len(prefix) :]
    if len(full) > max_length:
        full = full[-max_length:]
        labels = labels[-max_length:]
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

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

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
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        optim="paged_adamw_8bit",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collator,
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
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--grad_accum", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--max_seq_len", type=int, default=2048)
    args = parser.parse_args()
    train(args)
