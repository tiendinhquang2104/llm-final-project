"""Task 1 runner shared by Gemini and OpenAI; --preflight never calls an API."""

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

from src.data.loader import load_split, load_task1  # noqa: E402
from src.llm.api_client import GeminiBackend, QuotaExhausted  # noqa: E402
from src.llm.openai_client import CostLimitReached, OpenAIBackend  # noqa: E402
from src.task1.experiment import run_experiment  # noqa: E402
from src.task1.pipeline import Task1Pipeline  # noqa: E402
from src.task1.public_predict import predict_public, public_preflight  # noqa: E402
from src.utils.config import load_config, load_dotenv  # noqa: E402

CONFIG_DIR = ROOT / "configs" / "task1"


def prepare(name: str, settings: dict, provider: str) -> dict:
    path = CONFIG_DIR / f"{name}.yaml"
    cfg = load_config(path)
    cfg["_config_path"] = str(path.relative_to(ROOT)).replace("\\", "/")
    if settings["run"].get("test_mode"):
        cfg["data"]["sample_ids"] = settings["run"]["test_sample_ids"]
        cfg["name"] += "_test"
    model = settings[provider]["model"]
    cfg["name"] += "__" + provider + "__" + re.sub(r"[^A-Za-z0-9._-]+", "-", model)
    if provider == "openai":
        cfg["checkpoint_every"] = 1
    return cfg


def validate_split(dataset, split: dict) -> None:
    train, val = set(split["train"]), set(split["val"])
    ids = set(dataset.by_id())
    if train & val or train | val != ids:
        raise ValueError("Split IDs overlap or do not cover the Task 1 dataset")
    if len(ids) == 32 and (len(train), len(val)) != (26, 6):
        raise ValueError(f"Expected canonical 26/6 split, got {len(train)}/{len(val)}")


def preflight(dataset, split: dict, settings: dict, provider: str, names: list[str]) -> dict:
    validate_split(dataset, split)
    by_id = dataset.by_id()
    selected = settings["run"].get("test_sample_ids", []) if settings["run"].get("test_mode") else split["val"]
    if any(sid not in split["val"] for sid in selected):
        raise ValueError("Smoke-test IDs must be members of the 6 validation samples")
    prompts = {}
    estimated_usd = 0.0
    for name in names:
        cfg = prepare(name, settings, provider)
        pipe = Task1Pipeline(dataset, None, cfg, [by_id[i] for i in split["train"]])
        prompts[name] = {sid: pipe.build_request(by_id[sid])["demos"] for sid in selected}
        if provider == "openai":
            price = settings["openai"]
            for sid in selected:
                messages = pipe.build_request(by_id[sid])["messages"]
                estimated_usd += int(cfg["generation"].get("n", 1)) * (
                    max(1, sum(len(m["content"]) for m in messages) // 3) * price["input_usd_per_million"]
                    + int(cfg["generation"].get("max_new_tokens", 1024)) * price["output_usd_per_million"]
                ) / 1_000_000
    report = {"provider": provider, "model": settings[provider]["model"],
              "train": len(split["train"]), "validation": len(split["val"]),
              "selected_val_ids": selected, "experiments": names,
              "planned_initial_calls": sum(len(selected) * int(prepare(n, settings, provider)["generation"].get("n", 1)) for n in names),
              "estimated_initial_usd_excluding_repairs": round(estimated_usd, 6) if provider == "openai" else None,
              "few_shot_ids": prompts}
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-config", default=str(CONFIG_DIR / "run.yaml"))
    ap.add_argument("--provider", choices=("gemini", "openai"))
    ap.add_argument("--data-dir", help="Dataset root; can be the parent of sample_dataset/")
    ap.add_argument("--splits-dir", help="Directory with train_ids.json and val_ids.json")
    ap.add_argument("--output-dir", help="Private output directory")
    ap.add_argument("--preflight", action="store_true", help="Check data, prompts, split and call count without API")
    ap.add_argument("--smoke", action="store_true", help="Run one validation sample per selected experiment")
    ap.add_argument("--predict-only", action="store_true", help="Predict the unlabeled 360-sample public release")
    ap.add_argument("--predict-root", help="Extracted public release, or its parent directory")
    ap.add_argument("--predict-experiment", default="e2_zero_shot_structured")
    ap.add_argument("--predict-ids", help="Comma-separated public sample IDs for a smoke run")
    a = ap.parse_args()
    load_dotenv()
    settings = load_config(a.run_config)
    provider = a.provider or settings.get("provider", "gemini")
    run = settings["run"]
    if a.smoke:
        run["test_mode"] = True
        run["test_sample_ids"] = run.get("test_sample_ids", [])[:1]
    out = Path(a.output_dir) if a.output_dir else ROOT / settings.get("output_dir", "outputs/task1")
    base = load_config(CONFIG_DIR / "base.yaml")
    data_root = Path(a.data_dir) if a.data_dir else ROOT / base["data"]["root"]
    ds = load_task1(data_root, base["data"].get("task_file", "task1_grading.json"))
    split = load_split(Path(a.splits_dir) if a.splits_dir else ROOT / base["data"]["splits_dir"])
    validate_split(ds, split)
    if a.predict_only:
        if not a.predict_root:
            ap.error("--predict-only requires --predict-root")
        cfg = prepare(a.predict_experiment, settings, provider)
        selected_ids = [sid.strip() for sid in a.predict_ids.split(",") if sid.strip()] if a.predict_ids else None
        public_ds, report = public_preflight(a.predict_root, cfg, ds, split["train"], selected_ids)
        if provider == "openai":
            price = settings["openai"]
            pipe = Task1Pipeline(public_ds, None, cfg)
            rows = [public_ds.by_id()[sid] for sid in (selected_ids or sorted(public_ds.by_id()))]
            estimate = sum((max(1, sum(len(m["content"]) for m in pipe.build_request(s)["messages"]) // 3)
                            * price["input_usd_per_million"]
                            + int(cfg["generation"].get("max_new_tokens", 1024))
                            * price["output_usd_per_million"]) / 1_000_000 for s in rows)
            report["estimated_initial_usd_excluding_repairs"] = round(estimate, 6)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if a.preflight:
            return
        try:
            backend = GeminiBackend(**settings["gemini"]) if provider == "gemini" else OpenAIBackend(**settings["openai"])
        except RuntimeError as exc:
            sys.exit(str(exc))
        result = predict_public(public_ds, cfg, backend, out, ds, split["train"], selected_ids)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    names = list(run.get("experiments", []))
    if run.get("run_final"):
        names.append("final")
    report = preflight(ds, split, settings, provider, names)
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
            cfg = prepare(name, settings, provider)
            results[cfg["name"]] = run_experiment(cfg, ds, split, backend, out, use_cache=run.get("use_cache", True))
        if run.get("predict_file") and not run.get("test_mode"):
            cfg = prepare(run.get("predict_experiment", "e2_zero_shot_structured"), settings, provider)
            pred_root = Path(run["predict_root"]) if run.get("predict_root") else data_root
            public_ds, _ = public_preflight(pred_root, cfg, ds, split["train"])
            result = predict_public(public_ds, cfg, backend, out, ds, split["train"])
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (QuotaExhausted, CostLimitReached) as exc:
        print(f"DỪNG: {exc}. Các run đã xong vẫn được lưu trong {out}; chạy lại sẽ dùng cache.")
    print("\n===== Tóm tắt =====")
    for name, metrics in results.items():
        main = metrics["main"]
        print(f"{name}: n={main['n']} QWK={main['qwk']:.3f} MAE={main['mae']:.2f} EM6={main['exact_match_mean']:.2f}")
    print(f"{provider} usage: {json.dumps(backend.info()['usage'])}")


if __name__ == "__main__":
    main()
