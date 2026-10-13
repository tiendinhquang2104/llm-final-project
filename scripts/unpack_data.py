"""Extract the competition zips (public_test_release.zip, sample_dataset.zip) into data/raw/.

Accepts the zips themselves, a folder containing them, or the download bundle zip that wraps them.
"""
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

KNOWN = ("public_test_release.zip", "sample_dataset.zip")
KNOWN_DIRS = ("public_test_release", "sample_dataset")


def unpack(src: Path, dest: Path) -> list[Path]:
    src, dest = Path(src), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []

    # 1. Check if known folders are already unzipped (e.g. Kaggle Datasets auto-unzip)
    if src.is_dir():
        for dname in KNOWN_DIRS:
            target = dest / dname
            if target.exists():
                out.append(target)
                continue
            for fd in src.rglob(dname):
                if fd.is_dir() and fd.resolve() != target.resolve():
                    shutil.copytree(fd, target)
                    out.append(target)
                    break

    # 2. Check for zip files
    zips = [src] if src.is_file() else sorted(src.rglob("*.zip"))
    for z in zips:
        if z.name in KNOWN:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest)
            out.append(dest / z.stem)
            continue
        with zipfile.ZipFile(z) as zf:  # bundle: pull out the known inner zips
            inner = [n for n in zf.namelist() if Path(n).name in KNOWN]
            if not inner:
                continue
            tmp = dest / ".bundle"
            for name in inner:
                zf.extract(name, tmp)
                out += unpack(tmp / name, dest)
            shutil.rmtree(tmp, ignore_errors=True)
    return sorted(set(out))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", help="zip file or folder with zips (e.g. data/public-test)")
    ap.add_argument("--dest", default="data/raw")
    a = ap.parse_args()
    for p in unpack(Path(a.src), Path(a.dest)):
        print(p)


if __name__ == "__main__":
    main()
