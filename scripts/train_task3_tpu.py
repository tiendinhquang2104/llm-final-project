#!/usr/bin/env python3
"""Task 3 LoRA Fine-Tuning Script for Google Cloud / Kaggle TPU (v3-8 / v4).

Engineered for PyTorch-XLA:
1. Native bfloat16: TPUs have massive HBM (16GB/core x 8 = 128GB on TPU v3-8),
   allowing full bfloat16 training without bitsandbytes CUDA kernels.
2. XLA Graph Optimization: Static shape batching & dataloader_drop_last to minimize
   XLA graph recompilation overhead.
3. LoRA via PEFT: Efficient parameter-efficient training of Qwen2.5-Coder-7B.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add repo root to sys.path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Check PyTorch-XLA (TPU) availability
try:
    import torch_xla.core.xla_model as xm
    import torch_xla.distributed.xla_multiprocessing as xmp
    TPU_AVAILABLE = True
except ImportError:
    TPU_AVAILABLE = False


def load_dataset_samples(data_dir: Path) -> list[dict]:
    """Load training samples from real-train and synthetic-train."""
    samples = []
    for fname in ["real-train.jsonl", "synthetic-train.jsonl", "train.jsonl"]:
        fpath = data_dir / fname
        if fpath.is_file():
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            row = json.loads(line)
                            samples.append(row.get("record", row))
                        except Exception:
                            pass
    return samples


def main():
    parser = argparse.ArgumentParser(description="Task 3 TPU LoRA Trainer")
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--data-dir", default="data/processed/task3")
    parser.add_argument("--output-dir", default="checkpoints/task3/tpu_adapter")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    args = parser.parse_args()

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments
    from src.task3.prompts import build_messages

    if TPU_AVAILABLE:
        device = xm.xla_device()
        logger.info(f"[TPU] PyTorch-XLA runtime detected. Active Device: {device}")
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.warning(f"[TPU] PyTorch-XLA not found. Fallback to: {device}")

    logger.info(f"[TPU] Loading tokenizer for {args.model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 1. Load Training Data
    data_path = Path(args.data_dir)
    raw_samples = load_dataset_samples(data_path)
    if not raw_samples:
        logger.error(f"[TPU] No training samples found in {data_path}!")
        sys.exit(1)
    logger.info(f"[TPU] Loaded {len(raw_samples)} training samples.")

    # 2. Tokenize and Prepare SFT Dataset
    tokenized_rows = []
    max_len = args.max_seq_length

    for s in raw_samples:
        inp = s.get("input", s)
        out = s.get("output", {})
        lvl = inp.get("target_feedback_level", "Level 2 - Chẩn đoán")
        code = inp.get("student_code", "") or inp.get("code", "")
        reqs = inp.get("problem_description", "") or inp.get("requirements", "")
        clog = inp.get("compile_log", "")

        # Format user context
        user_prompt = f"Problem Requirements:\n{reqs}\n\nStudent Code:\n{code}\n"
        if clog:
            user_prompt += f"\nCompiler Log:\n{clog}\n"
        user_prompt += f"\nTarget Feedback Level: {lvl}\n"

        prompt_messages = [
            {"role": "system", "content": "Bạn là giảng viên C++ hướng dẫn sinh viên theo các mức độ gợi ý. Xuất JSON {\"taxonomy_error\": [...], \"feedback\": \"...\"}."},
            {"role": "user", "content": user_prompt}
        ]

        completion_text = json.dumps(out, ensure_ascii=False) if isinstance(out, dict) else str(out)

        # Prefix masking
        prefix_ids = tokenizer.apply_chat_template(prompt_messages, tokenize=True, add_generation_prompt=True)
        full_ids = tokenizer.apply_chat_template(
            prompt_messages + [{"role": "assistant", "content": completion_text}],
            tokenize=True,
            add_generation_prompt=False
        )

        if len(full_ids) > max_len:
            continue
        labels = [-100] * len(prefix_ids) + full_ids[len(prefix_ids):]
        tokenized_rows.append({
            "input_ids": full_ids,
            "attention_mask": [1] * len(full_ids),
            "labels": labels
        })

    logger.info(f"[TPU] Formatted {len(tokenized_rows)} records within context limit {max_len}.")

    # 3. Load Model in Native bfloat16 (No bitsandbytes for TPU compatibility)
    logger.info(f"[TPU] Initializing Base Model in bfloat16: {args.model_id}")
    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )

    # 4. Attach PEFT LoRA Adapter
    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # Move to TPU device
    if TPU_AVAILABLE:
        model = model.to(device)

    # 5. Collate with Padding
    pad_id = tokenizer.pad_token_id

    def data_collator(features):
        batch_size = len(features)
        max_batch_len = max(len(f["input_ids"]) for f in features)
        input_ids = torch.full((batch_size, max_batch_len), pad_id, dtype=torch.long)
        attention_mask = torch.zeros((batch_size, max_batch_len), dtype=torch.long)
        labels = torch.full((batch_size, max_batch_len), -100, dtype=torch.long)

        for i, f in enumerate(features):
            cur_len = len(f["input_ids"])
            input_ids[i, :cur_len] = torch.tensor(f["input_ids"], dtype=torch.long)
            attention_mask[i, :cur_len] = torch.tensor(f["attention_mask"], dtype=torch.long)
            labels[i, :cur_len] = torch.tensor(f["labels"], dtype=torch.long)

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }

    # 6. Training Arguments optimized for TPU
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps if args.max_steps else -1,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=5,
        save_strategy="no",
        bf16=True,
        dataloader_drop_last=True,  # Crucial for XLA static shapes
        dataloader_num_workers=2,
        optim="adamw_torch",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=Dataset.from_list(tokenized_rows),
        data_collator=data_collator,
    )

    logger.info("[TPU] Starting LoRA training...")
    trainer.train()

    # 7. Save Adapter & Synchronize XLA
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[TPU] Saving adapter to {out_dir}...")
    trainer.model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    if TPU_AVAILABLE:
        xm.mark_step()
    logger.info("[TPU] Training completed successfully!")


if __name__ == "__main__":
    main()
