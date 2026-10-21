"""CPU-only safety and objective tests; never load a model or run an optimizer."""
import copy
import math
import json

import pytest

from src.task3.inference import MockTokenizer
from src.task3.pilot_training import (
    WeightedCompletionCollator,
    aggregate_validation,
    claim_optimizer_start,
    completion_mean_losses,
    encode_pilot_examples,
    verify_encoded_binding,
    weighted_completion_loss,
    select_epoch,
    verify_before_optimizer,
    evaluate_internal,
)


def examples(sample_id="S1"):
    return [dict(sample_id=sample_id, example_id=sample_id+suffix,
                 kind=kind, messages=[{"role": "user", "content": "source"}],
                 completion=text, loss_weight=weight)
            for suffix, kind, text, weight in (
                ("-D", "diagnostic", "diagnosis", 2.0),
                ("-L1", "feedback", "short", 2/3),
                ("-L2", "feedback", "longer feedback", 2/3),
                ("-L3", "feedback", "the longest feedback here", 2/3))]


def test_completion_loss_uses_per_example_means_and_fixed_task_weights():
    torch = pytest.importorskip("torch")
    # Correct-class probability 1/2 for example 1, 1/4 for example 2.
    # Different completion lengths must not give the latter more weight.
    logits = torch.tensor([[[0., 0.]]*4, [[0., math.log(3)]]*4], requires_grad=True)
    labels = torch.tensor([[-100, 0, -100, -100], [-100, 0, 0, 0]])
    per_example = completion_mean_losses(logits, labels)
    assert per_example.tolist() == pytest.approx([math.log(2), math.log(4)])
    loss = weighted_completion_loss(logits, labels, torch.tensor([2., 2/3]))
    assert float(loss.detach()) == pytest.approx((2*math.log(2)+(2/3)*math.log(4))/2)
    loss.backward()
    assert bool(torch.isfinite(logits.grad).all())
    assert bool(torch.count_nonzero(logits.grad))


def test_loss_rejects_examples_without_supervised_shifted_tokens():
    torch = pytest.importorskip("torch")
    with pytest.raises(ValueError, match="supervised"):
        completion_mean_losses(torch.zeros(1, 3, 2), torch.tensor([[-100]*3]))


def test_encoding_reports_real_kind_tokens_and_masks_prompts_and_padding():
    rows, audit = encode_pilot_examples(MockTokenizer(), examples(), 8192)
    assert audit["examples"] == 4
    assert audit["sources"] == 1
    assert audit["by_kind"]["diagnostic"]["examples"] == 1
    assert audit["by_kind"]["feedback"]["examples"] == 3
    assert audit["tokens"] == sum(len(r["input_ids"]) for r in rows)
    assert audit["supervised_tokens"] == sum(sum(v != -100 for v in r["labels"]) for r in rows)
    assert all(row["labels"][0] == -100 for row in rows)
    batch = WeightedCompletionCollator(0)(rows[:2])
    assert batch["loss_weight"].tolist() == pytest.approx([2., 2/3])
    assert bool((batch["labels"][batch["attention_mask"] == 0] == -100).all())


def test_encoded_binding_rejects_source_target_and_tensor_changes():
    tokenizer = MockTokenizer()
    source_examples = examples()
    rows, _ = encode_pilot_examples(tokenizer, source_examples, 8192)
    sources = [{"sample_id": "S1", "code": "source", "source_text_sha256": "sealed"}]
    bound = verify_encoded_binding(tokenizer, source_examples, rows, sources, 8192)
    assert bound["sources"] == 1 and bound["examples"] == 4
    mutated = copy.deepcopy(rows)
    mutated[0]["labels"][-1] += 1
    with pytest.raises(ValueError, match="binding"):
        verify_encoded_binding(tokenizer, source_examples, mutated, sources, 8192)
    changed = copy.deepcopy(source_examples)
    changed[0]["completion"] += " changed"
    with pytest.raises(ValueError, match="binding"):
        verify_encoded_binding(tokenizer, changed, rows, sources, 8192)
    with pytest.raises(ValueError, match="source"):
        verify_encoded_binding(tokenizer, source_examples, rows, [{"sample_id": "other"}], 8192)


def test_validation_is_equal_source_and_equal_task_not_token_weighted():
    rows = examples("S1") + examples("S2")
    result = aggregate_validation(rows, [2., 1., 3., 5., 4., 6., 6., 6.])
    assert result["loss"] == pytest.approx(3.75)  # mean(.5*2+.5*3, .5*4+.5*6)
    assert result["diagnostic_loss"] == pytest.approx(3.)
    assert result["feedback_loss"] == pytest.approx(4.5)
    with pytest.raises(ValueError, match="four|diagnostic|feedback"):
        aggregate_validation(rows[:-1], [2., 1., 3., 5., 4., 6., 6.])


def test_optimizer_start_is_exclusive_and_survives_failed_attempt(tmp_path):
    marker = tmp_path / "optimizer-started.json"
    claim_optimizer_start(marker, {"binding_sha256": "first"})
    assert json.loads(marker.read_text())["binding_sha256"] == "first"
    with pytest.raises(FileExistsError, match="second pilot|exists"):
        claim_optimizer_start(marker, {"binding_sha256": "second"})
    assert json.loads(marker.read_text())["binding_sha256"] == "first"


def test_epoch_selection_uses_internal_validation_and_keeps_earliest_tie():
    assert select_epoch([{"epoch": 1, "validation": {"loss": 2.}},
                         {"epoch": 2, "validation": {"loss": 1.}}])["epoch"] == 2
    assert select_epoch([{"epoch": 1, "validation": {"loss": 1.}},
                         {"epoch": 2, "validation": {"loss": 1.}}])["epoch"] == 1
    with pytest.raises(ValueError, match="finite"):
        select_epoch([{"epoch": 1, "validation": {"loss": float('nan')}}])


def test_before_optimizer_rejects_mutation_before_calling_guard():
    tokenizer = MockTokenizer()
    source_examples = examples()
    sources = [{"sample_id": "S1", "code": "source"}]
    rows, _ = encode_pilot_examples(tokenizer, source_examples, 8192)
    frozen = ({"version": 1}, {"max_seq_length": 8192}, source_examples, [], sources, {})
    guarded = []
    def guard(current_sources, registry, *, stage):
        guarded.append((current_sources, stage))
        return {"passed": True}
    result = verify_before_optimizer(lambda: frozen, frozen, tokenizer, rows, guard)
    assert result['guard'] == {'passed': True}
    assert guarded == [(sources, 'before_optimizer')]
    changed = copy.deepcopy(frozen)
    changed[4][0]['code'] = 'different source bytes'
    with pytest.raises(ValueError, match="frozen|binding"):
        verify_before_optimizer(lambda: changed, frozen, tokenizer, rows, guard)
    assert len(guarded) == 1


def test_internal_validation_disables_gradients_and_restores_training_mode():
    torch = pytest.importorskip('torch')
    from types import SimpleNamespace
    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.anchor = torch.nn.Parameter(torch.zeros(()))
        def forward(self, input_ids, attention_mask, use_cache):
            assert not self.training and not torch.is_grad_enabled() and not use_cache
            return SimpleNamespace(logits=torch.zeros(*input_ids.shape, 256))
    rows, _ = encode_pilot_examples(MockTokenizer(), examples(), 8192)
    model = Tiny()
    result = evaluate_internal(model, rows, WeightedCompletionCollator(0))
    assert result['loss'] == pytest.approx(math.log(256))
    assert model.training
