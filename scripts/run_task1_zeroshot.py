"""Task 1 zero-shot CLM (no training): hand-written rubric questions, original CLM heads."""
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

from src.clm_zeroshot.task1 import run_task1_zeroshot  # noqa: E402
from src.data.loader import resolve_dataset_root  # noqa: E402
from src.task1.clm_probe import load_rubrics  # noqa: E402
from src.task1.experiment import REGISTRY  # noqa: E402
from src.task2.clm.encoder import CachedEncoder, build_from_config  # noqa: E402
from src.task2.clm.experiment import _select_public  # noqa: E402
from src.task2.compile import attach_compile_logs  # noqa: E402
from src.task2.data import load_task2  # noqa: E402
from src.utils.config import load_config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "task2" / "clm_local.yaml"))
    ap.add_argument("--gold-root")
    ap.add_argument("--public-root")
    ap.add_argument("--output-dir", default=str(ROOT / "outputs" / "task1"))
    ap.add_argument("--no-compile", action="store_true", help="No self-compiled compile_log")
    a = ap.parse_args()
    cfg = load_config(a.config)
    cfg_path = Path(a.config).resolve()
    cfg["_config_path"] = str(cfg_path.relative_to(ROOT)) if cfg_path.is_relative_to(ROOT) else str(cfg_path)
    cfg["name"] = "task1_zeroshot_" + cfg["name"].removeprefix("task2_")
    gold_root = Path(a.gold_root) if a.gold_root else ROOT / cfg["data"]["gold_root"]
    public_root = Path(a.public_root) if a.public_root else ROOT / cfg["data"]["public_root"]
    gold, public = load_task2(gold_root), load_task2(public_root)
    rubrics = load_rubrics(gold_root)
    t1_ids = {s["sample_id"] for s in json.loads(
        (resolve_dataset_root(public_root) / "task1_grading.json").read_text(encoding="utf-8"))["samples"]}
    assert t1_ids == {s.sample_id for s in public.samples}, "task1 and task2 public id sets differ"
    sel = _select_public(public, (cfg.get("data") or {}).get("public_per_exam"))
    public.samples[:] = sel
    public_ids = [s.sample_id for s in sel]
    lists, compiler_id = attach_compile_logs(cfg.get("compile"), [gold.samples, public.samples],
                                             enabled=not a.no_compile, root=ROOT)
    gold.samples[:], public.samples[:] = lists
    cfg["_compiler_id"] = compiler_id
    print(f"compile: {compiler_id or 'off (compile_log=None for every sample)'}")
    encoder, heads = build_from_config(cfg["encoder"], int(cfg["text"]["max_tokens"]), ROOT)
    enc = CachedEncoder(encoder, ROOT / cfg.get("cache_dir", "outputs/task2/_emb_cache"))
    out_dir = Path(a.output_dir) / cfg["name"]
    m = run_task1_zeroshot(cfg, enc, heads, gold, rubrics, public, public_ids, out_dir, registry=REGISTRY)
    v = m["systems"]["clm_zeroshot_prompts"]
    print(f"clm_zeroshot_prompts QWK={v['qwk']:.3f}  MAE={v['mae']:.3f}  ({m['evaluation']})")
    print(f"outputs -> {out_dir}")


if __name__ == "__main__":
    main()
