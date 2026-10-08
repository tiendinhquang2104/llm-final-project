"""Shared test paths. The dataset lives in data/raw/ (git-ignored), so data-dependent tests skip without it."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "sample_dataset"
HAS_DATA = (DATA / "exams.json").exists()


def require_data() -> None:
    """Call at module level: skips the whole test module when the dataset is not present."""
    if not HAS_DATA:
        raise unittest.SkipTest(f"dataset not found at {DATA}")
