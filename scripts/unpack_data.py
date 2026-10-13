"""Extract the competition zips (public_test_release.zip, sample_dataset.zip) into data/raw/.

Accepts the zips themselves, a folder containing them, or the download bundle zip that wraps them.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.loader import KNOWN, KNOWN_DIRS, unpack  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", help="zip file or folder with zips (e.g. data/public-test)")
    ap.add_argument("--dest", default="data/raw")
    a = ap.parse_args()
    for p in unpack(Path(a.src), Path(a.dest)):
        print(p)


if __name__ == "__main__":
    main()
