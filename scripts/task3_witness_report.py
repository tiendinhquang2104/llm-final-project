#!/usr/bin/env python3
"""Recompute paired witness metrics after inference; never calls a model."""
from __future__ import annotations
from collections import Counter,defaultdict
from copy import deepcopy
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.dataset import write_json
from src.task3.feedback_prompt import sha,verify_seal
from src.task3.witness_scoring import pair_metrics
ROOT=REPO/'outputs/task3/witness-behavior-20261022'


def apply_addendum(packet,addendum,parent_sha):
    if addendum['parent_review_sha256']!=parent_sha:raise ValueError('review addendum parent mismatch')
    result=deepcopy(packet);pairs={p['pair']['pair_id']:p for p in result};seen=set()
    allowed={'raw_first_operation_trace_present','raw_first_trace_reason_correct','raw_first_requirement_paraphrase'}
    for change in addendum['changes']:
        try:member=pairs[change['pair_id']]['members'][change['member']]
        except KeyError as exc:raise ValueError('unknown addendum member')from exc
        if member['sample_id']!=change['sample_id']or change['sample_id']in seen:raise ValueError('addendum ID mismatch or duplicate')
        patch=change['diagnosis_flag_patch']
        if not set(patch)<=allowed or not all(v is None or type(v)is bool for v in patch.values()):raise ValueError('invalid qualitative addendum')
        member['review']['diagnosis'].update(patch);member['review']['addendum']=deepcopy(change);seen.add(change['sample_id'])
    return result


def validate_membership(packet,selection):
    if len(packet)!=24 or len({p['pair']['pair_id']for p in packet})!=24:raise ValueError('all24 unique pairs required')
    expected={r['sample_id']:r for r in selection}
    if len(selection)!=48 or len(expected)!=48:raise ValueError('48 unique frozen IDs required')
    seen=set();splits=Counter();families=set()
    for p in packet:
        pair=p['pair'];splits[pair['split']]+=1
        if pair['family']in families:raise ValueError('family overlap within set')
        families.add(pair['family'])
        if set(p['members'])!={'base','mutant'}:raise ValueError('pair roles required')
        for role,member in p['members'].items():
            sid=member['sample_id'];r=expected.get(sid)
            if sid in seen or not r or pair['ids'][role]!=sid:raise ValueError('member ID mismatch or duplicate')
            if any(r[k]!=pair[k]for k in ['pair_id','family','split'])or r['member_private']!=role:raise ValueError('frozen selection mismatch')
            seen.add(sid)
    if seen!=set(expected)or splits!={'development':6,'evaluation':18}:raise ValueError('selection completeness or split mismatch')


def execution_summary(packet):
    def matches(c):
        a=c['actual']
        return a['executed'] and a['returncode']==0 and not a['timeout'] and a['stdout'].strip()==c['expected_stdout']
    baseline_ok=[];mutant_witness=[];executions=0;compiler_errors=0;tests=0
    for p in packet:
        members=p['hidden_execution']['members'];b=members['base'];m=members['mutant'];expected=[t['expected_stdout']for t in p['pair']['tests']]
        if not expected or any([c['expected_stdout']for c in members[role]['cases']]!=expected for role in ['base','mutant']):raise ValueError('hidden test coverage mismatch')
        baseline_ok.append(b['compiler']['status']=='pass' and all(matches(c)for c in b['cases']))
        compile_error=m['compiler']['status']=='error'
        if compile_error and not m['compiler'].get('stderr'):raise ValueError('missing compile diagnostic')
        mutant_witness.append(compile_error or any(c['actual']['executed'] and not matches(c)for c in m['cases']))
        compiler_errors+=compile_error;tests+=len(expected)
        executions+=sum(c['actual']['executed']for member in members.values()for c in member['cases'])
    if not all(baseline_ok) or not all(mutant_witness):raise ValueError('unverified baseline or mutant')
    return {'pairs':len(packet),'members':2*len(packet),'hidden_tests':tests,'hidden_runtime_executions':executions,'baseline_test_match':all(baseline_ok),'all_mutants_have_verified_witness_or_diagnostic':all(mutant_witness),'compiler_errors':compiler_errors,'global_correctness_claim':False}


def witness_success(status,score,is_base,mechanism_correct):
    return status==('no_defect_in_scope'if is_base else 'defect')and score['input_valid']and score['actual_correct']is True and score['expected_correct']is True and (not score['distinguishes']if is_base else score['distinguishes']and mechanism_correct is True)


def main():
    verify_seal(ROOT/'pre-inference-freeze.json');verify_seal(ROOT/'review-freeze.json')
    packet=apply_addendum(json.loads((ROOT/'paired-ledger.private.json').read_text()),json.loads((ROOT/'review-addendum.private.json').read_text()),sha(ROOT/'semantic-review.private.json'))
    if packet!=json.loads((ROOT/'paired-ledger-reviewed.private.json').read_text()):raise ValueError('derived review packet mismatch')
    validate_membership(packet,json.loads((ROOT/'frozen-selection.private.json').read_text()))
    execution=execution_summary(packet)
    rows=[]
    for p in packet:
        pair=p['pair'];b=p['members']['base'];m=p['members']['mutant'];br=b['review'];mr=m['review']
        baseline_base=br['R15']['no_spurious_base_defect']is True and not br['R15']['fallback']
        baseline_mutant=mr['R15']['main_mechanism_correct']is True and bool(m['R15']['output']['taxonomy_error'])and not mr['R15']['fallback']
        def candidate(member,is_base):
            d=member['diagnosis'];s=member['witness_scores']['primary_witness_score'];review=member['review']['diagnosis']
            return witness_success(d['status'],s,is_base,review['operational_main_mechanism_correct'])
        def observed(member,is_base):
            w=member['witness_scores'];s=w['raw_first_observation_score'];raw=w['raw_first_prediction']or{};review=member['review']['diagnosis']
            return witness_success(raw.get('status'),s,is_base,review['raw_first_mechanism_correct'])
        rows.append({'pair_id':pair['pair_id'],'family':pair['family'],'split':pair['split'],'mechanism':pair['mutation']['mechanism'],
            'R15':{'base_success':baseline_base,'mutant_success':baseline_mutant},
            'diagnosis_operational':{'base_success':candidate(b,True),'mutant_success':candidate(m,False)},
            'raw_first_posthoc':{'base_success':observed(b,True),'mutant_success':observed(m,False)},
            'raw_core_only_posthoc':{'base_success':(b['witness_scores']['raw_first_prediction']or{}).get('status')=='no_defect_in_scope','mutant_success':(m['witness_scores']['raw_first_prediction']or{}).get('status')=='defect'and mr['diagnosis']['raw_first_mechanism_correct']is True},
            'member_ids':pair['ids'],'context_dispute':br['R15']['context_dispute'],'review_authority':'author-agent review, not human-verified'})
    metrics={}
    for split in ['all','development','evaluation']:
        group=[r for r in rows if split=='all'or r['split']==split]
        metrics[split]={method:pair_metrics([{'pair_id':r['pair_id'],**r[method]}for r in group])for method in ['R15','diagnosis_operational','raw_first_posthoc','raw_core_only_posthoc']}
    by_mechanism={}
    for mechanism in sorted({r['mechanism']for r in rows}):
        group=[r for r in rows if r['mechanism']==mechanism]
        by_mechanism[mechanism]={method:pair_metrics([{'pair_id':r['pair_id'],**r[method]}for r in group])for method in ['R15','diagnosis_operational','raw_first_posthoc','raw_core_only_posthoc']}
    allmembers=[member for p in packet for member in p['members'].values()];rawmetrics={}
    for role in ['all','base','mutant']:
        members=allmembers if role=='all'else[p['members'][role]for p in packet];n=len(members)
        rawmetrics[role]={'IDs':n,'valid_input':sum(x['witness_scores']['raw_first_observation_score']['input_valid']for x in members),
            'actual_correct':sum(x['witness_scores']['raw_first_observation_score']['actual_correct']is True for x in members),
            'expected_correct':sum(x['witness_scores']['raw_first_observation_score']['expected_correct']is True for x in members),
            'actual_and_expected_correct':sum(x['witness_scores']['raw_first_observation_score']['actual_correct']is True and x['witness_scores']['raw_first_observation_score']['expected_correct']is True for x in members),
            'requirement_paraphrase':sum(x['review']['diagnosis']['raw_first_requirement_paraphrase']for x in members),
            'false_clean_decision':sum(x['review']['diagnosis']['raw_first_false_clean_decision']for x in members),
            'false_accusation':sum(x['review']['diagnosis']['raw_first_false_accusation']for x in members),
            'status_counts':dict(Counter((x['witness_scores']['raw_first_prediction']or{}).get('status','missing')for x in members))}
    run=json.loads((ROOT/'run.json').read_text());configuration=json.loads((ROOT/'resolved-config.json').read_text());gate=configuration['candidate']['gate'];evalm=metrics['evaluation']
    passed=(evalm['diagnosis_operational']['successes']>=gate['minimum_pair_successes']and evalm['diagnosis_operational']['successes']-evalm['R15']['successes']>=gate['minimum_gain_over_R15'])
    # The primary success minimum already fails; no hypothetical renderer or
    # repaired-output evaluation is created to rescue this diagnosis study.
    if passed:raise ValueError('gate unexpectedly passed: separate false-clean check and renderer review required before proceeding')
    calls={}
    for arm,path in [('R15',ROOT/'R15/attempts.jsonl'),('diagnosis',ROOT/'diagnosis/attempts.jsonl')]:
        data=[json.loads(l)for l in path.read_text().splitlines()]
        calls[arm]={'calls':len(data),'output_tokens':sum(x.get('output_tokens',0)for x in data),'generation_latency_s':sum(x.get('latency_s',0)for x in data),'runtime_errors':sum(bool(x.get('error')or x.get('runtime_error'))for x in data)}
    original_annotations=json.loads((ROOT/'annotation-audit.private.json').read_text())
    result={'verdict':'KEEP_R15_STOP_AT_DIAGNOSIS','answer':'No demonstrated improvement in reliable executable-witness diagnosis; operational format failure is a major confound, and raw-first traces also show requirement substitution, invalid inputs and numerical errors. Not a universal rejection of witness reasoning.',
        'review_authority':'author-agent review, not human-verified','pairs':metrics,'by_mechanism':by_mechanism,'operational_status_counts':run['diagnosis_status_counts'],
        'primary_witness_valid':sum(x['witness_scores']['primary_witness_score']['input_valid']for x in allmembers),
        'raw_first_posthoc':rawmetrics,'raw_first_policy':'Core-only post-hoc ignores schema/input/numerical correctness and is not a reliable witness success. Strict raw-first post-hoc additionally requires valid input, correct actual/expected and distinguishing mutant witness. Explicitly post-hoc. First attempt for every ID only. For stdin-only tasks, omitted files interpreted as{} for observation. Never count these as valid candidate completions, fallback or gate successes. All48/24 remain denominators.',
        'R15':{'base_nonempty_taxonomy':sum(bool(p['members']['base']['R15']['output']['taxonomy_error'])for p in packet),'mutant_empty_taxonomy':sum(not p['members']['mutant']['R15']['output']['taxonomy_error']for p in packet),'mutant_mechanism_correct':sum(p['members']['mutant']['review']['R15']['main_mechanism_correct']is True for p in packet),'mutant_mechanism_unknown':sum(p['members']['mutant']['review']['R15']['main_mechanism_correct']is None for p in packet),'fallback':sum(x['review']['R15']['fallback']for x in allmembers)},
        'gate':{'preregistered':gate,'passed':False,'renderer_run':False,'renderer_corruption_evaluated_this_round':False,'fallback':'none; uncertain/schema errors remain failures'},'calls':calls,
        'execution':execution,
        'historical_annotation_audit':[{'sample_id':r['sample_id'],'annotation_original':r['annotation_original'],'proposal':'quarantine/repair in versioned derivative pending reviewer; original unchanged','human_verified':False}for r in original_annotations],
        'limitations':['All24 families exposed historically; development6/evaluation18 family disjoint only within this authored controlled set.','7 CSV cases share3 parser scaffolds; pair members intentionally near. Not24 statistically independent tasks.','Short explicit scope in English appended to Vietnamese task, exact-quote/schema constraints and original-filename vs harness-data.csv context friction confound instruction following with tracing.','Baseline validity is checked on listed driver tests; P3 helpers source-reviewed, not all separately executed; no proof outside scope/tests.','Read-only author review after seeing numerical evidence, not human verified.','Chroot/UID/seccomp sandbox shares host kernel; runtime FS readonly and resource bounded; fixed trusted compiler phase has per-process limits and no aggregate disk quota. Scratch must share rootfs filesystem for hardlinks.'],
        'freeze_sha256':sha(ROOT/'pre-inference-freeze.json'),'review_sha256':sha(ROOT/'review-freeze.json'),'review_addendum_sha256':sha(ROOT/'review-addendum.private.json'),'per_pair':rows}
    write_json(ROOT/'metrics.json',result);write_json(REPO/'reports/task3/TASK3_WITNESS_BEHAVIOR_RESULTS_20261022.json',result)
    print(json.dumps({'pairs':metrics,'status':run['diagnosis_status_counts'],'raw_first':rawmetrics,'calls':calls,'execution':result['execution'],'R15':result['R15'],'gate':False},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
