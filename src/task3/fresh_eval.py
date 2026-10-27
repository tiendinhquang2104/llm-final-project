"""Small fresh-evaluation boundaries; native scientific pipelines are reused."""
from copy import deepcopy
import hashlib
import json
from collections import defaultdict
from src.task3.sft_v1_experiment import Journal
from src.task3.prompt_crossover import AXES, REVIEW_POLICY, call_state
from src.task3.prompt_crossover_analysis import summarize, successful_feedback,semantic_value

SYSTEMS=('A','V2-old','V3-v3')
SOURCE_KEYS={'sample_id','family_id','statement','code','language','exam_type','checker'}
POLICY=deepcopy(REVIEW_POLICY)
POLICY.update(version='fresh-paired-family-evaluation-v1',
    primary='L1–L3 joint; faulty L2–L3 supported diagnosis; faultyL3 correct useful repair; clean alarms/invalids on L1–L3',
    secondary='L4 separately; never contributes to screening',
    statistical_unit='20 family/pairs,40 programs; Levels of one program are repeated views, not independent programs',
    decision=dict(strict_joint_improvement=True,diagnosis_l23_no_worse=True,repair_l3_no_worse=True,
        clean_alarms_primary_no_worse=True,invalid_primary_no_worse=True,
        systematic_contradiction='at least2 distinct families with confirmed primary contradictions blocks screening',
        new_level_failure='any new confirmed disclosure or required-content failure versus a valid passing comparator on the same primary target blocks screening',
        uncertainty='valid disputed semantic/code reviews block recommendation; invalids remain known structural failures in full denominators',
        A_unavailable='finish V2/V3, mark A unavailable rather than substitute',
        failure='retain A submission baseline; at most3 observed failure mechanisms and later-training proposals; do not train or run public inference'),
    example_rule='Fixed hash-order by family/source/Level; prefer unused families; clean/faulty and improvements/regressions, at least2 distinct faultyL3 directions, contradiction/invalid if present; publish every case. No favorable-system selection.')


class EvaluationJournal(Journal):
    def __init__(self,path,system_budgets,target_ids):
        super().__init__(path)
        self.budgets=dict(system_budgets);self.ids=set(target_ids)
        if (not self.ids or len(self.ids)>160 or len(self.ids)!=len(target_ids)
                or any(not isinstance(e,str) or '/' in e for e in self.ids)
                or not self.budgets or any(s not in SYSTEMS or n!=(3 if s=='A' else 1) for s,n in self.budgets.items())):
            raise ValueError('invalid fixed evaluation budget')
        seen=set();completed=set()
        for event in self.events():
            if event.get('type') not in ('generation_reserved','generation_completed'):continue
            self._parts(event.get('key',''));key=event['key']
            if event['type']=='generation_reserved':
                if key in seen:raise ValueError('duplicate reservation')
                seen.add(key)
            else:
                if key not in seen or key in completed:raise ValueError('journal completion corruption')
                completed.add(key)

    def _parts(self,key):
        parts=key.split('/')
        if (len(parts)!=3 or parts[0] not in self.budgets or parts[1] not in self.ids
                or not parts[2].isdigit() or str(int(parts[2]))!=parts[2]
                or not 1<=int(parts[2])<=self.budgets[parts[0]]):raise ValueError('foreign target/system/attempt')
        return parts[0],parts[1],int(parts[2])

    def reserve(self,key,budget=None):
        system,eid,attempt=self._parts(key);reserved=self.reserved()
        if key in reserved:raise ValueError('attempt already reserved; never replay')
        if len(reserved)>=sum(self.budgets.values())*len(self.ids):raise ValueError('frozen total call ceiling')
        if attempt>1 and call_state(self,f'{system}/{eid}/{attempt-1}')[0]!='completed':
            raise ValueError('previous attempt incomplete or uncertain')
        self.append(dict(type='generation_reserved',key=key))


def text_sha(text):return hashlib.sha256(text.encode()).hexdigest()


def validate_dataset(sources,gold,labels):
    if len(sources)!=40 or len(gold)!=40:raise ValueError('exactly40 sources/gold required')
    by_id={r['sample_id']:r for r in gold};families=defaultdict(list);ids=set();codes=set()
    if len(by_id)!=40:raise ValueError('duplicate gold ID')
    for source in sources:
        if set(source)!=SOURCE_KEYS:raise ValueError('source input whitelist')
        sid=source['sample_id']
        if sid in ids or sid not in by_id:raise ValueError('source/gold ID coverage')
        ids.add(sid);g=by_id[sid]
        if (source['language']!='cpp11' or source['exam_type']!='single_problem'
                or source['checker'] not in ('tokens','exact_bytes') or not source['code'].endswith('\n')):
            raise ValueError('source submission contract')
        if g['family_id']!=source['family_id'] or type(g['faulty'])is not bool:raise ValueError('family/status binding')
        if g['source_sha256']!=text_sha(source['code']) or g['statement_sha256']!=text_sha(source['statement']):
            raise ValueError('source/spec hash differs from private gold')
        if (type(g['taxonomy'])is not list or len(set(g['taxonomy']))!=len(g['taxonomy'])
                or not set(g['taxonomy'])<=set(labels) or bool(g['taxonomy'])!=g['faulty']):
            raise ValueError('official labels/status conflict')
        normalized=''.join(source['code'].split())
        if normalized in codes:raise ValueError('duplicate normalized evaluation source')
        codes.add(normalized);families[source['family_id']].append((source,g))
    if len(families)!=20:raise ValueError('exactly20 problem families')
    for pair in families.values():
        if len(pair)!=2 or {g['faulty'] for s,g in pair}!={False,True}:raise ValueError('one clean/faulty pair')
        if pair[0][0]['statement']!=pair[1][0]['statement'] or pair[0][0]['checker']!=pair[1][0]['checker']:
            raise ValueError('paired specifications/checkers must match exactly')
    return True


def build_targets(sources,syntax):
    targets=[]
    for s in sources:
        if set(s)!=SOURCE_KEYS:raise ValueError('source input whitelist')
        if s['sample_id'] not in syntax or not isinstance(syntax[s['sample_id']].get('diagnostic'),str):
            raise ValueError('missing syntax-only evidence')
        for level in (1,2,3,4):
            x={k:s[k] for k in ('statement','exam_type','language','code')}
            x.update(compile_log=syntax[s['sample_id']]['diagnostic'],target_feedback_level=level)
            targets.append(dict(sample_id=f"{s['sample_id']}-L{level}",source_id=s['sample_id'],family_id=s['family_id'],input=x))
    if len({r['sample_id'] for r in targets})!=len(targets):raise ValueError('duplicate target ID')
    return targets


def _summary(rows):
    rows=list(rows)
    # The inherited aggregate helper re-parses using the native EOS-only parser.
    # A's authentic parser accepts schema payloads regardless of termination.
    # Project ONLY the already accepted A payload into that helper's interface;
    # raw text/actual termination in the durable generation and review stay intact.
    projected=[dict(r,raw=json.dumps(r['parsed'],ensure_ascii=False),finish_reason='eos')
        if r.get('payload_acceptance')=='historical_A' and r['status']=='valid' else r for r in rows]
    s=summarize(projected)
    contradictions=[r for r in rows if r.get('taxonomy_feedback_contradiction')is True]
    s.update(contradictions=len(contradictions),contradiction_sources=len({r['sample_id'] for r in contradictions}),
        contradiction_families=len({r['family_id'] for r in contradictions}),
        uncertain_reviews=sum(r['status']=='valid' and (semantic_value(r,'successful_feedback')is None
            or r.get('taxonomy_feedback_contradiction')=='uncertain') for r in rows))
    return s


def family_success(rows):
    result={'sources':{},'families':{}}
    for key,field in [('sources','sample_id'),('families','family_id')]:
        groups=defaultdict(list)
        for row in rows:groups[row[field]].append(row)
        for group,values in groups.items():
            primary=[r for r in values if r['level']<=3]
            result[key][group]=dict(sources=len({r['sample_id'] for r in values}),targets=len(values),
                primary_targets=len(primary),primary_success=sum(successful_feedback(r) for r in primary),
                secondary_l4_targets=sum(r['level']==4 for r in values),
                secondary_l4_success=sum(r['level']==4 and successful_feedback(r) for r in values),
                primary_invalid=sum(r['status']!='valid' for r in primary),
                primary_contradictions=sum(r.get('taxonomy_feedback_contradiction')is True for r in primary))
    return result


def summarize_system(rows):
    rows=list(rows)
    return dict(all=_summary(rows),primary=_summary(r for r in rows if r['level']<=3),
        secondary_l4=_summary(r for r in rows if r['level']==4),
        faulty_l23=_summary(r for r in rows if r['faulty'] and r['level']in(2,3)),
        faulty_l3=_summary(r for r in rows if r['faulty'] and r['level']==3),
        by_level={str(l):_summary(r for r in rows if r['level']==l) for l in (1,2,3,4)},
        by_level_status={str(l):{name:_summary(r for r in rows if r['level']==l and r['faulty']==flag)
            for name,flag in [('clean',False),('faulty',True)]} for l in (1,2,3,4)},
        primary_by_status={name:_summary(r for r in rows if r['level']<=3 and r['faulty']==flag)
            for name,flag in [('clean',False),('faulty',True)]},grouped=family_success(rows))


def level_safety(before,after):
    left={r['example_id']:r for r in before if r['level']<=3};right={r['example_id']:r for r in after if r['level']<=3}
    if set(left)!=set(right):raise ValueError('paired primary IDs differ')
    result=dict(new_disclosure_failures=0,new_required_content_failures=0,uncertain_level_pairs=0,invalid_level_pairs=0,targets=[])
    for eid in sorted(left):
        a,b=left[eid],right[eid]
        if (a['sample_id'],a['level'])!=(b['sample_id'],b['level']):raise ValueError('paired source/Level differs')
        if a['status']!='valid' or b['status']!='valid':result['invalid_level_pairs']+=1;continue
        if any(r['axes'].get(k) not in ('pass','fail') for r in (a,b) for k in ('disclosure_compliance','required_content')):
            result['uncertain_level_pairs']+=1
        for axis,name in [('disclosure_compliance','new_disclosure_failures'),('required_content','new_required_content_failures')]:
            if a['axes'].get(axis)=='pass' and b['axes'].get(axis)=='fail':
                result[name]+=1;result['targets'].append(dict(example_id=eid,axis=axis))
    return result


def screen_v3(systems,paired_safety):
    if 'V3-v3'not in systems or 'V2-old'not in systems:raise ValueError('required native comparator unavailable')
    current=systems['V3-v3'];baselines=[s for s in ('V2-old','A') if s in systems];comparisons={}
    def gate(v,c,operator):
        return dict(v3=v,comparator=c,operator=operator,passed={'gt':v>c,'ge':v>=c,'le':v<=c,'eq':v==c}[operator])
    for name in baselines:
        base=systems[name];safety=paired_safety[name]
        checks=dict(joint_primary=gate(current['primary']['successful_feedback'],base['primary']['successful_feedback'],'gt'),
            diagnosis_l23=gate(current['faulty_l23']['supported_faulty_diagnosis'],base['faulty_l23']['supported_faulty_diagnosis'],'ge'),
            repair_l3=gate(current['faulty_l3']['faulty_l3_correct'],base['faulty_l3']['faulty_l3_correct'],'ge'),
            clean_false_alarms=gate(current['primary']['clean_false_alarms'],base['primary']['clean_false_alarms'],'le'),
            invalid_primary=gate(current['primary']['invalid'],base['primary']['invalid'],'le'),
            systematic_contradictions=gate(current['primary']['contradiction_families'],1,'le'),
            new_disclosure_failures=gate(safety['new_disclosure_failures'],0,'eq'),
            new_required_content_failures=gate(safety['new_required_content_failures'],0,'eq'),
            disputed_primary=gate(current['primary']['uncertain_reviews']+base['primary']['uncertain_reviews']+safety['uncertain_level_pairs'],0,'eq'))
        comparisons[name]=checks
    passed=all(c['passed'] for checks in comparisons.values() for c in checks.values())
    return dict(passed=passed,available_baselines=baselines,comparisons=comparisons,
        recommendation='eligible_for_separately_authorized_public_inference' if passed else 'retain_A_submission_baseline',
        public_inference_authorized=False,public_inference_executed=False,
        policy=POLICY['decision'],claim='Conservative screening on newly authored agent-reviewed data; not proof of generalization or official score.')
