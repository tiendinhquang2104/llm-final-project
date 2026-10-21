#!/usr/bin/env python3
"""Explicit entrypoint for the sole frozen v2 direct SFT pilot; no overrides."""
import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='consume the one direct optimizer-run allowance')
    args = parser.parse_args(argv)
    if not args.run:
        parser.error('use --run to explicitly start the sole frozen v2 direct pilot')
    from scripts.task3_direct_sft_v2_prepare import verify_pilot
    from src.task3.direct_sft_v2_training import run_direct_sft
    result = run_direct_sft(REPO, verify_pilot)
    print({key: result[key] for key in ('status', 'selected_epoch', 'selected_validation_loss', 'selected_adapter_sha256')}, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
