"""Task 2 Hướng 2 runner: CLM-8B heads (zero-shot, fine-tuned) + linear probe on frozen Qwen3-8B embeddings."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.task2.augment import augment  # noqa: E402
from src.task2.augment_api import load_mutants  # noqa: E402
from src.task2.clm.encoder import CachedEncoder, build_from_config  # noqa: E402
from src.task2.clm.experiment import run_clm  # noqa: E402
from src.task2.compile import attach_compile_logs  # noqa: E402
from src.task2.data import load_task2  # noqa: E402
from src.utils.config import load_config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "task2" / "clm_local.yaml"))
    ap.add_argument("--augment-api", help="mutants.json from scripts/augment_task2_api.py (overrides config augment.api_path)")
    ap.add_argument("--gold-root")
    ap.add_argument("--public-root")
    ap.add_argument("--output-dir", default=str(ROOT / "outputs" / "task2"))
    ap.add_argument("--no-compile", action="store_true", help="No self-compiled compile_log (ablation / fallback)")
    ap.add_argument("--compile-source", choices=["self", "dataset"],
                    help="self: compile every sample; dataset: use compile_log already in the data (default: config compile.source)")
    ap.add_argument("--no-public", action="store_true", help="Skip public samples (gold only)")
    a = ap.parse_args()
    cfg = load_config(a.config)
    source = a.compile_source or (cfg.get("compile") or {}).get("source", "self")
    keep = source == "dataset"  # dataset logs: "" means a clean compile
    cfg_path = Path(a.config).resolve()
    cfg["_config_path"] = str(cfg_path.relative_to(ROOT)) if cfg_path.is_relative_to(ROOT) else str(cfg_path)
    gold = load_task2(Path(a.gold_root) if a.gold_root else ROOT / cfg["data"]["gold_root"], keep_empty_compile_log=keep)
    public = None if a.no_public else load_task2(Path(a.public_root) if a.public_root
                                                 else ROOT / cfg["data"]["public_root"], keep_empty_compile_log=keep)
    aug = cfg.get("augment") or {}
    mutants = augment(gold.samples, max_per_mutator=aug.get("max_per_mutator")) if aug.get("rules", True) else []
    api_path = a.augment_api or aug.get("api_path")
    if api_path:
        api_path = Path(api_path) if Path(api_path).is_absolute() else ROOT / api_path
        mutants += load_mutants(api_path)
    print(f"augmentation: {len(mutants)} mutants of gold code (rules={aug.get('rules', True)}, api={api_path or '-'})")
    # One batch: gold + bug-injection mutants + public; organizer logs are replaced everywhere (None without compiler)
    lists, compiler_id = attach_compile_logs(cfg.get("compile"), [gold.samples, mutants, public.samples if public else []],
                                             enabled=not a.no_compile, root=ROOT, source=source)
    gold.samples[:], mutants = lists[0], lists[1]
    if public:
        public.samples[:] = lists[2]
    cfg["_compiler_id"] = compiler_id
    cfg["_compile_source"] = source if compiler_id else None
    print(f"compile: source={source} {compiler_id or 'off (compile_log=None for every sample)'}")
    encoder, heads = build_from_config(cfg["encoder"], int(cfg["text"]["max_tokens"]), ROOT)
    enc = CachedEncoder(encoder, ROOT / cfg.get("cache_dir", "outputs/task2/_emb_cache"))
    out_dir = Path(a.output_dir) / cfg["name"]
    m = run_clm(cfg, enc, heads, gold, public, out_dir, mutants)
    for key, v in m["systems"].items():
        print(f"{key:24s} macro-F1={v['macro_f1']:.3f}  micro-F1={v['micro_f1']:.3f}  exact={v['exact_match']:.2f}")
    print(f"outputs -> {out_dir}  (metrics: out-of-fold over {m['n_gold']} gold, {m['cv_folds']} folds)")


if __name__ == "__main__":
    main()
