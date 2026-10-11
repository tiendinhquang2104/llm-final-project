"""Task 2 Hướng 1 runner (Gemini or OpenAI). --preflight never calls an API."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.data.loader import load_split  # noqa: E402
from src.llm.api_client import GeminiBackend, QuotaExhausted  # noqa: E402
from src.llm.openai_client import CostLimitReached, OpenAIBackend  # noqa: E402
from src.task2.api_experiment import run_api  # noqa: E402
from src.task2.compile import attach_compile_logs  # noqa: E402
from src.task2.data import load_task2  # noqa: E402
from src.task2.pipeline import Task2ApiPipeline  # noqa: E402
from src.utils.config import load_config, load_dotenv  # noqa: E402

CONFIG_DIR = ROOT / "configs" / "task2"


def prepare(name: str, settings: dict, provider: str, smoke: bool) -> dict:
    path = CONFIG_DIR / f"{name}.yaml"
    cfg = load_config(path)
    cfg["_config_path"] = str(path.relative_to(ROOT))
    cfg["name"] += ("_smoke" if smoke else "") + f"__{provider}__" + re.sub(r"[^A-Za-z0-9._-]+", "-",
                                                                           settings[provider]["model"])
    return cfg


def preflight_entry(pipe, samples, cfg: dict, provider: str, settings: dict) -> dict:
    """Cost-gate numbers: every one of the n requests per sample resends the whole prompt."""
    n = int(cfg["generation"].get("n", 1))
    requests = len(samples) * n
    chars = sum(len(m["content"]) for s in samples for m in pipe.build_request(s)["messages"])
    tokens = chars // 3 * n
    entry = {"samples": len(samples), "requests": requests, "approx_input_tokens": tokens}
    if provider == "openai":
        o = settings["openai"]
        entry["estimated_usd"] = round((tokens * float(o["input_usd_per_million"])
                                        + requests * int(cfg["generation"].get("max_new_tokens", 0))
                                        * float(o["output_usd_per_million"])) / 1e6, 4)
    entry["demos_first_sample"] = pipe.build_request(samples[0])["demos"] if samples else []
    return entry


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-config", default=str(CONFIG_DIR / "run_api.yaml"))
    ap.add_argument("--provider", choices=("gemini", "openai"))
    ap.add_argument("--gold-root")
    ap.add_argument("--public-root")
    ap.add_argument("--output-dir")
    ap.add_argument("--preflight", action="store_true", help="Build prompts and count requests; no API call")
    ap.add_argument("--no-compile", action="store_true", help="No self-compiled compile_log (ablation / fallback)")
    ap.add_argument("--smoke", action="store_true", help="One validation sample per experiment, no public run")
    a = ap.parse_args()
    load_dotenv()
    settings = load_config(a.run_config)
    provider = a.provider or settings.get("provider", "gemini")
    run = settings["run"]
    base = load_config(CONFIG_DIR / "base.yaml")
    gold = load_task2(ROOT / (a.gold_root or base["data"]["gold_root"]))
    split = load_split(ROOT / base["data"]["splits_dir"])
    out = Path(a.output_dir) if a.output_dir else ROOT / settings.get("output_dir", "outputs/task2")
    names = list(run.get("experiments", []))
    public = None
    if run.get("predict") and not a.smoke:
        public = load_task2(ROOT / (a.public_root or base["data"]["public_root"]))
    # Self-compiled logs replace the organizer's for every sample. --preflight stays compile-free (no Docker wait;
    # its token estimate then omits the compile block).
    compile_on = not (a.no_compile or a.preflight)
    lists, compiler_id = attach_compile_logs(base.get("compile"), [gold.samples, public.samples if public else []],
                                             enabled=compile_on, root=ROOT)
    gold.samples[:] = lists[0]
    if public:
        public.samples[:] = lists[1]
    by_id = gold.by_id()
    train_pool = [by_id[i] for i in split["train"]]
    val = [by_id[i] for i in (run["smoke_sample_ids"] if a.smoke else split["val"])]

    report = {"provider": provider, "model": settings[provider]["model"], "compiler": compiler_id,
              "val_ids": [s.sample_id for s in val], "experiments": {}}
    for name in names + ([run["predict_config"]] if public else []):
        cfg = prepare(name, settings, provider, a.smoke)
        # Same wiring as the real run below: the predict pass runs on the public set;
        # demos come from gold train ids only, so gold val never leaks into the predictions.
        is_predict = public is not None and name == run["predict_config"]
        samples = public.samples if is_predict else val
        dataset = public if is_predict else gold
        pipe = Task2ApiPipeline(dataset, None, cfg, train_pool)
        report["experiments"][cfg["name"]] = preflight_entry(pipe, samples, cfg, provider, settings)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if a.preflight:
        return
    try:
        backend = GeminiBackend(**settings["gemini"]) if provider == "gemini" else OpenAIBackend(**settings["openai"])
    except RuntimeError as exc:
        sys.exit(str(exc))
    results = {}
    try:
        for name in names:
            cfg = prepare(name, settings, provider, a.smoke)
            results[cfg["name"]] = run_api(cfg, gold, val, backend, out / cfg["name"], train_pool,
                                           use_cache=run.get("use_cache", True))
        if public:
            cfg = prepare(run["predict_config"], settings, provider, False)
            run_api(cfg, public, public.samples, backend, out / cfg["name"], train_pool,
                    use_cache=run.get("use_cache", True))
            print(f"predictions -> {out / cfg['name']}")
    except (QuotaExhausted, CostLimitReached) as exc:
        print(f"DỪNG: {exc}. Phần đã xong được lưu trong {out}; chạy lại sẽ dùng cache.")
    for name, m in results.items():
        api = m["systems"].get("api") or {}
        print(f"{name}: macro-F1={api.get('macro_f1')} micro-F1={api.get('micro_f1')} parse_fail={m['parse_failures']}")
    print(f"{provider} usage: {json.dumps(backend.info().get('usage'))}")


if __name__ == "__main__":
    main()
