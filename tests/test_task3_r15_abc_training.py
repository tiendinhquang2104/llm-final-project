"""Completion masking, optimizer allowance and exact-state recovery contracts."""
import pytest
import torch


class Tokenizer:
    pad_token_id = 0
    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False, **kwargs):
        result = []
        for m in messages:
            result += [1 if m["role"] == "user" else 2] + [3] * len(m["content"]) + [9]
        if add_generation_prompt:
            result += [2]
        return result


def test_prompt_padding_masked_target_eos_supervised():
    from src.task3.r15_abc_training import encode_train_rows
    from src.task3.pilot_training import WeightedCompletionCollator
    example = dict(sample_id="x", example_id="x@L1", kind="direct", loss_weight=1.,
                   messages=[{"role": "user", "content": "long prompt"}],
                   completion='{"taxonomy_error":[],"feedback":"vi"}')
    other = {**example, "example_id": "y@L1", "sample_id": "y", "completion": '{"taxonomy_error":[],"feedback":"longer vi"}'}
    rows, audit = encode_train_rows(Tokenizer(), [example, other], 8192)
    assert rows[0]["labels"][:14] == [-100] * 14
    assert rows[0]["labels"][-1] == 9
    batch = WeightedCompletionCollator(0)(rows)
    assert batch["labels"][0, -1].item() == -100
    assert audit["supervised_tokens"] > 0


def test_empty_supervision_rejected():
    from src.task3.r15_abc_training import encode_train_rows
    with pytest.raises(ValueError):
        encode_train_rows(Tokenizer(), [], 8192)
    e = dict(sample_id="x", example_id="x@L1", kind="direct", loss_weight=1.,
             messages=[{"role": "user", "content": "hi"}], completion="")
    with pytest.raises(ValueError):
        encode_train_rows(Tokenizer(), [e], 8192)


def test_only_lora_trainable():
    from src.task3.r15_abc_training import audit_trainable
    model = torch.nn.Module()
    model.register_parameter("lora_A", torch.nn.Parameter(torch.ones(2)))
    model.register_parameter("base", torch.nn.Parameter(torch.ones(2), requires_grad=False))
    assert audit_trainable(model)["trainable_parameters"] == 2
    model.base.requires_grad_(True)
    with pytest.raises(ValueError, match="base"):
        audit_trainable(model)


def test_step_budget_and_checkpoint_positions():
    from src.task3.r15_abc_training import step_budget
    assert step_budget(255, 4) == {"optimizer_steps": 64, "checkpoint_steps": [32, 64]}
    assert step_budget(3, 4) == {"optimizer_steps": 1, "checkpoint_steps": [1]}
    with pytest.raises(ValueError):
        step_budget(0, 4)


def test_resume_requires_optimizer_scheduler_rng_and_same_identity():
    from src.task3.r15_abc_training import validate_recovery
    state = dict(identity="sealed", step=1, cursor=4, order=[0, 1, 2, 3], adapter={"a": 1},
                 optimizer={"state": 1}, scheduler={"step": 1},
                 rng={"python": 1, "numpy": 2, "torch": 3, "cuda": [4]})
    assert validate_recovery(state, "sealed")["step"] == 1
    for key in ("optimizer", "scheduler", "rng", "adapter", "order", "cursor"):
        bad = dict(state)
        del bad[key]
        with pytest.raises(ValueError):
            validate_recovery(bad, "sealed")
    with pytest.raises(ValueError, match="identity"):
        validate_recovery(state, "different")


def test_optimizer_marker_cannot_be_replaced(tmp_path):
    from src.task3.r15_abc_training import claim_optimizer_start
    p = tmp_path / "optimizer-started.json"
    claim_optimizer_start(p, {"identity": "one"})
    with pytest.raises(FileExistsError):
        claim_optimizer_start(p, {"identity": "two"})
    assert '"one"' in p.read_text()


def test_recovery_rejects_optimizer_intent_ahead_of_saved_state():
    from src.task3.r15_abc_training import require_recovery_boundary
    require_recovery_boundary({"identity": "a", "step": 4}, {"identity": "a", "step": 4})
    with pytest.raises(ValueError, match="exact recovery"):
        require_recovery_boundary({"identity": "a", "step": 4}, {"identity": "a", "step": 5})


def test_training_costs_include_every_invocation_and_peak():
    from src.task3.r15_abc_training import aggregate_training_costs
    result = aggregate_training_costs([dict(wall_s=1.25, peak_allocated=12, peak_reserved=20),
                                       dict(wall_s=2.5, peak_allocated=8, peak_reserved=24)])
    assert result == dict(invocations=2, wall_s=3.75, peak_allocated=12, peak_reserved=24)
