#!/usr/bin/env python3
"""Exclusive TRAIN-only contract snapshot. Import/verify never loads a model."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
WORK=REPO/'outputs/task3/diagnosis-contract-v1-20261021'
FROZEN=WORK/'frozen'
CONFIG=REPO/'configs/task3/diagnosis_contract_v1_20261021.json'
PUBLIC=REPO/'reports/task3/TASK3_CONTRACT_V1_FREEZE_20261021.json'
SUP=REPO/'outputs/task3/train-supplement-v1-20261021/source-frozen'
PARENT=REPO/'reports/task3/TASK3_TRAIN_SUPPLEMENT_V1_FREEZE_20261021.json'


def read(path):return json.loads(Path(path).read_bytes())


def raw_json(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(raw_json(value))
    path.chmod(0o600)


def project_domain(value):
    """Keep input constraints, excluding annotation/witness commentary.

    Source-only reviewer checks the resulting thirty domains before freeze.
    This is not a general natural-language leakage detector.
    """
    parts=list(value.values()) if isinstance(value,dict) else [value]
    kept=[]
    for part in parts:
        part=re.sub(r'\s+unless the finding is specifically about P1','',part)
        for sentence in re.split(r'(?<=\.)\s+',part):
            if not re.search(r'counterexample|erroneous|\bfinding\b|independently verified|recursion depth',sentence,re.I):
                kept.append(sentence.strip())
    if not any(kept):raise ValueError('domain projection contains no input constraints')
    return ' '.join(s for s in kept if s)


def build_inputs(sources,selection,*,expected_count=30):
    by={r['sample_id']:r for r in sources};seen=set();rows=[]
    if len(by)!=len(sources) or len(selection)!=expected_count:raise ValueError('source/selection count mismatch')
    for item in selection:
        sid,level=item.get('sample_id'),item.get('level')
        if isinstance(level,str) and level in ('L1','L2','L3','L4'):level=int(level[1])
        if sid in seen or sid not in by or type(level) is not int or level not in (1,2,3,4):raise ValueError('invalid selected ID/Level')
        seen.add(sid);r=by[sid]
        if hashlib.sha256(r['code'].encode()).hexdigest()!=r['source_sha256']:raise ValueError('source hash drift')
        domain=project_domain(r['domain'])
        exam=r['parent_exam']
        task=dict(statement=exam['statement']+'\n\nMiền đầu vào áp dụng cho lượt kiểm tra TRAIN này: '+domain,
            problems=[{k:p[k] for k in ('pid','statement','prototype') if k in p} for p in exam.get('problems',[])],
            grading_policy=exam.get('grading_policy'),code=r['code'],domain=domain,
            compiler_evidence=dict(status='unavailable',program_executed=False,reason='No isolated compiler evidence; no compile expectation or reference finding is supplied.'))
        rows.append(dict(request_id=f'contract-v1:{sid}@L{level}',sample_id=sid,kind='primary',requested_level=level,task=task))
    return rows


def write_snapshot(root,artifacts,header):
    root=Path(root)
    if root.exists():raise FileExistsError('snapshot already exists; never overwrite')
    if any(Path(n).name!=n or n in {'manifest.json','seal.json'} for n in artifacts):raise ValueError('unsafe snapshot member')
    root.mkdir(parents=True)
    for name,value in artifacts.items():write_new(root/name,value)
    manifest={**header,'private_files_sha256':{n:sha(root/n) for n in artifacts}}
    write_new(root/'manifest.json',manifest)
    write_new(root/'seal.json',dict(files_sha256={**manifest['private_files_sha256'],'manifest.json':sha(root/'manifest.json')}))
    return manifest


def verify_snapshot(root):
    root=Path(root);seal=read(root/'seal.json')
    for name,expected in seal['files_sha256'].items():
        if Path(name).name!=name or sha(root/name)!=expected:raise ValueError('snapshot hash mismatch: '+name)
    manifest=read(root/'manifest.json')
    if manifest['private_files_sha256']!={n:h for n,h in seal['files_sha256'].items() if n!='manifest.json'}:raise ValueError('snapshot manifest/seal hash mismatch')
    return manifest


def prepare():
    if FROZEN.exists() or PUBLIC.exists():raise FileExistsError('experiment freeze exists')
    parent=read(PARENT)
    # Verify only the existing TRAIN source bytes. No parent verifier that opens
    # Evaluation v2, target prose, or public sources is invoked here.
    for name,h in parent['private_files_sha256'].items():
        if sha(SUP/name)!=h:raise ValueError('sealed TRAIN source drift: '+name)
    selection=read(WORK/'selection.private.json')
    if sha(SUP/'approved.private.json')!=selection['source_file_sha256']:raise ValueError('selection source hash drift')
    all_sources=read(SUP/'approved.private.json');selected=selection['selected'];rows=build_inputs(all_sources,selected)
    refs=read(WORK/'source-reference.private.json')
    if {r['sample_id'] for r in refs['records']}!={r['sample_id'] for r in rows}:raise ValueError('reference source membership mismatch')
    source_by={r['sample_id']:r for r in all_sources};private_sources=[source_by[r['sample_id']] for r in rows]
    for r in refs['records']:
        if r['source_sha256']!=source_by[r['sample_id']]['source_sha256']:raise ValueError('reference source hash mismatch')
    requests=[dict(request_id=r['request_id'],sample_id=r['sample_id'],kind='primary',level=r['requested_level']) for r in rows]
    # Pin transitive existing runtime files without consulting their data.
    files={str(p.relative_to(REPO)) for p in (REPO/'src').rglob('*.py')}
    files|={'scripts/task3_contract_v1_prepare.py','scripts/task3_contract_v1_infer.py','configs/task3/diagnosis_contract_v1_20261021.json'}
    header=dict(version='task3-diagnosis-contract-v1-20261021',head_before=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        work_dir=str(WORK),private_root=str(FROZEN),source_parent_sha256=sha(PARENT),source_seal_sha256=sha(SUP/'seal.json'),
        selection_sha256=sha(WORK/'selection.private.json'),reference_sha256=sha(WORK/'source-reference.private.json'),configuration_sha256=sha(CONFIG),
        implementation_sha256={f:sha(REPO/f) for f in sorted(files)},requests=requests,selection_counts=selection['counts'],
        source_hashes={r['sample_id']:r['source_sha256'] for r in private_sources},
        annotation_provenance='Sealed supplement-v1 agent-authored source labels; official archive annotation-v2 unavailable for SUP1 codes.',
        source_review='Fresh static agent review; not human-verified; no source compilation/execution.',
        prior_exposed_train_development=True,blind_benchmark=False,adapter=False,training=False,no_public_inference=True,
        one_pass_each=['R15','SHORT'],frozen_before_generation=True)
    manifest=write_snapshot(FROZEN,{'config.json':read(CONFIG),'inputs.private.json':rows,'sources.private.json':private_sources,
        'reference.private.json':refs,'selection.private.json':selection,
        'review-rubric.json':read(WORK/'review-rubric.private.json')},header)
    write_new(PUBLIC,manifest)
    return dict(sources=30,manifest_sha256=sha(PUBLIC),seal_sha256=sha(FROZEN/'seal.json'),counts=selection['counts'])


def verify():
    manifest=verify_snapshot(FROZEN)
    if raw_json(manifest)!=PUBLIC.read_bytes():raise ValueError('public freeze hash mismatch')
    for f,h in manifest['implementation_sha256'].items():
        if sha(REPO/f)!=h:raise ValueError('runtime hash drift: '+f)
    if sha(PARENT)!=manifest['source_parent_sha256'] or sha(SUP/'seal.json')!=manifest['source_seal_sha256']:raise ValueError('TRAIN parent drift')
    if sha(WORK/'selection.private.json')!=manifest['selection_sha256'] or sha(WORK/'source-reference.private.json')!=manifest['reference_sha256']:raise ValueError('selection/reference drift')
    rows=read(FROZEN/'inputs.private.json');sources=read(FROZEN/'sources.private.json');selection=read(FROZEN/'selection.private.json')
    if build_inputs(sources,selection['selected'])!=rows:raise ValueError('model input projection drift')
    return manifest,read(FROZEN/'config.json'),rows


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','verify']);args=parser.parse_args()
    if args.command=='prepare':result=prepare()
    else:
        manifest,_,rows=verify();result=dict(verified=True,requests=len(rows),manifest_sha256=sha(PUBLIC))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
