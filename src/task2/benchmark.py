"""Benchmark helpers for Task 2: hardware description and the Local-CLM-vs-API comparison table."""
from __future__ import annotations

import platform
import subprocess


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
