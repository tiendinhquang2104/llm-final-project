"""Privacy-safe reproducibility metadata; never log prompts or environment secrets."""

from __future__ import annotations

import hashlib
import platform
import subprocess
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path


def runtime_manifest(config, tokenizer=None, *, backend=None):
    packages = {}
    for package in (
        "torch",
        "transformers",
        "accelerate",
        "datasets",
        "peft",
        "trl",
        "bitsandbytes",
        "tokenizers",
        "pyyaml",
    ):
        try:
            packages[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            packages[package] = "not installed"
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except subprocess.CalledProcessError:
        commit = None
    device = {"device": "CPU", "cuda": False, "gpu_memory_bytes": None}
    if packages["torch"] != "not installed":
        import torch

        if torch.cuda.is_available():
            device = {
                "device": torch.cuda.get_device_name(),
                "cuda": True,
                "gpu_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
                "cuda_version": torch.version.cuda,
            }
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "git_commit": commit,
        "implementation_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*.py"))
        },
        "config": config,
        **device,
    }
    result["inference_precision"] = {
        "requested_precision": "nf4" if config.get("load_in_4bit", True) else "bf16",
        **(backend.runtime_metadata() if backend is not None and hasattr(backend, "runtime_metadata") else {"actual_precision": "not_measured"}),
    }
    if tokenizer is not None:
        from src.task3.inference import tokenizer_metadata

        result["tokenizer"] = tokenizer_metadata(tokenizer)
    return result
