#!/usr/bin/env python3
"""Offline, hash-bound reporting. Semantic verdicts are explicit review notes."""
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.round14_runner import digest
from src.task3.round15 import parse_response
from src.task3.dataset import write_json
from scripts.task3_round17 import ROOT,sha,implementation


def main():
    freeze=json.loads((ROOT/'freeze.json').read_text())
    if implementation()!=freeze['implementation_sha256']:raise ValueError('generation implementation changed')
    for path,h in freeze['protected_prior_files_sha256'].items():
        if sha(REPO/path)!=h:raise ValueError('prior artifact changed')
    for name,key in (('development.private.json','development_file_sha256'),('inputs.private.json','input_file_sha256'),('train-examples.json','bank_sha256')):
        if sha(ROOT/name)!=freeze[key]:raise ValueError('frozen input/bank changed')
    ledger_path=REPO/'reports/task3/TASK3_ROUND17_MANUAL_REVIEW_20261020.json'
    ledger=json.loads(ledger_path.read_text());inputs={r['sample_id']:r['query'] for r in json.loads((ROOT/'inputs.private.json').read_text())}
    if len(ledger['rows'])!=72:raise ValueError('review count mismatch')
    summary={};bundle=[]
    for condition in ('control','one_shot','few_shot'):
        folder=ROOT/condition;state=json.loads((folder/'progress.json').read_text())
        notes=[r for r in ledger['rows'] if r['condition']==condition]
        if {r['sample_id'] for r in notes}!=set(inputs):raise ValueError('review IDs mismatch')
        first_json=0;invalid_attempts=0;compiler={'TP':0,'FP':0,'FN':0,'TN':0};tokens=0
        decision_path=folder/'decisions.jsonl';decisions={}
        if decision_path.exists():decisions={a['attempt_id']:a for a in map(json.loads,decision_path.read_text().splitlines())}
        for note in notes:
            sid=note['sample_id'];entry=state['completed'].get(sid) or state['errors'][sid]
            attempts=entry['trace']['attempts'];final=entry.get('output')
            if (digest([a['raw_text'] for a in attempts])!=note['raw_binding_sha256']
                    or digest(final)!=note['final_binding_sha256']):raise ValueError('review bound to different raw/final')
            enriched=[]
            for i,a in enumerate(attempts):
                try:parse_response(a['raw_text']);first_json+=int(i==0)
                except (ValueError,TypeError):invalid_attempts+=1
                reason=a.get('retry_reason')
                if condition=='control' and i:
                    prior=attempts[i-1];d=decisions.get(prior['attempt_id'],{})
                    reason=d.get('error') or d.get('disclosure_violations') or prior.get('runtime_error')
                enriched.append({**a,'retry_reason':reason});tokens+=a.get('output_tokens') or 0
            bundle.append({'condition':condition,'sample_id':sid,'attempts':enriched,'final':final,
                           'unresolved_reason':state['errors'].get(sid,{}).get('reason')})
            if final:
                actual=inputs[sid]['compiler']['status']=='compile_error';pred='Lỗi biên dịch' in final['taxonomy_error']
                compiler['TP' if actual and pred else 'FP' if pred else 'FN' if actual else 'TN']+=1
        quality={key:sum(bool(n[key]) for n in notes) for key in (
            'first_raw_false','any_raw_false','final_false','first_raw_supported','final_supported',
            'false_clean_assurance','L2_strict_useful','L3_strict_feasible_repair','L3_partial_direction',
            'first_raw_L1_disclosure','final_L1_disclosure','L2_concrete_repair_leak')}
        source_wrong_union=sum(n['final_false'] or n['false_clean_assurance'] for n in notes)
        metrics=json.loads((folder/'metrics.json').read_text())
        summary[condition]={'automatic_metrics':metrics,'manual_source_Level':quality,
            'source_wrong_or_false_clean_union':source_wrong_union,
            'source_review_unit':ledger['unit'],'compiler_agreement':compiler,
            'schema_invalid_attempts':invalid_attempts,'first_json_count_verified':first_json,
            'output_tokens_all_attempts':tokens,'final_false_ids':[n['sample_id'] for n in notes if n['final_false']],
            'artifact_hashes':{'progress':sha(folder/'progress.json'),'attempts':sha(folder/'attempts.jsonl'),
                               'predictions':sha(folder/'predictions.json'),'run':sha(folder/'run.json')}}
    result={'decision':'No source-correctness improvement; stop prompt trials, retain R15 zero-shot control. No further prompt/bank/CoT/guard/public run.',
        'single_experiment':True,'conditions':summary,'dataset_v2_zip_sha256':freeze['dataset_v2_zip_sha256'],
        'task3_annotation_v2_sha256':freeze['task3_annotation_v2_sha256'],'freeze_sha256':sha(ROOT/'freeze.json'),
        'manual_review_sha256':sha(ledger_path),'source_review_before_generation_sha256':sha(ROOT/'source-review.pre.md'),
        'bank_sha256':freeze['bank_sha256'],'input_sha256':freeze['input_file_sha256'],
        'confirmed_defect_denominators':ledger['confirmed_defect_denominators'],
        'tests':'631 passed, 4 skipped: full tests/test_task3*.py; no model tests re-run for quality scoring',
        'independent_code_review':'no critical/important findings; 9 R16/R17 contract tests verified; reviewer did not inspect model outputs',
        'protected_prior_artifacts':{'count':len(freeze['protected_prior_files_sha256']),'all_hashes_unchanged':True},
        'source_correctness_claims':'one assistant, not human verified; no statistical superiority claim; subjective/unknown conditions separated',
        'bank_limitations':'eight sources/eight exam families, one bank only; MAXARR and SECONDMAX related extrema tasks; all four positive reference taxonomy sets use Lỗi logic; cannot separate shot count from added clean example contents.'}
    write_json(ROOT/'review/raw-final.private.json',bundle)
    write_json(ROOT/'review/summary.json',result)
    write_json(REPO/'reports/task3/TASK3_ROUND17_RESULTS_20261020.json',result)
    print(json.dumps({c:{'micro':r['automatic_metrics']['taxonomy_v2']['micro_f1'],
         'false':r['manual_source_Level']['final_false'],'L2':r['manual_source_Level']['L2_strict_useful'],
         'L3':r['manual_source_Level']['L3_strict_feasible_repair']} for c,r in summary.items()},ensure_ascii=False))


if __name__=='__main__':main()
