"""Label a Task 2 dataset with an exported zero-shot CoT bundle (scripts/run_task2_cot.py --export-bundle).

Writes predictions.json (submission format), predictions_full.json, debug.jsonl, report.html and run.log.
If the dataset has gold labels, metrics.json carries macro/micro-F1 too."""
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

from src.llm.local_backend import make_local_backend  # noqa: E402
from src.task2.cot_bundle import backend_settings, load_bundle  # noqa: E402
from src.task2.cot_runner import load_with_compile, run_and_report, tee_log  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--data-root", required=True, help="Folder (or zip) with exams.json + task2_error_taxonomy.json")
    ap.add_argument("--out", default=str(ROOT / "outputs" / "task2" / "predict_cot"))
    ap.add_argument("--backend", choices=("mlx", "hf"), help="Default: the bundle's backend")
    ap.add_argument("--compile-source", choices=("self", "dataset"), help="Default: the bundle's")
    ap.add_argument("--no-compile", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    meta = load_bundle(a.bundle)
    out = Path(a.out)
    with tee_log(out / "run.log"):
        if not meta["prompt_matches_code"]:
            print("CẢNH BÁO: prompt trong code khác prompt lúc export bundle (prompt_sha256 khác) — "
                  f"checkout git {meta.get('git_commit')} để tái lập đúng.")
        compile_cfg = dict(meta.get("compile") or {})
        source = a.compile_source or compile_cfg.pop("source", "self")
        compile_cfg.pop("compiler_id", None)
        ds, compiler_id = load_with_compile(Path(a.data_root), compile_cfg, source, not a.no_compile, ROOT)
        samples = ds.samples[:a.limit]
        kind, settings = backend_settings(meta, a.backend)
        cfg = {**meta["experiment"], "name": meta["experiment"]["name"] + "_bundle"}
        print(json.dumps({"bundle": str(a.bundle), "backend": kind, "settings": settings, "compiler": compiler_id,
                          "n": len(samples)}, ensure_ascii=False, indent=2))
        backend = make_local_backend(kind, settings)
        m = run_and_report(cfg, ds, samples, backend, out, registry=None)
        api = m["systems"].get("api") or {}
        if api:
            print(f"macro-F1={api.get('macro_f1')} micro-F1={api.get('micro_f1')}")
        print(f"parse_fail={m['parse_failures']} predictions -> {out / 'predictions.json'}")


if __name__ == "__main__":
    main()
