"""Bounded diagnostic-pair experiment: identities, metrics and dev selection only."""
from collections import Counter,defaultdict
from src.task3.sft_v1_experiment import Journal
from src.task3.prompt_crossover import call_state,AXES
from src.task3.prompt_crossover_analysis import summarize,successful_feedback,semantic_value

ASSESSMENT=('diagnosis_supported','coverage','factual_fidelity')

def conjunction(values):
    if any(v not in ('pass','fail') for v in values):return None
    return all(v=='pass' for v in values)


def diagnosis(r):
    if r['status']!='valid':return None
    truth=conjunction([r['axes'][a] for a in ASSESSMENT+('location_and_condition',)])
    if truth is None:return None
    return bool(r['parsed']['taxonomy_error']) and truth


def useful_repair(r):
    d=diagnosis(r)
    if d is None or r['axes']['l3_repair_direction'] not in ('pass','fail') or r.get('code_verdict')=='uncertain':return None
    return d and r['axes']['l3_repair_direction']=='pass' and r.get('code_verdict','absent') in ('pass','absent')


def pair_success(clean,faulty):
    if clean['status']!='valid' or faulty['status']!='valid':return None
    for r in [clean,faulty]:
        if r.get('correct_status','pass') in ('uncertain','not_evaluable'):return None
        if r.get('correct_status','pass')=='fail':return False
    c=conjunction([clean['axes'][a] for a in ASSESSMENT]);d=diagnosis(faulty)
    if c is None or d is None:return None
    return not clean['parsed']['taxonomy_error'] and c and d


class EvaluationJournal(Journal):
    def __init__(self,path,cells):
        super().__init__(path);self.cells={k:set(v) for k,v in cells.items()}
        if sum(map(len,self.cells.values()))>504 or any(len(ids)>72 for ids in self.cells.values()):raise ValueError('evaluation ceiling')
        reserved=set();done=set()
        for e in self.events():
            if e.get('type') not in ('generation_reserved','generation_completed'):continue
            self.parts(e['key'])
            if e['type']=='generation_reserved':
                if e['key'] in reserved:raise ValueError('duplicate reservation')
                reserved.add(e['key'])
            else:
                if e['key'] not in reserved or e['key'] in done:raise ValueError('corrupt completion')
                done.add(e['key'])
    def parts(self,key):
        p=key.split('/')
        if len(p)!=3 or '/'.join(p[:2]) not in self.cells or p[2] not in self.cells['/'.join(p[:2])]:raise ValueError('foreign cell/target')
    def reserve(self,key,budget=None):
        self.parts(key)
        if key in self.reserved():raise ValueError('never replay reserved call')
        if len(self.reserved())>=sum(map(len,self.cells.values())):raise ValueError('frozen call budget')
        self.append(dict(type='generation_reserved',key=key))


SELECTION_POLICY=dict(eligibility='clean alarms, invalids and disclosure failures no greater than matched V3 dev',
    ranking=['pair_success desc','repair desc','diagnosis desc','clean_false_alarms asc','step asc'],
    fallback='If no candidate eligible, same ranking, explicitly not eligible for promotion; finish test.',test='only after selection seal')


def choose_checkpoint(candidates,v3):
    if {c['step'] for c in candidates}!={48,96}:raise ValueError('two fixed checkpoints required')
    failures={str(c['step']):[k for k in ['clean_false_alarms','invalid','disclosure_failures'] if c[k]>v3[k]] for c in candidates}
    eligible=[c for c in candidates if not failures[str(c['step'])]]
    key=lambda c:(-c['pair_success'],-c['repair'],-c['diagnosis'],c['clean_false_alarms'],c['step'])
    chosen=min(eligible or candidates,key=key)
    unresolved=chosen.get('disclosure_unknown',0)>0 or v3.get('disclosure_unknown',0)>0
    return dict(step=chosen['step'],fallback=not bool(eligible),eligibility_counts_satisfied=bool(eligible),unresolved_disclosure=unresolved,eligible_for_promotion=bool(eligible) and not unresolved,eligible_steps=[c['step'] for c in eligible],
        eligibility_failures=failures,ranking=SELECTION_POLICY,candidates=candidates,v3_reference=v3)


def feedback_success(row):
    return row.get('correct_status','pass')=='pass' and successful_feedback(row)


def summary_with_status(rows):
    rows=list(rows);m=summarize(rows)
    clean=[r for r in rows if not r['faulty']];faulty=[r for r in rows if r['faulty']]
    m.update(successful_feedback=sum(feedback_success(r) for r in rows),clean_successful=sum(feedback_success(r) for r in clean),faulty_successful=sum(feedback_success(r) for r in faulty))
    m.update(joint_successful=m['successful_feedback'],clean_joint=m['clean_successful'],faulty_joint=m['faulty_successful'])
    m['balanced_success']=((m['clean_successful']/len(clean)+m['faulty_successful']/len(faulty))/2) if clean and faulty else m['successful_feedback']/len(rows) if rows else None
    m['balanced_joint']=m['balanced_success']
    return m


def metrics(rows):
    rows=list(rows);m=summary_with_status(rows);by=defaultdict(list)
    for r in rows:by[(r['family_id'],r['level'])].append(r)
    pairs=[]
    for (fam,l),rr in sorted(by.items()):
        if len(rr)!=2 or {r['faulty'] for r in rr}!={False,True}:raise ValueError('require exact clean/faulty pair')
        c=next(r for r in rr if not r['faulty']);f=next(r for r in rr if r['faulty'])
        status_both=None if any(r['status']!='valid' for r in rr) else not c['parsed']['taxonomy_error'] and bool(f['parsed']['taxonomy_error'])
        taxonomy_status=bool(status_both) if status_both is not None else None
        if status_both is not None:
            if any(r.get('correct_status') in ('uncertain','not_evaluable') for r in rr):status_both=None
            elif any(r.get('correct_status')=='fail' for r in rr):status_both=False
        pairs.append(dict(family_id=fam,level=l,status_both_correct=bool(status_both) if status_both is not None else None,taxonomy_status_both_correct=taxonomy_status,
            diagnostic_pair_success=pair_success(c,f) if l>1 else 'not_applicable',both_joint_successful=all(feedback_success(r) for r in rr)))
    f23=[r for r in rows if r['faulty'] and r['level']>1];f3=[r for r in rows if r['faulty'] and r['level']==3]
    eligible_pairs=[p for p in pairs if p['level']>1]
    m['diagnostic_pairs']=dict(count=sum(p['diagnostic_pair_success'] is True for p in eligible_pairs),denominator=len(eligible_pairs),unknown=sum(p['diagnostic_pair_success'] is None for p in eligible_pairs),
        by_level={str(l):dict(count=sum(p['diagnostic_pair_success'] is True for p in pairs if p['level']==l),denominator=sum(p['level']==l for p in pairs)) for l in [2,3]},details=pairs)
    m['supported_diagnosis']=dict(count=sum(diagnosis(r) is True for r in f23),denominator=len(f23),unknown=sum(diagnosis(r) is None for r in f23))
    m['useful_l3_repair']=dict(count=sum(useful_repair(r) is True for r in f3),denominator=len(f3),unknown=sum(useful_repair(r) is None for r in f3))
    groups=defaultdict(list)
    for r in rows:groups[r['sample_id']].append(r)
    consistency={sid:(None if any(r['status']!='valid' for r in rr) else len({tuple(sorted(r['parsed']['taxonomy_error'])) for r in rr})==1) for sid,rr in groups.items()}
    m['taxonomy_cross_level']=dict(consistent=sum(v is True for v in consistency.values()),inconsistent=sum(v is False for v in consistency.values()),unknown=sum(v is None for v in consistency.values()),sources=len(groups),per_source=consistency)
    m['contradictions']=sum(r.get('taxonomy_feedback_contradiction') is True for r in rows)
    m['disclosure_unknown']=sum(r['status']=='valid' and r['axes']['disclosure_compliance'] in ('uncertain','not_evaluable') for r in rows)
    m['disclosure_failures']=sum(r['status']=='valid' and r['axes']['disclosure_compliance']=='fail' for r in rows)
    m['by_level']={str(l):summary_with_status([r for r in rows if r['level']==l]) for l in [1,2,3]}
    m['status_assessment']={v:sum(r.get('correct_status')==v for r in rows) for v in ['pass','fail','uncertain','not_evaluable']}
    m['unsupported_additional_claims']={str(v):sum(type(r.get('unsupported_claims')) is type(v) and r.get('unsupported_claims')==v for r in rows) for v in [True,False,'uncertain','not_evaluable']}
    m['selection_counts']=dict(pair_success=m['diagnostic_pairs']['count'],repair=m['useful_l3_repair']['count'],diagnosis=m['supported_diagnosis']['count'],
        clean_false_alarms=m['clean_false_alarms'],invalid=m['invalid'],disclosure_failures=m['disclosure_failures'],disclosure_unknown=m['disclosure_unknown'])
    return m
