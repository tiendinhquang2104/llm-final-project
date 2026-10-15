"""Get the synthetic (silver) dataset: data/synth/v1/generate-dataset.zip -> data/synth/v1/generate-dataset/.

Order: extracted folder already there -> use it; else the zip is there -> extract it; else download the zip from
Google Drive (file id from the argument or the SILVER_DRIVE_ID environment variable / .env / Kaggle secret; the
id is not committed because the repo is public). macOS archive junk (__MACOSX/, ._*) is skipped.

Layout inside the folder (docs/synth_plan.md): exams.json + task{1,2,3}_*.json + submissions/ (silver, used to tune
prompts) and heldout/ (4 exams kept apart, evaluation only)."""
from __future__ import annotations

import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_DIR = Path("data/synth/v1")
ZIP_NAME = "generate-dataset.zip"
ENV_VAR = "SILVER_DRIVE_ID"


def _junk(name: str) -> bool:
    parts = Path(name).parts
    return not parts or parts[0] == "__MACOSX" or Path(name).name.startswith("._") or Path(name).name == ".DS_Store"


def extract(zip_path, dest) -> Path:
    """Extract `zip_path` into `dest` without macOS junk; refuses entries escaping `dest`. Returns the folder that
    holds exams.json."""
    zip_path, dest = Path(zip_path), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    base = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if _junk(info.filename):
                continue
            target = (dest / info.filename).resolve()
            if base != target and base not in target.parents:
                raise ValueError(f"{zip_path}: entry escapes the destination: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
    return find_root(dest)


def find_root(dest) -> Path:
    """Folder under `dest` with exams.json + task2_error_taxonomy.json, preferring the shallowest (heldout/ is
    one level deeper than the silver set)."""
    hits = sorted((p.parent for p in Path(dest).rglob("exams.json")
                   if (p.parent / "task2_error_taxonomy.json").exists() and "__MACOSX" not in p.parts),
                  key=lambda p: len(p.parts))
    if not hits:
        raise FileNotFoundError(f"no exams.json + task2_error_taxonomy.json under {dest}")
    return hits[0]


def download(drive_id: str, out_path) -> Path:
    """Download a Google Drive file (gdown when installed, else the direct-download URL; fine for small files)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import gdown
    except ImportError:
        gdown = None
    if gdown is not None:
        if gdown.download(id=drive_id, output=str(out_path), quiet=False) is None:
            raise RuntimeError("gdown failed: check the Drive id and that the file is shared 'anyone with the link'")
    else:
        url = f"https://drive.google.com/uc?export=download&id={drive_id}"
        with urllib.request.urlopen(url, timeout=120) as r, out_path.open("wb") as f:
            shutil.copyfileobj(r, f)
    if not zipfile.is_zipfile(out_path):
        out_path.unlink(missing_ok=True)
        raise RuntimeError("downloaded file is not a zip: check the Drive id and sharing permissions")
    return out_path


def fetch_synth(dest_dir=DEFAULT_DIR, drive_id: str | None = None, force: bool = False) -> Path:
    """Folder with the silver set (exams.json, task2_error_taxonomy.json, submissions/, heldout/)."""
    dest_dir = Path(dest_dir)
    zip_path = dest_dir / ZIP_NAME
    folder = dest_dir / Path(ZIP_NAME).stem
    if not force and (folder / "exams.json").exists():
        return folder
    if force or not zip_path.exists():
        drive_id = drive_id or os.environ.get(ENV_VAR, "")
        if not drive_id:
            raise SystemExit(f"Không thấy {zip_path}. Đặt {ENV_VAR} (biến môi trường, .env hoặc Kaggle secret) "
                             "hoặc truyền --drive-id để tải từ Google Drive.")
        download(drive_id, zip_path)
    if force and folder.exists():
        shutil.rmtree(folder)
    return extract(zip_path, dest_dir)


def silver_roots(dest_dir=DEFAULT_DIR, drive_id: str | None = None) -> dict[str, Path]:
    root = fetch_synth(dest_dir, drive_id)
    return {"silver": root, "heldout": root / "heldout"}
