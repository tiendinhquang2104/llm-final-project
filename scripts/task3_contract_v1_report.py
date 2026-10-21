#!/usr/bin/env python3
"""Offline TRAIN-only contract accounting; imports never read artifacts."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys

REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.synth.taxonomy import LABEL_SPACE


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _prf(tp,fp,fn):
    return dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else 0.,recall=tp/(tp+fn) if tp+fn else 0.,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)


def taxonomy(records,predictions,reference_key):
    """Score all ten labels; null reference excluded, abstention never exact-clean."""
    by={r['sample_id']:r for r in predictions};supported=[r for r in records if r.get(reference_key) is not None]
    if len(by)!=len(predictions):raise ValueError('duplicate prediction source')
    per_label={}
    def predicted(r):
        p=by.get(r['sample_id'],{})
        return p.get('output',{}).get('taxonomy_error',[]) if p.get('status')=='completed' else []
    for label in LABEL_SPACE:
        tp=sum(label in r[reference_key] and label in predicted(r) for r in supported)
        fp=sum(label not in r[reference_key] and label in predicted(r) for r in supported)
        fn=sum(label in r[reference_key] and label not in predicted(r) for r in supported)
        per_label[label]=dict(tp=tp,fp=fp,fn=fn,support=tp+fn)
    micro=_prf(*(sum(r[k] for r in per_label.values()) for k in ('tp','fp','fn')))
    macro=sum(_prf(r['tp'],r['fp'],r['fn'])['f1'] for r in per_label.values())/len(LABEL_SPACE)
    if not supported:micro={k:None for k in micro};macro=None
    exact=sum(by.get(r['sample_id'],{}).get('status')=='completed' and set(predicted(r))==set(r[reference_key]) for r in supported)
    return dict(supported_sources=len(supported),excluded_sources=len(records)-len(supported),per_label=per_label,micro=micro,macro_f1=macro,exact_set=dict(numerator=exact,denominator=len(supported)))


def require_complete(predictions,state,expected,*,expected_sources=None):
    ids=[p.get('request_id') for p in predictions]
    if (state.get('complete') is not True or state.get('processed_requests')!=len(expected)
            or len(ids)!=len(expected) or len(set(ids))!=len(ids) or set(ids)!=set(expected)):
        raise ValueError('complete exact cohort required; no prefix metrics')
    if expected_sources is not None and any(p.get('sample_id')!=expected_sources[p['request_id']] for p in predictions):
        raise ValueError('prediction source/request binding mismatch')


def read(path):return json.loads(Path(path).read_bytes())


def journal(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def summarize(work,manifest,rows,reviews=None):
    work=Path(work);preds={};states={};expected=[r['request_id'] for r in rows]
    for arm in ('R15','SHORT'):
        folder=work/'inference'/('arm-'+arm);preds[arm]=read(folder/'predictions.json');states[arm]=read(folder/'status.json')
        require_complete(preds[arm],states[arm],expected,expected_sources={r['request_id']:r['sample_id'] for r in rows})
    # No reference scoring before both canonical cohorts have finished.
    refs=read(work/'frozen/reference.private.json')['records'];result=dict(arms={},source_count=len(rows),annotation_provenance=manifest['annotation_provenance'])
    review_index={}
    for review in reviews or []:
        key=(review['arm'],review['request_id'])
        if key in review_index:raise ValueError('duplicate review')
        p=next((p for p in preds.get(review['arm'],[]) if p['request_id']==review['request_id']),None)
        if p is None:raise ValueError('unknown review request')
        if review.get('output_sha256')!=(digest(p['output']) if p.get('feedback_available') else None):raise ValueError('stale review output digest')
        if not review.get('reviewer') or not review.get('rationale') or not review.get('evidence'):raise ValueError('review evidence required')
        if not isinstance(review.get('assessments'),dict) or any(x is not None and type(x) is not bool for x in review['assessments'].values()):raise ValueError('review flags must be bool/null')
        review_index[key]=review
    for arm in ('R15','SHORT'):
        folder=work/'inference'/('arm-'+arm);generations=journal(folder/'generations.jsonl');decisions=journal(folder/'decisions.jsonl');lengths=[len(p['output']['feedback']) for p in preds[arm] if p.get('feedback_available')]
        fields={k for r in review_index.values() for k in r['assessments']};semantics={}
        for field in sorted(fields):
            values=[r['assessments'].get(field) for (a,_),r in review_index.items() if a==arm]
            actual=[v for v in values if v is not None];semantics[field]=dict(assessed=len(actual),true=sum(actual) if actual else None,false=len(actual)-sum(actual) if actual else None)
        if arm=='SHORT':
            audits=[d['machine_audit'] for d in decisions if d.get('machine_audit')]
            reasons=Counter(e for a in audits for e in a['errors']);warnings=Counter(w for a in audits for w in a['warnings'])
            schema=dict(assessed=len(audits),valid=sum(a['schema_valid'] for a in audits),accepted=sum(a['accepted'] for a in audits),reject_reasons=dict(reasons),warnings=dict(warnings),feedback_errors=dict(Counter(d['error'] for d in decisions if d.get('error') and d['error'].startswith('feedback:'))),feedback_attempts=sum(g['stage']=='feedback' for g in generations),feedback_schema_valid=sum(p.get('feedback_available',False) for p in preds[arm]))
            flow=dict(retries=0,fallbacks=0,raw_to_final_changes=None)
        else:
            legacy=journal(folder/'legacy/decisions.jsonl');schema=dict(assessed=len(legacy),valid=sum(d['schema_valid'] for d in legacy),reject_reasons=dict(Counter(v for d in legacy for v in d.get('disclosure_violations',[]))),invalid_schema=sum(not d['schema_valid'] for d in legacy))
            traces=read(folder/'legacy/traces.json');flow=dict(retries=len(generations)-len(rows),retried_sources=sum(len(t['attempts'])>1 for t in traces),fallbacks=sum(t['fallback_used'] for t in traces),raw_to_final_changes=sum(t['raw_to_final_changed'] for t in traces))
        result['arms'][arm]=dict(statuses=dict(Counter(p['status'] for p in preds[arm])),feedback_available=len(lengths),flow=flow,taxonomy_supplement_annotation=taxonomy(refs,preds[arm],'taxonomy_annotation'),taxonomy_source_review=taxonomy(refs,preds[arm],'source_reference'),schema=schema,semantic_review=semantics,reviewed_requests=sum(a==arm for a,_ in review_index),generation=dict(calls=len(generations),by_stage=dict(Counter(g['stage'] for g in generations)),input_tokens=sum(g.get('input_tokens') or 0 for g in generations),output_tokens=sum(g.get('output_tokens') or 0 for g in generations),latency_s=sum(g.get('latency_s') or 0 for g in generations),finish_reasons=dict(Counter(g['finish_reason'] for g in generations))),feedback_length=dict(count=len(lengths),mean=sum(lengths)/len(lengths) if lengths else None,median=statistics.median(lengths) if lengths else None),per_request_hashes=[dict(request_id=p['request_id'],sample_id=p['sample_id'],status=p['status'],feedback_available=p.get('feedback_available',False),output_sha256=digest(p['output']) if p.get('feedback_available') else None) for p in preds[arm]])
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--score',action='store_true');ap.add_argument('--reviews',type=Path);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if not args.score:ap.error('--score required; no model or training is called')
    from scripts.task3_contract_v1_prepare import verify
    manifest,_,rows=verify();reviews=read(args.reviews) if args.reviews else None
    report=summarize(manifest['work_dir'],manifest,rows,reviews)
    with args.output.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(status='complete',sources=report['source_count'],arms=list(report['arms']))))


if __name__=='__main__':main()
