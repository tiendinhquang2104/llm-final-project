"""Load project settings from environment / .env (per-person overrides)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def load_project_env(*extra_paths: str | Path) -> list[Path]:
    """
    Load .env files in order (later files do not override earlier by default
    unless override=True on a specific call). Returns paths that existed.
    """
    loaded: list[Path] = []
    candidates: list[Path] = []
    for p in extra_paths:
        if p:
            candidates.append(Path(p))
    # Drive / Colab private env (optional)
    drive_env = os.getenv("DRIVE_ENV_FILE")
    if drive_env:
        candidates.append(Path(drive_env))
    # CWD and repo-root .env
    candidates.append(Path.cwd() / ".env")
    candidates.append(Path(__file__).resolve().parents[2] / ".env")

    seen: set[Path] = set()
    for path in candidates:
        path = path.resolve() if path.exists() else path
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            load_dotenv(path, override=False)
            loaded.append(path)
    # Also pick up process env already set by Colab userdata, etc.
    load_dotenv(override=False)
    return loaded


def env_str(key: str, default: str = "") -> str:
    val = os.getenv(key)
    if val is None or val.strip() == "":
        return default
    return val.strip()


def env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)
