"""Task 1 zero-shot: hand-written rubric questions scored by the original CLM heads (no training).
Per dimension: softmax over one description per level -> expected level; per problem of a multi_problem exam:
a yes/no status question feeding the prerequisite rule. Compilable comes from the compile log.
Only gold-derived inputs: the prompt texts."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from src.clm_zeroshot.guides import PROBLEM_QUESTION, RUBRIC_LEVELS, RUBRIC_QUESTIONS
from src.clm_zeroshot.scoring import choice_probs, noul_candidates, noul_prob, question_states
from src.data.loader import DIM_MAX, DIMENSIONS
from src.task1.evaluator import evaluate, validate_predictions
from src.task1.experiment import _git_commit, _write_json, append_registry
from src.task1.prerequisite_rules import RuleConfig, apply_rules, policy_from_exam
from src.task2.benchmark import hardware_info
from src.task2.clm.heads import NoulModel
from src.task2.compile import has_compile_error

SCORED = list(RUBRIC_QUESTIONS)  # the 5 dimensions other than compilable


def _heads(heads) -> NoulModel:
    return heads if isinstance(heads, NoulModel) else NoulModel.from_checkpoint(heads)


def dimension_scores(samples, exams, encoder, heads, text_cfg: dict) -> dict[str, np.ndarray]:
    """Expected level sum_i i*p_i per scored dimension -> {dim: [n]}, each within [0, DIM_MAX[dim]]."""
    n = len(samples)
    if not n:
        return {d: np.zeros(0, np.float32) for d in SCORED}
    heads = _heads(heads)
    questions = [RUBRIC_QUESTIONS[d] for d in SCORED]
    texts = [t for s in samples for t in question_states(exams[s.exam_id], s, encoder.tokenizer, questions, text_cfg)]
    S = encoder.embed(texts).reshape(n, len(SCORED), -1)
    out = {}
    for j, d in enumerate(SCORED):
        C = encoder.embed(RUBRIC_LEVELS[d])
        p = choice_probs(heads, S[:, j], C)
        out[d] = (p * np.arange(p.shape[1])).sum(1)
    return out


def problem_status(samples, exams, encoder, heads, text_cfg: dict) -> list[dict[str, str]]:
    """Per sample {pid: "correct"|"wrong"} for multi_problem exams, {} for single-problem ones."""
    res: list[dict[str, str]] = [{} for _ in samples]
    items = [(k, p["pid"], PROBLEM_QUESTION.format(pid=p["pid"], prototype=p.get("prototype", "")))
             for k, s in enumerate(samples) if exams[s.exam_id].get("exam_type") == "multi_problem"
             for p in exams[s.exam_id].get("problems", [])]
    if not items:
        return res
    heads = _heads(heads)
    texts = []
    for k, pid, q in items:
        texts += question_states(exams[samples[k].exam_id], samples[k], encoder.tokenizer, [q], text_cfg)
    S = encoder.embed(texts)
    C = encoder.embed([t for _, _, q in items for t in noul_candidates(q)]).reshape(len(items), 2, -1)
    for i, (k, pid, _) in enumerate(items):
        p = float(noul_prob(heads, S[i:i + 1], C[i])[0])
        res[k][pid] = "correct" if p >= 0.5 else "wrong"
    return res


def assemble(scores_row: dict, compile_err: bool, statuses: dict, exam: dict) -> tuple[dict, int, list[str]]:
    """Round + clamp the expected levels, set compilable from the compile log, apply the grading-policy rules."""
    rubric = {"compilable": 0 if compile_err else 1}
    for d in SCORED:
        rubric[d] = int(min(max(np.floor(float(scores_row[d]) + 0.5), 0), DIM_MAX[d]))
    return apply_rules(rubric, statuses, policy_from_exam(exam),
                       RuleConfig(prerequisite=True, compile_gate=True, clamp=True))


def _predict(samples, exams, encoder, heads, text_cfg):
    sc = dimension_scores(samples, exams, encoder, heads, text_cfg)
    st = problem_status(samples, exams, encoder, heads, text_cfg)
    errs = [bool(has_compile_error(s.compile_log)) for s in samples]
    rows = []
    for k, s in enumerate(samples):
        row = {d: float(sc[d][k]) for d in SCORED}
        r, t, trace = assemble(row, errs[k], st[k], exams[s.exam_id])
        rows.append({"sample_id": s.sample_id, "exam_id": s.exam_id, "has_compile_error": errs[k],
                     "expected": {d: round(v, 4) for d, v in row.items()}, "statuses": st[k],
                     "rule_trace": trace, "rubric": r, "total_score": t})
    return rows


def run_task1_zeroshot(cfg: dict, encoder, heads_path, gold, rubrics: dict, public, public_ids, out_dir,
                       registry: Path | None = None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    text_cfg = cfg.get("text", {})
    heads = NoulModel.from_checkpoint(heads_path)
    gold_s = sorted((s for s in gold.samples if s.sample_id in rubrics), key=lambda s: s.sample_id)
    pub_by_id = {s.sample_id: s for s in public.samples} if public else {}
    missing = [i for i in public_ids if i not in pub_by_id]
    if missing:
        raise KeyError(f"public ids not loaded: {missing[:5]}")
    pub = [pub_by_id[i] for i in dict.fromkeys(public_ids)]
    t0 = time.time()
    g_rows = _predict(gold_s, gold.exams, encoder, heads, text_cfg)
    p_rows = _predict(pub, public.exams if public else {}, encoder, heads, text_cfg)
    seconds = time.time() - t0
    gold_map = {s.sample_id: rubrics[s.sample_id] for s in gold_s}
    systems = {"clm_zeroshot_prompts": evaluate(
        gold_map, {r["sample_id"]: {"rubric": r["rubric"], "total_score": r["total_score"]} for r in g_rows})}
    preds = [{"sample_id": r["sample_id"], "output": {"rubric": r["rubric"], "total_score": r["total_score"]}}
             for r in p_rows]
    errs = validate_predictions(preds, set(public_ids))
    extra = {p["sample_id"] for p in preds} - set(public_ids)
    if errs or extra:
        raise ValueError(f"invalid Task 1 predictions: {errs[:5]} extra={sorted(extra)[:5]}")
    _write_json(out_dir / "predictions.json", preds)
    _write_json(out_dir / "predictions_full.json", p_rows)
    metrics = {"name": cfg["name"], "mode": "clm_zeroshot",
               "evaluation": "in-sample over gold (prompts derived from gold: optimistic)",
               "n_gold": len(gold_s), "n_public": len(pub), "systems": systems,
               "compile": {"enabled": cfg.get("_compiler_id") is not None, "compiler_id": cfg.get("_compiler_id")}}
    n = len(gold_s) + len(pub)
    resources = {"backend": "clm", "model": getattr(encoder, "encoder_id", ""), "hardware": hardware_info(),
                 "n_samples": n, "seconds_per_sample": seconds / n if n else None,
                 "peak_memory_gb": encoder.peak_memory_gb() if hasattr(encoder, "peak_memory_gb") else None,
                 "tokens_in": None, "tokens_out": None, "cost_usd": 0.0}
    _write_json(out_dir / "metrics.json", metrics)
    _write_json(out_dir / "resources.json", resources)
    _write_json(out_dir / "config.json", {"config": cfg, "heads": str(heads_path),
                                          "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                          "public_ids": [s.sample_id for s in pub]})
    if registry is not None:
        best = systems["clm_zeroshot_prompts"]
        append_registry({"experiment_id": cfg["name"], "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "task": "task1", "model": resources["model"], "config_path": cfg.get("_config_path", ""),
                         "train_loss": "",
                         "metrics": json.dumps({"qwk_in_sample": best["qwk"], "mae_in_sample": best["mae"],
                                                "n_gold": len(gold_s)}),
                         "git_commit": _git_commit(), "notes": cfg.get("description", "")}, registry)
    return metrics
