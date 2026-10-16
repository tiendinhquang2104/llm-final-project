"""Task 3 Runner: Generate Pedagogical Feedback via LLM API with Pedagogical Guard."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.evaluation.metrics import evaluate_task3_compliance
from src.task3.pipeline import Task3Pipeline
from src.utils.config import load_config, load_dotenv

CONFIG_DIR = ROOT / "configs" / "task3"
DEFAULT_DATA_DIR = ROOT.parent / "public-test-cham-diem-phan-hoi-files" / "sample_dataset"


@dataclass
class Task3Item:
    sample_id: str
    exam_id: str
    exam_type: str
    exam_statement: str
    code: str
    target_feedback_level: str
    taxonomy_error: list[str]
    compile_log: str | None = None


def load_task3_data(data_dir: str | Path) -> list[Task3Item]:
    """Load Task 3 samples cleanly from data_dir."""
    root = Path(data_dir).resolve()
    # Resolve subfolder if needed
    for candidate in [root, root / "sample_dataset", root / "sample_dataset" / "sample_dataset"]:
        if (candidate / "exams.json").exists() and (candidate / "task3_feedback.json").exists():
            root = candidate
            break

    exams_file = root / "exams.json"
    t3_file = root / "task3_feedback.json"
    if not exams_file.exists() or not t3_file.exists():
        raise FileNotFoundError(f"Missing exams.json or task3_feedback.json under {root}")

    with exams_file.open(encoding="utf-8") as f:
        exams_data = {e["exam_id"]: e for e in json.load(f)["exams"]}

    with t3_file.open(encoding="utf-8") as f:
        t3_data = json.load(f)["samples"]

    items: list[Task3Item] = []
    for s in t3_data:
        sid = s["sample_id"]
        inp = s["input"]
        eid = inp["exam_id"]
        exam = exams_data[eid]

        code_path = root / inp["code_file"]
        code = ""
        if code_path.exists():
            code = code_path.read_text(encoding="utf-8", errors="replace")

        # taxonomy_error may be in input, or empty
        tax = inp.get("taxonomy_error", [])
        lvl = inp.get("target_feedback_level", "Level 2 - Chẩn đoán")
        clog = inp.get("compile_log", "")

        items.append(
            Task3Item(
                sample_id=sid,
                exam_id=eid,
                exam_type=inp.get("exam_type", exam.get("exam_type", "single_problem")),
                exam_statement=exam["statement"],
                code=code,
                target_feedback_level=lvl,
                taxonomy_error=tax,
                compile_log=clog,
            )
        )

    return items


def build_backend(provider: str, settings: dict):
    """Instantiate API backend (Gemini or OpenAI)."""
    if provider == "gemini":
        from src.llm.api_client import GeminiBackend
        cfg = settings.get("gemini", {})
        return GeminiBackend(
            model=cfg.get("model", "gemini-2.5-flash"),
            rpm=cfg.get("rpm", 15),
            tpm=cfg.get("tpm", 0),
            max_requests=cfg.get("max_requests_per_run", 400),
        )
    elif provider == "openai":
        from src.llm.openai_client import OpenAIBackend
        cfg = settings.get("openai", {})
        return OpenAIBackend(
            model=cfg.get("model", "gpt-4o-mini"),
            rpm=cfg.get("rpm", 60),
            tpm=cfg.get("tpm", 0),
            max_requests=cfg.get("max_requests_per_run", 400),
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Task 3 Feedback Generator Runner")
    parser.add_argument("--config", default="e1_api_baseline", help="Config name or relative path")
    parser.add_argument("--provider", default="gemini", choices=["gemini", "openai"])
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Dataset root directory")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of samples to evaluate")
    parser.add_argument("--preflight", action="store_true", help="Print prompt plan without calling API")
    parser.add_argument("--out", default=str(ROOT / "outputs" / "task3" / "predictions_task3.json"))
    args = parser.parse_args()

    load_dotenv()
    settings_path = ROOT / "configs" / "task1" / "run.yaml"
    settings = load_config(settings_path) if settings_path.exists() else {}

    cfg_file = CONFIG_DIR / f"{args.config}.yaml" if not args.config.endswith(".yaml") else Path(args.config)
    cfg = load_config(cfg_file) if cfg_file.exists() else {}

    print(f"Loading dataset from: {args.data_dir}...")
    samples = load_task3_data(args.data_dir)
    if args.limit:
        samples = samples[: args.limit]
    print(f"Loaded {len(samples)} samples.")

    if args.preflight:
        print("\n=== PREFLIGHT CHECK (NO API CALLS) ===")
        print(f"Provider: {args.provider}")
        print(f"Total samples: {len(samples)}")
        for i, s in enumerate(samples[:2]):
            print(f"\n--- Sample {i+1}: {s.sample_id} ({s.target_feedback_level}) ---")
            print(f"Errors: {s.taxonomy_error}")
            print(f"Statement: {s.exam_statement[:120]}...")
            print(f"Code lines: {len(s.code.splitlines())}")
        print("\nPreflight check complete. Everything looks ready.")
        return

    backend = build_backend(args.provider, settings)
    pipe = Task3Pipeline(backend, cfg)

    predictions = []
    compliance_records = []
    print(f"\nRunning Task 3 pipeline with {args.provider}...")
    start_time = time.time()

    for idx, s in enumerate(samples):
        res = pipe.process_single(
            exam_id=s.exam_id,
            exam_type=s.exam_type,
            exam_statement=s.exam_statement,
            code=s.code,
            target_level=s.target_feedback_level,
            taxonomy_error=s.taxonomy_error,
            compile_log=s.compile_log,
        )

        pred_entry = {
            "sample_id": s.sample_id,
            "output": {
                "taxonomy_error": res["taxonomy_error"],
                "feedback": res["feedback"],
            },
        }
        predictions.append(pred_entry)

        compliance_records.append({
            "feedback": res["feedback"],
            "target_feedback_level": s.target_feedback_level,
            "taxonomy_error": s.taxonomy_error,
        })

        status = "COMPLIANT" if res["is_compliant"] else "SANITIZED"
        print(f"[{idx+1}/{len(samples)}] {s.sample_id} | {s.target_feedback_level} -> {status}")

    elapsed = time.time() - start_time
    metrics = evaluate_task3_compliance(compliance_records)

    print("\n================ EVALUATION SUMMARY ================")
    print(f"Total evaluated: {int(metrics['total_samples'])} samples")
    print(f"Level Compliance Rate: {metrics['level_compliance_rate'] * 100:.2f}%")
    print(f"Empty on Zero-Error Rate: {metrics['empty_on_zero_error_rate'] * 100:.2f}%")
    print(f"Total Time: {elapsed:.2f}s ({elapsed / len(samples):.2f}s/sample)")
    print("====================================================")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)
    print(f"\nPredictions successfully saved to: {out_path}")


if __name__ == "__main__":
    main()
