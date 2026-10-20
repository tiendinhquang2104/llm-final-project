#!/usr/bin/env python3
"""Train-only paired A/B/C/D. Prepare freezes bank/split before any generation."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.utils.config import load_config
from src.task3.dataset import load_prepared, write_json
from src.task3.compiler import check_cpp_syntax
from src.task3.round14 import sanitize
from src.task3.round14_eval import taxonomy_metrics
from src.task3.round14_runner import digest
from src.task3.round15 import query_payload, parse_response as parse_control
from src.task3.round15_selection import select_prompt_development
from src.task3.round16 import parse_response, fitted_messages
from src.task3.round16_bank import make_bank
from src.task3.round16_runner import run_records

ROOT=REPO/'outputs/task3/round16'
CONFIGS={'control':'configs/task3/r15_zero_shot.yaml', **{v:f'configs/task3/r16_{v}.yaml' for v in ('one_shot','few_shot','evidence_cot')}}
CANDIDATES=('outputs/task3/round14/public-candidate/predictions.json','outputs/task3/round15/public-candidate-zero/predictions.json')
BOUND_FILES=('src/task3/round16.py','src/task3/round16_runner.py','src/task3/round16_bank.py',
             'src/task3/round15.py','src/task3/round15_runner.py','src/task3/round15_disclosure.py',
             'src/task3/round15_selection.py','src/task3/compiler.py','src/task3/inference.py',
             'scripts/task3_round16.py',*CONFIGS.values(),'configs/task3/r15_common.yaml')


def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def candidate_hashes():return {p:file_hash(REPO/p) for p in CANDIDATES}
def implementation():return {p:file_hash(REPO/p) for p in BOUND_FILES}


def training():
    rows,selection=select_prompt_development(REPO/'data/processed/task3')
    selected=[]
    for r in rows:
        e=check_cpp_syntax(r.code,compiler='/usr/bin/g++',standard='c++11',timeout_s=3)
        # Timing is not inference input and must not break deterministic resume.
        e.pop('latency_s',None)
        selected.append((r,sanitize(r,e)))
    return selected,selection


def original_sources():
    outer=zipfile.ZipFile(REPO/'data-20261017T044357Z-1-001.zip')
    middle=zipfile.ZipFile(io.BytesIO(outer.read('data/public-test-cham-diem-phan-hoi-files.zip')))
    sample=zipfile.ZipFile(io.BytesIO(middle.read('sample_dataset.zip')))
    meta=json.loads((REPO/'data/raw/sample_dataset/task3_feedback.json').read_text())
    checked=[]
    for row in meta['samples']:
        relative=row['input']['code_file']
        matches=[n for n in sample.namelist() if n.endswith('/'+relative) or n==relative]
        if len(matches)!=1:raise ValueError('ambiguous original sample source')
        blob=sample.read(matches[0]);local=(REPO/'data/raw/sample_dataset'/relative).read_bytes()
        if blob!=local:raise ValueError('original ZIP/source mismatch')
        checked.append({'id':row['sample_id'],'source_sha256':hashlib.sha256(blob).hexdigest()})
    return checked


def prepare():
    ROOT.mkdir(parents=True,exist_ok=True)
    if (ROOT/'freeze.json').exists():raise ValueError('freeze exists; do not overwrite or tune after evaluation')
    pairs,selection=training()
    pool=[r for r in load_prepared(REPO/'data/processed/task3','synthetic-train') if r.sample_id in selection['development_family_pool_ids']]
    bank=make_bank(REPO/'data/processed/task3',pool)
    write_json(ROOT/'train-examples.json',bank)
    write_json(ROOT/'development-selection.json',selection)
    write_json(ROOT/'inputs.private.json',[{'id':r.sample_id,'query':query_payload(clean)} for r,clean in pairs])
    manifest={'purpose':'single frozen paired prompt experiment; no second-round tuning',
        'selection':selection,'bank_sha256':file_hash(ROOT/'train-examples.json'),
        'inputs_sha256':file_hash(ROOT/'inputs.private.json'),'implementation_sha256':implementation(),
        'configs':{v:load_config(REPO/p) for v,p in CONFIGS.items()},'candidates':candidate_hashes(),
        'source_zip_verification':original_sources(),'public_schema':{
            k:v for k,v in json.loads((REPO/'data/raw/public_test_release/task3_feedback.json').read_text()).items()
            if k in ('input_fields','output_fields','n_samples')},
        'prior_exposure':'All 24 development IDs reviewed in Round15; Round13 saw training corpus. R14 reserve, not blind.',
        'selection_rule':'same Level; fixed positive first for one-shot; same positive + reviewed clean for few-shot; no gold-query selection',
        'contamination_review':'check borrowed identifiers chuyenHoa/uocChung/text/value/result/pos and uppercase/GCD task or repair; semantic manual review, not response gating',
        'review_protocol':'source before raw; inventory material supported/false/unassessed claims; raw then final; L1 praise/disclosure/template; L2 diagnosis/repair leak; L3 cause+feasible repair; L4 integrated code; CoT active code and evidence-feedback consistency',
        'decision_priority':['source correctness','Level boundaries','L2 useful diagnosis','L3 feasible repair','taxonomy agreement','style'],
        'bank_metadata':[{k:v for k,v in e.items() if k not in ('code','statement','problems','grading_policy','compiler')} for e in bank],
        'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}
    write_json(ROOT/'freeze.json',manifest)
    # Reviewable provenance without student source or model output.
    if ROOT==REPO/'outputs/task3/round16':
        write_json(REPO/'reports/task3/TASK3_ROUND16_FREEZE_20261020.json',manifest)
    print(json.dumps({'freeze_sha256':file_hash(ROOT/'freeze.json'),'records':len(pairs),'bank':len(bank)}))


def run(conditions):
    from src.task3.inference import HFBackend, load_tokenizer, tokenizer_metadata
    from src.task3.round15_runner import run_records as control_runner
    frozen=json.loads((ROOT/'freeze.json').read_text())
    if frozen['implementation_sha256']!=implementation():raise ValueError('frozen implementation mismatch')
    if frozen['candidates']!=candidate_hashes():raise ValueError('public candidate changed')
    pairs,selection=training();records=[clean for _,clean in pairs]
    inputs=[{'id':r.sample_id,'query':query_payload(clean)} for r,clean in pairs]
    if selection!=frozen['selection'] or digest(inputs)!=digest(json.loads((ROOT/'inputs.private.json').read_text())):
        raise ValueError('frozen evaluation input mismatch')
    if file_hash(ROOT/'train-examples.json')!=frozen['bank_sha256']:raise ValueError('bank changed')
    bank=json.loads((ROOT/'train-examples.json').read_text())
    os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'))
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    common=frozen['configs']['control'];tokenizer=load_tokenizer(common)
    # Preflight every condition, Level4 cap and worst bounded retry before GPU generation.
    budgets=[]
    for condition in conditions:
        cfg=frozen['configs'][condition]
        for record in records:
            level=int(record.target_feedback_level[6]);shots=[e for e in bank if e['level']==level]
            if condition=='one_shot':shots=shots[:1]
            if condition in ('control','evidence_cot'):shots=[]
            for retry in (None,'x'*500):
                cap=cfg['level4_max_tokens'] if level==4 else cfg['max_new_tokens']
                fn=fitted_messages
                if condition=='control':
                    from src.task3.round15 import fitted_messages as fn
                _,b=fn(record,shots,tokenizer,{**cfg,'max_new_tokens':cap},retry=retry)
                budgets.append({'condition':condition,'id':record.sample_id,'retry':bool(retry),**b})
    write_json(ROOT/'tokenizer-budget.json',budgets)
    backend=HFBackend(common,tokenizer);backend.model.generation_config.max_time=float(common['generation_max_time_s'])
    gold=[r for r,_ in pairs]
    for condition in conditions:
        cfg=frozen['configs'][condition];out=ROOT/condition
        runner=control_runner if condition=='control' else run_records
        result=runner(records,backend,cfg,out,examples=[] if condition=='control' else bank)
        first=[]
        for trace in all_traces(result):
            try:
                raw=parse_control(trace['first_raw_text']) if condition=='control' else parse_response(trace['first_raw_text'],condition)
                first.append({'sample_id':trace['sample_id'],'output':{k:raw[k] for k in ('taxonomy_error','feedback')}})
            except (ValueError,TypeError):pass
        write_json(out/'raw-first.predictions.json',first)
        predicted={p['sample_id']:p['output'] for p in result['predictions']}
        compiler_counts=Counter()
        for record in records:
            if record.sample_id not in predicted:continue
            status=record.provenance['_task3_compile_check']['status']
            if status not in ('compiled','compile_error'):continue
            actual=status=='compile_error';positive='Lỗi biên dịch' in predicted[record.sample_id]['taxonomy_error']
            compiler_counts['TP' if actual and positive else 'FN' if actual else 'FP' if positive else 'TN']+=1
        metrics={'completed':len(predicted),'requested':len(records),'raw_schema':len(first),
                 'taxonomy':available_taxonomy_metrics(gold,result['predictions']), 'raw_taxonomy':available_taxonomy_metrics(gold,first),
                 'compiler_agreement':{k:compiler_counts[k] for k in ('TP','FP','FN','TN')},
                 'fallback':sum(bool(t.get('fallback_used')) for t in result['traces']),
                 'attempts':sum(len(t['attempts']) for t in all_traces(result))}
        write_json(out/'metrics.json',metrics)
        write_json(out/'run.json',{'config':cfg,'identity':result['identity'],'freeze_sha256':file_hash(ROOT/'freeze.json'),
            'runtime':backend.runtime_metadata(),'tokenizer':tokenizer_metadata(tokenizer),'errors':result['errors'],
            'implementation_sha256':implementation(),'candidate_hashes_after':candidate_hashes()})
        if frozen['candidates']!=candidate_hashes():raise ValueError('public candidate changed')
        print(json.dumps({'condition':condition,**metrics},ensure_ascii=False),flush=True)



def all_traces(result):
    return result['traces']+[entry['trace'] for entry in result['errors'].values()]


def available_taxonomy_metrics(records, predictions):
    """Conditional F1 plus explicit coverage; never turn malformed JSON into []."""
    ids=[p['sample_id'] for p in predictions]
    known={r.sample_id for r in records}
    if len(set(ids))!=len(ids) or not set(ids)<=known:raise ValueError('invalid metric IDs')
    measured=[r for r in records if r.sample_id in set(ids)]
    return {**taxonomy_metrics(measured,predictions),'requested':len(records),
            'missing_ids':[r.sample_id for r in records if r.sample_id not in set(ids)]}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare',action='store_true')
    ap.add_argument('--output-root',default=str(ROOT),help='Fresh private run directory under outputs/task3')
    ap.add_argument('--conditions',nargs='+',choices=list(CONFIGS),default=list(CONFIGS))
    args=ap.parse_args()
    global_root=Path(args.output_root).resolve()
    if not global_root.is_relative_to(REPO/'outputs/task3'):ap.error('private output root must be under outputs/task3')
    globals()['ROOT']=global_root
    if args.prepare:prepare()
    else:run(args.conditions)

if __name__=='__main__':main()
