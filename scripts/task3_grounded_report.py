#!/usr/bin/env python3
"""Blinded source-first review packets and fixed-denominator paired accounting."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3 import grounded as g
from src.task3 import grounded_metrics as metrics
from src.task3.dataset import write_json
from src.task3.level_blind import digest,read,sha
from src.synth.taxonomy import LABEL_SPACE
from task3_grounded_inventory import DEFAULT,PARENT

RUBRIC={
 'finding_supported':'yes/no/disputed: support for taxonomy and asserted feedback claims from actual source',
 'taxonomy_missing':'list of official labels warranted by source, absent from output',
 'taxonomy_extra':'list of official labels in output unsupported by source',
 'main_error_covered_in_feedback':'yes/no (L1 appropriate general alert counts, no detail required)',
 'feedback_false_claim':'yes/no',
 'feedback_taxonomy_consistent':'yes/no',
 'level_compliant':'yes/no',
 'L1_specific_location_or_cause_leak':'boolean or null outside L1',
 'L2_repair_leak_explicit_or_implicit':'boolean or null outside L2',
 'L3_actionable_repair_direction':'boolean or null outside L3',
 'natural_vietnamese':'yes/no',
 'generic_feedback':'boolean; L1 permitted general hint is not automatically generic failure',
 'source_evidence_for_verdict':'nonempty list of {source_quote, feedback_quote, reason}; exact short quotes',
 'gold_disagreement':'pending until source-first review sealed; then yes/no and reason separately',
 'joint_pass_rationale':'brief explanation, no human-verified claim'
}


def outputs(out,split):
    d=out/split;units=read(d/'units.private.json')
    control={r['sample_id']:r['output']for r in read(d/'C0/completed.predictions.json')}
    candidate={r['request_id']:r for r in read(d/'candidate/results.private.json')}
    result=[]
    for u in units:
        arms={'C0':dict(status='resolved' if u['request_id'] in control else 'unresolved',output=control.get(u['request_id']))}
        for arm in ['C1','C2']:arms[arm]=candidate[u['request_id']]['arms'][arm]
        result.append(dict(unit=u,arms=arms))
    return result


def packets(out,split):
    d=out/split/'review';g.require(not d.exists(),'review packet already exists')
    rows=outputs(out,split);key={};cases=[]
    for row in rows:
        u=row['unit'];arms=[]
        for arm,value in row['arms'].items():
            blind=digest(['grounded-blind-v1',u['request_id'],arm])[:20]
            key[blind]=dict(request_id=u['request_id'],sample_id=u['sample_id'],arm=arm,output_sha256=digest(value.get('output')))
            arms.append(dict(blind_id=blind,status=value['status'],output=value.get('output')))
        arms.sort(key=lambda a:a['blind_id'])
        cases.append(dict(request_id=u['request_id'],sample_id=u['sample_id'],target_level=u['level'],task=u['task'],outputs=arms))
    d.mkdir();write_json(d/'key.private.json',key)
    instructions=('Independent Codex agent review, never human-verified. Read statement/source BEFORE outputs. '
       'Do not read key/gold/generator findings/traces. For each source first record source_taxonomy, '
       'source_disputed and primary_defect; cite short exact source evidence. Then review all three shuffled '
       'outputs with rubric, identifying explicit AND implicit Level2 repair. Unresolved is FAIL, not clean. '
       'Record boolean leak fields null outside their Level. Distinguish compile warnings from errors and '
       'static reasoning from actual execution. Return JSON {reviewer, cases:[{request_id,source_taxonomy, '
       'source_disputed,primary_defect,outputs:[{blind_id,...rubric fields}]}]}. '
       'Keep gold_disagreement="pending" until source-first seal. Do not edit code/prompts or infer arm names.')
    for i in range(0,len(cases),20):
        write_json(d/f'packet-{i//20+1}.private.json',dict(instructions=instructions,rubric=RUBRIC,cases=cases[i:i+20]))
    write_json(d/'packet-seal.json',{p.name:sha(p)for p in d.glob('packet-*.private.json')})
    print(json.dumps(dict(packets=(len(cases)+19)//20,cases=len(cases),directory=str(d))))


def verify_review_binding(out,split):
    """Bind blinded packet bytes and keys to the currently scored source/output."""
    d=out/split/'review';packet_seal=read(d/'packet-seal.json')
    paths=sorted(d.glob('packet-*.private.json'))
    g.require({p.name for p in paths}==set(packet_seal),'review packet inventory changed')
    for p in paths:g.require(sha(p)==packet_seal[p.name],'review packet changed')
    rows=outputs(out,split);expected_key={};expected_cases={}
    for row in rows:
        u=row['unit'];arms=[]
        for arm,value in row['arms'].items():
            blind=digest(['grounded-blind-v1',u['request_id'],arm])[:20]
            expected_key[blind]=dict(request_id=u['request_id'],sample_id=u['sample_id'],arm=arm,output_sha256=digest(value.get('output')))
            arms.append(dict(blind_id=blind,status=value['status'],output=value.get('output')))
        expected_cases[u['request_id']]=dict(request_id=u['request_id'],sample_id=u['sample_id'],target_level=u['level'],task=u['task'],outputs=sorted(arms,key=lambda a:a['blind_id']))
    g.require(read(d/'key.private.json')==expected_key,'review key/current output mismatch')
    actual_cases=[case for p in paths for case in read(p)['cases']]
    g.require(len(actual_cases)==len(expected_cases),'review packet coverage changed')
    g.require({case['request_id']:case for case in actual_cases}==expected_cases,'review packet/current source or output mismatch')


def review_index(out,split):
    verify_review_binding(out,split)
    d=out/split/'review';key=read(d/'key.private.json');reviews={};source_refs={}
    files=sorted(d.glob('source-review-*.private.json'))
    g.require(bool(files),'independent source review files missing')
    units={u['request_id']:u for u in read(out/split/'units.private.json')}
    for path in files:
        value=read(path)
        for case in value['cases']:
            rid=case['request_id'];g.require(rid in units and rid not in source_refs,'review ID duplicate/mismatch')
            g.validate_taxonomy(case['source_taxonomy']);g.require(type(case['source_disputed']) is bool,'source dispute boolean required');source_refs[rid]=case
            for r in case['outputs']:
                b=r['blind_id'];g.require(b in key and key[b]['request_id']==rid and b not in reviews,'blind review ID mismatch')
                g.require(set(RUBRIC)<=set(r),'missing rubric fields')
                for field in ['finding_supported']:
                    g.require(r[field] in ['yes','no','disputed'],'review verdict invalid')
                for field in ['main_error_covered_in_feedback','feedback_false_claim','feedback_taxonomy_consistent','level_compliant','natural_vietnamese']:
                    g.require(r[field] in ['yes','no'],'review boolean verdict required')
                for field in ['taxonomy_missing','taxonomy_extra']:g.validate_taxonomy(r[field])
                for field,level in [('L1_specific_location_or_cause_leak',1),('L2_repair_leak_explicit_or_implicit',2),('L3_actionable_repair_direction',3)]:
                    g.require(type(r[field]) is bool if units[rid]['level']==level else r[field] is None,'review Level flag must be bool at own Level, null otherwise')
                g.require(type(r['generic_feedback']) is bool,'generic feedback boolean required')
                evidence=r['source_evidence_for_verdict'];g.require(isinstance(evidence,list) and bool(evidence),'source evidence required')
                unit=units[rid];code=unit['task']['code'];requirement=unit['task']['statement']+'\n'+'\n'.join(p.get('statement','')for p in unit['task']['problems'])
                output_text=next(o.get('output',{}).get('feedback','') if o.get('output') else '' for c in read(d/f'packet-{list(units).index(rid)//20+1}.private.json')['cases']if c['request_id']==rid for o in c['outputs']if o['blind_id']==b)
                for e in evidence:
                    g.require(isinstance(e,dict) and set(e)=={'source_quote','feedback_quote','reason'},'evidence schema')
                    g.require(bool(e['reason']),'evidence rationale missing')
                    g.require(bool(e['source_quote']) and (e['source_quote'] in code or e['source_quote'] in requirement),'review source quote mismatch')
                    g.require(e['feedback_quote'] in output_text,'review feedback quote mismatch')
                reviews[b]=r
    g.require(set(reviews)==set(key),'incomplete independent review coverage')
    return key,reviews,source_refs,files


def seal_review(out,split):
    key,reviews,sources,files=review_index(out,split)
    d=out/split
    p=d/'review-seal.json';g.require(not p.exists(),'source review already sealed')
    write_json(p,dict(authority='Codex independent agent, not human verified',
         source_first_before_gold=True,outputs=len(reviews),sources=len(sources),
         hashes={str(f.relative_to(out)):sha(f)for f in files},packet_seal_sha256=sha(d/'review/packet-seal.json'),
         key_sha256=sha(d/'review/key.private.json'),units_sha256=sha(d/'units.private.json')))
    print(json.dumps(dict(sealed=split,outputs=len(reviews),sha256=sha(p))))


def gold_map(split):
    if split=='development':return {r['sample_id']:r['annotation_v2']for r in read(PARENT/'train-eligible.private.json')}
    return {r['sample_id']:r['annotation_v2']for r in read(PARENT/'reference.private.json')['records']}


def score(out,split):
    d=out/split;seal=read(d/'review-seal.json')
    g.require(sha(d/'review/packet-seal.json')==seal['packet_seal_sha256'],'review packet seal changed')
    for name,field in [('review/key.private.json','key_sha256'),('units.private.json','units_sha256')]:
        # Older development seals predate these fields; full logical packet binding
        # below still applies. New seals pin both bytes explicitly.
        if field in seal:g.require(sha(d/name)==seal[field],'review key or units changed after seal')
    for name,h in seal['hashes'].items():g.require(sha(out/name)==h,'review changed after source-first seal')
    key,reviews,sources,files=review_index(out,split)
    rows=outputs(out,split);gold=gold_map(split);byarm={};idmetrics=[]
    armreviews={}
    for b,v in reviews.items():armreviews[(key[b]['request_id'],key[b]['arm'])]=v
    for arm in ['C0','C1','C2']:
        refs=[gold[r['unit']['sample_id']]for r in rows];pred=[r['arms'][arm].get('output',{}).get('taxonomy_error') if r['arms'][arm].get('output') else None for r in rows]
        tax=metrics.taxonomy_metrics(refs,pred)
        source_tax=metrics.taxonomy_metrics([sources[r['unit']['request_id']]['source_taxonomy']for r in rows],pred)
        rs=[armreviews[(r['unit']['request_id'],arm)]for r in rows]
        completed=[r['arms'][arm]['status']=='resolved'for r in rows]
        flags=dict(completed=sum(completed),unresolved=len(rows)-sum(completed),reviewed_output_count=sum(completed),
             joint_pass=sum(metrics.joint_pass(v,r['arms'][arm]['status']=='resolved')for r,v in zip(rows,rs)),
             false_claims=sum(v['feedback_false_claim']=='yes'for v in rs),
             main_error_covered=sum(v['main_error_covered_in_feedback']=='yes'for v in rs),
             inconsistent=sum(ok and v['feedback_taxonomy_consistent']=='no'for ok,v in zip(completed,rs)),
             level_noncompliant=sum(ok and v['level_compliant']=='no'for ok,v in zip(completed,rs)),
             L1_leaks=sum(v['L1_specific_location_or_cause_leak'] is True for v in rs),
             L2_repair_leaks=sum(v['L2_repair_leak_explicit_or_implicit'] is True for v in rs),
             L3_actionable=sum(v['L3_actionable_repair_direction'] is True for v in rs),
             natural_vietnamese=sum(v['natural_vietnamese']=='yes'for v in rs),
             generic=sum(v['generic_feedback'] is True for v in rs),
             disputed=sum(v['finding_supported']=='disputed'for v in rs))
        flags['serious_L1_L2_leaks']=flags['L1_leaks']+flags['L2_repair_leaks']
        flags['micro_f1']=tax['micro_f1'];flags['false_clean']=tax['false_clean']
        flags['rare_tp']={label:v['TP']for label,v in tax['per_label'].items()if 0<v['support']<=5}
        byarm[arm]=dict(taxonomy_original=tax,taxonomy_independent_agent=source_tax,feedback=flags,
                        gate_summary=flags)
    for row in rows:
        u=row['unit'];case=sources[u['request_id']]
        disagreement=set(gold[u['sample_id']])!=set(case['source_taxonomy'])
        comparison=dict(verdict='yes' if disagreement else 'no',
             reason='Mechanical comparison AFTER sealed independent source review: original labels '+
                 json.dumps(gold[u['sample_id']],ensure_ascii=False)+'; independent agent labels '+
                 json.dumps(case['source_taxonomy'],ensure_ascii=False)+'. Source rationale: '+case['primary_defect'],
             authority='derived label comparison, not human adjudication; originals unchanged')
        idmetrics.append(dict(request_id=u['request_id'],sample_id=u['sample_id'],level=u['level'],family=u['family'],
             gold_disagreement=disagreement,gold_comparison=comparison,
             source_disputed=case['source_disputed'],
             arms={arm:dict(completed=row['arms'][arm]['status']=='resolved',
                 taxonomy_exact_original=row['arms'][arm].get('output') is not None and set(row['arms'][arm]['output']['taxonomy_error'])==set(gold[u['sample_id']]),
                 joint_pass=metrics.joint_pass(armreviews[(u['request_id'],arm)],row['arms'][arm]['status']=='resolved'),
                 review={**armreviews[(u['request_id'],arm)],'gold_disagreement':comparison})for arm in ['C0','C1','C2']}))
    costs={}
    c0_attempts=[json.loads(s)for s in (d/'C0/attempts.jsonl').read_text().splitlines()if s]
    cand_attempts=[json.loads(s)for s in (d/'candidate/attempts.jsonl').read_text().splitlines()if s]
    groups={'C0':c0_attempts,'shared_diagnosis':[r for r in cand_attempts if '/diagnosis/'in r['key']],
            'C1_renderer':[r for r in cand_attempts if '/C1/'in r['key']],
            'C2_renderer_and_guard':[r for r in cand_attempts if '/C2/'in r['key']]}
    for name,attempts in groups.items():
        costs[name]=dict(calls=len(attempts),input_tokens=sum(a.get('input_tokens') or 0 for a in attempts),
                        output_tokens=sum(a.get('output_tokens') or 0 for a in attempts),latency_s=sum(a['latency_s']for a in attempts))
    cfg=read(d/'freeze.json')['config']
    gates={arm:metrics.winner_gate(byarm['C0']['gate_summary'],byarm[arm]['gate_summary'],cfg['winner_gate'])for arm in ['C1','C2']} if split=='evaluation' else {}
    families={}
    for family in sorted({r['unit']['family']for r in rows}):
        subset=[r for r in rows if r['unit']['family']==family]
        families[family]={arm:metrics.taxonomy_metrics([gold[r['unit']['sample_id']]for r in subset],
            [r['arms'][arm].get('output',{}).get('taxonomy_error') if r['arms'][arm].get('output') else None for r in subset])for arm in ['C0','C1','C2']}
    summary=dict(split=split,source_count=len(rows),arms=byarm,cost=costs,gates=gates,families=families,
           gold_disagreement_sources=sum(r['gold_disagreement']for r in idmetrics),
           independent_agent_reference_not_human_gold=True,real_evaluation_sources=0,
           joint_proxy='exact supported source taxonomy + main error coverage + no false claim + consistency + Level; not official leaderboard score',
           verdict='retain R15; no winner' if not any(gate['passed']for gate in gates.values()) else 'candidate clears numerical gate; historical exposure and final review still apply')
    write_json(d/'metrics.private.json',summary);write_json(d/'id-metrics.private.json',idmetrics)
    print(json.dumps(dict(split=split,verdict=summary['verdict'],arms={a:{'taxonomy':{k:v['taxonomy_original'][k]for k in ['macro_f1','micro_f1','exact_count','false_clean','invalid']},'feedback':v['feedback']}for a,v in byarm.items()},cost=costs),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['packets','seal-review','score'])
    p.add_argument('--split',choices=['development','evaluation'],default='development');p.add_argument('--output',type=Path,default=DEFAULT)
    a=p.parse_args();{'packets':packets,'seal-review':seal_review,'score':score}[a.phase](a.output.resolve(),a.split)
