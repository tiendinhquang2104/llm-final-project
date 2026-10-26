"""Offline agent-review rubric and frozen global selection; no model calls."""
from __future__ import annotations

import math
import random
from collections import Counter
from collections import defaultdict

POSITIVE = ("structural_valid", "Vietnamese", "factual_support", "critical_finding_coverage",
            "source_location_and_condition_fidelity", "level_compliance", "taxonomy_feedback_consistency")
NEGATIVE = ("clean_false_alarm", "false_clean", "invented_requirement", "l2_repair_leak")
RUBRIC = {"positive": list(POSITIVE), "negative": list(NEGATIVE),
          "unknown": "Any unknown or unresolved is joint_pass=0 on the full requested population.",
          "fallback": "Neutral disclosure fallback never establishes diagnostic success.",
          "L1": "Cautious status consistent with source and predicted taxonomy; no location/cause/repair.",
          "L2": "Source location, triggering condition and cause; no repair direction or replacement value.",
          "L3": "Supported cause plus feasible local repair; no full solution.",
          "reviewer": "Codex agent static source review; not official teacher or human-independent review.",
          "primary": "(115*J1+163*J2+50*J3)/328; internal proxy only",
          "tie": "A before B before C; checkpoint earliest optimizer step"}


def score_reviews(reviews: list[dict], request_manifest: dict) -> dict:
    requests = request_manifest["requests"]
    by_id = {r["sample_id"]: r for r in reviews}
    ids = {r["sample_id"] for r in requests}
    if len(ids) != len(requests) or len(by_id) != len(reviews) or not set(by_id) <= ids:
        raise ValueError("review population binding mismatch")
    cases = []
    for req in requests:
        review = by_id.get(req["sample_id"])
        if review:
            if any(review.get(k) != req[k] for k in ("output_sha256", "reference_sha256")):
                raise ValueError("review output/reference binding mismatch")
            if not review.get("reviewer") or not review.get("evidence"):
                raise ValueError("review evidence/provenance required")
            if any(review.get(k) not in (True, False, None) for k in POSITIVE + NEGATIVE):
                raise ValueError("semantic verdicts must be boolean or unknown")
        unknown = not review or any(review.get(k) is None for k in POSITIVE + NEGATIVE)
        fallback = req["origin"] == "disclosure_fallback"
        passed = bool(req["completed"] and not fallback and not unknown
                      and all(review.get(k) is True for k in POSITIVE)
                      and all(review.get(k) is False for k in NEGATIVE))
        cases.append({**req, "joint_pass": passed, "unknown": unknown, "fallback": fallback,
                      "unsupported": bool(review and review.get("factual_support") is False),
                      "critical_miss": bool(review and review.get("critical_finding_coverage") is False),
                      "repair_leak": bool(req["level"] == 2 and review and review.get("l2_repair_leak") is True),
                      "verdicts": {k: review.get(k) if review else None for k in POSITIVE + NEGATIVE}})
    per_level = {}
    for level in (1, 2, 3):
        rows = [r for r in cases if r["level"] == level]
        per_level[str(level)] = {"population": len(rows), "joint_pass": sum(r["joint_pass"] for r in rows),
                                 "rate": sum(r["joint_pass"] for r in rows) / len(rows) if rows else 0.,
                                 "unknown": sum(r["unknown"] for r in rows)}
    return {"population": len(cases), "completed": sum(r["completed"] for r in cases),
            "joint_pass_count": sum(r["joint_pass"] for r in cases), "per_level": per_level,
            "JointScore": sum(w * per_level[str(i)]["rate"] for i, w in enumerate((115, 163, 50), 1)) / 328,
            "macro3Levels": sum(per_level[str(i)]["rate"] for i in (1, 2, 3)) / 3,
            "unknown": sum(r["unknown"] for r in cases), "fallback_count": sum(r["fallback"] for r in cases),
            "unsupported_claim_cases": sum(r["unsupported"] for r in cases),
            "l2_repair_leak_cases": sum(r["repair_leak"] for r in cases),
            "critical_finding_misses": sum(r["critical_miss"] for r in cases), "cases": cases,
            "factual_only": {"numerator": sum(r["verdicts"]["factual_support"] is True for r in cases),
                             "denominator": sum(r["verdicts"]["factual_support"] is not None for r in cases)},
            "flag_counts": {k: sum(r["verdicts"][k] is True for r in cases) for k in NEGATIVE}}


def select_checkpoint(candidates: list[dict], reviews: list[dict], *, baseline_score=0.) -> dict:
    if not candidates or any(not math.isfinite(c["metrics"]["JointScore"]) for c in candidates):
        raise ValueError("checkpoint selection requires finite semantic scores")
    best = min(candidates, key=lambda c: (-c["metrics"]["JointScore"], c["step"]))
    return {"selected": best["name"], "step": best["step"], "candidates": candidates,
            "policy": "max_checkpoint_dev_JointScore_earliest_step_tie",
            "promotion_eligible": best["metrics"]["JointScore"] >= baseline_score,
            "public_used": False}


def select_method(metrics_by_arm: dict) -> dict:
    base = metrics_by_arm["A"]
    eligible = ["A"]
    for arm in ("B", "C"):
        m = metrics_by_arm.get(arm)
        if (m and m["population"] == base["population"] and m["completed"] == m["population"]
                and m["JointScore"] > base["JointScore"]
                and all(m[k] <= base[k] for k in ("unsupported_claim_cases", "l2_repair_leak_cases", "critical_finding_misses"))):
            eligible.append(arm)
    winner = min(eligible, key=lambda arm: (-metrics_by_arm[arm]["JointScore"], "ABC".index(arm)))
    return {"recommended": winner, "eligible": eligible, "scope": "one_method_all_ids_all_levels",
            "public_observation_allowed": [a for a in "ABC" if metrics_by_arm.get(a)],
            "policy": "strict_improvement_complete_coverage_no_extra_unsupported_L2_leak_or_critical_miss",
            "public_used": False}


def taxonomy_summary(gold, predicted):
    from src.synth.taxonomy import LABEL_SPACE
    if len(gold) != len(predicted) or not gold:
        raise ValueError("taxonomy comparison population mismatch")
    tp = fp = fn = 0
    per_label = {}
    for label in LABEL_SPACE:
        hits = sum(label in g and p is not None and label in p for g, p in zip(gold, predicted))
        extra = sum(label not in g and p is not None and label in p for g, p in zip(gold, predicted))
        missed = sum(label in g and (p is None or label not in p) for g, p in zip(gold, predicted))
        per_label[label] = {"TP": hits, "FP": extra, "FN": missed,
                            "F1": 2 * hits / (2 * hits + extra + missed) if 2 * hits + extra + missed else 0.}
        tp += hits
        fp += extra
        fn += missed
    return {"population": len(gold), "invalid": sum(p is None for p in predicted),
            "micro_F1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.,
            "macro_F1_all_official_labels": sum(r["F1"] for r in per_label.values()) / len(per_label),
            "exact_match": sum(p is not None and set(g) == set(p) for g, p in zip(gold, predicted)) / len(gold),
            "per_label": per_label, "reference": "unchanged original annotations; unresolved output is not []"}


def paired_analysis(base, candidate, *, draws=2000):
    left = {r["sample_id"]: r for r in base["cases"]}
    right = {r["sample_id"]: r for r in candidate["cases"]}
    if set(left) != set(right):
        raise ValueError("paired comparison IDs differ")
    groups = defaultdict(list)
    for sid, row in left.items():
        if row["source_group"] != right[sid]["source_group"] or row["level"] != right[sid]["level"]:
            raise ValueError("paired source/Level binding differs")
        groups[row["source_group"]].append((row, right[sid]))
    differences = {g: sum(int(b["joint_pass"]) - int(a["joint_pass"]) for a, b in pairs) / len(pairs)
                   for g, pairs in groups.items()}
    wins = sum(d > 0 for d in differences.values())
    losses = sum(d < 0 for d in differences.values())
    rng = random.Random(42)
    names = sorted(groups)
    bootstrap = []
    for _ in range(draws):
        pairs = [pair for group in rng.choices(names, k=len(names)) for pair in groups[group]]
        total = 0.
        for level, weight in ((1, 115), (2, 163), (3, 50)):
            rows = [(a, b) for a, b in pairs if a["level"] == level]
            if rows:
                total += weight * sum(int(b["joint_pass"]) - int(a["joint_pass"]) for a, b in rows) / len(rows) / 328
        bootstrap.append(total)
    bootstrap.sort()
    return {"source_groups": len(groups), "requests": len(left), "bootstrap_unit": "source_group", "draws": draws,
            "win_loss_tie": {"wins": wins, "losses": losses, "ties": len(groups) - wins - losses},
            "paired_JointScore_delta_95pct": [bootstrap[int(.025 * (draws - 1))], bootstrap[int(.975 * (draws - 1))]],
            "source_differences": differences, "scope": "exposed internal development; not leaderboard accuracy"}
