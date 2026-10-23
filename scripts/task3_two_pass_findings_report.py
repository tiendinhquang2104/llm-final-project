#!/usr/bin/env python3
"""Offline blinded review packets and bound metrics; no inference or text editing."""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.dataset import write_json
from src.task3.level_blind import read, sha, digest
from src.task3.grounded_metrics import taxonomy_metrics

ARMS=['A','C-old','C','renderer-ablation']
GOOD=['factual','main_covered','level_ok','natural_role']
BAD=['false_claim','addresses_ban','self_reference','meta','placeholder_only','disputed']
SPECIAL=['l1_detail_leak','l2_repair_leak','l3_actionable']


def require(condition,message):
    if not condition:raise ValueError(message)


def assess(output,gold,source_taxonomies,reviews):
    values={k:all(r[k]for r in reviews)for k in GOOD}
    values.update({k:any(r[k]for r in reviews)for k in BAD})
    for k in SPECIAL:
        observed=[r[k]for r in reviews if r[k]is not None]
        values[k]=(all(observed)if k=='l3_actionable'else any(observed))if observed else None
    passes=bool(output is not None and reviews and all(values[k]for k in GOOD)and not any(values[k]for k in BAD)
                and values['l1_detail_leak']is not True and values['l2_repair_leak']is not True and values['l3_actionable']is not False)
    values.update(feedback_pass=passes,joint_gold=passes and set(output['taxonomy_error'])==set(gold),
                  joint_source=passes and all(set(output['taxonomy_error'])==set(s)for s in source_taxonomies))
    return values


def packets(out):
    from scripts import task3_two_pass_findings as cli
    cli.OUT=out;cli.verify()
    review=out/'review';require(not(review/'packet-seal.json').exists(),'one blinded packet only')
    units=read(out/'units.private.json');rng=random.Random(cli.verify()['config']['review_seed']);key={};cases=[]
    arms={a:cli.index_results(units,read(out/a/'results.private.json'))for a in ARMS}
    for u in units:
        order=ARMS.copy();rng.shuffle(order);outputs=[]
        for a in order:
            oid=f'{rng.getrandbits(96):024x}';key[oid]={'sample_id':u['sample_id'],'arm':a}
            row=arms[a][u['sample_id']]
            outputs.append({'output_id':oid,'status':row['status'],'output':row['output']})
        cases.append({'sample_id':u['sample_id'],'level':u['level'],'task':u['task'],'outputs':outputs})
    policy={
      'instructions':'Review against your sealed source assessment, using full source and requested Level. Names of arms are hidden, seeded order shuffled. Do not read key/gold/raw/other reviewer. Unresolved has no credit. No code execution or inference.',
      'official_levels':read(out/'label-space.private.json')['feedback_level'],
      'rubric':{
        'factual':'Every substantive feedback claim supported by source/evidence; inherited wrong claims still fail.',
        'main_covered':'Main source defect addressed. L1 warranted general warning counts; clean bounded praise counts. Do not demand every label in a short paragraph.',
        'level_ok':'Apply ONLY requested official Level: L1 no location/cause/testcase/repair even indirect; L2 location+cause with no replacement/repair action/changed bound; L3 source-correct feasible repair, not placeholder. Clean L2/L3 need no invented repair. L4 no1–3 sentence limit.',
        'natural_role':'Natural direct feedback to student; em when needed, technical sentences without pronouns valid. No bạn or self xưng mình/thầy/tôi; no meta. Do not require em token.',
        'false_claim':'False/unfounded claim, unsupported praise, invented code, execution/file/test success without evidence, contradiction.',
        'addresses_ban':'Calls student bạn, excluding quote/code token.',
        'self_reference':'Self xưng mình/thầy/tôi, not variable/token or quote.',
        'meta':'Comments on grader/teacher/model/feedback quality instead of submitted code.',
        'placeholder_only':'Only generic check-program filler; a natural warranted L1 light hint is not automatically placeholder.',
        'disputed':'Material uncertainty; explain, conservative no joint credit.',
        'l1_detail_leak':'boolean only at L1, otherwise null; includes location/name/cause/testcase/repair, even indirectly.',
        'l2_repair_leak':'boolean only at L2, otherwise null; token replacement, missing symbol instruction, changed bound/expression even no code. Current wrong token description alone can be diagnosis.',
        'l3_actionable':'boolean for L3 source with established defect, else null; must fix supported defect usefully.',
        'evidence':'source_quote exact substring from code/statement/policy; feedback_quote exact substring; reason explains finding.'},
      'schema':{'reviewer':'A or B','cases':[{'sample_id':'ID','outputs':[{'output_id':'opaque',**{k:False for k in GOOD+BAD},**{k:None for k in SPECIAL},'reason':'short explanation','evidence':[]}]}]},
      'cases':cases}
    write_json(review/'packet.private.json',policy);write_json(review/'key.private.json',key)
    inputs=['review/packet.private.json','review/key.private.json','review/source-seal.json','selection-seal.json','units.private.json','gold.private.json']+[a+'/results.private.json'for a in ARMS]
    accounting_paths=[a+'/'+name for a in ARMS for name in ['attempts.jsonl','reservations.jsonl','traces.json']] + ['run.private.json','runtime-before.private.json']
    write_json(review/'accounting-inputs.private.json',{p:{'exists':(out/p).exists(),'sha256':sha(out/p)if(out/p).exists()else None}for p in accounting_paths})
    inputs+=['review/accounting-inputs.private.json']+[p for p in accounting_paths if(out/p).exists()]
    cli.seal_files(out,'review/packet-seal.json',inputs)
    print(json.dumps({'IDs':len(units),'blinded_outputs':len(units)*len(ARMS),'packet_sha256':sha(review/'packet.private.json')}))


def unique_cases(rows, allowed_ids):
    by = {r['sample_id']: r for r in rows}
    require(len(rows) == len(by) and set(by) <= allowed_ids, 'duplicate or unknown source review ID')
    return by


def validate_attribution(case, reference_count, completed):
    indices = case['detected_reference_indices']
    require(isinstance(indices, list) and all(type(i) is int and 0 <= i < reference_count for i in indices)
            and len(indices) == len(set(indices)), 'unique valid reference finding indices required')
    for key in ['main_detected', 'stage2_faithful']:
        require(type(case[key]) is bool, 'attribution bool required: ' + key)
    for key in ['inherited_false_claims', 'new_false_claims']:
        require(type(case[key]) is int and case[key] >= 0, 'nonnegative integer claim count required')
    if not completed:
        require(not case['stage2_faithful'] and case['inherited_false_claims'] == case['new_false_claims'] == 0,
                'unresolved stage2 cannot receive faithfulness or claim credit')


def validate_reviews(out):
    from scripts import task3_two_pass_findings as cli
    cli.OUT=out;cli.verify();cli.verify_seal(out,'review/packet-seal.json')
    for p,meta in read(out/'review/accounting-inputs.private.json').items():
        require((out/p).exists()==meta['exists']and(not meta['exists']or sha(out/p)==meta['sha256']),'accounting source drift: '+p)
    units=read(out/'units.private.json');packet=read(out/'review/packet.private.json');key=read(out/'review/key.private.json')
    arms={a:cli.index_results(units,read(out/a/'results.private.json'))for a in ARMS}
    seen=set()
    for case in packet['cases']:
        u=next(u for u in units if u['sample_id']==case['sample_id'])
        require(case['task']==u['task']and case['level']==u['level'],'packet source drift')
        for o in case['outputs']:
            k=key[o['output_id']];require(k['sample_id']==case['sample_id'],'key ID drift')
            r=arms[k['arm']][k['sample_id']];require(o['status']==r['status']and o['output']==r['output'],'reviewed output drift')
            pair=(k['sample_id'],k['arm']);require(pair not in seen,'duplicate reviewed output');seen.add(pair)
    require(seen=={(u['sample_id'],a)for u in units for a in ARMS}and len(key)==len(seen),'blinded denominator drift')
    reviews={};sources={}
    for who in ['a','b']:
        source=read(out/f'review/source-{who}.private.json')['cases'];sources[who]=unique_cases(source,{u['sample_id']for u in units})
        rows=read(out/f'review/paired-{who}.private.json')['cases'];by={r['sample_id']:r for r in rows}
        require(len(rows)==len(by)and set(by)==set(sources[who]),'review/source ID coverage')
        if who=='a':require(set(by)=={u['sample_id']for u in units},'primary full denominator')
        for case in packet['cases']:
            sid=case['sample_id']
            if sid not in by:continue
            outputs=by[sid]['outputs'];idx={r['output_id']:r for r in outputs}
            require(len(outputs)==len(idx)==len(ARMS)and set(idx)=={r['output_id']for r in case['outputs']},'review arm denominator')
            source_text='\n'.join(str(case['task'][k])for k in ['code','statement','grading_policy'])
            for o in case['outputs']:
                row=idx[o['output_id']]
                for k in GOOD+BAD:require(type(row[k])is bool,'rubric bool '+k)
                for k in SPECIAL:require(row[k]is None or type(row[k])is bool,'special bool/null '+k)
                require((row['l1_detail_leak']is not None)==(case['level']==1),'L1 applicability')
                require((row['l2_repair_leak']is not None)==(case['level']==2),'L2 applicability')
                if case['level']!=3:require(row['l3_actionable']is None,'L3 applicability')
                if o['output']is None:require(not any(row[k]for k in GOOD),'unresolved receives credit')
                for e in row['evidence']:
                    require(o['output']is not None and e['source_quote']in source_text and e['feedback_quote']in o['output']['feedback'],'review evidence quote mismatch')
                reviews[(sid,key[o['output_id']]['arm'],who)]=row
    return units,arms,key,reviews,sources


def score(out):
    from scripts import task3_two_pass_findings as cli
    units,arms,key,reviews,sources=validate_reviews(out)
    review=out/'review'
    if not (review/'paired-seal.json').exists():
        cli.seal_files(review,'paired-seal.json',['paired-a.private.json','paired-b.private.json','packet-seal.json'])
    cli.verify_seal(review,'paired-seal.json')
    gold={r['sample_id']:r['taxonomy_error']for r in read(out/'gold.private.json')}
    attrs=read(review/'attribution-a.private.json')['cases'];attribution={r['sample_id']:r for r in attrs}
    require(len(attrs)==len(attribution)==len(units)and set(attribution)==set(gold),'attribution full denominator')
    if not(review/'attribution-seal.json').exists():
        cli.seal_files(review,'attribution-seal.json',['attribution-a.private.json','paired-seal.json','source-seal.json'])
    cli.verify_seal(review,'attribution-seal.json')
    rows=[]
    for u in units:
        sid=u['sample_id'];available=[w for w in sources if sid in sources[w]]
        refs=[sources[w][sid]['source_taxonomy']for w in available]
        item={'sample_id':sid,'family':u['family'],'level':u['level'],'source_sha256':u['provenance']['code_sha256'],
              'gold':gold[sid],'source_taxonomies':refs,'source_disputed':any(sources[w][sid]['source_disputed']for w in available)or any(set(r)!=set(refs[0])for r in refs),
              'reference_findings':sources['a'][sid]['findings'],'attribution':attribution[sid],'arms':{}}
        for a in ARMS:
            output=arms[a][sid]['output'];rs=[reviews[(sid,a,w)]for w in available]
            values=assess(output,gold[sid],refs,rs)
            if item['source_disputed']:values['joint_source']=False
            pred=output['taxonomy_error']if output else None
            values.update(status=arms[a][sid]['status'],taxonomy=pred,
                          TP=len(set(gold[sid])&set(pred or [])),FP=len(set(pred or [])-set(gold[sid])),FN=len(set(gold[sid])-set(pred or [])),
                          reviewer_disagreements=[k for k in GOOD+BAD+SPECIAL if len({r[k]for r in rs})>1])
            item['arms'][a]=values
        rows.append(item)
    summary={'samples':len(units),'unique_source_hashes':len({u['provenance']['code_sha256']for u in units}),
             'review':'Independent Codex source-first A30+B12; no human validation. Conservative combination; gold retained.',
             'zero_division':0,'unresolved_policy':'None as empty for TP/FP/FN only; exact/joint fail even gold empty; no fake output',
             'arms':{},'new_stage1':{},'provenance':{'freeze_sha256':sha(out/'frozen/freeze.json'),'selection_seal_sha256':sha(out/'selection-seal.json'),
             'packet_seal_sha256':sha(review/'packet-seal.json'),'paired_seal_sha256':sha(review/'paired-seal.json'),'attribution_seal_sha256':sha(review/'attribution-seal.json')}}
    for a in ARMS:
        rr=[r['arms'][a]for r in rows];results=read(out/a/'results.private.json')
        tax=taxonomy_metrics([gold[u['sample_id']]for u in units],[arms[a][u['sample_id']]['output']['taxonomy_error']if arms[a][u['sample_id']]['output']else None for u in units])
        path=out/a/'attempts.jsonl';trace=[json.loads(s)for s in path.read_text().splitlines()]if path.exists()else[]
        reservation_path=out/a/'reservations.jsonl'
        reservations=[json.loads(s)for s in reservation_path.read_text().splitlines()]if reservation_path.exists()else[]
        cost={'reservations':len(reservations)if reservation_path.exists()else None,'reserved_without_response':len({r['key']for r in reservations}-{r['key']for r in trace})if reservation_path.exists()else None,'fresh_calls':len(trace),'replayed_stage1':len(units)if a=='renderer-ablation'else 0,
              **{k:sum(t.get(k)or 0 for t in trace)for k in ['input_tokens','output_tokens','latency_s']},
              'by_stage':{stage:{'calls':sum(t.get('stage','one_pass')==stage for t in trace),**{k:sum(t.get(k)or 0 for t in trace if t.get('stage','one_pass')==stage)for k in ['input_tokens','output_tokens','latency_s']}}for stage in ['one_pass','taxonomy','feedback']}}
        fallback=sum(t.get('fallback_used',False)for t in read(out/a/'traces.json'))if a=='A'else 0
        summary['arms'][a]={'completed':sum(r['status']=='resolved'for r in rr),'unresolved':sum(r['status']!='resolved'for r in rr),'fallback':fallback,
            'taxonomy':tax,**{k:sum(r[k]is True for r in rr)for k in GOOD+BAD+SPECIAL+['feedback_pass','joint_gold','joint_source']},
            'per_level':{str(i):{'n':sum(u['level']==i for u in units),**{k:sum(r['arms'][a][k]is True for r in rows if r['level']==i)for k in GOOD+BAD+SPECIAL+['feedback_pass','joint_gold','joint_source']}}for i in [1,2,3]},'cost':cost}
    findings=[]
    for u in units:
        sid=u['sample_id'];stage=arms['C'][sid].get('stage1');observed=stage['findings']if stage else []
        aa=attribution[sid]
        validate_attribution(aa,len(sources['a'][sid]['findings']),arms['C'][sid]['output']is not None)
        require(len(aa['findings'])==len(observed),'per-finding attribution coverage')
        require([f['index']for f in aa['findings']]==list(range(len(observed))),'finding index binding')
        for f in aa['findings']:
            require(f['verdict']in ['correct','false','insufficient'],'finding verdict')
            require(all(type(f[k])is bool for k in ['location_ok','cause_ok','label_correct']),'finding flags')
        findings+=aa['findings']
    summary['new_stage1']={'taxonomy':taxonomy_metrics([gold[u['sample_id']]for u in units],[(arms['C'][u['sample_id']].get('stage1')or{}).get('taxonomy_error')for u in units]),'predicted_findings':len(findings),'correct':sum(f['verdict']=='correct'for f in findings),
       'false':sum(f['verdict']=='false'for f in findings),'insufficient':sum(f['verdict']=='insufficient'for f in findings),
       'correct_finding_wrong_label':sum(f['verdict']=='correct'and not f['label_correct']for f in findings),
       'location_correct':sum(f['location_ok']for f in findings),'cause_correct':sum(f['cause_ok']for f in findings),
       'completed_with_exactly_two_generates':sum(r['status']=='resolved'and all(r.get('steps',{}).get(s,{}).get('parse_status')=='passed'for s in ['taxonomy','feedback'])for r in arms['C'].values()),
       'reference_findings':sum(len(sources['a'][u['sample_id']]['findings'])for u in units),
       'detected_reference_findings':sum(len(attribution[u['sample_id']]['detected_reference_indices'])for u in units),
       'missed_reference_findings':sum(len(sources['a'][u['sample_id']]['findings'])-len(attribution[u['sample_id']]['detected_reference_indices'])for u in units),
       'main_detected_IDs':sum(attribution[u['sample_id']]['main_detected']for u in units),
       'false_positive_source_clean_IDs':sum(bool((arms['C'][u['sample_id']].get('stage1')or{}).get('findings',[]))and not sources['a'][u['sample_id']]['findings']for u in units),
       'faithful_stage2_IDs':sum(attribution[u['sample_id']]['stage2_faithful']for u in units),
       'inherited_false_claim_IDs':sum(attribution[u['sample_id']]['inherited_false_claims']>0 for u in units),
       'new_false_claim_IDs':sum(attribution[u['sample_id']]['new_false_claims']>0 for u in units),
       'inherited_false_claims':sum(attribution[u['sample_id']]['inherited_false_claims']for u in units),
       'new_false_claims':sum(attribution[u['sample_id']]['new_false_claims']for u in units)}
    # Full raw text/source remains only private. Committed JSON contains counts and hashes.
    write_json(out/'per-ID.private.json',rows);write_json(out/'metrics.private.json',summary)
    write_json(ROOT/'reports/task3/TASK3_TWO_PASS_FINDINGS_V1_METRICS_20261023.json',summary)
    print(json.dumps(summary,ensure_ascii=False))
