"""Protect dataset boundaries, private inputs, and complete assistant supervision."""
import hashlib
import json

import pytest

from src.task3.inference import MockTokenizer
from src.task3 import sft_v1


@pytest.fixture
def package(tmp_path):
    (tmp_path / 'SYSTEM_PROMPT.txt').write_text('Contract.\n')
    (tmp_path / 'label_space.json').write_text(json.dumps({'taxonomy_error': ['Lỗi logic']}))
    (tmp_path / 'sources').mkdir()
    partitions = {}
    for split, name, code in [('train', 'A', 'void a() {}\n'),
                              ('dev', 'B', 'void b() {}\n'),
                              ('test', 'C', 'void c() {}\n')]:
        (tmp_path / 'sources' / (name + '.cpp')).write_text(code)
        partitions[split] = [dict(source_id=name, family_id=name, cluster=name,
                                 source_sha256=hashlib.sha256(code.encode()).hexdigest())]
        records, sfts = [], []
        for level in range(1, 5):
            text = ('Hàm add_match đếm phần tử không chia hết, trái yêu cầu đề.'
                    if level == 2 else 'Phản hồi tiếng Việt. ' * level)
            output = dict(taxonomy_error=['Lỗi logic'], feedback=text)
            x = dict(statement='Đếm số.', exam_type='function', language='cpp11', code=code,
                     compile_log='', target_feedback_level=level)
            records.append(dict(sample_id=f'{name}-L{level}', source_id=name, family_id=name,
                                group_id=name, split=split, input=x, output=output))
            sfts.append(dict(prompt=[
                dict(role='system', content='Contract.\nAllowed taxonomy labels: ["Lỗi logic"]'),
                dict(role='user', content='Problem statement:\nĐếm số.\nSubmission mode: function\n'
                     'C++ source:\n```cpp\n' + code + '```\n'
                     'C++11 syntax-only diagnostics (empty means no diagnostic):\n\n'
                     'Requested feedback level: ' + str(level))],
                completion=[dict(role='assistant', content=json.dumps(output, ensure_ascii=False))]))
        for kind, rows in [('records', records), ('sft', sfts)]:
            (tmp_path / f'{split}.{kind}.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    (tmp_path / 'split-manifest.json').write_text(json.dumps({'partitions': partitions}))
    return tmp_path


def rewrite(path, transform):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    transform(rows)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))


def test_default_training_selection_preserves_l2_and_never_adds_alternatives(package):
    (package / 'train.messages.jsonl').write_text('not additional training data')
    (package / 'train.l123.sft.jsonl').write_text('not additional training data')
    examples = sft_v1.load_split(package)
    assert [r['example_id'] for r in examples] == ['A-L1', 'A-L2', 'A-L3', 'A-L4']
    assert json.loads(examples[1]['completion'])['feedback'] == (
        'Hàm add_match đếm phần tử không chia hết, trái yêu cầu đề.')
    assert all('A-L' not in m['content'] for r in examples for m in r['prompt'])


@pytest.mark.parametrize('location', ['prompt', 'record', 'output'])
def test_private_fields_or_extra_output_keys_cannot_enter_examples(package, location):
    if location == 'prompt':
        rewrite(package / 'train.sft.jsonl', lambda rows: rows[0]['prompt'][1].update(
            content=rows[0]['prompt'][1]['content'] + '\nreviewer verdict: correct'))
    elif location == 'record':
        rewrite(package / 'train.records.jsonl', lambda rows: rows[0]['input'].update(witness='secret'))
    else:
        def change(rows):
            value = json.loads(rows[0]['completion'][0]['content'])
            value['solution_source_id'] = 'secret'
            rows[0]['completion'][0]['content'] = json.dumps(value)
        rewrite(package / 'train.sft.jsonl', change)
    with pytest.raises(ValueError):
        sft_v1.load_split(package)


def test_declared_related_clusters_cannot_cross_splits(package):
    manifest = json.loads((package / 'split-manifest.json').read_text())
    manifest['partitions']['dev'][0]['cluster'] = 'A'
    (package / 'split-manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='cross-split'):
        sft_v1.validate_partitions(package)


def test_checksum_rejects_tampered_payload(tmp_path):
    (tmp_path / 'payload').write_text('original')
    checksums = hashlib.sha256(b'original').hexdigest() + '  payload\n'
    (tmp_path / 'SHA256SUMS').write_text(checksums)
    manifest_sha = hashlib.sha256(checksums.encode()).hexdigest()
    assert sft_v1.verify_checksums(tmp_path, manifest_sha)['files'] == 1
    (tmp_path / 'payload').write_text('changed')
    with pytest.raises(ValueError, match='checksum'):
        sft_v1.verify_checksums(tmp_path, manifest_sha)


@pytest.mark.parametrize('key,value', [('train_file', 'train.l123.sft.jsonl'),
    ('dev_file', 'train.sft.jsonl'), ('test_file', 'dev.sft.jsonl'),
    ('prompt_policy', 'historical_r15'), ('test_policy', 'checkpoint_selection')])
def test_config_cannot_claim_an_ablation_or_policy_that_preparation_does_not_apply(key, value):
    config = dict(train_file='train.sft.jsonl', dev_file='dev.sft.jsonl', test_file='test.sft.jsonl',
                  prompt_policy='delivered_native_system_and_user_prompt',
                  test_policy='evaluation_only_after_checkpoint_selection')
    sft_v1.validate_data_policy(config)
    config[key] = value
    with pytest.raises(ValueError, match=key):
        sft_v1.validate_data_policy(config)


def test_native_encoder_supervises_whole_json_and_ending_but_masks_prompt_and_padding(package):
    tokenizer = MockTokenizer()
    rows, report = sft_v1.encode_examples(tokenizer, sft_v1.load_split(package), 10000)
    from src.task3.pilot_training import WeightedCompletionCollator
    batch = WeightedCompletionCollator(0)(rows)
    for i, row in enumerate(rows):
        supervised = batch['labels'][i][batch['labels'][i] != -100].tolist()
        decoded = bytes(supervised).decode()
        assert decoded.endswith('\n</assistant>\n')
        assert set(json.loads(decoded.removesuffix('\n</assistant>\n'))) == {'taxonomy_error', 'feedback'}
        assert batch['labels'][i][batch['attention_mask'][i] == 0].eq(-100).all()
        prefix = len(row['labels']) - len(supervised)
        assert batch['labels'][i][:prefix].eq(-100).all()
    assert batch['attention_mask'].eq(0).any()
    assert set(report['by_level']) == {'1', '2', '3', '4'}
    assert sum(v['completion_tokens'] for v in report['by_level'].values()) == report['completion_tokens']


def test_overflow_is_rejected_with_example_id_instead_of_cropping(package):
    with pytest.raises(ValueError, match='A-L1'):
        sft_v1.encode_examples(MockTokenizer(), sft_v1.load_split(package), 2)


def test_trainer_preserves_collator_columns_and_uses_equal_example_completion_loss(tmp_path):
    import math
    from types import SimpleNamespace
    import torch
    from transformers import TrainingArguments

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.bias = torch.nn.Parameter(torch.tensor(0.))

        def forward(self, input_ids, attention_mask, use_cache=False):
            logits = torch.zeros(2, 5, 2) + self.bias
            logits[1, :, 0] += math.log(3)
            return SimpleNamespace(logits=logits)

    args = TrainingArguments(output_dir=str(tmp_path), use_cpu=True, report_to=[],
                             remove_unused_columns=False, per_device_train_batch_size=2)
    rows = [dict(input_ids=[0, 0, 0], attention_mask=[1, 1, 1], labels=[-100, -100, 0],
                 example_id='short', loss_weight=1.),
            dict(input_ids=[0] * 5, attention_mask=[1] * 5, labels=[-100, -100, 0, 0, 0],
                 example_id='long', loss_weight=1.)]
    trainer = sft_v1.make_trainer(Model(), args, rows, rows, 0)
    batch = trainer.data_collator(rows)
    loss = trainer.compute_loss(trainer.model, batch)
    assert float(loss.detach()) == pytest.approx((math.log(2) + math.log(4 / 3)) / 2)
    assert next(iter(trainer.get_train_dataloader()))['labels'].eq(-100).any()
    args.remove_unused_columns = True
    with pytest.raises(ValueError, match='remove_unused_columns'):
        sft_v1.make_trainer(Model(), args, rows, rows, 0)
