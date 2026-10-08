"""Task 1 experiment runner: every run saves prompt + config + raw outputs + predictions + metrics.

outputs/task1/<name>/
  config.json            resolved config + model/library versions + timestamp
  prompt.md              system prompt + rendered user prompt of the first eval sample
  raw_outputs.jsonl      raw model completions (cache: re-used if config hash unchanged)
  predictions_full.json  per-sample predictions incl. LLM-only rubric, problem statuses, rule trace
  predictions.json       leaderboard submission format
  metrics.json           main metrics + rule ablation (same raw outputs, different rule configs)
  error_analysis.md/json cases with |pred - gold| >= threshold
outputs/task1/_cache/    raw outputs shared by runs with identical requests
experiments/registry.csv one row per run (shared project registry)
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

from src.evaluation.error_analysis import error_analysis, to_markdown
from src.data.loader import Dataset, load_task1
from src.llm.api_client import Backend
from src.utils.config import PROJECT_ROOT
from src.utils.seed import set_seed
from src.task1.evaluator import evaluate, format_metrics
from src.task1.pipeline import Task1Pipeline, to_submission
from src.task1.prerequisite_rules import RuleConfig

REGISTRY = PROJECT_ROOT / "experiments" / "registry.csv"

RULE_VARIANTS = {
    "no_rules": {"prerequisite": False, "compile_gate": False},
    "compile_gate_only": {"prerequisite": False, "compile_gate": True},
    "prereq_only": {"prerequisite": True, "compile_gate": False},
    "full": {"prerequisite": True, "compile_gate": True},
    "full_strict": {"prerequisite": True, "compile_gate": True, "prereq_strict": True},
    "full_derive_logic": {"prerequisite": True, "compile_gate": True, "derive_logic": True},
}


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _gold(samples) -> dict:
    return {s.sample_id: {"rubric": s.gold_rubric, "total_score": s.gold_total} for s in samples if s.has_gold}


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _complete(record: dict) -> bool:
    """False if any request of this record failed (empty text) — such records are re-requested next time."""
    return bool(record["outputs"]) and all(t.strip() for t in record["outputs"])


def _read_cache(path: Path, infer_key: str) -> tuple[list[dict], dict] | None:
    """(records, inference metadata) if `path` holds complete outputs for `infer_key`, else None."""
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    head = json.loads(lines[0]) if lines else {}
    if head.get("infer_key") != infer_key:
        return None
    records = [json.loads(ln) for ln in lines[1:]]
    return (records, head.get("inference") or {}) if all(_complete(r) for r in records) else None


def _write_cache(path: Path, infer_key: str, records: list[dict], inference: dict | None = None) -> None:
    """The header keeps how the outputs were produced (served model, tokens, time) so cache hits keep provenance."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"infer_key": infer_key, "inference": inference or {}}, ensure_ascii=False) + "\n")
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _git_commit() -> str:
    head = PROJECT_ROOT / ".git" / "HEAD"
    try:
        ref = head.read_text().strip()
        if ref.startswith("ref: "):
            return (PROJECT_ROOT / ".git" / ref[5:]).read_text().strip()[:10]
        return ref[:10]
    except OSError:
        return ""


def append_registry(row: dict, path: Path = REGISTRY) -> None:
    """Upsert one run into the shared experiments registry (key: experiment_id)."""
    fields = ["experiment_id", "timestamp", "task", "model", "config_path", "train_loss", "val_loss", "metrics",
              "git_commit", "notes"]
    rows = []
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r.get("experiment_id") != row["experiment_id"]]
    rows.append({k: row.get(k, "") for k in fields})
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def run_experiment(cfg: dict, dataset: Dataset, split: dict, backend: Backend,
                   out_root: str | Path = "outputs/task1", use_cache: bool = True, verbose: bool = True,
                   registry: Path | None = REGISTRY) -> dict:
    seed = int(cfg.get("seed", 42))
    set_seed(seed)
    cfg.setdefault("generation", {}).setdefault("seed", seed)
    data_cfg = cfg.get("data", {})
    by_id = dataset.by_id()
    eval_on = data_cfg.get("eval_on", "val")
    eval_ids = split[eval_on] if eval_on in split else sorted(by_id)
    if data_cfg.get("sample_ids"):  # explicit subset (debugging specific submissions)
        eval_ids = [i for i in data_cfg["sample_ids"] if i in by_id]
    max_per_exam = data_cfg.get("max_eval_per_exam")
    if max_per_exam:  # quick test: first k eval samples of each exam (deterministic)
        seen: dict[str, int] = {}
        kept = []
        for i in eval_ids:
            e = by_id[i].exam_id
            if seen.get(e, 0) < int(max_per_exam):
                kept.append(i)
                seen[e] = seen.get(e, 0) + 1
        eval_ids = kept
    eval_samples = [by_id[i] for i in eval_ids]
    demo_pool = [by_id[i] for i in split.get("train", [])]

    out_dir = Path(out_root) / cfg["name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    pipe = Task1Pipeline(dataset, backend, cfg, demo_pool)

    # Prompt record (first eval sample) — exact text the model sees.
    req = pipe.build_request(eval_samples[0])
    (out_dir / "prompt.md").write_text(
        f"<!-- demos: {req['demos']} -->\n# SYSTEM\n\n{req['messages'][0]['content']}\n\n# USER\n\n"
        f"{req['messages'][1]['content']}\n", encoding="utf-8")

    model_info = backend.info()
    infer_key = _hash({
        "prompt": cfg.get("prompt"), "generation": cfg.get("generation"), "retry": cfg.get("retry_on_parse_fail", 1),
        "model": {k: model_info.get(k) for k in ("backend", "model", "json_mode", "thinking_off", "thinking_on")},
        "ids": eval_ids, "train": split.get("train"),
    })
    raw_path = out_dir / "raw_outputs.jsonl"
    # Shared cache across runs: identical prompt + generation + model + samples => identical request,
    # e.g. task1_final re-uses e3's outputs instead of calling the API again.
    shared_path = Path(out_root) / "_cache" / f"{infer_key}.jsonl"
    t0 = time.time()
    records = None
    if use_cache:
        for path in (raw_path, shared_path):
            hit = _read_cache(path, infer_key)
            if hit is not None:
                records, inference = hit
                model_info["inference"] = {**inference, "from_cache": str(path)}
                if verbose:
                    print(f"[{cfg['name']}] dùng cache ({len(records)} bài, không gọi API): {path}")
                if not shared_path.exists():  # runs made before the shared cache existed
                    _write_cache(shared_path, infer_key, records, inference)
                break
    if records is None:
        # Checkpoint: completed samples are appended after every chunk, so an interrupted run
        # (quota, Ctrl+C, 503) resumes with only the missing samples on the next call.
        partial_path = out_dir / "raw_outputs.partial.jsonl"
        done = {}
        if use_cache and partial_path.exists():
            lines = partial_path.read_text(encoding="utf-8").splitlines()
            if lines and json.loads(lines[0]).get("infer_key") == infer_key:
                done = {r["sample_id"]: r for r in map(json.loads, lines[1:]) if _complete(r)}
        if not done:
            _write_cache(partial_path, infer_key, [])
        todo = [s for s in eval_samples if s.sample_id not in done]
        if verbose:
            n = len(todo) * int(cfg.get("generation", {}).get("n", 1))
            resumed = f", {len(done)} bài đã có từ lần chạy dở" if done else ""
            print(f"[{cfg['name']}] gọi model cho {len(todo)} bài (~{n} request{resumed})...", flush=True)
        usage_before = dict(model_info.get("usage") or {})
        chunk = max(1, int(cfg.get("checkpoint_every", 4)))
        new: dict[str, dict] = {}
        for k in range(0, len(todo), chunk):
            for r in pipe.infer(todo[k:k + chunk]):
                new[r["sample_id"]] = r
                if _complete(r):
                    with open(partial_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
        records = [done.get(i) or new[i] for i in eval_ids]
        usage_after = backend.info().get("usage") or {}
        inference = {  # provenance of these outputs: model version actually served + cost (tokens)
            "model": model_info.get("model"), "served_models": backend.info().get("served_models"),
            "usage": {k: usage_after[k] - usage_before.get(k, 0) for k in usage_after},
            "inferred_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        model_info["inference"] = inference
        _write_cache(raw_path, infer_key, records, inference)
        if all(_complete(r) for r in records):  # never share outputs of failed requests
            _write_cache(shared_path, infer_key, records, inference)
            partial_path.unlink(missing_ok=True)
    infer_sec = time.time() - t0

    gold = _gold(eval_samples)
    groups = {s.sample_id: s.exam_id for s in eval_samples}
    preds = pipe.postprocess_all(records)
    main = evaluate(gold, {p["sample_id"]: p for p in preds}, groups)
    llm_only = evaluate(gold, {p["sample_id"]: {"rubric": p["rubric_llm"], "total_score": p["total_llm"]}
                               for p in preds}, groups)
    ablation = {}
    for vname, vcfg in RULE_VARIANTS.items():
        vp = pipe.postprocess_all(records, RuleConfig.from_dict(vcfg))
        m = evaluate(gold, {p["sample_id"]: p for p in vp}, groups)
        ablation[vname] = {"qwk": m["qwk"], "mae": m["mae"], "exact_total": m["exact_total"],
                           "exact_match_mean": m["exact_match_mean"]}
    parse_fail = sum(not p["parse_ok"] for p in preds)

    metrics = {"name": cfg["name"], "eval_on": eval_on, "rules": cfg.get("rules", {}), "main": main,
               "llm_only": llm_only, "rule_ablation": ablation, "parse_failures": parse_fail,
               "inference_seconds": round(infer_sec, 1)}
    _write_json(out_dir / "metrics.json", metrics)
    _write_json(out_dir / "predictions_full.json", preds)
    _write_json(out_dir / "predictions.json", to_submission(preds))
    ea = error_analysis(preds, by_id, threshold=int(cfg.get("analysis_threshold", 2)))
    _write_json(out_dir / "error_analysis.json", ea)
    (out_dir / "error_analysis.md").write_text(to_markdown(ea, f"Error analysis — {cfg['name']}"), encoding="utf-8")
    _write_json(out_dir / "config.json", {
        "config": cfg, "model_info": model_info, "infer_key": infer_key,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "n_eval": len(eval_samples),
        "eval_ids": eval_ids,
    })
    if registry is not None:
        compact = {"qwk": round(main["qwk"], 4), "mae": round(main["mae"], 3),
                   "exact_total": round(main["exact_total"], 3), "exact_match_mean": round(main["exact_match_mean"], 3),
                   "qwk_llm_only": round(llm_only["qwk"], 4), "n_eval": len(eval_samples),
                   "parse_failures": parse_fail}
        append_registry({
            "experiment_id": cfg["name"], "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "task": "task1",
            "model": model_info.get("model", ""), "config_path": cfg.get("_config_path", ""),
            "metrics": json.dumps(compact), "git_commit": _git_commit(),
            "notes": cfg.get("description", ""),
        }, registry)
    if verbose:
        print(f"== {cfg['name']} (rules={cfg.get('rules', {})})\n{format_metrics(main)}")
        print(f"   LLM-only (before rules): QWK={llm_only['qwk']:.4f} MAE={llm_only['mae']:.3f}")
        print(f"   parse failures: {parse_fail}/{len(preds)}  inference: {infer_sec:.0f}s  -> {out_dir}")
    return metrics


def predict(cfg: dict, predict_root: str | Path, predict_file: str, demo_dataset: Dataset, demo_ids: list[str],
            backend: Backend, out_path: str | Path) -> list[dict]:
    """Final-pipeline inference on an (unlabelled) task file, e.g. dev/test for the leaderboard.

    Few-shot demos come only from `demo_ids` of the labelled `demo_dataset` (never from the target set).
    """
    set_seed(int(cfg.get("seed", 42)))
    target = load_task1(predict_root, predict_file)
    demo_by_id = demo_dataset.by_id()
    pool = [demo_by_id[i] for i in demo_ids if i in demo_by_id]
    pipe = Task1Pipeline(target, backend, cfg, pool)
    records, preds = pipe.run(target.samples)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(out_path, to_submission(preds))
    _write_json(out_path.with_name(out_path.stem + "_full.json"), {"records": records, "predictions": preds})
    return preds
