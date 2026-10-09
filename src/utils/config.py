"""YAML config loading (with `extends` inheritance) and `.env` loading."""
from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(path: str | Path) -> dict:
    """Load a YAML config; `extends: <relative path>` merges the parent config underneath."""
    path = Path(path)
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "extends" in cfg:
        parent = load_config(path.parent / cfg.pop("extends"))
        cfg = deep_merge(parent, cfg)
    return cfg


def load_dotenv(path: str | Path = PROJECT_ROOT / ".env") -> None:
    """Minimal .env reader (KEY=VALUE lines); never overrides variables already set in the environment."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
