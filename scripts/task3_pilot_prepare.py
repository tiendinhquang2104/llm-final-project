#!/usr/bin/env python3
"""Freeze one TRAIN-only pilot before evaluation predictions; never run GPU work."""
from __future__ import annotations
from collections import Counter
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from scripts.task3_train_supplement import verify as verify_supplement
from scripts.task3_freeze_eval_v2 import verify as verify_eval
from src.task3.eval_snapshot import sha_bytes,sha_file,json_bytes,write_new,write_seal,verify_seal
from src.task3.pilot_protocol import diagnosis_messages,feedback_messages,parse_diagnosis,normalize_task,source_split,split_examples
from src.task3.train_supplement import require_supplement_isolation,summarize

WORK=REPO/'outputs/task3/pilot-v1-20261021';FROZEN=WORK/'frozen'
SUP=REPO/'outputs/task3/train-supplement-v1-20261021'
CONFIG=REPO/'configs/task3/pilot_v1_20261021.json'
MANIFEST=REPO/'reports/task3/TASK3_PILOT_V1_FREEZE_20261021.json'
FILES=('src/task3/pilot_protocol.py','src/task3/pilot_training.py','scripts/task3_pilot_prepare.py',
       'scripts/task3_pilot_train.py','scripts/task3_pilot_infer.py','src/task3/inference.py',
       'src/task3/train.py','src/task3/round15.py','src/task3/round15_runner.py','configs/task3/pilot_v1_20261021.json')
# Pin transitive local runtime imports as well as directly called entry points.
FILES=tuple(sorted(set(FILES)|{str(p.relative_to(REPO)) for p in (REPO/'src').rglob('*.py')}
                   |{str(p.relative_to(REPO)) for p in (REPO/'scripts').glob('task3*.py')
                     if p.name!='task3_pilot_report.py'}))


def read(path):return json.loads(Path(path).read_text())


def training_view(drafts,sources):
    by={r['sample_id']:r for r in sources};result=[]
    for d in drafts:
        r=by[d['sample_id']]
        task=d['input'] if d['kind']=='diagnostic' else d['input']['task']
        if normalize_task(task)['code']!=r['code']:raise ValueError('draft/source code mismatch')
        if d['kind']=='diagnostic':
            parse_diagnosis(json.dumps(d['output']),task)
            messages=diagnosis_messages(task);level=None;weight=2.
        else:
            diagnosis=d['input']['diagnosis'];parse_diagnosis(json.dumps(diagnosis),task)
            level=d['input']['requested_level'];messages=feedback_messages(task,diagnosis,level);weight=2/3
        result.append(dict(sample_id=d['sample_id'],example_id=d['example_id'],kind=d['kind'],level=level,
            messages=messages,completion=json.dumps(d['output'],ensure_ascii=False,sort_keys=True),loss_weight=weight,
            source_sha256=sha_bytes(r['code'].encode()),sealed_draft_sha256=sha_bytes(json_bytes(d))))
    return result


def review_selection(selection,requests,count=24):
    ordered=sorted(selection,key=lambda r:sha_bytes(('seed42:'+r['sample_id']).encode()))
    chosen={}
    for r in ordered:chosen.setdefault(r['family'],r)
    ids={r['sample_id'] for r in chosen.values()}
    for level in (1,2,3,4):
        if not any(r['level']==level for r in chosen.values()):
            r=next(r for r in ordered if r['level']==level);ids.add(r['sample_id'])
    for r in ordered:
        if len(ids)>=count:break
        ids.add(r['sample_id'])
    if len(ids)!=count:raise ValueError('review source quota inconsistent')
    return [r for r in requests if r['kind']=='primary' and r['sample_id'] in ids]


def data():
    verify_supplement();ev=verify_eval()
    sources=read(SUP/'source-frozen/approved.private.json');drafts=read(SUP/'target-frozen/draft-targets.private.json')
    excluded=[r for r in sources if r['sample_id']=='SUP1-PALIN-008']
    if len(excluded)!=1 or sha_bytes(excluded[0]['code'].encode())!='63346df35c3bd3e334e6399d003e5b3ef78c29297895c55b4aa8bf6dcc3b1ee0':
        raise ValueError('quality exclusion source binding mismatch')
    exclusions=[dict(sample_id=r['sample_id'],source_sha256=sha_bytes(r['code'].encode()),
        removed_examples=[dict(example_id=d['example_id'],sha256=sha_bytes(json_bytes(d))) for d in drafts if d['sample_id']==r['sample_id']],
        reason='Conservative exclusion: L3 repeated endpoint comparison omits preserving earlier mismatch; no sealed target edited.',
        audit_sha256=sha_file(WORK/'train-quality-audit.private.json')) for r in excluded]
    active=[r for r in sources if r['sample_id'] not in {e['sample_id'] for e in exclusions}]
    drafts=[d for d in drafts if d['sample_id'] in {r['sample_id'] for r in active}]
    registry=read(SUP/'source-frozen/guard-registry.private.json')
    gate=require_supplement_isolation(active,registry,stage='before_targets')
    examples=training_view(drafts,active)
    train_ids,val_ids=source_split(active,seed=42,validation_fraction=.2)
    train,val=split_examples(examples,train_ids,val_ids)
    trainsources=[r for r in active if r['sample_id'] in train_ids]
    valsources=[r for r in active if r['sample_id'] in val_ids]
    review=review_selection(ev['evaluation_selection'],ev['requests'])
    return dict(active=active,train=train,validation=val,train_sources=trainsources,validation_sources=valsources,
                registry=registry,exclusions=exclusions,review=review,gate=gate,evaluation=ev)


def prepare():
    if FROZEN.exists() or MANIFEST.exists():raise FileExistsError('pilot freeze exists; no overwrite')
    d=data();cfg=read(CONFIG)
    from src.task3.inference import load_tokenizer,tokenizer_metadata
    from src.task3.pilot_training import encode_pilot_examples
    os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'))
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    tok=load_tokenizer(cfg)
    _,ta=encode_pilot_examples(tok,d['train'],cfg['max_seq_length'])
    _,va=encode_pilot_examples(tok,d['validation'],cfg['max_seq_length'])
    artifacts={'config.json':cfg,'train-examples.private.json':d['train'],'validation-examples.private.json':d['validation'],
        'train-sources.private.json':d['train_sources'],'validation-sources.private.json':d['validation_sources'],
        'registry.private.json':d['registry'],'exclusions.json':d['exclusions'],'paired-review-selection.json':d['review'],
        'token-audit.json':dict(train=ta,validation=va,tokenizer=tokenizer_metadata(tok)),
        'before-targets-gate.json':d['gate']}
    hashes={name:sha_bytes(json_bytes(value)) for name,value in artifacts.items()}
    manifest=dict(version='task3-pilot-v1-20261021',head_before=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        private_root=str(FROZEN),configuration_sha256=sha_file(CONFIG),private_files_sha256=hashes,
        implementation_sha256={f:sha_file(REPO/f) for f in FILES},
        parent_sha256={f:sha_file(REPO/f) for f in ('reports/task3/TASK3_TRAIN_SUPPLEMENT_V1_FREEZE_20261021.json',
            'reports/task3/TASK3_TRAIN_SUPPLEMENT_V1_TARGETS_20261021.json','reports/task3/TASK3_EVAL_V2_FREEZE_20261021.json')},
        quality_audit_sha256=sha_file(WORK/'train-quality-audit.private.json'),exclusions=d['exclusions'],
        retained=summarize(d['active']),train=summarize(d['train_sources']),internal_validation=summarize(d['validation_sources']),
        train_ids=[r['sample_id'] for r in d['train_sources']],validation_ids=[r['sample_id'] for r in d['validation_sources']],
        train_source_hashes={r['sample_id']:sha_bytes(r['code'].encode()) for r in d['train_sources']},
        validation_source_hashes={r['sample_id']:sha_bytes(r['code'].encode()) for r in d['validation_sources']},
        token_audit=dict(train=ta,validation=va),paired_review_selection=d['review'],
        evaluation_requests=d['evaluation']['requests'],evaluation_model_inputs_sha256=d['evaluation']['private_files_sha256']['model-inputs.private.json'],
        checkpoint_selection='Lowest internal TRAIN-only equal-source/equal-task completion loss among epochs1/2; earliest tie.',
        loss_balance='All examples once per epoch; per-example mean completion CE times2 diagnosis or2/3 eachfeedback.',
        no_truncation=True,controlled_holdout=True,prior_exposure=True,blind_benchmark=False,
        teacher_forcing='TRAIN feedback sees reviewed target diagnosis; inference sees only model-predicted diagnosis.',
        domain_policy='TRAIN uses scoped domain assumptions present in sealed input; evaluation uses only explicit problem constraints, no reference domains.',
        language_limitation='Sealed diagnostic domain/evidence includes mixed English prose and stale author_static provenance; preserved, not silently relabeled.',
        frozen_before_optimizer=True,frozen_before_evaluation_predictions=True,no_public_inference=True)
    digest=sha_bytes(json_bytes(manifest))
    for name,value in artifacts.items():write_new(FROZEN/name,value)
    write_new(FROZEN/'public-manifest.json',manifest)
    write_seal(FROZEN/'seal.json',{**hashes,'public-manifest.json':digest})
    write_new(MANIFEST,manifest)
    return dict(manifest_sha256=sha_file(MANIFEST),seal_sha256=sha_file(FROZEN/'seal.json'),
                train_sources=len(d['train_sources']),validation_sources=len(d['validation_sources']),token_audit=manifest['token_audit'])


def verify_pilot():
    verify_supplement();verify_eval();m=read(MANIFEST)
    verify_seal(FROZEN/'seal.json',expected_hashes={**m['private_files_sha256'],'public-manifest.json':sha_file(MANIFEST)})
    for f,h in {**m['implementation_sha256'],**m['parent_sha256']}.items():
        if sha_file(REPO/f)!=h:raise ValueError('pilot implementation/parent drift: '+f)
    if sha_file(WORK/'train-quality-audit.private.json')!=m['quality_audit_sha256']:raise ValueError('quality audit drift')
    cfg=read(FROZEN/'config.json');train=read(FROZEN/'train-examples.private.json');val=read(FROZEN/'validation-examples.private.json')
    sources=read(FROZEN/'train-sources.private.json');vs=read(FROZEN/'validation-sources.private.json');reg=read(FROZEN/'registry.private.json')
    if {r['sample_id'] for r in sources}&{r['sample_id'] for r in vs}:raise ValueError('source split leakage')
    if [r['sample_id'] for r in sources]!=m['train_ids'] or [r['sample_id'] for r in vs]!=m['validation_ids']:
        raise ValueError('source split membership drift')
    # Rebind the full view to original sealed drafts, not just a mutable cache.
    drafts=read(SUP/'target-frozen/draft-targets.private.json');by={r['example_id']:r for r in drafts}
    for examples,ss in ((train,sources),(val,vs)):
        if training_view([by[e['example_id']] for e in examples],ss)!=examples:
            raise ValueError('training view differs from original sealed draft/source')
    require_supplement_isolation(sources,reg,stage='before_targets')
    return m,cfg,train,val,sources,reg


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=('prepare','verify'))
    args=ap.parse_args()
    if args.command=='prepare':out=prepare()
    else:
        m,cfg,tr,va,sources,reg=verify_pilot()
        out=dict(verified=True,train_sources=len(sources),validation_sources=len(m['validation_ids']),train_examples=len(tr),validation_examples=len(va))
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
