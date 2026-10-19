"""Bounded C++ syntax-only checks used as explicit diagnosis evidence."""

from __future__ import annotations

import os
import shutil
import subprocess
import time


MAX_SOURCE_CHARS = 200_000
MAX_DIAGNOSTIC_CHARS = 8_000


def check_cpp_syntax(code: str, *, compiler: str | None = None, timeout_s: float = 5.0) -> dict:
    """Run a compiler in syntax-only mode; never execute or emit a binary."""
    if not isinstance(code, str):
        raise TypeError("C++ source must be text")
    if len(code) > MAX_SOURCE_CHARS:
        return {"status": "source_too_large", "diagnostic": "", "latency_s": 0.0, "command": []}
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
        raise ValueError("compiler timeout must be positive")
    selected = compiler or next((shutil.which(name) for name in ("g++", "clang++", "c++") if shutil.which(name)), None)
    if not selected:
        return {"status": "unavailable", "diagnostic": "", "latency_s": 0.0, "command": []}
    command = [selected, "-std=c++17", "-fsyntax-only", "-fno-diagnostics-color", "-x", "c++", "-"]
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            input=code,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
    except subprocess.TimeoutExpired as exc:
        text = exc.stderr or ""
        if isinstance(text, bytes):
            text = text.decode("utf-8", "replace")
        return {
            "status": "timeout",
            "diagnostic": text[-MAX_DIAGNOSTIC_CHARS:],
            "latency_s": time.perf_counter() - started,
            "command": command,
        }
    except OSError as exc:
        return {
            "status": "unavailable",
            "diagnostic": type(exc).__name__,
            "latency_s": time.perf_counter() - started,
            "command": command,
        }
    diagnostic = (result.stderr or result.stdout or "")[-MAX_DIAGNOSTIC_CHARS:]
    return {
        "status": "compiled" if result.returncode == 0 else "compile_error",
        "diagnostic": diagnostic,
        "returncode": result.returncode,
        "latency_s": time.perf_counter() - started,
        "command": command,
    }
