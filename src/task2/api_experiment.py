"""Run Task 2 Hướng 1 on a list of samples: cached/resumable inference, predictions, metrics."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from src.task1.experiment import REGISTRY, _git_commit, _write_json, append_registry
from src.task2.evaluator import f1_scores, write_submission
from src.task2.pipeline import Task2ApiPipeline
from src.utils.seed import set_seed


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def run_api(cfg: dict, dataset, samples: list, backend, out_dir, demo_pool=(), registry: Path | None = REGISTRY,
            use_cache: bool = True) -> dict:
    seed = int(cfg.get("seed", 42))
    set_seed(seed)
    cfg = {**cfg, "generation": {**cfg.get("generation", {}), "seed": seed}}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pipe = Task2ApiPipeline(dataset, backend, cfg, demo_pool)
    info = backend.info()
    model_key = {k: info.get(k) for k in ("backend", "model")}
    keys = {s.sample_id: _hash({"model": model_key, "messages": pipe.build_request(s)["messages"],
                                "generation": cfg["generation"], "retry": cfg.get("retry_on_parse_fail", 1)})
            for s in samples}

    cache_path = out_dir / "raw_outputs.jsonl"
    done: dict[str, dict] = {}
    if use_cache and cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            try:  # a line truncated by a killed run is skipped, not fatal
                row = json.loads(line)
                if keys.get(row["sample_id"]) == row["key"] and pipe.postprocess(row["record"])["parse_ok"]:
                    done[row["sample_id"]] = row["record"]
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    todo = [s for s in samples if s.sample_id not in done]
    print(f"[{cfg['name']}] {len(done)} bài từ cache, gọi model cho {len(todo)} bài", flush=True)

    usage_before = dict(info.get("usage") or {})
    ledger_before = len(getattr(backend, "ledger", []))
    t0 = time.time()
    chunk = max(1, int(getattr(backend, "checkpoint_every", None) or cfg.get("checkpoint_every", 4)))  # vLLM: big batches
    if todo and cache_path.exists() and cache_path.stat().st_size and not cache_path.read_bytes().endswith(b"\n"):
        with cache_path.open("a", encoding="utf-8") as f:  # end a truncated last line so new rows stay parseable
            f.write("\n")
    try:
        for k in range(0, len(todo), chunk):
            for r in pipe.infer(todo[k:k + chunk]):
                done[r["sample_id"]] = r
                with cache_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"sample_id": r["sample_id"], "key": keys[r["sample_id"]], "record": r},
                                       ensure_ascii=False) + "\n")
    finally:
        if hasattr(backend, "ledger"):
            with (out_dir / "usage.jsonl").open("a", encoding="utf-8") as f:
                for entry in backend.ledger[ledger_before:]:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    infer_seconds = time.time() - t0

    preds = [pipe.postprocess(done[s.sample_id]) if s.sample_id in done else pipe.empty_prediction(s)
             for s in samples]
    ids = [s.sample_id for s in samples]
    labels = {p["sample_id"]: p["labels"] for p in preds}
    write_submission(out_dir / "predictions.json", labels, ids)
    _write_json(out_dir / "predictions_full.json", preds)
    gold = {s.sample_id: s.labels for s in samples if s.has_gold}
    metrics = {"name": cfg["name"], "n": len(samples), "parse_failures": sum(not p["parse_ok"] for p in preds),
               "evaluation": f"gold val ({len(gold)})" if gold else "public (no labels)",
               "systems": {"api": f1_scores(gold, labels)} if gold else {}}
    usage_after = backend.info().get("usage") or {}
    delta = {k: usage_after[k] - usage_before.get(k, 0) for k in usage_after
             if isinstance(usage_after[k], (int, float))}
    # Cost evidence accumulates across resumed runs: nothing inferred -> keep the previous totals as they are;
    # otherwise add this invocation's usage to them (a missing previous value counts as 0).
    res_path = out_dir / "resources.json"
    prev = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else {}
    if todo:
        totals = {"tokens_in": (prev.get("tokens_in") or 0) + (delta.get("prompt_tokens") or 0),
                  "tokens_out": (prev.get("tokens_out") or 0) + (delta.get("output_tokens") or 0),
                  "cost_usd": (prev.get("cost_usd") or 0) + (delta.get("cost_usd") or 0)}
        seconds = infer_seconds / len(todo)
    else:
        totals = {k: prev.get(k) for k in ("tokens_in", "tokens_out", "cost_usd")}
        seconds = prev.get("seconds_per_sample")
    info_after = backend.info()  # local backends report their hardware and peak memory; API backends do not
    resources = {"backend": info.get("backend"), "model": info.get("model"),
                 "hardware": info_after.get("hardware", "API"),
                 "n_samples": len(samples), "seconds_per_sample": seconds,
                 "train_seconds": None, "peak_memory_gb": info_after.get("peak_memory_gb"), **totals}
    _write_json(out_dir / "metrics.json", metrics)
    _write_json(out_dir / "resources.json", resources)
    _write_json(out_dir / "config.json", {"config": cfg, "model_info": backend.info(),
                                          "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "ids": ids})
    if registry is not None:
        api = metrics["systems"].get("api") or {}
        append_registry({"experiment_id": cfg["name"], "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "task": "task2", "model": info.get("model", ""), "config_path": cfg.get("_config_path", ""),
                         "metrics": json.dumps({"macro_f1": api.get("macro_f1"), "micro_f1": api.get("micro_f1"),
                                                "n": len(samples), "parse_failures": metrics["parse_failures"]}),
                         "git_commit": _git_commit(), "notes": cfg.get("description", "")}, registry)
    return metrics
