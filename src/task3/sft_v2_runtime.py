"""V2 orchestration reusing the native v1 encoder, generation and Trainer stack."""
from collections import Counter
from datetime import datetime,timezone
from importlib.metadata import version
import gc
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import time

from src.task3.sft_v1 import sha256,read_jsonl,encode_examples,verify_checksums
from src.task3.sft_v1_experiment import Journal,write_json,smoke_ids,training_arguments
from src.task3.sft_v1_runtime import verify_frozen,evaluating,generate,gpu_cost,adapter_identity
from src.task3.sft_v1_evaluation import aggregate_metrics,EVALUATION_POLICY
from src.task3.sft_v2 import load_split,BudgetJournal,CALL_BUDGET,SELECTION_POLICY,cross_level_consistency

V1='outputs/task3/sft-v1-qlora-20261026-run1'
R15='outputs/task3/r15-abc-20261025'


def compiler_view(syntax):
    return dict(status='pass' if syntax['returncode']==0 and not syntax.get('timeout',False) else 'error',diagnostic=syntax['stderr'])


def historical_payload(prediction):
    if prediction is None:return None
    return {k:prediction['output'][k] for k in ('taxonomy_error','feedback')}


def pending_dev_evaluations(resume_step,complete):
    return [step for step in (120,240) if step<=resume_step and step not in complete]


def verify_model_files(manifest):
    snapshot=Path(manifest['config']['tokenizer_local'])
    for name,expected in manifest['model_files'].items():
        if sha256(snapshot/name)!=expected:raise ValueError('pinned physical model file changed: '+name)


def validated_selection(repo,out,manifest):
    from src.task3.sft_v2 import select_checkpoint
    selection=json.loads((out/'selection.json').read_text())
    if sha256(out/'selection.json')!=json.loads((out/'selection.sha256.json').read_text())['sha256']:
        raise ValueError('selection seal changed')
    if (selection.get('step') not in (120,240) or selection.get('dev_only') is not True
        or selection.get('manifest_sha256')!=sha256(out/'manifest.json')
        or selection.get('policy')!=SELECTION_POLICY or selection.get('final_outputs_absent_at_selection') is not True):
        raise ValueError('invalid dev selection provenance')
    for category in ('review_files','dev_artifacts','l4_files'):
        if not selection.get(category):raise ValueError('missing selection evidence '+category)
        for name,expected in selection[category].items():
            p=(out/name).resolve()
            if not p.is_relative_to(out.resolve()) or sha256(p)!=expected:raise ValueError('selection evidence changed '+name)
    limits=selection['native_base_limits']
    recomputed=select_checkpoint(selection['candidates'],limits['clean_false_alarms'],limits['invalid'])
    if any(selection[k]!=recomputed[k] for k in recomputed):raise ValueError('selection rule mismatch')
    checkpoint=out/'main'/f"checkpoint-{selection['step']}"
    if Path(selection['checkpoint']).resolve()!=checkpoint.resolve():raise ValueError('checkpoint selection path')
    identity=json.loads((checkpoint/'checkpoint-identity.json').read_text())
    for name,h in identity.items():
        if sha256(checkpoint/name)!=h:raise ValueError('selected checkpoint changed')
    return selection


def freeze(repo,out):
    import yaml
    from transformers import AutoTokenizer
    if (out/'manifest.json').exists(): raise FileExistsError('already frozen')
    state=json.loads((out/'initial-workspace-state.json').read_text())
    for p,h in state['files'].items():
        if sha256(repo/p)!=h: raise ValueError('preexisting file changed: '+p)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()
    if head!=state['head'] or branch!='fix/task3-strict-feedback':raise ValueError('workspace moved')
    old=json.loads((repo/V1/'manifest.json').read_text());verify_frozen(repo,repo/V1,old)
    for p,h in json.loads((repo/V1/'artifact-sha256.json').read_text()).items():
        if sha256(repo/V1/p)!=h:raise ValueError('v1 artifact changed: '+p)
    config=yaml.safe_load((repo/'configs/task3/sft_v1.yaml').read_text())
    config.update(experiment='task3-sft-v2',dataset_root='data/raw/task3-sft-v2')
    root=repo/config['dataset_root'];config['checksum_manifest_sha256']=sha256(root/'SHA256SUMS')
    config['expected_rows']=dict(train=960,dev=80,test=80,final=160)
    # Historical recipe validator is reused without pretending its loss-only
    # checkpoint_selection field selects v2; the actual rule below supersedes it.
    config['compatibility_recipe_selection_field']='ignored by v2; semantic selection_rule is authoritative'
    verify_checksums(root,config['checksum_manifest_sha256'])
    tokenizer=AutoTokenizer.from_pretrained(config['tokenizer_local'],local_files_only=True,trust_remote_code=False)
    if hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()!=old['tokenizer']['chat_template_sha256']:
        raise ValueError('native chat template changed')
    examples={s:load_split(root,s) for s in ('train','dev','test','final')}
    stats={};encoded={};preflight=out/'preflight';preflight.mkdir()
    from scripts.task3_sft_v2_prepare import write_jsonl
    for s,items in examples.items():
        rows,stats[s]=encode_examples(tokenizer,items,8192)
        write_jsonl(preflight/f'{s}.encoded.private.jsonl',rows)
        write_json(preflight/f'{s}.examples.private.json',items)
        encoded[s]=sha256(preflight/f'{s}.encoded.private.jsonl')
    # Exact shared prompt, parser, native generation and model profile binding.
    from src.task3.sft_v1 import load_split as load_v1
    parity={}
    for split in ('dev','test'):
        original=load_v1(repo/'data/raw/task3-sft-v1',split)
        if examples[split]!=original:raise ValueError('shared examples changed')
        if sha256(root/f'{split}.sft.jsonl')!=old['dataset'][f'{split}.sft.jsonl']:
            raise ValueError('shared dataset bytes changed')
        parity[split]=dict(targets=len(original),example_objects_equal=True,sft_bytes_equal=True,
                          prompt_sha256={e['example_id']:hashlib.sha256(json.dumps(e['prompt'],ensure_ascii=False).encode()).hexdigest() for e in original})
    # Reuse only exact native historical states. Old-test reuse is reported as
    # observed regression, never used by checkpoint selection.
    reused={}
    for source,target,split in [('base-dev','base-dev','dev'),('step-160-dev','v1-dev','dev'),
                                ('base-test','base-regression','test'),('selected-test','v1-regression','test')]:
        dest=out/target;dest.mkdir()
        files={}
        for n in ('generations.jsonl','losses.jsonl','complete.json'):
            shutil.copyfile(repo/V1/source/n,dest/n);files[n]=sha256(dest/n)
        reused[target]=dict(original=str(repo/V1/source),files=files,split=split,
            reason='exact unchanged source/prompt/gold, pinned base/preparation or selected v1 step160, native generation/parser code and config hashes verified',
            generated_in_this_experiment=False)
    write_json(out/'reuse-provenance.json',reused);write_json(out/'native-prompt-parity.private.json',parity)
    ar15=json.loads((repo/R15/'A/comparison-dev/execution-binding.json').read_text())['binding']['config']
    ar15={k:v for k,v in ar15.items() if k in ('model_id','revision','seed','context_limit','max_new_tokens','level4_max_tokens',
        'max_attempts','generation_max_time_s','do_sample','load_in_4bit','few_shot_k','prompt_variant','prompt_policy','completion_policy','hf_cache')}
    ar15.update(runtime_out=str(repo/R15),prompt_variant='zero_shot',few_shot_k=0)
    historical={str(p.relative_to(repo)):sha256(p) for p in (repo/R15/'vendor').rglob('*.py')}
    paths=set(old['code'])|{str(p.relative_to(repo)) for p in (repo/'src/task3').glob('sft_v2*.py')}|{
        str(p.relative_to(repo)) for p in (repo/'scripts').glob('task3_sft_v2*.py')}|{'src/task3/r15_abc_experiment.py','src/task3/r15_abc_data.py','src/task3/cpp_sandbox.py'}
    code={p:sha256(repo/p) for p in sorted(paths)};code.update(historical)
    actual_args=training_arguments(config,out/'main');actual_args['save_steps']=120
    snapshot=Path(config['tokenizer_local'])
    model_paths=sorted(snapshot.glob('*.safetensors'))+[snapshot/n for n in ('model.safetensors.index.json','config.json','generation_config.json')]
    if not any(p.suffix=='.safetensors' for p in model_paths):raise ValueError('pinned local weights unavailable')
    model_files={p.name:sha256(p) for p in model_paths}
    from scripts.task3_sft_v2_review import L4_POLICY
    write_json(out/'l4-policy.json',L4_POLICY)
    manifest=dict(created_utc=datetime.now(timezone.utc).isoformat(),config=config,head=head,branch=branch,
        code=code,model_files=model_files,dataset={str(p.relative_to(root)):sha256(p) for p in root.rglob('*') if p.is_file()},
        preflight=str(preflight),encoded=encoded,tokenizer=old['tokenizer'],versions={n:version(n) for n in old['versions']},
        generation=old['generation'],evaluation_policy=EVALUATION_POLICY,selection_rule=SELECTION_POLICY,l4_policy=L4_POLICY,
        call_budget=CALL_BUDGET,steps=dict(smoke=4,main=240,checkpoints=[120,240]),
        smoke_ids=smoke_ids(examples['train']),main_training_arguments=actual_args,
        smoke_training_arguments=training_arguments(config,out/'smoke',True),token_statistics=stats,
        ar15_config=ar15,ar15_identity=dict(runtime='historical Round15 snapshot from original git blobs; import namespace only',
            input_mapping='new source/spec plus syntax-only compiler status; problems=[], grading_policy=None; no private witnesses',
            backend='original HFBackend, NF4 double quant BF16 compute; default nonquantized storage differs from prepared native profile',
            policy='original Vietnamese zero-shot prompt, parser, disclosure guard, at most3 attempts, deterministic L1/L2 fallback; context16384; original model EOS list',
            administrative_adaptation='reservation prompt digest corrected to historical runner.digest; shared global physical budget; scientific renderer/backend/controller unchanged'),
        final_freeze=dict(dataset_sha256=sha256(root/'final.sft.jsonl'),records_sha256=sha256(root/'final.records.jsonl'),
            uses='authoring verification and tokenizer preflight only before selected checkpoint; training/selection read train/dev only',
            synthetic_agent_reviewed=True,independent_gold=False),request_sha256=sha256(out/'request.txt'))
    write_json(out/'manifest.json',manifest);write_json(out/'manifest.sha256.json',dict(sha256=sha256(out/'manifest.json')))
    snapshot=out/'source-snapshot'
    for p in code:
        target=snapshot/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/p,target)
    write_json(preflight/'actual-config.json',dict(stats=stats,versions=manifest['versions'],tokenizer=manifest['tokenizer'],model_loaded=False))
    verify_frozen(repo,out,manifest)
    return manifest


def evaluate(model,tokenizer,examples,rows,directory,manifest,journal,state_name,reset_peak=True):
    """Same native primary call; generic denominators and explicit memory scope."""
    import torch
    from src.task3.pilot_training import WeightedCompletionCollator,completion_mean_losses
    directory.mkdir(parents=True,exist_ok=True)
    if (directory/'complete.json').exists():return json.loads((directory/'complete.json').read_text())
    collator=WeightedCompletionCollator(tokenizer.pad_token_id)
    losses=read_jsonl(directory/'losses.jsonl') if (directory/'losses.jsonl').exists() else []
    gens=read_jsonl(directory/'generations.jsonl') if (directory/'generations.jsonl').exists() else []
    loss_ids={r['example_id'] for r in losses};gen_ids={r['example_id'] for r in gens}
    if len(loss_ids)!=len(losses) or len(gen_ids)!=len(gens):raise ValueError('duplicate durable evaluation row')
    start=time.perf_counter()
    if reset_peak:torch.cuda.reset_peak_memory_stats()
    with evaluating(model):
        for row in rows:
            if row['example_id'] in loss_ids:continue
            tick=time.perf_counter();batch=collator([row]);inputs={k:batch[k].cuda() for k in ('input_ids','attention_mask')}
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                output=model(**inputs,use_cache=False)
                loss=float(completion_mean_losses(output.logits,batch['labels'].cuda())[0])
            torch.cuda.synchronize()
            if not math.isfinite(loss):raise ValueError('nonfinite evaluation loss')
            result=dict(example_id=row['example_id'],level=row['level'],loss=loss,
                completion_tokens=sum(x!=-100 for x in row['labels']),wall_s=time.perf_counter()-tick)
            Journal(directory/'losses.jsonl').append(result);losses.append(result);del output,batch,inputs
        for e in examples:
            if e['example_id'] in gen_ids:continue
            key=state_name+'/'+e['example_id']
            prior=[x['result'] for x in journal.events() if x.get('type')=='generation_completed' and x.get('key')==key]
            result=prior[-1] if prior else generate(model,tokenizer,e,manifest['generation'],journal,key)
            Journal(directory/'generations.jsonl').append(result);gens.append(result)
            print(json.dumps(dict(phase=state_name,generated=len(gens),id=e['example_id'],status=result['status'])),flush=True)
    expected={e['example_id'] for e in examples}
    if {r['example_id'] for r in losses}!=expected or {r['example_id'] for r in gens}!=expected:raise ValueError('evaluation population mismatch')
    counts=Counter(r['level'] for r in losses)
    summary=dict(mean_loss=sum(r['loss'] for r in losses)/len(losses),
        by_level_loss={str(k):sum(r['loss'] for r in losses if r['level']==k)/v for k,v in counts.items()},
        metrics=aggregate_metrics(examples,gens),cross_level_consistency=cross_level_consistency(gens),
        teacher_forced=dict(forwards=len(losses),wall_s=sum(r['wall_s'] for r in losses)),
        generation=dict(calls=len(gens),wall_s=sum(r['wall_s'] for r in gens)),
        memory_scope='this evaluation phase' if reset_peak else 'whole main trajectory so far including nested evaluation; peak counter NOT reset',**gpu_cost(start))
    write_json(directory/'complete.json',summary);return summary


def load_native(manifest,journal):
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig
    from peft import prepare_model_for_kbit_training
    from src.task3.pilot_training import _model_precision_audit
    verify_model_files(manifest)
    config=manifest['config'];start=time.perf_counter();journal.append(dict(type='base_model_load_started',profile='native'))
    tokenizer=AutoTokenizer.from_pretrained(config['tokenizer_local'],local_files_only=True,trust_remote_code=False)
    base=AutoModelForCausalLM.from_pretrained(config['model_id'],revision=config['revision'],local_files_only=True,
        trust_remote_code=False,quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16),dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa')
    precision=_model_precision_audit(base,config['revision'])
    base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
    base.config.use_cache=False
    journal.append(dict(type='base_model_load_completed',profile='native',wall_s=time.perf_counter()-start,precision=precision))
    return base,tokenizer


def train(repo,out,manifest,journal,resume=False):
    import torch
    from src.task3.sft_v1_training import smoke,new_adapter
    from src.task3.sft_v2_training import audited_train
    verify_frozen(repo,out,manifest)
    root=repo/manifest['config']['dataset_root']
    examples={s:load_split(root,s) for s in ('train','dev')}
    rows={s:read_jsonl(Path(manifest['preflight'])/f'{s}.encoded.private.jsonl') for s in examples}
    if (out/'main/training-result.json').exists():raise ValueError('main already complete')
    base,tokenizer=load_native(manifest,journal)
    if not (out/'smoke/complete.json').exists():
        if (out/'smoke/started.json').exists():raise ValueError('interrupted smoke requires diagnosis')
        base=smoke(repo,out,base,tokenizer,examples,rows,manifest,journal)
    model=new_adapter(base,manifest['config'])
    if adapter_identity(model)!=json.loads((out/'smoke/complete.json').read_text())['initial_adapter_identity']:
        raise ValueError('main does not start fresh pre-smoke seeded adapter')
    write_json(out/'main-freshness.json',dict(initial_equals_pre_smoke=True,smoke_updates_discarded=True,
        optimizer_scheduler_rng='fresh native Trainer; seed42 reset by new_adapter',v1_adapter_loaded=False))
    checkpoint=None
    if (out/'main/started.json').exists():
        if not resume:raise ValueError('explicit resume required')
        candidates=[p for p in (out/'main').glob('checkpoint-*') if (p/'checkpoint-identity.json').exists()]
        if not candidates:raise ValueError('no complete resumable checkpoint')
        checkpoint=max(candidates,key=lambda p:int(p.name.split('-')[-1]))
    def callback(m,step):
        evaluate(m,tokenizer,examples['dev'],rows['dev'],out/f'step-{step}-dev',manifest,journal,f'step-{step}-dev',reset_peak=False)
    if checkpoint:
        from src.task3.sft_v2_training import validate_start
        from safetensors.torch import load_file
        from peft import set_peft_model_state_dict
        validate_start(out/'main',checkpoint,journal)
        complete={s for s in (120,240) if (out/f'step-{s}-dev/complete.json').exists()}
        for step in pending_dev_evaluations(int(checkpoint.name.split('-')[-1]),complete):
            sealed=out/'main'/f'checkpoint-{step}'
            for n,h in json.loads((sealed/'checkpoint-identity.json').read_text()).items():
                if sha256(sealed/n)!=h:raise ValueError('pending evaluation checkpoint changed')
            set_peft_model_state_dict(model,load_file(str(sealed/'adapter_model.safetensors')))
            callback(model,step)
    trainer,result=audited_train(repo,out,model,tokenizer,rows['train'],rows['dev'],examples['train'],manifest,journal,
                                 'main',callback,checkpoint)
    del trainer,model,base;gc.collect();torch.cuda.empty_cache()
    write_json(out/'status.json',dict(status='awaiting_dev_source_grounded_review',main_optimizer_steps=240))


def ar15(repo,out,manifest,journal,split):
    """Run original scientific R15 controller with an audited administrative wrapper."""
    from src.task3 import r15_abc_experiment as abc
    from src.task3.r15_abc_data import query_record
    from scripts.task3_sft_v2_prepare import write_jsonl
    if split=='final':validated_selection(repo,out,manifest)
    verify_frozen(repo,out,manifest)
    verify_model_files(manifest)
    examples=load_split(repo/manifest['config']['dataset_root'],split)
    records=read_jsonl(repo/manifest['config']['dataset_root']/f'{split}.records.jsonl')
    query=[];root=repo/manifest['config']['dataset_root']
    if split=='dev':
        evidence=json.loads((repo/'data/raw/task3-sft-v1/verification/execution.private.json').read_text())
        syntax_by_id={sid:ev['compiler_syntax'] for sid,ev in evidence.items()}
    else:
        evidence=json.loads((root/'authoring/final-verification/execution.private.json').read_text())
        syntax_by_id={sid:ev['syntax_only'] for sid,ev in evidence.items()}
    for r in records:
        x=r['input'];compiler=compiler_view(syntax_by_id[r['source_id']])
        if compiler['diagnostic']!=x['compile_log']:raise ValueError('compiler input binding')
        query.append(query_record(dict(sample_id=r['sample_id'],family=r['family_id'],statement=x['statement'],
            exam_type=x['exam_type'],code=x['code'],compiler=compiler),x['target_feedback_level']))
    config=manifest['ar15_config'];runner=abc.historical_module(config['runtime_out'],'task3.round15_runner')
    inference=abc.historical_module(config['runtime_out'],'task3.inference')
    start=time.perf_counter();journal.append(dict(type='base_model_load_started',profile='ar15'))
    backend=inference.HFBackend(config)
    journal.append(dict(type='base_model_load_completed',profile='ar15',wall_s=time.perf_counter()-start,precision=backend.precision_audit))
    state='ar15-'+split;directory=out/state;directory.mkdir(exist_ok=True)
    original=abc.ReservedBackend
    class SharedReservation(original):
        def generate(self,messages,active):
            reserved=abc.jsonl(self.path)
            if len(reserved)>=3:raise ValueError('historical request cap')
            key=state+'/'+self.sample_id+'/'+str(len(reserved)+1);journal.reserve(key)
            abc.append_event(self.path,dict(identity=self.identity,sample_id=self.sample_id,attempt=len(reserved)+1,
                prompt_sha256=runner.digest(messages),input_tokens=len(self.tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)),reserved_unix=time.time()))
            result=self.backend.generate(messages,active)
            journal.append(dict(type='ar15_generation_completed',key=key,output_tokens=result.output_tokens,wall_s=result.latency_s,
                                finish_reason=result.finish_reason,raw=result.text))
            return result
    abc.ReservedBackend=SharedReservation
    try:result=abc.run_arm(query,'A',config,directory/'historical',examples=[],adapter=None,backend=backend)
    finally:abc.ReservedBackend=original
    predictions={r['sample_id']:r for r in result['predictions']};traces={r['sample_id']:r for r in result['traces']}
    gens=[]
    for e in examples:
        eid=e['example_id'];p=predictions.get(eid);trace=traces.get(eid) or result.get('unresolved',{})
        request=directory/'historical/requests'/abc.execution_identity(eid)[:24]
        attempts=abc.jsonl(request/'attempts.jsonl')
        parsed=historical_payload(p)
        gens.append(dict(example_id=eid,sample_id=e['sample_id'],level=e['level'],status='valid' if p else 'missing',
            parsed=parsed,raw=json.dumps(parsed,ensure_ascii=False) if p else '',finish_reason='eos' if p else 'missing',
            raw_kind='historical_controller_final_export; actual raw attempts preserved separately',
            structural_validity_basis='completed historical controller export; finish_reason here describes export, actual model terminations below',
            actual_attempt_finish_reasons=[a.get('finish_reason') for a in attempts],
            raw_attempts=[a.get('raw_text') for a in attempts],historical_final_origin=trace.get('final_origin') if isinstance(trace,dict) else None,
            input_tokens=sum(a.get('input_tokens',0) for a in attempts),output_tokens=sum(a.get('output_tokens',0) for a in attempts),
            wall_s=sum(a.get('latency_s',0) for a in attempts),physical_calls=len(attempts)))
    write_jsonl(directory/'generations.jsonl',gens)
    write_json(directory/'complete.json',dict(mean_loss=None,metrics=aggregate_metrics(examples,gens),
        cross_level_consistency=cross_level_consistency(gens),physical_calls=sum(r['physical_calls'] for r in gens),
        scope='historical system comparator with internal retries/fallback; not native adapter-only comparison',runtime=backend.runtime_metadata()))


def final_native(repo,out,manifest,journal):
    import torch
    from peft import PeftModel
    verify_frozen(repo,out,manifest)
    selection=validated_selection(repo,out,manifest)
    journal.append(dict(type='final_evaluation_started',selection_sha256=sha256(out/'selection.json')))
    root=repo/manifest['config']['dataset_root'];pre=Path(manifest['preflight'])
    base,tokenizer=load_native(manifest,journal)
    examples=load_split(root,'final');rows=read_jsonl(pre/'final.encoded.private.jsonl')
    evaluate(base,tokenizer,examples,rows,out/'base-final',manifest,journal,'base-final')
    for state,path in [('v1-final',repo/V1/'main/checkpoint-160'),('v2-final',out/'main'/f"checkpoint-{selection['step']}")]:
        model=PeftModel.from_pretrained(base,str(path),is_trainable=False)
        journal.append(dict(type='adapter_loaded',role=state,path=str(path),adapter_identity=adapter_identity(model)))
        evaluate(model,tokenizer,examples,rows,out/state,manifest,journal,state)
        if state=='v2-final':evaluate(model,tokenizer,load_split(root,'test'),read_jsonl(pre/'test.encoded.private.jsonl'),out/'v2-regression',manifest,journal,'v2-regression')
        base=model.unload();del model;gc.collect();torch.cuda.empty_cache()

