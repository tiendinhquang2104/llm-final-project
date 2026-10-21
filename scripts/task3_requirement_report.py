#!/usr/bin/env python3
"""Recompute the private study scores; public output contains aggregate/ID data."""
from __future__ import annotations
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.dataset import write_json
from src.task3.feedback_prompt import sha,verify_seal
from src.task3.requirement_evidence import annotation_metrics
ROOT=REPO/'outputs/task3/requirement-evidence-20261021'


def validate_pairs(rows):
    by={arm:{r['sample_id']:r for r in rows if r['arm']==arm}for arm in ('R15','candidate')}
    if any(len(by[a])!=sum(r['arm']==a for r in rows)for a in by):raise ValueError('duplicate ID')
    if set(by['R15'])!=set(by['candidate']):raise ValueError('paired ID sets differ')
    for sid in by['R15']:
        if by['R15'][sid]['level']!=by['candidate'][sid]['level']:raise ValueError('paired Level differs')
        if by['R15'][sid]['reference_status']!=by['candidate'][sid]['reference_status']:raise ValueError('paired reference differs')
    return by


def summarize_semantics(rows,outputs):
    def ratio(n,d,unknown=0):return {'numerator':n,'denominator':d,'rate':n/d if d else None,'unknown':unknown}
    def flag(name,selected=None):
        group=rows if selected is None else selected
        known=[r for r in group if isinstance(r['flags'].get(name),bool)]
        return ratio(sum(r['flags'][name]for r in known),len(known),len(group)-len(known))
    clean=[r for r in rows if r['reference_status']=='clean'];defect=[r for r in rows if r['reference_status']=='defect']
    diagnostic=[r for r in defect if r['level']>=2]
    both=[r for r in diagnostic if r['flags'].get('location_correct')is True and r['flags'].get('cause_correct')is True]
    strict=[r for r in both if r['completion'] and all(r['flags'].get(k)is False for k in ('false_technical_claim','main_defect_missed','false_clean_praise','level_violation'))]
    def output(r):return outputs.get(r['sample_id'])
    nonempty=lambda r:output(r)is not None and bool(output(r)['taxonomy_error'])
    severe=[]
    for r in rows:
        f=r['flags']
        if (r in clean and nonempty(r)) or f.get('false_clean_praise')is True or f.get('false_technical_claim')is True or (r in diagnostic and f.get('main_defect_missed')is True):severe.append(r['sample_id'])
    return {'requested':len(rows),'completed':sum(r['completion']for r in rows),'completion_errors':sum(not r['completion']for r in rows),
      'source_uncertain':sum(r['reference_status']=='uncertain'for r in rows),'clean_support':len(clean),'defect_support':len(defect),
      'clean_nonempty_taxonomy':ratio(sum(nonempty(r)for r in clean),len(clean)),
      'clean_empty_taxonomy':ratio(sum(output(r)is not None and not nonempty(r)for r in clean),len(clean)),
      'defect_nonempty_taxonomy':ratio(sum(nonempty(r)for r in defect),len(defect)),
      'defect_empty_taxonomy':ratio(sum(output(r)is not None and not nonempty(r)for r in defect),len(defect)),
      'false_clean_praise':flag('false_clean_praise',defect),'main_defect_missed':flag('main_defect_missed',defect),
      'location_correct':flag('location_correct',diagnostic),'cause_correct':flag('cause_correct',diagnostic),
      'location_and_cause':ratio(len(both),len(diagnostic)),'strict_useful_diagnosis':ratio(len(strict),len(diagnostic)),
      'false_technical_claim':flag('false_technical_claim'),'level_violation':flag('level_violation'),
      'level12_repair_disclosure':flag('repair_disclosure',[r for r in rows if r['level']<=2]),
      'level3_feasible_repair':flag('feasible_L3_repair',[r for r in rows if r['level']==3]),
      'taxonomy_feedback_aligned':flag('taxonomy_feedback_aligned'),'fallback':ratio(sum(r['fallback_used']for r in rows),len(rows)),
      'severe':ratio(len(severe),len(rows)),'severe_ids':severe,
      'per_level':{str(l):{'support':sum(r['level']==l for r in rows),'level_violation':flag('level_violation',[r for r in rows if r['level']==l])}for l in range(1,5)}}


def main():
    verify_seal(ROOT/'study-freeze.json');verify_seal(ROOT/'semantic-review-freeze.json')
    refs=json.loads((ROOT/'reference-review.private.json').read_text());reviews=json.loads((ROOT/'semantic-review.private.json').read_text());validate_pairs(reviews)
    base={r['sample_id']:r['output']for r in json.loads((ROOT/'R15/predictions.json').read_text())}
    candrows=json.loads((ROOT/'candidate/results.private.json').read_text());cand={r['sample_id']:r['output']for r in candrows}
    scores={};sources={r['sample_id']:r for r in refs}
    for arm,outputs in [('R15',base),('candidate',cand)]:
        scores[arm]={}
        for name,ids in [('all20',set(sources)),('new2',{r['sample_id']for r in refs if r['stratum']=='new'}),('investigation18',{r['sample_id']for r in refs if r['stratum']!='new'}),('template6',{r['sample_id']for r in refs if r['stratum']=='investigation-template-overlap'}),('confirmation12',{r['sample_id']for r in refs if r['stratum']=='investigation-confirmation-exposed'})]:
            orig=[{'sample_id':r['sample_id'],'labels':r['annotation_original']}for r in refs if r['sample_id']in ids and r['annotation_original']is not None]
            scores[arm][name]={'original_annotation':annotation_metrics(orig,outputs),'source_review':summarize_semantics([r for r in reviews if r['arm']==arm and r['sample_id']in ids],outputs)}
    # Complete per-ID redacted comparison: flags, labels, hashes and branch only.
    redacted=[]
    for sid,ref in sources.items():
        by={r['arm']:r for r in reviews if r['sample_id']==sid}
        redacted.append({'sample_id':sid,'stratum':ref['stratum'],'reference_status':ref['status'],'level':by['R15']['level'],
            'annotation_original':ref['annotation_original'],'taxonomy_proposed':ref['taxonomy_proposed'],
            **{arm:{'taxonomy':out[sid]['taxonomy_error']if out.get(sid)is not None else None,'flags':by[arm]['flags'],'output_sha256':by[arm]['output_sha256'],'fallback':by[arm]['fallback_used'],'origin':by[arm]['origin']}for arm,out in [('R15',base),('candidate',cand)]}})
    attempts={}
    for arm,path in [('R15',ROOT/'R15/attempts.jsonl'),('candidate',ROOT/'candidate/attempts.jsonl')]:
        calls=[json.loads(l)for l in path.read_text().splitlines()]
        attempts[arm]={'calls':len(calls),'output_tokens':sum(r.get('output_tokens',0)for r in calls),'generation_latency_s':sum(r.get('latency_s',0)for r in calls),'runtime_errors':sum(bool(r.get('runtime_error')or r.get('error'))for r in calls),'by_stage':{s:sum(r.get('stage','direct')==s for r in calls)for s in ('direct','diagnosis','render')}}
    result={'verdict':'INSUFFICIENT_NEW_EVIDENCE_KEEP_R15; investigated operational variant also trades fewer false accusations for more false-clean outputs',
        'authority':'author-agent review, not human-verified','original_annotation_policy':'Only 8 unmodified raw training archive sources have original labels. Exposed authored12 have no original annotation; never substitute agent labels. New2 have only empty original labels, no positive label support.',
        'source_policy':'New2 uncertain under full unbounded statements; no forced clean or defect. Clean5/defect13 are investigation only. Core diagnosis requires correct location/cause AND no false claim, primary-miss, false-clean or Level violation for strict metric.',
        'severe_definition':'Invented defect on reviewed-clean source OR false-clean praise OR a demonstrably false technical claim OR main defect missed on defect at L2+. Count each ID once; unknown evidence not converted to false.',
        'scores':scores,'attempts':attempts,'candidate_internal':{'operational_uncertain_or_unresolved':sum(r['uncertain']for r in candrows),'explicit_uncertain_requirement':sum(bool(r['diagnosis'])and any(x['status']=='chưa đủ căn cứ'for x in r['diagnosis']['requirements'])for r in candrows),'fallback':sum(r['fallback_used']for r in candrows),'completed':sum(r['output']is not None for r in candrows),'requested':len(candrows)},
        'study_freeze_sha256':sha(ROOT/'study-freeze.json'),'semantic_review_sha256':sha(ROOT/'semantic-review-freeze.json'),'paired_ids':redacted}
    write_json(ROOT/'metrics.json',result)
    write_json(REPO/'reports/task3/TASK3_REQUIREMENT_EVIDENCE_RESULTS_20261021.json',result)
    print(json.dumps({'verdict':result['verdict'],'original8':{a:scores[a]['all20']['original_annotation']for a in scores},'semantic_all20':{a:scores[a]['all20']['source_review']for a in scores},'attempts':attempts,'internal':result['candidate_internal']},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
