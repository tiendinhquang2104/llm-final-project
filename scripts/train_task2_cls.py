"""Train one F-cls run (a gold fold or the final model) and score it; safe to re-run after a Kaggle timeout.

    # fold runs (out-of-fold scores on gold), one GPU each, then the final model + public probabilities
    CUDA_VISIBLE_DEVICES=0 python scripts/train_task2_cls.py --holdout EX01 --deadline $DEADLINE &
    CUDA_VISIBLE_DEVICES=1 python scripts/train_task2_cls.py --holdout EX02 --deadline $DEADLINE &
    python scripts/train_task2_cls.py --holdout all --deadline $DEADLINE

A run lives in <out-root>/<name>__<holdout>/: checkpoints/, adapter/ (when done), status.json, train_log.jsonl,
run_info.json, probs_gold.jsonl (+ probs_public.jsonl for the final run). Re-running a run that is "done" only
redoes the missing probabilities; a "paused" or interrupted run resumes from its last checkpoint (also looked
for under --resume-dir, e.g. /kaggle/input, and on the Hub with --hub-repo + HF_TOKEN).
Exit code 0 when done, 3 when paused by the deadline (run the notebook again to continue).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# before CUDA is initialised: lets the allocator grow segments instead of fragmenting (the OOM log showed
# 2.3 GiB reserved but unallocated)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.task2.cls_data import (eval_records, label_counts, oversample, pos_weight, read_jsonl, sample_weights,  # noqa: E402
                                train_records, write_jsonl)
from src.training.task2_cls import (HubSync, env_info, predict, read_status, resolved_revision,  # noqa: E402
                                    train_run, write_status)
from src.utils.config import load_config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/task2/cls_qwen7b.yaml")
    ap.add_argument("--records", help="records.jsonl (default: <data.cls_dir>/records.jsonl)")
    ap.add_argument("--holdout", required=True, help="gold exam left out (EX01 / EX02) or 'all' for the final model")
    ap.add_argument("--out-root", default="outputs/task2/cls")
    ap.add_argument("--deadline", type=float, help="unix time: save + stop before it (Kaggle session limit)")
    ap.add_argument("--max-hours", type=float, help="alternative to --deadline: stop after this many hours")
    ap.add_argument("--resume-dir", action="append", default=[], help="extra folder to look for checkpoints in")
    ap.add_argument("--hub-repo", help="private HF repo mirroring the last checkpoint (needs HF_TOKEN)")
    ap.add_argument("--model", help="override model.name (tiny model for smoke tests)")
    ap.add_argument("--epochs", type=float, help="override train.epochs")
    ap.add_argument("--lr", type=float, help="override train.lr")
    ap.add_argument("--tag", default="", help="suffix of the run folder (lr/epoch grid)")
    ap.add_argument("--limit-train", type=int, help="first N training rows (smoke tests)")
    ap.add_argument("--no-public", action="store_true", help="final run: skip the public probabilities")
    a = ap.parse_args()

    cfg = load_config(ROOT / a.config)
    if a.model:
        cfg["model"]["name"] = a.model
    if a.epochs:
        cfg["train"]["epochs"] = a.epochs
    if a.lr:
        cfg["train"]["lr"] = a.lr
    tcfg = cfg["train"]
    records = read_jsonl(ROOT / (a.records or Path(cfg["data"]["cls_dir"]) / "records.jsonl"))
    holdout = None if a.holdout == "all" else a.holdout
    run_dir = ROOT / a.out_root / f"{cfg['name']}__{a.holdout}{('_' + a.tag) if a.tag else ''}"
    deadline = a.deadline or (time.time() + a.max_hours * 3600 if a.max_hours else None)

    train = train_records(records, holdout, tcfg.get("use_gold", True), tcfg.get("use_mutants", True))
    train = oversample(train, int(tcfg.get("oversample_min", 0)), seed=int(cfg.get("seed", 42)))
    if a.limit_train:
        train = train[:a.limit_train]
    weights = sample_weights(train, tcfg.get("source_weight"))
    pw = pos_weight(train, float(tcfg.get("pos_weight_cap", 10.0)))
    evals = eval_records(records, holdout) if holdout else [r for r in records if r["source"] == "gold"]
    run_dir.mkdir(parents=True, exist_ok=True)
    info_path = run_dir / "run_info.json"
    if not info_path.exists():
        info_path.write_text(json.dumps({
            "holdout": a.holdout, "config": cfg, "n_train": len(train), "train_label_counts": label_counts(train),
            "by_source": {s: sum(r["source"] == s for r in train) for s in ("synth", "gold", "gold_mut")},
            "pos_weight": pw, "n_eval": len(evals), "model_revision": resolved_revision(cfg["model"]["name"],
                                                                                          cfg["model"].get("revision")),
            "env": env_info()}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[run] {run_dir.name}: train={len(train)} eval={len(evals)} pos_weight={[round(x, 1) for x in pw]}",
          flush=True)

    hub = None
    if a.hub_repo and os.environ.get("HF_TOKEN"):
        hub = HubSync(a.hub_repo, run_dir.name, os.environ["HF_TOKEN"])
    st = train_run(cfg, train, weights, pw, run_dir, deadline, a.resume_dir, hub)
    if st.get("state") != "done":
        sys.exit(3)

    bs = int(tcfg.get("eval_batch_size", 4))
    todo = [("gold", evals)]
    if not holdout and not a.no_public:
        todo.append(("public", [r for r in records if r["source"] == "public"]))
    for split, rows in todo:
        path = run_dir / f"probs_{split}.jsonl"
        if path.exists() or not rows:
            continue
        if deadline and time.time() > deadline - 300:
            print(f"[predict] no time left for {split}: run again", flush=True)
            sys.exit(3)
        t0 = time.time()
        write_jsonl(path, predict(cfg, rows, run_dir / "adapter", bs))
        print(f"[predict] {split}: {len(rows)} rows in {time.time() - t0:.0f}s -> {path}", flush=True)
    write_status(run_dir, **{**read_status(run_dir), "predicted": True})


if __name__ == "__main__":
    main()
