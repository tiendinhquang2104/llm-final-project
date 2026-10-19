"""Create a labelled sample ZIP with compiler diagnostics added to every task input.

The original ZIP and all teacher labels are left untouched. Compile-only (-c)
avoids a false missing-main error for function submissions and never runs code.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


TASK_FILES = ("task1_grading.json", "task2_error_taxonomy.json", "task3_feedback.json")
FLAGS = ("-std=c++11", "-c", "student.cpp", "-o", "student.o", "-fmax-errors=3")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compile_code(item: tuple[str, bytes], compiler: str, timeout: int) -> dict:
    sample_id, code = item
    with tempfile.TemporaryDirectory(prefix="task1-compile-") as temporary:
        work = Path(temporary)
        (work / "student.cpp").write_bytes(code)
        try:
            result = subprocess.run(
                [compiler, *FLAGS], cwd=work, capture_output=True, timeout=timeout, check=False,
                env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Compiler timed out for {sample_id} after {timeout}s") from exc
    return {
        "sample_id": sample_id,
        "compile_ok": result.returncode == 0,
        "returncode": result.returncode,
        "compile_log": result.stderr.decode("utf-8", errors="replace"),
        "code_sha256": digest(code),
    }


def build(source: Path, output: Path, manifest_path: Path, compiler: str, workers: int, timeout: int) -> dict:
    with zipfile.ZipFile(source) as source_zip:
        if "sample_dataset.zip" in source_zip.namelist():
            sample_bytes = source_zip.read("sample_dataset.zip")
        else:
            sample_bytes = source.read_bytes()
    with zipfile.ZipFile(io.BytesIO(sample_bytes)) as sample_zip:
        names = sample_zip.namelist()
        grading_name = next((n for n in names if n.endswith("/task1_grading.json")), None)
        if grading_name is None:
            raise ValueError("sample_dataset.zip lacks task1_grading.json")
        root = grading_name[: -len("task1_grading.json")]
        task_names = {name: root + name for name in TASK_FILES}
        if any(name not in names for name in task_names.values()):
            raise ValueError("sample_dataset.zip lacks a task label file")
        documents = {short: json.loads(sample_zip.read(full)) for short, full in task_names.items()}
        grading = documents["task1_grading.json"]["samples"]
        ids = [row["sample_id"] for row in grading]
        if len(ids) != 32 or len(set(ids)) != 32:
            raise ValueError(f"Expected 32 unique gold sample IDs, got {len(ids)} records")
        code_items = []
        for row in grading:
            code_name = root + row["input"]["code_file"]
            if code_name not in names:
                raise FileNotFoundError(code_name)
            code_items.append((row["sample_id"], sample_zip.read(code_name)))

        version = subprocess.run([compiler, "--version"], capture_output=True, text=True, check=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            compiled = list(pool.map(lambda item: compile_code(item, compiler, timeout), code_items))
        by_id = {row["sample_id"]: row for row in compiled}

        updated_bytes = {}
        for short, document in documents.items():
            rows = document["samples"]
            if len(rows) != 32 or {row["sample_id"] for row in rows} != set(ids):
                raise ValueError(f"Sample IDs differ in {short}")
            old_outputs = {row["sample_id"]: row["output"] for row in rows}
            for row in rows:
                row["input"]["compile_log"] = by_id[row["sample_id"]]["compile_log"]
            if old_outputs != {row["sample_id"]: row["output"] for row in rows}:
                raise AssertionError(f"Teacher labels changed in {short}")
            updated_bytes[task_names[short]] = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

        output.parent.mkdir(parents=True, exist_ok=True)
        temporary_output = output.with_name(output.name + ".tmp")
        try:
            with zipfile.ZipFile(temporary_output, "w") as target:
                for member in sample_zip.infolist():
                    target.writestr(member, updated_bytes.get(member.filename, sample_zip.read(member)))
            with zipfile.ZipFile(temporary_output) as verify:
                if verify.testzip() is not None:
                    raise ValueError("Derived sample ZIP failed integrity check")
            temporary_output.replace(output)
        finally:
            temporary_output.unlink(missing_ok=True)

    manifest = {
        "source_file": str(source),
        "source_sha256": digest(source.read_bytes()),
        "source_sample_zip_sha256": digest(sample_bytes),
        "output_file": str(output),
        "output_sha256": digest(output.read_bytes()),
        "compiler": version.stdout.splitlines()[0],
        "compiler_flags": list(FLAGS),
        "compile_only_no_link_or_execution": True,
        "n_samples": len(compiled),
        "n_compiled": sum(row["compile_ok"] for row in compiled),
        "n_failed": sum(not row["compile_ok"] for row in compiled),
        "results": [
            {key: value for key, value in row.items() if key != "compile_log"}
            | {"compile_log_sha256": digest(row["compile_log"].encode("utf-8"))}
            for row in compiled
        ],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Outer ZIP or sample_dataset.zip")
    parser.add_argument("--output", type=Path, required=True, help="Derived sample_dataset ZIP")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    if args.workers < 1 or args.timeout < 1:
        parser.error("workers and timeout must be positive")
    result = build(args.source, args.output, args.manifest, args.compiler, args.workers, args.timeout)
    print(json.dumps({key: result[key] for key in ("output_file", "output_sha256", "n_samples", "n_compiled", "n_failed")}, indent=2))


if __name__ == "__main__":
    main()
