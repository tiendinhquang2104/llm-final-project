"""Report local CUDA and bounded bitsandbytes NF4/LoRA execution capability."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from importlib import metadata
from pathlib import Path

from src.task3.dataset import write_json

_PACKAGES = ("torch", "transformers", "peft", "bitsandbytes", "accelerate")


def _nvidia_smi():
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=10,
        )
        devices = []
        for line in output.splitlines():
            fields = [field.strip() for field in line.split(",")]
            if len(fields) == 4:
                devices.append(
                    {
                        "name": fields[0],
                        "driver_version": fields[1],
                        "memory_total_mib": int(fields[2]),
                        "memory_free_mib": int(fields[3]),
                    }
                )
        return {"status": "available", "devices": devices}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"status": "failed", "error_type": type(exc).__name__}


def gpu_workload_status():
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=10,
        )
        external = []
        for line in output.splitlines():
            fields = [field.strip() for field in line.split(",")]
            if len(fields) != 2:
                raise ValueError("unexpected nvidia-smi process output")
            pid = int(fields[0])
            used_memory = 0 if fields[1] in {"N/A", "[N/A]"} else int(fields[1])
            if pid != os.getpid():
                external.append(used_memory)
        return {
            "status": "available",
            "external_process_count": len(external),
            "external_memory_mib": sum(external),
        }
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"status": "failed", "error_type": type(exc).__name__}


def _version(package):
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "not installed"


def _failure(exc):
    return {"status": "failed", "error_type": type(exc).__name__, "message": str(exc)[:500]}


def collect_preflight(smoke_4bit=False):
    report = {
        "status": "failed",
        "python": platform.python_version(),
        "platform": platform.system(),
        "packages": {package: _version(package) for package in _PACKAGES},
        "nvidia_smi": _nvidia_smi(),
        "cuda": {
            "available": False,
            "device_count": 0,
            "devices": [],
            "matmul": {"status": "not_run"},
            "bf16_supported": False,
            "supported_precisions": ["fp32"],
            "nf4_lora_smoke": {"status": "not_requested" if not smoke_4bit else "not_run"},
        },
        "checks": {
            "cuda_matmul": "not_run",
            "nf4_lora_forward_backward_update": "not_requested" if not smoke_4bit else "not_run",
        },
    }
    try:
        import torch
    except ImportError as exc:
        report["cuda"]["torch_import"] = _failure(exc)
        return report
    report["torch"] = {
        "version": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "compiled_architectures": torch.cuda.get_arch_list(),
    }
    report["cuda"]["available"] = bool(torch.cuda.is_available())
    report["cuda"]["device_count"] = torch.cuda.device_count()
    if torch.cuda.is_available():
        for index in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(index)
            report["cuda"]["devices"].append(
                {
                    "index": index,
                    "name": props.name,
                    "capability": list(torch.cuda.get_device_capability(index)),
                    "total_memory_bytes": props.total_memory,
                }
            )
        report["cuda"]["selected_device"] = torch.cuda.get_device_name(0)
        report["cuda"]["bf16_supported"] = bool(torch.cuda.is_bf16_supported())
        report["cuda"]["supported_precisions"] = ["fp32", "fp16"] + (
            ["bf16"] if report["cuda"]["bf16_supported"] else []
        )
        free_bytes, total_bytes = torch.cuda.mem_get_info()
        workload = gpu_workload_status()
        report["cuda"]["free_memory_bytes"] = int(free_bytes)
        report["cuda"]["total_memory_bytes"] = int(total_bytes)
        report["cuda"]["workload_isolation"] = workload
        if workload["status"] != "available" or workload["external_process_count"] or free_bytes < 1024**3:
            reason = (
                "workload_check_failed"
                if workload["status"] != "available"
                else "competing_gpu_workload"
                if workload["external_process_count"]
                else "insufficient_free_vram"
            )
            report["cuda"]["matmul"] = {"status": "not_run", "reason": reason}
            report["checks"]["cuda_matmul"] = "not_run"
            if smoke_4bit:
                outcome = {"status": "not_run", "reason": reason}
                report["cuda"]["nf4_lora_smoke"] = outcome
                report["checks"]["nf4_lora_forward_backward_update"] = "not_run"
            return report
        try:
            device = torch.device("cuda:0")
            left = torch.randn((16, 16), device=device, requires_grad=True)
            right = torch.randn((16, 16), device=device, requires_grad=True)
            loss = (left @ right).square().mean()
            loss.backward()
            torch.cuda.synchronize(device)
            report["cuda"]["matmul"] = {"status": "passed"}
            report["checks"]["cuda_matmul"] = "passed"
        except Exception as exc:
            report["cuda"]["matmul"] = _failure(exc)
            report["checks"]["cuda_matmul"] = "failed"
    else:
        report["cuda"]["matmul"] = {"status": "failed", "error_type": "CudaUnavailable"}
        report["checks"]["cuda_matmul"] = "failed"

    if smoke_4bit:
        if not torch.cuda.is_available():
            outcome = {"status": "failed", "error_type": "CudaUnavailable"}
        elif report["packages"]["bitsandbytes"] == "not installed":
            outcome = {"status": "failed", "error_type": "BitsAndBytesNotInstalled"}
        else:
            try:
                import bitsandbytes as bnb

                device = torch.device("cuda:0")
                dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                base = bnb.nn.Linear4bit(
                    8,
                    8,
                    bias=False,
                    compute_dtype=dtype,
                    compress_statistics=True,
                    quant_type="nf4",
                ).to(device)
                lora_a = torch.nn.Parameter(torch.randn((8, 2), device=device, dtype=dtype) * 0.01)
                lora_b = torch.nn.Parameter(torch.randn((2, 8), device=device, dtype=dtype) * 0.01)
                optimizer = torch.optim.AdamW((lora_a, lora_b), lr=1e-3)
                source = torch.randn((2, 8), device=device, dtype=dtype)
                optimizer.zero_grad(set_to_none=True)
                output = base(source) + (source @ lora_a @ lora_b)
                loss = output.float().square().mean()
                loss.backward()
                gradients_ok = all(
                    parameter.grad is not None
                    and bool(torch.isfinite(parameter.grad).all())
                    and bool(torch.count_nonzero(parameter.grad))
                    for parameter in (lora_a, lora_b)
                )
                if not bool(torch.isfinite(loss)) or not gradients_ok:
                    raise RuntimeError("NF4/LoRA smoke produced non-finite loss or empty gradients")
                lora_before = [parameter.detach().clone() for parameter in (lora_a, lora_b)]
                optimizer.step()
                torch.cuda.synchronize(device)
                deltas = [
                    (parameter.detach() - before).abs()
                    for parameter, before in zip((lora_a, lora_b), lora_before)
                ]
                update_ok = all(bool(torch.isfinite(delta).all()) for delta in deltas) and any(
                    bool(torch.count_nonzero(delta)) for delta in deltas
                )
                if not update_ok:
                    raise RuntimeError("NF4/LoRA smoke produced no finite nonzero parameter update")
                outcome = {
                    "status": "passed",
                    "loss_finite": True,
                    "lora_gradients_finite_nonzero": True,
                    "lora_parameter_update_finite_nonzero": True,
                    "optimizer_update": "passed",
                    "trainable_parameters": int(lora_a.numel() + lora_b.numel()),
                    "base_parameters_frozen": not base.weight.requires_grad,
                }
            except Exception as exc:
                outcome = _failure(exc)
        report["cuda"]["nf4_lora_smoke"] = outcome
        report["checks"]["nf4_lora_forward_backward_update"] = outcome["status"]
    required = ["cuda_matmul"]
    if smoke_4bit:
        required.append("nf4_lora_forward_backward_update")
    report["status"] = "passed" if all(report["checks"][key] == "passed" for key in required) else "failed"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Task 3 CUDA/RTX 5090 compatibility preflight")
    parser.add_argument("--smoke-4bit", action="store_true", help="run a tiny NF4 + trainable LoRA CUDA update")
    parser.add_argument("--output", default="outputs/task3/gpu-preflight.json")
    args = parser.parse_args(argv)
    result = collect_preflight(smoke_4bit=args.smoke_4bit)
    write_json(args.output, result)
    print(json.dumps({"status": result["status"], "report": str(Path(args.output))}, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
