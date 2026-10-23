#!/usr/bin/env python3
"""Seal independent reviews and replay fixed-denominator compact accounting."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from src.task3 import grounded as g,grounded_metrics as metrics
from src.task3.dataset import write_json
from src.task3.level_blind import read,sha,digest
from task3_compact import OUT

FIELDS=['finding_supported','main_error_covered_in_feedback','feedback_false_claim',
        'feedback_taxonomy_consistent','level_compliant','natural_vietnamese','generic_feedback',
        'taxonomy_missing','taxonomy_extra']


def runtime_snapshots():
    for name in ['p1-v1','p1-v2','renderer']:
        d=OUT/name;m=read(d/'freeze.json')
        g.require(sha(d/'freeze.json')==(d/'freeze.sha256').read_text().strip(),'freeze drift:'+name)
        fields=m.get('implementation_sha256',m.get('code_sha256'))
        for path,h in fields.items():g.require(sha(d/'code'/path)==h,'original runtime snapshot drift')
        source='units.private.json'if name.startswith('p1')else'cases.private.json'
        g.require(sha(d/source)==m.get('units_sha256',m.get('cases_sha256')),'runtime source drift')
        for line in (d/'candidate/attempts.jsonl').read_text().splitlines():
            row=json.loads(line);g.require(row['prompt_sha256']==digest(row['messages']),'raw prompt hash drift')
    return True


def current_outputs():
    original=read(ROOT/'outputs/task3/grounded-20261023/development/C0/completed.predictions.json')
    control={x['sample_id']:x['output']for x in original};values={}
    for u,row in zip(read(OUT/'p1-selection.private.json'),read(OUT/'p1-v2/results.private.json')):
        rid=u['request_id'];g.require(row['request_id']==rid,'production ID drift')
        for arm,value in {'R15':{'status':'resolved','output':control[rid]},'G':row['grounded'],'GR':row['final']}.items():values[(rid,arm)]=value
    for row in read(OUT/'renderer/results.private.json'):
        for arm,value in row['arms'].items():values[(row['request_id']+'@renderer',arm)]=value
    return values


def validate_reviews():
    runtime_snapshots();r=OUT/'review'
    source_seal=read(r/'source-seal.json')
    for name,h in source_seal['reviewers'].items():g.require(sha(r/name)==h,'source review drift')
    for name,h in read(r/'output-packet-seal.json').items():g.require(sha(r/name)==h,'review packet drift')
    key=read(r/'key.private.json');values=current_outputs()
    for bid,k in key.items():
        g.require(bid==digest(['compact-review-v1',k['request_id'],k['arm']])[:20],'blinded mapping drift')
        g.require(digest(values[(k['request_id'],k['arm'])].get('output'))==k['output_sha256'],'reviewed output drift')
    indexed={}
    for reviewer in ['a','b']:
        packet=read(r/f'outputs-{reviewer}.private.json');cases={x['request_id']:x for x in packet['cases']};reviews={}
        expected={o['blind_id']for x in cases.values()for o in x['outputs']}
        for case in read(r/f'output-review-{reviewer}.private.json')['cases']:
            task=cases[case['request_id']]['task'];level=cases[case['request_id']]['level']
            for v in case['outputs']:
                bid=v['blind_id'];g.require(bid in expected and bid not in reviews,'review identity duplicate/mismatch')
                g.require(key[bid]['request_id']==case['request_id'],'cross-case review')
                value=values[(key[bid]['request_id'],key[bid]['arm'])]
                o=next(x for x in cases[case['request_id']]['outputs']if x['blind_id']==bid)
                g.require(o['output']==value.get('output')and o['status']==value['status'],'packet status/content drift')
                g.validate_taxonomy(v['taxonomy_missing']);g.validate_taxonomy(v['taxonomy_extra'])
                g.require(v['finding_supported']in {'yes','no','disputed'},'invalid support verdict')
                for field in FIELDS[1:6]:g.require(v[field]in {'yes','no'},'review yes/no field')
                g.require(type(v['generic_feedback'])is bool and type(v['source_disputed'])is bool,'review booleans')
                for field,at in [('L1_specific_location_or_cause_leak',1),('L2_repair_leak_explicit_or_implicit',2),('L3_actionable_repair_direction',3)]:
                    flag=v[field];g.require((flag is None)or(type(flag)is bool and at==level),'Level flag mismatch')
                    if value['status']=='resolved'and level==at:g.require(type(flag)is bool,'observable Level flag missing')
                text=(value.get('output')or{}).get('feedback','')
                g.require(bool(v['source_evidence_for_verdict']),'evidence missing')
                requirement=task['statement']+'\n'+'\n'.join(p.get('statement','')for p in task['problems'])
                for e in v['source_evidence_for_verdict']:
                    g.require(bool(e['source_quote'])and(e['source_quote']in task['code']or e['source_quote']in requirement),'review source quote mismatch')
                    g.require(e['feedback_quote']in text and bool(e['reason']),'review feedback quote/rationale mismatch')
                reviews[bid]=v
        g.require(set(reviews)==expected,'review coverage incomplete');indexed[reviewer]=reviews
    g.require(set(indexed['a'])==set(key),'primary review coverage drift')
    attempts=read(r/'guard-attempts.private.json')['attempts'];attempt_refs={x['blind_id']:x for x in attempts}
    judgements=read(r/'guard-review-a.private.json')['attempts']
    g.require({x['blind_id']for x in judgements}==set(attempt_refs)and len(judgements)==len(attempt_refs),'guard review coverage')
    for v in judgements:
        x=attempt_refs[v['blind_id']];g.require(type(v['acceptable'])is bool,'guard accept bool')
        g.require(bool(v['source_quote'])and(v['source_quote']in x['task']['code']or v['source_quote']in x['task']['statement']),'guard source quote')
        g.require(v['feedback_quote']in x['feedback']and bool(v['reason']),'guard evidence')
    return key,indexed,values


def seal():
    validate_reviews();r=OUT/'review';p=r/'review-seal.json';g.require(not p.exists(),'reviews already sealed')
    files=['source-seal.json','output-packet-seal.json','output-review-a.private.json','output-review-b.private.json',
           'guard-review-a.private.json','guard-fixture-review-b.private.json']
    write_json(p,dict(source_before_outputs_and_gold=True,authority='independent Codex agents, not human verified',
        hashes={name:sha(r/name)for name in files}))
    print(json.dumps({'sealed':True,'sha256':sha(p)}))


def strict(v,completed):
    return metrics.joint_pass(v,completed)and not v['generic_feedback']and v['natural_vietnamese']=='yes'and not v['source_disputed']


def disagrees(left,right):
    return bool(right and any((set(left[f])!=set(right[f]))if f in {'taxonomy_missing','taxonomy_extra'}else left[f]!=right[f]for f in FIELDS))


def seal_artifacts():
    """Supplement the immutable review seal with exact scored/runtime bytes."""
    p=OUT/'review/artifact-seal.json';g.require(not p.exists(),'artifact seal exists')
    paths=[OUT/'p1-selection.private.json']
    for name in ['p1-v1','p1-v2','renderer']:
        d=OUT/name
        paths += [d/n for n in ['freeze.json','freeze.sha256','results.private.json','run.private.json','candidate/attempts.jsonl']]
        paths.append(d/('units.private.json'if name.startswith('p1')else'cases.private.json'))
    paths += [OUT/'renderer/guard-probes.private.json',OUT/'renderer/guard-fixtures.private.json']
    write_json(p,dict(review_seal_sha256=sha(OUT/'review/review-seal.json'),hashes={str(x.relative_to(OUT)):sha(x)for x in paths}))
    print(json.dumps({'artifact_seal_sha256':sha(p)}))


def accounting(rows,arms,refs,key,reviews,values):
    reverse={(k['request_id'],k['arm']):bid for bid,k in key.items()};result={};casebook=[]
    for arm in arms:
        predictions=[(values[(u['request_id'],arm)].get('output')or{}).get('taxonomy_error')for u in rows]
        valid=[values[(u['request_id'],arm)]['status']=='resolved'for u in rows]
        verdicts=[reviews['a'][reverse[(u['request_id'],arm)]]for u in rows]
        dispute=[]
        for u,v in zip(rows,verdicts):
            b=reverse[(u['request_id'],arm)];other=reviews['b'].get(b)
            dispute.append(disagrees(v,other))
        taxonomy=metrics.taxonomy_metrics([refs[u['sample_id']]['gold']for u in rows],predictions)
        source=metrics.taxonomy_metrics([refs[u['sample_id']]['source']for u in rows],predictions)
        feedback=dict(completed=sum(valid),unresolved=len(rows)-sum(valid),
            main_covered=sum(ok and v['main_error_covered_in_feedback']=='yes'for ok,v in zip(valid,verdicts)),
            false_claims=sum(ok and v['feedback_false_claim']=='yes'for ok,v in zip(valid,verdicts)),
            inconsistent=sum(ok and v['feedback_taxonomy_consistent']=='no'for ok,v in zip(valid,verdicts)),
            level_noncompliant=sum(ok and v['level_compliant']=='no'for ok,v in zip(valid,verdicts)),
            natural=sum(ok and v['natural_vietnamese']=='yes'for ok,v in zip(valid,verdicts)),
            generic=sum(ok and v['generic_feedback']for ok,v in zip(valid,verdicts)),
            support_disputed=sum(v['finding_supported']=='disputed'for v in verdicts),
            reviewer_disagreement=sum(dispute),old_joint_A=sum(metrics.joint_pass(v,ok)for v,ok in zip(verdicts,valid)),
            strict_joint_A=sum(strict(v,ok)for v,ok in zip(verdicts,valid)),
            strict_joint_conservative=sum(strict(v,ok)and not disputed for v,ok,disputed in zip(verdicts,valid,dispute)))
        for field,l in [('L1_specific_location_or_cause_leak',1),('L2_repair_leak_explicit_or_implicit',2),('L3_actionable_repair_direction',3)]:
            feedback[field]=dict(observable=sum(ok and u['level']==l for ok,u in zip(valid,rows)),
                count=sum(ok and v[field]is True for ok,v in zip(valid,verdicts)))
        result[arm]=dict(taxonomy_original=taxonomy,taxonomy_source_A=source,feedback=feedback)
    for u in rows:
        data=dict(sample_id=u['sample_id'],request_id=u['request_id'],level=u['level'],
            gold_disagreement=set(refs[u['sample_id']]['gold'])!=set(refs[u['sample_id']]['source']),arms={})
        for arm in arms:
            bid=reverse[(u['request_id'],arm)];v=reviews['a'][bid];other=reviews['b'].get(bid);value=values[(u['request_id'],arm)]
            data['arms'][arm]=dict(completed=value['status']=='resolved',strict_joint_A=strict(v,value['status']=='resolved'),
                reviewer_disagreement=disagrees(v,other),
                review_A={k:v[k]for k in FIELDS},review_B={k:other[k]for k in FIELDS}if other else None)
        casebook.append(data)
    return dict(count=len(rows),arms=result,casebook=casebook)


def score():
    r=OUT/'review';seal=read(r/'review-seal.json')
    artifacts=read(r/'artifact-seal.json')
    g.require(sha(r/'review-seal.json')==artifacts['review_seal_sha256'],'review seal drift')
    for name,h in artifacts['hashes'].items():g.require(sha(OUT/name)==h,'scored runtime/output artifact drift:'+name)
    for name,h in seal['hashes'].items():g.require(sha(r/name)==h,'review changed after seal')
    key,reviews,values=validate_reviews()
    # Only after the independent source/output seals do original labels enter accounting.
    original=read(ROOT/'outputs/task3/eval-freeze-v2-20261021/frozen/train-eligible.private.json')
    gold={x['sample_id']:x['annotation_v2']for x in original}
    source={x['sample_id']:x['source_taxonomy']for x in read(r/'source-a.private.json')['cases']}
    refs={sid:dict(gold=gold[sid],source=source[sid])for sid in source}
    prod=read(OUT/'p1-selection.private.json')
    oracle=[{**x['unit'],'request_id':x['unit']['request_id']+'@renderer'}for x in read(OUT/'renderer/cases.private.json')]
    summary=dict(verdict='retain R15; P1 failed; no P2 or new evaluation/public inference',
        production_P1=accounting(prod,['R15','G','GR'],refs,key,reviews,values),
        offline_oracle_renderer=accounting(oracle,['C1','C2'],refs,key,reviews,values),
        references=refs,source_overlap=read(r/'source-seal.json')['overlap'],
        limits=['8 prior-exposed development sources; no fresh evaluation.','Oracle renderer is not production accuracy.',
                'All post-run correctness fixes tested on artificial data only; frozen model results not rerun.',
                'Strict joint requires non-generic and natural; old joint reported separately.',
                'Conservative joint withholds credit on any overlapping reviewer disagreement.'],cost={})
    for name in ['p1-v1','p1-v2','renderer']:
        attempts=[json.loads(x)for x in (OUT/name/'candidate/attempts.jsonl').read_text().splitlines()]
        groups={}
        for x in attempts:
            group='guard_fixture'if x['key'].startswith('fixture/')else 'rescue_support'if '/support'in x['key']else'rescue'if '/rescue/'in x['key']else'diagnosis'if '/diagnosis/'in x['key']else'render_guard'if x['key'].endswith('/guard')else'render'
            group=groups.setdefault(group,dict(calls=0,input_tokens=0,output_tokens=0,latency_s=0.0))
            group['calls']+=1;group['input_tokens']+=x['input_tokens'];group['output_tokens']+=x['output_tokens']or 0;group['latency_s']+=x['latency_s']
        summary['cost'][name]=groups
    guard_j={x['blind_id']:x for x in read(r/'guard-review-a.private.json')['attempts']};guard_key=read(r/'guard-attempt-key.private.json')
    rows={x['key']:x for x in [json.loads(s)for s in (OUT/'renderer/candidate/attempts.jsonl').read_text().splitlines()]}
    decisions=[]
    for bid,k in guard_key.items():
        if '/C2/'not in k['key']or k['key']+'/guard'not in rows:continue
        try:actual=g.parse_guard(rows[k['key']+'/guard']['raw_text'])['accepted']
        except (ValueError,KeyError,TypeError):actual=None
        decisions.append(dict(blind_id=bid,actual=actual,reviewer=guard_j[bid]['acceptable'],disputed=guard_j[bid]['source_disputed']))
    summary['semantic_guard_generated']=dict(observed=len(decisions),
        false_accept=sum(x['actual']is True and not x['reviewer']for x in decisions),
        false_reject=sum(x['actual']is False and x['reviewer']for x in decisions),
        parse_failure=sum(x['actual']is None for x in decisions),
        reviewer_disputed=sum(x['disputed']for x in decisions),decisions=decisions)
    probes=read(OUT/'renderer/guard-probes.private.json');fixture_b={x['id']:x for x in read(r/'guard-fixture-review-b.private.json')['fixtures']}
    g.require(set(fixture_b)=={x['id']for x in probes},'fixture reviewer coverage')
    summary['guard_fixtures']=dict(count=len(probes),expected_accept=sum(x['expected_accept']for x in probes),
        actual_accept=sum(x['actual_accept']is True for x in probes),
        false_accept=sum(x['actual_accept']is True and not x['expected_accept']for x in probes),
        false_reject=sum(x['actual_accept']is False and x['expected_accept']for x in probes),
        reviewer_disagreement=sum(x['expected_accept']!=fixture_b[x['id']]['acceptable']for x in probes))
    write_json(OUT/'metrics.private.json',summary)
    print(json.dumps({k:v for k,v in summary.items()if k not in ['production_P1','offline_oracle_renderer','references','cost']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['seal','seal-artifacts','score','verify']);a=p.parse_args()
    {'seal':seal,'seal-artifacts':seal_artifacts,'score':score,'verify':lambda:print(json.dumps({'runtime_snapshots_verified':runtime_snapshots()}))}[a.phase]()
