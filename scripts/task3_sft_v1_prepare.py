"""Offline dataset/tokenizer/Trainer-dataloader audit; never load Qwen or train."""
from __future__ import annotations

import argparse
from collections import Counter
from importlib.metadata import version
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.task3.sft_v1 import (encode_examples, load_split, make_trainer,
                             sha256, validate_data_policy, verify_checksums)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def bundled_audits(root, out):
    """The delivered scripts write into their own package; run them on a copy."""
    with tempfile.TemporaryDirectory(prefix='task3-sft-v1-audit-') as temp:
        copy = Path(temp) / 'task3-sft-v1'
        shutil.copytree(root, copy)
        for script, flags, report in [('audit_exports.py', [], 'final-audit.json'),
                                      ('verify_dataset.py', ['--offline'], 'offline-report.json')]:
            result = subprocess.run([sys.executable, 'scripts/' + script, *flags], cwd=copy,
                                    text=True, capture_output=True)
            (out / (script + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
            result.check_returncode()
            shutil.copy2(copy / 'verification' / report, out / report)


def audit_batch(batch, rows_by_id, examples_by_id, tokenizer):
    """Inspect tensors produced by the actual Trainer's collator, including pads."""
    padding = 0
    for index, eid in enumerate(batch['example_id']):
        row = rows_by_id[eid]
        size = len(row['input_ids'])
        ids = batch['input_ids'][index].tolist()
        labels = batch['labels'][index].tolist()
        attention = batch['attention_mask'][index].tolist()
        if (ids[:size] != row['input_ids'] or labels[:size] != row['labels']
                or attention != [1] * size + [0] * (len(ids) - size)
                or any(label != -100 for label in labels[size:])
                or any(token != tokenizer.pad_token_id for token in ids[size:])):
            raise ValueError('Trainer batch input/labels/padding differ: ' + eid)
        prefix = next(i for i, label in enumerate(labels) if label != -100)
        supervised = [label for label in labels if label != -100]
        if (any(label != -100 for label in labels[:prefix])
                or supervised != row['input_ids'][prefix:]
                or tokenizer.eos_token_id not in supervised
                or tokenizer.decode(supervised, skip_special_tokens=True).strip()
                != examples_by_id[eid]['completion']):
            raise ValueError('Full assistant JSON/ending not preserved: ' + eid)
        padding += len(ids) - size
    return padding


def prepare(config_path, out, tokenizer_path=None):
    import yaml
    config = yaml.safe_load(config_path.read_text())
    validate_data_policy(config)
    historical = yaml.safe_load((REPO / config['historical_config']).read_text())
    for key in ('model_id', 'revision'):
        if config[key] != historical[key]:
            raise ValueError('actual historical configuration differs: ' + key)
    if config['training']['max_seq_length'] != historical['training']['max_seq_length']:
        raise ValueError('training context differs from the inspected configuration')
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=REPO, text=True).strip()
    if branch != config['required_branch']:
        raise ValueError('unexpected branch: ' + branch)
    root = REPO / config['dataset_root']
    tokenizer_path = Path(tokenizer_path or config['tokenizer_local']).absolute()
    if not tokenizer_path.is_dir() or tokenizer_path.name != config['revision']:
        raise ValueError('local tokenizer must be the pinned checkpoint snapshot directory')
    model_config = json.loads((tokenizer_path / 'config.json').read_text())
    if model_config.get('model_type') != 'qwen2':
        raise ValueError('unexpected local model architecture')
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    report = dict(status='preparing', training_performed=False, model_loaded=False, model_calls=0,
                  optimizer_steps=0, branch=branch, config=config, config_sha256=sha256(config_path),
                  historical_config_sha256=sha256(REPO / config['historical_config']))
    try:
        report['checksums'] = verify_checksums(root, config['checksum_manifest_sha256'])
        bundled_audits(root, out)
        examples = {split: load_split(root, split) for split in ('train', 'dev', 'test')}
        if {key: len(value) for key, value in examples.items()} != config['expected_rows']:
            raise ValueError('unexpected native split counts')
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        command = [sys.executable, str(root / 'scripts/preflight_tokenizer.py'),
                   '--tokenizer', str(tokenizer_path), '--revision', config['revision'],
                   '--max-length', str(config['training']['max_seq_length']),
                   '--out', str(out / 'tokenizer-audit.json')]
        result = subprocess.run(command, text=True, capture_output=True)
        (out / 'preflight_tokenizer.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        result.check_returncode()

        import torch
        from transformers import AutoTokenizer, TrainingArguments, set_seed
        tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path), revision=config['revision'],
                                                  local_files_only=True, trust_remote_code=False)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        report['versions'] = {name: version(name) for name in
                              ('torch', 'transformers', 'peft', 'bitsandbytes', 'accelerate', 'datasets', 'pyyaml')}
        report['python'] = sys.version
        report['tokenizer'] = dict(snapshot=str(tokenizer_path), revision=config['revision'],
            chat_template_sha256=hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
            files={p.name: sha256(p) for p in tokenizer_path.iterdir()
                   if p.is_file() and (p.suffix in ('.json', '.txt', '.jinja'))},
            pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
        encoded, report['tokens'] = {}, {}
        for split, data in examples.items():
            encoded[split], report['tokens'][split] = encode_examples(
                tokenizer, data, config['training']['max_seq_length'])
            (out / (split + '.encoded.private.jsonl')).write_text(''.join(
                json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n' for row in encoded[split]),
                encoding='utf-8')
        set_seed(config['seed'])

        class NoForward(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.placeholder = torch.nn.Parameter(torch.zeros(()))

            def forward(self, *args, **kwargs):
                raise RuntimeError('preparation is forbidden from calling a model')

        args = TrainingArguments(output_dir=str(out / 'cpu-dataloader'), use_cpu=True,
            per_device_train_batch_size=config['training']['per_device_train_batch_size'],
            seed=config['seed'], data_seed=config['seed'], report_to=[], remove_unused_columns=False,
            dataloader_num_workers=0, dataloader_pin_memory=False)
        trainer = make_trainer(NoForward(), args, encoded['train'], encoded['dev'], tokenizer.pad_token_id)
        rows_by_id = {row['example_id']: row for row in encoded['train']}
        examples_by_id = {row['example_id']: row for row in examples['train']}
        exposures, pads, first = Counter(), 0, None
        for batch in trainer.get_train_dataloader():
            pads += audit_batch(batch, rows_by_id, examples_by_id, tokenizer)
            exposures.update(batch['example_id'])
            if first is None:
                first = {key: value.tolist() if hasattr(value, 'tolist') else value for key, value in batch.items()}
        if exposures != Counter({eid: 1 for eid in rows_by_id}):
            raise ValueError('Trainer must expose each train target exactly once, and no dev/test')
        ordered = sorted(encoded['train'], key=lambda row: len(row['input_ids']))
        stress = trainer.data_collator([ordered[0], ordered[-1]])
        stress_pads = audit_batch(stress, rows_by_id, examples_by_id, tokenizer)
        if stress_pads <= 0:
            raise ValueError('padding audit did not exercise any padding')
        write_json(out / 'trainer-minibatch.private.json', dict(actual_first_batch=first,
            padding_stress_batch={k: v.tolist() if hasattr(v, 'tolist') else v for k, v in stress.items()}))
        report['collator'] = dict(passed=True, trainer_factory='src.task3.sft_v1.make_trainer',
            scope='CPU Trainer dataloader with NoForward placeholder; no Qwen model or optimizer',
            actual_qwen_training_minibatch_checked=False, train_rows_checked=sum(exposures.values()),
            train_padding_tokens=pads, stress_padding_tokens=stress_pads,
            system_user_padding_masked=True, full_assistant_json_and_ending_supervised=True)
        report['loss_policy'] = dict(objective=config['training']['loss'], example_weight=1.,
            note='Per-example completion mean, then equal example mean. Token shares are not loss shares.',
            train_completion_token_share_by_level={level: stats['completion_tokens'] /
                report['tokens']['train']['completion_tokens']
                for level, stats in report['tokens']['train']['by_level'].items()})
        report['implementation_sha256'] = {name: sha256(REPO / name) for name in
            ('scripts/task3_sft_v1_prepare.py', 'src/task3/sft_v1.py', 'src/task3/train.py',
             'src/task3/pilot_training.py')}
        verify_checksums(root, config['checksum_manifest_sha256'])
        report.update(status='prepared', wall_s=time.perf_counter() - started)
        write_json(out / 'actual-config.json', report)
        write_json(out / 'artifact-sha256.json', {p.name: sha256(p) for p in out.iterdir() if p.is_file()})
        print(json.dumps({key: report[key] for key in ('status', 'tokens', 'collator', 'loss_policy', 'wall_s')}, indent=2))
    except Exception as exc:
        report.update(status='failed', error=str(exc), wall_s=time.perf_counter() - started)
        write_json(out / 'actual-config.json', report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=REPO / 'configs/task3/sft_v1.yaml')
    parser.add_argument('--tokenizer', type=Path, help='Existing pinned local snapshot; no download')
    parser.add_argument('--out', type=Path, required=True, help='New run directory; existing paths are refused')
    args = parser.parse_args()
    prepare(args.config.resolve(), args.out.resolve(), args.tokenizer)


if __name__ == '__main__':
    main()
