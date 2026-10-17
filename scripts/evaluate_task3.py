#!/usr/bin/env python3
"""Task3 entry point; supports --help without GPU packages."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.task3.cli import evaluate_main

if __name__ == "__main__":
    try:
        evaluate_main()
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        # All explicit errors contain IDs/counts only. Never print private record data.
        raise SystemExit(str(exc)) from None
