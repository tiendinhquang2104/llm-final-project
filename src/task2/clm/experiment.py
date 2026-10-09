"""Task 2 Hướng 2 end to end: embed (cached) -> zero-shot CLM / fine-tuned CLM (A) / linear probe (B)
-> per-label thresholds -> gold-val metrics -> public predictions."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from src.task1.experiment import REGISTRY, _git_commit, _write_json, append_registry
from src.task2.benchmark import hardware_info
from src.task2.clm.heads import LinearProbe, NoulModel, TrainConfig, predict_noul, train_noul
from src.task2.clm.text import build_state_texts, candidate_texts
from src.task2.evaluator import f1_scores, write_submission
from src.task2.labels import LABELS, from_vector, to_vector
from src.task2.thresholds import apply_thresholds, tune_thresholds
from src.utils.seed import set_seed

SYSTEMS = ("clm_zero_shot", "clm_noul", "probe")


def embed_candidates(encoder) -> np.ndarray:
    texts = [t for lab in LABELS for t in candidate_texts(lab)]
    return encoder.embed(texts).reshape(len(LABELS), 2, -1)


def embed_samples(samples, exams, encoder, text_cfg: dict, dim: int) -> dict:
    if not samples:
        return {"X": np.zeros((0, dim), np.float32), "S": np.zeros((0, len(LABELS), dim), np.float32)}
    contexts, questions = [], []
    for s in samples:
        st = build_state_texts(exams[s.exam_id], s, encoder.tokenizer, **text_cfg)
        contexts.append(st["context"])
        questions.extend(st["questions"][lab] for lab in LABELS)
    return {"X": encoder.embed(contexts), "S": encoder.embed(questions).reshape(len(samples), len(LABELS), -1)}


def _select_public(public, per_exam):
    samples = sorted(public.samples, key=lambda s: s.sample_id)
    if not per_exam:
        return samples
    seen: dict[str, int] = {}
    out = []
    for s in samples:
        if seen.get(s.exam_id, 0) < int(per_exam):
            out.append(s)
            seen[s.exam_id] = seen.get(s.exam_id, 0) + 1
    return out


def _gold_matrix(samples) -> np.ndarray:
    return np.array([to_vector(s.labels) for s in samples], np.float32).reshape(len(samples), len(LABELS))


def run_clm(cfg: dict, encoder, heads_path, gold, public, split: dict, out_dir, silver: dict | None = None,
            registry: Path | None = REGISTRY) -> dict:
    seed = int(cfg.get("seed", 42))
    set_seed(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    text_cfg = cfg.get("text", {})
    by_id = gold.by_id()
    train_g = [by_id[i] for i in split["train"] if i in by_id]
    val_g = [by_id[i] for i in split["val"] if i in by_id]
    pub = _select_public(public, (cfg.get("data") or {}).get("public_per_exam")) if public else []

    # 1. embeddings (frozen encoder, cached on disk)
    t0 = time.time()
    C = embed_candidates(encoder)
    dim = C.shape[-1]
    e_train = embed_samples(train_g, gold.exams, encoder, text_cfg, dim)
    e_val = embed_samples(val_g, gold.exams, encoder, text_cfg, dim)
    e_pub = embed_samples(pub, public.exams if public else {}, encoder, text_cfg, dim)
    embed_seconds = time.time() - t0

    # 2. training / tuning sets: gold train (+ silver fit) / gold val (+ silver holdout)
    S_tr, X_tr, Y_tr = e_train["S"], e_train["X"], _gold_matrix(train_g)
    S_tu, X_tu, Y_tu = e_val["S"], e_val["X"], _gold_matrix(val_g)
    if silver and pub:
        have = [k for k, s in enumerate(pub) if s.sample_id in silver]
        perm = np.random.default_rng(seed).permutation(have).astype(int)
        n_hold = int(round(len(perm) * float((cfg.get("silver") or {}).get("holdout", 0.1))))
        hold, fit = perm[:n_hold], perm[n_hold:]
        Ys = np.array([[float(silver.get(s.sample_id, {}).get(lab, 0.0)) for lab in LABELS] for s in pub],
                      np.float32)
        S_tr, X_tr, Y_tr = (np.concatenate([S_tr, e_pub["S"][fit]]), np.concatenate([X_tr, e_pub["X"][fit]]),
                            np.concatenate([Y_tr, Ys[fit]]))
        S_tu, X_tu, Y_tu = (np.concatenate([S_tu, e_pub["S"][hold]]), np.concatenate([X_tu, e_pub["X"][hold]]),
                            np.concatenate([Y_tu, Ys[hold]]))
    n_val = len(val_g)
    gold_val = {s.sample_id: s.labels for s in val_g}

    def score(P, thr) -> dict:
        pred = apply_thresholds(P[:n_val], thr)
        return f1_scores(gold_val, {s.sample_id: from_vector(r) for s, r in zip(val_g, pred)})

    # 3. learners
    zero = NoulModel.from_checkpoint(heads_path)
    model = NoulModel.from_checkpoint(heads_path)
    tcfg = TrainConfig(**{**(cfg.get("train") or {}), "seed": seed})
    eval_fn = (lambda m: score(predict_noul(m, e_val["S"], C), np.full(len(LABELS), 0.5))["macro_f1"]) \
        if n_val else None
    t1 = time.time()
    history = train_noul(model, S_tr, C, Y_tr, tcfg, eval_fn)
    probe = LinearProbe(C=float((cfg.get("probe") or {}).get("C", 1.0)), seed=seed).fit(X_tr, Y_tr)
    train_seconds = time.time() - t1

    def probs(system: str, e: dict) -> np.ndarray:
        if system == "probe":
            return probe.predict_proba(e["X"]) if len(e["X"]) else np.zeros((0, len(LABELS)), np.float32)
        return predict_noul(zero if system == "clm_zero_shot" else model, e["S"], C)

    # 4. thresholds + metrics on the gold validation samples
    th = cfg.get("thresholds") or {}
    tune = {"X": X_tu, "S": S_tu}
    thresholds, systems = {}, {}
    for system in SYSTEMS:
        P = probs(system, tune)
        thr = tune_thresholds(P, Y_tu >= 0.5, default=float(th.get("default", 0.5)))
        thresholds[system] = thr.tolist()
        if n_val:
            systems[f"{system}@0.5"] = score(P, np.full(len(LABELS), 0.5))
            systems[f"{system}@tuned"] = score(P, thr)

    # 5. public predictions with the final system
    final = cfg.get("final_system", "clm_noul")
    if pub:
        P_pub = {system: probs(system, e_pub) for system in SYSTEMS}
        pred = apply_thresholds(P_pub[final], np.array(thresholds[final]), float(th.get("min_rate", 0.0)))
        labels = {s.sample_id: from_vector(r) for s, r in zip(pub, pred)}
        write_submission(out_dir / "predictions.json", labels, [s.sample_id for s in pub])
        _write_json(out_dir / "predictions_full.json", [
            {"sample_id": s.sample_id, "exam_id": s.exam_id, "labels": labels[s.sample_id],
             "probs": {system: dict(zip(LABELS, np.round(P_pub[system][k], 4).tolist())) for system in SYSTEMS}}
            for k, s in enumerate(pub)])

    torch.save(model.state_dict(), out_dir / "clm_noul_heads.pt")
    n_samples = len(train_g) + len(val_g) + len(pub)
    peak = encoder.peak_memory_gb() if hasattr(encoder, "peak_memory_gb") else None
    resources = {"backend": "clm", "model": getattr(encoder, "encoder_id", ""), "hardware": hardware_info(),
                 "n_samples": n_samples,
                 "seconds_per_sample": (getattr(encoder, "seconds", embed_seconds) / n_samples) if n_samples else None,
                 "embed_seconds_total": embed_seconds, "n_encoded": getattr(encoder, "n_computed", None),
                 "n_cache_hits": getattr(encoder, "n_hits", None), "train_seconds": train_seconds,
                 "peak_memory_gb": peak, "tokens_in": None, "tokens_out": None, "cost_usd": 0.0}
    metrics = {"name": cfg["name"], "n_train": int(len(S_tr)), "n_val_gold": n_val, "systems": systems,
               "history": history, "final_system": final}
    _write_json(out_dir / "metrics.json", metrics)
    _write_json(out_dir / "thresholds.json", {s: dict(zip(LABELS, t)) for s, t in thresholds.items()})
    _write_json(out_dir / "resources.json", resources)
    _write_json(out_dir / "config.json", {"config": cfg, "heads": str(heads_path),
                                          "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                          "train_ids": [s.sample_id for s in train_g],
                                          "val_ids": [s.sample_id for s in val_g],
                                          "public_ids": [s.sample_id for s in pub]})
    if registry is not None:
        best = systems.get(f"{final}@tuned") or {}
        append_registry({"experiment_id": cfg["name"], "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "task": "task2", "model": resources["model"], "config_path": cfg.get("_config_path", ""),
                         "train_loss": history["loss"][-1] if history["loss"] else "",
                         "metrics": json.dumps({"macro_f1": best.get("macro_f1"), "micro_f1": best.get("micro_f1"),
                                                "n_train": metrics["n_train"], "n_val_gold": n_val}),
                         "git_commit": _git_commit(), "notes": cfg.get("description", "")}, registry)
    return metrics
