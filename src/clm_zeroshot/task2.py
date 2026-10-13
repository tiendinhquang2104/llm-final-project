"""Task 2 zero-shot: one hand-written yes/no question per label scored by the original CLM heads (no training).
Only gold-derived inputs: the prompt texts and the per-label label frequency used to place each threshold."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from src.clm_zeroshot.guides import LABEL_QUESTIONS
from src.clm_zeroshot.scoring import noul_candidates, noul_prob, question_states
from src.task1.experiment import _git_commit, _write_json, append_registry
from src.task2.benchmark import hardware_info
from src.task2.clm.experiment import _select_public
from src.task2.clm.heads import NoulModel
from src.task2.compile import has_compile_error
from src.task2.evaluator import f1_scores, write_submission
from src.task2.labels import LABELS, from_vector, to_vector

COMPILE_LABEL = "Lỗi biên dịch"


def _candidates(encoder) -> np.ndarray:
    texts = [t for lab in LABELS for t in noul_candidates(LABEL_QUESTIONS[lab])]
    return encoder.embed(texts).reshape(len(LABELS), 2, -1)


def label_probs(samples, exams, encoder, heads, text_cfg: dict) -> np.ndarray:
    """P(yes) per (sample, label) -> [n, 10]. `heads` is a NoulModel or a checkpoint path."""
    if not isinstance(heads, NoulModel):
        heads = NoulModel.from_checkpoint(heads)
    if not len(samples):
        return np.zeros((0, len(LABELS)), np.float32)
    C = _candidates(encoder)
    questions = [LABEL_QUESTIONS[lab] for lab in LABELS]
    texts = [t for s in samples for t in question_states(exams[s.exam_id], s, encoder.tokenizer, questions, text_cfg)]
    S = encoder.embed(texts).reshape(len(samples), len(LABELS), -1)
    return np.stack([noul_prob(heads, S[:, j], C[j]) for j in range(len(LABELS))], axis=1)


def prevalence_thresholds(P_gold: np.ndarray, Y_gold: np.ndarray, floor: float) -> np.ndarray:
    """Per label: the (1 - p) quantile of P_gold, p = max(label frequency, floor)."""
    p = np.maximum(np.asarray(Y_gold, float).mean(0), float(floor))
    return np.array([np.quantile(P_gold[:, j], 1.0 - min(p[j], 1.0), method="higher")
                     for j in range(P_gold.shape[1])])


def decide(P: np.ndarray, thr: np.ndarray, compile_err: np.ndarray,
           max_labels: int | None = None) -> np.ndarray:
    pred = np.asarray(P) >= np.asarray(thr)
    compile_idx = LABELS.index(COMPILE_LABEL)
    pred[:, compile_idx] = np.asarray(compile_err, bool)
    if max_labels is not None and max_labels > 0:
        thr_arr = np.asarray(thr)
        for i in range(pred.shape[0]):
            active = [j for j in range(len(LABELS)) if pred[i, j] and j != compile_idx]
            if len(active) > max_labels:
                ranked = sorted(active, key=lambda j: float(P[i, j] - thr_arr[j]), reverse=True)
                for j in ranked[max_labels:]:
                    pred[i, j] = False
    return pred


def run_task2_zeroshot(cfg: dict, encoder, heads_path, gold, public, out_dir, registry: Path | None = None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    text_cfg = cfg.get("text", {})
    gold_s = sorted((s for s in gold.samples if s.has_gold), key=lambda s: s.sample_id)
    cfg_floor = (cfg.get("thresholds") or {}).get("floor")
    floor = float(cfg_floor) if cfg_floor is not None else 1.0 / max(1, len(gold_s))
    pub = _select_public(public, (cfg.get("data") or {}).get("public_per_exam")) if public else []
    heads = NoulModel.from_checkpoint(heads_path)
    t0 = time.time()
    P_gold = label_probs(gold_s, gold.exams, encoder, heads, text_cfg)
    P_pub = label_probs(pub, public.exams if public else {}, encoder, heads, text_cfg)
    seconds = time.time() - t0
    Y = np.array([to_vector(s.labels) for s in gold_s], np.float32).reshape(len(gold_s), len(LABELS)) >= 0.5
    thr = prevalence_thresholds(P_gold, Y, floor)
    err_gold = np.array([has_compile_error(s.compile_log) for s in gold_s], bool)
    err_pub = np.array([has_compile_error(s.compile_log) for s in pub], bool)
    max_labels = (cfg.get("thresholds") or {}).get("max_labels")
    pred_gold = decide(P_gold, thr, err_gold, max_labels=max_labels)
    gold_map = {s.sample_id: s.labels for s in gold_s}
    systems = {"clm_zeroshot_prompts": f1_scores(
        gold_map, {s.sample_id: from_vector(r) for s, r in zip(gold_s, pred_gold)})}
    if pub:
        labels = {s.sample_id: from_vector(r) for s, r in zip(pub, decide(P_pub, thr, err_pub, max_labels=max_labels))}
        write_submission(out_dir / "predictions.json", labels, [s.sample_id for s in pub])
        _write_json(out_dir / "predictions_full.json", [
            {"sample_id": s.sample_id, "exam_id": s.exam_id, "labels": labels[s.sample_id],
             "has_compile_error": bool(err_pub[k]), "probs": dict(zip(LABELS, np.round(P_pub[k], 4).tolist()))}
            for k, s in enumerate(pub)])
    metrics = {"name": cfg["name"], "mode": "clm_zeroshot",
               "evaluation": "in-sample over gold (prompts and thresholds derived from gold: optimistic)",
               "n_gold": len(gold_s), "n_public": len(pub), "floor": floor, "systems": systems,
               "thresholds": dict(zip(LABELS, thr.tolist())),
               "prevalence": dict(zip(LABELS, Y.mean(0).tolist())),
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
                         "task": "task2", "model": resources["model"], "config_path": cfg.get("_config_path", ""),
                         "train_loss": "",
                         "metrics": json.dumps({"macro_f1_in_sample": best.get("macro_f1"),
                                                              "micro_f1_in_sample": best.get("micro_f1"),
                                                              "n_gold": len(gold_s)}),
                         "git_commit": _git_commit(), "notes": cfg.get("description", "")}, registry)
    return metrics
