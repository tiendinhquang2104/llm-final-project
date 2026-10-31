"""Reinforcement Learning with Verifiable Rewards (RLVR) for Task 3.

Provides deterministic, execution-based, and rule-based reward functions
for Group Relative Policy Optimization (GRPO).

All rewards are programmatic and verifiable:
1. Format & Schema Verifier (valid JSON, correct keys, taxonomy space)
2. Pedagogical Level Compliance Verifier (Level 1-3 rules, zero severe leaks)
3. Compiler Truth Verifier (verifies 'Lỗi biên dịch' against actual compile status)
4. Level 1 Safe Policy Verifier (penalizes false positive taxonomy on Level 1)
5. Ground Truth Taxonomy F1 Verifier (when GT labels are provided)
6. Anti-Degeneration & Language Quality Verifier (penalizes repetitive/corrupted phrases)
7. Pedagogical Structure Verifier (checks 'Hướng sửa:' directive on Level 3)
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Union

from src.synth.taxonomy import LABEL_SPACE
from src.task3.compliance import check as compliance_check
from src.utils.json_extractor import extract_json_objects

# Known phrases that indicate language degeneration from overfitted adapters
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
# 1. Format & Schema Reward
# -----------------------------------------------------------------------------
def format_reward_func(completions: Sequence[str], **kwargs) -> List[float]:
    """Verifies that completion is valid JSON with required Task 3 keys."""
    rewards = []
    for c in completions:
        data = parse_completion(c)
        if not data:
            rewards.append(-2.0)
            continue

        has_tax = "taxonomy_error" in data and isinstance(data["taxonomy_error"], list)
        has_fb = "feedback" in data and isinstance(data["feedback"], str) and bool(data["feedback"].strip())

        if not (has_tax and has_fb):
            rewards.append(-1.0)
            continue

        # Check all taxonomy labels are in LABEL_SPACE
        invalid_labels = [lbl for lbl in data["taxonomy_error"] if lbl not in LABEL_SPACE]
        if invalid_labels:
            rewards.append(-0.5)
        else:
            rewards.append(1.0)
    return rewards


# -----------------------------------------------------------------------------
# 2. Level Compliance Verifier (Zero Severe Leaks)
# -----------------------------------------------------------------------------
def compliance_reward_func(
    completions: Sequence[str],
    target_feedback_level: Sequence[str],
    **kwargs,
) -> List[float]:
    """Evaluates strict pedagogical compliance using compliance.py v3."""
    rewards = []
    for c, lvl in zip(completions, target_feedback_level):
        data = parse_completion(c)
        if not data:
            rewards.append(-1.0)
            continue

        fb = data.get("feedback", "")
        if not fb.strip():
            rewards.append(-2.0)
            continue

        try:
            res = compliance_check(feedback=fb, level=lvl, version=3)
            if res.severe:
                # Severe leak (code solution in L1/L2) -> zero score on sample
                rewards.append(-2.5)
            elif res.ok:
                rewards.append(1.5)
            else:
                # Non-compliant violation (e.g. repair instruction in L2, or technical disclosure in L1)
                rewards.append(-1.0)
        except Exception:
            rewards.append(-0.5)
    return rewards


# -----------------------------------------------------------------------------
# 3. Compiler Truth Verifier
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
                rewards.append(1.0)  # Correctly identified compiler failure
            else:
                rewards.append(-1.0)  # Missed obvious compiler error
        else:
            if has_compile_error_label:
                rewards.append(-1.0)  # Hallucinated a compiler error on clean code
            else:
                rewards.append(0.5)  # Correctly did not output compile error
    return rewards


# -----------------------------------------------------------------------------
# 4. Level 1 Safe Policy Verifier
# -----------------------------------------------------------------------------
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
            # On compile failure, Level 1 should only have ['Lỗi biên dịch']
            if tax == ["Lỗi biên dịch"]:
                rewards.append(1.0)
            else:
                rewards.append(-0.5)
        else:
            # On non-compile error, Level 1 taxonomy MUST be empty []
            if len(tax) == 0:
                rewards.append(1.0)
            else:
                # Guessing taxonomy on Level 1 collapses macro-F1 due to false positives
                rewards.append(-1.5)
    return rewards


# -----------------------------------------------------------------------------
# 5. Anti-Degeneration & Natural Vietnamese Reward
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
            rewards.append(-2.0)
            continue

        # Check repetition: ratio of unique 3-grams to total 3-grams
        words = fb.lower().split()
        if len(words) >= 12:
            trigrams = [tuple(words[i : i + 3]) for i in range(len(words) - 2)]
            unique_ratio = len(set(trigrams)) / max(1, len(trigrams))
            if unique_ratio < 0.65:
                rewards.append(-1.5)  # High repetitive looping
                continue

        rewards.append(0.5)
    return rewards


# -----------------------------------------------------------------------------
# 6. Level 3 Action Directive Verifier
# -----------------------------------------------------------------------------
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
        # Level 3 requires actionable direction
        if re.search(r"\bhướng sửa\s*:", fb, re.IGNORECASE) or re.search(r"\bgợi ý sửa\s*:", fb, re.IGNORECASE):
            rewards.append(1.0)
        else:
            rewards.append(-0.5)
    return rewards


# -----------------------------------------------------------------------------
# Composite Verifiable Reward
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

    r_format = format_reward_func(c_list)[0]
    r_compliance = compliance_reward_func(c_list, lvl_list)[0]
    r_compiler = compiler_truth_reward_func(c_list, clog_list)[0]
    r_l1 = level1_policy_reward_func(c_list, lvl_list, clog_list)[0]
    r_anti_degen = anti_degeneration_reward_func(c_list)[0]
    r_l3 = level3_directive_reward_func(c_list, lvl_list)[0]

    # Ground truth taxonomy F1 (optional)
    r_gt_tax = 0.0
    if ground_truth_taxonomy is not None:
        data = parse_completion(completion)
        pred_tax = set(data.get("taxonomy_error", [])) if data else set()
        gt_tax = set(ground_truth_taxonomy)
        if not pred_tax and not gt_tax:
            r_gt_tax = 1.0
        elif not pred_tax or not gt_tax:
            r_gt_tax = 0.0
        else:
            intersection = len(pred_tax & gt_tax)
            prec = intersection / len(pred_tax)
            rec = intersection / len(gt_tax)
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            r_gt_tax = 1.5 * f1

    # Weights for composite sum
    total = (
        1.0 * r_format
        + 1.5 * r_compliance
        + 1.0 * r_compiler
        + 1.0 * r_l1
        + 1.0 * r_anti_degen
        + 0.5 * r_l3
        + (1.0 * r_gt_tax if ground_truth_taxonomy is not None else 0.0)
    )

    return {
        "total": float(total),
        "format": r_format,
        "compliance": r_compliance,
        "compiler_truth": r_compiler,
        "level1_policy": r_l1,
        "anti_degeneration": r_anti_degen,
        "level3_directive": r_l3,
        "ground_truth_tax": r_gt_tax,
    }
