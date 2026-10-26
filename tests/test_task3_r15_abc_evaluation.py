"""Semantic selection must not turn missing evidence or fallback into success."""
import copy
import pytest


def manifest():
    return {"requests": [{"sample_id": "a", "level": 2, "source_group": "g", "output_sha256": "o",
                           "reference_sha256": "r", "origin": "qwen_initial", "completed": True}]}


def review(**extra):
    return {"sample_id": "a", "output_sha256": "o", "reference_sha256": "r", "reviewer": "codex-agent",
            "structural_valid": True, "Vietnamese": True, "factual_support": True,
            "critical_finding_coverage": True, "source_location_and_condition_fidelity": True,
            "level_compliance": True, "taxonomy_feedback_consistency": True,
            "clean_false_alarm": False, "false_clean": False, "invented_requirement": False,
            "l2_repair_leak": False, "evidence": "Source-grounded review", **extra}


def test_unknown_and_unresolved_not_joint_pass():
    from src.task3.r15_abc_evaluation import score_reviews
    assert score_reviews([review(factual_support=None)], manifest())["joint_pass_count"] == 0
    assert score_reviews([], manifest())["unknown"] == 1
    m = manifest()
    m["requests"][0]["completed"] = False
    assert score_reviews([review()], m)["joint_pass_count"] == 0


def test_neutral_fallback_not_diagnostic_success():
    from src.task3.r15_abc_evaluation import score_reviews
    m = manifest()
    m["requests"][0]["origin"] = "disclosure_fallback"
    result = score_reviews([review()], m)
    assert result["joint_pass_count"] == 0
    assert result["fallback_count"] == 1


def test_review_hash_drift_rejected():
    from src.task3.r15_abc_evaluation import score_reviews
    with pytest.raises(ValueError, match="binding"):
        score_reviews([review(output_sha256="different")], manifest())


def test_checkpoint_tie_uses_earlier_step():
    from src.task3.r15_abc_evaluation import select_checkpoint
    candidates = [{"name": "final", "step": 30, "metrics": {"JointScore": .2}},
                  {"name": "half", "step": 15, "metrics": {"JointScore": .2}}]
    result = select_checkpoint(candidates, [], baseline_score=.3)
    assert result["selected"] == "half"
    assert result["promotion_eligible"] is False


def test_global_selection_never_switches_per_id():
    from src.task3.r15_abc_evaluation import select_method
    base = {"JointScore": .4, "completed": 90, "population": 90, "unsupported_claim_cases": 3,
            "l2_repair_leak_cases": 1, "critical_finding_misses": 2}
    metrics = {"A": base, "B": {**base, "JointScore": .5, "unsupported_claim_cases": 4},
               "C": {**base, "JointScore": .45}}
    result = select_method(metrics)
    assert result["recommended"] == "C"
    assert result["scope"] == "one_method_all_ids_all_levels"
    assert "by_id" not in result


def test_low_quality_does_not_block_public_observation():
    from src.task3.r15_abc_evaluation import select_method
    base = {"JointScore": 0., "completed": 90, "population": 90, "unsupported_claim_cases": 90,
            "l2_repair_leak_cases": 30, "critical_finding_misses": 90}
    r = select_method({arm: copy.deepcopy(base) for arm in "ABC"})
    assert r["recommended"] == "A"
    assert r["public_observation_allowed"] == ["A", "B", "C"]


def test_paired_analysis_resamples_source_groups_not_level_variants():
    from src.task3.r15_abc_evaluation import paired_analysis
    a = {"cases": [{"sample_id": "x@L1", "level": 1, "source_group": "g", "joint_pass": False},
                   {"sample_id": "x@L2", "level": 2, "source_group": "g", "joint_pass": False}]}
    b = {"cases": [{**r, "joint_pass": True} for r in a["cases"]]}
    result = paired_analysis(a, b, draws=20)
    assert result["source_groups"] == 1
    assert result["win_loss_tie"] == {"wins": 1, "losses": 0, "ties": 0}
    assert result["bootstrap_unit"] == "source_group"


def test_invalid_taxonomy_output_is_not_an_empty_clean_prediction():
    from src.task3.r15_abc_evaluation import taxonomy_summary
    result = taxonomy_summary([[], ["Lỗi logic"]], [None, ["Lỗi logic"]])
    assert result["exact_match"] == .5
    assert result["invalid"] == 1
