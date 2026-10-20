#!/usr/bin/env python3
"""Opt-in Round14 train-development comparison or frozen public candidate run."""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.utils.config import load_config
from src.task3.dataset import write_json,load_task3
from src.task3.compiler import check_cpp_syntax
from src.task3.inference import HFBackend,load_tokenizer,tokenizer_metadata
from src.task3.round14 import sanitize
from src.task3.round14_runner import run_records,digest,journal_totals
from src.task3.round14_eval import select_development,taxonomy_metrics,feedback_metrics
from src.task3.public_contract import verify_public_contract
from src.task3.submission import validate_submission

IMPLEMENTATION=('src/task3/round14.py','src/task3/round14_runner.py','src/task3/round14_eval.py',
                'src/task3/public_contract.py','src/task3/inference.py','src/task3/compiler.py',
                'src/task3/discovery.py','src/task3/discovery_render.py','src/task3/renderer.py',
                'scripts/task3_round14.py','src/task3/compliance.py','src/task3/quality_review.py',
                'src/task3/schema.py','src/task3/dataset.py','src/task3/submission.py',
                'src/synth/taxonomy.py','src/synth/feedback.py','src/synth/compliance.py',
                'src/utils/config.py','src/utils/json_extractor.py','src/task3/adequacy.py')


def implementation_hashes():
    return {p:hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in IMPLEMENTATION}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--phase',choices=('development','public'),required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--per-level',type=int,default=6)
    parser.add_argument('--freeze')
    parser.add_argument('--oracle-from',help='development-only B traces to hold stage1 context fixed')
    parser.add_argument('--public-root',default='data/raw/public_test_release')
    args=parser.parse_args()
    config=load_config(args.config);out=Path(args.output_dir).resolve()
    if not out.is_relative_to(REPO/'outputs/task3'):parser.error('private outputs must be under ignored outputs/task3/')
    if config.get('few_shot_k',0)!=0:parser.error('Round14 frozen K=0 method does not read public demonstrations')
    out.mkdir(parents=True,exist_ok=True)
    oracle_labels=assessment_cache=None;selection=None;contract=None
    if args.phase=='public':
        if args.oracle_from:parser.error('oracle taxonomy forbidden for public')
        if not args.freeze:parser.error('public requires a pre-public development selection freeze')
        freeze=json.loads(Path(args.freeze).read_text())
        if freeze['config']!=config or freeze['implementation_sha256']!=implementation_hashes():
            parser.error('frozen method/config implementation mismatch; do not tune on public')
        if not freeze.get('development_evidence') or freeze.get('public_used_for_selection') is not False:
            parser.error('train-only selection evidence required')
        contract=verify_public_contract(args.public_root)
        requested=contract['requested_levels']
        levels_path=out/'official-requested-levels.json';write_json(levels_path,requested)
        records=load_task3(args.public_root,'public',levels_path)
        by_id={r.sample_id:r for r in records};records=[by_id[sid] for sid in requested]
    else:
        records,selection=select_development(config.get('data_dir','data/processed/task3'),per_level=args.per_level)
        write_json(out/'development-selection.json',selection)
        if args.oracle_from:
            if config['method']!='two_stage':parser.error('paired oracle control requires B')
            prior_manifest=json.loads(Path(args.oracle_from).with_name('run.json').read_text())
            if prior_manifest['phase']!='development' or prior_manifest['condition']!='no_gold_inference' or prior_manifest['config']!=config or prior_manifest['selection']['selection_id']!=selection['selection_id']:parser.error('paired assessment provenance mismatch')
            prior=json.loads(Path(args.oracle_from).read_text())
            assessment_cache={r['sample_id']:r['assessment'] for r in prior}
            if set(assessment_cache)!={r.sample_id for r in records}:parser.error('paired assessment IDs mismatch')
            oracle_labels={r.sample_id:r.gold_taxonomy for r in records}
    started=time.perf_counter();evidence_cache={};sanitized=[]
    for r in records:
        key=hashlib.sha256(r.code.encode()).hexdigest()
        if key not in evidence_cache:
            evidence_cache[key]=check_cpp_syntax(r.code,compiler=config.get('cpp_compiler'),standard='c++11',timeout_s=config.get('compiler_timeout_s',3))
        sanitized.append(sanitize(r,evidence_cache[key]))
    write_json(out/'compiler-evidence.json',{r.sample_id:r.provenance['_task3_compile_check'] for r in sanitized})
    os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'))
    os.environ.setdefault('HF_HUB_OFFLINE','1');os.environ.setdefault('TRANSFORMERS_OFFLINE','1')
    tokenizer=load_tokenizer(config)
    # Preflight both initial and maximal retry instructions before model loading.
    from src.task3.round14 import fitted_messages
    budgets=[]
    for r in sanitized:
        for stage in ('direct','classify','classifier_fallback','feedback'):
            reserve=config.get('level4_max_tokens',1536) if int(r.target_feedback_level[6])==4 else max(config.get('direct_max_tokens',1024),config.get('classification_max_tokens',768),config.get('feedback_max_tokens',640))
            try:
                _,count=fitted_messages(r,stage,tokenizer,{**config,'max_new_tokens':reserve},assessment=None,retry='Schema/Level validation failed. '+('x'*650))
                budgets.append({'sample_id':r.sample_id,'stage':stage,'tokens':count,'reserve':reserve,'fits':True})
            except ValueError as exc:budgets.append({'sample_id':r.sample_id,'stage':stage,'fits':False,'error':str(exc)})
    write_json(out/'tokenizer-budget.json',{'tokenizer':tokenizer_metadata(tokenizer),'records':budgets})
    backend=HFBackend(config,tokenizer)
    backend.model.generation_config.max_time=float(config.get('generation_max_time_s',45))
    result=run_records(sanitized,backend,dict(config,implementation_sha256=implementation_hashes()),out,
                       oracle_labels=oracle_labels,assessment_cache=assessment_cache)
    completed_ids={p['sample_id'] for p in result['predictions']}
    scored_records=[r for r in records if r.sample_id in completed_ids]
    metrics={'feedback':feedback_metrics(scored_records,result['predictions'],result['traces']),
             'completion':{'requested':len(records),'completed':len(result['predictions']),'unresolved_ids':list(result['errors'])}}
    if args.phase=='development':
        metrics['taxonomy']=taxonomy_metrics(scored_records,result['predictions']) if oracle_labels is None else {'condition':'oracle_taxonomy_supplied_not_model_scored'}
    write_json(out/'metrics.json',metrics)
    trace_by_id={t['sample_id']:t for t in result['traces']}
    write_json(out/'audit-summary.json',[{'sample_id':r.sample_id,'requested_level':int(r.target_feedback_level[6]),
        'compiler_status':r.provenance['_task3_compile_check']['status'],
        'taxonomy_error':trace_by_id[r.sample_id]['assessment']['taxonomy_error'],
        'model_taxonomy_error':trace_by_id[r.sample_id]['assessment'].get('model_taxonomy_error'),
        'compiler_reconciliation':trace_by_id[r.sample_id]['assessment'].get('compiler_reconciliation',False),
        'epistemic_status':trace_by_id[r.sample_id]['assessment']['epistemic_status'],
        'uncertain':trace_by_id[r.sample_id]['assessment']['uncertain'],
        'classification_fallback':trace_by_id[r.sample_id]['classification_fallback'],
        'feedback_origin':trace_by_id[r.sample_id]['feedback_origin'],
        'feedback_fallback':trace_by_id[r.sample_id]['fallback_used'],
        'policy_flags':trace_by_id[r.sample_id]['feedback_level_errors'],
        'rejected_support_count':len(trace_by_id[r.sample_id]['assessment'].get('rejected_rationales',[])),
        'attempts':len(trace_by_id[r.sample_id]['attempts'])} for r in sanitized if r.sample_id in trace_by_id])
    manifest={'status':'complete_candidate_not_submitted' if not result['errors'] else 'incomplete_resumable',
              'phase':args.phase,'method':config['method'],'condition':'oracle_taxonomy_development_diagnostic' if oracle_labels is not None else 'no_gold_inference',
              'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'worktree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
              'implementation_sha256':implementation_hashes(),'config':config,'config_sha256':digest(config),
              'tokenizer':tokenizer_metadata(tokenizer),'runtime':backend.runtime_metadata(),
              'wall_s':time.perf_counter()-started,'records':len(records),'completed':len(result['predictions']),
              'resume_identity':result['identity'],'unresolved_ids':list(result['errors']),
              'compiler_status':dict(Counter(e['status'] for e in evidence_cache.values())),
              'compiler_unique_sources':len(evidence_cache),'standard':'c++11','student_programs_executed':False,
              'selection':selection,'public_contract':contract,'freeze':args.freeze,
              'generation_max_time_s':backend.model.generation_config.max_time,
              'cumulative_attempts':journal_totals(out/'attempts.jsonl'),
              'attempt_output_tokens':journal_totals(out/'attempts.jsonl')['output_tokens'],
              'attempt_latency_s':journal_totals(out/'attempts.jsonl')['latency_s'],
              'wall_time_scope':'this invocation; cumulative generation counters come from append-only journal'}
    if not result['errors']:
        requested={r.sample_id:r.target_feedback_level for r in records}
        manifest['validation']=validate_submission(out/'predictions.json',requested)
        manifest['predictions_sha256']=hashlib.sha256((out/'predictions.json').read_bytes()).hexdigest()
    write_json(out/'run.json',manifest)
    print(json.dumps({k:manifest[k] for k in ('status','records','completed','wall_s')},ensure_ascii=False))
    return 0 if not result['errors'] else 2


if __name__=='__main__':raise SystemExit(main())
