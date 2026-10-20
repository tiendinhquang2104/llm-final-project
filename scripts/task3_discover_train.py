#!/usr/bin/env python3
"""Round 13 offline TRAIN experiment only. No oracle/labels in inference API."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.task3.compiler import check_cpp_syntax
from src.task3.dataset import write_json
from src.task3.discovery import discover
from src.task3.discovery_render import render,project,complete
from src.task3.discovery_eval import assert_isolated,load_train_rows,inference_input,score_findings,label_metrics
from tests.task3_discovery_cases import development_cases,independent_cases,oracle_findings
from src.synth.taxonomy import LABEL_SPACE


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',default='data/processed/task3')
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args();repo=Path(__file__).resolve().parents[1];out=Path(args.output_dir).resolve()
    if not out.is_relative_to(repo/'outputs') or out.exists():parser.error('new ignored outputs directory required')
    out.mkdir(parents=True)
    dev,check=development_cases(),independent_cases();assert_isolated(dev,check)
    files=['src/task3/discovery.py','src/task3/discovery_render.py','src/task3/discovery_eval.py','tests/task3_discovery_cases.py',str(Path(__file__).relative_to(repo))]
    write_json(out/'frozen-before-check.json',{'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'implementation_sha256':{f:hashlib.sha256((repo/f).read_bytes()).hexdigest() for f in files},
        'scope':'train-only independent check; not heldout; no method tuning from check results',
        'input_paths':[str(Path(args.data_dir)/f'{s}.jsonl') for s in ('real-train','synthetic-train')]})
    cache={}
    def compile_code(code):
        key=hashlib.sha256(code.encode()).hexdigest()
        if key not in cache:cache[key]=check_cpp_syntax(code,standard='c++11',timeout_s=3)
        return cache[key]
    fixture_summary={}
    for partition,cases in [('development',dev),('independent_train_check',check)]:
        rows=[];by_group={g:Counter(tp=0,fp=0,fn=0) for g in LABEL_SPACE}
        for case in cases:
            compiler=compile_code(case.code)
            item=inference_input({'code':case.code,'statement':case.statement,'problems':case.problems},compiler)
            result=discover(item);oracle=oracle_findings(case);score=score_findings(oracle,result['findings'])
            for g,v in score['by_group'].items():by_group[g].update(v)
            paired={}
            for level in range(1,5):
                paired[level]={'oracle':project(item,oracle,level),'predicted':render(item,result['findings'],level)}
            policies={policy:{level:complete(item,level,policy=policy) for level in range(1,5)} for policy in ('abstain','supported_partial')}
            rows.append({'name':case.name,'exam':case.exam,'group':case.group,'code':case.code,'statement':case.statement,
                'compiler':compiler,'prediction':result,'oracle_findings':oracle,'finding_score':score,'paired':paired,'policies':policies})
        per_group={g:dict(v,precision=v['tp']/(v['tp']+v['fp']) if v['tp']+v['fp'] else None,
                          recall=v['tp']/(v['tp']+v['fn']) if v['tp']+v['fn'] else None) for g,v in by_group.items()}
        fixture_summary[partition]={'cases':len(rows),'supported_findings':sum(len(r['prediction']['findings']) for r in rows),
            'finding_metric_kind':'taxonomy_and_span_agreement_not_semantic_correctness',
            'tp':sum(r['finding_score']['tp'] for r in rows),'fp':sum(r['finding_score']['fp'] for r in rows),'fn':sum(r['finding_score']['fn'] for r in rows),
            'no_supported_finding':sum(r['prediction']['status']=='unknown' for r in rows),
            'coverage_incomplete':sum(not r['prediction']['coverage_complete'] for r in rows),'per_group':per_group,
            'render_by_level':{level:{kind:sum(r['paired'][level][kind]['status']=='rendered' for r in rows) for kind in ('oracle','predicted')} for level in range(1,5)},
            'policies':{policy:{level:{'usable_feedback':sum(r['policies'][policy][level]['feedback'] is not None for r in rows),
                'exportable':sum(r['policies'][policy][level]['submission'] is not None for r in rows),
                'export_label_exact':sum(r['policies'][policy][level]['submission'] is not None and set(r['policies'][policy][level]['submission']['taxonomy_error'])=={f['taxonomy_group'] for f in r['oracle_findings']} for r in rows)} for level in range(1,5)} for policy in ('abstain','supported_partial')}}
        write_json(out/f'{partition}.raw.json',rows)
    dataset_summary={};all_rows=[]
    for split in ('real-train','synthetic-train'):
        rows=load_train_rows(args.data_dir,split);raw=[];metrics=[]
        for row in rows:
            compiler=compile_code(row['code']);item=inference_input(row,compiler);result=discover(item)
            level=int(row['target_feedback_level'][6]);feedback=render(item,result['findings'],level)
            policies={p:complete(item,level,policy=p) for p in ('abstain','supported_partial')}
            # Only now read labels, solely for taxonomy evaluation. Never read teacher feedback.
            metrics.append({'expected':row['gold_taxonomy'],'predicted':result['taxonomy'] or []})
            raw.append({'sample_id':row['sample_id'],'exam':row['exam_id'],'group':row['group_key'],'code':row['code'],'statement':row['statement'],
                        'compiler':compiler,'prediction':result,'render':feedback,'level':level,'policies':policies,
                        'expected_taxonomy_evaluation_only':row['gold_taxonomy']})
        dataset_summary[split]=dict(label_metrics(metrics),
            supported_findings=sum(len(r['prediction']['findings']) for r in raw),
            no_supported_finding=sum(r['prediction']['status']=='unknown' for r in raw),
            coverage_incomplete=sum(not r['prediction']['coverage_complete'] for r in raw),
            rejected_candidates=sum(len(r['prediction']['rejected_candidates']) for r in raw),
            compiler_status=dict(Counter(r['compiler']['status'] for r in raw)),
            render_by_level={level:{'total':sum(r['level']==level for r in raw),'rendered':sum(r['level']==level and r['render']['status']=='rendered' for r in raw)} for level in range(1,5)},
            completion={p:{'exportable':sum(r['policies'][p]['submission'] is not None for r in raw),
                           'usable_feedback':sum(r['policies'][p]['feedback'] is not None for r in raw)} for p in ('abstain','supported_partial')},
            finding_accuracy='unassessed without source-level annotations; taxonomy agreement is not factual verification')
        write_json(out/f'{split}.raw.json',raw);all_rows.extend(raw)
        print(json.dumps({'split':split,'records':len(rows),'supported_findings':dataset_summary[split]['supported_findings']},ensure_ascii=False),flush=True)
    # Inventory only: no baseline predictions/checkpoints loaded or silently assumed.
    baseline_files=[]
    for root in ('outputs/task2','checkpoints','models'):
        base=repo/root
        if base.exists():
            baseline_files.extend(str(p.relative_to(repo)) for p in base.rglob('*') if p.is_file() and p.suffix in {'.json','.jsonl','.safetensors','.bin','.pt'})
    write_json(out/'summary.json',{'fixtures':fixture_summary,'datasets':dataset_summary,
        'task2_inventory':{'paths_checked':['outputs/task2','checkpoints','models'],'candidate_files':baseline_files,'baseline_run':False},
        'model_calls':0,'student_programs_executed':False,'compiler_calls':len(cache),
        'oracle_authority':'assistant-authored artificial train expectations, independent of extractor and teacher feedback',
        'no_heldout_or_public_read':True})
    print(json.dumps({'status':'train_only_experiment_complete','compiler_calls':len(cache)}))


if __name__=='__main__':main()
