"""Task 2 Hướng 2 end to end (no test-derived labels — instructor ruling 2026-10-11):
embed gold + bug-injection mutants of gold + public (cached) -> k-fold CV on gold giving out-of-fold
probabilities for zero-shot CLM / fine-tuned CLM / linear probe, each with and without augmentation
-> per-label thresholds from OOF -> final models on all gold -> public predictions."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from src.task1.experiment import REGISTRY, _git_commit, _write_json, append_registry
from src.task2.augment import source_id
from src.task2.benchmark import hardware_info
from src.task2.clm.heads import LinearProbe, NoulModel, TrainConfig, predict_noul, train_noul
from src.task2.clm.text import build_state_texts, candidate_texts
from src.task2.evaluator import f1_scores, write_submission
from src.task2.labels import LABELS, from_vector, to_vector
from src.task2.thresholds import apply_thresholds, tune_thresholds
from src.utils.seed import set_seed


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


SYSTEMS = ("clm_zero_shot", "clm_noul", "clm_noul_aug", "probe", "probe_aug")


def kfold_ids(ids, k: int, seed: int) -> list[list[str]]:
    ids = sorted(ids)
    k = max(1, min(int(k), len(ids)))
    perm = np.random.default_rng(seed).permutation(len(ids))
    return [sorted(ids[i] for i in perm[f::k]) for f in range(k)]


def run_clm(cfg: dict, encoder, heads_path, gold, public, out_dir, mutants=(),
            registry: Path | None = REGISTRY) -> dict:
    seed = int(cfg.get("seed", 42))
    set_seed(seed)
    final = cfg.get("final_system", "clm_noul_aug")
    if final not in SYSTEMS:
        raise ValueError(f"final_system={final!r} not in {SYSTEMS}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    text_cfg = cfg.get("text", {})
    gold_s = sorted((s for s in gold.samples if s.has_gold), key=lambda s: s.sample_id)
    gold_ids = {s.sample_id for s in gold_s}
    mutants = [m for m in mutants if source_id(m.sample_id) in gold_ids]  # never anything test-derived
    pub = _select_public(public, (cfg.get("data") or {}).get("public_per_exam")) if public else []

    # 0. fail fast on a wrong / missing checkpoint, before hours of embedding
    zero = NoulModel.from_checkpoint(heads_path)

    # 1. embeddings (frozen encoder, cached on disk)
    t0 = time.time()
    C = embed_candidates(encoder)
    dim = C.shape[-1]
    e_gold = embed_samples(gold_s, gold.exams, encoder, text_cfg, dim)
    e_mut = embed_samples(mutants, gold.exams, encoder, text_cfg, dim)
    e_pub = embed_samples(pub, public.exams if public else {}, encoder, text_cfg, dim)
    embed_seconds = time.time() - t0
    Y_gold, Y_mut = _gold_matrix(gold_s), _gold_matrix(mutants)
    src_mut = np.array([source_id(m.sample_id) for m in mutants])
    tcfg = TrainConfig(**{**(cfg.get("train") or {}), "seed": seed})
    probe_c = float((cfg.get("probe") or {}).get("C", 1.0))

    def fit(rows: np.ndarray, with_aug: bool):
        """Train CLM heads + probe on gold rows (+ mutants whose source gold sample is among those rows)."""
        S, X, Y = e_gold["S"][rows], e_gold["X"][rows], Y_gold[rows]
        if with_aug and len(mutants):
            keep = np.isin(src_mut, [gold_s[i].sample_id for i in rows])
            S = np.concatenate([S, e_mut["S"][keep]])
            X = np.concatenate([X, e_mut["X"][keep]])
            Y = np.concatenate([Y, Y_mut[keep]])
        model = NoulModel.from_checkpoint(heads_path)
        hist = train_noul(model, S, C, Y, tcfg)
        return model, LinearProbe(C=probe_c, seed=seed).fit(X, Y), hist, int(len(S))

    def probe_proba(probe, X) -> np.ndarray:
        return probe.predict_proba(X) if len(X) else np.zeros((0, len(LABELS)), np.float32)

    # 2. k-fold CV -> out-of-fold probabilities for every gold sample
    n = len(gold_s)
    pos = {s.sample_id: i for i, s in enumerate(gold_s)}
    folds = kfold_ids(list(pos), int((cfg.get("cv") or {}).get("folds", 4)), seed)
    oof = {system: np.zeros((n, len(LABELS)), np.float32) for system in SYSTEMS}
    oof["clm_zero_shot"] = predict_noul(zero, e_gold["S"], C)
    fold_hist = []
    t1 = time.time()
    for f, held in enumerate(folds):
        te = np.array([pos[i] for i in held])
        held_rows = set(te.tolist())
        tr = np.array([i for i in range(n) if i not in held_rows])
        for with_aug, (s_clm, s_probe) in ((False, ("clm_noul", "probe")), (True, ("clm_noul_aug", "probe_aug"))):
            model, probe, hist, n_fit = fit(tr, with_aug)
            oof[s_clm][te] = predict_noul(model, e_gold["S"][te], C)
            oof[s_probe][te] = probe_proba(probe, e_gold["X"][te])
            fold_hist.append({"fold": f, "augment": with_aug, "n_train": n_fit, "loss": hist["loss"]})
    cv_seconds = time.time() - t1

    # 3. thresholds from OOF; metrics = OOF over all gold (@tuned is optimistic: same rows)
    th = cfg.get("thresholds") or {}
    gold_map = {s.sample_id: s.labels for s in gold_s}

    def score(P, thr) -> dict:
        pred = apply_thresholds(P, thr)
        return f1_scores(gold_map, {s.sample_id: from_vector(r) for s, r in zip(gold_s, pred)})

    thresholds, systems = {}, {}
    for system in SYSTEMS:
        thr = tune_thresholds(oof[system], Y_gold >= 0.5, default=float(th.get("default", 0.5)))
        thresholds[system] = thr.tolist()
        systems[f"{system}@0.5"] = score(oof[system], np.full(len(LABELS), 0.5))
        systems[f"{system}@tuned"] = score(oof[system], thr)

    # 4. final models on all gold (+ all mutants), public predictions
    t2 = time.time()
    rows = np.arange(n)
    m_plain, p_plain, h_plain, n_plain = fit(rows, False)
    m_aug, p_aug, h_aug, n_aug = fit(rows, True)
    train_seconds = time.time() - t2
    if pub:
        P_pub = {"clm_zero_shot": predict_noul(zero, e_pub["S"], C), "clm_noul": predict_noul(m_plain, e_pub["S"], C),
                 "clm_noul_aug": predict_noul(m_aug, e_pub["S"], C), "probe": probe_proba(p_plain, e_pub["X"]),
                 "probe_aug": probe_proba(p_aug, e_pub["X"])}
        pred = apply_thresholds(P_pub[final], np.array(thresholds[final]), float(th.get("min_rate", 0.0)))
        labels = {s.sample_id: from_vector(r) for s, r in zip(pub, pred)}
        write_submission(out_dir / "predictions.json", labels, [s.sample_id for s in pub])
        _write_json(out_dir / "predictions_full.json", [
            {"sample_id": s.sample_id, "exam_id": s.exam_id, "labels": labels[s.sample_id],
             "probs": {system: dict(zip(LABELS, np.round(P_pub[system][k], 4).tolist())) for system in SYSTEMS}}
            for k, s in enumerate(pub)])
    torch.save(m_plain.state_dict(), out_dir / "clm_noul_heads.pt")
    torch.save(m_aug.state_dict(), out_dir / "clm_noul_aug_heads.pt")

    n_samples = n + len(mutants) + len(pub)
    peak = encoder.peak_memory_gb() if hasattr(encoder, "peak_memory_gb") else None
    resources = {"backend": "clm", "model": getattr(encoder, "encoder_id", ""), "hardware": hardware_info(),
                 "n_samples": n_samples,
                 "seconds_per_sample": (getattr(encoder, "seconds", embed_seconds) / n_samples) if n_samples else None,
                 "embed_seconds_total": embed_seconds, "n_encoded": getattr(encoder, "n_computed", None),
                 "n_cache_hits": getattr(encoder, "n_hits", None), "cv_seconds": cv_seconds,
                 "train_seconds": train_seconds, "peak_memory_gb": peak, "tokens_in": None, "tokens_out": None,
                 "cost_usd": 0.0}
    metrics = {"name": cfg["name"], "n_gold": n, "n_mutants": len(mutants), "cv_folds": len(folds),
               "evaluation": "out-of-fold over gold", "systems": systems,
               "history": {"folds": fold_hist, "final": {"clm_noul": {"n_train": n_plain, "loss": h_plain["loss"]},
                                                         "clm_noul_aug": {"n_train": n_aug, "loss": h_aug["loss"]}}},
               "final_system": final}
    _write_json(out_dir / "metrics.json", metrics)
    _write_json(out_dir / "thresholds.json", {s: dict(zip(LABELS, t)) for s, t in thresholds.items()})
    _write_json(out_dir / "resources.json", resources)
    _write_json(out_dir / "config.json", {"config": cfg, "heads": str(heads_path),
                                          "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                          "folds": folds, "mutant_ids": [m.sample_id for m in mutants],
                                          "public_ids": [s.sample_id for s in pub]})
    if registry is not None:
        best = systems.get(f"{final}@tuned") or {}
        append_registry({"experiment_id": cfg["name"], "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "task": "task2", "model": resources["model"], "config_path": cfg.get("_config_path", ""),
                         "train_loss": h_aug["loss"][-1] if h_aug["loss"] else "",
                         "metrics": json.dumps({"macro_f1_oof_tuned": best.get("macro_f1"),
                                                "micro_f1_oof_tuned": best.get("micro_f1"),
                                                "n_gold": n, "n_mutants": len(mutants), "cv_folds": len(folds)}),
                         "git_commit": _git_commit(), "notes": cfg.get("description", "")}, registry)
    return metrics
