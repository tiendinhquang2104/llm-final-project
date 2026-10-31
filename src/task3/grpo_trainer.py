"""Group Relative Policy Optimization (GRPO) Trainer for Task 3 QLoRA.

Implements memory-efficient GRPO with Verifiable Rewards (RLVR):
1. Critic-Free: Samples a group of G responses per prompt, computes advantage relative to group mean/std.
2. VRAM-Efficient PEFT Reference: Evaluates reference log-probs using `model.disable_adapter()`,
   requiring NO second model in GPU VRAM (fits on single Kaggle T4 / P100 / L4 GPU).
3. Verifiable Reward Functions: JSON Schema, Level Compliance, Compiler Truth, Level 1 Safe Policy,
   Anti-Degeneration, and Level 3 Action Directive.
4. Native TRL Interoperability: Can also dispatch to `trl.GRPOTrainer` if requested.
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.task3.rlvr_rewards import compute_composite_reward

logger = logging.getLogger(__name__)


@dataclass
class GRPOTrainingConfig:
    """Hyperparameters for GRPO + RLVR Training."""
    output_dir: str = "checkpoints/task3/rlvr_grpo"
    learning_rate: float = 1e-5
    group_size: int = 4                # Number of candidate responses sampled per prompt (G)
    max_steps: int = 60                # Number of optimization steps
    batch_size: int = 1                # Prompts per step
    gradient_accumulation_steps: int = 2
    clip_range: float = 0.2            # PPO / GRPO clip epsilon
    kl_beta: float = 0.04              # KL penalty weight beta
    max_prompt_length: int = 2048
    max_new_tokens: int = 256
    temperature: float = 0.8
    top_p: float = 0.95
    seed: int = 42
    save_steps: int = 20
    logging_steps: int = 5


def compute_group_advantages(rewards: Sequence[float], eps: float = 1e-4) -> Any:
    """Computes group-relative normalized advantages: A_i = (R_i - mean(R)) / (std(R) + eps)."""
    import torch
    t_rewards = torch.tensor(rewards, dtype=torch.float32)
    mean = t_rewards.mean()
    std = t_rewards.std(unbiased=False)
    if std < eps:
        # If all rewards in group are identical, advantages are 0
        return torch.zeros_like(t_rewards)
    return (t_rewards - mean) / (std + eps)


def extract_prompt_and_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    """Extract standard prompt string and metadata required for reward functions."""
    inp = item.get("input", item)
    exam_id = inp.get("exam_id", "")
    etype = inp.get("exam_type", "single_problem")
    lvl = inp.get("target_feedback_level", "Level 2 - Chẩn đoán")
    clog = inp.get("compile_log", "")
    code = inp.get("student_code", "") or inp.get("code", "")
    reqs = inp.get("problem_description", "") or inp.get("requirements", "") or inp.get("statement", "")
    gt_tax = item.get("output", {}).get("taxonomy_error", None) if isinstance(item.get("output"), dict) else (item.get("gold_taxonomy") or item.get("taxonomy_error"))

    # Standard Vietnamese Prompt for Task 3
    system_prompt = (
        "Bạn là một trợ lý AI chấm bài lập trình C++ sư phạm cho sinh viên đại học. "
        "Hãy đọc kỹ đề bài, mã nguồn sinh viên nộp và log biên dịch (nếu có). "
        "Sau đó đưa ra phản hồi bằng định dạng JSON nghiêm ngặt:\n"
        "{\n"
        '  "taxonomy_error": ["<nhãn lỗi 1>", ...],\n'
        '  "feedback": "<nhận xét sư phạm chuẩn xác theo đúng Level được yêu cầu>"\n'
        "}\n"
    )

    user_prompt = (
        f"[YÊU CẦU MỨC ĐỘ PHẢN HỒI]\n{lvl}\n\n"
        f"[THÔNG TIN ĐỀ BÀI ({exam_id} - {etype})]\n{reqs}\n\n"
        f"[LOG BIÊN DỊCH]\n{clog if clog else 'Biên dịch bình thường (hoặc không có log lỗi).'}\n\n"
        f"[MÃ NGUỒN C++ SINH VIÊN NỘP]\n```cpp\n{code}\n```\n\n"
        "Hãy phân tích và trả về DUY NHẤT một khối JSON hợp lệ theo đúng quy định."
    )

    formatted_text = (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    return {
        "formatted_prompt": formatted_text,
        "target_feedback_level": lvl,
        "compile_log": clog,
        "student_code": code,
        "ground_truth_taxonomy": gt_tax,
        "exam_id": exam_id,
    }


class StandaloneGRPOTrainer:
    """Lightweight, memory-efficient GRPO Trainer for QLoRA."""

    def __init__(
        self,
        model: Any,
        tokenizer: Any,
        config: GRPOTrainingConfig,
        train_items: List[Dict[str, Any]],
    ):
        import torch
        self.model = model
        self.tokenizer = tokenizer
        self.config = config
        self.train_items = train_items
        self.optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, self.model.parameters()),
            lr=config.learning_rate,
            weight_decay=0.01,
        )

    def train(self) -> Dict[str, Any]:
        """Main GRPO training loop."""
        import torch
        import torch.nn.functional as F
        self.model.train()
        cfg = self.config
        total_steps = cfg.max_steps
        logger.info(f"[GRPO] Starting RLVR training for {total_steps} steps | Group Size: {cfg.group_size}")

        history: List[Dict[str, float]] = []
        step = 0
        item_idx = 0
        random.seed(cfg.seed)
        shuffled_indices = list(range(len(self.train_items)))
        random.shuffle(shuffled_indices)

        self.optimizer.zero_grad()
        accum_loss = 0.0

        while step < total_steps:
            idx = shuffled_indices[item_idx % len(shuffled_indices)]
            item_idx += 1
            sample = extract_prompt_and_metadata(self.train_items[idx])

            # 1. Tokenize prompt
            prompt_str = sample["formatted_prompt"]
            prompt_inputs = self.tokenizer(
                prompt_str,
                return_tensors="pt",
                truncation=True,
                max_length=cfg.max_prompt_length,
            )
            prompt_ids = prompt_inputs["input_ids"].to(self.model.device)
            prompt_len = prompt_ids.shape[1]

            # 2. Sample G completions from current policy
            self.model.eval()
            with torch.no_grad():
                gen_out = self.model.generate(
                    prompt_ids,
                    do_sample=True,
                    temperature=cfg.temperature,
                    top_p=cfg.top_p,
                    max_new_tokens=cfg.max_new_tokens,
                    num_return_sequences=cfg.group_size,
                    pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
                )

            # 3. Decode completions and evaluate with Verifiable Rewards
            completions_text: List[str] = []
            rewards: List[float] = []
            reward_breakdowns: List[Dict[str, float]] = []

            for i in range(cfg.group_size):
                full_ids = gen_out[i]
                comp_ids = full_ids[prompt_len:]
                text = self.tokenizer.decode(comp_ids, skip_special_tokens=True)
                completions_text.append(text)

                r_dict = compute_composite_reward(
                    completion=text,
                    target_feedback_level=sample["target_feedback_level"],
                    compile_log=sample["compile_log"],
                    ground_truth_taxonomy=sample["ground_truth_taxonomy"],
                )
                rewards.append(r_dict["total"])
                reward_breakdowns.append(r_dict)

            # 4. Compute Group Advantages
            advantages = compute_group_advantages(rewards).to(self.model.device)

            # 5. Compute Policy Log-Probs and Reference Log-Probs
            self.model.train()
            # Forward pass with policy
            all_prompt_ids = prompt_ids.repeat(cfg.group_size, 1)
            target_ids = gen_out[:, prompt_len:].contiguous()
            attention_mask = (gen_out != (self.tokenizer.pad_token_id or self.tokenizer.eos_token_id)).long()

            logits = self.model(input_ids=gen_out, attention_mask=attention_mask).logits
            gen_logits = logits[:, prompt_len - 1 : -1, :]
            log_probs = F.log_softmax(gen_logits, dim=-1)
            token_log_probs = log_probs.gather(dim=-1, index=target_ids.unsqueeze(-1)).squeeze(-1)

            # Reference log-probs using model.disable_adapter() (Zero additional VRAM!)
            with torch.no_grad():
                if hasattr(self.model, "disable_adapter"):
                    with self.model.disable_adapter():
                        ref_logits = self.model(input_ids=gen_out, attention_mask=attention_mask).logits
                        ref_gen_logits = ref_logits[:, prompt_len - 1 : -1, :]
                        ref_log_probs = F.log_softmax(ref_gen_logits, dim=-1)
                        ref_token_log_probs = ref_log_probs.gather(dim=-1, index=target_ids.unsqueeze(-1)).squeeze(-1)
                else:
                    ref_token_log_probs = token_log_probs.detach()

            # 6. GRPO Loss: Clipped surrogate objective + KL penalty
            # Ratio of policy to old policy (for 1-step on-policy rollout, old is token_log_probs.detach())
            old_log_probs = token_log_probs.detach()
            ratio = torch.exp(token_log_probs - old_log_probs)

            # Per-token mask (ignore padding tokens)
            token_mask = (target_ids != (self.tokenizer.pad_token_id or self.tokenizer.eos_token_id)).float()

            # KL divergence per token (Schulman approximation)
            kl_div = torch.exp(ref_token_log_probs - token_log_probs) - (ref_token_log_probs - token_log_probs) - 1.0

            # Broadcast advantage (G,) to (G, seq_len)
            adv_expanded = advantages.unsqueeze(-1).expand_as(ratio)

            # PPO / GRPO clip
            surr1 = ratio * adv_expanded
            surr2 = torch.clamp(ratio, 1.0 - cfg.clip_range, 1.0 + cfg.clip_range) * adv_expanded
            surrogate_loss = -torch.min(surr1, surr2)

            # Total loss per token
            token_loss = surrogate_loss + cfg.kl_beta * kl_div
            # Average over valid completion tokens
            loss = (token_loss * token_mask).sum() / (token_mask.sum() + 1e-6)

            # Normalize by gradient accumulation
            loss = loss / cfg.gradient_accumulation_steps
            loss.backward()
            accum_loss += loss.item()

            if (step + 1) % cfg.gradient_accumulation_steps == 0 or (step + 1) == total_steps:
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                self.optimizer.zero_grad()

            mean_reward = float(sum(rewards) / len(rewards))
            mean_compliance = float(sum(r["compliance"] for r in reward_breakdowns) / len(reward_breakdowns))

            if step % cfg.logging_steps == 0:
                print(
                    f"[GRPO Step {step:03d}/{total_steps}] "
                    f"Loss: {accum_loss:.4f} | "
                    f"Mean Reward: {mean_reward:+.2f} | "
                    f"Compliance: {mean_compliance:+.2f} | "
                    f"Level: {sample['target_feedback_level']}"
                )
                accum_loss = 0.0

            history.append({
                "step": step,
                "mean_reward": mean_reward,
                "mean_compliance": mean_compliance,
            })
            step += 1

            if step % cfg.save_steps == 0 or step == total_steps:
                self.save_adapter(Path(cfg.output_dir))

        return {"history": history, "final_reward": history[-1]["mean_reward"] if history else 0.0}

    def save_adapter(self, out_dir: Path):
        """Save the calibrated LoRA adapter."""
        out_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(self.model, "save_pretrained"):
            self.model.save_pretrained(str(out_dir))
        self.tokenizer.save_pretrained(str(out_dir))
        print(f"[GRPO] Calibrated adapter checkpoint saved to {out_dir}")
