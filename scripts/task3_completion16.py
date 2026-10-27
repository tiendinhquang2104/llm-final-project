#!/usr/bin/env python3
"""Targeted completion of selected A's unresolved population; no historical writes."""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3 import completion16 as c,arm_d_plus_v16 as v16,arm_d_plus_v15 as old
from src.task3 import recovery_candidates as candidates,finite_choice
from src.task3.dataset import read_json,write_json
from src.task3.level_blind import digest,sha
from src.task3.inference import load_tokenizer,tokenizer_metadata
from src.task3.two_pass import append
from src.task3.v16_experiment import jsonl,stable
from src.task3.submission import validate_submission
from scripts.task3_arm_d_plus import DPlusBackend,validate_export

PRIOR=ROOT/'outputs/task3/v1.6-json-transport-grounded'
OUT=ROOT/'outputs/task3/v1.6-completion16-20261024'


def require(ok,reason):
    if not ok:raise ValueError(reason)


def prepare(prior,out):
    units=read_json(prior/'inputs/public.private.json');by={u['sample_id']:u for u in units}
    baseline=read_json(prior/'public/partial.predictions.json');unresolved=read_json(prior/'public/unresolved.private.json')
    results=read_json(prior/'public/results.private.json');requested=read_json(prior/'inputs/public-requested-levels.private.json')
    space=read_json(prior/'inputs/label-space.private.json');config=read_json(prior/'config.json')
    require(read_json(prior/'selection.json')['selected']=='A','selected arm must remain A')
    require(len(baseline)==312 and len(unresolved)==16 and len(results)==328,'original population changed')
    good_ids=[r['sample_id'] for r in baseline];bad_ids=[r['sample_id'] for r in unresolved]
    require(len(set(good_ids))==312 and len(set(bad_ids))==16 and not set(good_ids)&set(bad_ids) and set(good_ids+bad_ids)==set(requested)==set(by),'exact disjoint population mismatch')
    require(Counter(by[s]['level'] for s in good_ids)=={1:112,2:151,3:49} and Counter(by[s]['level'] for s in bad_ids)=={1:3,2:12,3:1},'authoritative Level distribution mismatch')
    for u in units:
        require(requested[u['sample_id']]==old.v14.FEEDBACK_LEVELS[u['level']-1],'requested Level mapping changed')
    require([r for r in results if r['status']=='unresolved']==unresolved,'historical unresolved/results disagree')
    require([dict(sample_id=r['sample_id'],output=r['output']) for r in results if r['status']=='resolved']==baseline,'baseline/results disagree')
    # Verify schemas on their own authoritative ordered subset, without pretending312 is complete328.
    validate_submission(prior/'public/partial.predictions.json',{sid:requested[sid] for sid in good_ids})
    oldfreeze=read_json(prior/'method-freeze.json')
    for n,h in oldfreeze['code_sha256'].items():require(sha(ROOT/n)==h,'original selected implementation drift: '+n)
    hashes={r['sample_id']:c.object_hash(r['output']) for r in baseline}
    stable(out/'baseline312-hashes.private.json',dict(serialization='UTF-8 JSON, ensure_ascii=False, sort_keys=True, separators=(comma,colon), allow_nan=False; hash of output object',
        original_file_sha256=sha(prior/'public/partial.predictions.json'),output_sha256=hashes))
    stable(out/'inputs.private.json',[by[s] for s in bad_ids]);stable(out/'requested-levels.private.json',requested)
    stable(out/'label-space.private.json',space);stable(out/'config.json',config)
    if not (out/'historical-run-manifest.private.json').exists():
        write_json(out/'historical-run-manifest.private.json',{str(p.relative_to(prior)):sha(p) for p in sorted(prior.rglob('*')) if p.is_file()})
    rows=jsonl(prior/'public/attempts.jsonl');manifest=[]
    for historical in unresolved:
        sid=historical['sample_id'];u=by[sid];old.validate_unit(u)
        attempts=[(i+1,r) for i,r in enumerate(rows) if r['sample_id']==sid and r['stage']=='taxonomy']
        require(bool(attempts),'missing final recorded detector attempt')
        index,row=attempts[-1]
        require(row['prompt_sha256']==digest(row['messages']),'historical prompt binding mismatch')
        view_path=prior/'public/views'/(digest([sid,'taxonomy',row['attempt']])+'.json')
        view=read_json(view_path)
        inv=c.inventory(row,u,view);scopes=c.build_scopes(u) if inv['route']!='fields' else []
        kind=sum(v['field']=='kind' for v in inv['violations']);reference=sum(v['field']=='reference' for v in inv['violations'])
        group='length' if inv['route']=='length' else 'kind' if kind else 'reference'
        possible_reassess=old.task_payload(u)['problem_ids'] if scopes else sorted({inv['findings'][v['finding_index']]['problem_id'] for v in inv['violations']})
        slots=max(16,2*len(inv['findings'] or []))
        generated=len(scopes)+len(possible_reassess)
        taxonomy_slots=max(sum(len(f['labels']) for f in inv['findings'] or []),2*slots*generated)
        budget=dict(initial_kind=kind,initial_bad_reference_fields=reference,generated_field_slots=slots,
            kind_choices=kind+slots*generated,reference_choices=2*(reference+slots*generated),
            length_generations=2*len(scopes),reassessment_generations=len(possible_reassess),taxonomy_resolvers=taxonomy_slots,
            renderer_generations=0 if u['level']==1 else 2,
            policy='Upper ceilings, not finding caps. No finding is dropped on exhaustion; its scope remains unresolved. Each invalid kind once, refs max2 pages, reassessment once per affected problem, no recursion.')
        budget['total_calls']=sum(budget[k] for k in ('kind_choices','reference_choices','length_generations','reassessment_generations','taxonomy_resolvers','renderer_generations'))
        catalog=candidates.build_catalog(u)
        stable(out/'catalogs'/f'{sid}.private.json',catalog)
        stable(out/'original-attempts'/f'{sid}.json',dict(original_run=str(prior),journal_row=index,row=row,original_view=view,inventory=inv,historical_failure=historical))
        raw=out/'original-attempts'/f'{sid}.raw.txt'
        if raw.exists():require(raw.read_bytes()==row['raw_text'].encode('utf-8'),'raw copy drift')
        else:raw.write_bytes(row['raw_text'].encode('utf-8'))
        manifest.append(dict(sample_id=sid,level=u['level'],group=group,input_sha256=c.object_hash(u),
            source_hashes={s:d['sha256'] for s,d in u['source_catalog'].items()},raw_sha256=c.refs.source_sha(row['raw_text']),
            original_run=str(prior),original_journal_row=index,original_key=row['key'],original_prompt_sha256=row['prompt_sha256'],
            original_view_sha256=sha(view_path),inventory=inv,candidates_sha256=c.object_hash(catalog),scopes=scopes,
            reassessment_problem_ids=possible_reassess,budget=budget))
    require(Counter(m['group'] for m in manifest)=={'kind':6,'reference':7,'length':3},'actual failure groups differ; inspect before inference')
    stable(out/'recovery-manifest.private.json',manifest)
    return [by[s] for s in bad_ids],space,config,manifest,baseline,requested


def preflight(out,units,space,config,manifest,tok):
    checks=[]
    for code_count in (3,17):finite_choice.choice_token_ids(tok,[chr(65+i) for i in range(code_count)])
    for u,m in zip(units,manifest):
        cat=read_json(out/'catalogs'/f'{u["sample_id"]}.private.json');probes=[]
        for v in m['inventory']['violations']:
            f=m['inventory']['findings'][v['finding_index']]
            if v['field']=='kind':probes.append(('kind',c.selector_messages(u,f,dict(A='defect',B='omission',C=None),'kind')))
            elif v['field']=='reference':
                ranked=candidates.rank_candidates(cat,f,u)
                for pi in (0,1):
                    page=candidates.page_candidates(ranked,pi);choices={chr(65+i):z['candidate_id'] for i,z in enumerate(page)};choices[chr(65+len(page))]=None
                    probes.append(('reference',c.selector_messages(u,f,choices,'reference',page)))
        # All frozen length scope initial prompts and potential reassessment prompts are measured.
        for scope in m['scopes']+[dict(scope_id='reassess:'+pid,problem_ids=[pid],focus='Reassess prior unresolved claims') for pid in m['reassessment_problem_ids']]:
            messages=v16.messages_findings(u,space['taxonomy_error'],'A');messages[0]['content']+='\n\n'+c.SCOPE_INSTRUCTION+c.REASSESS_INSTRUCTION
            body=json.loads(messages[1]['content']);body['recovery_scope']=scope;body['problem_ids']=scope['problem_ids'];body['unresolved_prior_claims']=m['inventory']['findings'] or []
            messages[1]['content']=json.dumps(body,ensure_ascii=False);probes.append(('scope',messages))
        probes.append(('feedback',v16.messages_feedback(u,[],space['taxonomy_error'],space['feedback_level'])))
        for kind,messages in probes:
            cap=1 if kind in ('kind','reference') else config['max_new_tokens'] if kind=='feedback' else config['findings_max_new_tokens']
            if kind!='reference':messages,view=c.dv.prepare_messages(u,messages,tok,cap,config['context_limit'])
            n=len(tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True))
            require(n+cap<=config['context_limit'],'planned prompt overflow: '+u['sample_id'])
            checks.append(dict(sample_id=u['sample_id'],kind=kind,input_tokens=n,allowance=cap,prompt_sha256=digest(messages)))
    sources=[ROOT/n for n in ('src/task3/completion16.py','src/task3/finite_choice.py','src/task3/recovery_candidates.py','scripts/task3_completion16.py',
        'src/task3/arm_d_plus.py','src/task3/arm_d_plus_v15.py','src/task3/arm_d_plus_v16.py','src/task3/diagnostic_view.py','src/task3/source_refs.py','src/task3/json_transport.py','src/task3/inference.py','src/task3/language_precision_ablation.py','scripts/task3_arm_d_plus.py')]
    freeze=dict(version=c.VERSION,config=config,label_space=space,tokenizer=tokenizer_metadata(tok),
        original_run=str(PRIOR),original_method_sha256=sha(PRIOR/'method-freeze.json'),baseline_hashes_sha256=sha(out/'baseline312-hashes.private.json'),
        manifest_sha256=sha(out/'recovery-manifest.private.json'),code_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},
        prompts=dict(kind=c.KIND_SYSTEM,reference=c.REF_SYSTEM,scope=c.SCOPE_INSTRUCTION,reassessment=c.REASSESS_INSTRUCTION,
            arm_A=old.FINDINGS_SYSTEM,level2=v16.LEVEL2_SYSTEM,other_feedback=old.FEEDBACK_SYSTEM),
        policy=dict(reference_page_size=16,reference_pages=2,invalid_kind_decisions=1,scoped_followups=1,reassessment_per_problem=1,
            recursive_reassessment=False,baseline312_immutable=True,selected_arm='A',quality_nonblocking=True,
            duplicate_policy='canonical exact whole-finding equality only',candidate_version=candidates.VERSION,selector_version=finite_choice.VERSION))
    stable(out/'method-freeze.json',freeze);stable(out/'preflight.json',dict(all_fit=True,model_loaded=False,cases=checks))
    for n in freeze['code_sha256']:
        path=out/'frozen-code'/n
        if not path.exists():path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,path)
        require(sha(path)==freeze['code_sha256'][n],'frozen code mismatch')
    return {**config,'official_labels':space['taxonomy_error'],'implementation_identity':digest(freeze)}


def export(out,prior,baseline,requested):
    results=read_json(out/'results.private.json');new=[dict(sample_id=r['sample_id'],output=r['output']) for r in results if r['status']=='resolved']
    write_json(out/'recovered.predictions.json',new)
    h=read_json(out/'baseline312-hashes.private.json');merged=c.merge_outputs(baseline,new,list(requested),h['output_sha256'])
    write_json(out/'partial.predictions.json',merged);write_json(out/'unresolved.private.json',[r for r in results if r['status']!='resolved'])
    try:validation=validate_export(out,requested,read_json(out/'label-space.private.json')['taxonomy_error'])
    except ValueError:validation=read_json(out/'validation.json')
    preserved=all(c.object_hash(next(r['output'] for r in merged if r['sample_id']==sid))==value for sid,value in h['output_sha256'].items())
    require(preserved and sha(prior/'public/partial.predictions.json')==h['original_file_sha256'],'original312 preservation failed')
    write_json(out/'baseline312-preservation.json',dict(passed=preserved,checked=312,serialization=h['serialization'],original_file_sha256=h['original_file_sha256'],
        merged_file_sha256=sha(out/('predictions.json' if validation['passed'] else 'partial.predictions.json'))))
    return validation


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['inventory','preflight','run','verify'],required=True)
    parser.add_argument('--out',type=Path,default=OUT);parser.add_argument('--prior',type=Path,default=PRIOR)
    args=parser.parse_args();out=args.out.resolve();prior=args.prior.resolve()
    require(Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=ROOT,text=True).strip())==ROOT,'root mismatch')
    require(subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='fix/task3-strict-feedback','branch mismatch')
    require(out.is_relative_to(ROOT/'outputs') and not out.is_relative_to(prior),'separate output required')
    out.mkdir(parents=True,exist_ok=True);out.chmod(0o700)
    if not (out/'initial-state.json').exists():write_json(out/'initial-state.json',dict(root=str(ROOT),branch='fix/task3-strict-feedback',HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        status=subprocess.check_output(['git','status','--short'],text=True),initial_user_turn_status='clean before helper/coordinator implementation'))
    units,space,config,manifest,baseline,requested=prepare(prior,out)
    if args.mode=='inventory':print(json.dumps(dict(cases=len(manifest),groups=dict(Counter(m['group'] for m in manifest)),invalid_fields={m['sample_id']:len(m['inventory']['violations']) for m in manifest}),ensure_ascii=False));return
    os.environ.update(HF_HOME='/workspace/llm-final-project/outputs/task3/hf-cache',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    tok=load_tokenizer(config);bound=preflight(out,units,space,config,manifest,tok)
    stable(out/'commands.json',{mode:f'{sys.executable} {Path(__file__).resolve()} --mode {mode}' for mode in ('inventory','preflight','run','verify')})
    if args.mode=='preflight':print('PREFLIGHT_PASSED_NO_MODEL_LOAD');return
    if args.mode=='verify':
        rows=jsonl(out/'attempts.jsonl');reservations=jsonl(out/'reservations.jsonl')
        require(len(rows)==len(reservations)==len({r['key'] for r in rows}),'incomplete/duplicate journal')
        for r in rows:
            n=len(tok.apply_chat_template(r['messages'],tokenize=True,add_generation_prompt=True));cap=1 if r['stage']=='resolver' else config['max_new_tokens'] if r['stage']=='feedback' else config['findings_max_new_tokens']
            require(n==r['input_tokens'] and n+cap<=config['context_limit'] and digest(r['messages'])==r['prompt_sha256'],'actual prompt integrity mismatch')
        for m in manifest:require(sum(r['sample_id']==m['sample_id'] for r in rows)<=m['budget']['total_calls'],'case budget exceeded')
        historical=read_json(out/'historical-run-manifest.private.json');require(all((prior/n).is_file() and sha(prior/n)==h for n,h in historical.items()),'historical v1.6 artifact drift')
        validation=export(out,prior,baseline,requested)
        write_json(out/'verification.json',dict(passed=True,journal_rows=len(rows),historical_files_unchanged=len(historical),baseline312_preserved=True,export=validation))
        print(json.dumps(read_json(out/'verification.json')));return
    backend=None;started=time.perf_counter();budgets={m['sample_id']:m['budget'] for m in manifest}
    try:
        backend=DPlusBackend(config,tok,out);append(out/'model-loads.jsonl',backend.runtime_metadata())
        journal=c.RecoveryJournal(out,c.BackendAdapter(backend),bound,digest([bound,manifest]),budgets)
        previous=read_json(out/'results.private.json') if (out/'results.private.json').exists() else []
        by={r['sample_id']:r for r in previous};results=[]
        require(len(by)==len(previous) and set(by)<={m['sample_id'] for m in manifest},'recovery checkpoint population mismatch')
        for u,m in zip(units,manifest):
            sid=u['sample_id'];saved=by.get(sid)
            if saved and saved.get('terminal'):
                if saved.get('stage1'):old.validate_normalized(saved['stage1']['findings'],u,space['taxonomy_error'])
                results.append(saved);continue
            result=saved or dict(sample_id=sid,level=u['level'],group=m['group'],lineage='v1.6 A with targeted recovery',status='unresolved',stage1=None,output=None,terminal=False,
                original_provenance={k:m[k] for k in ('original_run','original_journal_row','original_key','raw_sha256','input_sha256')})
            results.append(result);recover=c.Recoverer(u,journal,read_json(out/'catalogs'/f'{sid}.private.json'),space['taxonomy_error'],m)
            stage='detector'
            try:
                if result['stage1'] is None:
                    original=read_json(out/'original-attempts'/f'{sid}.json')
                    stage1,mapping=recover.detector(original['row'],original['original_view'])
                    result.update(stage1=stage1,mapping_audit=mapping,field_decisions=recover.events,scope_ledger=recover.ledger)
                    write_json(out/'results.private.json',results)
                stage='feedback'
                if u['level']==1:feedback=old.LEVEL1_FEEDBACK[bool(result['stage1']['findings'])]
                else:feedback=v16.schema_stage(journal,sid,'feedback',v16.messages_feedback(u,result['stage1']['findings'],space['taxonomy_error'],space['feedback_level']),u)
                result.update(status='resolved',output=dict(taxonomy_error=result['stage1']['taxonomy_error'],feedback=feedback),failure=None,terminal=True)
            except (ValueError,TypeError,KeyError) as exc:
                infrastructure=getattr(exc,'category',None)=='infrastructure'
                result.update(failure=dict(stage=stage,**v16.failure_record(exc)),terminal=not infrastructure)
                if stage=='detector':result.update(field_decisions=recover.events,scope_ledger=recover.ledger)
                if getattr(exc,'category',None)=='infrastructure':write_json(out/'results.private.json',results);raise
            write_json(out/'results.private.json',results)
            write_json(out/'derived-findings'/f'{sid}.json',dict(derived=True,result=result))
            print(json.dumps(dict(sample_id=sid,processed=len(results),status=result['status'],failure=result.get('failure')),ensure_ascii=False),flush=True)
        print(json.dumps(export(out,prior,baseline,requested),ensure_ascii=False),flush=True)
    finally:
        if backend is not None:write_json(out/'runtime-after.json',backend.runtime_metadata())
        rows=jsonl(out/'attempts.jsonl');write_json(out/'costs-and-runtime.json',dict(model_loads=jsonl(out/'model-loads.jsonl'),process_elapsed_s=time.perf_counter()-started,
            total_calls=len(rows),selector_forward_passes=sum(r['stage']=='resolver' for r in rows),text_generations=sum(r['stage']!='resolver' for r in rows),
            input_tokens=sum(r['input_tokens'] for r in rows),output_tokens=sum(r.get('output_tokens') or 0 for r in rows),call_latency_s=sum(r['latency_s'] for r in rows),historical_cost_not_new=True,
            by_stage={stage:dict(calls=sum(r['stage']==stage for r in rows),input_tokens=sum(r['input_tokens'] for r in rows if r['stage']==stage),output_tokens=sum(r.get('output_tokens') or 0 for r in rows if r['stage']==stage),latency_s=sum(r['latency_s'] for r in rows if r['stage']==stage)) for stage in ('taxonomy','resolver','feedback')}))


if __name__=='__main__':main()
