"""Task 1 QLoRA v3: relabel the synthetic silver set with the API grader (knowledge distillation).

The API pipeline (Gemini e2 zero-shot structured + prerequisite/compile rules; QWK 0.8707 on the public leaderboard)
grades every silver submission and its final rubric replaces the generator's label. Only synthetic SYN-* exams are
sent: never public/private test inputs (no labels may be generated on them) and never a gold label.
Resumable: after a quota stop, run the same command again (graded samples come from checkpoints, no new calls).

    python scripts/distill_task1_silver.py --preflight            # counts only, no API call
    python scripts/distill_task1_silver.py --limit 3              # smoke: 3 API calls, writes nothing for training
    python scripts/distill_task1_silver.py                        # all 462 samples (about one day of free quota)

Output (default data/synth/v1_api, gitignored): a copy of the silver release (exams, submissions, heldout) whose
task1_grading.json carries the API labels, plus distill_manifest.json (teacher model, prompt config, tokens and cost
for the report, agreement with the generator labels). Use it as --silver-root of scripts/run_task1_finetune.py, or
upload it to the Kaggle data set in place of generate-dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import statistics
import sys
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.data.loader import DIMENSIONS, load_task1, resolve_dataset_root  # noqa: E402
from src.llm.api_client import GeminiBackend  # noqa: E402
from src.llm.openai_client import OpenAIBackend  # noqa: E402
from src.task1.public_predict import PUBLIC_EXAMS, grade_release  # noqa: E402
from src.utils.config import load_config, load_dotenv  # noqa: E402

CONFIG_DIR = ROOT / "configs" / "task1"
MANIFEST = "distill_manifest.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--silver-root", type=Path, default=ROOT / "data/synth/v1")
    ap.add_argument("--output-dir", type=Path, default=ROOT / "data/synth/v1_api")
    ap.add_argument("--experiment", default="e2_zero_shot_structured", help="API prompt config (configs/task1/)")
    ap.add_argument("--provider", choices=("gemini", "openai"))
    ap.add_argument("--run-config", type=Path, default=CONFIG_DIR / "run.yaml")
    ap.add_argument("--api-dir", type=Path, help="checkpoints and usage of the API run (default <output_dir>/distill)")
    ap.add_argument("--limit", type=int, help="grade only N samples spread over the exams (smoke test)")
    ap.add_argument("--allow-partial", action="store_true", help="write the output with the samples graded so far")
    ap.add_argument("--preflight", action="store_true", help="check data and count calls; no API call")
    return ap.parse_args(argv)


def spread_ids(samples, limit: int | None) -> list[str]:
    """Round-robin over exams so a small --limit still covers several exams."""
    by_exam: dict[str, list[str]] = {}
    for s in sorted(samples, key=lambda s: s.sample_id):
        by_exam.setdefault(s.exam_id, []).append(s.sample_id)
    order = [ids[i] for i in range(max(map(len, by_exam.values()))) for _, ids in sorted(by_exam.items())
             if i < len(ids)]
    return sorted(order[:limit]) if limit else sorted(order)


def agreement(rows: list[dict], api: dict[str, dict]) -> dict:
    pairs = [(r["output"], api[r["sample_id"]]) for r in rows if r["sample_id"] in api]
    if not pairs:
        return {}
    return {"n": len(pairs),
            "exact_total": round(sum(g["total_score"] == a["total_score"] for g, a in pairs) / len(pairs), 3),
            "mae_total": round(statistics.mean(abs(g["total_score"] - a["total_score"]) for g, a in pairs), 3),
            "exact_per_dim": {d: round(sum(g["rubric"][d] == a["rubric"][d] for g, a in pairs) / len(pairs), 3)
                              for d in DIMENSIONS}}


def distribution(outputs) -> dict:
    outputs = list(outputs)
    return {d: dict(sorted(Counter(o["rubric"][d] for o in outputs).items())) for d in DIMENSIONS} | {
        "total_mean": round(statistics.mean(o["total_score"] for o in outputs), 3)}


def main(argv: list[str] | None = None) -> None:
    a = parse_args(argv)
    load_dotenv()
    settings = load_config(a.run_config)
    provider = a.provider or settings.get("provider", "gemini")
    model = settings[provider]["model"]
    cfg = load_config(CONFIG_DIR / f"{a.experiment}.yaml")
    cfg["name"] += "__" + provider + "__" + re.sub(r"[^A-Za-z0-9._-]+", "-", model)

    root = resolve_dataset_root(a.silver_root)
    dataset = load_task1(root)
    not_synthetic = sorted(e for e in dataset.exams if not e.startswith("SYN-") or e in PUBLIC_EXAMS)
    if not_synthetic:
        sys.exit(f"Refusing: only synthetic SYN-* exams may be labelled by the API, found {not_synthetic[:5]}")
    # The generator labels are never shown to the API (zero-shot prompt); drop them so no code path can use them.
    dataset.samples = [replace(s, gold_rubric=None, gold_total=None) for s in dataset.samples]
    ids = spread_ids(dataset.samples, a.limit)
    rows = json.loads((root / "task1_grading.json").read_text(encoding="utf-8"))["samples"]
    print(json.dumps({"silver_root": str(root), "samples": len(dataset.samples), "exams": len(dataset.exams),
                      "to_grade": len(ids), "teacher": f"{provider}/{model}", "experiment": cfg["name"],
                      "max_calls_with_repairs": len(ids) * (1 + int(cfg.get("retry_on_parse_fail", 1)))},
                     ensure_ascii=False, indent=2))
    if a.preflight:
        return
    try:
        backend = GeminiBackend(**settings["gemini"]) if provider == "gemini" else OpenAIBackend(**settings["openai"])
    except RuntimeError as exc:
        sys.exit(str(exc))
    out_root = a.api_dir or ROOT / settings.get("output_dir", "outputs/task1") / "distill"
    report = grade_release(dataset, cfg, backend, out_root, selected_ids=ids if a.limit else None, tag="silver")
    run_dir = Path(report["out_dir"])
    graded = sorted(set(ids) - set(report["missing_ids"]))
    api = {sid: json.loads((run_dir / "checkpoints" / f"{sid}.json").read_text(encoding="utf-8"))["submission"]["output"]
           for sid in graded}
    print(f"[silver] graded {len(graded)}/{len(ids)} | errors {len(report['errors'])} | stopped: {report['stopped']}")
    if a.limit:
        print(json.dumps({"smoke": agreement(rows, api)}, indent=2))
        return
    if len(graded) < len(rows) and not a.allow_partial:
        print(f"Not finished ({len(rows) - len(graded)} left). Run the same command again after the quota resets; "
              "graded samples are kept. --allow-partial writes what is graded so far.")
        return

    out = a.output_dir.resolve()
    if out.exists():
        if not (out / MANIFEST).exists():
            sys.exit(f"{out} exists and was not written by this script; choose another --output-dir")
        shutil.rmtree(out)
    shutil.copytree(root, out, ignore=lambda d, names: ["task1_grading.json"] if Path(d) == root else [])
    kept = [{**r, "output": api[r["sample_id"]]} for r in rows if r["sample_id"] in api]
    (out / "task1_grading.json").write_text(json.dumps({"samples": kept}, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    usage = report["usage_total"]
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_silver": str(root),
        "source_task1_sha256": hashlib.sha256((root / "task1_grading.json").read_bytes()).hexdigest(),
        "labels": "api_teacher",
        "teacher": {"provider": provider, "model": model, "experiment": cfg["name"],
                    "config": f"configs/task1/{a.experiment}.yaml", "config_sha256": report["config_sha256"],
                    "source_commit": report["source_commit"]},
        "n_source": len(rows), "n_labelled": len(kept), "missing_ids": sorted(set(r["sample_id"] for r in rows) - set(api)),
        "errors": report["errors"],
        "cost": {"api_calls": usage["api_calls"], "input_tokens": usage["input_tokens"],
                 "output_tokens": usage["output_tokens"], "thinking_tokens": usage["thinking_tokens"],
                 "cost_usd": usage["cost_usd"], "price": report["price"],
                 "note": None if report["price"] else "free tier (billed USD 0); set gemini.input_usd_per_million / "
                                                      "output_usd_per_million in run.yaml to log the paid-tier price"},
        "agreement_with_generator_labels": agreement(rows, api),
        "distribution": {"generator": distribution(r["output"] for r in rows),
                         "api": distribution(api.values())},
        "api_run_dir": str(run_dir),
    }
    (out / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("n_labelled", "cost", "agreement_with_generator_labels")},
                     ensure_ascii=False, indent=2))
    print(f"wrote {out}  -> use it as --silver-root (or upload it to Kaggle instead of generate-dataset)")


if __name__ == "__main__":
    main()
