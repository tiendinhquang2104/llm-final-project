"""Task 2 Hướng 2 runner: CLM-8B heads (zero-shot, fine-tuned) + linear probe on frozen Qwen3-8B embeddings."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.data.loader import load_split  # noqa: E402
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
    ap.add_argument("--silver", help="silver_labels.json from run_task2_api.py (overrides config)")
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
    split = load_split(ROOT / cfg["data"]["splits_dir"])
    silver_path = a.silver or (cfg.get("silver") or {}).get("path")
    silver = json.loads(Path(silver_path).read_text(encoding="utf-8")) if silver_path else None
    if silver_path:
        print(f"silver labels: {len(silver)} samples from {silver_path}")
    encoder, heads = build_encoder(cfg["encoder"], int(cfg["text"]["max_tokens"]))
    enc = CachedEncoder(encoder, ROOT / cfg.get("cache_dir", "outputs/task2/_emb_cache"))
    out_dir = Path(a.output_dir) / cfg["name"]
    m = run_clm(cfg, enc, heads, gold, public, split, out_dir, silver)
    for key, v in m["systems"].items():
        print(f"{key:22s} macro-F1={v['macro_f1']:.3f}  micro-F1={v['micro_f1']}  exact={v['exact_match']:.2f}")
    print(f"outputs -> {out_dir}")


if __name__ == "__main__":
    main()
