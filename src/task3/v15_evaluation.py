"""Bounded fixed-findings experiment, frozen promotion policy and comparisons."""
from __future__ import annotations
import copy
from collections import Counter
import json
from pathlib import Path
from src.task3 import arm_d_plus as old
from src.task3 import arm_d_plus_v15 as plus
from src.task3.dataset import read_json,write_json
from src.task3.grounded_metrics import taxonomy_metrics
from src.task3.level_blind import digest,sha
from src.task3.source_refs import build_catalog, source_sha

FIXTURES = Path(__file__).resolve().parents[2]/'configs/task3/renderer_v15_fixtures.json'
POLICY_VERSION = 'conservative-engineering-public-promotion-v1'
KNOWN_KINDS = ('false_initialization','false_bounds','ignored_compiler_error','concrete_L2_repair')
INTERNAL_DIMENSIONS = ('findings_factual','feedback_factual','location_cause','level_compliance','schema','natural_vietnamese')


def load_fixtures():
    cases=read_json(FIXTURES)
    if len(cases)!=8 or len({c['case_id'] for c in cases})!=8:raise ValueError('eight unique cases required')
    for c in cases:
        if source_sha(c['source'])!=c['source_sha256']:raise ValueError('fixture source hash mismatch')
        u=dict(source_catalog=build_catalog(c['source']),source_map_version='source-catalog-lines-v1',
               local_compiler={},task=dict(statement=c['requirement'],exam_type='single_problem',code=c['source'],problems=[{'pid':'P1'}]))
        plus.parse_findings(json.dumps({'findings':c['findings']}),u)
    return cases


def projection(case):
    return {k:[{name:f[name] for name in ('problem_id','location','error')} for f in case['findings']] for k in ['findings']}


def review_binding(output,verdicts,reviewer,method,reasons=None):
    return dict(output_sha256=digest(output),reviewer=reviewer,method=method,independent_human=False,
                verdicts=verdicts,reasons=reasons or [])


def validate_review(output,review):
    if review['output_sha256']!=digest(output) or not review['reviewer'] or not review['method']:
        raise ValueError('qualitative review output hash/identity mismatch')
    return True


def run_renderer_experiment(backend,config,out,space):
    out=Path(out);cases=load_fixtures()
    frozen=dict(cases=cases,fixtures_sha256=sha(FIXTURES),prompts={'v14':old.FEEDBACK_SYSTEM,'v15':plus.LEVEL2_SYSTEM},
                projection='only problem_id, location, error; requested Level2 and official rule',
                scope='isolated development; same common projection; not historical end-to-end reproduction')
    path=out/'renderer-fixtures-freeze.json'
    if path.exists() and read_json(path)!=frozen:raise ValueError('renderer fixture freeze drift')
    write_json(path,frozen)
    labels=space['taxonomy_error'];definitions=space['feedback_level']
    identity=digest([frozen,config,plus.method_identity(config,labels,definitions,backend.tokenizer)])
    journal=plus.DPlusJournal(out/'renderer-eval',backend,config,identity)
    results=[]
    for version,system in frozen['prompts'].items():
        for c in cases:
            messages=plus.messages_feedback({'level':2},c['findings'],labels,definitions);messages[0]['content']=system
            row=dict(prompt_version=version,case_id=c['case_id'],status='unresolved',feedback=None,failure=None)
            try:
                row.update(status='resolved',feedback=plus.schema_stage(journal,version+'/'+c['case_id'],'feedback',messages,lambda raw:plus.parse_feedback(raw,2)))
            except (ValueError,TypeError,KeyError) as exc:
                row['failure']=dict(category=getattr(exc,'category','schema'),reason=str(exc))
            results.append(row);write_json(out/'renderer-eval/outputs.private.json',results)
    attempts=[json.loads(line) for line in (out/'renderer-eval/attempts.jsonl').read_text().splitlines()]
    write_json(out/'renderer-eval/costs.json',dict(normal_calls=sum(r['kind']=='normal' for r in attempts),
        correction_calls=sum(r['kind']=='repair' for r in attempts),input_tokens=sum(r['input_tokens'] for r in attempts),
        output_tokens=sum(r.get('output_tokens') or 0 for r in attempts),latency_s=sum(r['latency_s'] for r in attempts)))
    return results


def renderer_reviews(out):
    out=Path(out);results=read_json(out/'renderer-eval/outputs.private.json');reviews=read_json(out/'renderer-eval/reviews.private.json')
    expected={(version,c['case_id']) for version in ('v14','v15') for c in load_fixtures()}
    output_keys=[(r['prompt_version'],r['case_id']) for r in results]
    review_keys=[(r['prompt_version'],r['case_id']) for r in reviews]
    if len(output_keys)!=16 or len(set(output_keys))!=16 or set(output_keys)!=expected or len(review_keys)!=16 or len(set(review_keys))!=16 or set(review_keys)!=expected:
        raise ValueError('renderer outputs/reviews require exact unique frozen case/version keys')
    by={(r['prompt_version'],r['case_id']):r for r in reviews}
    if len(by)!=16:raise ValueError('duplicate renderer reviews')
    checks=[]
    for row in results:
        r=by[(row['prompt_version'],row['case_id'])];validate_review(row,r)
        if row['prompt_version']=='v15':
            required=('factual_fidelity','location_cause','level2_disclosure','empty_findings')
            checks.append(row['status']=='resolved' and all(r['verdicts'].get(k) is True for k in required))
    return dict(new_prompt_all_eight_pass=len(checks)==8 and all(checks),new_prompt_passed=sum(checks),new_prompt_expected=8)


def tax(row):return row['output']['taxonomy_error'] if row['status']=='resolved' else None


def comparison(gold,populations):
    ids=[g['sample_id'] for g in gold];g={r['sample_id']:r['taxonomy_error'] for r in gold}
    clean=[sid for sid in ids if not g[sid]]
    all_metrics={};same={}
    for name,rows in populations.items():
        by={r['sample_id']:r for r in rows}
        if len(by)!=len(rows) or set(by)!=set(ids):raise ValueError('comparison population ID mismatch: '+name)
        def score(subset,by=by):
            m=taxonomy_metrics([g[sid] for sid in subset],[tax(by[sid]) for sid in subset])
            m['clean_false_alarms']=sum(bool(tax(by[sid])) for sid in subset if sid in clean)
            for p in m['per_label'].values():p['recall']=p['TP']/p['support'] if p['support'] else 0.
            return m
        all_metrics[name]=score(ids)
        same[name]=score
    fixed26=[sid for sid in ids if 'v14' not in populations or next(r for r in populations['v14'] if r['sample_id']==sid)['status']=='resolved']
    shared=[sid for sid in ids if all(next(r for r in rows if r['sample_id']==sid)['status']=='resolved' for rows in populations.values())]
    return dict(all=all_metrics,fixed_v14_resolved_ids=fixed26,
                fixed_v14_resolved={name:fn(fixed26) for name,fn in same.items()} if fixed26 else {},
                same_resolved_ids=shared,same_resolved={name:fn(shared) for name,fn in same.items()} if shared else {},clean_ids=clean)


def freeze_policy(gold_path,baselines,ids,expected=30):
    gold=read_json(gold_path)
    if len(ids)!=expected or [r['sample_id'] for r in gold]!=ids:raise ValueError('fixed input/gold population required')
    populations={name:read_json(path) for name,path in baselines.items()}
    metrics=comparison(gold,populations)['all']['D']
    scorer=Path(__file__).with_name('grounded_metrics.py')
    return dict(version=POLICY_VERSION,status='pending',population=ids,expected=expected,
                gold_binding={'path':str(Path(gold_path).resolve()),'sha256':sha(gold_path)},
                baseline_bindings={name:dict(path=str(Path(path).resolve()),sha256=sha(path)) for name,path in baselines.items()},
                metric=dict(implementation='src.task3.grounded_metrics.taxonomy_metrics',sha256=sha(scorer),
                            unresolved='invalid; included in all30 denominator'),numerical_tolerance=1e-12,
                thresholds={k:metrics[k] for k in ('micro_f1','macro_f1','clean_false_alarms')},
                clean_ids=[r['sample_id'] for r in gold if not r['taxonomy_error']],
                rules=['exact30 IDs/completions, missing0/extra0/duplicate0','no unresolved recovery or invalid references',
                       'all8 new renderer outputs factual/location/Level2/empty-findings pass; style separate',
                       'review all internal30; zero continuing false initialization/bounds, ignored compiler errors, concrete L2 repairs',
                       'both F1 >= historical D within1e-12 AND clean false alarms <= D; all requirements mandatory'],
                review_policy='qualitative automated-agent review, explicitly not independent human evaluation',
                promotion_policy='conservative engineering choice; not instructor requirement')


def metric_checks(policy,metrics):
    t=policy['thresholds'];epsilon=policy['numerical_tolerance']
    return dict(micro_f1=metrics['micro_f1']+epsilon>=t['micro_f1'],macro_f1=metrics['macro_f1']+epsilon>=t['macro_f1'],
                clean_false_alarms=metrics['clean_false_alarms']<=t['clean_false_alarms'])


def validate_internal_review(result,review):
    validate_review(result,review)
    if review.get('sample_id')!=result['sample_id'] or not review.get('reasons'):
        raise ValueError('internal review requires exact ID and qualitative reasons')
    verdicts=review.get('verdicts',{})
    if set(verdicts)!=set(INTERNAL_DIMENSIONS) or any(v not in ('pass','fail','mixed','not_evaluable') for v in verdicts.values()):
        raise ValueError('internal review requires separate factual/Level/schema judgments')
    checks=review.get('known_kind_checks',{})
    if set(checks)!=set(KNOWN_KINDS) or any(type(v) is not bool for v in checks.values()):
        raise ValueError('internal review requires explicit checks for every known failure kind')
    if review.get('known_failures')!=[k for k in KNOWN_KINDS if checks[k]]:
        raise ValueError('internal review known failures/checks mismatch')
    return True


def evaluate_gate(out):
    out=Path(out);policy=read_json(out/'public-run-gate-policy.json')
    for binding in [policy['gold_binding'],*policy['baseline_bindings'].values()]:
        if sha(Path(binding['path']))!=binding['sha256']:raise ValueError('frozen baseline/gold drift')
    results=read_json(out/'results.private.json');gold=read_json(out/'gold.private.json');units=read_json(out/'enriched-inputs.private.json')['units']
    baseline={name:read_json(binding['path']) for name,binding in policy['baseline_bindings'].items()}
    comp=comparison(gold,{**baseline,'v15':results});write_json(out/'comparison.private.json',comp)
    ids=[r['sample_id'] for r in results];units_by={u['sample_id']:u for u in units};valid_refs=True
    for r in results:
        if r['stage1'] is not None:plus.validate_normalized(r['stage1']['findings'],units_by[r['sample_id']],list(plus.DEFINITIONS))
    review_path=out/'internal-reviews.private.json';reviews=read_json(review_path) if review_path.exists() else []
    by={r['sample_id']:r for r in reviews};all_reviewed=len(by)==len(reviews)==len(ids)==policy['expected'] and set(by)==set(ids)
    known=Counter()
    if all_reviewed:
        for result in results:
            r=by[result['sample_id']];validate_internal_review(result,r);known.update(r['known_failures'])
    rendering=renderer_reviews(out)
    checks=dict(exact_ids=len(ids)==len(set(ids))==policy['expected'] and ids==policy['population'],
                all_completed=all(r['status']=='resolved' and not r['failure'] for r in results),valid_references=valid_refs,
                renderer=rendering['new_prompt_all_eight_pass'],all_internal_reviewed=all_reviewed,
                no_known_systematic_failures=all_reviewed and not any(known.values()),**metric_checks(policy,comp['all']['v15']))
    decision=dict(method_freeze_sha256=sha(out/'method-freeze.json'),status='passed' if all(checks.values()) else 'blocked',policy=policy,policy_sha256=sha(out/'public-run-gate-policy.json'),
                  checks=checks,measurements=comp['all']['v15'],known_failure_counts=dict(known),renderer_review=rendering,
                  reasons=[k for k,v in checks.items() if not v],public_inference_authorized=all(checks.values()))
    write_json(out/'public-run-gate.json',decision)
    return decision
