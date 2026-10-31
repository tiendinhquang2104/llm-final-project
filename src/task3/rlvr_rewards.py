"""Reinforcement Learning with Verifiable Rewards (RLVR) v2 for Task 3.

Engineered under DeepSeek-R1 / RLVR post-training best practices:
1. Multi-Tier Verifiable Signals:
   - Tier 1: Format & Schema Purity (JSON parse, no trailing chatter, LABEL_SPACE check).
   - Tier 2: Pedagogical Level Compliance & Strict Anti-Leak (Severe Leak penalty: -5.0).
   - Tier 3: Objective Truth & Compiler Grounding (Compiler log consistency & GT Taxonomy F1).
   - Tier 4: Length Floor & Anti-Hacking (Anti-6-token penalty: -3.0, optimal 25-85 words: +1.5).
   - Tier 5: Anti-Degeneration & Natural Vietnamese (N-gram diversity, banned phrase detector).
2. Anti-Reward-Hacking Mechanisms:
   - Prevents length collapse (penalizes minimal 6-token responses).
   - Prevents verbosity bloat (penalizes rambling over 130 words).
   - Prevents taxonomy hallucination (penalizes guessing on Level 1 and false hard-code).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Union

from src.synth.taxonomy import LABEL_SPACE
from src.task3.compliance import check as compliance_check
from src.utils.json_extractor import extract_json_objects

# Known phrases indicating language degeneration from overfitted adapters
DEGENERATION_PATTERNS = [
    re.compile(r"học em kỹ", re.IGNORECASE),
    re.compile(r"gọi em làm em", re.IGNORECASE),
    re.compile(r"bài tập em còn một chỗ", re.IGNORECASE),
    re.compile(r"code chưa hoàn thiện\.\.\.", re.IGNORECASE),
    re.compile(r"làm em nhé", re.IGNORECASE),
    re.compile(r"chúc em làm tốt\.\s*chúc em làm tốt", re.IGNORECASE),
]


def parse_completion(text: str) -> Optional[Dict[str, Any]]:
    """Robustly extract and parse JSON completion into a dictionary."""
    if not text or not isinstance(text, str):
        return None
    try:
        objs = extract_json_objects(text)
        if objs:
            return objs[0]
    except Exception:
        pass

    # Direct json loads fallback
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


# -----------------------------------------------------------------------------
# Tier 1: Format, Schema & Output Purity Verifier
# -----------------------------------------------------------------------------
def format_reward_func(completions: Sequence[str], **kwargs) -> List[float]:
    """Verifies that completion is valid JSON, pure (no chatter), and keys are correct."""
    rewards = []
    for c in completions:
        data = parse_completion(c)
        if not data:
            rewards.append(-3.0)  # Heavy penalty for unparseable completion
            continue

        has_tax = "taxonomy_error" in data and isinstance(data["taxonomy_error"], list)
        has_fb = "feedback" in data and isinstance(data["feedback"], str) and bool(data["feedback"].strip())

        if not (has_tax and has_fb):
            rewards.append(-2.0)
            continue

        # Check all taxonomy labels are in LABEL_SPACE
        invalid_labels = [lbl for lbl in data["taxonomy_error"] if lbl not in LABEL_SPACE]
        if invalid_labels:
            rewards.append(-1.5)
            continue

        # Purity bonus: check if output is cleanly formatted JSON without markdown chatter
        stripped = c.strip()
        is_clean_json = (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("```json") and stripped.endswith("```")
        )
        purity_bonus = 0.5 if is_clean_json else -0.5

        rewards.append(1.0 + purity_bonus)
    return rewards


# -----------------------------------------------------------------------------
# Tier 2: Pedagogical Level Compliance & Strict Anti-Leak (Severe Leak = -5.0)
# -----------------------------------------------------------------------------
def compliance_reward_func(
    completions: Sequence[str],
    target_feedback_level: Sequence[str],
    **kwargs,
) -> List[float]:
    """Evaluates strict pedagogical compliance using compliance.py v3 with extreme severe leak penalty."""
    rewards = []
    for c, lvl in zip(completions, target_feedback_level):
        data = parse_completion(c)
        if not data:
            rewards.append(-1.0)
            continue

        fb = data.get("feedback", "")
        if not fb.strip():
            rewards.append(-2.5)
            continue

        try:
            res = compliance_check(feedback=fb, level=lvl, version=3)
            if res.severe:
                # Severe leak (code solution in L1/L2) -> zero score on sample, severe penalty!
                rewards.append(-5.0)
            elif res.ok:
                rewards.append(2.0)  # High reward for 100% compliance
            else:
                # Minor violation (e.g. repair instruction in L2, or technical disclosure in L1)
                rewards.append(-1.5)
        except Exception:
            rewards.append(-0.5)
    return rewards


# -----------------------------------------------------------------------------
# Tier 3: Objective Truth, Compiler Grounding & Taxonomy Alignment
# -----------------------------------------------------------------------------
def compiler_truth_reward_func(
    completions: Sequence[str],
    compile_log: Sequence[str],
    **kwargs,
) -> List[float]:
    """Verifies that 'Lỗi biên dịch' strictly matches actual compilation status."""
    rewards = []
    for c, clog in zip(completions, compile_log):
        data = parse_completion(c)
        if not data:
            rewards.append(0.0)
            continue

        tax = data.get("taxonomy_error", [])
        has_compile_error_label = "Lỗi biên dịch" in tax
        is_actually_failing = bool(clog and "error:" in clog.lower())

        if is_actually_failing:
            if has_compile_error_label:
                rewards.append(1.5)   # Correctly identified compiler failure
            else:
                rewards.append(-2.0)  # Missed obvious compiler error
        else:
            if has_compile_error_label:
                rewards.append(-2.0)  # Hallucinated compiler error on clean code
            else:
                rewards.append(0.5)   # Correctly did not output compile error
    return rewards


def level1_policy_reward_func(
    completions: Sequence[str],
    target_feedback_level: Sequence[str],
    compile_log: Sequence[str],
    **kwargs,
) -> List[float]:
    """Penalizes guessing taxonomy labels on Level 1 unless compilation failed."""
    rewards = []
    for c, lvl, clog in zip(completions, target_feedback_level, compile_log):
        data = parse_completion(c)
        if not data:
            rewards.append(0.0)
            continue

        if not str(lvl).startswith("Level 1"):
            rewards.append(0.0)
            continue

        tax = data.get("taxonomy_error", [])
        is_actually_failing = bool(clog and "error:" in clog.lower())

        if is_actually_failing:
            if tax == ["Lỗi biên dịch"]:
                rewards.append(1.5)
            else:
                rewards.append(-1.0)
        else:
            # On non-compile error, Level 1 taxonomy MUST be empty []
            if len(tax) == 0:
                rewards.append(1.5)
            else:
                # Guessing taxonomy on Level 1 collapses macro-F1 due to false positives
                rewards.append(-2.5)
    return rewards


def ground_truth_taxonomy_reward_func(
    completions: Sequence[str],
    ground_truth_taxonomy: Sequence[Optional[List[str]]],
    **kwargs,
) -> List[float]:
    """Awards F1 alignment reward when ground truth taxonomy is available."""
    rewards = []
    for c, gt_tax in zip(completions, ground_truth_taxonomy):
        if gt_tax is None:
            rewards.append(0.0)
            continue

        data = parse_completion(c)
        pred_tax = set(data.get("taxonomy_error", [])) if data else set()
        gt_set = set(gt_tax)

        # Penalize false prediction of Lỗi hard-code (since GT support is 0)
        hard_code_penalty = -1.5 if "Lỗi hard-code" in pred_tax and "Lỗi hard-code" not in gt_set else 0.0

        if not pred_tax and not gt_set:
            rewards.append(1.5 + hard_code_penalty)
        elif not pred_tax or not gt_set:
            rewards.append(0.0 + hard_code_penalty)
        else:
            intersection = len(pred_tax & gt_set)
            prec = intersection / len(pred_tax)
            rec = intersection / len(gt_set)
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            rewards.append(3.0 * f1 + hard_code_penalty)
    return rewards


# -----------------------------------------------------------------------------
# Tier 4: Length Floor & Anti-Hacking Verifier
# -----------------------------------------------------------------------------
def pedagogical_density_reward_func(
    completions: Sequence[str],
    target_feedback_level: Sequence[str],
    **kwargs,
) -> List[float]:
    """Penalizes ultra-short (6-token) reward hacks and rambling over-verbose outputs."""
    rewards = []
    for c, lvl in zip(completions, target_feedback_level):
        data = parse_completion(c)
        fb = data.get("feedback", "") if data else c
        words = fb.split()
        num_words = len(words)

        # Anti-Reward-Hacking: Heavy penalty for ultra-short responses (< 15 words)
        if num_words < 15:
            rewards.append(-3.0)
            continue
        elif num_words < 22:
            rewards.append(-0.5)
            continue

        # Ideal pedagogical sweet spot: 25 to 85 words
        if 25 <= num_words <= 85:
            rewards.append(1.5)
        elif 85 < num_words <= 125:
            rewards.append(0.5)
        else:
            # Overly verbose / rambling (> 125 words)
            rewards.append(-1.0)
    return rewards


# -----------------------------------------------------------------------------
# Tier 5: Anti-Degeneration, N-gram Diversity & Action Directives
# -----------------------------------------------------------------------------
def anti_degeneration_reward_func(completions: Sequence[str], **kwargs) -> List[float]:
    """Penalizes repetitive n-grams and known adapter degeneration artifacts."""
    rewards = []
    for c in completions:
        data = parse_completion(c)
        fb = data.get("feedback", "") if data else c

        # Check corrupted phrases
        corrupted = False
        for pattern in DEGENERATION_PATTERNS:
            if pattern.search(fb):
                corrupted = True
                break

        if corrupted:
            rewards.append(-3.0)  # Strict penalty for corrupted language
            continue

        # Check repetition: ratio of unique 3-grams to total 3-grams
        words = fb.lower().split()
        if len(words) >= 14:
            trigrams = [tuple(words[i : i + 3]) for i in range(len(words) - 2)]
            unique_ratio = len(set(trigrams)) / max(1, len(trigrams))
            if unique_ratio < 0.70:
                rewards.append(-2.0)  # High repetitive looping
                continue

        rewards.append(1.0)
    return rewards


def level3_directive_reward_func(
    completions: Sequence[str],
    target_feedback_level: Sequence[str],
    **kwargs,
) -> List[float]:
    """Ensures Level 3 feedback provides an explicit 'Hướng sửa:' directive."""
    rewards = []
    for c, lvl in zip(completions, target_feedback_level):
        if not str(lvl).startswith("Level 3"):
            rewards.append(0.0)
            continue

        data = parse_completion(c)
        if not data:
            rewards.append(-0.5)
            continue

        fb = data.get("feedback", "")
        if re.search(r"\bhướng sửa\s*:", fb, re.IGNORECASE) or re.search(r"\bgợi ý sửa\s*:", fb, re.IGNORECASE):
            rewards.append(1.5)
        else:
            rewards.append(-1.5)
    return rewards


# -----------------------------------------------------------------------------
# Composite Multi-Tier Verifiable Reward Aggregator
# -----------------------------------------------------------------------------
def compute_composite_reward(
    completion: str,
    target_feedback_level: str,
    compile_log: str = "",
    ground_truth_taxonomy: Optional[List[str]] = None,
) -> Dict[str, float]:
    """Computes all individual rewards and total weighted composite reward for a single completion."""
    c_list = [completion]
    lvl_list = [target_feedback_level]
    clog_list = [compile_log]
    gt_list = [ground_truth_taxonomy]

    r_format = format_reward_func(c_list)[0]
    r_compliance = compliance_reward_func(c_list, lvl_list)[0]
    r_compiler = compiler_truth_reward_func(c_list, clog_list)[0]
    r_l1 = level1_policy_reward_func(c_list, lvl_list, clog_list)[0]
    r_density = pedagogical_density_reward_func(c_list, lvl_list)[0]
    r_anti_degen = anti_degeneration_reward_func(c_list)[0]
    r_l3 = level3_directive_reward_func(c_list, lvl_list)[0]
    r_gt_tax = ground_truth_taxonomy_reward_func(c_list, gt_list)[0]

    # Weighted composite sum
    total = (
        1.0 * r_format
        + 1.5 * r_compliance
        + 1.0 * r_compiler
        + 1.0 * r_l1
        + 1.2 * r_density
        + 1.0 * r_anti_degen
        + 0.8 * r_l3
        + (1.5 * r_gt_tax if ground_truth_taxonomy is not None else 0.0)
    )

    return {
        "total": float(total),
        "format": r_format,
        "compliance": r_compliance,
        "compiler_truth": r_compiler,
        "level1_policy": r_l1,
        "density": r_density,
        "anti_degeneration": r_anti_degen,
        "level3_directive": r_l3,
        "ground_truth_tax": r_gt_tax,
    }
