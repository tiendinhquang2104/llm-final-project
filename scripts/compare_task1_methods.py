"""Score table: Task 1 API runs vs the QLoRA adapter, on the gold validation split.

    python scripts/compare_task1_methods.py --api-runs outputs/task1 --finetune <run>/training_summary.json

API rows come from <api-runs>/*/metrics.json ("after rules" = submitted score, "before rules" = raw model);
fine-tune rows from training_summary.json (best epoch of each arm; the adapter applies no rules).
"""
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--api-runs", type=Path, default=Path(__file__).resolve().parents[1] / "outputs" / "task1")
ap.add_argument("--finetune", type=Path, nargs="*", default=[], help="training_summary.json file(s)")
a = ap.parse_args()


def row(name, m):
    return f"| {name} | {m['n']} | {m['qwk']:.3f} | {m['mae']:.2f} | {m['exact_total']:.2f} |"


print("| Run | n | QWK | MAE | Exact total |")
print("|---|---|---|---|---|")
for path in sorted(a.api_runs.glob("*/metrics.json")):
    d = json.loads(path.read_text(encoding="utf-8"))
    if "main" not in d:
        continue
    print(row(f"API {d['name']} (after rules)", d["main"]))
    print(row(f"API {d['name']} (before rules)", d["llm_only"]))
for path in a.finetune:
    s = json.loads(path.read_text(encoding="utf-8"))
    for arm in ("gold_only_best", "silver_then_gold_best"):
        best = s[arm]
        mark = " (selected)" if best["variant"] == s["selected_variant"] else ""
        print(row(f"QLoRA {best['variant']} epoch {best['epoch']}{mark}", best["metrics"]))
