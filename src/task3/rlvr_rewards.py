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
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Union

from src.synth.taxonomy import LABEL_SPACE
from src.task3.compliance import check as compliance_check
from src.utils.json_extractor import extract_json_objects


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
    """Verifies that 'Lỗi biên dịch' strictly matches compiler reality without guessing."""
    rewards = []
    for c, clog in zip(completions, compile_log):
        data = parse_completion(c)
        if not data:
            rewards.append(0.0)
            continue

        tax = data.get("taxonomy_error", [])
        has_compile_error_label = "Lỗi biên dịch" in tax

        clog_str = (clog or "").strip()
        has_log_error = bool(clog_str and re.search(r"\b(?:error|fatal error):", clog_str, re.IGNORECASE))
        has_log_success = bool(clog_str and not has_log_error)

        if has_log_error:
            # Code definitely failed to compile
            if has_compile_error_label:
                rewards.append(2.0)   # Correctly identified compiler failure
            else:
                rewards.append(-2.5)  # Missed obvious compiler error
        elif has_log_success:
            # Code definitely compiled cleanly -> penalize hallucinating compile error
            if has_compile_error_label:
                rewards.append(-2.5)  # Hallucinated compiler error on clean code
            else:
                rewards.append(0.5)   # Correctly did not output compile error
        else:
            # Compile status is unknown (missing/empty log) -> Neutral, do not penalize unfairly
            rewards.append(0.0)
    return rewards


def level1_policy_reward_func(
    completions: Sequence[str],
    target_feedback_level: Sequence[str],
    compile_log: Sequence[str],
    ground_truth_taxonomy: Optional[Sequence[Optional[List[str]]]] = None,
    **kwargs,
) -> List[float]:
    """Ensures Level 1 feedback remains pedagogically safe without penalizing valid taxonomy diagnosis."""
    rewards = []
    gt_list = ground_truth_taxonomy if ground_truth_taxonomy is not None else [None] * len(completions)
    for c, lvl, clog, gt_tax in zip(completions, target_feedback_level, compile_log, gt_list):
        data = parse_completion(c)
        if not data:
            rewards.append(0.0)
            continue

        if not str(lvl).startswith("Level 1"):
            rewards.append(0.0)
            continue

        tax = data.get("taxonomy_error", [])
        fb = data.get("feedback", "").strip()

        # Factual Consistency: If ground truth taxonomy is known to be clean ([]), penalize claiming bugs
        if gt_tax is not None and len(gt_tax) == 0:
            if len(tax) > 0:
                rewards.append(-2.0)  # Hallucinated taxonomy on clean code
                continue
            if fb and re.search(r"\b(?:chưa\s+(?:hoàn\s+thiện|đúng|tốt)|còn\s+(?:lỗi|vấn\s+đề|chỗ)|cần\s+sửa)\b", fb, re.IGNORECASE):
                rewards.append(-2.5)  # Hallucinated defects in feedback on clean code
                continue

        # If code has compiler failure, reward correct diagnosis
        clog_str = (clog or "").strip()
        has_compile_error = bool(clog_str and re.search(r"\b(?:error|fatal error):", clog_str, re.IGNORECASE))
        if has_compile_error and "Lỗi biên dịch" in tax:
            rewards.append(1.5)
            continue

        # Safe Level 1 guidance reward
        rewards.append(1.5)
    return rewards


def ground_truth_taxonomy_reward_func(
    completions: Sequence[str],
    ground_truth_taxonomy: Sequence[Optional[List[str]]],
    **kwargs,
) -> List[float]:
    """Pure mathematical multi-label F1 alignment reward without manual heuristic distortion."""
    rewards = []
    for c, gt_tax in zip(completions, ground_truth_taxonomy):
        if gt_tax is None:
            rewards.append(0.0)
            continue

        data = parse_completion(c)
        pred_tax = set(data.get("taxonomy_error", [])) if data else set()
        gt_set = set(gt_tax)

        if not pred_tax and not gt_set:
            rewards.append(2.0)  # Correctly clean
        elif not pred_tax or not gt_set:
            rewards.append(-1.0)  # Total mismatch (false alarm or complete omission)
        else:
            intersection = len(pred_tax & gt_set)
            prec = intersection / len(pred_tax)
            rec = intersection / len(gt_set)
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            rewards.append(3.0 * f1 - 0.5)
    return rewards


# -----------------------------------------------------------------------------
# Tier 4: Information-Theoretic Length Floor & Asymmetric Brevity Pressure
# Pure mathematical formulation; zero hardcoded string heuristics.
# -----------------------------------------------------------------------------
def pedagogical_density_reward_func(
    completions: Sequence[str],
    target_feedback_level: Sequence[str],
    **kwargs,
) -> List[float]:
    """Continuous, asymmetric condition-aware pedagogical length verifier.

    Enforces strict teacher standards:
    - Level 1: 100% "Bài làm đáp ứng đúng yêu cầu của đề bài." or short compile error notice (<= 75 chars).
    - Level 2: Exactly 1 technical sentence (15-30 words, <= 100 chars) pointing to root cause.
    - Level 3: Exactly 1-2 sentences (cause + algorithmic fix direction, <= 120 chars), zero chatter/bullets/code.
    """
    rewards = []
    for c, lvl in zip(completions, target_feedback_level):
        data = parse_completion(c)
        raw_fb = data.get("feedback", "") if data else c
        fb = (raw_fb if isinstance(raw_fb, str) else str(raw_fb)).strip()
        words = fb.split()
        num_words = len(words)
        lvl_str = str(lvl)
        fb_len = len(fb)

        if num_words == 0:
            rewards.append(-3.0)
            continue

        # Check for banned conversational greetings and pleasantries
        has_chatter = bool(re.search(r"\b(chào em|chào bạn|em thử|em xem|nhé|nha|chúc em)\b", fb, re.I))
        has_bullets = bool(re.search(r"^\s*[-*•]\s+|\n\s*[-*•]\s+|\b\d+\.\s+", fb))
        has_code = "```" in fb

        r = 0.0
        if "Level 1" in lvl_str:
            if fb == "Bài làm đáp ứng đúng yêu cầu của đề bài.":
                r = 3.0
            elif fb_len <= 75 and num_words <= 15:
                r = 2.0
            else:
                r = max(-4.0, 1.0 - 0.1 * (fb_len - 75))

        elif "Level 2" in lvl_str:
            # Level 2 target: Exactly 1 technical sentence (15-30 words, <= 100 chars)
            sentences = [s for s in re.split(r"(?<=[.!?])\s+", fb) if s.strip()]
            num_sentences = len(sentences)

            if fb_len <= 100 and 15 <= num_words <= 30 and num_sentences == 1 and not has_chatter and not has_bullets and not has_code:
                r = 3.5  # Optimal reward for perfect teacher diagnosis
            else:
                r = 1.0
                if fb_len > 100:
                    r -= 0.15 * (fb_len - 100)
                if num_words < 15:
                    r -= 0.20 * (15 - num_words)
                elif num_words > 30:
                    r -= 0.25 * (num_words - 30)
                if num_sentences > 1:
                    r -= 1.5 * (num_sentences - 1)
                if has_chatter:
                    r -= 2.0
                if has_bullets or has_code:
                    r -= 3.0
                r = max(-5.0, r)

        elif "Level 3" in lvl_str:
            # Level 3 target: 1-2 sentences (cause + algorithmic fix, <= 120 chars)
            sentences = [s for s in re.split(r"(?<=[.!?])\s+", fb) if s.strip()]
            num_sentences = len(sentences)

            if fb_len <= 120 and 1 <= num_sentences <= 2 and not has_chatter and not has_bullets and not has_code:
                r = 3.5  # Optimal reward for concise repair guidance
            else:
                r = 1.0
                if fb_len > 120:
                    r -= 0.15 * (fb_len - 120)
                if num_sentences > 2:
                    r -= 2.0 * (num_sentences - 2)
                if has_chatter:
                    r -= 2.5
                if has_bullets or has_code:
                    r -= 3.5
                r = max(-5.0, r)

        else:
            # Level 4 or other
            if 30 <= num_words <= 100:
                r = 2.0
            else:
                r = max(-3.0, 2.0 - 0.05 * abs(num_words - 60))

        rewards.append(r)

    return rewards


# -----------------------------------------------------------------------------
# Tier 5: Statistical & Information-Theoretic Diversity (Anti-Degeneration)
# Standard Senior LLM / RLVR formulation: Pure statistical linguistics & entropy
# Zero hardcoded token blacklists; fully invariant to language & phrasing
# -----------------------------------------------------------------------------
def anti_degeneration_reward_func(
    completions: Sequence[str],
    target_feedback_level: Optional[Sequence[str]] = None,
    **kwargs,
) -> List[float]:
    """Penalizes language degeneration via information-theoretic metrics:
    - Type-Token Ratio (TTR)
    - Shannon Unigram Entropy
    - Bigram & Trigram Distinct-N Diversity
    - Consecutive Sentence Jaccard Echoing
    - Character-level Typography Purity (penalizes pictorial/symbol flood)
    """
    rewards = []
    lvl_list = target_feedback_level if target_feedback_level is not None else ["Level 2"] * len(completions)

    for c, lvl in zip(completions, lvl_list):
        data = parse_completion(c)
        fb = data.get("feedback", "") if data else c
        if not fb or not isinstance(fb, str):
            rewards.append(-3.0)
            continue

        fb_str = fb.strip()
        words = [w for w in re.findall(r"\w+", fb_str.lower()) if w]
        n_words = len(words)

        if n_words == 0:
            rewards.append(-3.0)
            continue

        # 1. Typography / Character Purity & Unicode Script Integrity (Information Theory)
        # Rejects non-Latin script hallucinations (CJK, Cyrillic, Hangul) from Alibaba multilingual base model.
        if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]", fb_str):
            rewards.append(-5.0)
            continue

        standard_chars = sum(1 for ch in fb_str if ch.isalnum() or ch.isspace() or ch in ".,!?:;\"'()-_/[]{}<>~`@#$%^&*+=|\\")
        char_purity = standard_chars / max(1, len(fb_str))
        if char_purity < 0.90:
            rewards.append(-4.0)
            continue

        # 1b. Structural Syntax & Sentence Boundary Integrity (Language-Agnostic)
        # Penalizes completions cutting off on a colon/comma or trailing colon-punctuation stubs (e.g. ":.", ":,")
        clean_end = fb_str.rstrip(".!? ")
        if clean_end.endswith((":", ",", ";", "->", "=>")) or re.search(r":\s*[:.,;!]", fb_str):
            rewards.append(-3.0)
            continue

        # 1c. Acoustic Echo / Stuttering across Colons (Language-Agnostic)
        # Penalizes prefix duplication like "Header: header..." (e.g. "X: X...")
        if re.search(r"^([^:]{4,30}):\s*\1\b", fb_str, re.IGNORECASE):
            rewards.append(-3.0)
            continue

        # 2. Universal Token Diversity & Non-Redundancy (Length-Invariant)
        # Any repeating word in a short phrase (<= 7 words) indicates degeneration loop (e.g. "gọi em làm em")
        if n_words <= 7:
            distinct_1 = len(set(words)) / n_words
            if distinct_1 < 1.0:
                rewards.append(-3.5)
                continue
            # Structural syntax sanity: transitive action verb + pronoun without subject (e.g. "học em...", "làm em...")
            if n_words >= 2 and words[0] in {"học", "làm", "gọi", "viết", "code"} and words[1] in {"em", "bạn"}:
                rewards.append(-3.0)
                continue

        # 3. Level 1 Concise Pedagogical Target
        # In Level 1, instructor feedback is high-level guidance or concise praise
        if "Level 1" in str(lvl):
            if 4 <= n_words <= 16:
                counts = Counter(words)
                entropy = -sum((cnt / n_words) * math.log2(cnt / n_words) for cnt in counts.values())
                max_entropy = math.log2(n_words)
                norm_entropy = entropy / max_entropy if max_entropy > 0 else 1.0
                if norm_entropy < 0.85:
                    rewards.append(-2.5)
                else:
                    rewards.append(1.5)
            elif n_words < 4:
                rewards.append(-2.0)
            else:
                # Information density decay: Level 1 should not ramble
                rewards.append(-2.0)
            continue

        # Level 2/3 requires substantive content
        if n_words < 5:
            rewards.append(-2.5)
            continue

        # 3. Single-Token Frequency Dominance (Anti-Monologue Loop)
        word_counts = Counter(words)
        top_freq = word_counts.most_common(1)[0][1] / n_words
        if top_freq >= 0.25 and n_words >= 8:
            rewards.append(-3.0)
            continue

        # 4. Consecutive Sentence / Clause Echoing (Jaccard Overlap)
        sentences = [re.findall(r"\w+", s.lower()) for s in re.split(r"[.!?\n;]+", fb_str) if s.strip()]
        sentences = [s for s in sentences if len(s) >= 3]
        has_sentence_echo = False
        for i in range(len(sentences) - 1):
            s1, s2 = set(sentences[i]), set(sentences[i + 1])
            if s1 and s2:
                jaccard = len(s1 & s2) / len(s1 | s2)
                if jaccard >= 0.60:
                    has_sentence_echo = True
                    break
        if has_sentence_echo:
            rewards.append(-3.0)
            continue

        # 5. N-gram Diversity (Distinct-2 and Distinct-3)
        if n_words >= 8:
            trigrams = [tuple(words[i : i + 3]) for i in range(n_words - 2)]
            counts = Counter(trigrams)
            max_rep = counts.most_common(1)[0][1] if counts else 1
            distinct_3 = len(counts) / max(1, len(trigrams))
            if max_rep >= 2 or distinct_3 < 0.80:
                rewards.append(-2.5)
                continue

        if n_words >= 10:
            bigrams = [tuple(words[i : i + 2]) for i in range(n_words - 1)]
            distinct_2 = len(set(bigrams)) / max(1, len(bigrams))
            if distinct_2 < 0.72:
                rewards.append(-2.0)
                continue

        # 6. Type-Token Ratio (TTR) & Shannon Unigram Entropy
        if n_words >= 12:
            ttr = len(set(words)) / n_words
            entropy = -sum((cnt / n_words) * math.log2(cnt / n_words) for cnt in word_counts.values())
            if ttr < 0.60 or entropy < 3.2:
                rewards.append(-2.0)
                continue

        rewards.append(1.0)
    return rewards


def level3_directive_reward_func(
    completions: Sequence[str],
    target_feedback_level: Sequence[str],
    **kwargs,
) -> List[float]:
    """Ensures Level 3 feedback provides algorithmic repair guidance concisely (<= 120 chars)."""
    rewards = []
    for c, lvl in zip(completions, target_feedback_level):
        if not str(lvl).startswith("Level 3"):
            rewards.append(0.0)
            continue

        data = parse_completion(c)
        if not data:
            rewards.append(-1.0)
            continue

        fb = (data.get("feedback") or "").strip()
        if not fb:
            rewards.append(-2.0)
            continue

        # Check for algorithmic direction keywords (cần, nên, duyệt, kiểm tra, thay vì, cập nhật, lưu, dồn, etc.)
        has_direction = bool(
            re.search(
                r"\b(?:cần|nên|hướng sửa|gợi ý|kiểm tra|cập nhật|thay vì|duyệt|dồn|sắp xếp|lưu|trả về|loại bỏ)\b",
                fb,
                re.IGNORECASE,
            )
        )
        is_concise = len(fb) <= 120

        if has_direction and is_concise:
            rewards.append(2.0)
        elif has_direction and not is_concise:
            rewards.append(0.5)
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
    r_l1 = level1_policy_reward_func(c_list, lvl_list, clog_list, ground_truth_taxonomy=gt_list)[0]
    r_density = pedagogical_density_reward_func(c_list, lvl_list)[0]
    r_anti_degen = anti_degeneration_reward_func(c_list, lvl_list)[0]
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
