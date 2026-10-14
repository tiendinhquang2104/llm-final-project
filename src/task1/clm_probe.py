"""API-free Task 1: ridge probe on frozen CLM context embeddings (+ has_compile_error), one output per rubric
dimension, rounded, clamped, then the Task 1 compile-gate rule. Trained and tuned only on the labelled gold
samples (k-fold out-of-fold QWK); the public release is only predicted."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from src.data.loader import DIM_MAX, DIMENSIONS
from src.task1.evaluator import evaluate, validate_predictions
from src.task1.experiment import REGISTRY, _git_commit, _write_json, append_registry
from src.task1.prerequisite_rules import RuleConfig, apply_rules, policy_from_exam
from src.task2.benchmark import hardware_info
from src.task2.clm.experiment import kfold_ids
from src.task2.clm.text import build_state_texts
from src.task2.compile import has_compile_error
from src.utils.seed import set_seed


def load_rubrics(root, task_file: str = "task1_grading.json") -> dict[str, dict]:
    from src.data.loader import resolve_dataset_root

    payload = json.loads((resolve_dataset_root(root) / task_file).read_text(encoding="utf-8"))
    out = {}
    for s in payload["samples"]:
        o = s.get("output")
        if o and "rubric" in o:
            out[s["sample_id"]] = {"rubric": {d: int(o["rubric"][d]) for d in DIMENSIONS},
                                   "total_score": int(o["total_score"])}
    return out


def embed_contexts(samples, exams, encoder, text_cfg: dict) -> np.ndarray:
    """Context embedding (the exact text Task 2 embeds, so the cache is shared) + has_compile_error column."""
    if not samples:
        return np.zeros((0, 1), np.float32)
    texts = [build_state_texts(exams[s.exam_id], s, encoder.tokenizer, **text_cfg)["context"] for s in samples]
    err = np.array([has_compile_error(s.compile_log) for s in samples], np.float32)[:, None]
    return np.hstack([np.asarray(encoder.embed(texts), np.float32), err])


class RubricProbe:
    def __init__(self, alpha: float = 1.0):
        self.alpha = float(alpha)

    def fit(self, X, R) -> "RubricProbe":
        R = np.asarray(R, np.float64)
        self.const_ = R.min(axis=0) == R.max(axis=0)
        self.value_ = R[0].copy() if len(R) else np.zeros(R.shape[1])
        self.model_ = None
        if (~self.const_).any():
            self.model_ = Ridge(alpha=self.alpha).fit(np.asarray(X, np.float64), R[:, ~self.const_])
        return self

    def predict(self, X) -> np.ndarray:
        out = np.tile(self.value_, (len(X), 1))
        if self.model_ is not None:
            out[:, ~self.const_] = np.asarray(self.model_.predict(np.asarray(X, np.float64))).reshape(len(X), -1)
        return out


def to_rubric(row) -> dict[str, int]:
    return {d: int(min(max(np.floor(float(v) + 0.5), 0), DIM_MAX[d])) for d, v in zip(DIMENSIONS, row)}


def finalize(rubric: dict, exam: dict, compile_gate: bool = True) -> tuple[dict, int]:
    r, total, _ = apply_rules(rubric, None, policy_from_exam(exam),
                              RuleConfig(prerequisite=False, compile_gate=compile_gate, clamp=True))
    return r, total


def _fit_predict(alpha: float, X_tr, R_tr, X_te) -> np.ndarray:
    scaler = StandardScaler().fit(X_tr)  # fold train only
    return RubricProbe(alpha).fit(scaler.transform(X_tr), R_tr).predict(scaler.transform(X_te))


def _decide(P, samples, exams, gate: bool) -> dict[str, dict]:
    out = {}
    for s, row in zip(samples, P):
        r, t = finalize(to_rubric(row), exams[s.exam_id], gate)
        out[s.sample_id] = {"rubric": r, "total_score": t}
    return out


def run_task1_clm(cfg: dict, encoder, gold, rubrics: dict, public, public_ids, out_dir,
                  registry: Path | None = REGISTRY) -> dict:
    seed = int(cfg.get("seed", 42))
    set_seed(seed)
    t1 = cfg.get("task1") or {}
    alphas = sorted(float(a) for a in t1.get("alphas", [0.1, 1.0, 10.0, 100.0]))
    gate = bool(t1.get("compile_gate", True))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    text_cfg = cfg.get("text", {})
    gold_s = sorted((s for s in gold.samples if s.sample_id in rubrics), key=lambda s: s.sample_id)
    pub_by_id = {s.sample_id: s for s in public.samples}
    missing = [i for i in public_ids if i not in pub_by_id]
    if missing:
        raise KeyError(f"public ids not loaded: {missing[:5]}")
    pub = [pub_by_id[i] for i in sorted(set(public_ids))]

    t0 = time.time()
    X = embed_contexts(gold_s, gold.exams, encoder, text_cfg)
    X_pub = embed_contexts(pub, public.exams, encoder, text_cfg)
    embed_seconds = time.time() - t0
    R = np.array([[rubrics[s.sample_id]["rubric"][d] for d in DIMENSIONS] for s in gold_s], np.float64)
    gold_map = {s.sample_id: rubrics[s.sample_id] for s in gold_s}

    n = len(gold_s)
    pos = {s.sample_id: i for i, s in enumerate(gold_s)}
    folds = kfold_ids(list(pos), int((cfg.get("cv") or {}).get("folds", 4)), seed)
    oof = {a: np.zeros_like(R) for a in alphas}
    oof_mean = np.zeros_like(R)
    t1s = time.time()
    for held in folds:
        te = np.array([pos[i] for i in held])
        tr = np.array([i for i in range(n) if i not in set(te.tolist())])
        for a in alphas:
            oof[a][te] = _fit_predict(a, X[tr], R[tr], X[te])
        oof_mean[te] = R[tr].mean(axis=0)
    cv_seconds = time.time() - t1s

    scores = {a: evaluate(gold_map, _decide(oof[a], gold_s, gold.exams, gate)) for a in alphas}

    def key(a):
        q = scores[a]["qwk"]
        return (-np.inf if q != q else q, a)  # best QWK, ties -> larger alpha

    best = max(alphas, key=key)
    systems = {"ridge": scores[best],
               "mean_baseline": evaluate(gold_map, _decide(oof_mean, gold_s, gold.exams, gate))}

    t2 = time.time()
    P_pub = _fit_predict(best, X, R, X_pub) if len(pub) else np.zeros((0, len(DIMENSIONS)))
    train_seconds = time.time() - t2
    final = _decide(P_pub, pub, public.exams, gate)
    preds = [{"sample_id": s.sample_id, "output": {"rubric": final[s.sample_id]["rubric"],
                                                   "total_score": final[s.sample_id]["total_score"]}} for s in pub]
    errs = validate_predictions(preds, set(public_ids))
    extra = {p["sample_id"] for p in preds} - set(public_ids)
    if errs or extra:
        raise ValueError(f"invalid Task 1 predictions: {errs[:5]} extra={sorted(extra)[:5]}")
    _write_json(out_dir / "predictions.json", preds)
    _write_json(out_dir / "predictions_full.json", [
        {"sample_id": s.sample_id, "exam_id": s.exam_id, "has_compile_error": bool(X_pub[k, -1]),
         "raw": dict(zip(DIMENSIONS, np.round(P_pub[k], 4).tolist())),
         "rubric": final[s.sample_id]["rubric"], "total_score": final[s.sample_id]["total_score"]}
        for k, s in enumerate(pub)])

    n_samples = n + len(pub)
    resources = {"backend": "clm", "model": getattr(encoder, "encoder_id", ""), "hardware": hardware_info(),
                 "n_samples": n_samples,
                 "seconds_per_sample": (getattr(encoder, "seconds", embed_seconds) / n_samples) if n_samples else None,
                 "embed_seconds_total": embed_seconds, "n_encoded": getattr(encoder, "n_computed", None),
                 "n_cache_hits": getattr(encoder, "n_hits", None), "cv_seconds": cv_seconds,
                 "train_seconds": train_seconds, "tokens_in": None, "tokens_out": None, "cost_usd": 0.0}
    metrics = {"name": cfg["name"], "n_gold": n, "cv_folds": len(folds), "evaluation": "out-of-fold over gold",
               "alpha_selection": {str(a): scores[a]["qwk"] for a in alphas}, "chosen_alpha": best,
               "systems": systems,
               "compile": {"enabled": cfg.get("_compiler_id") is not None, "compiler_id": cfg.get("_compiler_id"),
                           "source": cfg.get("_compile_source")}}
    _write_json(out_dir / "metrics.json", metrics)
    _write_json(out_dir / "resources.json", resources)
    _write_json(out_dir / "config.json", {"config": cfg, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                          "folds": folds, "public_ids": [s.sample_id for s in pub]})
    if registry is not None:
        r = systems["ridge"]
        append_registry({"experiment_id": cfg["name"], "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "task": "task1", "model": resources["model"], "config_path": cfg.get("_config_path", ""),
                         "metrics": json.dumps({"qwk_oof": r["qwk"], "mae_oof": r["mae"], "chosen_alpha": best,
                                                "baseline_qwk_oof": systems["mean_baseline"]["qwk"],
                                                "n_gold": n, "cv_folds": len(folds)}),
                         "git_commit": _git_commit(), "notes": cfg.get("description", "")}, registry)
    return metrics
