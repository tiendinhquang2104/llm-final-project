"""Bounded C++ syntax-only checks used as explicit diagnosis evidence."""

from __future__ import annotations

import os
import shutil
import subprocess
import time


MAX_SOURCE_CHARS = 200_000
MAX_DIAGNOSTIC_CHARS = 8_000


def check_cpp_syntax(code: str, *, compiler: str | None = None, timeout_s: float = 5.0, standard: str = "c++17", full_diagnostics: bool = False) -> dict:
    """Run syntax-only, never execute. Keep legacy bounded diagnostic by default.

    Full captured streams are always retained; full_diagnostics selects the
    complete stderr+stdout view. Timeout captures can be partial and say so.
    """
    if not isinstance(code, str):
        raise TypeError("C++ source must be text")
    if len(code) > MAX_SOURCE_CHARS:
        return {"status": "source_too_large", "diagnostic": "", "latency_s": 0.0, "command": []}
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
        raise ValueError("compiler timeout must be positive")
    if standard not in {"c++11", "c++17"}:
        raise ValueError("compiler standard must be c++11 or c++17")
    selected = compiler or next((shutil.which(name) for name in ("g++", "clang++", "c++") if shutil.which(name)), None)
    if not selected:
        return {"status": "unavailable", "diagnostic": "", "latency_s": 0.0, "command": []}
    command = [selected, f"-std={standard}", "-fsyntax-only", "-fno-diagnostics-color", "-x", "c++", "-"]
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
        stdout = exc.stdout or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        captured = text + stdout
        return {
            "status": "timeout",
            "diagnostic": captured if full_diagnostics else captured[:MAX_DIAGNOSTIC_CHARS],
            "stderr_full": text, "stdout_full": stdout, "capture_complete": False,
            "diagnostic_truncated": len(captured) > MAX_DIAGNOSTIC_CHARS and not full_diagnostics,
            "diagnostic_limit_chars": None if full_diagnostics else MAX_DIAGNOSTIC_CHARS,
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
    captured = (result.stderr or "") + (result.stdout or "")
    diagnostic = captured if full_diagnostics else captured[:MAX_DIAGNOSTIC_CHARS]
    return {
        "status": "compiled" if result.returncode == 0 else "compile_error",
        "diagnostic": diagnostic,
        "stderr_full": result.stderr or "", "stdout_full": result.stdout or "",
        "capture_complete": True, "diagnostic_truncated": len(diagnostic) < len(captured),
        "diagnostic_limit_chars": None if full_diagnostics else MAX_DIAGNOSTIC_CHARS,
        "returncode": result.returncode,
        "latency_s": time.perf_counter() - started,
        "command": command,
    }
