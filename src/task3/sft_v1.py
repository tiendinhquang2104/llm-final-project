"""Offline integration for the delivered Task 3 SFT v1 package."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.task3.train import encode_completion


SPLITS = ('train', 'dev', 'test')
CHECKSUM_MANIFEST_SHA256 = '8374da28569cd235112b928ff48a70ad5c69df2af6a30b9978c48825458be846'
INPUT_KEYS = {'statement', 'exam_type', 'language', 'code', 'compile_log', 'target_feedback_level'}


def validate_data_policy(config):
    """Reject selector-like config values that this canonical integration cannot apply."""
    supported = dict(train_file='train.sft.jsonl', dev_file='dev.sft.jsonl', test_file='test.sft.jsonl',
                     prompt_policy='delivered_native_system_and_user_prompt',
                     test_policy='evaluation_only_after_checkpoint_selection')
    for key, value in supported.items():
        if config.get(key) != value:
            raise ValueError('unsupported data policy: ' + key)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def verify_checksums(root, expected_manifest_sha256=CHECKSUM_MANIFEST_SHA256):
    """Verify the pinned delivered manifest, including every private audit sidecar."""
    root = Path(root).resolve()
    if sha256(root / 'SHA256SUMS') != expected_manifest_sha256:
        raise ValueError('checksum manifest differs from the delivered package')
    files = {}
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        path = (root / name).resolve()
        if not path.is_relative_to(root) or name in files or sha256(path) != expected:
            raise ValueError('checksum mismatch or invalid path: ' + name)
        files[name] = expected
    if not files:
        raise ValueError('empty checksum manifest')
    return dict(passed=True, files=len(files), manifest_sha256=expected_manifest_sha256)


def validate_partitions(root):
    """Check whole-package grouping without using targets to form a split."""
    root = Path(root)
    parts = json.loads((root / 'split-manifest.json').read_text())['partitions']
    if set(parts) != set(SPLITS):
        raise ValueError('expected separate train/dev/test partitions')
    owners = {}
    for split, sources in parts.items():
        seen = set()
        for source in sources:
            sid = source['source_id']
            if sid in seen:
                raise ValueError('duplicate source: ' + sid)
            seen.add(sid)
            code = (root / 'sources' / (sid + '.cpp')).read_text(encoding='utf-8')
            if sha256(root / 'sources' / (sid + '.cpp')) != source['source_sha256']:
                raise ValueError('source checksum mismatch: ' + sid)
            values = dict(source_id=sid, family_id=source['family_id'], cluster=source['cluster'],
                          source_sha256=source['source_sha256'], normalized=''.join(code.split()))
            for kind, value in values.items():
                if not value or owners.setdefault((kind, value), split) != split:
                    raise ValueError('missing or cross-split ' + kind + ': ' + sid)
    return parts


def native_prompt(root, x, labels):
    """Exact delivered renderer, accepting no private fields or extra messages."""
    system = (Path(root) / 'SYSTEM_PROMPT.txt').read_text(encoding='utf-8').removesuffix('\n')
    return [dict(role='system', content=system + '\nAllowed taxonomy labels: '
                 + json.dumps(labels, ensure_ascii=False)),
            dict(role='user', content='Problem statement:\n' + x['statement']
                 + '\nSubmission mode: ' + x['exam_type'] + '\nC++ source:\n```cpp\n'
                 + x['code'] + '```\nC++11 syntax-only diagnostics (empty means no diagnostic):\n'
                 + x['compile_log'] + '\nRequested feedback level: ' + str(x['target_feedback_level']))]


def load_split(root, split='train'):
    """Read exactly one canonical SFT file; identifiers remain outside model input.

    Call verify_checksums before this API when accepting a delivered package.
    The preparation CLI does so automatically. Records are validation sidecars.
    """
    if split not in SPLITS:
        raise ValueError('split must be train, dev or test')
    root = Path(root)
    parts = validate_partitions(root)
    manifest = {s['source_id']: s for s in parts[split]}
    labels = json.loads((root / 'label_space.json').read_text())['taxonomy_error']
    records = read_jsonl(root / (split + '.records.jsonl'))
    data = read_jsonl(root / (split + '.sft.jsonl'))
    if len(records) != len(data) or len(data) != len(manifest) * 4:
        raise ValueError('each manifest source requires exactly four canonical SFT targets')
    examples, seen, coverage = [], set(), {}
    for record, row in zip(records, data):
        sid, eid, x = record['source_id'], record['sample_id'], record['input']
        if sid not in manifest or eid in seen or record['split'] != split:
            raise ValueError('duplicate ID or record split mismatch: ' + eid)
        seen.add(eid)
        level = x.get('target_feedback_level')
        if set(x) != INPUT_KEYS or type(level) is not int or level not in (1, 2, 3, 4):
            raise ValueError('input whitelist or requested Level invalid: ' + eid)
        source = manifest[sid]
        if (record['family_id'] != source['family_id'] or record['group_id'] != source['cluster']
                or x['code'] != (root / 'sources' / (sid + '.cpp')).read_text(encoding='utf-8')
                or x['language'] != 'cpp11'):
            raise ValueError('source/manifest binding mismatch: ' + eid)
        if (set(row) != {'prompt', 'completion'} or row['prompt'] != native_prompt(root, x, labels)
                or len(row['completion']) != 1
                or set(row['completion'][0]) != {'role', 'content'}
                or row['completion'][0]['role'] != 'assistant'):
            raise ValueError('canonical prompt/completion mapping differs: ' + eid)
        completion = row['completion'][0]['content']
        output = json.loads(completion)
        if (not isinstance(output, dict) or set(output) != {'taxonomy_error', 'feedback'}
                or not isinstance(output['taxonomy_error'], list)
                or any(label not in labels for label in output['taxonomy_error'])
                or not isinstance(output['feedback'], str) or not output['feedback'].strip()
                or output != record['output']):
            raise ValueError('invalid output schema or record mismatch: ' + eid)
        coverage.setdefault(sid, []).append(level)
        examples.append(dict(example_id=eid, sample_id=sid, level=level,
                             prompt=row['prompt'], completion=completion, loss_weight=1.))
    if set(coverage) != set(manifest) or any(sorted(v) != [1, 2, 3, 4] for v in coverage.values()):
        raise ValueError('source does not have one target per Level')
    return examples


def encode_examples(tokenizer, examples, max_length):
    """Reuse the trainer encoder, preserving full JSON and assistant ending."""
    rows, by_level = [], {}
    for example in examples:
        try:
            row = encode_completion(tokenizer, example['prompt'], example['completion'], max_length)
        except ValueError as exc:
            raise ValueError(example['example_id'] + ': ' + str(exc)) from exc
        row.update({k: example[k] for k in ('example_id', 'sample_id', 'level', 'loss_weight')})
        stats = by_level.setdefault(str(example['level']), dict(rows=0, full_tokens=0, completion_tokens=0))
        stats['rows'] += 1
        stats['full_tokens'] += len(row['input_ids'])
        stats['completion_tokens'] += sum(label != -100 for label in row['labels'][1:])
        rows.append(row)
    if not rows:
        raise ValueError('empty SFT split')
    return rows, dict(rows=len(rows), sources=len({r['sample_id'] for r in rows}),
                      max_full_tokens=max(len(r['input_ids']) for r in rows),
                      completion_tokens=sum(v['completion_tokens'] for v in by_level.values()),
                      by_level=by_level, truncated=False)


def make_trainer(model, args, train_rows, dev_rows, pad_token_id):
    """Dataset integration point; same encoder, collator and loss for future training.

    test_rows is intentionally absent. Constructing a Trainer does not train it.
    """
    if args.remove_unused_columns:
        raise ValueError('remove_unused_columns must be False for completion labels and loss weights')
    from transformers import Trainer
    from src.task3.pilot_training import WeightedCompletionCollator, weighted_completion_loss

    class SFTTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            weights = inputs['loss_weight']
            if not bool((weights == 1).all()):
                raise ValueError('SFT v1 uses equal-example loss weights of one')
            outputs = model(input_ids=inputs['input_ids'], attention_mask=inputs['attention_mask'], use_cache=False)
            loss = weighted_completion_loss(outputs.logits, inputs['labels'], weights)
            return (loss, outputs) if return_outputs else loss

    trainer = SFTTrainer(model=model, args=args, train_dataset=train_rows, eval_dataset=dev_rows,
                         data_collator=WeightedCompletionCollator(pad_token_id))
    trainer.model_accepts_loss_kwargs = False
    return trainer
