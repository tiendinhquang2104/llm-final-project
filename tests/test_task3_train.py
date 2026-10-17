import json

import pytest

from src.task3.inference import MockTokenizer
from src.task3.prompts import ContextTooLong
from src.task3.train import (
    _checkpoint_metadata,
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
    (checkpoint / "trainer_state.json").write_text(json.dumps({"global_step": 10}), encoding="utf-8")
    from src.task3.dataset import write_json

    write_json(checkpoint / "task3_resume_metadata.json", metadata)
    assert validate_resume_checkpoint(checkpoint, metadata) == 10
    with pytest.raises(ValueError, match="incompatible"):
        validate_resume_checkpoint(checkpoint, {**metadata, "data_manifest_sha256": "OTHER"})


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
    observed = {}
    tokenizer = MockTokenizer()
    tokenizer.save_pretrained = lambda path: observed.update(tokenizer_saved=str(path))
    monkeypatch.setattr("src.task3.train.load_tokenizer", lambda cfg: tokenizer)
    monkeypatch.setattr("src.task3.train.runtime_manifest", lambda cfg: {"config": cfg, "TEST_ONLY": True})
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: True)
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 0)
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda: None)
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda: 1234)
    monkeypatch.setattr(torch.cuda, "max_memory_reserved", lambda: 2345)
    monkeypatch.setattr(torch.cuda, "mem_get_info", lambda: (10_000, 20_000))
    monkeypatch.setattr(torch.cuda, "synchronize", lambda *args, **kwargs: None)
    monkeypatch.setattr(transformers, "set_seed", lambda seed: observed.update(seed=seed))

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
