import json
from pathlib import Path

import pytest

from src.task3.inference import MockTokenizer
from src.task3.prompts import ContextTooLong
from src.task3.train import (
    _audit_lora_parameter_updates,
    _checkpoint_metadata,
    _session_throughput,
    _training_gpu_preflight,
    encode_completion,
    sample_training_rows,
    sequence_audit,
    tokenize_records,
    validate_resume_checkpoint,
)
from tests.test_task3_dataset import record


def test_loss_masks_every_input_and_preserves_full_target():
    tokenizer = MockTokenizer()
    prompt = [{"role": "system", "content": "TEST instructions"}, {"role": "user", "content": "TEST private code"}]
    completion = "TEST phản hồi học tập."
    encoded = encode_completion(tokenizer, prompt, completion, 10000)
    prefix = tokenizer.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(
        prompt + [{"role": "assistant", "content": completion}], tokenize=True, add_generation_prompt=False
    )
    assert encoded["input_ids"] == full
    assert encoded["labels"][: len(prefix)] == [-100] * len(prefix)
    assert encoded["labels"][len(prefix) :] == full[len(prefix) :]
    assert bytes(encoded["input_ids"][len(prefix) :]).decode().startswith(completion)


def test_smoke_update_audit_allows_zero_warmup_step_before_lora_update():
    torch = pytest.importorskip("torch")

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lora_weight = torch.nn.Parameter(torch.tensor([1.0]))

    model = Model()
    before = {"lora_weight": model.lora_weight.detach().clone()}
    with torch.no_grad():
        model.lora_weight.add_(0.0)
        model.lora_weight.add_(0.25)

    result = _audit_lora_parameter_updates(before, model)

    assert result == {
        "checked": True,
        "finite_nonzero_lora_update": True,
        "max_abs_delta": 0.25,
    }


def test_incompatible_template_rejected():
    class Incompatible(MockTokenizer):
        def apply_chat_template(self, messages, **kwargs):
            return [0 if messages[-1]["role"] == "assistant" else 1] + super().apply_chat_template(messages, **kwargs)

    with pytest.raises(ValueError, match="prefix-stable"):
        encode_completion(Incompatible(), [{"role": "user", "content": "TEST"}], "target", 10000)


def test_target_never_silently_truncated():
    with pytest.raises(ContextTooLong):
        encode_completion(MockTokenizer(), [{"role": "user", "content": "TEST"}], "target" * 200, 100)
    with pytest.raises(ContextTooLong):
        tokenize_records([record(gold_feedback="target" * 2000)], MockTokenizer(), 2048)


def test_sequence_length_selected_from_audit():
    result = sequence_audit([record()], MockTokenizer())
    assert result["selected"] in (2048, 4096)
    assert result["tokenizer"]["mock"]
    result = sequence_audit([record(code="TEST" * 5000)], MockTokenizer())
    assert result["selected"] is None
    assert result["candidates"]["4096"]["overlength_ids"] == ["TEST-A"]


def test_collator_masks_padding_and_preserves_targets():
    pytest.importorskip("torch")
    from src.task3.train import CompletionCollator

    rows = [
        {"input_ids": [1, 2, 3], "labels": [-100, 2, 3], "attention_mask": [1, 1, 1]},
        {"input_ids": [4, 5], "labels": [-100, 5], "attention_mask": [1, 1]},
    ]
    batch = CompletionCollator(0)(rows)
    assert batch["labels"].tolist() == [[-100, 2, 3], [-100, 5, -100]]
    assert batch["attention_mask"].tolist() == [[1, 1, 1], [1, 1, 0]]


def test_balanced_source_sampling_is_deterministic_and_logs_exposures():
    records = [record(f"REAL-{index}", source="real") for index in range(40)]
    records.extend(record(f"SYN-{index}", source="synthetic") for index in range(160))
    rows = [{"input_ids": [index], "labels": [-100], "attention_mask": [1]} for index in range(len(records))]
    first, exposures = sample_training_rows(rows, records, {"real": 0.75, "synthetic": 0.25}, seed=42)
    second, repeated = sample_training_rows(rows, records, {"real": 0.75, "synthetic": 0.25}, seed=42)
    assert [row["input_ids"] for row in first] == [row["input_ids"] for row in second]
    assert exposures == repeated
    assert 125 <= exposures["real"] <= 175
    assert 25 <= exposures["synthetic"] <= 75


def test_resume_requires_full_compatible_trainer_checkpoint(tmp_path):
    metadata = _checkpoint_metadata(
        {"model_id": "TEST-model", "revision": "TEST-rev", "experiment": "mixed_uniform"},
        "TEST-manifest",
    )
    adapter_only = tmp_path / "adapter"
    adapter_only.mkdir()
    with pytest.raises(ValueError, match="complete Trainer checkpoint"):
        validate_resume_checkpoint(adapter_only, metadata)
    checkpoint = tmp_path / "checkpoint-10"
    checkpoint.mkdir()
    for name in ("optimizer.pt", "scheduler.pt", "rng_state.pth"):
        (checkpoint / name).write_bytes(b"TEST")
    (checkpoint / "adapter_model.safetensors").write_bytes(b"TEST weights")
    (checkpoint / "trainer_state.json").write_text(json.dumps({"global_step": 10}), encoding="utf-8")
    from src.task3.dataset import write_json

    write_json(checkpoint / "task3_resume_metadata.json", metadata)
    assert validate_resume_checkpoint(checkpoint, metadata) == 10
    with pytest.raises(ValueError, match="incompatible"):
        validate_resume_checkpoint(checkpoint, {**metadata, "data_manifest_sha256": "OTHER"})


def test_session_throughput_uses_only_steps_and_timing_from_resumed_session():
    result = _session_throughput(
        final_step=100,
        resume_start_step=90,
        step_times=[2.0] * 10,
        samples_per_step=4,
        tokens_per_sample=50,
    )
    assert result == {
        "cumulative_optimizer_steps": 100,
        "session_optimizer_steps": 10,
        "session_samples_per_second": 2.0,
        "session_supervised_tokens_per_second": 100.0,
        "session_optimizer_step_wall_time_s": 20.0,
    }


def test_runtime_gpu_preflight_honors_single_device_bf16_vram_and_workload_safety(monkeypatch):
    from types import SimpleNamespace

    import src.task3.gpu_preflight as preflight

    class FakeCuda:
        device_count = staticmethod(lambda: 1)
        current_device = staticmethod(lambda: 0)
        get_device_name = staticmethod(lambda device: "NVIDIA GeForce RTX 5090")
        is_bf16_supported = staticmethod(lambda: True)
        mem_get_info = staticmethod(lambda device=None: (28 * 1024**3, 32 * 1024**3))
        is_available = staticmethod(lambda: True)

    fake_torch = SimpleNamespace(cuda=FakeCuda())
    monkeypatch.setattr(
        preflight,
        "gpu_workload_status",
        lambda: {"status": "available", "external_process_count": 0, "external_memory_mib": 0},
    )
    result = _training_gpu_preflight(
        fake_torch,
        {
            "single_gpu": True,
            "expected_gpu_name": "NVIDIA GeForce RTX 5090",
            "require_bf16": True,
            "min_free_vram_gib": 24,
        },
    )
    assert result["selected_device"] == 0
    assert result["bf16_supported"]
    assert result["free_vram_bytes"] == 28 * 1024**3

    monkeypatch.setattr(
        preflight,
        "gpu_workload_status",
        lambda: {"status": "available", "external_process_count": 1, "external_memory_mib": 1024},
    )
    with pytest.raises(RuntimeError, match="another GPU workload"):
        _training_gpu_preflight(fake_torch, {"single_gpu": True})

    monkeypatch.setattr(FakeCuda, "device_count", staticmethod(lambda: 2))
    with pytest.raises(RuntimeError, match="exactly one visible"):
        _training_gpu_preflight(fake_torch, {"single_gpu": True})


def test_staged_dispatch_applies_stage2_learning_rate_and_budgets(tmp_path, monkeypatch):
    import yaml

    import src.task3.train as training
    from tests.test_task3_cli import fixture_prepared

    _, config_path = fixture_prepared(tmp_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config.update(
        experiment="staged",
        output_dir=str(tmp_path / "staged-checkpoint"),
        stage1_fraction=0.75,
        stage2_learning_rate=1e-5,
    )
    data_dir = Path(config["data_dir"])
    synthetic_path = data_dir / "synthetic-train.jsonl"
    import hashlib
    from dataclasses import asdict

    from src.task3.dataset import read_json, write_json

    synthetic_path.write_text(
        json.dumps({"record": asdict(record("TEST-ONLY-SYNTH", source="synthetic", group_key="synth"))}) + "\n",
        encoding="utf-8",
    )
    manifest = read_json(data_dir / "manifest.json")
    manifest["processed_sha256"][synthetic_path.name] = hashlib.sha256(synthetic_path.read_bytes()).hexdigest()
    write_json(data_dir / "manifest.json", manifest)

    calls = []

    def stage_stub(stage_config, *, max_steps):
        calls.append((stage_config, max_steps))
        return {
            "status": "COMPLETE",
            "optimizer_steps": max_steps,
            "checkpoint_path": str(Path(stage_config["output_dir"]) / "adapter"),
        }

    original = training.run_training
    monkeypatch.setattr(training, "run_training", stage_stub)
    result = original(config, max_steps=8)

    assert [steps for _, steps in calls] == [6, 2]
    assert calls[0][0]["experiment"] == "synthetic"
    assert calls[1][0]["experiment"] == "real"
    assert calls[1][0]["learning_rate"] == 1e-5
    assert calls[1][0]["stage_name"] == "real-adaptation-fresh-optimizer"
    assert result["status"] == "COMPLETE"
    assert result["optimizer_steps"] == 8


def test_real_qwen_template_masking_when_tokenizer_cached():
    """Offline-only optional integration; never downloads or reads private data."""
    transformers = pytest.importorskip("transformers")
    try:
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            "Qwen/Qwen2.5-Coder-7B-Instruct",
            revision="c03e6d358207e414f1eca0bb1891e29f1db0e242",
            local_files_only=True,
        )
    except OSError:
        pytest.skip("pinned Qwen tokenizer not cached")
    prompt = [{"role": "system", "content": "TEST ONLY"}, {"role": "user", "content": "TEST code"}]
    completion = "Em tự kiểm tra lại nhé."
    row = encode_completion(tokenizer, prompt, completion, 2048)
    prefix = tokenizer.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True)
    assert row["labels"][: len(prefix)] == [-100] * len(prefix)
    assert tokenizer.decode([v for v in row["labels"] if v != -100]).startswith(completion)
    assert tokenizer.eos_token_id in row["labels"][len(prefix) :]


def test_mocked_cuda_qlora_dispatch_and_logging(tmp_path, monkeypatch):
    """Exercise the entire training dispatch with mocked CUDA/model/Trainer; no weights loaded."""
    from types import SimpleNamespace

    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    peft = pytest.importorskip("peft")
    pytest.importorskip("datasets")
    from src.task3.dataset import read_json
    from src.task3.train import run_training
    from tests.test_task3_cli import fixture_prepared

    _, config_path = fixture_prepared(tmp_path)
    import yaml

    config = yaml.safe_load(config_path.read_text())
    config.update(single_gpu=True, expected_gpu_name="NVIDIA GeForce RTX 5090", require_bf16=True, min_free_vram_gib=24)
    observed = {}
    tokenizer = MockTokenizer()
    tokenizer.save_pretrained = lambda path: observed.update(tokenizer_saved=str(path))
    monkeypatch.setattr("src.task3.train.load_tokenizer", lambda cfg: tokenizer)
    monkeypatch.setattr("src.task3.train.runtime_manifest", lambda cfg: {"config": cfg, "TEST_ONLY": True})
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 1)
    monkeypatch.setattr(torch.cuda, "get_device_name", lambda device: "NVIDIA GeForce RTX 5090")
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: True)
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 0)
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda: None)
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda: 1234)
    monkeypatch.setattr(torch.cuda, "max_memory_reserved", lambda: 2345)
    monkeypatch.setattr(torch.cuda, "mem_get_info", lambda device=None: (30 * 1024**3, 32 * 1024**3))
    monkeypatch.setattr(torch.cuda, "synchronize", lambda *args, **kwargs: None)
    monkeypatch.setattr(transformers, "set_seed", lambda seed: observed.update(seed=seed))
    monkeypatch.setattr(
        "src.task3.gpu_preflight.gpu_workload_status",
        lambda: {"status": "available", "external_process_count": 0, "external_memory_mib": 0},
    )

    def quant(**kw):
        observed["quant"] = kw
        return SimpleNamespace(**kw)

    monkeypatch.setattr(transformers, "BitsAndBytesConfig", quant)

    def model_load(*args, **kw):
        observed["model"] = kw

        class FakeModel:
            config = SimpleNamespace(use_cache=True)

            def parameters(self):
                return iter(())

            def named_parameters(self):
                return iter(())

        return FakeModel()

    monkeypatch.setattr(transformers.AutoModelForCausalLM, "from_pretrained", model_load)
    monkeypatch.setattr(peft, "prepare_model_for_kbit_training", lambda model, **kw: model)

    def attach_lora(model, lora):
        observed["lora"] = lora
        return model

    monkeypatch.setattr(peft, "get_peft_model", attach_lora)
    monkeypatch.setattr(transformers, "TrainingArguments", lambda **kw: SimpleNamespace(**kw))

    class FakeTrainer:
        state = SimpleNamespace(log_history=[{"loss": 1.0}, {"eval_loss": 1.1}], global_step=2)

        def __init__(self, **kw):
            observed["trainer"] = kw

        def train(self, **kwargs):
            return SimpleNamespace(metrics={"train_loss": 1.0})

        def evaluate(self):
            return {"eval_loss": 1.1}

        def save_model(self, path):
            observed["saved"] = path

    import sys

    # Replace lazy import namespaces so later Transformers re-exports cannot undo patches.
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoModelForCausalLM=SimpleNamespace(from_pretrained=model_load),
            BitsAndBytesConfig=quant,
            Trainer=FakeTrainer,
            TrainerCallback=transformers.TrainerCallback,
            TrainingArguments=lambda **kw: SimpleNamespace(**kw),
            set_seed=lambda seed: observed.update(seed=seed),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "peft",
        SimpleNamespace(
            LoraConfig=peft.LoraConfig,
            PeftModel=peft.PeftModel,
            get_peft_model=attach_lora,
            prepare_model_for_kbit_training=lambda model, **kw: model,
        ),
    )
    monkeypatch.setitem(sys.modules, "datasets", SimpleNamespace(Dataset=SimpleNamespace(from_list=lambda rows: rows)))
    result = run_training(config, max_steps=10)
    assert observed["quant"]["bnb_4bit_quant_type"] == "nf4"
    assert observed["quant"]["bnb_4bit_use_double_quant"] is True
    assert observed["lora"].r == 16
    assert observed["trainer"]["args"].report_to == []
    assert observed["trainer"]["args"].max_steps == 10
    labels = observed["trainer"]["train_dataset"][0]["labels"]
    assert labels[0] == -100 and labels[-1] != -100
    assert result["status"] == "COMPLETE"  # mocked dispatch only, not GPU execution
    logged = read_json(tmp_path / "checkpoint/run.json")
    assert logged["TEST_ONLY"] is True
    assert logged["precision"] == "bf16"
    assert logged["peak_gpu_memory_allocated_bytes"] == 1234


def test_no_cuda_training_stops_before_model_loading(tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    import yaml

    from src.task3.train import run_training
    from tests.test_task3_cli import fixture_prepared

    _, path = fixture_prepared(tmp_path)
    config = yaml.safe_load(path.read_text())
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(
        "src.task3.train.load_tokenizer", lambda cfg: pytest.fail("must not download tokenizer without CUDA")
    )
    with pytest.raises(RuntimeError, match="CUDA unavailable"):
        run_training(config)


def _staged_fixture(tmp_path):
    import hashlib
    from dataclasses import asdict

    import yaml

    from src.task3.dataset import read_json, write_json
    from tests.test_task3_cli import fixture_prepared

    data, config_path = fixture_prepared(tmp_path)
    synthetic = [record("TEST-ONLY-SYNTH", source="synthetic", split="synthetic-train", group_key="synthetic")]
    (data / "synthetic-train.jsonl").write_text(
        "".join(json.dumps({"record": asdict(item)}, ensure_ascii=False) + "\n" for item in synthetic),
        encoding="utf-8",
    )
    manifest = read_json(data / "manifest.json")
    manifest["processed_sha256"]["synthetic-train.jsonl"] = hashlib.sha256(
        (data / "synthetic-train.jsonl").read_bytes()
    ).hexdigest()
    write_json(data / "manifest.json", manifest)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["experiment"] = "staged"
    config["stage1_fraction"] = 0.75
    return data, config_path, config


@pytest.mark.parametrize(("mode", "expected_status"), [("dry", "DRY RUN"), ("audit", "AUDIT ONLY")])
def test_staged_nontraining_modes_never_recurse_or_start_training(
    tmp_path, monkeypatch, mode, expected_status
):
    import sys
    from types import SimpleNamespace

    import src.task3.train as training

    _, _, config = _staged_fixture(tmp_path)
    config["output_dir"] = str(tmp_path / "staged-checkpoint")
    original_run_training = training.run_training
    nested_calls = []

    def forbid_nested_training(*args, **kwargs):
        nested_calls.append((args, kwargs))
        raise AssertionError("staged dry-run/audit must not recurse into training")

    def forbidden(*args, **kwargs):
        raise AssertionError("non-training modes must not enter model, Trainer, or optimizer execution")

    class FakeOptimizer:
        step = forbidden

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: True, is_bf16_supported=forbidden),
            optim=SimpleNamespace(Optimizer=FakeOptimizer),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoModelForCausalLM=SimpleNamespace(from_pretrained=forbidden),
            Trainer=forbidden,
        ),
    )
    monkeypatch.setattr(training, "run_training", forbid_nested_training)
    monkeypatch.setattr(
        training,
        "load_tokenizer",
        lambda cfg: MockTokenizer(),
    )
    monkeypatch.setattr(
        training,
        "runtime_manifest",
        lambda cfg, tokenizer=None: {"status": "TEST-ONLY", "experiment": cfg.get("experiment")},
    )

    result = original_run_training(
        config,
        dry_run=mode == "dry",
        audit_only=mode == "audit",
        max_steps=100,
    )

    assert result["status"].startswith(expected_status)
    assert result.get("training_succeeded") is False
    assert not nested_calls
    assert not (tmp_path / "staged-checkpoint/stage-synthetic").exists()
    assert not (tmp_path / "staged-checkpoint/stage-real").exists()


def test_staged_smoke_is_rejected_before_stage_side_effects(tmp_path):
    from src.task3.train import run_training

    _, _, config = _staged_fixture(tmp_path)
    config["output_dir"] = str(tmp_path / "staged-checkpoint")

    with pytest.raises(ValueError, match="staged.*smoke"):
        run_training(config, max_steps=10, smoke_test=True)

    assert not (tmp_path / "staged-checkpoint").exists()
