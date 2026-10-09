"""Benchmark helpers for Task 2: hardware description and the Local-CLM-vs-API comparison table."""
from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path


def hardware_info() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return " + ".join(torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count()))
    except ImportError:
        pass
    if platform.system() == "Darwin":
        try:
            chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True,
                                  timeout=5).stdout.strip()
            mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True,
                                     timeout=5).stdout.strip()) / 2**30
            return f"{chip} {mem:.0f}GB"
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return platform.processor() or platform.machine()


COLUMNS = [("run", "Run"), ("system", "Hệ thống"), ("hardware", "Phần cứng"), ("n_eval", "n val"),
           ("macro_f1", "macro-F1"), ("micro_f1", "micro-F1"), ("seconds_per_sample", "giây/bài"),
           ("train_seconds", "train (s)"), ("peak_memory_gb", "bộ nhớ đỉnh (GB)"), ("tokens_in", "token vào"),
           ("tokens_out", "token ra"), ("cost_usd", "USD")]


def collect_rows(run_dirs) -> list[dict]:
    rows = []
    for d in map(Path, run_dirs):
        if not (d / "metrics.json").exists() or not (d / "resources.json").exists():
            continue
        metrics = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
        res = json.loads((d / "resources.json").read_text(encoding="utf-8"))
        for system, m in (metrics.get("systems") or {}).items():
            rows.append({"run": d.name, "system": system, "hardware": res.get("hardware"), "n_eval": m.get("n"),
                         "macro_f1": m.get("macro_f1"), "micro_f1": m.get("micro_f1"),
                         **{k: res.get(k) for k in ("seconds_per_sample", "train_seconds", "peak_memory_gb",
                                                    "tokens_in", "tokens_out", "cost_usd")}})
    return rows


def _fmt(key: str, v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if v != v:  # NaN
            return "—"
        return f"{v:.3f}" if key in ("macro_f1", "micro_f1") else (f"{v:.4f}" if key == "cost_usd" else f"{v:.2f}")
    return str(v)


def to_markdown(rows: list[dict]) -> str:
    head = "| " + " | ".join(t for _, t in COLUMNS) + " |"
    sep = "|" + "|".join("---" for _ in COLUMNS) + "|"
    body = ["| " + " | ".join(_fmt(k, r.get(k)) for k, _ in COLUMNS) + " |" for r in rows]
    return "\n".join([head, sep, *body]) + "\n"
