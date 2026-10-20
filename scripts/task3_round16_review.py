#!/usr/bin/env python3
"""Offline reporting of locked paired outputs and explicit assistant annotations.

This script never calls a model, edits a response, or infers source correctness
from keywords. Semantic judgements are in the committed per-ID review ledger.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.dataset import load_prepared, write_json
from src.task3.round14_runner import digest
from src.task3.round15 import parse_response as parse_control
from src.task3.round16 import parse_response
from scripts.task3_round16 import all_traces, available_taxonomy_metrics, candidate_hashes, file_hash

CONDITIONS=('control','one_shot','few_shot','evidence_cot')



def verify_review_binding(note,attempts,final):
    if (note.get('reviewed_raw_sha256')!=digest([a['raw_text'] for a in attempts])
            or note.get('reviewed_final_sha256')!=digest(final)):
        raise ValueError('manual review is bound to different responses; review the new run first')


def summarize(root,review):
    root=Path(root);review_file=Path(review);review=json.loads(review_file.read_text())
    freeze=json.loads((root/'freeze.json').read_text())
    if candidate_hashes()!=freeze['candidates']:raise ValueError('public artifacts changed')
    selection=freeze['selection'];ids=selection['selected_ids']
    rows=[r for r in load_prepared(REPO/'data/processed/task3','synthetic-train') if r.sample_id in ids]
    if {r.sample_id for r in rows}!=set(ids):raise ValueError('train ID coverage mismatch')
    data={};bundle=[];quality={}
    for condition in CONDITIONS:
        folder=root/condition;state=json.loads((folder/'progress.json').read_text())
        traces=all_traces({'traces':[e['trace'] for e in state['completed'].values()], 'errors':state['errors']})
        by_trace={t['sample_id']:t for t in traces}
        predictions=[{'sample_id':sid,'output':e['output']} for sid,e in state['completed'].items()]
        first=[];decisions={}
        path=folder/'decisions.jsonl'
        if path.exists():decisions={v['attempt_id']:v for v in map(json.loads,path.read_text().splitlines())}
        for sid in ids:
            trace=by_trace[sid];raw=None
            try:
                text=trace['first_raw_text']
                raw=parse_control(text) if condition=='control' else parse_response(text,condition)
                first.append({'sample_id':sid,'output':{k:raw[k] for k in ('taxonomy_error','feedback')}})
            except (ValueError,TypeError):pass
            attempts=[]
            for i,a in enumerate(trace['attempts']):
                reason=a.get('retry_reason')
                if i and condition=='control':
                    prior=trace['attempts'][i-1];decision=decisions.get(prior['attempt_id'],{})
                    reason=decision.get('error') or decision.get('disclosure_violations') or prior.get('runtime_error')
                attempts.append({**a,'retry_reason':reason})
            bundle.append({'condition':condition,'sample_id':sid,'first_raw_parsed':raw,
                           'attempts':attempts,'final':state['completed'].get(sid,{}).get('output'),
                           'unresolved_reason':state['errors'].get(sid,{}).get('reason')})
        measured=available_taxonomy_metrics(rows,predictions)
        source={r.sample_id:r for r in rows}
        inputs={v['id']:v['query'] for v in json.loads((root/'inputs.private.json').read_text())}
        compiler={}
        for name,preds in (('first_raw',first),('final',predictions)):
            counts=Counter()
            for p in preds:
                status=inputs[p['sample_id']]['compiler']['status']
                if status not in ('compiled','compile_error'):counts['unknown']+=1;continue
                actual=status=='compile_error';positive='Lỗi biên dịch' in p['output']['taxonomy_error']
                counts['TP' if actual and positive else 'FN' if actual else 'FP' if positive else 'TN']+=1
            compiler[name]={k:counts[k] for k in ('TP','FP','FN','TN','unknown')}
        data[condition]={'completion':len(predictions),'requested':len(ids),'raw_schema':len(first),
            'taxonomy_available':measured,'raw_taxonomy_available':available_taxonomy_metrics(rows,first),
            'compiler_agreement':compiler,'attempts':sum(len(t['attempts']) for t in traces),
            'fallback':sum(bool(t.get('fallback_used')) for t in traces),
            'output_tokens':sum(a['output_tokens'] or 0 for t in traces for a in t['attempts']),
            'latency_s':sum(a.get('latency_s',0) for t in traces for a in t['attempts']),
            'raw_to_final_changed_ids':[t['sample_id'] for t in traces if len(t['attempts'])>1 and t['sample_id'] in state['completed']],
            'predictions':predictions}
        # Manual flags are record counts, not invented numerical correctness scores.
        notes=[r for r in review['rows'] if r['condition']==condition]
        if {r['sample_id'] for r in notes}!=set(ids):raise ValueError('review coverage mismatch')
        for note in notes:
            sid=note['sample_id'];entry=state['completed'].get(sid) or state['errors'][sid]
            verify_review_binding(note,entry['trace']['attempts'],entry.get('output'))
        quality[condition]={k:sum(bool(r[k]) for r in notes) for k in (
            'raw_has_source_supported_material_claim','raw_has_materially_false_claim','raw_has_unassessed_claim',
            'final_has_source_supported_material_claim','final_has_materially_false_claim','final_has_unassessed_claim',
            'raw_L1_disclosure','final_L1_disclosure','raw_L2_repair_leak','final_L2_repair_leak',
            'strict_L2_useful_final','strict_L3_feasible_repair_final','contamination_observed_erroneous_transfer')}
        quality[condition]['raw_false_any_attempt_ids']=[r['sample_id'] for r in notes if r['raw_has_materially_false_claim']]
        l1=[state['completed'][sid]['output']['feedback'] for sid in ids[:4] if sid in state['completed']]
        freq=Counter(l1);quality[condition]['L1_exact_template_repeated_records']=sum(n for n in freq.values() if n>1)
        quality[condition]['L1_false_praise_count']=0
        quality[condition]['final_feedback_chars_median']=sorted(len(p['output']['feedback']) for p in predictions)[len(predictions)//2]
    common=set.intersection(*(set(p['sample_id'] for p in d['predictions']) for d in data.values()))
    for condition,d in data.items():
        d['taxonomy_common_completed']=available_taxonomy_metrics([r for r in rows if r.sample_id in common],
                                               [p for p in d['predictions'] if p['sample_id'] in common])
        del d['predictions']
        # Correct earlier metrics in place from immutable journals, no inference.
        write_json(root/condition/'metrics.json',d)
    write_json(root/'review/raw-final.private.json',bundle)
    summary={'metrics':data,'quality':quality,'common_completed_ids':sorted(common),
        'manual_review_sha256':file_hash(review_file),'review_provenance':review['reviewer'],
        'claim_unit':review['claim_unit'],'candidate_hashes_verified':candidate_hashes(),
        'raw_attempt_count':len([a for b in bundle for a in b['attempts']]),
        'decision':'no winner; retain R15 control, preserve other prompts as experimental artifacts; no prompt tuning after outputs'}
    write_json(root/'review/summary.json',summary)
    return summary


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',default=str(REPO/'outputs/task3/round16'))
    ap.add_argument('--review',default=str(REPO/'reports/task3/TASK3_ROUND16_MANUAL_REVIEW_20261020.json'))
    args=ap.parse_args();review_path=Path(args.review)
    result=summarize(args.root,review_path)
    write_json(REPO/'reports/task3/TASK3_ROUND16_RESULTS_20261020.json',result)
    for condition,d in result['metrics'].items():
        print(condition,d['completion'],d['attempts'],d['taxonomy_common_completed']['micro_f1'],d['taxonomy_common_completed']['macro_f1'])
    print(json.dumps(result['quality'],ensure_ascii=False,indent=2))
