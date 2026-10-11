"""Optional: generate API bug-injection mutants of the LABELLED gold samples (never test inputs).
Writes a JSON list for configs/task2/clm_*.yaml `augment.api_path`. --preflight never calls an API."""
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

from src.llm.api_client import GeminiBackend, QuotaExhausted  # noqa: E402
from src.llm.openai_client import CostLimitReached, OpenAIBackend  # noqa: E402
from src.task2.augment_api import generate_mutants, plan_jobs  # noqa: E402
from src.task2.data import load_task2  # noqa: E402
from src.task2.labels import LABELS  # noqa: E402
from src.utils.config import load_config, load_dotenv  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-config", default=str(ROOT / "configs" / "task2" / "run_api.yaml"))
    ap.add_argument("--provider", choices=("gemini", "openai"))
    ap.add_argument("--gold-root", default=str(ROOT / "data" / "raw" / "sample_dataset"))
    ap.add_argument("--labels", nargs="*", default=list(LABELS))
    ap.add_argument("--per-label", type=int, default=6)
    ap.add_argument("--output", default=str(ROOT / "outputs" / "task2" / "augment_api" / "mutants.json"))
    ap.add_argument("--preflight", action="store_true")
    a = ap.parse_args()
    load_dotenv()
    settings = load_config(a.run_config)
    provider = a.provider or settings.get("provider", "gemini")
    gold = load_task2(a.gold_root)
    out = Path(a.output)
    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    have = {r["sample_id"] for r in done}
    jobs = [(s, lab) for s, lab in plan_jobs(gold.samples, a.labels, a.per_label)
            if f"{s.sample_id}~api-{LABELS.index(lab)}" not in have]
    print(json.dumps({"provider": provider, "model": settings[provider]["model"], "existing": len(done),
                      "new_requests": len(jobs)}, ensure_ascii=False))
    if a.preflight or not jobs:
        return
    backend = GeminiBackend(**settings["gemini"]) if provider == "gemini" else OpenAIBackend(**settings["openai"])
    gen = {"temperature": 0.7, "max_new_tokens": 4096, "n": 1, "seed": 42}
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        for k in range(0, len(jobs), 8):  # checkpoint every 8 requests
            done += generate_mutants(gold, jobs[k:k + 8], backend, gen)
            out.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    except (QuotaExhausted, CostLimitReached) as exc:
        print(f"DỪNG: {exc}. Đã lưu {len(done)} mẫu; chạy lại sẽ làm tiếp.")
    print(f"{len(done)} mutants -> {out}  usage: {json.dumps(backend.info().get('usage'))}")


if __name__ == "__main__":
    main()
