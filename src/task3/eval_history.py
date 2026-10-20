"""Explicit allowlist of historical metadata; never inspect inference outputs.

Prepared records contribute identity only (prompt/completion/teacher prose are
not retained). Corpus exposure is distinct from a selected experiment ID. Every
historical source/family is denied for future training, including old heldout.
"""
from __future__ import annotations

import json
from pathlib import Path
import runpy

from src.task3.eval_snapshot import identity, sha_file, structural_shingles

METADATA_PATHS = (
    'outputs/task3/round14/selection-A/development-selection.json',
    'outputs/task3/round14/selection-B/development-selection.json',
    'outputs/task3/round14/selection-B-oracle/development-selection.json',
    'outputs/task3/round14/selection-freeze.json',
    'outputs/task3/round15/development-selection.json',
    'outputs/task3/round15/development-probe-freeze.json',
    'outputs/task3/round15/example-candidate-selection.json',
    'outputs/task3/round15/example-source-shortlist.json',
    'outputs/task3/round16/development-selection.json',
    'reports/task3/TASK3_ROUND16_FREEZE_20261020.json',
    'reports/task3/TASK3_ROUND17_FREEZE_20261020.json',
    'reports/task3/TASK3_ROUND18_FREEZE_20261020.json',
    'reports/task3/TASK3_ROUND18_TARGET_PROVENANCE_20261020.json',
    'reports/task3/TASK3_ROUND18_PILOT_ELIGIBILITY_20261020.json',
)
BANK_PATHS = tuple(f'outputs/task3/{r}/{n}.json' for r,n in (
    ('round15','train-examples.draft'), ('round15','train-examples'),
    ('round16','train-examples'), ('round17','train-examples')))
PARTITIONS = ('real-train', 'real-val', 'synthetic-train', 'synthetic-heldout')


def historical_inventory(repo, archive):
    repo = Path(repo)
    input_hashes, variants, by_id, counts = {}, {}, {}, {}
    def read(relative):
        path = repo/relative
        input_hashes[relative] = sha_file(path)
        return json.loads(path.read_text())
    def add(row, exposure, direct=False):
        r = identity(row)
        if any(not r.get(k) for k in ('sample_id','group','family','source_sha256','code_identity','renamed_identity')):
            raise ValueError('incomplete historical identity: '+str(r.get('sample_id')))
        key = (r['sample_id'], r['source_sha256'])
        entry = variants.setdefault(key, dict(r, exposures=[], direct_experiment_use=False,
            structural_shingles=sorted(structural_shingles(row['code'])) if 'code' in row else []))
        if exposure not in entry['exposures']:entry['exposures'].append(exposure)
        entry['direct_experiment_use'] |= direct
        by_id.setdefault(r['sample_id'], []).append(entry)
        return entry
    # Archive root is inventoried, but not every root ID was actually used.
    root_by = {r['sample_id']: r for r in archive['records']}
    for part in PARTITIONS:
        relative = f'data/processed/task3/{part}.jsonl'
        p = repo/relative; input_hashes[relative] = sha_file(p)
        rows = [json.loads(line)['record'] for line in p.read_text().splitlines() if line]
        counts['prepared_'+part.replace('-','_')] = len(rows)
        for row in rows:
            add(row, 'R13 corpus/static pipeline exposure' if part.endswith('train') else 'old repeatedly evaluated '+part,
                direct=part.endswith('val') or part.endswith('heldout'))
    # Root metadata supplies exact new annotation-source identities; old variants stay too.
    for r in archive['heldout']:
        add(r, 'current ZIP heldout reserved; prior evaluation status unknown', direct=False)
    old_path = 'data/synth/generate-dataset/task3_feedback.json'
    old = read(old_path)
    old_ids = {r['sample_id'] for r in old['samples']}
    new_ids = sorted(set(root_by)-old_ids)
    def expose(sid, reason, direct=True):
        if sid in root_by:
            add(root_by[sid], reason, direct=direct)
        elif sid in by_id:
            for entry in by_id[sid]:
                if reason not in entry['exposures']:entry['exposures'].append(reason)
                entry['direct_experiment_use'] |= direct
        else:
            raise ValueError('historical ID has no source identity: '+sid)
    metadata = {p:read(p) for p in METADATA_PATHS}
    # Capture all R14 development selections, including superseded pre-freeze probes.
    for path in sorted((repo/'outputs/task3/round14').glob('*/development-selection.json')):
        relative = path.relative_to(repo).as_posix()
        if relative not in metadata:metadata[relative] = read(relative)
    for p,d in metadata.items():
        if 'selected_ids' in d and 'example-candidate-selection' not in p:
            for sid in d['selected_ids']:expose(sid,p)
        if 'selection' in d:
            for sid in d['selection'].get('selected_ids',[]):expose(sid,p)
        if 'round18' in p.lower() and 'sets' in d:
            for name,rr in d['sets'].items():
                for r in rr:expose(r['sample_id'], 'R18 '+name)
        if 'TARGET_PROVENANCE' in p:
            counts['r18_training_ids'] = len(d['provenance'])
            for r in d['provenance']:expose(r['sample_id'],'R18 supervised target/optimizer',direct=True)
        if 'example-candidate-selection' in p:
            for r in d['records']:expose(r['sample_id'],'R15 example candidate source pool; output use not implied',False)
        if 'example-source-shortlist' in p:
            for r in d['candidates']:expose(r['sample_id'],'R15 source-reviewed example shortlist',True)
    for p in BANK_PATHS:
        for i,r in enumerate(read(p)):
            parent = r.get('provenance',{}).get('parent_id')
            sid = r.get('sample_id',r.get('id',f'{p}:{i}'))
            if parent:
                expose(parent, p+' parent',True)
            elif sid in root_by:
                expose(sid,p,True)
            family = r.get('provenance',{}).get('family')
            if not family:
                family = root_by[sid]['family'] if sid in root_by else root_by[parent]['family']
            add(dict(sample_id=sid,family=family,group='bank:'+sid,code=r['code']),p+' full bank source',True)
    # R13 artificial development/check sources are protected as well as the corpus.
    fixture = 'tests/task3_discovery_cases.py'
    input_hashes[fixture] = sha_file(repo/fixture)
    definitions = runpy.run_path(str(repo/fixture))
    for name in ('development_cases','independent_cases'):
        for case in definitions[name]():
            add(dict(sample_id='R13-'+case.name,family=case.exam,group=case.group,code=case.code),
                'R13 artificial '+name,True)
    entries = sorted(variants.values(),key=lambda r:(r['sample_id'],r['source_sha256']))
    for e in entries:e['exposures'].sort()
    return dict(entries=entries,input_hashes=input_hashes,counts=counts,new_source_ids=new_ids,
        exposure_policy='Corpus/source pool exposure does not imply model-output use. Direct use is tracked separately. No source/family is asserted blind.',
        strict_train_policy='All listed identities and families denied before targets AND before optimizer; no family exception for current corpus.')
