#!/usr/bin/env python3
"""Exactly one train-only A/B/C comparison with a frozen diverse bank and v2 gold."""
import argparse
from collections import Counter
from dataclasses import asdict,replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.dataset import load_prepared,write_json
from src.task3.schema import Task3Record
from src.task3.compiler import check_cpp_syntax
from src.task3.round14 import sanitize
from src.task3.round14_runner import digest
from src.task3.round15 import query_payload,parse_response as parse_plain
from src.task3.round17 import select_development,validate_bank
from src.task3.round17_bank import make_bank
from src.utils.config import load_config
from scripts.task3_round16 import all_traces,available_taxonomy_metrics

ROOT=REPO/'outputs/task3/round17'
CONFIGS={'control':'configs/task3/r15_zero_shot.yaml','one_shot':'configs/task3/r17_one_shot.yaml','few_shot':'configs/task3/r17_few_shot.yaml'}
FILES=('scripts/task3_round17.py','src/task3/round17.py','src/task3/round17_bank.py',
       'src/task3/round16.py','src/task3/round16_runner.py','src/task3/round15.py',
       'src/task3/round15_runner.py','src/task3/round15_disclosure.py','src/task3/inference.py',
       'src/task3/compiler.py','configs/task3/r15_common.yaml',*CONFIGS.values())
V2_SHA='3581498f3db9b55e8bef911609b7829d1928805e66d2956d36a2084b3ca190d0'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def implementation():return {p:sha(REPO/p) for p in FILES}


def prepare():
    if (ROOT/'freeze.json').exists():raise ValueError('already frozen: no second bank/prompt round')
    ROOT.mkdir(parents=True,exist_ok=True)
    archive=REPO/'generate-dataset_v2.zip'
    if sha(archive)!=V2_SHA:raise ValueError('v2 archive version mismatch')
    z=zipfile.ZipFile(archive);annotation=z.read('generate-dataset/task3_feedback.json')
    labels={r['sample_id']:r for r in json.loads(annotation)['samples']}
    official=json.loads(z.read('generate-dataset/label_space.json'))['taxonomy_error']
    previous=json.loads((REPO/'outputs/task3/round16/freeze.initial.json').read_text())
    prepared=REPO/'data/processed/task3/synthetic-train.jsonl'
    if sha(prepared)!=previous['selection']['partition_identity']['synthetic-train']['sha256']:
        raise ValueError('original train eligibility partition changed')
    train=[]
    for r in load_prepared(REPO/'data/processed/task3','synthetic-train'):
        v2=labels[r.sample_id]
        if r.code!=z.read('generate-dataset/'+v2['input']['code_file']).decode():raise ValueError('v2 source changed')
        if r.target_feedback_level!=v2['input']['target_feedback_level']:raise ValueError('v2 Level changed')
        # v1 label/feedback is never used for stratification, references or metrics.
        train.append(replace(r,gold_taxonomy=v2['output']['taxonomy_error'],gold_feedback=None,
                             test_report=None,synthetic_exec_report=None))
    by_id={r.sample_id:r for r in train}
    old=[by_id[sid] for sid in previous['selection']['selected_ids']]
    families=set(previous['selection']['selected_families'])
    pool=[r for r in train if r.exam_id in families]
    records,selection=select_development(pool,old)
    if selection['missing_labels']!=['Lỗi thuật toán']:raise ValueError('expected nine-label coverage, algorithm unsupported')
    bank=make_bank(train,pool)
    records_with_compiler=[]
    for r in records:
        evidence=check_cpp_syntax(r.code,compiler='/usr/bin/g++',standard='c++11',timeout_s=3)
        evidence.pop('latency_s',None)
        records_with_compiler.append(replace(r,provenance={'_task3_compile_check':evidence}))
    write_json(ROOT/'development.private.json',[asdict(r) for r in records_with_compiler])
    write_json(ROOT/'inputs.private.json',[{'sample_id':r.sample_id,'query':query_payload(sanitize(r,r.provenance['_task3_compile_check']))} for r in records_with_compiler])
    write_json(ROOT/'train-examples.json',bank)
    protected=json.loads((REPO/'reports/task3/TASK3_ROUND16_DATASET_VERSION_AUDIT_20261020.json').read_text())['protected_files_sha256']
    for p,h in protected.items():
        if sha(REPO/p)!=h:raise ValueError('prior artifact changed: '+p)
    freeze={'purpose':'single final diverse-bank one/few shot retry; no CoT/guard/public; stop prompt trials if source correctness does not improve',
        'dataset_v2_zip_sha256':sha(archive),'task3_annotation_v2_sha256':hashlib.sha256(annotation).hexdigest(),
        'train_eligibility_partition_sha256':sha(prepared),
        'train_eligibility_note':'original fixed synthetic-train membership/source; v2 taxonomy overlaid before any selection; no v1 gold stratification or teacher feedback',
        'selection':selection,'selection_sha256':digest(selection),'official_labels':official,
        'v2_full_root_support':{l:sum(l in r['output']['taxonomy_error'] for r in labels.values()) for l in official},
        'development_file_sha256':sha(ROOT/'development.private.json'),'input_file_sha256':sha(ROOT/'inputs.private.json'),
        'bank_sha256':sha(ROOT/'train-examples.json'),'bank_entries':8,'bank_distinct_sources':8,'bank_distinct_families':8,
        'bank_metadata':[{k:v for k,v in ex.items() if k not in ('code','statement','problems','grading_policy','compiler')} for ex in bank],
        'example_selection':'query requested Level only; fixed defect first for one-shot, fixed defect+clean for few-shot; no query taxonomy/feedback/source retrieval',
        'configs':{c:load_config(REPO/p) for c,p in CONFIGS.items()},'implementation_sha256':implementation(),
        'protected_prior_files_sha256':protected,'prior_exposure':'R13 corpus seen; development families used R15/16 but all24 ID/group/code identities new vs R16; bank parent families may have prior R14 exposure; not blind',
        'review_policy':'source expectations before outputs; manually review first/retry/final; strict L2 diagnosis without repair, L3 feasible repair; count materially false claims and schema failures, no content rejection',
        'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}
    write_json(ROOT/'freeze.json',freeze);write_json(REPO/'reports/task3/TASK3_ROUND17_FREEZE_20261020.json',freeze)
    print(json.dumps({'selection':selection,'bank_families':[e['provenance']['family'] for e in bank],'freeze_sha256':sha(ROOT/'freeze.json')},ensure_ascii=False))


def run():
    from src.task3.inference import HFBackend,load_tokenizer,tokenizer_metadata
    from src.task3.round15 import fitted_messages as control_messages
    from src.task3.round16 import fitted_messages
    from src.task3.round15_runner import run_records as control_runner
    from src.task3.round16_runner import run_records as treatment_runner
    f=json.loads((ROOT/'freeze.json').read_text())
    if f['implementation_sha256']!=implementation():raise ValueError('frozen implementation mismatch')
    for name,key in (('development.private.json','development_file_sha256'),('inputs.private.json','input_file_sha256'),('train-examples.json','bank_sha256')):
        if sha(ROOT/name)!=f[key]:raise ValueError('frozen data/bank mismatch')
    if not (ROOT/'source-review.pre.md').exists():raise ValueError('source expectations required before inference')
    # Bind the pre-generation source review on first invocation, never overwrite it.
    review_hash=sha(ROOT/'source-review.pre.md');binding_path=ROOT/'source-review.binding.json'
    if binding_path.exists():
        if json.loads(binding_path.read_text())['sha256']!=review_hash:raise ValueError('source review changed')
    else:write_json(binding_path,{'sha256':review_hash})
    for p,h in f['protected_prior_files_sha256'].items():
        if sha(REPO/p)!=h:raise ValueError('prior artifact changed')
    gold=[Task3Record(**r) for r in json.loads((ROOT/'development.private.json').read_text())]
    records=[sanitize(r,r.provenance['_task3_compile_check']) for r in gold]
    bank=validate_bank(json.loads((ROOT/'train-examples.json').read_text()),records)
    os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'))
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    common=f['configs']['control'];tokenizer=load_tokenizer(common);budgets=[]
    for condition,cfg in f['configs'].items():
        for r in records:
            level=int(r.target_feedback_level[6]);shots=[e for e in bank if e['level']==level]
            if condition=='control':shots=[]
            if condition=='one_shot':shots=shots[:1]
            for retry in (None,'x'*500):
                cap=cfg['level4_max_tokens'] if level==4 else cfg['max_new_tokens']
                fn=control_messages if condition=='control' else fitted_messages
                _,b=fn(r,shots,tokenizer,{**cfg,'max_new_tokens':cap},retry=retry)
                budgets.append({'condition':condition,'sample_id':r.sample_id,'retry':bool(retry),**b})
    write_json(ROOT/'tokenizer-budget.json',budgets)
    backend=HFBackend(common,tokenizer);backend.model.generation_config.max_time=float(common['generation_max_time_s'])
    results={}
    for c,cfg in f['configs'].items():
        folder=ROOT/c;runner=control_runner if c=='control' else treatment_runner
        result=runner(records,backend,cfg,folder,examples=[] if c=='control' else bank)
        raw=[]
        for t in all_traces(result):
            try:raw.append({'sample_id':t['sample_id'],'output':parse_plain(t['first_raw_text'])})
            except (ValueError,TypeError):pass
        write_json(folder/'raw-first.predictions.json',raw)
        metrics={'completed':len(result['predictions']),'requested':len(records),'first_raw_schema':len(raw),
            'schema_unresolved':len(result['errors']),'attempts':sum(len(t['attempts']) for t in all_traces(result)),
            'taxonomy_v2':available_taxonomy_metrics(gold,result['predictions']),
            'taxonomy_first_raw_v2':available_taxonomy_metrics(gold,raw),
            'fallback':sum(bool(t.get('fallback_used')) for t in result['traces'])}
        write_json(folder/'metrics.json',metrics)
        write_json(folder/'run.json',{'freeze_sha256':sha(ROOT/'freeze.json'),'input_sha256':f['input_file_sha256'],
            'bank_sha256':f['bank_sha256'],'source_review_pre_sha256':review_hash,'identity':result['identity'],
            'config':cfg,'runtime':backend.runtime_metadata(),'tokenizer':tokenizer_metadata(tokenizer),
            'errors':result['errors'],'implementation_sha256':implementation()})
        results[c]=metrics
        print(json.dumps({'condition':c,**metrics},ensure_ascii=False),flush=True)
    write_json(ROOT/'metrics.json',results)
    for p,h in f['protected_prior_files_sha256'].items():
        if sha(REPO/p)!=h:raise ValueError('prior artifact changed')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--prepare',action='store_true');args=ap.parse_args()
    prepare() if args.prepare else run()
