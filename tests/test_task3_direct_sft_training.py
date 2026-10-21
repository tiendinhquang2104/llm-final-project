"""Artificial direct-SFT safety tests: no downloads, model loads, or optimizers."""
import copy
import hashlib
import json
import math
from types import SimpleNamespace

import pytest

from src.task3.inference import MockTokenizer
from src.task3 import direct_sft_training as training


def examples(sample_id='S1', levels=(1, 2, 3)):
    return [dict(sample_id=sample_id, example_id=f'{sample_id}-L{level}', kind='direct',
                 level=level, messages=[{'role': 'user', 'content': 'source'}],
                 completion=json.dumps({'taxonomy_error': [], 'feedback': f'feedback {level}'}),
                 source_sha256=hashlib.sha256(b'source').hexdigest(), loss_weight=1.)
            for level in levels]


def config():
    return dict(model_id='Qwen/Qwen2.5-Coder-7B-Instruct',
                revision='c03e6d358207e414f1eca0bb1891e29f1db0e242', seed=42,
                load_in_4bit=True, max_seq_length=8192, lora_r=16, lora_alpha=32,
                lora_dropout=.05, learning_rate=1e-4, epochs=2,
                per_device_train_batch_size=1, gradient_accumulation_steps=4,
                lr_scheduler_type='cosine', warmup_ratio=.03,
                target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
                checkpoint_policy='min_internal_validation_equal_source_loss_earliest_tie',
                output_dir='outputs/task3/direct-sft-v1-20261021/training',
                work_dir='outputs/task3/direct-sft-v1-20261021', loss_weights={'direct': 1.})


def test_direct_encoding_masks_prompt_and_padding_without_intermediate_target():
    rows, audit = training.encode_direct_examples(MockTokenizer(), examples(), 8192)
    assert audit['by_kind']['direct']['examples'] == 3
    assert audit['sources'] == 1 and not audit['truncated']
    assert all(row['kind'] == 'direct' and row['loss_weight'] == 1 for row in rows)
    assert all(row['labels'][0] == -100 for row in rows)
    assert audit['supervised_tokens'] == sum(sum(v != -100 for v in r['labels']) for r in rows)
    batch = training.WeightedCompletionCollator(0)(rows)
    assert batch['loss_weight'].tolist() == [1., 1., 1.]
    assert bool((batch['labels'][batch['attention_mask'] == 0] == -100).all())


@pytest.mark.parametrize('field,value', [('kind', 'diagnostic'), ('loss_weight', 2.),
    ('completion', '{"taxonomy_error":[],"feedback":"x","findings":[]}')])
def test_direct_encoding_rejects_intermediate_targets_and_nonunit_weights(field, value):
    records = examples()
    records[0][field] = value
    with pytest.raises(ValueError):
        training.encode_direct_examples(MockTokenizer(), records, 8192)


def test_direct_encoding_rejects_truncation_and_duplicate_ids():
    with pytest.raises(ValueError, match='truncated'):
        training.encode_direct_examples(MockTokenizer(), examples(), 8)
    with pytest.raises(ValueError, match='duplicate'):
        training.encode_direct_examples(MockTokenizer(), examples() * 2, 8192)


def test_direct_validation_means_examples_within_source_then_means_sources():
    records = examples('S1') + examples('S2', (1,))
    result = training.aggregate_validation(records, [1., 3., 5., 9.])
    assert result['loss'] == pytest.approx(6.)  # mean(mean(1,3,5),9), not 4.5
    assert result['per_source']['S1']['loss'] == pytest.approx(3.)
    assert result['sources'] == 2 and result['examples'] == 4
    with pytest.raises(ValueError, match='finite'):
        training.aggregate_validation(records, [1., 3., 5., float('nan')])


def test_unit_weight_completion_loss_is_example_mean_not_token_mean():
    torch = pytest.importorskip('torch')
    logits = torch.tensor([[[0., 0.]]*4, [[0., math.log(3)]]*4], requires_grad=True)
    labels = torch.tensor([[-100, 0, -100, -100], [-100, 0, 0, 0]])
    loss = training.weighted_completion_loss(logits, labels, torch.ones(2))
    assert float(loss.detach()) == pytest.approx((math.log(2) + math.log(4))/2)
    loss.backward()
    assert bool(torch.isfinite(logits.grad).all())
    assert bool(torch.count_nonzero(logits.grad))


def test_source_binding_recomputes_actual_source_bytes():
    records = examples()
    rows, _ = training.encode_direct_examples(MockTokenizer(), records, 8192)
    sources = [{'sample_id': 'S1', 'code': 'source'}]
    training.verify_encoded_binding(MockTokenizer(), records, rows, sources, 8192)
    sources[0]['code'] = 'changed source bytes'
    with pytest.raises(ValueError, match='source'):
        training.verify_encoded_binding(MockTokenizer(), records, rows, sources, 8192)


def test_both_optimizer_boundaries_reverify_exact_sources_and_validation():
    records, validation = examples(), examples('S2', (1,))
    tokenizer = MockTokenizer()
    rows, _ = training.encode_direct_examples(tokenizer, records, 8192)
    val_rows, _ = training.encode_direct_examples(tokenizer, validation, 8192)
    sources = [{'sample_id': 'S1', 'code': 'source'}]
    frozen = ({'version': 'direct'}, config(), records, validation, sources, {'new_policy': True})
    calls = []
    def guard(sources, registry, *, stage):
        calls.append((sources, registry, stage))
        return {'passed': True, 'actual_source_bytes': True}
    for boundary in ('before_optimizer_setup', 'first_optimizer_step'):
        result = training.verify_before_optimizer(lambda: frozen, frozen, tokenizer, rows, guard,
            validation_rows=val_rows, boundary=boundary)
        assert result['boundary'] == boundary and result['guard']['passed']
    assert [call[2] for call in calls] == ['before_optimizer', 'before_optimizer']
    changed = copy.deepcopy(frozen)
    changed[4][0]['code'] += ' drift'
    with pytest.raises(ValueError, match='frozen'):
        training.verify_before_optimizer(lambda: changed, frozen, tokenizer, rows, guard, validation_rows=val_rows)
    changed_rows = copy.deepcopy(val_rows)
    changed_rows[0]['labels'][-1] += 1
    with pytest.raises(ValueError, match='validation'):
        training.verify_before_optimizer(lambda: frozen, frozen, tokenizer, rows, guard, validation_rows=changed_rows)
    assert len(calls) == 2


def test_frozen_config_prevents_retargeting_or_resume():
    training.validate_frozen_config(config())
    for key, value in [('epochs', 3), ('revision', 'main'), ('lora_r', 32),
                       ('max_seq_length', 4096), ('adapter', '/old/adapter'),
                       ('resume_from_checkpoint', 'old'), ('output_dir', 'other')]:
        changed = dict(config(), **{key: value})
        with pytest.raises(ValueError, match='frozen|resume|adapter'):
            training.validate_frozen_config(changed)


def test_base_model_rejects_preexisting_peft_without_loading_any_model():
    class Fake:
        def named_parameters(self):
            return iter([('base.weight', object())])
    assert training.audit_unadapted_base(Fake())['preexisting_adapter'] is False
    fake = Fake()
    fake.peft_config = {'default': object()}
    with pytest.raises(RuntimeError, match='adapter|PEFT'):
        training.audit_unadapted_base(fake)


def test_internal_validation_no_grad_and_restores_mode():
    torch = pytest.importorskip('torch')
    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.anchor = torch.nn.Parameter(torch.zeros(()))
        def forward(self, input_ids, attention_mask, use_cache):
            assert not self.training and not torch.is_grad_enabled() and not use_cache
            return SimpleNamespace(logits=torch.zeros(*input_ids.shape, 256))
    rows, _ = training.encode_direct_examples(MockTokenizer(), examples(), 8192)
    model = Tiny()
    result = training.evaluate_internal(model, rows, training.WeightedCompletionCollator(0))
    assert result['loss'] == pytest.approx(math.log(256)) and model.training


def test_exclusive_marker_and_earliest_tie_selection(tmp_path):
    marker = tmp_path/'optimizer-started.json'
    training.claim_optimizer_start(marker, {'pilot': 'direct'})
    with pytest.raises(FileExistsError):
        training.claim_optimizer_start(marker, {'pilot': 'second'})
    assert json.loads(marker.read_text()) == {'pilot': 'direct'}
    assert training.select_epoch([{'epoch': 2, 'validation': {'loss': 1.}},
                                  {'epoch': 1, 'validation': {'loss': 1.}}])['epoch'] == 1
