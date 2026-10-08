"""Print a markdown comparison table of all Task 1 runs (main metrics + rule ablation)."""
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--runs", default=str(Path(__file__).resolve().parents[1] / "outputs" / "task1"))
a = ap.parse_args()

rows = []
for m in sorted(Path(a.runs).glob("*/metrics.json")):
    d = json.loads(m.read_text(encoding="utf-8"))
    rows.append(d)
print("| run | QWK | MAE | exact total | exact-match mean | QWK LLM-only | parse fail |")
print("|---|---|---|---|---|---|---|")
for d in rows:
    mm, lo = d["main"], d["llm_only"]
    print(f"| {d['name']} | {mm['qwk']:.4f} | {mm['mae']:.3f} | {mm['exact_total']:.3f} | "
          f"{mm['exact_match_mean']:.3f} | {lo['qwk']:.4f} | {d['parse_failures']} |")
print("\nRule ablation (QWK / MAE):\n")
variants = list(rows[0]["rule_ablation"]) if rows else []
print("| run | " + " | ".join(variants) + " |")
print("|---|" + "---|" * len(variants))
for d in rows:
    ab = d["rule_ablation"]
    print(f"| {d['name']} | " + " | ".join(f"{ab[v]['qwk']:.3f} / {ab[v]['mae']:.2f}" for v in variants) + " |")
