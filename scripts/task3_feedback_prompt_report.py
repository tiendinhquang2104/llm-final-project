#!/usr/bin/env python3
"""Reproduce offline metrics and verify every rendered prompt against frozen code."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys

REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.synth.taxonomy import LABEL_SPACE
from src.task3.dataset import write_json
from src.task3.feedback_prompt import verify_seal,sha,proxy_score,fitted
from src.task3.feedback_prompt_report import validate_reviews,paired,decision,audit_payload
from src.task3.schema import Task3Record
from src.task3 import round15
from src.task3.round15_disclosure import disclosure_violations
from src.task3.inference import load_tokenizer
from src.task3.submission import validate_submission

ROOT=REPO/'outputs/task3/feedback-prompt-20261021'


def taxonomy_metrics(reference,pred):
    tp=fp=fn=0;per={}
    for label in LABEL_SPACE:
        t=sum(label in reference[s] and label in pred[s]['taxonomy_error'] for s in reference)
        f=sum(label not in reference[s] and label in pred[s]['taxonomy_error'] for s in reference)
        n=sum(label in reference[s] and label not in pred[s]['taxonomy_error'] for s in reference)
        per[label]={'tp':t,'fp':f,'fn':n,'f1':2*t/(2*t+f+n) if 2*t+f+n else 0}
        tp+=t;fp+=f;fn+=n
    return {'micro_f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
            'macro_f1_10_labels':sum(x['f1'] for x in per.values())/10,'per_label':per}


def uncertainty(reviews):
    by={a:{r['sample_id']:r for r in reviews if r['arm']==a} for a in 'AC'}
    differences=[by['C'][s]['score']-by['A'][s]['score'] for s in by['A']]
    rng=random.Random(20261021)
    means=sorted(sum(rng.choices(differences,k=len(differences)))/len(differences) for _ in range(10000))
    return {'paired_mean_difference':sum(differences)/len(differences),'bootstrap_95_percent_interval':[means[249],means[9749]],
            'method':'10,000 fixed-seed paired source bootstrap; descriptive only, shared task families/author review violate independent sampling; not leaderboard uncertainty'}


def summarize(reviews,predictions,traces,references):
    out={}
    flags=['false_technical_claim','false_clean','location_correct','cause_correct','feasible_repair','generic','level_violation','repair_disclosure','unknown']
    for arm,items in predictions.items():
        g=[r for r in reviews if r['arm']==arm]
        out[arm]={'n':len(g),'mean_proxy':sum(r['score'] for r in g)/len(g),'sum_proxy':sum(r['score'] for r in g),
          **{k:sum(bool(r.get(k)) for r in g) for k in flags},
          'core_finding_coverage':{'covered':sum(r.get('covered_findings',0) for r in g),'total':sum(r.get('total_findings',0) for r in g),'scope':'preselected core findings only; not exhaustive coverage of every source defect'},
          'per_level':{str(l):{'n':len(h:=[r for r in g if r['level']==l]),'mean_proxy':sum(r['score'] for r in h)/len(h),**{k:sum(bool(r.get(k)) for r in h) for k in flags}} for l in range(1,5)},
          'taxonomy_source_core_reference':taxonomy_metrics({r['sample_id']:r['taxonomy'] for r in references},items),
          'fallback':sum(t['fallback_used'] for t in traces[arm]),'retries':sum(max(0,len(t['attempts'])-1) for t in traces[arm]),
          'raw_first_regex_disclosure':sum(bool(t.get('first_raw_disclosure_violations')) for t in traces[arm]),
          'final_regex_disclosure':sum(bool(disclosure_violations(items[t['sample_id']]['feedback'],next(r['level'] for r in g if r['sample_id']==t['sample_id']))) for t in traces[arm])}
    return out


def audit_run(phase,arm,tokenizer,bank,records):
    out=ROOT/phase/arm;run=json.loads((out/'run.json').read_text());cfg=run['config']
    if sha(out/'predictions.json')!=run['output_sha256'] or sha(out/'attempts.jsonl')!=run['attempts_sha256']:raise ValueError('output/journal binding mismatch')
    if cfg['prompt_freeze_sha256']!=sha(ROOT/'prompt-freeze.json'):raise ValueError('prompt freeze binding mismatch')
    if cfg['input_sha256']!=sha(ROOT/(phase+'-inputs.private.json')):raise ValueError('input binding mismatch')
    pred={x['sample_id']:x['output'] for x in json.loads((out/'predictions.json').read_text())}
    trace=json.loads((out/'traces.json').read_text());index={r.sample_id:r for r in records};last_error={}
    calls=0;payloads=0
    for line in (out/'attempts.jsonl').read_text().splitlines():
        attempt=json.loads(line);r=index[attempt['sample_id']];level=int(r.target_feedback_level[6])
        callcfg=dict(cfg,max_new_tokens=cfg['level4_max_tokens'] if level==4 else cfg['max_new_tokens'])
        examples=[e for e in bank if e['level']==level] if arm=='C' else []
        if arm=='A':expected,budget=round15.fitted_messages(r,[],tokenizer,callcfg,retry=last_error.get(r.sample_id))
        else:expected,budget=fitted(r,examples,tokenizer,callcfg,arm=arm,retry=last_error.get(r.sample_id))
        if expected!=attempt['prompt_messages']:raise ValueError('rendered prompt differs from frozen implementation')
        for msg in expected:
            if msg['role']=='user' and msg['content'].startswith('{'):
                audit_payload(json.loads(msg['content']));payloads+=1
        for key in ('input_tokens','examples_used','examples_dropped'):
            if budget[key]!=attempt[key]:raise ValueError('token budget binding mismatch')
        if attempt.get('runtime_error'):last_error[r.sample_id]=attempt['runtime_error']
        else:
            try:
                parsed=round15.parse_response(attempt['raw_text']);v=disclosure_violations(parsed['feedback'],level)
                if v:last_error[r.sample_id]='disclosure: '+','.join(v)
            except (ValueError,TypeError,KeyError) as exc:last_error[r.sample_id]=str(exc)
        calls+=1
    validation=validate_submission(out/'predictions.json',{r.sample_id:r.target_feedback_level for r in records})
    return pred,trace,{'attempts':calls,'scalar_payloads_audited':payloads,'all_full_messages_exact_replay':True,'validator':validation,'output_sha256':sha(out/'predictions.json'),'identity':run['identity']}


def main():
    import os
    os.environ['HF_HOME']=str(REPO/'outputs/task3/hf-cache');os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    for name in ['prompt','fresh','calibration-review','selection','fresh-output','fresh-review']:
        verify_seal(ROOT/(name+'-freeze.json'))
    cfg=json.loads((REPO/'configs/task3/feedback_prompt_20261021.json').read_text());tokenizer=load_tokenizer(cfg)
    bank=json.loads((ROOT/'bank.private.json').read_text());result={};audits={}
    for phase,arms in [('calibration','ABC'),('fresh','AC')]:
        records=[Task3Record(**r) for r in json.loads((ROOT/(phase+'-inputs.private.json')).read_text())]
        refs=json.loads((ROOT/(phase+'-reference.private.json')).read_text());reviews=json.loads((ROOT/(phase+'-review.private.json')).read_text())
        pred={};traces={};audits[phase]={}
        for arm in arms:pred[arm],traces[arm],audits[phase][arm]=audit_run(phase,arm,tokenizer,bank,records)
        validate_reviews([{'sample_id':r.sample_id,'code':r.code} for r in records],{a:{s:x['feedback'] for s,x in items.items()} for a,items in pred.items()},reviews)
        for r in reviews:
            if r['score']!=proxy_score(r,r['level'],r['clean']):raise ValueError('review proxy formula mismatch')
        result[phase]=summarize(reviews,pred,traces,refs)
        if phase=='calibration':
            result['calibration_paired']={arm:paired([r for r in reviews if r['arm'] in ['A',arm]],arm) for arm in 'BC'}
        else:
            result['decision']=decision(reviews,complete=all(len(x)==len(records) for x in pred.values()))
            result['fresh_uncertainty']=uncertainty(reviews)
            strict=[r for r in reviews if not r['isolation_unknown']];ids={r['sample_id'] for r in strict}
            result['strict44']={a:{'n':len(g:=[r for r in strict if r['arm']==a]),'mean_proxy':sum(r['score'] for r in g)/len(g)} for a in 'AC'}
            result['strict44_decision']=decision(strict,complete=True)
            result['strict44_uncertainty']=uncertainty(strict)
            result['strict44_distribution']={str(l):sum(r['level']==l and r['arm']=='A' for r in strict) for l in range(1,5)}
    original=json.loads((ROOT/'protected-hashes.json').read_text())
    changed=[name for name,h in original.items() if not Path(name).is_file() or sha(name)!=h]
    if changed:raise ValueError('pre-existing artifact changed: '+str(changed))
    result['preservation']={'unchanged_session_start_paths':len(original),'changed':changed,'historical_root_prediction_hash_differs_from_R15':True}
    result['journal_audit']=audits
    write_json(ROOT/'results.json',result)
    print(json.dumps({'decision':result['decision'],'fresh':{a:{k:v for k,v in g.items() if k in ['n','mean_proxy','false_technical_claim','false_clean','repair_disclosure']} for a,g in result['fresh'].items()},'strict44':result['strict44'],'audited_attempts':sum(x['attempts'] for phase in audits.values() for x in phase.values())},ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
