#!/usr/bin/env python3
"""Finish one remaining case under a new identity; preserve prior outputs/files."""
from __future__ import annotations
import argparse,copy,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3 import completion16 as c,completion1 as focused,finite_choice
from src.task3.dataset import read_json,write_json
from src.task3.level_blind import digest,sha
from src.task3.inference import load_tokenizer,tokenizer_metadata
from src.task3.v16_experiment import stable,jsonl
from src.task3.submission import validate_submission
from src.task3.two_pass import append
from scripts.task3_arm_d_plus import DPlusBackend
PRIOR=ROOT/'outputs/task3/v1.6-completion16-20261024'
OUT=ROOT/'outputs/task3/v1.6-completion1-20261024'


def require(ok,message):
    if not ok:raise ValueError(message)


def prepare(out):
    baseline=read_json(PRIOR/'partial.predictions.json');unresolved=read_json(PRIOR/'unresolved.private.json')
    requested=read_json(PRIOR/'requested-levels.private.json');config=read_json(PRIOR/'config.json');space=read_json(PRIOR/'label-space.private.json')
    require(len(baseline)==327 and len(unresolved)==1 and len(requested)==328,'expected exact327+1 population')
    sid=unresolved[0]['sample_id'];u=next(u for u in read_json(PRIOR/'inputs.private.json') if u['sample_id']==sid)
    c.old.validate_unit(u);require(requested[sid]==c.old.v14.FEEDBACK_LEVELS[u['level']-1],'authoritative Level mismatch')
    ids=[r['sample_id'] for r in baseline]
    require(len(set(ids))==327 and set(ids)|{sid}==set(requested) and sid not in ids,'population/duplicate mismatch')
    validate_submission(PRIOR/'partial.predictions.json',{s:v for s,v in requested.items() if s!=sid})
    previous_freeze=read_json(PRIOR/'method-freeze.json')
    for name,h in previous_freeze['code_sha256'].items():require(sha(ROOT/name)==h,'previous frozen implementation drift: '+name)
    stable(out/'baseline327-hashes.private.json',dict(serialization='SHA256 of completion16.canonical(output), UTF-8 ensure_ascii=False sorted keys compact separators allow_nan=False',
        original_file_sha256=sha(PRIOR/'partial.predictions.json'),output_sha256={r['sample_id']:c.object_hash(r['output']) for r in baseline}))
    for name,value in [('input.private.json',u),('requested-levels.private.json',requested),('label-space.private.json',space),('config.json',config)]:stable(out/name,value)
    if not(out/'prior-files.private.json').exists():write_json(out/'prior-files.private.json',{str(p.relative_to(PRIOR)):sha(p) for p in sorted(PRIOR.rglob('*')) if p.is_file()})
    rows={r['key']:r for r in jsonl(PRIOR/'attempts.jsonl')};scopes=c.build_scopes(u);reused={}
    for entry in unresolved[0]['scope_ledger']:
        if entry['status']!='valid':continue
        row=rows[entry['journal_key']];inv=c.inventory(row,u)
        require(inv['route']=='fields' and not inv['violations'] and inv['findings']==entry['findings'],'invalid reusable scope')
        require(digest(row['messages'])==row['prompt_sha256'],'reused prompt hash mismatch')
        audit=read_json(PRIOR/'generations'/(digest([sid,entry['purpose'],entry['scope']['scope_id'],row['attempt']])+'.audit.json'))
        c.dv.validate_presented_refs(entry['findings'],audit['view'],u)
        reused[entry['scope']['scope_id']]={**entry,'prior_run':str(PRIOR),'prior_prompt_sha256':row['prompt_sha256'],'prior_raw_sha256':c.refs.source_sha(row['raw_text'])}
    pending=[s for s in scopes if s['scope_id'] not in reused]
    require(len(reused)==2 and len(pending)==3 and all(len(s['problem_ids'])==1 for s in pending),'unexpected pending coverage')
    stable(out/'reused-scopes.private.json',reused)
    catalog=read_json(PRIOR/'catalogs'/f'{sid}.private.json');stable(out/'catalog.private.json',catalog)
    original=read_json(PRIOR/'original-attempts'/f'{sid}.json');stable(out/'original-attempt.private.json',original)
    n=len(pending);slots=16;generated=n*2
    budget=dict(length_generations=2*n,reassessment_generations=n,renderer_generations=2,
        generated_field_slots=slots,kind_choices=slots*generated,reference_choices=2*slots*generated,taxonomy_resolvers=2*slots*generated)
    budget['total_calls']=sum(v for k,v in budget.items() if k!='generated_field_slots')
    manifest=dict(sample_id=sid,level=u['level'],selected_arm='A',input_sha256=c.object_hash(u),
        source_hashes={s:d['sha256'] for s,d in u['source_catalog'].items()},prior_run=str(PRIOR),prior_unresolved_sha256=sha(PRIOR/'unresolved.private.json'),
        scopes=scopes,pending_scopes=pending,reused_scope_hashes={s:c.object_hash(e) for s,e in reused.items()},candidates_sha256=c.object_hash(catalog),budget=budget,
        policy='Active requirement/prototypes separated from verbatim background. Full source/logs retained; no filtering/remapping of out-of-scope model findings. Existing valid P1/integration reused unchanged. Field ceilings do not delete findings. One reassessment/problem, no recursion; max2 text calls/pending scope and renderer.')
    stable(out/'recovery-manifest.private.json',manifest)
    return u,baseline,requested,config,space,manifest,reused,catalog,original


def preflight(out,u,config,space,manifest,tok):
    checks=[]
    for n in (3,17):finite_choice.choice_token_ids(tok,[chr(65+i) for i in range(n)])
    for scope in manifest['pending_scopes']:
        messages=c.v16.messages_findings(u,space['taxonomy_error'],'A');messages[0]['content']+='\n\n'+c.SCOPE_INSTRUCTION
        body=json.loads(messages[1]['content']);body['recovery_scope']=scope;messages[1]['content']=json.dumps(body,ensure_ascii=False)
        messages=focused.focus_messages(messages,u)
        messages,view=c.dv.prepare_messages(u,messages,tok,config['findings_max_new_tokens'],config['context_limit'])
        checks.append(dict(scope=scope,prompt_sha256=digest(messages),input_tokens=len(tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)),allowance=config['findings_max_new_tokens'],view=view))
    sources=list(read_json(PRIOR/'method-freeze.json')['code_sha256'])+['src/task3/completion1.py','scripts/task3_completion1.py']
    freeze=dict(version=focused.VERSION,selected_arm='A',config=config,label_space=space,tokenizer=tokenizer_metadata(tok),
        manifest_sha256=sha(out/'recovery-manifest.private.json'),baseline_sha256=sha(out/'baseline327-hashes.private.json'),
        original_method_sha256=sha(PRIOR/'method-freeze.json'),code_sha256={n:sha(ROOT/n) for n in sources},focus_rule=focused.FOCUS_RULE)
    stable(out/'method-freeze.json',freeze);stable(out/'preflight.json',dict(model_loaded=False,planned=checks,all_fit=all(r['input_tokens']+r['allowance']<=config['context_limit'] for r in checks)))
    require(read_json(out/'preflight.json')['all_fit'],'preflight overflow')
    for n,h in freeze['code_sha256'].items():
        target=out/'frozen-code'/n
        if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,target)
        require(sha(target)==h,'frozen code drift')
    return {**config,'official_labels':space['taxonomy_error'],'implementation_identity':digest(freeze)}


def export(out,baseline,requested):
    result=read_json(out/'result.private.json');new=[dict(sample_id=result['sample_id'],output=result['output'])] if result['status']=='resolved' else []
    write_json(out/'recovered.predictions.json',new)
    hashes=read_json(out/'baseline327-hashes.private.json');merged=c.merge_outputs(baseline,new,list(requested),hashes['output_sha256'])
    write_json(out/'partial.predictions.json',merged)
    preserved=all(c.object_hash(next(r['output'] for r in merged if r['sample_id']==sid))==h for sid,h in hashes['output_sha256'].items())
    require(preserved and sha(PRIOR/'partial.predictions.json')==hashes['original_file_sha256'],'baseline327 changed')
    validation=dict(expected=328,completed=len(merged),passed=False)
    try:
        focused.complete_merge(baseline,new,list(requested),hashes['output_sha256'])
        valid=validate_submission(out/'partial.predictions.json',requested)
        validation.update(passed=True,**valid)
    except ValueError as exc:validation['error']=str(exc)
    # Complete filename is emitted only after both preservation and official validation.
    if validation['passed']:write_json(out/'predictions.json',merged)
    write_json(out/'validation.json',validation);write_json(out/'unresolved.private.json',[] if new else [result])
    write_json(out/'baseline327-preservation.json',dict(passed=preserved,checked=327,baseline_file_sha256=hashes['original_file_sha256'],merged_file_sha256=sha(out/('predictions.json' if validation['passed'] else 'partial.predictions.json'))))
    return validation


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=['inventory','preflight','run','verify'],required=True)
    args=parser.parse_args();out=OUT
    require(Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip())==ROOT,'root mismatch')
    require(subprocess.check_output(['git','branch','--show-current'],text=True).strip()=='fix/task3-strict-feedback','branch mismatch')
    out.mkdir(parents=True,exist_ok=True);out.chmod(0o700)
    if not(out/'initial-state.json').exists():write_json(out/'initial-state.json',dict(root=str(ROOT),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),status=subprocess.check_output(['git','status','--short'],text=True),user_request='xử lý nốt Class01-Test1-S09'))
    u,baseline,requested,config,space,manifest,reused,catalog,original=prepare(out)
    if args.mode=='inventory':print(json.dumps(manifest,ensure_ascii=False));return
    os.environ.update(HF_HOME='/workspace/llm-final-project/outputs/task3/hf-cache',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    tok=load_tokenizer(config);bound=preflight(out,u,config,space,manifest,tok);identity=digest([bound,manifest])
    stable(out/'commands.json',{mode:f'{sys.executable} {Path(__file__).resolve()} --mode {mode}' for mode in ('inventory','preflight','run','verify')})
    if args.mode=='preflight':print('PREFLIGHT_PASSED_NO_MODEL_LOAD');return
    if args.mode=='verify':
        rows=jsonl(out/'attempts.jsonl');reservations=jsonl(out/'reservations.jsonl')
        require(len(rows)==len(reservations)==len({r['key'] for r in rows}),'journal count mismatch')
        require(len(rows)<=manifest['budget']['total_calls'] and {r['sample_id'] for r in rows}=={u['sample_id']},'budget/population mismatch')
        for r in rows:
            n=len(tok.apply_chat_template(r['messages'],tokenize=True,add_generation_prompt=True));cap=1 if r['stage']=='resolver' else config['max_new_tokens'] if r['stage']=='feedback' else config['findings_max_new_tokens']
            require(n==r['input_tokens'] and digest(r['messages'])==r['prompt_sha256'] and n+cap<=config['context_limit'],'actual prompt integrity mismatch')
        historical=read_json(out/'prior-files.private.json')
        require(all((PRIOR/n).is_file() and sha(PRIOR/n)==h for n,h in historical.items()),'previous completion16 files changed')
        priorroot=Path(read_json(PRIOR/'recovery-manifest.private.json')[0]['original_run'])
        originalhashes=read_json(PRIOR/'historical-run-manifest.private.json')
        require(all((priorroot/n).is_file() and sha(priorroot/n)==h for n,h in originalhashes.items()),'original v1.6 files changed')
        validation=export(out,baseline,requested)
        class NoModel:
            def __getattr__(self,name):raise AssertionError('offline replay touched backend: '+name)
        journal=c.RecoveryJournal(out,NoModel(),bound,identity,{u['sample_id']:manifest['budget']})
        before={n:sha(out/n) for n in ('attempts.jsonl','reservations.jsonl','model-loads.jsonl')}
        for row in rows:require(journal.call(row['sample_id'],row['stage'],row['messages'],row['attempt'],row['resolver_id'])==row,'cached replay mismatch')
        require(before=={n:sha(out/n) for n in before},'cached replay wrote model/journal')
        write_json(out/'verification.json',dict(passed=validation['passed'],export=validation,baseline327_unchanged=True,prior_files_unchanged=len(historical),original_v16_files_unchanged=len(originalhashes),cached_replay_rows=len(rows),new_model_calls_during_replay=0))
        print(json.dumps(read_json(out/'verification.json')));return
    if (out/'result.private.json').exists() and read_json(out/'result.private.json').get('terminal'):
        print(json.dumps(export(out,baseline,requested)));return
    result=read_json(out/'result.private.json') if (out/'result.private.json').exists() else dict(sample_id=u['sample_id'],level=u['level'],status='unresolved',stage1=None,output=None,terminal=False,lineage='v1.6 A with completion16 and active-problem targeted recovery')
    backend=None;started=time.perf_counter();stage='detector';recover=None
    try:
        backend=DPlusBackend(config,tok,out);append(out/'model-loads.jsonl',backend.runtime_metadata())
        journal=c.RecoveryJournal(out,c.BackendAdapter(backend),bound,identity,{u['sample_id']:manifest['budget']})
        recover=focused.FocusedRecoverer(u,journal,catalog,space['taxonomy_error'],manifest,reused=reused)
        if result['stage1'] is None:
            stage1,mapping=recover.detector(original['row'],original['original_view'])
            result.update(stage1=stage1,mapping_audit=mapping,field_decisions=recover.events,scope_ledger=recover.ledger)
            write_json(out/'result.private.json',result)
        stage='feedback'
        feedback=c.v16.schema_stage(journal,u['sample_id'],'feedback',c.v16.messages_feedback(u,result['stage1']['findings'],space['taxonomy_error'],space['feedback_level']),u)
        result.update(output=dict(taxonomy_error=result['stage1']['taxonomy_error'],feedback=feedback),status='resolved',terminal=True,failure=None)
    except (ValueError,TypeError,KeyError) as exc:
        result.update(failure=dict(stage=stage,**c.v16.failure_record(exc)),terminal=getattr(exc,'category',None)!='infrastructure')
        if stage=='detector' and recover is not None:result.update(field_decisions=recover.events,scope_ledger=recover.ledger)
        write_json(out/'result.private.json',result)
        if getattr(exc,'category',None)=='infrastructure':raise
    finally:
        if backend is not None:write_json(out/'runtime-after.json',backend.runtime_metadata())
        rows=jsonl(out/'attempts.jsonl');write_json(out/'costs-and-runtime.json',dict(model_load_count=len(jsonl(out/'model-loads.jsonl')),run_elapsed_s=time.perf_counter()-started,total_calls=len(rows),selector_forward_passes=sum(r['stage']=='resolver' for r in rows),text_generations=sum(r['stage']!='resolver' for r in rows),input_tokens=sum(r['input_tokens'] for r in rows),output_tokens=sum(r.get('output_tokens') or 0 for r in rows),call_latency_s=sum(r['latency_s'] for r in rows),prior_cost_excluded=True))
    write_json(out/'result.private.json',result);print(json.dumps(export(out,baseline,requested),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
