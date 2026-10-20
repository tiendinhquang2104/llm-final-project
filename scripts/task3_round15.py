#!/usr/bin/env python3
"""Prompt-only Qwen comparison and development-frozen public candidate."""
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
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.utils.config import load_config
from src.task3.dataset import write_json,load_task3
from src.task3.compiler import check_cpp_syntax
from src.task3.inference import HFBackend,load_tokenizer,tokenizer_metadata
from src.task3.round14 import sanitize,object_json
from src.task3.round14_runner import digest,journal_totals
from src.task3.round14_eval import taxonomy_metrics
from src.task3.round15 import fitted_messages,validate_examples,parse_response
from src.task3.round15_runner import run_records,RawCaptureBackend
from src.task3.round15_selection import select_prompt_development,select_example_candidates,DEVELOPMENT_FAMILIES
from src.task3.round15_disclosure import disclosure_violations,audit_flags
from src.task3.public_contract import verify_public_contract
from src.task3.submission import validate_submission
from src.task3.schema import validate_taxonomy

FILES=('scripts/task3_round15.py','src/task3/round15.py','src/task3/round15_runner.py',
 'src/task3/round15_disclosure.py','src/task3/round15_selection.py','src/task3/inference.py',
 'src/task3/compiler.py','src/task3/dataset.py','src/task3/schema.py','src/task3/public_contract.py',
 'src/task3/submission.py','src/task3/round14.py','src/task3/round14_runner.py',
 'src/task3/round14_eval.py','src/synth/taxonomy.py','src/utils/config.py','src/utils/json_extractor.py')


def implementation_hashes():return {p:hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in FILES}


def parse_raw_candidate(text,*,baseline=False):
    if not baseline:return parse_response(text)
    value=object_json(text)
    if not {'taxonomy_error','rationales','assessment','feedback'}<=set(value):raise ValueError('Round14 joint response schema required')
    if not isinstance(value['rationales'],list) or not isinstance(value['assessment'],str):raise ValueError('Round14 joint field types required')
    if not isinstance(value['feedback'],str) or not value['feedback'].strip():raise ValueError('nonempty feedback required')
    return {'taxonomy_error':validate_taxonomy(value['taxonomy_error']),'feedback':value['feedback']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config',required=True);ap.add_argument('--phase',choices=('development','public'),required=True)
    ap.add_argument('--output-dir',required=True);ap.add_argument('--freeze')
    ap.add_argument('--baseline-round14',action='store_true',help='development-only immutable Round14 prompt/controller control')
    args=ap.parse_args();cfg=load_config(args.config);out=Path(args.output_dir).resolve()
    if not out.is_relative_to(REPO/'outputs/task3/round15'):ap.error('private output must be under outputs/task3/round15')
    if cfg.get('prompt_variant') not in ('zero_shot','few_shot'):ap.error('zero_shot or few_shot required')
    out.mkdir(parents=True,exist_ok=True)
    bank_path=Path(cfg['example_bank']);bank_hash=hashlib.sha256(bank_path.read_bytes()).hexdigest()
    bank=validate_examples(json.loads(bank_path.read_text()),select_example_candidates(cfg['data_dir'],DEVELOPMENT_FAMILIES))
    original=REPO/'outputs/task3/round14/public-candidate/predictions.json'
    original_hash=hashlib.sha256(original.read_bytes()).hexdigest()
    contract=selection=None
    if args.phase=='public':
        if args.baseline_round14:ap.error('Round14 public candidate is immutable, no new public baseline run')
        if not args.freeze:ap.error('public requires pre-public selected-prompt freeze')
        frozen=json.loads(Path(args.freeze).read_text())
        if frozen.get('config')!=cfg or frozen.get('implementation_sha256')!=implementation_hashes() or frozen.get('example_bank_sha256')!=bank_hash:
            ap.error('frozen config/code/train-example bank mismatch')
        if frozen.get('public_used_for_prompt_selection') is not False or not frozen.get('development_evidence'):ap.error('train-only selection evidence required')
        contract=verify_public_contract(REPO/'data/raw/public_test_release');requested=contract['requested_levels']
        levels_path=out/'official-requested-levels.json';write_json(levels_path,requested)
        source=load_task3(REPO/'data/raw/public_test_release','public',levels_path)
        by_id={r.sample_id:r for r in source};records=[by_id[sid] for sid in requested]
    else:
        records,selection=select_prompt_development(cfg['data_dir']);write_json(out/'development-selection.json',selection)
    started=time.perf_counter();cache={};inputs=[]
    for r in records:
        h=hashlib.sha256(r.code.encode()).hexdigest()
        if h not in cache:cache[h]=check_cpp_syntax(r.code,compiler=cfg.get('cpp_compiler'),standard='c++11',timeout_s=cfg.get('compiler_timeout_s',3))
        inputs.append(sanitize(r,cache[h]))
    write_json(out/'compiler-evidence.json',{r.sample_id:r.provenance['_task3_compile_check'] for r in inputs})
    os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'))
    os.environ.setdefault('HF_HUB_OFFLINE','1');os.environ.setdefault('TRANSFORMERS_OFFLINE','1')
    tokenizer=load_tokenizer(cfg)
    budget=[]
    for r in inputs:
        shots=[ex for ex in bank if ex['level']==int(r.target_feedback_level[6])] if cfg['prompt_variant']=='few_shot' else []
        cap=cfg.get('level4_max_tokens',1536) if int(r.target_feedback_level[6])==4 else cfg.get('max_new_tokens',1024)
        for retry in (None,'schema/disclosure correction '+('x'*500)):
            _,info=fitted_messages(r,shots,tokenizer,{**cfg,'max_new_tokens':cap},retry=retry)
            budget.append({'sample_id':r.sample_id,'retry':bool(retry),**info})
    write_json(out/'tokenizer-budget.json',budget)
    backend=HFBackend(cfg,tokenizer);backend.model.generation_config.max_time=float(cfg.get('generation_max_time_s',45))
    active=dict(cfg,implementation_sha256=implementation_hashes(),example_bank_sha256=bank_hash)
    baseline_cfg=None
    if args.baseline_round14:
        from src.task3.round14_runner import run_records as baseline
        baseline_cfg=load_config(REPO/'configs/task3/r14_selected.yaml')
        result=baseline(inputs,RawCaptureBackend(backend,out/'legacy-pre-guard.jsonl'),dict(baseline_cfg,implementation_sha256=implementation_hashes()),out)
    else:result=run_records(inputs,backend,active,out,examples=bank)
    predicted={p['sample_id']:p for p in result['predictions']};trace_by={t['sample_id']:t for t in result['traces']}
    raw=[];bundles=[]
    for r in records:
        trace=trace_by.get(r.sample_id) or result['errors'].get(r.sample_id,{}).get('trace',{})
        attempts=trace.get('attempts',[]);raw_text=trace.get('first_raw_text')
        if raw_text is None and attempts:raw_text=attempts[0].get('raw_text')
        initial=None
        try:
            initial=parse_raw_candidate(raw_text,baseline=args.baseline_round14)
        except (ValueError,TypeError,KeyError):pass
        if initial is not None:raw.append({'sample_id':r.sample_id,'output':initial})
        bundles.append({'sample_id':r.sample_id,'requested_level':int(r.target_feedback_level[6]),
            'code':r.code,'statement':r.statement,'problems':r.problems,'compiler':cache[hashlib.sha256(r.code.encode()).hexdigest()],
            'first_raw_text':raw_text,'first_raw_output':initial,'final_output':predicted.get(r.sample_id,{}).get('output'),
            'trace':trace,**({'evaluation_only_gold_taxonomy':r.gold_taxonomy} if args.phase=='development' else {})})
    # Raw student source and evaluation annotations never go to Git or a model prompt.
    write_json(out/'raw-and-final.audit.json',bundles);write_json(out/'raw-first.predictions.json',raw)
    metrics={'completed':len(predicted),'requested':len(records),'raw_schema_outputs':len(raw),
             'fallback_count':sum(bool(t.get('fallback_used')) for t in trace_by.values()),
             'raw_schema_scope':'Round14 joint field projection, no factual/rationale checks' if args.baseline_round14 else 'same strict two-key schema as candidate runner',
             'feedback_factual_or_useful_rate':'requires_source_based_review_not_schema_or_keyword_score',
             'per_level':{}}
    for level in range(1,5):
        group=[b for b in bundles if b['requested_level']==level]
        metrics['per_level'][str(level)]={'count':len(group),'completed':sum(b['final_output'] is not None for b in group),
            'raw_schema_count':sum(b['first_raw_output'] is not None for b in group),
            'raw_explicit_disclosure':sum(bool(disclosure_violations(b['first_raw_output']['feedback'],level)) for b in group if b['first_raw_output']),
            'final_explicit_disclosure':sum(bool(disclosure_violations(b['final_output']['feedback'],level)) for b in group if b['final_output']),
            'raw_to_final_changed':sum(b['first_raw_output']!=b['final_output'] for b in group),
            'fallback':sum(bool(b['trace'].get('fallback_used')) for b in group),
            'final_audit_flags':dict(Counter(flag for b in group if b['final_output'] for flag in audit_flags(b['final_output']['feedback'],level)))}
    if args.phase=='development':
        lookup={r.sample_id:r for r in records}
        metrics['taxonomy_final']=taxonomy_metrics([lookup[p['sample_id']] for p in result['predictions']],result['predictions'])
        metrics['taxonomy_first_raw']=taxonomy_metrics([lookup[p['sample_id']] for p in raw],raw)
    write_json(out/'metrics.json',metrics)
    totals=journal_totals(out/'attempts.jsonl')
    manifest={'status':'complete_candidate_not_submitted' if len(predicted)==len(records) else 'incomplete_resumable',
        'phase':args.phase,'condition':'round14_train_control' if args.baseline_round14 else cfg['prompt_variant'],
        'config':cfg,'baseline_effective_config':baseline_cfg,'implementation_sha256':implementation_hashes(),'example_bank_sha256':bank_hash,
        'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'worktree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
        'model_runtime':backend.runtime_metadata(),'tokenizer':tokenizer_metadata(tokenizer),'wall_s':time.perf_counter()-started,
        'records':len(records),'completed':len(predicted),'unresolved_ids':list(result['errors']),
        'attempt_totals':totals,'selection':selection,'freeze':args.freeze,'public_contract':contract,
        'compiler_unique_calls':len(cache),'compiler_status':dict(Counter(e['status'] for e in cache.values())),
        'student_programs_executed':False,'round14_candidate_sha256_before':original_hash}
    assert hashlib.sha256(original.read_bytes()).hexdigest()==original_hash,'Round14 candidate changed'
    manifest['round14_candidate_sha256_after']=original_hash
    if len(predicted)==len(records):
        manifest['validation']=validate_submission(out/'predictions.json',{r.sample_id:r.target_feedback_level for r in records})
        manifest['predictions_sha256']=hashlib.sha256((out/'predictions.json').read_bytes()).hexdigest()
    write_json(out/'run.json',manifest)
    print(json.dumps({k:manifest[k] for k in ('status','completed','records','wall_s')}))
    return 0 if len(predicted)==len(records) else 2


if __name__=='__main__':raise SystemExit(main())
