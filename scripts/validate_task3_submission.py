#!/usr/bin/env python3
"""Validate a Task 3 output JSON against requested IDs/Levels without model access."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.task3.submission import validate_submission_files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--requested-levels", required=True)
    args = parser.parse_args(argv)
    result = validate_submission_files(args.predictions, args.requested_levels)
    print(json.dumps({"status": "VALID", **result}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise SystemExit(str(exc)) from None
