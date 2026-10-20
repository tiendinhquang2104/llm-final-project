#!/usr/bin/env python3
"""Prepare/seal/verify a source-only evaluation; offline scoring and train guard.

There is deliberately no inference, training, checkpoint, or public-data command.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.eval_snapshot import (LABEL_SPACE, LEVEL_CONTRACTS, IDENTITY_KEYS, ZIP_SHA256,
    assign_levels, identity, json_bytes, read_archive, require_train_isolation, sha_bytes,
    sha_file, structural_shingles, validate_review, verify_seal, write_new, write_seal)
from src.task3.eval_history import historical_inventory
from src.task3.frozen_eval import evaluate, review_template

WORK=REPO/'outputs/task3/eval-freeze-v1-20261021'
MANIFEST=REPO/'reports/task3/TASK3_EVAL_V1_FREEZE_20261021.json'
TRAIN_MANIFEST=REPO/'reports/task3/TASK3_EVAL_V1_TRAIN_EXCLUSION_20261021.json'
IMPLEMENTATION=('src/task3/eval_snapshot.py','src/task3/eval_history.py','src/task3/frozen_eval.py',
    'scripts/task3_freeze_eval.py','tests/test_task3_eval_snapshot.py',
    'tests/test_task3_frozen_eval.py','tests/test_task3_freeze_cli.py',
    'src/task3/schema.py','src/synth/taxonomy.py','src/synth/feedback.py')
CF_IDS=('SYN-ARM-0027','SYN-BASE2-0006','SYN-COUNT-0011','SYN-COUNTEVEN-0019',
    'SYN-COUNTGT-0000','SYN-COUNTUPPER-0007','SYN-DIGITSUM-0016','SYN-MAXARR-0000',
    'SYN-MAXDIFF-0008','SYN-PROD-0017','SYN-SUMB-0034','SYN-PRIME-0010')

METRIC_DEFINITIONS={
    'references':'annotation_v2 and source_reference always separate; neither selected by observed scores',
    'taxonomy':'all 10 labels; zero_division=0; macro includes unsupported labels; missing/schema/error/abstention contributes reference FN and never exact-clean',
    'source_reference_support':'null unresolved references excluded with explicit count; scoped-clean [] remains scoped to frozen domain',
    'unit':'one source for primary taxonomy; counterfactual requests scored separately; no triple weighting in primary results',
    'completion':'schema-valid completed / requested, with received/declared completed/schema error/unresolved/abstained/runtime error counts',
    'schema':'valid completed / declared completed plus explicit schema_error rows; feedback must be nonblank; strict output keys taxonomy_error and feedback',
    'invariance':'same taxonomy set on schema-valid complete L1/2/3 triples only; report requested/incomplete triples too',
    'feedback':'per-request external ledger, exact output SHA, reviewer, source evidence and rationale. Null/missing assessments pending, never scored as success/false.',
    'level_denominators':'disclosure L1 and repair leak L2 on all matching-level sources; useful L2 and feasible L3 only on confirmed source defects; false-clean/missing-core on confirmed defects',
    'semantic_limits':'agent review is not human ground truth or atomic-claim precision; no keyword/LLM judge certified as truth',
    'language':'Vietnamese and CJK semantic judgments require review; automated CJK Unicode diagnostic is separate',
    'strata':'report each metric by requested Level and single_problem/multi_problem, with requested/completed/reviewed/assessed supports',
    'counterexample_status':'symbolic source-derived counterexamples, not observed program executions; no compiler invocation or student-code execution in this snapshot',
}
POLICY={
    'version':'task3-evaluation-v1-20261021', 'selection':'source-only review shortlist, at most four independent byte/renamed identities per family, taxonomy strata and scoped-clean intent before any new outputs; no quota padding',
    'target_source_count':'60–100 if justified; 86 reviewed, including one disputed whitespace case retained as unresolved',
    'historical_isolation':'reject selected historical experiment IDs, groups, exact, token and renamed identity; corpus/source-pool exposure retained, not called blind',
    'levels':'six Level4; remaining levels assigned by seed42 shuffle after largest-remainder quotas 115:163:50; label-independent',
    'counterfactual':'12 predeclared IDs from evaluation, each requested at levels1/2/3; task payload identical',
    'near_duplicate':'identifier-erased 5-token shingle Jaccard >=0.85 is a review/block signal, not equivalence proof; all current-corpus families denied for training',
    'train_gate':'require_train_isolation with all identities, before_targets and before_optimizer; a new family must also pass source-bearing shingle screening; no fallback when metadata missing',
    'reference':'source/statement/prototype/prerequisite reviewed by agents; no teacher feedback references, no human-verified claim, all conditional claims separate',
    'model_scope':'Qwen/Qwen2.5-Coder-7B-Instruct only (<10B); no new model use in preparation; R18 adapter ineligible',
    'blind_benchmark':False, 'new_model_calls':0, 'training_runs':0,
}


def support(records):
    return dict(annotation_v2={l:sum(l in r['annotation_v2'] for r in records) for l in LABEL_SPACE},
        source_reference={l:sum(l in (r['source_reference'] or []) for r in records) for l in LABEL_SPACE},
        source_reference_known=sum(r['source_reference'] is not None for r in records),
        defect_status=dict(Counter(r['defect_status'] for r in records)),
        level={str(k):v for k,v in sorted(Counter(r['level'] for r in records).items())},
        exam_type=dict(Counter(r['exam_type'] for r in records)),
        family=dict(sorted(Counter(r['family'] for r in records).items())),
        evidence_status=dict(Counter(f['status'] for r in records for f in r['findings'])),
        evidence_kind=dict(Counter(f['evidence']['kind'] for r in records for f in r['findings'])),
        annotation_disagreements=sum(set(r['annotation_v2'])!=set(r['source_reference'] or []) for r in records if r['source_reference'] is not None),
        conditional_sources=sum(bool(r['conditional_claims'] or r.get('conditional_findings')) for r in records),
        conditional_finding_count=sum(len(r.get('conditional_findings',[])) for r in records),
        source_reference_by_level={str(level):{l:sum(l in (r['source_reference'] or []) for r in records if r['level']==level) for l in LABEL_SPACE} for level in (1,2,3,4)},
        source_reference_by_exam_type={t:{l:sum(l in (r['source_reference'] or []) for r in records if r['exam_type']==t) for l in LABEL_SPACE} for t in ('single_problem','multi_problem')},
        source_reference_families={l:sorted({r['family'] for r in records if l in (r['source_reference'] or [])}) for l in LABEL_SPACE})


def assemble(archive, history, reviews, selected_ids):
    """Pure assembly, no I/O: selection cannot depend on any prediction file."""
    if len(selected_ids)!=len(set(selected_ids)):
        raise ValueError('duplicate selected ID')
    by={r['sample_id']:r for r in archive['records']}
    rev={r['sample_id']:r for r in reviews}
    if len(rev)!=len(reviews) or set(rev)!=set(selected_ids):
        raise ValueError('duplicate/missing/extra source review')
    records=[];seen={k:set() for k in ('group','source_sha256','code_identity','renamed_identity')}
    direct=[r for r in history['entries'] if r.get('direct_experiment_use')]
    direct_index={k:{r[k] for r in direct} for k in IDENTITY_KEYS if k!='family'}
    for sid in selected_ids:
        r=dict(by[sid]);review=deepcopy(rev[sid])
        allowed_review_fields={'sample_id','defect_status','domain','clean_basis','source_reference','findings',
            'conditional_claims','disputes','must_not_claim','reviewer'}
        if set(review)-allowed_review_fields:
            raise ValueError('review contains immutable archive field or unknown field')
        validate_review(r,review)
        for k,values in seen.items():
            if r[k] in values:raise ValueError('duplicate selected '+k+': '+sid)
            values.add(r[k])
        for k,values in direct_index.items():
            if r[k] in values:raise ValueError('selected historical experiment identity: '+sid+' '+k)
        r.update(review)
        r['conditional_findings']=[f for f in r['findings'] if f['status']=='conditional']
        r['findings']=[f for f in r['findings'] if f['status']!='conditional']
        if r['source_reference'] is not None:
            r['source_reference']=[label for label in r['source_reference'] if any(f['label']==label for f in r['findings'])]
        r['new_source_in_zip']=sid in history['new_source_ids']
        r['exposure']='new source ID/bytes but previously exposed family/template' if r['new_source_in_zip'] else 'old corpus/source-pool exposure; no matched direct experiment identity'
        r['compiler_evidence']={'status':'unavailable','program_executed':False,
            'reason':'No isolated execution sandbox; static review only. Compile pass is never proof of correctness.'}
        r['annotation_disagreement']=None if r['source_reference'] is None else set(r['annotation_v2'])!=set(r['source_reference'])
        for f in r['findings']+r['conditional_findings']:
            positions=[];offset=0
            while (start:=r['code'].find(f['quote'],offset))>=0:
                end=start+len(f['quote']);positions.append(dict(start=start,end=end,
                    line_start=r['code'][:start].count('\n')+1,line_end=r['code'][:end].count('\n')+1));offset=end
            f['quote_spans']=positions
            f['span_policy']='All exact occurrences listed; function location disambiguates repeated text; quote linkage is not semantic proof.'
            f['feedback_rubric']={
                '1':{'required':['acknowledge unmet requirements without false-clean'],
                     'forbidden':['specific location','specific cause','repair direction','repair code']},
                '2':{'required':[f['location'],f['cause']], 'forbidden':['concrete repair direction','repair code']},
                '3':{'required':[f['location'],f['cause'],f['repair_direction']], 'forbidden':['complete solution']},
                '4':{'required':[f['cause'],'technically sound explanation'], 'allowed':['sample solution']}}
        records.append(r)
    levels=assign_levels(records)
    for r in records:r['level']=levels[r['sample_id']]
    primary=[dict(request_id=r['sample_id']+'@primary-L'+str(r['level']),sample_id=r['sample_id'],level=r['level'],kind='primary') for r in records]
    if not set(CF_IDS)<=set(selected_ids):raise ValueError('counterfactual source missing')
    cf=[dict(request_id=sid+'@cf-L'+str(level),sample_id=sid,level=level,kind='counterfactual') for sid in CF_IDS for level in (1,2,3)]
    requests=primary+cf
    by={r['sample_id']:r for r in records}
    inputs=[]
    for req in requests:
        r=by[req['sample_id']]
        inputs.append(dict(request_id=req['request_id'],sample_id=r['sample_id'],kind=req['kind'],requested_level=req['level'],
            task=dict(statement=r['statement'],problems=r['problems'],grading_policy=r['grading_policy'],student_code=r['code'],
                      compiler_evidence=r['compiler_evidence'],allowed_labels=list(LABEL_SPACE))))
    entries=[dict(r) for r in history['entries']]
    entries.extend(dict(identity(r),exposures=['frozen evaluation v1'],direct_experiment_use=False,
        structural_shingles=sorted(structural_shingles(r['code']))) for r in records)
    registry=dict(entries=entries,policy=POLICY['train_gate'],near_duplicate_threshold=0.85)
    # Exact duplicate metadata entries are useful exposure history, not extra sources.
    all_rows=archive['records']+archive['heldout']
    denied_families={r['family'] for r in entries}
    eligible=[r['sample_id'] for r in all_rows if r['family'] not in denied_families]
    if eligible:raise ValueError('unexpected current-corpus training family eligibility; audit policy')
    similarities=[]
    for r in records:
        sig=structural_shingles(r['code'])
        for old in history['entries']:
            prior=set(old.get('structural_shingles',[])); union=sig|prior
            score=len(sig&prior)/len(union) if union else 0
            if score>=0.85:
                similarities.append(dict(evaluation_id=r['sample_id'],historical_id=old['sample_id'],historical_source_sha256=old['source_sha256'],
                    score=round(score,6),same_family=r['family']==old['family'],direct_experiment_use=old['direct_experiment_use']))
    near=dict(definition=POLICY['near_duplicate'],evaluation_vs_history=similarities,
              admitted_train_overlaps=[],planned_train_eligible_ids=eligible,
              warning='Similarity is lexical evidence only; low score does not exclude semantic near-duplicates. Evaluation sources within a family share motifs.')
    meta=dict(support=support(records),new_source_count=sum(r['new_source_in_zip'] for r in records),
              completely_unseen_families=[],blind_benchmark=False,planned_train_eligible_count=len(eligible),
              current_zip_new_sources=[dict(sample_id=sid,selected=sid in selected_ids,
                  prior_direct_use=any(e['sample_id']==sid and e['direct_experiment_use'] for e in history['entries'])) for sid in history['new_source_ids']],
              near_duplicate_review_pairs=len(similarities))
    return dict(records=records,requests=requests,level_contracts=LEVEL_CONTRACTS),registry,inputs,meta,near


def prepare():
    frozen=WORK/'frozen'
    if frozen.exists() or MANIFEST.exists() or TRAIN_MANIFEST.exists():
        raise FileExistsError('snapshot already exists; never overwrite or reselect after output')
    archive=read_archive(REPO/'generate-dataset_v2.zip')
    history=historical_inventory(REPO,archive)
    reviews=sum([json.loads((WORK/f'review-{i}.private.json').read_text()) for i in range(3)],[])
    ids=json.loads((WORK/'selection-draft.private.json').read_text())+['SYN-PRIME-0010']
    snapshot,registry,inputs,meta,near=assemble(archive,history,reviews,ids)
    audit_names=[f'review-audit-{i}.private.json' for i in range(3)]+['inventory-review.private.json','code-review.private.json','code-review-followup.private.json']
    audits=[dict(file=name,sha256=sha_file(WORK/name),review=json.loads((WORK/name).read_text())) for name in audit_names]
    packet=[r for r in snapshot['records'] if r['defect_status']=='unresolved' or r['disputes'] or r['conditional_claims'] or r['conditional_findings'] or r['annotation_disagreement']]
    artifacts={'reference.private.json':snapshot,'model-inputs.private.json':inputs,
        'train-registry.private.json':registry,'near-duplicate-registry.private.json':near,
        'review-packet.private.json':dict(authority='agent-reviewed, not human-verified; no model outputs',records=packet,audits=audits),
        'historical-inventory.private.json':history,'policy.json':POLICY,
        'metric-definitions.json':METRIC_DEFINITIONS,'level-contracts.json':LEVEL_CONTRACTS}
    for name,value in artifacts.items():write_new(frozen/name,value)
    private_hashes={name:sha_file(frozen/name) for name in artifacts}
    train_public=dict(version=POLICY['version'],private_registry=str(frozen/'train-registry.private.json'),
        private_registry_sha256=private_hashes['train-registry.private.json'],policy=POLICY['train_gate'],
        blocked_families=sorted({r['family'] for r in registry['entries']}),
        entries=[{k:v for k,v in r.items() if k!='structural_shingles'} for r in registry['entries']],
        current_corpus_eligible_ids=[],current_corpus_eligible_count=0,
        note='No target writer/optimizer is run or modified here. Future integrations MUST call the guard at both boundaries; family blocking admits no current ZIP family.')
    write_new(TRAIN_MANIFEST,train_public)
    selection=[dict(**{k:r[k] for k in ('sample_id','family','exam_type','group','source_sha256','statement_sha256','code_identity','renamed_identity','level','annotation_v2','source_reference','defect_status')},
        problem_context_sha256=sha_bytes(json_bytes(dict(problems=r['problems'],grading_policy=r['grading_policy']))),
        reference_sha256=sha_bytes(json_bytes(r)),source_member=r['source_member'],exposure=r['exposure']) for r in snapshot['records']]
    handoff=dict(version=POLICY['version'],initial_head='da41adb69b3091e5c9c859be13b94d40892fb80a',
        freeze_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip(),
        freeze_date_client='2026-10-21',timezone='Asia/Saigon',archive_sha256=ZIP_SHA256,
        archive_root_count=len(archive['records']),archive_heldout_count=len(archive['heldout']),
        archive_members_sha256=archive['members_sha256'],historical_inputs_sha256=history['input_hashes'],
        historical_counts=history['counts'],policy=POLICY,metric_definitions=METRIC_DEFINITIONS,level_contracts=LEVEL_CONTRACTS,
        selection=selection,requests=snapshot['requests'],private_root=str(frozen),private_files_sha256=private_hashes,
        implementation_sha256={p:sha_file(REPO/p) for p in IMPLEMENTATION},
        train_exclusion_sha256=sha_file(TRAIN_MANIFEST),**meta,
        limitations=['No human verification or execution/compilation evidence; all findings static agent reasoning.',
            'All28 data families previously exposed; ID/code isolation does not imply template/generalization isolation.',
            'Source-reference style support0; no explicit style requirement in selected statements. Unsupported labels remain in 10-label macro.',
            'One leading-whitespace case unresolved; v2 kept, source-reference null.',
            'All current-corpus training families denied; later valid fine-tuning needs new isolated families and full guard pass.',
            'Review ledgers for future predictions are pending, not scored by a keyword gate.'])
    write_new(frozen/'handoff.json',handoff)
    write_new(MANIFEST,handoff)
    write_seal(frozen/'seal.json',{name:sha_file(frozen/name) for name in [*artifacts,'handoff.json']})
    print(json.dumps({'manifest':str(MANIFEST),'manifest_sha256':sha_file(MANIFEST),'seal_sha256':sha_file(frozen/'seal.json'),**meta},ensure_ascii=False))


def verify_snapshot(manifest=MANIFEST):
    manifest=Path(manifest);m=json.loads(manifest.read_text());frozen=Path(m['private_root'])
    if not frozen.resolve().is_relative_to((REPO/'outputs/task3').resolve()):raise ValueError('private snapshot outside repository ignored storage')
    verify_seal(frozen/'seal.json',expected_hashes={**m['private_files_sha256'],'handoff.json':sha_file(manifest)})
    if sha_file(manifest)!=sha_file(frozen/'handoff.json'):raise ValueError('public handoff differs from sealed copy')
    if sha_file(TRAIN_MANIFEST)!=m['train_exclusion_sha256']:raise ValueError('train exclusion manifest changed')
    if sha_file(REPO/'generate-dataset_v2.zip')!=m['archive_sha256']:raise ValueError('archive changed')
    for p,h in {**m['implementation_sha256'],**m['historical_inputs_sha256']}.items():
        if sha_file(REPO/p)!=h:raise ValueError('implementation/history changed: '+p)
    return m


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('prepare');sub.add_parser('verify')
    for name in ('evaluate','review-template'):
        p=sub.add_parser(name);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
        if name=='evaluate':p.add_argument('--ledger',type=Path)
    p=sub.add_parser('train-gate');p.add_argument('--candidates',type=Path,required=True);p.add_argument('--stage',choices=['before_targets','before_optimizer'],required=True)
    args=ap.parse_args()
    if args.command=='prepare':prepare();return
    m=verify_snapshot();frozen=Path(m['private_root'])
    if args.command=='verify':print(json.dumps({'verified':True,'manifest_sha256':sha_file(MANIFEST),'seal_sha256':sha_file(frozen/'seal.json')}));return
    if args.command=='train-gate':
        rows=json.loads(args.candidates.read_text());registry=json.loads((frozen/'train-registry.private.json').read_text())
        result=require_train_isolation(rows,registry,stage=args.stage)
        print(json.dumps(dict(result,candidates_sha256=sha_file(args.candidates),registry_sha256=sha_file(frozen/'train-registry.private.json'))));return
    snapshot=json.loads((frozen/'reference.private.json').read_text())
    predictions=json.loads(args.predictions.read_text())
    if args.command=='review-template':result=review_template(snapshot,predictions)
    else:result=evaluate(snapshot,predictions,json.loads(args.ledger.read_text()) if args.ledger else None)
    write_new(args.output,result)
    print(json.dumps({'output':str(args.output),'sha256':sha_file(args.output)}))


if __name__=='__main__':main()
