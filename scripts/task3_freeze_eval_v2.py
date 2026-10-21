#!/usr/bin/env python3
"""Independent v2 family-first preparation, prefreeze report, seal and guards.

No model, training or inference commands. Existing v1 is read-only and verified.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import random
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from scripts.task3_freeze_eval import verify_snapshot as verify_v1, support, METRIC_DEFINITIONS
from src.task3.eval_snapshot import (LABEL_SPACE, LEVEL_CONTRACTS, identity, json_bytes, read_archive,
    sha_bytes, sha_file, write_new, write_seal, verify_seal)
from src.task3.eval_history import historical_inventory
from src.task3.eval_v2 import (make_guard_registry, make_registries, require_train_isolation,
    select_train, validate_partition, v2_references, apply_manual_review, validate_reference_origin, require_parent_binding, MATCH_KEYS, THRESHOLD)
from src.task3.frozen_eval import evaluate, review_template

WORK=REPO/'outputs/task3/eval-freeze-v2-20261021'
MANIFEST=REPO/'reports/task3/TASK3_EVAL_V2_FREEZE_20261021.json'
FILES=('src/task3/eval_v2.py','scripts/task3_freeze_eval_v2.py','tests/test_task3_eval_v2.py')
CF_IDS=('SYN-COUNTGT-0000','SYN-MINA-0004','SYN-SUMB-0005','SYN-MAXDIFF-0003','SYN-PROD-0017',
    'SYN-ARM-0027','SYN-BASE2-0006','SYN-COUNTUPPER-0007','SYN-DIGITSUM-0016','SYN-FACT-0008',
    'SYN-GCDARR-0009','SYN-DISTINCT-0001')
L3=('SYN-GCDARR-0009','SYN-MAXDIFF-0003','SYN-MINA-0004','SYN-PRIME-0010',
    'SYN-DIGITSUM-0016','SYN-PROD-0017','SYN-FACT-0001','SYN-COUNTUPPER-0001')
L4=('SYN-ARM-0008','SYN-BASE2-0006','SYN-COUNTGT-0000','SYN-REVSTR-0001','SYN-PERFECT-0011','SYN-SUMEVEN-0008')
FORCED={1:('SYN-ARM-0027','SYN-ARM-0000','SYN-SECONDMAX-0009'),
        2:('SYN-DISTINCT-0017','SYN-FACT-0008','SYN-PRIME-0005','SYN-FIB-0000')}
POLICY=dict(version='evaluation-v2-family-first-20261021',controlled_holdout=True,blind_benchmark=False,
    family_partition='10 TRAIN /18 EVALUATION families fixed before source selection; never optimize membership after eligibility counts',
    prior_exposure='All28 families have prior exposure. This metadata does not ban an entire TRAIN family.',
    id_protection='Historical examples/targets/output-reviewed IDs, reserved heldout and all86 v1 evaluation identities blocked individually with group/code/rename/near variants.',
    near_policy='Identifier-erased5-token shingle Jaccard>=0.85 blocks train against ALL evaluation-family sources, historical used/reserved identities. Mandatory independent source review also excludes obvious template clones below threshold; neither step proves absence of every semantic duplicate.',
    train_policy='Fixed prepared synthetic-train membership only; unique source/renamed code; sealed whitelist; recompute actual code and enforce both before_targets and before_optimizer. Eligibility is isolation eligibility, not correctness/target verification.',
    evaluation_policy='Only assigned evaluation families.56 v1 source-reviewed references plus4 additional invariant-reviewed scoped-clean sources; no model outputs used.',
    level_policy='60 primary:19/27/8/6 at L1/2/3/4. Predeclared source-level assignments ensure L3 covers nine supported source groups; remaining L1/2 slots seeded42. Never infer taxonomy from Level.',
    style_policy='Only an explicit statement/policy requirement plus an actual source violation can support style. Comments/TODO/unused names alone do not. Explicit Armstrong pow restriction checked; no active calls present in its corpus.',
    model_scope='Qwen2.5-Coder-7B-Instruct only (<10B); no model loading/training/inference performed.')


def levels(records):
    if len(records)!=60:raise ValueError('v2 reviewed selection must contain60 sources')
    result={sid:3 for sid in L3};result.update({sid:4 for sid in L4})
    result.update({sid:l for l,ids in FORCED.items() for sid in ids})
    ids={r['sample_id'] for r in records}
    if not set(result)<=ids:raise ValueError('predeclared Level source missing')
    remaining=sorted(ids-set(result));slots=[1]*(19-len(FORCED[1]))+[2]*(27-len(FORCED[2]))
    random.Random(42).shuffle(slots)
    if len(slots)!=len(remaining):raise ValueError('Level quota mismatch')
    result.update(zip(remaining,slots));return result


def plan():
    v1m=verify_v1();old=json.loads((Path(v1m['private_root'])/'reference.private.json').read_text())
    archive=read_archive(REPO/'generate-dataset_v2.zip')
    partition=json.loads((WORK/'family-partition.json').read_text())
    require_parent_binding(partition,sha_file(REPO/'reports/task3/TASK3_EVAL_V1_FREEZE_20261021.json'))
    validate_partition(partition,{r['family'] for r in archive['records']})
    history=historical_inventory(REPO,archive)
    evaluation_pool=[r for r in archive['records'] if r['family'] in partition['evaluation_families']]
    registries=make_registries(history,old['records'],evaluation_pool)
    prepared_ids={json.loads(line)['record']['sample_id'] for line in (REPO/'data/processed/task3/synthetic-train.jsonl').read_text().splitlines()}
    train,rejections=select_train(archive['records'],prepared_ids,partition,registries['training_protected_identities'])
    preliminary_train_count=len(train)
    manual_path=WORK/'train-near-review.private.json'
    manual_review=json.loads(manual_path.read_text()) if manual_path.exists() else None
    if manual_review is not None:
        train,manual_rejected=apply_manual_review(train,manual_review)
        for r in manual_rejected:
            rejections.append(dict(sample_id=r['sample_id'],family=r['family'],reason='independent source review: below-threshold near-template',matches=[]))
    records=v2_references(old['records'],json.loads((WORK/'additional-reference.private.json').read_text()),partition)
    validate_reference_origin(records,archive['records'])
    lv=levels(records)
    for r in records:
        r['level']=lv[r['sample_id']]
        r['reference_provenance']='v1 source-only reference re-used after family partition; no previous model-output use' if r['sample_id'] in {o['sample_id'] for o in old['records']} else 'additional v2 source-only invariant review'
    records.sort(key=lambda r:r['sample_id'])
    requests=[dict(request_id=f'v2:{r["sample_id"]}@primary-L{r["level"]}',sample_id=r['sample_id'],level=r['level'],kind='primary') for r in records]
    requests += [dict(request_id=f'v2:{sid}@cf-L{level}',sample_id=sid,level=level,kind='counterfactual') for sid in CF_IDS for level in (1,2,3)]
    by={r['sample_id']:r for r in records};inputs=[]
    for req in requests:
        r=by[req['sample_id']]
        inputs.append(dict(request_id=req['request_id'],sample_id=r['sample_id'],kind=req['kind'],requested_level=req['level'],
            task=dict(statement=r['statement'],problems=r['problems'],grading_policy=r['grading_policy'],student_code=r['code'],
                compiler_evidence=r['compiler_evidence'],allowed_labels=list(LABEL_SPACE))))
    guard=make_guard_registry(train,registries['training_protected_identities'],partition['train_families'],partition['evaluation_families'])
    guard['family_exposure']=registries['family_exposure']
    for stage in ('before_targets','before_optimizer'):require_train_isolation(train,guard,stage=stage)
    audit=json.loads((WORK/'disagreement-review.private.json').read_text())
    if isinstance(audit,list):audit={'records':audit}
    # Audit all19, including TRAIN-family cases; none becomes a training target.
    expected={r['sample_id'] for r in old['records'] if r['annotation_disagreement']}
    if {r['sample_id'] for r in audit['records']}!=expected:raise ValueError('19-disagreement audit incomplete')
    return dict(partition=partition,archive=archive,history=history,registries=registries,guard_registry=guard,
        train_records=train,train_rejections=rejections,preliminary_train_count=preliminary_train_count,manual_review=manual_review,snapshot=dict(records=records,requests=requests,level_contracts=LEVEL_CONTRACTS),
        model_inputs=inputs,support=support(records),disagreement_review=audit)


def prefreeze_summary(data):
    train=data['train_records'];s=data['support']
    return dict(version=POLICY['version'],partition_sha256=sha_file(WORK/'family-partition.json'),
        manual_near_review_complete=data['manual_review'] is not None,preliminary_train_source_count=data['preliminary_train_count'],
        manual_near_review_sha256=sha_file(WORK/'train-near-review.private.json') if data['manual_review'] is not None else None,
        train_source_count=len(train),train_family_count=len({r['family'] for r in train}),
        train_by_family=dict(sorted(Counter(r['family'] for r in train).items())),
        assigned_train_families=data['partition']['train_families'],assigned_evaluation_families=data['partition']['evaluation_families'],
        train_families_with_no_eligible_sources=sorted(set(data['partition']['train_families'])-{r['family'] for r in train}),
        evaluation_source_count=len(data['snapshot']['records']),evaluation_family_count=len({r['family'] for r in data['snapshot']['records']}),
        requests=len(data['snapshot']['requests']),support=s,controlled_holdout=True,prior_exposure=True,blind_benchmark=False,
        train_identity_sha256=sha_bytes(json_bytes([identity(r) for r in train])),
        evaluation_identity_sha256=sha_bytes(json_bytes([dict(identity(r),level=r['level'],source_reference=r['source_reference']) for r in data['snapshot']['records']])))


def freeze():
    frozen=WORK/'frozen'
    if frozen.exists() or MANIFEST.exists():raise FileExistsError('v2 already exists; no overwrite')
    data=plan();summary=prefreeze_summary(data)
    if data['manual_review'] is None:raise ValueError('manual near-template review required before freeze')
    if json.loads((WORK/'prefreeze-final-report.json').read_text())!=summary:
        raise ValueError('prefreeze report drift; report counts before sealing')
    artifacts={'reference.private.json':data['snapshot'],'train-eligible.private.json':data['train_records'],
        'guard-registry.private.json':data['guard_registry'],'used-identity-registry.private.json':data['registries']['used_reserved_identities'],
        'family-exposure-registry.json':data['registries']['family_exposure'],
        'train-rejections.private.json':data['train_rejections'],'model-inputs.private.json':data['model_inputs'],
        'disagreement-review.private.json':data['disagreement_review'],'family-partition.json':data['partition'],
        'train-near-review.private.json':data['manual_review'],
        'prefreeze-final-report.json':summary,'policy.json':POLICY,'metric-definitions.json':METRIC_DEFINITIONS,
        'isolation-probe.json':json.loads((WORK/'isolation-probe.json').read_text()),
        'code-review.private.json':json.loads((WORK/'v2-code-review.private.json').read_text()),
        'code-review-followup.private.json':json.loads((WORK/'v2-code-review-followup.private.json').read_text()),
        'review-packet.private.json':{'disagreements':data['disagreement_review'],'conditional_disputed':[r for r in data['snapshot']['records'] if r['disputes'] or r['conditional_claims'] or r.get('conditional_findings')],'authority':'agent-reviewed, not human-verified'}}
    for name,value in artifacts.items():write_new(frozen/name,value)
    hashes={name:sha_file(frozen/name) for name in artifacts}
    v1m=verify_v1()
    source_inputs={name:sha_file(WORK/name) for name in ['family-partition.json','additional-reference.private.json','disagreement-review.private.json','prefreeze-final-report.json','isolation-probe.json','train-near-review.private.json','v2-code-review.private.json','v2-code-review-followup.private.json']}
    handoff=dict(version=POLICY['version'],policy=POLICY,summary=summary,private_root=str(frozen),private_files_sha256=hashes,
        parent_v1_manifest_sha256=sha_file(REPO/'reports/task3/TASK3_EVAL_V1_FREEZE_20261021.json'),
        partition_before_selection_sha256=sha_file(WORK/'family-partition.json'),source_inputs_sha256=source_inputs,
        implementation_sha256={**v1m['implementation_sha256'],**{p:sha_file(REPO/p) for p in FILES}},
        archive_sha256=data['archive']['archive_sha256'],archive_members_sha256=data['archive']['members_sha256'],
        historical_inputs_sha256=data['history']['input_hashes'],
        train_eligible=[identity(r) for r in data['train_records']],
        evaluation_selection=[dict(identity(r),level=r['level'],annotation_v2=r['annotation_v2'],source_reference=r['source_reference'],
            statement_sha256=r['statement_sha256'],reference_sha256=sha_bytes(json_bytes(r))) for r in data['snapshot']['records']],
        requests=data['snapshot']['requests'],no_model_calls=True,no_training=True)
    write_new(frozen/'handoff.json',handoff);write_new(MANIFEST,handoff)
    write_seal(frozen/'seal.json',{**hashes,'handoff.json':sha_file(MANIFEST)})
    print(json.dumps(dict(verified=True,manifest_sha256=sha_file(MANIFEST),seal_sha256=sha_file(frozen/'seal.json')),ensure_ascii=False))


def verify():
    verify_v1();m=json.loads(MANIFEST.read_text());p=Path(m['private_root'])
    if not p.resolve().is_relative_to((REPO/'outputs/task3').resolve()):raise ValueError('unsafe private root')
    verify_seal(p/'seal.json',expected_hashes={**m['private_files_sha256'],'handoff.json':sha_file(MANIFEST)})
    require_parent_binding(json.loads((p/'family-partition.json').read_text()),sha_file(REPO/'reports/task3/TASK3_EVAL_V1_FREEZE_20261021.json'),m['parent_v1_manifest_sha256'])
    if sha_file(p/'handoff.json')!=sha_file(MANIFEST):raise ValueError('handoff mismatch')
    for rel,h in {**m['implementation_sha256'],**m['historical_inputs_sha256']}.items():
        if sha_file(REPO/rel)!=h:raise ValueError('implementation/history drift: '+rel)
    for rel,h in m['source_inputs_sha256'].items():
        if sha_file(WORK/rel)!=h:raise ValueError('source review/partition drift: '+rel)
    if sha_file(REPO/'generate-dataset_v2.zip')!=m['archive_sha256']:raise ValueError('archive changed')
    return m


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('plan');sub.add_parser('freeze');sub.add_parser('verify')
    p=sub.add_parser('train-gate');p.add_argument('--candidates',type=Path,required=True);p.add_argument('--stage',choices=['before_targets','before_optimizer'],required=True)
    for command in ('evaluate','review-template'):
        p=sub.add_parser(command);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
        if command=='evaluate':p.add_argument('--ledger',type=Path)
    args=ap.parse_args()
    if args.command=='plan':
        summary=prefreeze_summary(plan());write_new(WORK/'prefreeze-final-report.json',summary);print(json.dumps(summary,ensure_ascii=False));return
    if args.command=='freeze':freeze();return
    m=verify();p=Path(m['private_root'])
    if args.command=='verify':print(json.dumps({'verified':True,'manifest_sha256':sha_file(MANIFEST),'seal_sha256':sha_file(p/'seal.json')}));return
    if args.command=='train-gate':
        rows=json.loads(args.candidates.read_text());reg=json.loads((p/'guard-registry.private.json').read_text())
        result=require_train_isolation(rows,reg,stage=args.stage);print(json.dumps(dict(result,candidates_sha256=sha_file(args.candidates),registry_sha256=sha_file(p/'guard-registry.private.json'))));return
    snapshot=json.loads((p/'reference.private.json').read_text());predictions=json.loads(args.predictions.read_text())
    result=review_template(snapshot,predictions) if args.command=='review-template' else evaluate(snapshot,predictions,json.loads(args.ledger.read_text()) if args.ledger else None)
    write_new(args.output,result);print(json.dumps({'output':str(args.output),'sha256':sha_file(args.output)}))


if __name__=='__main__':main()
