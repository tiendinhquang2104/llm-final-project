"""Official-contract v3 policy; independent diagnostic and disclosure axes."""
from collections import Counter
import math
from src.task3.sft_v1_experiment import Journal

AXES = ('diagnosis_supported','coverage','factual_fidelity','location_and_condition',
        'level_compliance','l3_repair_direction','l4_usefulness','vietnamese_compliance')
SELECTION_POLICY = {
    'version':'sft-v3-official-contract-diagnostic-preservation-v1',
    'reference':'existing v2 step240 evaluated with the identical new v3 prompt',
    'eligibility':['invalid <= v2','clean_false_alarms <= v2',
                   'faulty_misses_with_invalid <= v2','supported_faulty_diagnosis >= v2',
                   'faulty_l3_correct >= v2'],
    'eligible_order':['level_compliant desc','balanced_joint desc','oracle_joint desc','mean_loss asc','step asc'],
    'fallback_order':['balanced_joint desc','supported_faulty_diagnosis desc','level_compliant desc','step asc'],
    'no_eligible':'select diagnostic candidate, fail promotion conditions, continue observed-final evaluation',
    'level_goal':'95% descriptive, overall and per-Level, never sole promotion criterion',
}
REVIEW_POLICY = {
    'version':'official-level-v3-agent-source-grounded-v1',
    'reviewer':'source-grounded agent review; not independent human gold',
    'axes':list(AXES),
    'L1':'status or praise only; no defect location, specific cause or repair code',
    'L2':'location and precise cause; no specific repair instructions/code; no sentence limit',
    'L3':'diagnosis plus correct useful repair direction; no complete solution; localized actionable hints allowed',
    'L4':'correct useful assessment/explanation; full code permitted, absence alone never fails',
    'wrong_hint':'record repair correctness failure separately from disclosure; do not automatically fail disclosure',
    'clean':'truthful clean status needs no fictitious defect, location or repair',
    'faulty_praise':'not useful task completion even if disclosure compliant',
    'code':'any supplied code must be correct; bounded compile/runtime evidence where feasible; unresolved is non-pass',
    'fidelity':'no invented conditions/defects; essential triggering conditions preserved; examples verified',
    'style':'length monotonicity and sentence counts are descriptive only, never official metrics',
    'verdicts':['pass','fail','uncertain','not_applicable'],
}


class BudgetJournal(Journal):
    """1120 single-attempt primary calls, two separate smoke reservations."""
    def reserve(self,key,budget=None):
        reserved=self.reserved()
        if key in reserved:raise ValueError('generation already reserved: '+key)
        smoke=sum(k.startswith('smoke-') for k in reserved)
        if key.startswith('smoke-'):
            if smoke>=2:raise ValueError('smoke ceiling exhausted')
        elif len(reserved)-smoke>=1120:raise ValueError('primary ceiling exhausted')
        self.append(dict(type='generation_reserved',key=key))


def validate_exposures(forwards,ids,epochs):
    ids=list(ids)
    if len(set(ids))!=len(ids) or Counter(forwards)!=Counter({eid:epochs for eid in ids}):
        raise ValueError('each training target must appear exactly once per completed epoch')
    return True


def joint_success(status,level,faulty,axes,code_verdict):
    if status!='valid':return False
    if any(axes.get(k)!='pass' for k in ('diagnosis_supported','coverage','factual_fidelity','level_compliance','vietnamese_compliance')):return False
    if level>1 and faulty and axes.get('location_and_condition')!='pass':return False
    if level==3 and faulty and axes.get('l3_repair_direction')!='pass':return False
    if level==4 and axes.get('l4_usefulness')!='pass':return False
    if code_verdict not in ('pass','absent'):return False
    return True


def summarize(rows):
    clean=[r for r in rows if not r['faulty']];faulty=[r for r in rows if r['faulty']]
    def valid(r):return r['status']=='valid'
    def labels(r):return r['parsed']['taxonomy_error'] if valid(r) else []
    def assessment(r):
        return valid(r) and all(r['axes'].get(k)=='pass' for k in ('diagnosis_supported','coverage','factual_fidelity'))
    def joint(r):return joint_success(r['status'],r['level'],r['faulty'],r['axes'],r.get('code_verdict','absent'))
    l3=[r for r in faulty if r['level']==3]
    result=dict(targets=len(rows),sources=len({r['sample_id'] for r in rows}),clean_targets=len(clean),faulty_targets=len(faulty),
        invalid=sum(not valid(r) for r in rows),clean_invalids=sum(not valid(r) for r in clean),
        faulty_invalids=sum(not valid(r) for r in faulty),
        clean_false_alarms=sum(valid(r) and bool(labels(r)) for r in clean),
        faulty_misses=sum(valid(r) and not labels(r) for r in faulty),
        supported_faulty_diagnosis=sum(assessment(r) and bool(labels(r)) for r in faulty),
        faulty_l3_targets=len(l3),faulty_l3_correct=sum(assessment(r) and r['axes'].get('l3_repair_direction')=='pass' for r in l3),
        level_compliant=sum(valid(r) and r['axes'].get('level_compliance')=='pass' for r in rows),
        joint_successful=sum(joint(r) for r in rows),clean_joint=sum(joint(r) for r in clean),faulty_joint=sum(joint(r) for r in faulty))
    result['faulty_misses_with_invalid']=result['faulty_misses']+result['faulty_invalids']
    for key,den in [('clean_false_alarm_rate',len(clean)),('faulty_missed_defect_rate',len(faulty)),
                    ('supported_faulty_diagnosis_rate',len(faulty)),('faulty_l3_repair_rate',len(l3)),('official_level_compliance_rate',len(rows))]:
        numerator={'clean_false_alarm_rate':'clean_false_alarms','faulty_missed_defect_rate':'faulty_misses',
                   'supported_faulty_diagnosis_rate':'supported_faulty_diagnosis','faulty_l3_repair_rate':'faulty_l3_correct',
                   'official_level_compliance_rate':'level_compliant'}[key]
        result[key]=result[numerator]/den if den else None
    result['balanced_joint']=((result['clean_joint']/len(clean)+result['faulty_joint']/len(faulty))/2
                              if clean and faulty else result['joint_successful']/len(rows) if rows else 0.)
    result['axes']={k:{v:sum(r['axes'].get(k)==v for r in rows) for v in ('pass','fail','uncertain','not_applicable')} for k in AXES}
    return result


def select_checkpoint(candidates,v2):
    if len(candidates)!=2 or len({c['step'] for c in candidates})!=2:raise ValueError('two epoch candidates required')
    failures={};eligible=[]
    for c in candidates:
        if not all(math.isfinite(c[k]) for k in ('mean_loss','balanced_joint','oracle_joint')):raise ValueError('nonfinite selection value')
        wrong=[]
        for k in ('invalid','clean_false_alarms','faulty_misses_with_invalid'):
            if c[k]>v2[k]:wrong.append(k)
        for k in ('supported_faulty_diagnosis','faulty_l3_correct'):
            if c[k]<v2[k]:wrong.append(k)
        failures[str(c['step'])]=wrong
        if not wrong:eligible.append(c)
    key=(lambda c:(-c['level_compliant'],-c['balanced_joint'],-c['oracle_joint'],c['mean_loss'],c['step'])) if eligible else (
        lambda c:(-c['balanced_joint'],-c['supported_faulty_diagnosis'],-c['level_compliant'],c['step']))
    chosen=min(eligible or candidates,key=key)
    return dict(step=chosen['step'],passes_preliminary_conditions=bool(eligible),eligible_steps=[c['step'] for c in eligible],
                eligibility_failures=failures,candidates=candidates,v2_reference=v2,policy=SELECTION_POLICY)


def compatibility_config(config):
    """Use the unchanged recipe validator for every setting except epoch count."""
    from copy import deepcopy
    value=deepcopy(config)
    value['training']['epochs']=1
    value['training']['sampling']='one_seeded_shuffle_of_train_rows_without_replacement'
    return value


def main_training_arguments(config,directory,rows):
    from src.task3.sft_v1_experiment import training_arguments
    if rows<=0 or rows%4 or config['training']['epochs']!=2 or config['training']['sampling']!='seeded_epoch_shuffle_without_replacement':
        raise ValueError('v3 requires complete four-Level sources and exactly two seeded epochs')
    values=training_arguments(compatibility_config(config),directory,smoke=False)
    values.update(num_train_epochs=2,save_steps=rows//4,skip_memory_metrics=True)
    return values


ORACLE_WRAPPER = ('Oracle-assisted rendering probe v1 (evaluation only). The following findings were reviewed and frozen before model generation. '
                  'Treat the reviewed faulty/clean status, locations and conditions as evidence; express an appropriate Vietnamese response at the requested Level. '
                  'Do not disclose findings forbidden by that Level. These are findings, not a prewritten answer:\n')
ORACLE_KEYS = ('faulty','taxonomy','diagnosis','location','mechanism','essential_conditions','repair_direction','clean_invariant')


def oracle_prompt(prompt,packet):
    from copy import deepcopy
    import json
    if any(k in packet for k in ('targets','revised_targets','completion','feedback','solution_code')):
        raise ValueError('oracle findings must not contain a prewritten answer or complete repair code')
    if type(packet.get('faulty')) is not bool:raise ValueError('explicit reviewed clean/faulty status required')
    result=deepcopy(prompt)
    result[1]['content']+='\n\n'+ORACLE_WRAPPER+json.dumps({k:packet[k] for k in ORACLE_KEYS if k in packet},ensure_ascii=False)
    return result

CODE_POLICY = {
    'version':'v3-supplied-code-bounded-v1',
    'extraction':'Reuse exact historical extract_cpp; when no backticks, exact extract_unfenced. Never repair code. Multiple/partial blocks receive semantic review and unresolved code is non-pass.',
    'absence':'L4 code absence alone is permitted; assess usefulness and correctness of supplied explanation separately.',
    'scope':'all valid targets with supplied complete code, including a disclosed complete solution below L4',
    'execution':'existing CppSandbox with unchanged harness/checker/test cases; all jails under this run; no unbounded shell execution',
    'limits':'unchanged CppSandbox chroot uid/cap drop seccomp and CPU/wall/memory/process/output limits',
    'ceiling_compile_calls':1120,'ceiling_runtime_calls':25000,'retries':0,
    'reuse':'only byte-identical code and harness with identical test suite/checker and fully recorded provenance',
    'interpretation':'finite test success is bounded evidence, agent checks prose and source semantics separately; supplied wrong code fails joint success',
}
