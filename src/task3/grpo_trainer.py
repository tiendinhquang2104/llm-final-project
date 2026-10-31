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
    max_prompt_length: int = 1536
    max_new_tokens: int = 256
    temperature: float = 0.8
    top_p: float = 0.95
    seed: int = 42
    save_steps: int = 10
    logging_steps: int = 1


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
        val_items: Optional[List[Dict[str, Any]]] = None,
    ):
        import torch
        self.model = model
        self.tokenizer = tokenizer
        self.config = config
        self.train_items = train_items
        self.val_items = val_items or []
        self.optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, self.model.parameters()),
            lr=config.learning_rate,
            weight_decay=0.01,
        )

    def train(self) -> Dict[str, Any]:
        """Main GRPO training loop with class-balanced sampling and best-checkpoint tracking."""
        import torch
        import torch.nn.functional as F
        self.model.train()
        cfg = self.config
        total_steps = cfg.max_steps
        logger.info(f"[GRPO] Starting RLVR training for {total_steps} steps | Group Size: {cfg.group_size}")

        history: List[Dict[str, float]] = []
        step = 0
        item_idx = 0

        # Class-Balanced Sampling (Việc 3): Oversample rare categories to ensure strong gradient signal
        sample_weights = []
        for it in self.train_items:
            out_tax = []
            if isinstance(it.get("output"), dict):
                out_tax = it["output"].get("taxonomy_error", [])
            elif it.get("gold_taxonomy"):
                out_tax = it["gold_taxonomy"]
            elif it.get("taxonomy_error"):
                out_tax = it["taxonomy_error"]

            w = 1.0
            if any(t in out_tax for t in ["Lỗi edge case", "Lỗi style", "Lỗi nhập/xuất"]):
                w = 4.0
            elif any(t in out_tax for t in ["Lỗi hàm", "Lỗi vòng lặp", "Lỗi mảng/chuỗi"]):
                w = 2.5
            sample_weights.append(w)

        random.seed(cfg.seed)
        shuffled_indices = random.choices(range(len(self.train_items)), weights=sample_weights, k=max(1000, total_steps * 4))

        best_val_macro_f1 = -1.0
        best_step = -1
        best_checkpoint_dir = Path(cfg.output_dir) / "best_checkpoint"

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

            # 2. Sample G completions from current policy (ENABLE FAST KV-CACHE)
            self.model.eval()
            if hasattr(self.model, "gradient_checkpointing_disable"):
                self.model.gradient_checkpointing_disable()
            if hasattr(self.model.config, "use_cache"):
                self.model.config.use_cache = True

            with torch.no_grad():
                gen_out = self.model.generate(
                    prompt_ids,
                    do_sample=True,
                    temperature=cfg.temperature,
                    top_p=cfg.top_p,
                    max_new_tokens=cfg.max_new_tokens,
                    num_return_sequences=cfg.group_size,
                    pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
                    use_cache=True,
                )

            # 3. Clear generation cache and decode completions
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

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

            # 5 & 6. Micro-batched Policy Log-Probs, Ref Log-Probs, and Backprop
            # Switch to train mode: disable KV-cache and enable gradient checkpointing for minimal VRAM
            self.model.train()
            if hasattr(self.model.config, "use_cache"):
                self.model.config.use_cache = False
            if hasattr(self.model, "gradient_checkpointing_enable"):
                self.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})

            step_loss_val = 0.0

            for i in range(cfg.group_size):
                adv_i = advantages[i]
                single_gen = gen_out[i : i + 1]  # Shape: (1, seq_len)
                single_target = single_gen[:, prompt_len:].contiguous()
                single_mask = (single_gen != (self.tokenizer.pad_token_id or self.tokenizer.eos_token_id)).long()
                target_mask = (single_target != (self.tokenizer.pad_token_id or self.tokenizer.eos_token_id)).float()

                if target_mask.sum() == 0:
                    continue

                # Forward pass for single completion
                logits_i = self.model(input_ids=single_gen, attention_mask=single_mask).logits
                gen_logits_i = logits_i[:, prompt_len - 1 : -1, :]
                log_probs_i = F.log_softmax(gen_logits_i, dim=-1)
                token_log_probs_i = log_probs_i.gather(dim=-1, index=single_target.unsqueeze(-1)).squeeze(-1)

                # Reference log-probs with adapter disabled
                with torch.no_grad():
                    if hasattr(self.model, "disable_adapter"):
                        with self.model.disable_adapter():
                            ref_logits_i = self.model(input_ids=single_gen, attention_mask=single_mask).logits
                            ref_gen_logits_i = ref_logits_i[:, prompt_len - 1 : -1, :]
                            ref_log_probs_i = F.log_softmax(ref_gen_logits_i, dim=-1)
                            ref_token_log_probs_i = ref_log_probs_i.gather(dim=-1, index=single_target.unsqueeze(-1)).squeeze(-1)
                    else:
                        ref_token_log_probs_i = token_log_probs_i.detach()

                # On-policy rollout: old log-probs is detached current log-probs
                old_log_probs_i = token_log_probs_i.detach()
                ratio_i = torch.exp(token_log_probs_i - old_log_probs_i)

                # KL divergence per token (Schulman approximation)
                kl_i = torch.exp(ref_token_log_probs_i - token_log_probs_i) - (ref_token_log_probs_i - token_log_probs_i) - 1.0

                # Clipped surrogate objective
                surr1_i = ratio_i * adv_i
                surr2_i = torch.clamp(ratio_i, 1.0 - cfg.clip_range, 1.0 + cfg.clip_range) * adv_i
                surrogate_loss_i = -torch.min(surr1_i, surr2_i)

                # Total loss per token
                token_loss_i = surrogate_loss_i + cfg.kl_beta * kl_i
                sample_loss = (token_loss_i * target_mask).sum() / (target_mask.sum() + 1e-6)

                # Backward pass immediately for this micro-batch sample
                scaled_loss = sample_loss / (cfg.group_size * cfg.gradient_accumulation_steps)
                scaled_loss.backward()
                step_loss_val += sample_loss.item() / cfg.group_size

                # Free tensors immediately
                del logits_i, gen_logits_i, log_probs_i, token_log_probs_i, ref_token_log_probs_i
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            accum_loss += step_loss_val

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
                    f"Level: {sample['target_feedback_level']}",
                    flush=True,
                )
                accum_loss = 0.0

            history.append({
                "step": step,
                "mean_reward": mean_reward,
                "mean_compliance": mean_compliance,
            })
            step += 1

            # Validation tracking every 5 steps (Việc 5)
            if self.val_items and (step % 5 == 0 or step == total_steps):
                val_macro_f1, val_severe = self._evaluate_validation(max_samples=25)
                print(f"[VAL EVAL Step {step:03d}/{total_steps}] Val Macro-F1: {val_macro_f1:.4f} | Severe Leaks: {val_severe}", flush=True)
                if val_macro_f1 > best_val_macro_f1 and val_severe == 0:
                    best_val_macro_f1 = val_macro_f1
                    best_step = step
                    self.save_adapter(best_checkpoint_dir)
                    print(f"[BEST MODEL] Step {step}: New Best Val Macro-F1 ({val_macro_f1:.4f}) saved to {best_checkpoint_dir}", flush=True)

            if step % cfg.save_steps == 0 or step == total_steps:
                self.save_adapter(Path(cfg.output_dir))

        # Deploy best validation checkpoint if available (Việc 5)
        if best_checkpoint_dir.exists() and any(best_checkpoint_dir.iterdir()):
            import shutil
            for item in best_checkpoint_dir.iterdir():
                dest = Path(cfg.output_dir) / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
            print(f"[GRPO] Automatically deployed best validated checkpoint from Step {best_step} (Val Macro-F1: {best_val_macro_f1:.4f}) to {cfg.output_dir}", flush=True)

        return {"history": history, "final_reward": history[-1]["mean_reward"] if history else 0.0, "best_val_macro_f1": best_val_macro_f1}

    def _evaluate_validation(self, max_samples: int = 25) -> Tuple[float, int]:
        """Fast validation evaluation on a subset of heldout data."""
        import torch
        from src.synth.taxonomy import LABEL_SPACE
        from src.task3.compliance import check as compliance_check
        from src.task3.rlvr_rewards import parse_completion

        self.model.eval()
        eval_subset = self.val_items[:max_samples]
        gold_map = {}
        pred_map = {}
        severe_leaks = 0

        for it in eval_subset:
            sample = extract_prompt_and_metadata(it)
            sid = it.get("sample_id", str(len(gold_map)))
            gold_tax = sample.get("ground_truth_taxonomy") or []
            gold_map[sid] = gold_tax
            lvl = sample.get("target_feedback_level", "Level 2")

            prompt_str = sample["formatted_prompt"]
            prompt_inputs = self.tokenizer(
                prompt_str,
                return_tensors="pt",
                truncation=True,
                max_length=self.config.max_prompt_length,
            )
            p_ids = prompt_inputs["input_ids"].to(self.model.device)

            with torch.no_grad():
                out_ids = self.model.generate(
                    p_ids,
                    do_sample=False,
                    max_new_tokens=self.config.max_new_tokens,
                    pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
                    use_cache=True,
                )
            gen_text = self.tokenizer.decode(out_ids[0][p_ids.shape[1]:], skip_special_tokens=True)
            data = parse_completion(gen_text)
            pred_tax = data.get("taxonomy_error", []) if data else []
            fb = data.get("feedback", "") if data else gen_text
            pred_map[sid] = pred_tax

            chk = compliance_check(fb, lvl, version=3)
            if chk.severe and ("Level 1" in lvl or "Level 2" in lvl):
                severe_leaks += 1

        macro_sum = 0.0
        for lbl in LABEL_SPACE:
            tp, fp, fn = 0, 0, 0
            for sid, g in gold_map.items():
                p = pred_map.get(sid, [])
                if lbl in g and lbl in p: tp += 1
                elif lbl not in g and lbl in p: fp += 1
                elif lbl in g and lbl not in p: fn += 1
            prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fp == 0 else 0.0)
            rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fn == 0 else 0.0)
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else (1.0 if (tp == 0 and fp == 0 and fn == 0) else 0.0)
            macro_sum += f1

        macro_f1 = macro_sum / len(LABEL_SPACE)
        return float(macro_f1), int(severe_leaks)

    def save_adapter(self, out_dir: Path):
        """Save the calibrated LoRA adapter."""
        out_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(self.model, "save_pretrained"):
            self.model.save_pretrained(str(out_dir))
        self.tokenizer.save_pretrained(str(out_dir))
        print(f"[GRPO] Calibrated adapter checkpoint saved to {out_dir}", flush=True)
