"""Build a copy of the public test release whose task files carry a pre-filled `compile_log`.

Everything is copied byte-for-byte except `compile_log` of every sample in the task files; the result zips with a
single root folder `public_test_release/` (same layout as the original, so scripts/unpack_data.py works unchanged).
"""
from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

# files whose samples get a compile_log (grading, taxonomy and feedback share the sample schema)
TASK_FILES = ("task1_grading.json", "task2_error_taxonomy.json", "task3_feedback.json")


def _rewrite(raw: bytes, logs: dict[str, str], name: str) -> bytes:
    text = raw.decode("utf-8")
    bom = text.startswith("﻿")
    text = text.lstrip("﻿")
    newline = "\r\n" if "\r\n" in text else "\n"
    m = re.search(r"^([ \t]+)\S", text.replace("\r\n", "\n"), re.MULTILINE)
    indent = len(m.group(1)) if m and m.group(1).isspace() and "\t" not in m.group(1) else 2
    payload = json.loads(text)
    missing = [s["sample_id"] for s in payload["samples"] if s["sample_id"] not in logs]
    if missing:
        raise KeyError(f"{name}: no compile log for {len(missing)} samples, e.g. {missing[:3]}")
    for s in payload["samples"]:
        s["input"]["compile_log"] = logs[s["sample_id"]]
    out = json.dumps(payload, ensure_ascii=False, indent=indent).replace("\n", newline)
    if text.endswith(newline):
        out += newline
    return (("﻿" if bom else "") + out).encode("utf-8")


def build_compiled_dataset(src, out, logs: dict[str, str], make_zip: bool = True) -> Path:
    """Copy `src` to `<out>/public_test_release/` with compile_log filled from `logs`; return that folder.

    Raises KeyError (before writing anything) if a sample of a task file has no entry in `logs`."""
    src, out = Path(src), Path(out)
    rewritten = {n: _rewrite((src / n).read_bytes(), logs, n) for n in TASK_FILES if (src / n).exists()}
    dst = out / "public_test_release"
    shutil.rmtree(dst, ignore_errors=True)
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = f.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if len(rel.parts) == 1 and rel.name in rewritten:
            target.write_bytes(rewritten[rel.name])
        else:
            shutil.copyfile(f, target)
    if make_zip:
        zpath = out / "public_test_release.zip"
        zpath.unlink(missing_ok=True)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(p for p in dst.rglob("*") if p.is_file()):
                zf.write(f, Path("public_test_release") / f.relative_to(dst))
    return dst
