"""unpack_data: extracts the known competition zips, directly or from a bundle zip."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from unpack_data import unpack  # noqa: E402


def _zip(path: Path, files: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return path


class TestUnpack(unittest.TestCase):
    def test_inner_and_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "src"
            src.mkdir()
            _zip(src / "sample_dataset.zip", {"sample_dataset/exams.json": "{}"})
            inner = _zip(tmp / "public_test_release.zip", {"public_test_release/exams.json": "{}"})
            with zipfile.ZipFile(src / "bundle.zip", "w") as zf:  # download bundle wrapping an inner zip
                zf.writestr("metadata.txt", "x")
                zf.write(inner, "public_test_release.zip")
            out = unpack(src, tmp / "raw")
            self.assertTrue((tmp / "raw" / "sample_dataset" / "exams.json").exists())
            self.assertTrue((tmp / "raw" / "public_test_release" / "exams.json").exists())
            self.assertEqual(sorted(p.name for p in out), ["public_test_release", "sample_dataset"])
