#!/usr/bin/env python3
"""User-authorized noninteractive v1.5 observation: internal30 then public328.

Run control only: inference prompts/config/parser/compiler/reservations are reused
unchanged. Quality assessments remain recorded but never authorize submission.
"""
from __future__ import annotations
import argparse
import copy
from collections import Counter
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import task3_arm_d_plus as runner
from src.task3 import arm_d_plus_v15 as plus
from src.task3 import compiler_evidence
from src.task3.dataset import read_json,write_json
from src.task3.inference import load_tokenizer,tokenizer_metadata
from src.task3.level_blind import digest,sha
from src.task3.two_pass import append

POLICY_VERSION='v15-observation-user-authorized-20261024-v1'
DEFAULT_PRIOR=ROOT/'outputs/task3/internal-arm-d-plus-v1.5-compiler-refs'


class ExecutionIntegrityFailure(Exception):
    """Stop measurement after a real backend failure, retaining durable rows."""


def execution_allowed(readiness,quality,phase):
    if phase not in ('internal','public') or readiness.get('integrity')!='passed' or readiness.get('infrastructure')!='ready':
        raise ExecutionIntegrityFailure('execution integrity/infrastructure is not ready')
    return True


@contextmanager
def stop_on_new_backend_failure():
    original=plus.DPlusJournal
    class ObservationJournal(original):
        def call(self,sid,stage,messages,attempt=0,resolver_id=None):
            key=digest([sid,stage,attempt,resolver_id]);replayed=key in self.reserved
            try:
                row=super().call(sid,stage,messages,attempt,resolver_id)
            except (ValueError,TypeError,KeyError) as exc:
                if isinstance(exc,plus.v14.StageFailure) and exc.category=='context':raise
                raise ExecutionIntegrityFailure('journal/backend construction failure: '+str(exc)) from exc
            if not replayed and row.get('error') and row.get('error_category')=='infrastructure':
                raise ExecutionIntegrityFailure(row['error'])
            return row
    plus.DPlusJournal=ObservationJournal
    try:yield
    finally:plus.DPlusJournal=original


def observe_phase(units,backend,config,out,space):
    with stop_on_new_backend_failure():
        return plus.run_units(units,backend,config,out,space)


def phase_counts(results):
    return dict(attempted=len(results),detector_valid=sum(r['stage1'] is not None for r in results),
                feedback_valid=sum(r['status']=='resolved' for r in results),unresolved=sum(r['status']!='resolved' for r in results))


def export_phase(out,results,requested,labels):
    out=Path(out)
    write_json(out/'detector-results.private.json',[dict(sample_id=r['sample_id'],level=r['level'],stage1=r['stage1'],failure=r['failure']) for r in results])
    write_json(out/'unresolved.private.json',[r for r in results if r['status']!='resolved'])
    try:return runner.validate_export(out,requested,labels)
    except ValueError:return read_json(out/'validation.json')


def capture_runtime(backend,path):
    try:metadata=backend.runtime_metadata()
    except Exception as exc:
        metadata=dict(capture_status='unavailable',exception=type(exc).__name__,reason=str(exc),
                      note='Backend measurement failed; this is not a claimed inference peak.')
    write_json(path,metadata)
    return metadata


def stable_file(path,value):
    path=Path(path)
    if path.exists():runner.require(read_json(path)==value,'frozen observation artifact drift: '+str(path))
    else:write_json(path,value)


def stage_costs(out):
    path=Path(out)/'attempts.jsonl';rows=[json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
    cost={}
    for stage in ('taxonomy','feedback','resolver'):
        selected=[r for r in rows if r['stage']==stage]
        cost[stage]=dict(normal_calls=sum(r['kind']=='normal' for r in selected),correction_calls=sum(r['kind']=='repair' for r in selected),
                         resolver_calls=sum(r['kind']=='resolver' for r in selected),input_tokens=sum(r['input_tokens'] for r in selected),
                         output_tokens=sum(r.get('output_tokens') or 0 for r in selected),latency_s=sum(r['latency_s'] for r in selected),
                         failed_backend_calls=sum(bool(r.get('error')) for r in selected),resolver_forward_passes=sum(r.get('forward_passes',0) for r in selected))
    return dict(total_calls=len(rows),by_stage=cost)


def verify_journal(units,tok,config,out,space):
    identity=plus.run_identity(units,config,space,tok)
    journal=plus.DPlusJournal(out,SimpleNamespace(tokenizer=tok),{**config,'official_labels':space['taxonomy_error']},identity)
    by={u['sample_id']:u for u in units}
    path=Path(out)/'results.private.json'
    if path.exists():
        rows=read_json(path)
        runner.require(len({r['sample_id'] for r in rows})==len(rows) and set(r['sample_id'] for r in rows)<=set(by),'checkpoint IDs corrupted')
        for r in rows:
            if r['stage1'] is not None:
                plus.validate_normalized(r['stage1']['findings'],by[r['sample_id']],space['taxonomy_error'])
                runner.require(r['stage1']['taxonomy_error']==plus.taxonomy(r['stage1']['findings'],space['taxonomy_error']),'checkpoint taxonomy corruption')
            if r['status']=='resolved':
                runner.require(r['stage1'] is not None and r['output']['taxonomy_error']==r['stage1']['taxonomy_error'],'resolved checkpoint corruption')
                plus.parse_feedback(json.dumps({'feedback':r['output']['feedback']}),r['level'])
    token_audit=[]
    for row in journal.rows.values():
        count=len(tok.apply_chat_template(row['messages'],tokenize=True,add_generation_prompt=True))
        cap=1 if row['stage']=='resolver' else config['findings_max_new_tokens'] if row['stage']=='taxonomy' else config['max_new_tokens']
        runner.require(count==row['input_tokens'] and count+cap<=config['context_limit'],'actual journal token/context corruption')
        token_audit.append(dict(key=row['key'],sample_id=row['sample_id'],stage=row['stage'],attempt=row['attempt'],input_tokens=count,output_allowance=cap))
    write_json(Path(out)/'actual-prompt-token-audit.json',dict(all_fit=True,calls=len(token_audit),context_limit=config['context_limit'],cases=token_audit))
    return identity


def verify_treatment(current,prior):
    # A freshly constructed freeze still has integer guidance keys; JSON files
    # necessarily have string object keys. Compare their exact persisted forms.
    for key in ('prompts','mapping','config'):
        runner.require(json.loads(json.dumps(current[key],ensure_ascii=False))==prior[key], 'inference treatment changed: '+key)
    return True


def restore_investigated_evidence(units,out,decision):
    """Resume preparation from unchanged cache after an explicit readiness audit.

    This does not reclassify a compiler state or repair source. The old helper
    has already compiled every unit and persisted all cache/audit records.
    """
    out=Path(out);audit=read_json(out/'compiler-audit.private.json')
    if decision.get('readiness')!='investigated_source_dependency' or decision.get('compiler_policy_changed') is not False or not decision.get('reason'):
        raise ExecutionIntegrityFailure('compiler readiness investigation is incomplete')
    approved={digest(x) for x in decision['approved_evidence']};rows={x['sample_id']:x for x in audit['samples']};enriched=[]
    for original in units:
        u=copy.deepcopy(original);row=rows[u['sample_id']];saved=read_json(out/'compiler-cache'/(row['cache_key']+'.json'))
        expected=compiler_evidence.cache_identity(u['task']['code'],row['standard'],audit['toolchain'],5)
        if saved['identity']!=expected or saved['result_sha256']!=digest(saved['result']) or row['source_sha256']!=compiler_evidence.source_sha(u['task']['code']):
            raise ExecutionIntegrityFailure('compiler cache/source binding corruption during investigated preparation')
        result=saved['result']
        if row['status']=='dependency_failure':
            binding=dict(source_sha256=row['source_sha256'],cache_key=row['cache_key'],toolchain_fingerprint=row['toolchain_fingerprint'],diagnostic_sha256=digest(result['diagnostic']))
            if digest(binding) not in approved:raise ExecutionIntegrityFailure('uninvestigated compiler dependency failure')
        elif row['status'] not in ('compiled','compile_error'):
            raise ExecutionIntegrityFailure('compiler infrastructure remains unavailable: '+row['status'])
        u['local_compiler']={k:v for k,v in row.items() if k not in ('sample_id','cache_hit')}
        u['source_catalog']=compiler_evidence.build_catalog(u['task']['code'],provided_compile_log=u['task'].get('compile_log'),local_compile_log=result.get('diagnostic'),test_report=u['task'].get('test_report'))
        u['source_map_version']=compiler_evidence.SOURCE_VERSION;enriched.append(u)
    stable_file(out/'enriched-inputs.private.json',dict(units=enriched,identity=digest(enriched)))
    write_json(out/'source-catalog.private.json',{u['sample_id']:u['source_catalog'] for u in enriched})
    stable_file(out/'compiler-readiness-investigation.json',decision)
    return enriched,audit


def prepare_phase(args,phase,out,tok,config,prior):
    out.mkdir(parents=True,exist_ok=True);out.chmod(0o700)
    cache=out/'compiler-cache';cache.mkdir(exist_ok=True)
    for source in (args.prior/'compiler-cache').glob('*.json'):
        target=cache/source.name
        if target.exists():runner.require(sha(target)==sha(source),'copied compiler cache drift')
        else:shutil.copyfile(source,target)
    units,space,requested=runner.prepare_inputs(SimpleNamespace(phase=phase,public_root=args.public_root,internal_root=args.internal_root,history=args.history),out)
    try:
        units,compiler_audit=compiler_evidence.prepare(units,out)
    except ValueError as exc:
        if str(exc)!='compiler prerequisite: non-student failure; see compiler-audit.private.json' or args.compiler_readiness is None:raise
        units,compiler_audit=restore_investigated_evidence(units,out,read_json(args.compiler_readiness))
    for u in units:plus.validate_unit(u)
    expected=30 if phase=='internal' else 328
    expected_levels={1:10,2:10,3:10} if phase=='internal' else {1:115,2:163,3:50}
    runner.require(len(units)==expected and dict(Counter(u['level'] for u in units))==expected_levels,'authoritative population/Level drift')
    if phase=='internal':
        runner.require(units==read_json(args.prior/'enriched-inputs.private.json')['units'],'prior internal frozen input/evidence mismatch')
        runner.require(read_json(out/'gold.private.json')==read_json(args.prior/'gold.private.json'),'prior internal gold mismatch')
    stable_file(out/'run-input-freeze.json',dict(enriched_inputs_sha256=digest(units),source_map_version=units[0]['source_map_version'],
                source_hashes={u['sample_id']:{k:d['sha256'] for k,d in u['source_catalog'].items()} for u in units},compiler_toolchain=compiler_audit['toolchain']))
    frozen=runner.freeze_method(out,config,space,tok,out/'method-freeze.json' if (out/'method-freeze.json').exists() else None)
    verify_treatment(frozen,prior)
    checks=[]
    for u in units:
        try:checks.append(runner.preflight([u],tok,config,space)['cases'][0])
        except ValueError as exc:
            if 'exceeds context' not in str(exc):raise
            checks.append(dict(sample_id=u['sample_id'],isolated_preflight_failure=str(exc),policy='record sample failure via unchanged per-call check; do not truncate'))
    stable_file(out/'preflight.json',dict(records=len(units),tokenizer=tokenizer_metadata(tok),cases=checks,minimum_renderer_is_not_future_actual_prompt_proof=True))
    bound={**config,'implementation_sha256':frozen['code_sha256']}
    verify_journal(units,tok,bound,out,space)
    return units,space,requested,bound,frozen


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--prior',type=Path,default=DEFAULT_PRIOR)
    p.add_argument('--config',type=Path,default=ROOT/'configs/task3/arm_d_plus_v15.json')
    p.add_argument('--public-root',type=Path,default=runner.BASE/'data/raw/public_test_release')
    p.add_argument('--internal-root',type=Path,default=runner.BASE/'data/synth/generate-dataset')
    p.add_argument('--history',type=Path,default=runner.HISTORY)
    p.add_argument('--resume',action='store_true');p.add_argument('--verify-only',action='store_true')
    p.add_argument('--compiler-readiness',type=Path,help='Hash-bound investigation of source dependency diagnostics; preserves compiler states/evidence')
    args=p.parse_args();out=args.out.resolve();args.prior=args.prior.resolve()
    runner.require(Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=ROOT,text=True).strip())==ROOT,'repository root mismatch')
    runner.require(subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='fix/task3-strict-feedback','required existing branch mismatch')
    runner.require(out.is_relative_to(ROOT) and out!=args.prior and not out.is_relative_to(args.prior),'new observation directory must be in same worktree outside historical output')
    runner.require(out.is_dir() if args.resume else not out.exists(),'use --resume for an existing observation directory')
    out.mkdir(parents=True,exist_ok=True);out.chmod(0o700)
    runner.plus=plus;runner.CONFIG=args.config.resolve();config=read_json(runner.CONFIG)
    prior=runner.verify_method(ROOT,args.prior/'method-freeze.json',config)
    os.environ.update(HF_HOME=str(runner.BASE/'outputs/task3/hf-cache'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    tok=load_tokenizer(config)
    policy=dict(version=POLICY_VERSION,user_authorization='2026-10-24 continuation: collect internal30 then public328 even when quality fails; no automatic submission',
                supersedes=['stop before internal30 on failed renderer quality','block public inference solely for internal F1/Level/diagnostic quality'],
                unchanged_config=config,quality_nonblocking=True,phases=['internal30','public328'],planned_passes_per_dataset=1,
                correction_per_invoked_stage=1,resolver_policy=config['resolver_passes_policy'],no_fixture_regeneration=True,
                infrastructure_integrity='stop affected run; journal/checkpoints preserved; recover same method and resume pending only',
                partial_policy='only complete exact-ID contract-valid output gets predictions.json; no padding or semantic quality-based suppression',
                no_tuning_or_submission=True,prior_references={n:dict(path=str(args.prior/n),sha256=sha(args.prior/n)) for n in
                    ['method-freeze.json','run-input-freeze.json','renderer-fixtures-freeze.json','renderer-eval/attempts.jsonl','renderer-eval/reviews.private.json','public-run-gate-policy.json','public-run-gate.json']},
                inference_treatment_identity=digest([config,prior['prompts'],prior['mapping'],{n:h for n,h in prior['code_sha256'].items() if n.startswith('src/')}]),
                compiler_readiness_investigation=None if args.compiler_readiness is None else dict(path=str(args.compiler_readiness.resolve()),sha256=sha(args.compiler_readiness)),
                changed_files={'scripts/task3_v15_observe.py':'new orchestration-only noninteractive observation entrypoint; frozen inference files unchanged'})
    policy['execution_policy_identity']=digest(policy);stable_file(out/'observation-policy.json',policy)
    prepared={phase:prepare_phase(args,phase,out/phase,tok,config,prior) for phase in ('internal','public')}
    public_units=prepared['public'][0]
    # Selection is fixed before any generation: one hashed-first ID per family,
    # union one per available Level, preserving original input order.
    selected=set()
    for field in ('family','level'):
        groups={u[field] for u in public_units}
        for group in groups:selected.add(min((u for u in public_units if u[field]==group),key=lambda u:digest(['public-content-review-v1',u['sample_id']]))['sample_id'])
    stable_file(out/'public-review-selection.json',dict(rule='SHA256(public-content-review-v1,sample_id) minimum per family union minimum per requested Level; selected before any model calls',
                ids=[u['sample_id'] for u in public_units if u['sample_id'] in selected],
                additional_cases='all structural failures; explicit L2 repair-operation signal; feedback main identifier absent from supplied findings',
                automated_flags_are_review_signals_not_factual_or_Level_proofs=True))
    cmd=[sys.executable,str(Path(__file__).resolve()),'--out',str(out),'--prior',str(args.prior),'--config',str(runner.CONFIG),
         '--public-root',str(args.public_root.resolve()),'--internal-root',str(args.internal_root.resolve()),'--history',str(args.history.resolve())]
    if args.compiler_readiness:cmd += ['--compiler-readiness',str(args.compiler_readiness.resolve())]
    write_json(out/'commands.json',dict(actual_invocation=shlex.join([*cmd,*(['--resume'] if args.resume else []),*(['--verify-only'] if args.verify_only else [])]),
                resume=shlex.join([*cmd,'--resume']),offline_verify=shlex.join([*cmd,'--resume','--verify-only'])))
    write_json(out/'execution-readiness.json',dict(integrity='passed',infrastructure='not_loaded',method_unchanged=True,policy_identity=policy['execution_policy_identity']))
    if not (out/'quality-assessment.json').exists():write_json(out/'quality-assessment.json',dict(prior_renderer='failed, joint3/8 (unchanged)',internal='pending',public='pending',blocks_measurement=False,acceptance_thresholds_unchanged=True))
    if args.verify_only:
        print(json.dumps(dict(verified=True,internal=30,public=328,model_loaded=False)));return 0
    free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()
    runner.require(len(free)==1 and int(free[0])>=config['minimum_free_gpu_mib'],'CUDA prerequisites/free memory unavailable')
    started=time.perf_counter();backend=None;completed=[]
    try:
        backend=runner.DPlusBackend(config,tok,out)
        write_json(out/'runtime-before.json',backend.runtime_metadata())
        write_json(out/'config.resolved.json',dict(requested=config,tokenizer=tokenizer_metadata(tok),runtime=backend.runtime_metadata(),
                   generation={stage:read_json(out/f'generation-{stage}.json') for stage in ('taxonomy','feedback')},
                   inference_treatment_identity=policy['inference_treatment_identity'],execution_policy_identity=policy['execution_policy_identity']))
        for phase in ('internal','public'):
            units,space,requested,bound,frozen=prepared[phase];phase_out=out/phase
            before=stage_costs(phase_out)['total_calls'];phase_started=time.perf_counter()
            execution_allowed({'integrity':'passed','infrastructure':'ready'},read_json(out/'quality-assessment.json'),phase)
            results=observe_phase(units,backend,bound,phase_out,space)
            validation=export_phase(phase_out,results,requested,space['taxonomy_error'])
            runtime=backend.runtime_metadata();write_json(phase_out/'runtime-after.json',runtime)
            summary=dict(phase=phase,counts=phase_counts(results),submission_readiness=validation,
                         quality='requires separate review; schema-valid low-quality outputs retained',costs=stage_costs(phase_out),
                         newly_generated_calls=stage_costs(phase_out)['total_calls']-before,replayed_prior_call_rows=before,
                         elapsed_phase_s=time.perf_counter()-phase_started,runtime=runtime)
            write_json(phase_out/'observation-summary.json',summary)
            verify_journal(units,tok,bound,phase_out,space)
            runner.verify_method(ROOT,phase_out/'method-freeze.json',config)
            completed.append(phase)
            print(json.dumps(dict(phase=phase,**summary['counts'],export_complete=validation['passed']),ensure_ascii=False),flush=True)
        write_json(out/'execution-readiness.json',dict(integrity='passed',infrastructure='completed',completed_phases=completed,quality_is_acceptance_not_execution_permission=True))
    except Exception as exc:
        write_json(out/'execution-failure.json',dict(type=type(exc).__name__,reason=str(exc),completed_phases=completed,policy='stop infrastructure/integrity; no new content retries'))
        raise
    finally:
        try:
            if backend is not None:capture_runtime(backend,out/'runtime-after.json')
        finally:
            append(out/'invocations.jsonl',dict(elapsed_s=time.perf_counter()-started,model_loads=1 if backend is not None else 0,
                        load_latency_s=backend.load_latency_s if backend is not None else None,resume=args.resume,completed_phases=completed,
                        review_pause_s=0,prior_fixture_calls_reused=27,new_fixture_calls=0))
    return 0


if __name__=='__main__':sys.exit(main())
