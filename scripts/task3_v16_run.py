#!/usr/bin/env python3
"""Frozen bounded v1.6 experiment: offline replay, probes, internal A/B, selected public.

No upload/submission. A review checkpoint keeps the model loaded while source-grounded
agent review is written locally; it is not an approval request or quality gate.
"""
from __future__ import annotations
import argparse
import copy
from collections import Counter
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.task3_arm_d_plus import DPlusBackend,validate_export
from scripts.task3_v15_observe import capture_runtime,stage_costs
from src.task3 import arm_d_plus_v15 as old
from src.task3 import arm_d_plus_v16 as method
from src.task3 import compiler_evidence,diagnostic_view,v15_evaluation
from src.task3.dataset import read_json,write_json
from src.task3.inference import load_tokenizer,tokenizer_metadata
from src.task3.level_blind import digest,sha
from src.task3.public_contract import verify_public_contract
from src.task3.v16_experiment import offline_replay,stable,metrics,paired_cases,pair_units,public_sample,jsonl

PRIOR=ROOT/'outputs/task3/v1.5-observation-20261024'
DEFAULT_OUT=ROOT/'outputs/task3/v1.6-json-transport-grounded'


def require(ok,message):
    if not ok:raise ValueError(message)


def prepare(out,prior,config,tok):
    units={p:read_json(prior/p/'enriched-inputs.private.json')['units'] for p in ('internal','public')}
    space=read_json(prior/'internal/label-space.private.json')
    require(space==read_json(prior/'public/label-space.private.json'),'label space mismatch')
    contract=verify_public_contract(Path('/workspace/llm-final-project/data/raw/public_test_release'))
    for phase in units:
        expected=30 if phase=='internal' else 328
        require(len(units[phase])==len({u['sample_id'] for u in units[phase]})==expected,'exact population required')
        for u in units[phase]:old.validate_unit(u)
        requested=read_json(prior/phase/'requested-levels.private.json')
        require(set(requested)=={u['sample_id'] for u in units[phase]},'requested IDs mismatch')
        require(all(requested[u['sample_id']]==old.v14.FEEDBACK_LEVELS[u['level']-1] for u in units[phase]),'Level mapping mismatch')
        if phase=='public':
            require(requested==contract['requested_levels'],'public authoritative mapping drift')
            require(dict(Counter(u['level'] for u in units[phase]))=={1:115,2:163,3:50},'public Level counts drift')
        stable(out/'inputs'/f'{phase}.private.json',units[phase])
        stable(out/'inputs'/f'{phase}-requested-levels.private.json',requested)
    stable(out/'inputs/gold.private.json',read_json(prior/'internal/gold.private.json'))
    stable(out/'inputs/label-space.private.json',space)
    stable(out/'public-review-selection.json',public_sample(units['public']))
    cases=paired_cases();stable(out/'paired-inputs-and-expectations.private.json',cases)
    fixture_out=out/'paired-preparation'
    if (fixture_out/'enriched-inputs.private.json').exists():
        pair_enriched=read_json(fixture_out/'enriched-inputs.private.json')['units']
        # Bind cache/source without recompiling or overwriting prep costs.
        require([u['task'] for u in pair_enriched]==[u['task'] for u in pair_units(cases)],'pair input drift')
    else:pair_enriched,_=compiler_evidence.prepare(pair_units(cases),fixture_out)
    for u in pair_enriched:old.validate_unit(u)
    stable(out/'renderer-fixtures.private.json',v15_evaluation.load_fixtures())
    checks=[]
    for phase,population in [*units.items(),('paired',pair_enriched)]:
        for arm in ('A','B'):
            for u in population:
                messages=method.messages_findings(u,space['taxonomy_error'],arm)
                projected,view=diagnostic_view.prepare_messages(u,messages,tok,config['findings_max_new_tokens'],config['context_limit'])
                count=len(tok.apply_chat_template(projected,tokenize=True,add_generation_prompt=True))
                require(count+config['findings_max_new_tokens']<=config['context_limit'],'projected detector context overflow')
                checks.append(dict(phase=phase,arm=arm,sample_id=u['sample_id'],tokens=count,view=view,prompt_sha256=digest(projected)))
    # Freeze implementations, original evidence bindings, prompts/policies before any model load.
    files=sorted((ROOT/'src').rglob('*.py'))+[Path(__file__),ROOT/'scripts/task3_arm_d_plus.py',ROOT/'scripts/task3_v15_observe.py']
    frozen=dict(version=method.VERSION,config=config,tokenizer=tokenizer_metadata(tok),
        code_sha256={str(p.relative_to(ROOT)):sha(p) for p in files},
        prompts=dict(A=method.FINDINGS_A,B=method.FINDINGS_B,L2=method.LEVEL2_SYSTEM,L2_identity=method.L2_VERSION,
                     other_feedback=old.FEEDBACK_SYSTEM,level1=old.LEVEL1_FEEDBACK,guidance=old.GUIDANCE,
                     repair=method.REPAIR_SYSTEM,length_replacement=method.LENGTH_REPLACEMENT,resolver=old.RESOLVER_SYSTEM),
        labels=space,parser_identity=method.PARSER_VERSION,transport_version=method.transport.VERSION,
        diagnostic_version=diagnostic_view.VERSION,paired_inputs_sha256=digest(cases),
        historical_bindings={phase:{name:sha(prior/phase/name) for name in ('enriched-inputs.private.json','attempts.jsonl','method-freeze.json','requested-levels.private.json')} for phase in units},
        inputs_sha256={phase:digest(pop) for phase,pop in units.items()},
        policy=dict(attempt0_only=True,historical_correction_diagnostic_only=True,corrections_per_stage=1,
            length_policy='one complete concise replacement; same cap',kind_never_coerced=True,quality_nonblocking=True,
            global_selection='Prefer B only if coverage/micro/macro/paired >= A (F1 tolerance1e-12), unsupported cases <= A, at least one strict improvement and no disputed verdict; otherwise A.',
            review_rubric=['supported','partially_supported_mislocated','unsupported','condition_omitted','optional_requirement_invented','genuine_omission','gold_disagreement'],
            review_by='source-grounded Codex agent, not independent human grading',
            no_case_specific_manual_edits=True,no_public_gold=True,no_per_id_arm_selection=True,
            output_only_on_exact_id_schema_validation=True))
    # JSON integer keys are normalized once, before stable comparisons.
    frozen=json.loads(json.dumps(frozen,ensure_ascii=False))
    stable(out/'method-freeze.json',frozen)
    for name in frozen['code_sha256']:
        target=out/'frozen-code'/name
        if target.exists():require(sha(target)==frozen['code_sha256'][name],'frozen code drift')
        else:target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    stable(out/'preflight.json',dict(all_fit=True,model_loaded=False,cases=checks))
    bound={**config,'implementation_sha256':digest(frozen),'method_identity':method.VERSION,'L2_identity':method.L2_VERSION}
    return units,pair_enriched,space,bound


def renderer_fixtures(backend,config,out,space):
    out=out/'renderer';fixtures=v15_evaluation.load_fixtures()
    journal=old.DPlusJournal(out,backend,config,digest([fixtures,method.LEVEL2_SYSTEM,config]))
    results=[]
    for c in fixtures:
        u=dict(level=2)
        r=dict(case_id=c['case_id'],status='unresolved',feedback=None,failure=None)
        try:
            feedback=method.schema_stage(journal,c['case_id'],'feedback',method.messages_feedback(u,c['findings'],space['taxonomy_error'],space['feedback_level']),u)
            r.update(status='resolved',feedback=feedback)
        except ValueError as exc:r['failure']=method.failure_record(exc)
        results.append(r);write_json(out/'results.private.json',results)
    return results


def selection_from_reviews(out,gold,populations,pairs):
    reviews=read_json(out/'reviews/internal-and-probes.private.json')
    measures={};disputed=False
    for arm in ('A','B'):
        rr=reviews['internal'][arm];population=populations[arm]
        by={r['sample_id']:r for r in rr}
        require(len(by)==len(rr)==30 and set(by)=={r['sample_id'] for r in population},'review exact30 mismatch')
        for r in population:
            review=by[r['sample_id']]
            require(review['result_sha256']==digest(r),'review result binding mismatch')
            require(review.get('reason') and isinstance(review.get('unsupported_case'),bool),'review rubric incomplete')
            disputed=disputed or review.get('disputed',False)
        pr=reviews['paired'][arm];pb={r['sample_id']:r for r in pr}
        require(len(pb)==len(pr)==12 and set(pb)=={r['sample_id'] for r in pairs[arm]},'pair review mismatch')
        for r in pairs[arm]:
            review=pb[r['sample_id']]
            require(review['result_sha256']==digest(r),'pair review binding mismatch')
            require(type(review.get('expected_diagnosis_pass')) is bool,'pair verdict must be boolean')
            require(type(review.get('disputed',False)) is bool,'pair dispute must be boolean')
            disputed=disputed or review.get('disputed',False)
        pair_scores=[]
        for pair in sorted({r['sample_id'].rsplit('-',1)[0] for r in pairs[arm]}):
            pair_scores.append(all(pb[pair+'-'+v]['expected_diagnosis_pass'] for v in ('a','b')))
        m=metrics(gold,population)
        measures[arm]=dict(coverage=m['valid'],micro_f1=m['micro_f1'],macro_f1=m['macro_f1'],
            unsupported_cases=sum(r['unsupported_case'] for r in rr),paired_score=sum(pair_scores))
    selected=method.select_method(measures['A'],measures['B'],disputed)
    selected.update(reviews_sha256=sha(out/'reviews/internal-and-probes.private.json'),frozen_method_sha256=sha(out/'method-freeze.json'))
    return selected


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=DEFAULT_OUT)
    p.add_argument('--prior',type=Path,default=PRIOR)
    p.add_argument('--mode',choices=['replay','preflight','run','verify'],required=True)
    args=p.parse_args();out=args.out.resolve();prior=args.prior.resolve()
    require(Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=ROOT,text=True).strip())==ROOT,'root mismatch')
    require(subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='fix/task3-strict-feedback','branch mismatch')
    require(out.is_relative_to(ROOT/'outputs') and not out.is_relative_to(prior),'new output outside historical run required')
    out.mkdir(parents=True,exist_ok=True);out.chmod(0o700)
    if not (out/'initial-state.json').exists():
        write_json(out/'initial-state.json',dict(root=str(ROOT),branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
            HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
            no_AGENTS_found=True,requested_report_language='Vietnamese',timezone='Asia/Saigon'))
    replay,cache=offline_replay(prior,out)
    if args.mode=='replay':print(json.dumps(replay,ensure_ascii=False));return 0
    config=read_json(ROOT/'configs/task3/arm_d_plus_v15.json');config={**config,'version':method.VERSION}
    stable(out/'config.json',config)
    os.environ.update(HF_HOME='/workspace/llm-final-project/outputs/task3/hf-cache',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    tok=load_tokenizer(config)
    units,paired,space,bound=prepare(out,prior,config,tok)
    stable(out/'commands.json',dict(replay=f'{sys.executable} {Path(__file__)} --out {out} --mode replay',
        preflight=f'{sys.executable} {Path(__file__)} --out {out} --mode preflight',
        run=f'{sys.executable} {Path(__file__)} --out {out} --mode run',
        verify=f'{sys.executable} {Path(__file__)} --out {out} --mode verify',
        actual_invocation=shlex.join([sys.executable,str(Path(__file__)),*sys.argv[1:]]).replace('--mode run','--mode MODE').replace('--mode preflight','--mode MODE').replace('--mode verify','--mode MODE')))
    if args.mode=='preflight':print(json.dumps(dict(preflight='passed',internal=30,public=328,paired=12,model_loaded=False)));return 0
    if args.mode=='verify':
        audit=[]
        for path in sorted(out.rglob('attempts.jsonl')):
            if 'replay' in path.parts:continue
            rows=jsonl(path);reserved=jsonl(path.with_name('reservations.jsonl'))
            require(len({r['key'] for r in rows})==len(rows),'duplicate generated row')
            require({r['key'] for r in rows}<={r['key'] for r in reserved},'unreserved generation')
            for r in rows:
                n=len(tok.apply_chat_template(r['messages'],tokenize=True,add_generation_prompt=True))
                cap=1 if r['stage']=='resolver' else config['findings_max_new_tokens'] if r['stage']=='taxonomy' else config['max_new_tokens']
                require(n==r['input_tokens'] and n+cap<=config['context_limit'],'journal token/context mismatch')
                require(r['prompt_sha256']==digest(r['messages']),'journal prompt hash mismatch')
            audit.append(dict(path=str(path),calls=len(rows),tokens_fit=True))
        selected=read_json(out/'selection.json')['selected']
        for phase,pop in [('internal-A',units['internal']),('internal-B',units['internal']),('public',units['public'])]:
            path=out/phase;results=read_json(path/'results.private.json')
            require(len(results)==len(pop) and {r['sample_id'] for r in results}=={u['sample_id'] for u in pop},'final population mismatch')
            by={u['sample_id']:u for u in pop}
            for r in results:
                require(r['level']==by[r['sample_id']]['level'],'Level drift')
                if r['stage1'] is not None:old.validate_normalized(r['stage1']['findings'],by[r['sample_id']],space['taxonomy_error'])
            requested={u['sample_id']:old.v14.FEEDBACK_LEVELS[u['level']-1] for u in pop}
            try:validate_export(path,requested,space['taxonomy_error'])
            except ValueError:pass
        write_json(out/'verification.json',dict(passed=True,selected=selected,journals=audit,public=read_json(out/'public/validation.json')))
        print(json.dumps(dict(verified=True,selected=selected,journals=audit)));return 0
    free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()
    require(len(free)==1 and int(free[0])>=config['minimum_free_gpu_mib'],'CUDA free memory insufficient')
    started=time.perf_counter();backend=None;load_index=len(jsonl(out/'model-loads.jsonl'))+1
    from src.task3.two_pass import append
    try:
        backend=DPlusBackend(config,tok,out)
        append(out/'model-loads.jsonl',dict(load_index=load_index,runtime=backend.runtime_metadata()))
        write_json(out/'runtime-before.json',backend.runtime_metadata())
        renderer_fixtures(backend,bound,out,space)
        pair_results={arm:method.run_units(paired,backend,bound,out/f'paired-{arm}',space,arm,detector_only=True) for arm in ('A','B')}
        internal={}
        for arm in ('A','B'):
            internal[arm]=method.run_units(units['internal'],backend,bound,out/f'internal-{arm}',space,arm,
                                           replays=cache['internal'] if arm=='A' else None)
        gold=read_json(out/'inputs/gold.private.json')
        comp={arm:dict(detector=metrics(gold,internal[arm]),end_to_end=metrics(gold,internal[arm],False)) for arm in ('A','B')}
        comp.update(replay_only_A=replay['internal']['detector_metrics'],historical=read_json(prior/'internal-comparison.private.json'))
        write_json(out/'internal-comparison.private.json',comp)
        write_json(out/'review-request.json',dict(status='waiting_for_source_grounded_agent_review',
            target='reviews/internal-and-probes.private.json',not_user_approval=True,quality_failures_nonblocking=True))
        print('INTERNAL_AND_PROBES_READY_FOR_REVIEW',flush=True)
        while not (out/'reviews/internal-and-probes.private.json').exists():time.sleep(2)
        selected=selection_from_reviews(out,gold,internal,pair_results);stable(out/'selection.json',selected)
        write_json(out/'review-request.json',dict(status='review_complete',selected=selected['selected']))
        print('GLOBAL_SELECTED_'+selected['selected'],flush=True)
        public=method.run_units(units['public'],backend,bound,out/'public',space,selected['selected'],
                                replays=cache['public'] if selected['selected']=='A' else None)
        for phase,population in [('internal-A',internal['A']),('internal-B',internal['B']),('public',public)]:
            original=units['public'] if phase=='public' else units['internal']
            requested={u['sample_id']:old.v14.FEEDBACK_LEVELS[u['level']-1] for u in original}
            try:validate_export(out/phase,requested,space['taxonomy_error'])
            except ValueError:pass
            write_json(out/phase/'unresolved.private.json',[r for r in population if r['status']!='resolved'])
        print('PUBLIC_COMPLETE_BOUNDED_ATTEMPT',flush=True)
    finally:
        if backend is not None:capture_runtime(backend,out/f'runtime-after-load-{load_index}.json')
        paths=[out/n for n in ('renderer','paired-A','paired-B','internal-A','internal-B','public')]
        write_json(out/'costs-and-runtime.json',dict(model_loads=jsonl(out/'model-loads.jsonl'),
            phases={path.name:stage_costs(path) for path in paths},process_elapsed_s=time.perf_counter()-started,
            historical_replay_cost_new_calls=0,paired_compiler=read_json(out/'paired-preparation/compiler-audit.private.json')))


if __name__=='__main__':raise SystemExit(main())
