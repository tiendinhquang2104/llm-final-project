"""Frozen public context32768 pass. Prior runs/modules remain immutable."""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from src.task3.sft_v1 import sha256,read_jsonl,native_prompt
from src.task3.sft_v1_experiment import write_json
from src.task3.sft_v1_runtime import digest
from src.task3.sft_v2_public import PublicJournal,map_input,export_submission
from src.task3.sft_v2_public_context import generate,preflight
from src.task3.sft_v2_public_runtime import verify_hashes,recover_results,jsonl,PUBLIC,TEMPLATE,FLAGS
from src.task3 import sft_v2_public_runtime as previous

OLD='outputs/task3/sft-v2-public-20261026-run1'
METHOD='task3-sft-v2-step240-native-public-context32768-v1'
CONTEXT=32768


def load(path):return json.loads(Path(path).read_text())


def history(repo,out):
    state=load(out/'initial-state.json');verify_hashes(repo,state['files'])
    for cmd,key in [(['git','rev-parse','HEAD'],'head'),(['git','branch','--show-current'],'branch')]:
        if subprocess.check_output(cmd,cwd=repo,text=True).strip()!=state[key]:raise ValueError('workspace identity changed')
    if state['branch']!='fix/task3-strict-feedback':raise ValueError('wrong branch')
    if sha256(repo/'predictions.json')!=state['root_predictions_sha256']:raise ValueError('root predictions changed')
    old=repo/OLD
    if sha256(old/'artifact-sha256.json')!=state['old_public_index_sha256']:raise ValueError('previous public index changed')
    verify_hashes(old,load(old/'artifact-sha256.json'))
    oldfreeze,manifest=previous.verify(repo,old)
    preserved=previous.preserve(repo,old)
    return oldfreeze,manifest,dict(previous_public_files=len(load(old/'artifact-sha256.json')),old_public_preserved=True,
                                 preexisting_repo_files=len(state['files']),historical=preserved)


def prepare(repo,out):
    from transformers import AutoTokenizer
    from src.task3.public_contract import verify_public_contract
    from src.task3.dataset import load_task3
    from src.task3.sft_v2_runtime import verify_model_files
    if (out/'freeze.json').exists():raise FileExistsError('freeze already exists')
    prior,manifest,preserved=history(repo,out);old=repo/OLD;verify_model_files(manifest)
    contract=verify_public_contract(PUBLIC)
    if contract['requested_levels']!=load(old/'requested-levels.private.json'):raise ValueError('official mapping changed')
    write_json(out/'official-contract.json',contract);write_json(out/'requested-levels.private.json',contract['requested_levels'])
    snapshot=Path(manifest['config']['tokenizer_local']);cfg=load(snapshot/'config.json');tcfg=load(snapshot/'tokenizer_config.json')
    if cfg['max_position_embeddings']!=CONTEXT or cfg.get('rope_scaling') is not None or cfg.get('use_sliding_window'):
        raise ValueError('pinned model does not support requested unscaled full context')
    if tcfg['model_max_length']<CONTEXT:raise ValueError('tokenizer context unsupported')
    tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
    if hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()!=manifest['tokenizer']['chat_template_sha256']:raise ValueError('chat template differs')
    records={r.sample_id:r for r in load_task3(PUBLIC,'public',out/'requested-levels.private.json')}
    bindings=read_jsonl(old/'public-inputs.private.jsonl');examples=read_jsonl(old/'examples.private.jsonl')
    if [e['sample_id'] for e in examples]!=list(contract['requested_levels']):raise ValueError('ordered IDs differ')
    labels=contract['taxonomy_labels'];root=repo/manifest['config']['dataset_root'];equivalence=[]
    previous_preflight={r['sample_id']:r for r in load(old/'context-preflight.json')}
    for binding,example in zip(bindings,examples):
        sid=example['sample_id'];r=records[sid];syntax=binding['local_syntax'];identity=syntax['identity']
        if sha256(Path(r.code_path))!=binding['source_sha256'] or r.code!=binding['mapped_input']['code']:raise ValueError('source changed '+sid)
        if identity['original_source_sha256']!=binding['source_sha256'] or identity['decoded_source_sha256']!=hashlib.sha256(r.code.encode()).hexdigest():raise ValueError('compiler source provenance '+sid)
        if (identity['flags']!=FLAGS or identity['template_ready_sha256']!=sha256(TEMPLATE/'READY.json')
            or identity['compiler_sha256']!=sha256(TEMPLATE/'usr/bin/g++') or identity['policy_sha256']!=sha256(repo/'src/task3/cpp_sandbox.py')):raise ValueError('compiler provenance '+sid)
        if load(old/'compiler'/(digest(identity)+'.json'))!=syntax:raise ValueError('compiler evidence mismatch '+sid)
        if map_input(r,syntax)!=binding['mapped_input']:raise ValueError('mapping changed '+sid)
        rendered=native_prompt(root,binding['mapped_input'],labels)
        if rendered!=example['prompt'] or digest(rendered)!=binding['prompt_sha256']:raise ValueError('prompt content changed '+sid)
        oldtext=tokenizer.apply_chat_template(example['prompt'],tokenize=False,add_generation_prompt=True)
        text=tokenizer.apply_chat_template(rendered,tokenize=False,add_generation_prompt=True)
        ids=tokenizer.apply_chat_template(rendered,tokenize=True,add_generation_prompt=True,truncation=False)
        oldids=tokenizer.apply_chat_template(example['prompt'],tokenize=True,add_generation_prompt=True,truncation=False)
        if text.encode()!=oldtext.encode() or ids!=oldids or len(ids)!=previous_preflight[sid]['prompt_tokens']:raise ValueError('token/prompt discrepancy '+sid)
        equivalence.append(dict(sample_id=sid,prompt_sha256=digest(rendered),rendered_utf8_sha256=hashlib.sha256(text.encode()).hexdigest(),
            token_ids_sha256=digest(ids),tokens=len(ids),identical_prompt_bytes=True,identical_token_ids=True,
            comparison='new renderer versus re-tokenized frozen old prompt with same pinned tokenizer; old recorded token count also identical'))
    for name in ['public-inputs.private.jsonl','examples.private.jsonl']:(out/name).write_bytes((old/name).read_bytes())
    pf=preflight(tokenizer,examples,prior['generation'],CONTEXT);write_json(out/'context-preflight.json',pf)
    if any(r['status']!='evaluable' for r in pf):raise ValueError('not all public prompts fit requested context')
    longest=max(pf,key=lambda r:r['prompt_tokens'])['sample_id'];order=[longest]+[e['sample_id'] for e in examples if e['sample_id']!=longest]
    write_json(out/'generation-order.json',dict(rule='longest actual prompt first; remaining authoritative ID order',ids=order,first_primary=longest))
    write_json(out/'prompt-equivalence.json',equivalence);write_json(out/'preservation-before.json',preserved)
    config=dict(method=METHOD,context_limit=CONTEXT,model_id=prior['model'],revision=prior['revision'],seed=manifest['config']['seed'],
        adapter=prior['selected_checkpoint'],generation=prior['generation'],quantization=prior['quantization'],
        attention_implementation='sdpa',device_map={'':0},effective_generation_use_cache=True,
        scientific_change='only application inference context8192→32768; no model/RoPE/tokenizer/prompt/decoding changes',
        administrative_changes=['fresh run and journal identity','longest-primary-first schedule','runtime/context evidence and comparison','seed42 explicitly restored before inference'])
    write_json(out/'inference-config.json',config)
    code=['src/task3/sft_v2_public_context.py','src/task3/sft_v2_public_context_runtime.py','scripts/task3_sft_v2_context32768.py','tests/test_task3_sft_v2_public_context.py']
    names=['initial-state.json','request.txt','official-contract.json','requested-levels.private.json','public-inputs.private.jsonl',
        'examples.private.jsonl','context-preflight.json','generation-order.json','prompt-equivalence.json','inference-config.json','preservation-before.json']
    freeze=dict(created_utc=datetime.now(timezone.utc).isoformat(),method=METHOD,context_limit=CONTEXT,config=config,
        prior_public_freeze_sha256=sha256(old/'public-freeze.json'),prior_public_index_sha256=sha256(old/'artifact-sha256.json'),
        generation=prior['generation'],ordered_requested_ids=list(contract['requested_levels']),maximum_physical_calls=len(examples),
        generation_order=order,code={n:sha256(repo/n) for n in code},files={n:sha256(out/n) for n in names},
        tokenizer=prior['tokenizer'],model_files=manifest['model_files'],adapter_files=prior['adapter_files'],
        support=dict(max_position_embeddings=cfg['max_position_embeddings'],rope_theta=cfg['rope_theta'],rope_scaling=cfg.get('rope_scaling'),
            use_sliding_window=cfg.get('use_sliding_window'),tokenizer_model_max_length=tcfg['model_max_length'],
            config_sha256=sha256(snapshot/'config.json'),tokenizer_config_sha256=sha256(snapshot/'tokenizer_config.json')),
        one_attempt=True,resume='completed recovered from journal; uncertain reservations never regenerated',
        new_compile_calls=0,new_link_calls=0,new_public_program_runtime_calls=0,compiler_evidence_verified_inputs=len(bindings))
    write_json(out/'freeze.json',freeze);write_json(out/'freeze.sha256.json',dict(sha256=sha256(out/'freeze.json')))
    print(json.dumps(dict(preflight=len(pf),context=CONTEXT,longest=longest,max_prompt=max(x['prompt_tokens'] for x in pf))),flush=True)


def verify(repo,out):
    f=load(out/'freeze.json')
    if sha256(out/'freeze.json')!=load(out/'freeze.sha256.json')['sha256']:raise ValueError('freeze seal changed')
    verify_hashes(repo,f['code']);verify_hashes(out,f['files'])
    prior,manifest,preserved=history(repo,out)
    if f['prior_public_freeze_sha256']!=sha256(repo/OLD/'public-freeze.json'):raise ValueError('prior freeze changed')
    if f['context_limit']!=CONTEXT or f['config']['context_limit']!=CONTEXT:raise ValueError('context configuration mismatch')
    return f,manifest,preserved


class BoundJournal(PublicJournal):
    def __init__(self,path,allowed,identity):self.identity=identity;super().__init__(path,allowed)
    def _validate(self,events):
        for event in events:
            if event.get('method')!=METHOD or event.get('runtime_identity_sha256')!=self.identity:
                raise ValueError('journal method identity differs from this frozen fresh run')
            if event.get('type')=='generation_completed':
                result=event.get('result',{})
                if result.get('method')!=METHOD or result.get('runtime_identity_sha256')!=self.identity:
                    raise ValueError('completed result method identity differs')
        reserved,completed=super()._validate(events)
        failures=set()
        for event in events:
            if event.get('type')=='public_input_allocation_failed':
                key=event.get('key')
                if key not in self.allowed or key in reserved or key in failures or event['result']['sample_id']!=key:
                    raise ValueError('unreserved infrastructure-failure binding invalid')
                failures.add(key)
        return reserved,completed
    def append(self,event):
        event=dict(event,method=METHOD,runtime_identity_sha256=self.identity)
        if event.get('type')=='generation_completed':
            key=event['key'];event['result']=dict(event['result'],method=METHOD,prompt_sha256=self.allowed[key],runtime_identity_sha256=self.identity)
        super().append(event)


def recover(out,freeze):
    examples=read_jsonl(out/'examples.private.jsonl'); allowed={e['sample_id']:digest(e['prompt']) for e in examples}
    journal=BoundJournal(out/'generation-journal.jsonl',allowed,sha256(out/'freeze.json'))
    results=recover_results(examples,journal.events(),set())
    for e in examples:
        if e['sample_id'] in results:
            r=results[e['sample_id']]
            if r['sample_id']!=e['sample_id'] or r['level']!=e['level']:raise ValueError('journal ID/Level binding')
    return examples,journal,results


def normalized(out,examples,results):
    return [dict(results[e['sample_id']],method=METHOD,prompt_sha256=digest(e['prompt']),runtime_identity_sha256=sha256(out/'freeze.json')) for e in examples if e['sample_id'] in results]


def infer(repo,out):
    import fcntl
    import torch
    from transformers import set_seed
    from peft import PeftModel
    from src.task3.sft_v2_runtime import load_native
    with (out/'inference.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        f,manifest,_=verify(repo,out);examples,journal,results=recover(out,f);by_id={e['sample_id']:e for e in examples}
        pending=[sid for sid in f['generation_order'] if sid not in results]
        def save():jsonl(out/'generations.jsonl',normalized(out,examples,results))
        save()
        if not pending:print('No unreserved inputs remain. No model loaded.');return
        set_seed(f['config']['seed']);start=time.perf_counter();base,tokenizer=load_native(manifest,journal)
        model=PeftModel.from_pretrained(base,f['config']['adapter'],is_trainable=False)
        for p in model.parameters():p.requires_grad_(False)
        model.eval();torch.cuda.synchronize()
        if model.config.max_position_embeddings!=CONTEXT or getattr(model.config,'rope_scaling',None) is not None or model.config._attn_implementation!='sdpa':raise ValueError('loaded backend context differs')
        journal.append(dict(type='public_model_and_adapter_load_completed',wall_s=time.perf_counter()-start,
            adapter=f['adapter_files'],model_max_position_embeddings=model.config.max_position_embeddings,rope_theta=model.config.rope_theta,
            rope_scaling=getattr(model.config,'rope_scaling',None),attention=model.config._attn_implementation,
            prepared_model_use_cache=model.config.use_cache,effective_generation_use_cache=True,
            gpu=torch.cuda.get_device_name(0),device=str(next(model.parameters()).device),
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved()))
        torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
        journal.append(dict(type='public_generation_phase_started',pending=len(pending),peak_scope='whole generation phase after load, reset once; longest first official primary retained'))
        sound=True
        for sid in pending:
            e=by_id[sid];callstart=time.perf_counter()
            try:result=generate(model,tokenizer,e,f['generation'],journal,sid,f['config']['context_limit'])
            except torch.cuda.OutOfMemoryError as exc:
                reserved=sid in journal.reserved()
                result=dict(sample_id=sid,example_id=sid,level=e['level'],status='generation_error',finish_reason='generation_error',raw='',parsed=None,
                    input_tokens=next(x['prompt_tokens'] for x in load(out/'context-preflight.json') if x['sample_id']==sid),output_tokens=None if reserved else 0,
                    wall_s=time.perf_counter()-callstart,error='CUDA OOM: '+str(exc),output_cost_unknown=reserved,physical_call_reserved=reserved)
                journal.append(dict(type='generation_completed' if reserved else 'public_input_allocation_failed',key=sid,result=result))
                torch.cuda.empty_cache()
            results[sid]=result;save()
            if result['status']=='generation_error':
                try:torch.cuda.synchronize()
                except Exception as exc:
                    journal.append(dict(type='cuda_context_unsound',key=sid,error=str(exc)));sound=False;break
            print(json.dumps(dict(processed=len(results),expected=len(examples),sample_id=sid,status=result['status'])),flush=True)
        if sound:torch.cuda.synchronize()
        journal.append(dict(type='public_generation_phase_completed' if sound else 'public_generation_phase_aborted',wall_s=time.perf_counter()-start,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            scope='whole generation phase after load, all calls including failures, no per-case reset',cuda_context_sound=sound))
        write_json(out/'generation-complete.json',dict(expected=len(examples),normalized=len(results),physical_reservations=len(journal.reserved()),
            processed_all=len(results)==len(examples),status_counts=dict(Counter(r['status'] for r in results.values())),journal_sha256=sha256(journal.path)))


def export(repo,out):
    f,_,_=verify(repo,out);examples,journal,results=recover(out,f);rows=normalized(out,examples,results)
    if read_jsonl(out/'generations.jsonl')!=rows:raise ValueError('normalized outputs differ from journal')
    validation=export_submission(out/'submission',load(out/'requested-levels.private.json'),rows,load(out/'official-contract.json')['taxonomy_labels'])
    if validation['complete_export']:
        candidate=repo/'submission-candidates/sft-v2-context32768'
        if candidate.exists():raise FileExistsError('convenient candidate destination exists; preserved')
        candidate.mkdir(parents=True)
        source=Path(validation['path']);dest=candidate/'predictions.json'
        with dest.open('xb') as stream:stream.write(source.read_bytes())
        if dest.read_bytes()!=source.read_bytes():raise ValueError('convenient copy differs')
        write_json(out/'convenient-copy.json',dict(path=str(dest),sha256=sha256(dest),bytes=dest.stat().st_size,byte_identical=True))
    print(json.dumps(validation,ensure_ascii=False),flush=True)
