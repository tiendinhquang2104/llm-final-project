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
from src.task2.clm.encoder import CachedEncoder  # noqa: E402
from src.task2.clm.experiment import run_clm  # noqa: E402
from src.task2.data import load_task2  # noqa: E402
from src.utils.config import load_config  # noqa: E402


def build_encoder(enc_cfg: dict, max_tokens: int):
    """-> (encoder, heads_path). Downloads only weights/config files, never Python code from the Hub."""
    if enc_cfg["backend"] == "mlx":
        from huggingface_hub import snapshot_download

        from src.task2.clm.encoder import MLXEncoder

        local = Path(snapshot_download(enc_cfg["repo"], local_dir=str(ROOT / enc_cfg["local_dir"]),
                                       allow_patterns=["encoder/*", "heads/*", "clm_mlx.json", "LICENSE", "NOTICE"]))
        return MLXEncoder(local / "encoder", max_tokens, int(enc_cfg.get("batch_tokens", 4096))), local / "heads"
    from huggingface_hub import hf_hub_download

    from src.task2.clm.encoder import HFEncoder

    heads = hf_hub_download(enc_cfg["heads_repo"], enc_cfg["heads_file"])
    enc = HFEncoder(enc_cfg["model"], max_tokens, enc_cfg.get("dtype", "float16"),
                    bool(enc_cfg.get("load_in_8bit", False)), int(enc_cfg.get("batch_size", 2)))
    return enc, Path(heads)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "task2" / "clm_local.yaml"))
    ap.add_argument("--augment-api", help="mutants.json from scripts/augment_task2_api.py (overrides config augment.api_path)")
    ap.add_argument("--gold-root")
    ap.add_argument("--public-root")
    ap.add_argument("--output-dir", default=str(ROOT / "outputs" / "task2"))
    ap.add_argument("--no-public", action="store_true", help="Skip public samples (gold only)")
    a = ap.parse_args()
    cfg = load_config(a.config)
    cfg_path = Path(a.config).resolve()
    cfg["_config_path"] = str(cfg_path.relative_to(ROOT)) if cfg_path.is_relative_to(ROOT) else str(cfg_path)
    gold = load_task2(Path(a.gold_root) if a.gold_root else ROOT / cfg["data"]["gold_root"])
    public = None if a.no_public else load_task2(Path(a.public_root) if a.public_root
                                                 else ROOT / cfg["data"]["public_root"])
    aug = cfg.get("augment") or {}
    mutants = augment(gold.samples, max_per_mutator=aug.get("max_per_mutator")) if aug.get("rules", True) else []
    api_path = a.augment_api or aug.get("api_path")
    if api_path:
        api_path = Path(api_path) if Path(api_path).is_absolute() else ROOT / api_path
        mutants += load_mutants(api_path)
    print(f"augmentation: {len(mutants)} mutants of gold code (rules={aug.get('rules', True)}, api={api_path or '-'})")
    encoder, heads = build_encoder(cfg["encoder"], int(cfg["text"]["max_tokens"]))
    enc = CachedEncoder(encoder, ROOT / cfg.get("cache_dir", "outputs/task2/_emb_cache"))
    out_dir = Path(a.output_dir) / cfg["name"]
    m = run_clm(cfg, enc, heads, gold, public, out_dir, mutants)
    for key, v in m["systems"].items():
        print(f"{key:24s} macro-F1={v['macro_f1']:.3f}  micro-F1={v['micro_f1']:.3f}  exact={v['exact_match']:.2f}")
    print(f"outputs -> {out_dir}  (metrics: out-of-fold over {m['n_gold']} gold, {m['cv_folds']} folds)")


if __name__ == "__main__":
    main()
