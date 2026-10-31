#!/usr/bin/env python3
"""CLI Entry Point for Task 3 RLVR + GRPO (Group Relative Policy Optimization) Training.

Executes reinforcement learning with verifiable rewards starting from a pre-trained
or Stage-1 QLoRA adapter:
- Verifiable Rewards: JSON Schema, Pedagogical Level Compliance (compliance.py v3),
  Compiler Truth, Level 1 Safe Policy, and Anti-Degeneration.
- Optimization: Group Relative Policy Optimization (GRPO) without Critic network.
- Reference Model: PEFT `model.disable_adapter()` to avoid double VRAM allocation.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

# Add repo root to sys.path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.task3.grpo_trainer import GRPOTrainingConfig, StandaloneGRPOTrainer


def _load_records_from_file(file_path: Path) -> list[dict]:
    if not file_path.is_file():
        return []
    records = []
    if file_path.suffix == ".jsonl":
        with open(file_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        row = json.loads(line)
                        records.append(row.get("record", row))
                    except Exception:
                        pass
    else:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, list):
            records = [r.get("record", r) if isinstance(r, dict) else r for r in data]
        elif isinstance(data, dict):
            items = data.get("samples", [data])
            records = [r.get("record", r) if isinstance(r, dict) else r for r in items]
    return records


def load_training_samples(data_path: str) -> list[dict]:
    """Load training samples from specified file or directory, with full .jsonl and .json support."""
    p = Path(data_path)
    if not p.is_absolute():
        p = repo_root / p

    # 1. If path is a directory (e.g. data/processed/task3)
    if p.is_dir():
        samples = []
        for name in [
            "real-train.jsonl",
            "synthetic-train.jsonl",
            "real-train.json",
            "synthetic-train.json",
            "train.jsonl",
            "train.json",
        ]:
            sp = p / name
            samples.extend(_load_records_from_file(sp))
        if samples:
            print(f"[DATA] Loaded {len(samples)} training samples from directory: {p}")
            return samples

        # Fallback: any .jsonl or .json in directory (excluding public and manifest)
        for sp in sorted(p.glob("*.jsonl")) + sorted(p.glob("*.json")):
            if "manifest" in sp.name or "public" in sp.name or "levels" in sp.name:
                continue
            samples.extend(_load_records_from_file(sp))
        if samples:
            print(f"[DATA] Loaded {len(samples)} training samples from files in {p}")
            return samples
        raise FileNotFoundError(f"Directory {p} exists but contains no usable training data files.")

    # 2. If path is a specific file
    if p.is_file():
        samples = _load_records_from_file(p)
        if samples:
            print(f"[DATA] Loaded {len(samples)} training samples from file: {p}")
            return samples

    # 3. Canonical fallback search
    fallbacks = [
        repo_root / "data" / "processed" / "task3",
        repo_root / "data" / "processed" / "task3_train.json",
        repo_root / "data" / "processed" / "task3_synthetic_curated.json",
        repo_root / "data" / "raw" / "sample_dataset" / "task3_feedback.json",
    ]
    for c in fallbacks:
        if c.is_dir():
            try:
                s = load_training_samples(str(c))
                if s:
                    return s
            except Exception:
                pass
        elif c.is_file():
            s = _load_records_from_file(c)
            if s:
                print(f"[DATA] Loaded {len(s)} training samples from fallback: {c}")
                return s

    raise FileNotFoundError(f"Cannot find training dataset at {data_path} or any canonical fallback paths.")


def load_validation_samples(data_path: str) -> list[dict]:
    """Load validation samples for tracking Dev Macro-F1 checkpointing."""
    p = Path(data_path)
    if not p.is_absolute():
        p = repo_root / p
    val_samples = []
    if p.is_dir():
        for name in [
            "real-val.jsonl",
            "synthetic-heldout.jsonl",
            "real-val.json",
            "synthetic-heldout.json",
            "val.jsonl",
            "val.json",
        ]:
            sp = p / name
            val_samples.extend(_load_records_from_file(sp))
    if val_samples:
        print(f"[DATA] Loaded {len(val_samples)} validation samples for dev tracking from {p}")
    return val_samples


def parse_args():
    parser = argparse.ArgumentParser(description="Task 3 RLVR + GRPO Trainer")
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--sft-adapter", type=str, default="checkpoints/task3/mixed_balanced")
    parser.add_argument("--train-data", type=str, default="data/processed/task3_train.json")
    parser.add_argument("--output-dir", type=str, default="checkpoints/task3/rlvr_grpo")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--group-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--kl-beta", type=float, default=0.04)
    parser.add_argument("--clip-range", type=float, default=0.2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=2)
    parser.add_argument("--max-prompt-length", type=int, default=1536)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--device", type=str, default="cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") != "" else "auto")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 70)
    print(" TASK 3: REINFORCEMENT LEARNING WITH VERIFIABLE REWARDS (RLVR + GRPO)")
    print(f" Base Model     : {args.base_model}")
    print(f" SFT Adapter    : {args.sft_adapter}")
    print(f" Output Dir     : {args.output_dir}")
    print(f" Max Steps      : {args.max_steps}")
    print(f" Group Size (G) : {args.group_size}")
    print(f" Learning Rate  : {args.learning_rate}")
    print(f" KL Penalty Beta: {args.kl_beta}")
    print("=" * 70)

    # 1. Load Data
    train_samples = load_training_samples(args.train_data)
    val_samples = load_validation_samples(args.train_data)

    # 2. Setup Config
    cfg = GRPOTrainingConfig(
        output_dir=args.output_dir,
        learning_rate=args.learning_rate,
        group_size=args.group_size,
        max_steps=args.max_steps,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        clip_range=args.clip_range,
        kl_beta=args.kl_beta,
        max_prompt_length=args.max_prompt_length,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        seed=args.seed,
    )

    # 3. Import heavy GPU packages inside main so --help runs without PyTorch/CUDA
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel

    # Quantization config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    print(f"[MODEL] Loading base model: {args.base_model}...")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        attn_implementation="sdpa",
        trust_remote_code=True,
    )

    # Load SFT adapter if present
    adapter_path = Path(args.sft_adapter)
    if adapter_path.exists() and (
        (adapter_path / "adapter_model.safetensors").exists()
        or (adapter_path / "adapter_model.bin").exists()
    ):
        print(f"[PEFT] Loading pre-trained SFT adapter from {adapter_path}...")
        model = PeftModel.from_pretrained(base_model, str(adapter_path), is_trainable=True)
    else:
        print(f"[PEFT] No pre-existing adapter at {adapter_path}. Initializing new LoRA adapter...")
        from peft import LoraConfig, get_peft_model
        lora_config = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(base_model, lora_config)

    # Prepare model for gradient checkpointing during training
    if hasattr(base_model, "enable_input_require_grads"):
        base_model.enable_input_require_grads()
    if hasattr(base_model.config, "use_cache"):
        base_model.config.use_cache = True

    model.print_trainable_parameters()

    # 4. Run GRPO Training
    trainer = StandaloneGRPOTrainer(
        model=model,
        tokenizer=tokenizer,
        config=cfg,
        train_items=train_samples,
        val_items=val_samples,
    )

    result = trainer.train()
    print(f"[GRPO] Training successfully completed! Final average reward: {result.get('final_reward', 0.0):+.2f}")
    print(f"[GRPO] Output saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
