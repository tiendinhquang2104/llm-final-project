import os

import pytest

from src.task3.gpu_preflight import collect_preflight


def test_preflight_is_machine_readable_without_hardware_execution(monkeypatch):
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 0)
    report = collect_preflight(smoke_4bit=False)
    assert report["python"]
    assert set(report["packages"]) == {"torch", "transformers", "peft", "bitsandbytes", "accelerate"}
    assert report["cuda"]["nf4_lora_smoke"]["status"] == "not_requested"
    assert report["checks"]["nf4_lora_forward_backward_update"] == "not_requested"
    assert report["cuda"]["matmul"]["status"] == "failed"


@pytest.mark.skipif(
    os.environ.get("TASK3_RUN_GPU_TESTS") != "1",
    reason="opt-in local CUDA test; offline unit tests must not imply real GPU execution",
)
def test_opt_in_real_nf4_lora_cuda_update():
    report = collect_preflight(smoke_4bit=True)
    assert report["cuda"]["available"]
    assert report["cuda"]["matmul"]["status"] == "passed"
    assert report["cuda"]["nf4_lora_smoke"]["status"] == "passed", report["cuda"]["nf4_lora_smoke"]
