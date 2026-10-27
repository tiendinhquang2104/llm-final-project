"""Offline control comparison; semantics supplied only by explicit agent reviews."""
import argparse
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from scripts.task3_base_pv3_control import load, verify, matched_population, ControlJournal, PREVIOUS, DEFAULT_OUT
from src.task3.sft_v1 import read_jsonl, sha256
from src.task3.sft_v1_experiment import write_json
from src.task3.fresh_eval import summarize_system
from src.task3.prompt_crossover import AXES
from src.task3.prompt_crossover_analysis import paired_analysis, successful_feedback, semantic_value
from scripts.task3_fresh_eval_report import render_casebook, pre, table, ratio


def supported(r):
    if r['status']!='valid':return None
    needed=['diagnosis_supported','coverage','factual_fidelity','location_and_condition']
    if any(r['axes'][a] in ('uncertain','not_evaluable') for a in needed):return None
    return bool(r['parsed']['taxonomy_error']) and all(r['axes'][a]=='pass' for a in needed)


def repair(r):
    if r['status']!='valid':return None
    diagnosis=supported(r)
    if diagnosis is None or r['axes']['l3_repair_direction'] in ('uncertain','not_evaluable') or r['code_verdict']=='uncertain':return None
    return diagnosis and r['axes']['l3_repair_direction']=='pass' and r['code_verdict'] in ('absent','pass')


def metrics_for(rows):
    m=summarize_system(rows)
    faulty=[r for r in rows if r['faulty']]; clean=[r for r in rows if not r['faulty']]
    f23=[r for r in faulty if r['level']>1];f3=[r for r in faulty if r['level']==3]
    # Add strict source/location/content gates explicitly; preserve inherited summaries unchanged.
    m['control_primary']=dict(supported_diagnosis=dict(count=sum(supported(r) is True for r in f23),denominator=40),
        correct_useful_repair=dict(count=sum(repair(r) is True for r in f3),denominator=20),
        valid_nonempty_incorrect_faulty_l23=dict(count=sum(r['status']=='valid' and bool(r['parsed']['taxonomy_error']) and supported(r) is False for r in f23),denominator=40),
        valid_nonempty_incorrect_faulty_all_levels=dict(count=sum(r['status']=='valid' and bool(r['parsed']['taxonomy_error']) and (supported(r) is False if r['level']>1 else not all(r['axes'][a]=='pass' for a in ['diagnosis_supported','coverage','factual_fidelity'])) for r in faulty),denominator=60),
        nonempty_faulty=dict(count=sum(r['status']=='valid' and bool(r['parsed']['taxonomy_error']) for r in faulty),denominator=60),
        nonempty_clean=dict(count=sum(r['status']=='valid' and bool(r['parsed']['taxonomy_error']) for r in clean),denominator=60),
        supported_diagnosis_by_level={str(l):dict(count=sum(supported(r) is True for r in f23 if r['level']==l),denominator=20) for l in [2,3]},
        unknown_repair=sum(repair(r) is None for r in f3),
        unknown_diagnosis=sum(supported(r) is None or any(r['axes'][a]=='uncertain' for a in ['diagnosis_supported','coverage','factual_fidelity','location_and_condition']) for r in f23))
    pairs={}
    for level in (1,2,3):
        groups=defaultdict(list)
        for r in rows:
            if r['level']==level:groups[r['family_id']].append(r)
        details={}
        for fam,rr in sorted(groups.items()):
            c=next(r for r in rr if not r['faulty']);f=next(r for r in rr if r['faulty'])
            known=all(r['status']=='valid' for r in rr)
            distinguished=known and not c['parsed']['taxonomy_error'] and bool(f['parsed']['taxonomy_error'])
            assessments=[semantic_value(r,'assessment') for r in rr]
            assessment=None if None in assessments else all(assessments)
            actual=supported(f) if level>1 else 'not_evaluable_at_L1'
            details[fam]=dict(taxonomy_status_distinguished=bool(distinguished),semantic_assessment_both_correct=assessment,
                actual_defect_identified=(supported(f) if level>1 else 'not_evaluable_at_L1'),
                distinguished_and_actual_defect=(None if actual is None else bool(distinguished and actual)) if level>1 else 'not_evaluable_at_L1',
                both_joint_successful=(None if any(semantic_value(r,'successful_feedback') is None for r in rr) else all(successful_feedback(r) for r in rr)),unknown=not known or assessment is None or actual is None)
        pairs[str(level)]=dict(denominator=20,taxonomy_status_distinguished=sum(d['taxonomy_status_distinguished'] for d in details.values()),
            semantic_assessment_both_correct=sum(d['semantic_assessment_both_correct'] is True for d in details.values()),
            distinguished_and_actual_defect=sum(d['distinguished_and_actual_defect'] is True for d in details.values()) if level>1 else None,
            both_joint_successful=sum(d['both_joint_successful'] is True for d in details.values()),unknown=sum(d['unknown'] for d in details.values()),families=details)
    m['paired_families']=pairs
    return m


def transition(a,b,fn):
    groups=defaultdict(list)
    for eid in sorted(a):
        x,y=fn(a[eid]),fn(b[eid])
        name='unknown' if x is None or y is None else 'both_correct' if x and y else 'base_only' if x else 'v3_only' if y else 'both_miss'
        groups[name].append(eid)
    return {k:dict(count=len(groups[k]),targets=groups[k]) for k in ['base_only','v3_only','both_miss','both_correct','unknown']}


def build(out):
    m=verify(out);examples=load(out/'prompts.private.json');base=read_jsonl(out/'base-generations.jsonl');v3=read_jsonl(out/'v3-generations.reused.jsonl')
    br=read_jsonl(out/'base-reviews.private.jsonl');vr=read_jsonl(out/'v3-reviews.reused.private.jsonl')
    for rows in [base,v3,br,vr]:matched_population(examples,rows)
    for gen,revs in [(base,br),(v3,vr)]:
        by={r['example_id']:r for r in gen}
        for r in revs:
            g=by[r['example_id']]
            if any(r.get(k)!=v for k,v in g.items()):raise ValueError('review/generation binding changed')
            if set(r['axes'])!=set(AXES) or any(v not in ['pass','fail','uncertain','not_applicable','not_evaluable'] for v in r['axes'].values()):raise ValueError('unfinished review')
    historical_reviews={r['example_id']:r for r in read_jsonl(PREVIOUS/'reviews.private.jsonl') if r['system_id']=='V3-v3' and r['level']<=3}
    if any(r!=historical_reviews[r['example_id']] for r in vr):raise ValueError('V3 verdict modified')
    b={r['example_id']:r for r in br};v={r['example_id']:r for r in vr}
    metric={'base':metrics_for(br),'V3':metrics_for(vr)}
    write_json(out/'metrics.json',metric)
    diag_ids=[eid for eid,r in b.items() if r['faulty'] and r['level']>1]
    l3_ids=[eid for eid in diag_ids if b[eid]['level']==3]
    pair=paired_analysis(br,vr)
    pair['diagnostic_transitions']=transition({k:b[k] for k in diag_ids},{k:v[k] for k in diag_ids},supported)
    pair['l3_repair_transitions']=transition({k:b[k] for k in l3_ids},{k:v[k] for k in l3_ids},repair)
    clean_ids=[eid for eid in b if not b[eid]['faulty']]
    def alarm(r):return bool(r['parsed']['taxonomy_error']) if r['status']=='valid' else None
    pair['clean_alarm_transitions']=transition({k:b[k] for k in clean_ids},{k:v[k] for k in clean_ids},alarm)
    pair['clean_alarm_transition_interpretation']='base_only=alarm removed by V3; v3_only=alarm introduced; both_correct=both alarm; both_miss=neither alarm; unknown kept separate.'
    pair['faulty_nonempty_to_empty']=[eid for eid in b if b[eid]['faulty'] and b[eid]['status']=='valid' and v[eid]['status']=='valid' and b[eid]['parsed']['taxonomy_error'] and not v[eid]['parsed']['taxonomy_error']]
    write_json(out/'paired-comparison.json',pair)
    ordering=lambda eid:(hashlib.sha256(f"{b[eid]['family_id']}/{b[eid]['sample_id']}/L{b[eid]['level']}".encode()).hexdigest(),eid)
    categories=[('base_better',[eid for eid in diag_ids if supported(b[eid]) is True and supported(v[eid]) is False]),
        ('V3_better',[eid for eid in b if semantic_value(b[eid],'successful_feedback') is False and semantic_value(v[eid],'successful_feedback') is True]),
        ('both_miss',[eid for eid in diag_ids if supported(b[eid]) is False and supported(v[eid]) is False]),
        ('clean_behavior',clean_ids),('L3_repair',[eid for eid in l3_ids if repair(b[eid]) is True or repair(v[eid]) is True]),
        ('contradiction_or_invalid',[eid for eid in b if any(r['status']!='valid' or r.get('taxonomy_feedback_contradiction') is True for r in [b[eid],v[eid]])])]
    selected=[];used=set();families=set()
    for name,candidates in categories:
        ranked=sorted(candidates,key=lambda eid:(eid in used,b[eid]['family_id'] in families,ordering(eid)))
        eid=next((x for x in ranked if x not in used),None)
        selected.append(dict(category=name,example_id=eid,absent_reason=None if eid else 'Không có ví dụ riêng thỏa điều kiện trong dữ liệu.'))
        if eid:used.add(eid);families.add(b[eid]['family_id'])
    write_json(out/'example-selection.json',dict(rule=load(out/'review-rubric.json')['example_rule'],examples=selected))
    costs=load(out/'base-runtime.json');costs=dict(base=costs,V3_reused=dict(outputs=120,new_model_calls=0,original_input_tokens=sum(r['input_tokens'] for r in v3),original_output_tokens=sum(r['output_tokens'] for r in v3),original_generation_wall_s=sum(r['wall_s'] for r in v3),vram='historical peak measured over all160 V3 targets, not a 120-target isolated peak; see original complete.json',original_all160_peak=load(PREVIOUS/'generations/V3-v3/complete.json')),
        model_generation_calls_this_experiment=120,new_compile_calls=0,new_runtime_test_calls=0,scope='Base inference measured; V3 original cost contextual only. Agent review token usage and monetary bill not instrumented.')
    if (out/'additional-tests.private.json').exists():costs['additional_claim_tests']=load(out/'additional-tests.private.json')
    write_json(out/'costs-and-runtime.json',costs)
    sources={r['sample_id']:r for r in read_jsonl(out/'dataset.private.jsonl')};gold={r['sample_id']:r for r in read_jsonl(out/'gold.private.jsonl')}
    full={sid:load(PREVIOUS/g['witness_evidence_path']) for sid,g in gold.items()}
    witnesses={sid:next(t for t in full[sid]['tests'] if t['input']==g['witness_input']) for sid,g in gold.items()}
    validation={r['sample_id']:r for r in load(PREVIOUS/'evidence/source-validation.private.json')}
    targets={r['sample_id']:r for r in load(out/'targets.private.json')}
    # Reuse full source/evidence/raw/parsed renderer, with names hidden initially.
    pop=dict(systems=['X','Y'],targets=targets,sources=sources,gold=gold,gold_witness=witnesses,source_validation=validation,full_evidence=full,
        by_system={'X':b,'Y':v},generations={'X':{r['example_id']:r for r in base},'Y':{r['example_id']:r for r in v3}},
        code_evidence={(s,eid):dict(status=rr['code_verdict'],reason=rr['evidence'],unsupported_additional_claims=rr.get('unsupported_additional_claims','see unsupported-claims.private.json for secondary V3 coding'),scope='agent source review; original V3 code evidence preserved in prior run') for s,rrs in [('X',br),('Y',vr)] for rr in rrs for eid in [rr['example_id']]})
    book=render_casebook(pop).replace('toàn bộ 160 targets','toàn bộ 120 targets').replace('<option>4</option>','')
    book=book.replace('Task3 — fresh evaluation toàn bộ cặp','Task3 — matched base–V3 control').replace('Fresh evaluation —','Matched base–V3 control —')
    book=book.replace('Mới được tác giả agent soạn và đánh giá;', 'Bộ authored đã quan sát; 120 base mới, 120 V3 tái dùng; review của agent;')
    book=book.replace('<h1>', '<details><summary>Hiện tên hệ thống</summary>X = pinned prepared base, adapter disabled; Y = V3 checkpoint-480. Thứ tự cố định; đây không phải review mù độc lập.</details><h1>',1)
    (out/'paired-casebook.html').write_text(book)
    ex=['# Sáu ví dụ chọn theo quy tắc cố định','', 'Agent review trên bộ đã quan sát; V3 giữ nguyên verdict lịch sử. Chi tiết đầy đủ cũng nằm trong paired-casebook.html.','']
    for choice in selected:
        ex+=['## '+choice['category'],'']
        eid=choice['example_id']
        if eid is None:ex+=[choice['absent_reason'],''];continue
        sid=b[eid]['sample_id'];s=sources[sid]
        ex += [f"{eid} — {b[eid]['family_id']} — L{b[eid]['level']}",'','Đặc tả:','',s['statement'],'','```cpp',s['code'],'```','','Gold/bằng chứng:','','```json',json.dumps(dict(gold=gold[sid],witness=witnesses[sid]),ensure_ascii=False,indent=2),'```','']
        for label,row in [('Base',b[eid]),('V3',v[eid])]:
            ex += [label+' raw:','','````text',row['raw'],'````','','Parsed/verdict/lý do:','','````json',json.dumps({k:row[k] for k in ['parsed','axes','taxonomy_feedback_contradiction','evidence']},ensure_ascii=False,indent=2),'````','']
    (out/'EXAMPLES.vi.md').write_text('\n'.join(ex))
    write_json(out/'report-data.json',dict(examples=selected,metrics=metric,transitions=pair['diagnostic_transitions']))
    print(json.dumps(dict(status='comparison_complete',base=metric['base']['control_primary'],V3=metric['V3']['control_primary'],transitions=pair['diagnostic_transitions']),ensure_ascii=False))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,default=DEFAULT_OUT);args=a.parse_args();build(args.out.resolve())
