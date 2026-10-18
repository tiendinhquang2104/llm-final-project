"""Reproduce Task 2 predictions from a CoT bundle in one command.

    python scripts/predict_task2_cot.py

with no option uses the bundle named in bundles/task2_cot/BEST, labels the 360 public samples
(configs/task2/base.yaml data.public_root), picks the backend for this machine (MLX on Apple Silicon, else
transformers) and writes predictions.json (submission format), predictions_full.json, debug.jsonl, report.html and
run.log to outputs/task2/predict_cot/<bundle>/. The backbone is downloaded at the bundle's pinned revision (or read
from <bundle>/model when the bundle carries weights); few-shot bundles rebuild their demo pools from this repo's
gold + silver (silver fetched via SILVER_DRIVE_ID) and warn when those differ from export time.
If the dataset has gold labels, metrics.json carries macro/micro-F1 too.

Bundles are written by scripts/run_task2_cot*.py --export-bundle (the Kaggle notebooks do it)."""
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.llm.local_backend import make_local_backend  # noqa: E402
from src.task2.cot_bundle import backend_settings, check_demo_pools, load_bundle  # noqa: E402
from src.task2.cot_runner import build_retriever, load_with_compile, run_and_report, tee_log  # noqa: E402
from src.utils.config import load_config, load_dotenv  # noqa: E402

BUNDLES = ROOT / "bundles" / "task2_cot"


def resolve_bundle(name: str) -> Path:
    """'best' -> the folder named on the first line of bundles/task2_cot/BEST; a bare name -> bundles/task2_cot/<name>;
    anything else is a path."""
    if name == "best":
        name = (BUNDLES / "BEST").read_text(encoding="utf-8").split()[0]
    path = Path(name)
    return path if path.exists() else BUNDLES / name


def auto_backend() -> str:
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            import mlx_lm  # noqa: F401
            return "mlx"
        except ImportError:
            pass
    return "hf"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", default="best", help="'best' (bundles/task2_cot/BEST), a name in bundles/task2_cot/, "
                    "or a path")
    ap.add_argument("--data-root", help="Folder (or zip) with exams.json + task2_error_taxonomy.json "
                    "(default: the 360 public samples)")
    ap.add_argument("--out", help="Default: outputs/task2/predict_cot/<bundle>")
    ap.add_argument("--backend", choices=("auto", "mlx", "hf", "vllm"), default="auto",
                    help="auto: MLX on Apple Silicon with mlx_lm installed, else transformers")
    ap.add_argument("--compile-source", choices=("self", "dataset"), help="Default: the bundle's")
    ap.add_argument("--no-compile", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ids", nargs="+", help="Only these sample_ids")
    a = ap.parse_args()
    load_dotenv()
    bundle = resolve_bundle(a.bundle)
    meta = load_bundle(bundle)
    data_root = Path(a.data_root) if a.data_root else ROOT / load_config(ROOT / "configs/task2/base.yaml")["data"]["public_root"]
    out = Path(a.out) if a.out else ROOT / "outputs" / "task2" / "predict_cot" / bundle.name
    with tee_log(out / "run.log"):
        if not meta["prompt_matches_code"]:
            print("CẢNH BÁO: prompt trong code khác prompt lúc export bundle (prompt_sha256 khác) — "
                  f"checkout git {meta.get('git_commit')} để tái lập đúng.")
        compile_cfg = dict(meta.get("compile") or {})
        source = a.compile_source or compile_cfg.pop("source", "self")
        compile_cfg.pop("source", None)
        compile_cfg.pop("compiler_id", None)
        ds, compiler_id = load_with_compile(data_root, compile_cfg, source, not a.no_compile, ROOT)
        if (meta["experiment"].get("prompt") or {}).get("compile_rule") and not a.no_compile and not compiler_id \
                and source == "self":
            print("CẢNH BÁO: không có compiler (Docker tắt? g++ thiếu?) -> quy tắc 'Lỗi biên dịch' không áp dụng.")
        samples = [ds.by_id()[i] for i in a.ids] if a.ids else ds.samples[:a.limit]
        kind, settings = backend_settings(meta, auto_backend() if a.backend == "auto" else a.backend)
        cfg = {**meta["experiment"], "name": meta["experiment"]["name"] + "_bundle"}
        print(json.dumps({"bundle": str(bundle), "data_root": str(data_root), "backend": kind, "settings": settings,
                          "compiler": compiler_id, "n": len(samples)}, ensure_ascii=False, indent=2))
        backend = make_local_backend(kind, settings)
        # few-shot bundles retrieve demos from this repo's gold + silver (never from the predicted set's labels)
        retriever = build_retriever(cfg, ROOT, compile_cfg, source, not a.no_compile)
        for diff in check_demo_pools(meta, retriever.fingerprint() if retriever else None):
            print(f"CẢNH BÁO demo pool khác lúc export ({diff}): demo và kết quả có thể khác.")
        m = run_and_report(cfg, ds, samples, backend, out, registry=None, demo_pool=retriever or ())
        api = m["systems"].get("api") or {}
        if api:
            print(f"macro-F1={api.get('macro_f1')} micro-F1={api.get('micro_f1')}")
        print(f"parse_fail={m['parse_failures']} predictions -> {out / 'predictions.json'}")


if __name__ == "__main__":
    main()
