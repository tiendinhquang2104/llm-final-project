"""Download (if needed) and extract the synthetic silver dataset into data/synth/v1/generate-dataset/.

The Google Drive file id comes from --drive-id or SILVER_DRIVE_ID (environment, .env or Kaggle secret); it is
not committed because the repo is public. Prints the silver and heldout folders with their sample counts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.synth_fetch import DEFAULT_DIR, fetch_synth  # noqa: E402
from src.task2.data import load_task2  # noqa: E402
from src.utils.config import load_dotenv  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drive-id", help="Google Drive file id of generate-dataset.zip (default: $SILVER_DRIVE_ID)")
    ap.add_argument("--dest", default=str(ROOT / DEFAULT_DIR))
    ap.add_argument("--force", action="store_true", help="Download and extract again")
    a = ap.parse_args()
    load_dotenv()
    root = fetch_synth(Path(a.dest), a.drive_id, a.force)
    for name, path in (("silver", root), ("heldout", root / "heldout")):
        if (path / "exams.json").exists():
            ds = load_task2(path)
            print(f"{name}: {path} ({len(ds.samples)} bài, {len(ds.exams)} đề)")


if __name__ == "__main__":
    main()
