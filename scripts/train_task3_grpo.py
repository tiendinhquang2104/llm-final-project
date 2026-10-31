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


def load_training_samples(data_path: str) -> list[dict]:
    """Load training samples from specified file or search canonical paths."""
    p = Path(data_path)
    if p.is_dir():
        samples = []
        for name in ["real-train.json", "synthetic-train.json", "train.json"]:
            sp = p / name
            if sp.exists():
                with open(sp, "r", encoding="utf-8-sig") as f:
                    part_data = json.load(f)
                items = part_data.get("samples", part_data) if isinstance(part_data, dict) else part_data
                samples.extend(items)
        if samples:
            print(f"[DATA] Loaded {len(samples)} training samples from directory: {p}")
            return samples

    if not p.exists():
        candidates = [
            repo_root / "data" / "processed" / "task3" / "real-train.json",
            repo_root / "data" / "processed" / "task3" / "synthetic-train.json",
            repo_root / "data" / "processed" / "task3_train.json",
            repo_root / "data" / "processed" / "task3_synthetic_curated.json",
            repo_root / "data" / "processed" / "task3_requested_levels.json",
            repo_root / "data" / "raw" / "task3_feedback.json",
        ]
        # Also check if data/processed/task3 directory exists
        proc_t3 = repo_root / "data" / "processed" / "task3"
        if proc_t3.is_dir():
            samples = []
            for name in ["real-train.json", "synthetic-train.json"]:
                sp = proc_t3 / name
                if sp.exists():
                    with open(sp, "r", encoding="utf-8-sig") as f:
                        part_data = json.load(f)
                    items = part_data.get("samples", part_data) if isinstance(part_data, dict) else part_data
                    samples.extend(items)
            if samples:
                print(f"[DATA] Loaded {len(samples)} training samples from {proc_t3}")
                return samples

        for c in candidates:
            if c.exists():
                p = c
                break

    if not p.exists():
        raise FileNotFoundError(f"Cannot find training dataset at {data_path} or canonical paths.")

    with open(p, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    samples = data.get("samples", data) if isinstance(data, dict) else data
    print(f"[DATA] Loaded {len(samples)} training samples from {p}")
    return samples


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
    parser.add_argument("--gradient-accumulation-steps", type=int, default=2)
    parser.add_argument("--max-prompt-length", type=int, default=2048)
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

    # 2. Setup Config
    cfg = GRPOTrainingConfig(
        output_dir=args.output_dir,
        learning_rate=args.learning_rate,
        group_size=args.group_size,
        max_steps=args.max_steps,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
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

    model.print_trainable_parameters()

    # 4. Run GRPO Training
    trainer = StandaloneGRPOTrainer(
        model=model,
        tokenizer=tokenizer,
        config=cfg,
        train_items=train_samples,
    )

    result = trainer.train()
    print(f"[GRPO] Training successfully completed! Final average reward: {result.get('final_reward', 0.0):+.2f}")
    print(f"[GRPO] Output saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
