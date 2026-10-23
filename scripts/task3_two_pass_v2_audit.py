#!/usr/bin/env python3
"""Private boundary reconstruction and offline evaluation; never generates text."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.task3 import two_pass as v1
from src.task3.dataset import write_json
from src.task3.level_blind import read, sha, digest
from src.task3.grounded_metrics import taxonomy_metrics

OLD = ROOT / 'outputs/task3/two-pass-20261023'
OUT = ROOT / 'outputs/task3/two-pass-v2-20261023'
GOOD=['finding_supported','main_covered','consistent','level_ok','natural','direct_em']
BAD=['false_claim','meta','clean_false_error','generic_only','disputed']
SPECIAL=['l1_detail_leak','l2_repair_leak','l3_actionable']


def require(condition,message):
    if not condition:raise ValueError(message)


def combine(output,reviews,refs):
    r={k:all(x[k] for x in reviews) for k in GOOD}
    r.update({k:any(x[k] for x in reviews) for k in BAD})
    for k in SPECIAL:
        values=[x[k]for x in reviews if x[k] is not None]
        r[k]=(all(values) if k=='l3_actionable' else any(values)) if values else None
        r[k+'_confirmed']=all(values) if len(values)==2 else False
    r['clean_false_error_confirmed']=len(reviews)==2 and all(x['clean_false_error'] for x in reviews)
    r['source_disputed']=any(x['source_disputed']for x in refs) or any(set(x['source_taxonomy'])!=set(refs[0]['source_taxonomy'])for x in refs)
    r['taxonomy_exact_source']=bool(output is not None and all(set(output['taxonomy_error'])==set(x['source_taxonomy'])for x in refs))
    level_contradiction=r['l1_detail_leak'] is True or r['l2_repair_leak'] is True or r['l3_actionable'] is False
    r['feedback_pass']=bool(output is not None and not level_contradiction and all(r[k]for k in GOOD) and not any(r[k]for k in BAD))
    r['content_level_pass_without_role']=bool(output is not None and not level_contradiction and all(r[k]for k in GOOD if k!='direct_em') and not any(r[k]for k in BAD if k!='meta'))
    r['strict_joint']=r['taxonomy_exact_source'] and not r['source_disputed'] and r['feedback_pass']
    r['reviewer_disagreements']=[k for k in GOOD+BAD+SPECIAL if len({x[k]for x in reviews})>1]
    return r


def e_checks(arms):
    b,c,d=arms['B'],arms['C'],arms['D']
    bt,dt=b['taxonomy_original'],d['taxonomy_original']
    return {'C_no_meta':c['meta']==0,'C_no_confirmed_clean_false_error':c['clean_false_error_confirmed']==0,
            'C_no_unresolved_clean_false_error_disagreement':c['clean_false_error']==0,
            'C_direct_em_for_all_completed':c['completed']>=15 and c['direct_em']==c['completed'],
            'D_micro_improves':dt['micro_f1']>bt['micro_f1'], 'D_macro10_improves':dt['macro_f1']>bt['macro_f1'],
            'D_new_TP_outside_compile_logic':any(dt['per_label'][k]['TP']>bt['per_label'][k]['TP']for k in dt['per_label'] if k not in ['Lỗi biên dịch','Lỗi logic'])}


def validate_level_fields(row,level,source_has_error):
    for name,applicable in [('l1_detail_leak',level==1),('l2_repair_leak',level==2),('l3_actionable',level==3 and source_has_error)]:
        require(type(row[name]) is bool if applicable else row[name] is None,'Level applicability: '+name)


def load_arms(names):
    units=read(OUT/'units.private.json'); ids={u['sample_id']for u in units};arms={}
    for arm in names:
        if arm=='A': rows=[{**r,'status':'resolved'}for r in read(OUT/'control.private.json')]
        elif arm=='B': rows=read(OLD/'B/results.private.json')
        else: rows=read(OUT/arm/'results.private.json')
        require(len(rows)==len(ids) and {r['sample_id']for r in rows}==ids,'arm full-ID coverage')
        arms[arm]={r['sample_id']:{'status':r['status'],'output':r.get('output')}for r in rows}
    return units,arms


def bind(units,arms,key,packet):
    by={u['sample_id']:u for u in units};seen=set()
    require(len(packet['cases'])==len(units),'packet ID denominator')
    for c in packet['cases']:
        u=by[c['sample_id']]
        require(c['task']==u['task'] and c['level']==u['level'],'review source/Level mismatch')
        for o in c['outputs']:
            k=key[o['output_id']];pair=(k['sample_id'],k['arm'])
            require(pair not in seen and k['sample_id']==c['sample_id'],'duplicate/mismatched arm key')
            seen.add(pair)
            require(arms[k['arm']][k['sample_id']]=={k:o[k]for k in ['status','output']},'whole reviewed output differs')
    require(seen=={(sid,a)for sid in by for a in arms} and len(key)==len(seen),'exact blinded arm/ID coverage')


def packets(phase):
    from scripts.task3_two_pass_v2 import verify
    verify();names=['A','B','C','D'] if phase=='CD' else ['E']
    units,arms=load_arms(names);r=OUT/'review';key={};cases=[];rng=random.Random(2026102303)
    require(not (r/f'packet-seal-{phase}.json').exists(),'exclusive blinded packet')
    for u in units:
        sid=u['sample_id'];outputs=[];order=list(names);rng.shuffle(order)
        for arm in order:
            oid=digest([sid,arm,'v2-blind-v1'])[:20];key[oid]={'sample_id':sid,'arm':arm}
            outputs.append({'output_id':oid,**arms[arm][sid]})
        cases.append({'sample_id':sid,'level':u['level'],'task':u['task'],'outputs':outputs})
    policy={'instructions':'Use your sealed source assessment first. Score anonymous outputs independently; never read key, gold, generation notes, raw attempts, old reports or another reviewer. Unresolved output has no feedback to credit. No execution or model generation.',
      'official_levels':read(OUT/'frozen/level-definitions.json'),
      'rubric':{'finding_supported':'ALL substantive feedback claims supported by source; uncertainty recorded separately',
        'main_covered':'main defect assessed; clean warrants bounded praise; L1 warranted general warning counts',
        'false_claim':'any false/unfounded assertion about code/execution/input/diagnosis',
        'consistent':'feedback agrees with final taxonomy, including empty list',
        'level_ok':'L1 no position/cause/repair; L2 position+cause but no replacement or implicit repair; L3 feasible source-correct repair, no full solution. Clean code warrants praise at L2/3 too.',
        'direct_em':'natural direct assistant-to-student speech using em, NOT simply regex contains em',
        'meta':'comments on teacher/grader/model/feedback/rubric or assessment process, rather than directly reviewing submitted code',
        'clean_false_error':'asserts an unsupported error/optimization on code you judged clean within stated scope; explain any source-domain dispute',
        'l1_detail_leak':'bool at L1 only, else null; variable/function/expression/location/cause disclosure',
        'l2_repair_leak':'bool at L2 only, else null; explicit or implicit repair. Describing current erroneous operand alone is not automatically a repair.',
        'l3_actionable':'bool for erroneous-source L3 only, else null; actual feasible correction direction',
        'natural':'natural comprehensible Vietnamese, not mechanistic or awkward repetition',
        'generic_only':'no useful source-grounded assessment; a permitted L1 light hint is not automatically generic. Lone forbidden check-program placeholder is generic.',
        'disputed':'retain ambiguity, do not force credit',
        'evidence':'exact source_quote in code/statement/grading_policy and feedback_quote in this output, with reason'},
      'schema':{'reviewer':'A or B','cases':[{'sample_id':'...','outputs':[{'output_id':'...',**{k:False for k in GOOD+BAD},**{k:None for k in SPECIAL},'reason':'...','evidence':[{'source_quote':'...','feedback_quote':'...','reason':'...'}]}]}]},'cases':cases}
    write_json(r/f'packet-{phase}.private.json',policy);write_json(r/f'key-{phase}.private.json',key)
    inputs=[r/f'packet-{phase}.private.json',r/f'key-{phase}.private.json',r/'source-seal.json',r/'source-a.private.json',r/'source-b.private.json']
    for a in names: inputs.append(OUT/'control.private.json' if a=='A' else OLD/'B/results.private.json' if a=='B' else OUT/a/'results.private.json')
    write_json(r/f'packet-seal-{phase}.json',{str(p.relative_to(ROOT)):sha(p)for p in inputs})
    print(json.dumps({'phase':phase,'cases':len(cases),'outputs':len(cases)*len(names)}))


def verify_packet(phase):
    from scripts.task3_two_pass_v2 import verify
    verify();r=OUT/'review'
    for n,h in read(r/f'packet-seal-{phase}.json').items():require(sha(ROOT/n)==h,n)
    for n,h in read(r/'source-seal.json')['hashes'].items():require(sha(r/n)==h,n)
    units,arms=load_arms(['A','B','C','D'] if phase=='CD' else ['E'])
    key=read(r/f'key-{phase}.private.json');packet=read(r/f'packet-{phase}.private.json');bind(units,arms,key,packet)
    return units,arms,key,packet


def seal(phase):
    units,arms,key,packet=verify_packet(phase);r=OUT/'review'
    for who in ['a','b']:
        source_by={c['sample_id']:c for c in read(r/f'source-{who}.private.json')['cases']}
        path=r/f'paired-{phase}-{who}.private.json';reviews=read(path)['cases'];by={c['sample_id']:c for c in reviews}
        require(len(by)==len(reviews)==len(units),'review ID count')
        for c in packet['cases']:
            rr=by[c['sample_id']]['outputs'];rows={o['output_id']:o for o in rr}
            require(len(rows)==len(rr)==len(c['outputs']) and set(rows)=={o['output_id']for o in c['outputs']},'review output IDs')
            source='\n'.join(str(c['task'].get(k,''))for k in ['code','statement','grading_policy'])
            for o in c['outputs']:
                row=rows[o['output_id']]
                for k in GOOD+BAD:require(type(row[k]) is bool,'boolean rubric '+k)
                for k in SPECIAL:require(row[k] is None or type(row[k]) is bool,'nullable bool '+k)
                validate_level_fields(row,c['level'],bool(source_by[c['sample_id']]['source_taxonomy']))
                if o['output'] is None:
                    require(not any(row[k]for k in GOOD),'no feedback credit for unresolved')
                for e in row['evidence']:
                    require(e['source_quote'] in source,'source evidence exact')
                    require(o['output'] is not None and e['feedback_quote'] in o['output']['feedback'],'feedback evidence exact')
    target=r/f'paired-seal-{phase}.json';require(not target.exists(),'exclusive paired seal')
    names=[f'paired-{phase}-{w}.private.json'for w in ['a','b']]+[f'packet-seal-{phase}.json']
    write_json(target,{n:sha(r/n)for n in names});print(json.dumps({'sealed':phase,'sha256':sha(target)}))


def score():
    r=OUT/'review';names=['A','B','C','D'];phases=['CD']
    if (r/'paired-seal-E.json').exists():names+=['E'];phases+=['E']
    units,arms=load_arms(names);reviews={}
    for phase in phases:
        verify_packet(phase)
        for n,h in read(r/f'paired-seal-{phase}.json').items():require(sha(r/n)==h,n)
        key=read(r/f'key-{phase}.private.json')
        for who in ['a','b']:
            for c in read(r/f'paired-{phase}-{who}.private.json')['cases']:
                for o in c['outputs']:
                    k=key[o['output_id']];reviews[(k['sample_id'],k['arm'],who)]=o
    source={w:{c['sample_id']:c for c in read(r/f'source-{w}.private.json')['cases']}for w in ['a','b']}
    ids={u['sample_id']for u in units};require(all(set(s)==ids for s in source.values()),'source coverage')
    # Original gold opened only after source and blinded output seals.
    parent=ROOT/'outputs/task3/eval-freeze-v2-20261021/frozen'
    dev={x['sample_id']:x['annotation_v2']for x in read(parent/'train-eligible.private.json')}
    ev={x['sample_id']:x['annotation_v2']for x in read(parent/'reference.private.json')['records']}
    selection=read(OUT/'selection.private.json')
    gold={x['sample_id']:(dev if x['old_split']=='development' else ev)[x['sample_id']]for x in selection['IDs']}
    summary={'IDs':len(units),'exposure':'same prior-exposed16 synthetic development; not new evaluation','arms':{},'per_ID':[]}
    for u in units:
        sid=u['sample_id'];row={'sample_id':sid,'level':u['level'],'original_gold':gold[sid],
            'source_A':source['a'][sid]['source_taxonomy'],'source_B':source['b'][sid]['source_taxonomy'],
            'source_disputed':any(source[w][sid]['source_disputed']for w in ['a','b']) or set(source['a'][sid]['source_taxonomy'])!=set(source['b'][sid]['source_taxonomy']),
            'arms':{}}
        for arm in names:
            result=arms[arm][sid];rr=[reviews[(sid,arm,w)]for w in ['a','b']]
            a=combine(result['output'],rr,[source[w][sid]for w in ['a','b']])
            a.update(status=result['status'],taxonomy=result['output']['taxonomy_error'] if result['output'] else None,
                     taxonomy_exact_original=bool(result['output'] is not None and set(result['output']['taxonomy_error'])==set(gold[sid])))
            row['arms'][arm]=a
        if 'E' not in names:row['arms']['E']={'status':'not_run'}
        summary['per_ID'].append(row)
    for arm in names:
        rows=[x['arms'][arm]for x in summary['per_ID']];tax=[x['taxonomy']for x in rows]
        counts={k:sum(x[k] is True for x in rows)for k in GOOD+BAD+SPECIAL+['strict_joint','feedback_pass','content_level_pass_without_role','clean_false_error_confirmed','l2_repair_leak_confirmed']}
        levels={}
        for level in [1,2,3]:
            subset=[x['arms'][arm]for x in summary['per_ID']if x['level']==level]
            levels[str(level)]={'n':len(subset),**{k:sum(x[k] is True for x in subset)for k in GOOD+BAD+SPECIAL+['strict_joint','feedback_pass']},
                                'actionable_eligible':sum(x['l3_actionable'] is not None for x in subset)}
        summary['arms'][arm]={'status':'run','completed':sum(x['status']=='resolved'for x in rows),'unresolved':sum(x['status']!='resolved'for x in rows),'fallback':0,
            'taxonomy_original':taxonomy_metrics([gold[u['sample_id']]for u in units],tax),
            'taxonomy_source_A_sensitivity':taxonomy_metrics([source['a'][u['sample_id']]['source_taxonomy']for u in units],tax),
            **counts,'per_level':levels,'strict_joint_rate':counts['strict_joint']/len(units),
            'original_clean_n':sum(not gold[u['sample_id']]for u in units),
            'original_clean_false_error':sum(x['arms'][arm]['clean_false_error']for x in summary['per_ID']if not x['original_gold'])}
        if arm=='A':cost_rows=read(OUT/'control-runtime.private.json')
        elif arm=='B':cost_rows=[json.loads(x)for x in (OLD/'B/attempts.jsonl').read_text().splitlines()]
        else:
            path=OUT/arm/'attempts.jsonl';cost_rows=[json.loads(x)for x in path.read_text().splitlines()] if path.exists() else []
        summary['arms'][arm]['cost']={'calls':len(cost_rows),'fresh_calls':0 if arm in ['A','B'] else len(cost_rows),
            **{k:sum(x.get(k) or 0 for x in cost_rows)for k in ['input_tokens','output_tokens','latency_s']},
            'reused_stage1_calls':16 if arm=='C' else 0}
        if arm in ['C','D','E']:
            results=read(OUT/arm/'results.private.json')
            summary['arms'][arm]['inconsistency']=sum(x['inconsistency']for x in results)
            for row in results:
                if row['output'] is not None:require(row['output']['taxonomy_error']==row['stage1']['taxonomy_error'],'immutable taxonomy')
            reservations=OUT/arm/'reservations.jsonl';reserved=[json.loads(x)for x in reservations.read_text().splitlines()] if reservations.exists() else []
            require(all(sum(x['sample_id']==sid for x in reserved)<=(1 if arm=='C' else 2)for sid in ids),'call cap')
            order=[]
            for u in units:
                sid=u['sample_id'];order.extend((sid,s)for s in ['taxonomy','feedback']if any(x['sample_id']==sid and x['stage']==s for x in reserved))
            require([(x['sample_id'],x['stage'])for x in reserved]==order,'serial one-ID stage order')
    checks=e_checks(summary['arms']);allow=all(checks.values())
    gate={'allow_E':allow,'checks':checks,'freeze_sha256':sha(OUT/'frozen/freeze.json'),
          'review_sha256':{str(p.relative_to(OUT)):sha(p)for p in [r/'packet-seal-CD.json',r/'paired-seal-CD.json',r/'paired-CD-a.private.json',r/'paired-CD-b.private.json']}}
    target=OUT/'E-gate.private.json'
    if target.exists():require(read(target)==gate,'offline E gate drift')
    else:write_json(target,gate)
    summary['E_gate']=gate
    if 'E' not in names:summary['arms']['E']={'status':'not_run','planned_IDs':16,'taxonomy_original':None,'reason':'C/D eligibility gate failed' if not allow else 'eligible; not yet run'}
    summary['provenance']={'initial_HEAD':read(OUT/'initial.private.json')['HEAD'],'freeze_sha256':sha(OUT/'frozen/freeze.json'),
      'trace_sha256':sha(OUT/'boundary-trace.private.json'),'source_seal_sha256':sha(r/'source-seal.json'),
      'paired_seals':{phase:sha(r/f'paired-seal-{phase}.json')for phase in phases},
      'original_gold_unchanged':True,'no_public_inference':True,'selection':selection}
    summary['decision']='retain_R15_E_not_run' if not allow and 'E' not in names else 'E_requires_joint_review_selection' if 'E' in names else 'eligible_for_E_only'
    write_json(ROOT/'reports/task3/TASK3_TWO_PASS_V2_METRICS_20261023.json',summary)
    print(json.dumps({'arms':{a:{k:v for k,v in data.items() if k not in ['taxonomy_original','taxonomy_source_A_sensitivity','per_level']}for a,data in summary['arms'].items()},'E_gate':checks,'decision':summary['decision']},ensure_ascii=False))


def trace():
    """Reconstruct actual rendered input with the pinned tokenizer, no model load."""
    from src.task3.inference import load_tokenizer, tokenizer_metadata
    from scripts.task3_two_pass import verify
    frozen = verify()
    os.environ.update(HF_HOME=str(ROOT/'outputs/task3/hf-cache'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    tokenizer = load_tokenizer(frozen['config'])
    assert tokenizer_metadata(tokenizer) == frozen['tokenizer']
    units = read(OLD/'units.private.json')
    results = {r['sample_id']: r for r in read(OLD/'B/results.private.json')}
    final = {r['sample_id']: r['output'] for r in read(OLD/'B/predictions.json')}
    rows = [json.loads(x) for x in (OLD/'B/attempts.jsonl').read_text().splitlines()]
    journal = {(r['sample_id'], r['stage']): r for r in rows}
    assert len(rows) == len(journal) == 2*len(units)
    definitions = read(OLD/'frozen/level-definitions.json')
    phrase = 'Giảng viên đã phân tích'
    traces = []
    (OUT/'rendered-v1').mkdir(exist_ok=True)
    for u in units:
        sid = u['sample_id']; first = journal[(sid, 'taxonomy')]; second = journal[(sid, 'feedback')]
        parsed = v1.parse_taxonomy(first['raw_text'])
        assert first['messages'] == v1.messages_taxonomy(u)
        assert parsed == results[sid]['stage1']
        assert second['messages'] == v1.messages_feedback(u, parsed, definitions)
        feedback = v1.parse_feedback(second['raw_text'])
        assert results[sid]['output'] == final[sid] == {'taxonomy_error': parsed['taxonomy_error'], 'feedback': feedback}
        row = {'sample_id': sid, 'requested_level': u['level'], 'source_sha256': digest(u['task']),
               'phrase_in_source': phrase in json.dumps(u['task'], ensure_ascii=False),
               'stage1_parsed': parsed, 'stage2_feedback_equals_final': True, 'boundaries': []}
        for stage, attempt in [('taxonomy', first), ('feedback', second)]:
            messages = attempt['messages']
            assert [m['role'] for m in messages] == ['system', 'user']
            assert digest(messages) == attempt['prompt_sha256']
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            without = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            assert rendered == without + '<|im_start|>assistant\n'
            tokens = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
            assert len(tokens) == attempt['input_tokens']
            path = OUT/'rendered-v1'/f'{sid}.{stage}.txt'; path.write_text(rendered)
            payload = json.loads(messages[1]['content'])
            allowed = set(v1.task_payload(u)) | ({'predicted', 'requested_level', 'level_rule', 'level_guidance'} if stage == 'feedback' else set())
            assert set(payload) == allowed
            row['boundaries'].append({'stage': stage, 'rendered_sha256': sha(path), 'messages_sha256': digest(messages),
               'raw_response_sha256': hashlib.sha256(attempt['raw_text'].encode()).hexdigest(),
               'phrase_in_rendered_input': phrase in rendered, 'phrase_in_raw_response': phrase in attempt['raw_text'],
               'roles': ['system', 'user'], 'assistant_generation_prefix': True, 'input_tokens_match': True,
               'input_equals_source_allowlist_plus_own_prediction_and_Level': True})
        traces.append(row)
    write_json(OUT/'boundary-trace.private.json', {'old_freeze_sha256': sha(OLD/'frozen/freeze.json'),
        'old_attempts_sha256': sha(OLD/'B/attempts.jsonl'), 'tokenizer': tokenizer_metadata(tokenizer), 'cases': traces,
        'backend_behavior': 'HFBackend applies system/user template with add_generation_prompt=True; decodes generated suffix only; parse_feedback returns JSON string unchanged',
        'conclusion': 'Meta phrase first occurs in DIGITSUM-0001 stage2 raw response. No observed injected teacher/gold/reviewer/cross-sample text. V1 speaker/recipient and clean L2/L3 behavior are underspecified. This is stage2 generation/role-grounding failure, not demonstrated data leakage.'})
    print(json.dumps({'traced_IDs': len(traces), 'model_calls': 0, 'trace_sha256': sha(OUT/'boundary-trace.private.json'),
        'DIGITSUM_0001': next(r for r in traces if r['sample_id']=='SYN-DIGITSUM-0001')}, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('phase', choices=['trace','packets-CD','packets-E','seal-CD','seal-E','score']); args = p.parse_args()
    if args.phase=='trace':trace()
    elif args.phase.startswith('packets-'):packets(args.phase.split('-')[1])
    elif args.phase.startswith('seal-'):seal(args.phase.split('-')[1])
    else:score()
