#!/usr/bin/env python3
"""Private-only v2 freeze: fixed old validation, immutable prior paired outputs."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
WORK = REPO/'outputs/task3/direct-sft-v2-20261021'
FROZEN = WORK/'frozen'
CONFIG = REPO/'configs/task3/direct_sft_v2_20261021.json'
V1 = REPO/'outputs/task3/direct-sft-v1-20261021'
VERSION = 'direct-sft-v2-20261021'
LIBRARIES = ('torch','transformers','peft','bitsandbytes','accelerate','datasets')

from scripts.task3_direct_sft_prepare import (read, sha, digest, write_new,
    build_examples as build_v1_examples, verify_hashes)
from scripts.task3_direct_sft_infer import LOCKED, validate_rows
from src.task3.direct_sft_v2_data import require_direct_v2_isolation


def build_examples(sources, reviewed):
    """Use the exact proven final JSON prompt formatter with independent v2 IDs."""
    result = build_v1_examples(sources, reviewed)
    for row in result:
        row['example_id'] = f"direct-v2:{row['sample_id']}@L{row['requested_level']}"
    return result


def preserved_split(sources, old_validation):
    """Retain all fourteen old source identities and bytes; never random-resplit."""
    by = {r['sample_id']: r for r in sources}
    old = {r['sample_id']: r for r in old_validation}
    if len(by) != len(sources) or len(old) != 14 or len(old) != len(old_validation):
        raise ValueError('duplicate source or invalid fixed validation membership')
    if not set(old) <= set(by):
        raise ValueError('missing original validation source')
    for sid, row in old.items():
        if by[sid] != row:
            raise ValueError('original validation source bytes/context changed')
    train = [r for r in sources if r['sample_id'] not in old]
    if not train:
        raise ValueError('empty optimizer source split')
    return train, [by[r['sample_id']] for r in old_validation]


def verify_example_bindings(train_sources, val_sources, reviewed, train_examples, val_examples):
    ids = [r['sample_id'] for r in train_sources + val_sources]
    if len(ids) != len(set(ids)):
        raise ValueError('optimizer/internal validation source overlap')
    def indexed(rows):
        result = {r['example_id']: r for r in rows}
        if len(result) != len(rows):
            raise ValueError('duplicate frozen example ID')
        return result
    fresh = build_examples(train_sources + val_sources, reviewed)
    if indexed(fresh) != indexed(train_examples + val_examples):
        raise ValueError('source/context/target-to-example mismatch')
    for sources, examples in ((train_sources, train_examples), (val_sources, val_examples)):
        if {r['sample_id'] for r in sources} != {r['sample_id'] for r in examples}:
            raise ValueError('example split/source mismatch')


def verify_reused_arm(path, arm, rows):
    """Prove prior outputs have identical inputs, config, and complete coverage."""
    path = Path(path)
    started, status, predictions = (read(path/name) for name in ('started.json','status.json','predictions.json'))
    if (started.get('arm') != arm or started.get('config') != LOCKED
            or started.get('config_sha256') != digest(LOCKED)
            or started.get('inputs_sha256') != digest(rows)
            or started.get('requests') != 60 or started.get('resume_allowed') is not False):
        raise ValueError('reused arm input/config provenance mismatch')
    if (status.get('complete') is not True or any(status.get(k) != 60 for k in ('requests','processed','completed'))):
        raise ValueError('reused arm incomplete')
    expected = {(r['request_id'], r['sample_id']) for r in rows}
    actual = {(r.get('request_id'), r.get('sample_id')) for r in predictions}
    if len(rows) != 60 or len(predictions) != 60 or len(actual) != 60 or actual != expected:
        raise ValueError('reused predictions request/source membership mismatch')
    from src.task3.round15 import parse_response
    for prediction in predictions:
        if prediction.get('status') != 'completed':
            raise ValueError('reused prediction not completed')
        parse_response(json.dumps(prediction['output'], ensure_ascii=False))
    return {p.name: sha(p) for p in sorted(path.iterdir()) if p.is_file()}


def _verify_old_frozen():
    seal = read(V1/'frozen/seal.json')
    for name, expected in seal['files_sha256'].items():
        if Path(name).name != name or sha(V1/'frozen'/name) != expected:
            raise ValueError('v1 frozen artifact changed: ' + name)
    manifest = read(V1/'frozen/manifest.json')
    verify_hashes(manifest['implementation_sha256'])
    verify_hashes({name:expected for name,expected in manifest['parent_files_sha256'].items()
                   if not name.startswith('data/raw/public_test_release/')})
    return manifest


def _target_gate():
    quality = read(WORK/'review/pretrain-target-audit.private.json')
    if quality.get('training_gate_pass') is not True or quality.get('targets_sha256') != sha(WORK/'targets/targets-reviewed-final.private.json'):
        raise ValueError('v2 target quality gate failed or target hash unbound')
    audit = WORK/'analysis/v1-error-audit.private.json'
    if not audit.is_file():
        raise ValueError('retrospective v1 error audit required before freeze')
    # The audit itself is bound in parent_files_sha256 before any optimizer.
    read(audit)
    return quality


def _decision():
    return dict(completion='All 60 requests complete and all relevant semantic flags known for BASE,V1,V2.',
        taxonomy='For each source/annotation micro/macro F1: V2 >= BASE + .9*max(0,V1-BASE).',
        L2='Defect L2 useful location+cause rate AND strict location+cause/no false claim/no concrete repair rate each strictly exceed both BASE and V1.',
        L3='Defect L3 cause+feasible repair >=2/6 and strictly exceeds both BASE and V1.',
        false_claims='Overall V2 false claims <=V1 and <BASE; L1 false-clean <=V1.',
        failure='Any failed or unknown condition => keep R15; no retuning or further training, no public candidate.',
        public='No public generation authorized by this protocol.')


def verify_pilot():
    seal, manifest = read(FROZEN/'seal.json'), read(FROZEN/'manifest.json')
    for name, expected in seal['files_sha256'].items():
        if Path(name).name != name or sha(FROZEN/name) != expected:
            raise ValueError('v2 frozen artifact changed: ' + name)
    verify_hashes(manifest['implementation_sha256'])
    verify_hashes(manifest['parent_files_sha256'])
    if any(version(name) != expected for name, expected in manifest['library_versions'].items()):
        raise ValueError('runtime library versions changed')
    _target_gate()
    config = read(FROZEN/'config.json')
    from src.task3.direct_sft_v2_training import validate_frozen_config
    validate_frozen_config(config)
    if config != read(CONFIG):
        raise ValueError('v2 configuration changed after freeze')
    sources, val = read(FROZEN/'train-sources.private.json'), read(FROZEN/'validation-sources.private.json')
    preserved_split(sources + val, read(V1/'frozen/validation-sources.private.json'))
    registry = read(FROZEN/'registry.private.json')
    require_direct_v2_isolation(sources, registry, stage='before_optimizer', validation_sources=val)
    examples, validation = read(FROZEN/'train-examples.private.json'), read(FROZEN/'validation-examples.private.json')
    verify_example_bindings(sources, val, read(WORK/'targets/targets-reviewed-final.private.json'), examples, validation)
    rows = read(FROZEN/'development-inputs.private.json')
    if rows != read(V1/'frozen/development-inputs.private.json'):
        raise ValueError('frozen development inputs changed from v1')
    validate_rows(rows)
    for display, original in (('BASE','BASE'),('V1','SFT')):
        if verify_reused_arm(V1/'inference'/f'arm-{original}', original, rows) != manifest['reused_outputs_sha256'][display]:
            raise ValueError('reused prior output bytes changed')
    return manifest, config, examples, validation, sources, registry


def prepare():
    if FROZEN.exists():
        raise FileExistsError('v2 freeze already exists')
    old_manifest = _verify_old_frozen()
    quality = _target_gate()
    config = read(CONFIG)
    from src.task3.direct_sft_v2_training import validate_frozen_config, encode_direct_examples
    validate_frozen_config(config)
    sources = read(WORK/'targets/approved-sources.private.json')
    reviewed = read(WORK/'targets/targets-reviewed-final.private.json')
    registry = read(WORK/'data/registry.private.json')
    train, val = preserved_split(sources, read(V1/'frozen/validation-sources.private.json'))
    old_train = read(V1/'frozen/train-sources.private.json')
    by = {r['sample_id']:r for r in train}
    if len(old_train) != 56 or any(by.get(row['sample_id']) != row for row in old_train):
        raise ValueError('all 56 original optimizer sources must remain byte/context identical')
    refs = {r['sample_id']:r for r in reviewed}
    if any(set(refs[row['sample_id']]['source_reference']) != set(row['taxonomy_annotation']) for row in sources):
        raise ValueError('annotation/source target conflict')
    guard = require_direct_v2_isolation(train, registry, stage='before_targets', validation_sources=val)
    all_examples = build_examples(sources, reviewed)
    tids = set(by)
    examples = [r for r in all_examples if r['sample_id'] in tids]
    validation = [r for r in all_examples if r['sample_id'] not in tids]
    for source in sources:
        levels = {r['requested_level'] for r in all_examples if r['sample_id'] == source['sample_id']}
        if levels != {1,2,3}:
            raise ValueError('every v2 source requires exactly L1/L2/L3 targets')
    verify_example_bindings(train, val, reviewed, examples, validation)
    rows = read(V1/'frozen/development-inputs.private.json')
    validate_rows(rows)
    if len(rows) != 60 or {r['sample_id'] for r in rows} & {r['sample_id'] for r in sources}:
        raise ValueError('development membership/leakage')
    reused = {display:verify_reused_arm(V1/'inference'/f'arm-{original}', original, rows) for display,original in (('BASE','BASE'),('V1','SFT'))}
    trained = read(V1/'training/training-result.json')
    if trained.get('status') != 'complete':
        raise ValueError('completed v1 selected adapter provenance required')
    adapter = V1/'training/adapter'
    actual = {str(p.relative_to(adapter)):sha(p) for p in adapter.rglob('*') if p.is_file()}
    if actual != trained['selected_adapter_files_sha256']:
        raise ValueError('v1 selected adapter drift')
    # Loading a tokenizer here is explicit prepare-only; no model, optimizer or inference.
    from src.task3.inference import load_tokenizer, tokenizer_metadata
    tokenizer = load_tokenizer(config)
    _, train_audit = encode_direct_examples(tokenizer, examples, config['max_seq_length'])
    _, val_audit = encode_direct_examples(tokenizer, validation, config['max_seq_length'])
    files = set(old_manifest['implementation_sha256'])
    files.update(str(p.relative_to(REPO)) for package in ('src/task3','src/synth','src/utils') for p in (REPO/package).glob('*.py'))
    files.update(('scripts/task3_direct_sft_v2_prepare.py','scripts/task3_direct_sft_v2_train.py','scripts/task3_direct_sft_v2_infer.py','scripts/task3_direct_sft_v2_report.py'))
    parents = [CONFIG, WORK/'targets/approved-sources.private.json',WORK/'targets/targets-reviewed-final.private.json',WORK/'data/registry.private.json',WORK/'review/pretrain-target-audit.private.json',WORK/'analysis/v1-error-audit.private.json',V1/'training/training-result.json']
    parents += [p for base in (V1/'frozen',V1/'inference',adapter) for p in base.rglob('*') if p.is_file()]
    # Bind original dataset bytes from old protocol without reopening public sources.
    parents += [REPO/name for name in old_manifest['parent_files_sha256'] if not name.startswith('data/raw/public_test_release/')]
    parents += [p for directory in ('data','review','targets','analysis')
                for p in (WORK/directory).rglob('*.json') if p.is_file()]
    parents = sorted(set(parents))
    protocol = dict(version=VERSION,library_versions={name:version(name) for name in LIBRARIES},
        source_split='same14v1internal_validation; original56optimizer plus reviewed additions; all Levels of a source together',
        training_signal='assistant final two-field JSON only; no diagnosis or CoT',
        family_disjoint=False, evaluation_status='Previously exposed Evalv2 development; source-level isolation only; shared families are allowed.',
        levels=dict(trained=[1,2,3],Level4='not trained; development L4 is generalization only'),
        selection='min_internal_validation_equal_source_loss_earliest_tie; no development selection',
        optimizer_runs=1,base_initialization='fresh pinned base7B, no previous adapter or resume',
        train=dict(sources=len(train),examples=len(examples)),validation=dict(sources=len(val),examples=len(validation)),
        guard=guard,token_audit=dict(train=train_audit,validation=val_audit),tokenizer=tokenizer_metadata(tokenizer),
        development=dict(primary=60,exact_v1_inputs_sha256=sha(V1/'frozen/development-inputs.private.json')),
        reused_outputs_sha256=reused,reused_output_paths={display:str((V1/'inference'/f'arm-{original}').relative_to(REPO)) for display,original in (('BASE','BASE'),('V1','SFT'))},
        old_runtime_files=len(old_manifest['implementation_sha256']),decision=_decision(),
        implementation_sha256={name:sha(REPO/name) for name in sorted(files)},
        parent_files_sha256={str(p.relative_to(REPO)):sha(p) for p in parents})
    artifacts={'config.json':config,'train-sources.private.json':train,'validation-sources.private.json':val,
        'train-examples.private.json':examples,'validation-examples.private.json':validation,'registry.private.json':registry,
        'development-inputs.private.json':rows,'protocol.json':protocol,'token-audit.json':protocol['token_audit'],
        'rubric.json':protocol['decision'],'manifest.json':protocol}
    FROZEN.mkdir(parents=True)
    for name,value in artifacts.items():
        write_new(FROZEN/name,value)
    write_new(FROZEN/'seal.json',dict(files_sha256={p.name:sha(p) for p in FROZEN.iterdir() if p.is_file()}))
    verify_pilot()
    print(json.dumps(dict(version=VERSION,train=protocol['train'],validation=protocol['validation']),ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','verify'])
    args=parser.parse_args()
    if args.command=='prepare':
        prepare()
    else:
        manifest,*_=verify_pilot()
        print(json.dumps(dict(verified=True,version=manifest['version'])))


if __name__=='__main__':
    main()
