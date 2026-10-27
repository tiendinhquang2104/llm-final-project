"""One frozen v3 run, shared native renderer and isolated evaluation probes."""
from collections import Counter
from copy import deepcopy
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
from src.task3.sft_v1_runtime import verify_frozen,evaluating,gpu_cost,adapter_identity,digest
from src.task3.sft_v2_runtime import load_native,verify_model_files
from src.task3.sft_v2_public_context import generate as context_generate,preflight as _context_preflight
from src.task3.sft_v3 import (BudgetJournal,REVIEW_POLICY,SELECTION_POLICY,oracle_prompt,
                           ORACLE_KEYS,compatibility_config,main_training_arguments,CODE_POLICY)
from scripts.task3_sft_v3_prepare import load_examples,jsonl,records

V2='outputs/task3/sft-v2-qlora-20261026-run1'


def preservation(repo,out):
    initial=json.loads((out/'initial-workspace-state.json').read_text())
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()!=initial['head']:raise ValueError('HEAD changed')
    if subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()!='fix/task3-strict-feedback':raise ValueError('branch changed')
    for name,expected in initial['files'].items():
        if sha256(repo/name)!=expected:raise ValueError('preexisting file changed: '+name)
    for name,expected in initial['historical_indices'].items():
        if sha256(repo/name)!=expected:raise ValueError('historical artifact index changed')
    return dict(passed=True,preexisting_files=len(initial['files']),historical_indices=len(initial['historical_indices']),
        head=initial['head'],branch=initial['branch'],root_predictions_sha256=sha256(repo/'predictions.json'))


def oracle_examples(root,examples):
    findings={r['source_id']:r for r in records(root/'oracle-dev.private.json')}
    result=[]
    for e in examples:
        r=findings[e['sample_id']]
        packet={k:r[k] for k in ORACLE_KEYS if k in r}
        packet['taxonomy']=r.get('taxonomy',r.get('taxonomy_labels',r.get('labels',[])))
        if isinstance(packet.get('location'),dict):packet['location']=packet['location'].get('excerpts',[])
        x=deepcopy(e);x['prompt']=oracle_prompt(e['prompt'],packet);result.append(x)
    return result


def context_preflight(tokenizer,examples,settings,context):
    adapted=[dict(e,sample_id=e['example_id']) for e in examples]
    result=_context_preflight(tokenizer,adapted,settings,context)
    for r,e in zip(result,examples):r['source_id']=e['sample_id']
    if any(r['status']!='evaluable' for r in result):raise ValueError('evaluation input exceeds frozen context')
    return result


def freeze(repo,out):
    import yaml
    from transformers import AutoTokenizer
    from src.task3.sft_v1_evaluation import EVALUATION_POLICY
    if (out/'manifest.json').exists():raise FileExistsError('already frozen')
    write_json(out/'preservation-before.json',preservation(repo,out))
    config=yaml.safe_load((repo/'configs/task3/sft_v3.yaml').read_text());root=repo/config['dataset_root']
    dataset=json.loads((root/'dataset-manifest.json').read_text());n=dataset['train_targets']
    config['expected_rows']['train']=n;config['checksum_manifest_sha256']=sha256(root/'SHA256SUMS')
    verify_checksums(root,config['checksum_manifest_sha256'])
    historical=json.loads((repo/V2/'manifest.json').read_text());verify_model_files(historical)
    snapshot=Path(config['tokenizer_local']);model_cfg=json.loads((snapshot/'config.json').read_text());tok_cfg=json.loads((snapshot/'tokenizer_config.json').read_text())
    if (model_cfg['max_position_embeddings']!=32768 or model_cfg.get('rope_scaling') is not None
        or model_cfg.get('use_sliding_window') or tok_cfg['model_max_length']<32768):raise ValueError('unscaled context32768 unsupported')
    tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
    if hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()!=historical['tokenizer']['chat_template_sha256']:raise ValueError('tokenizer template differs')
    examples={s:load_examples(root,s) for s in ('train','dev')};examples['oracle-dev']=oracle_examples(root,examples['dev'])
    encoded={};stats={};pre=out/'preflight';pre.mkdir(exist_ok=True)
    for split,items in examples.items():
        rows,stats[split]=encode_examples(tokenizer,items,8192)
        jsonl(pre/f'{split}.encoded.private.jsonl',rows);write_json(pre/f'{split}.examples.private.json',items)
        encoded[split]=sha256(pre/f'{split}.encoded.private.jsonl')
        if split!='train':write_json(pre/f'{split}.context32768.json',context_preflight(tokenizer,items,historical['generation'],32768))
    if len(examples['dev'])!=80 or len(examples['oracle-dev'])!=80 or len(examples['train'])!=n:raise ValueError('population mismatch')
    v2_adapter=repo/V2/'main/checkpoint-240'
    adapter_files={name:sha256(v2_adapter/name) for name in ('adapter_model.safetensors','adapter_config.json')}
    policy_code=['src/task3/sft_v3.py','src/task3/sft_v3_training.py','src/task3/sft_v3_runtime.py',
        'scripts/task3_sft_v3_prepare.py','scripts/task3_sft_v3_experiment.py','configs/task3/sft_v3.yaml',
        'src/task3/sft_v1.py','src/task3/sft_v1_experiment.py','src/task3/sft_v1_training.py','src/task3/sft_v1_runtime.py',
        'src/task3/sft_v1_evaluation.py','src/task3/sft_v2_runtime.py','src/task3/sft_v2_public_context.py',
        'src/task3/sft_v2_public.py','src/task3/sft_v2.py','src/task3/train.py','src/task3/pilot_training.py',
        'scripts/task3_sft_v1_prepare.py','src/task3/cpp_sandbox.py',
        'scripts/task3_sft_v1_l4_audit.py','scripts/task3_sft_v1_l4_unfenced_audit.py']
    code={p:sha256(repo/p) for p in policy_code}
    for p,h in code.items():
        target=out/'source-snapshot'/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/p,target)
    write_json(out/'code-policy.json',CODE_POLICY)
    aux_names=['code-policy.json','official-contract.json','review-policy.json','selection-policy.json','ORACLE_WRAPPER.txt','SYSTEM_PROMPT.txt','request.txt']
    aux={name:sha256(out/name) for name in aux_names}
    manifest=dict(version='task3-sft-v3.0',created_utc=datetime.now(timezone.utc).isoformat(),
        config=config,head=json.loads((out/'initial-workspace-state.json').read_text())['head'],branch='fix/task3-strict-feedback',
        code=code,dataset={str(p.relative_to(root)):sha256(p) for p in root.rglob('*') if p.is_file()},
        model_files=historical['model_files'],tokenizer=historical['tokenizer'],versions={name:version(name) for name in historical['versions']},
        preflight=str(pre),encoded=encoded,token_statistics=stats,generation=historical['generation'],inference_context=32768,
        model_context=dict(max_position_embeddings=model_cfg['max_position_embeddings'],rope_scaling=model_cfg.get('rope_scaling'),tokenizer_model_max_length=tok_cfg['model_max_length']),
        parser_policy=EVALUATION_POLICY['parser'],review_policy=REVIEW_POLICY,selection_rule=SELECTION_POLICY,
        call_budget=dict(primary=1120,smoke=2,dev=640,observed_final=480,total=1122),
        steps=dict(smoke=4,train_rows=n,epochs=2,per_epoch=n//4,main=n//2,checkpoints=[n//4,n//2]),
        smoke_ids=smoke_ids(examples['train']),main_training_arguments=main_training_arguments(config,out/'main',n),
        smoke_training_arguments=training_arguments(compatibility_config(config),out/'smoke',True),
        v2_adapter=str(v2_adapter),v2_adapter_files=adapter_files,aux_files=aux,
        input_boundary='E2E statement/source/submission mode/syntax-only diagnostics/Level; no findings or private metadata',
        oracle_boundary='20 reviewed dev sources only, 80 generation targets, frozen findings no Level answers/code; no training oracle',
        final_policy='observed synthetic final160, previously inspected; contents loaded after sealed dev selection; no independent unseen claim',
        training_memory_scope='main Trainer only, evaluations run after training; separate peak resets',
        causal_scope='targets plus official prompt changed together; oracle changes task; no separate causal attribution')
    write_json(out/'manifest.json',manifest);write_json(out/'manifest.sha256.json',dict(sha256=sha256(out/'manifest.json')))
    verify(repo,out,manifest)
    print(json.dumps(dict(status='frozen',steps=manifest['steps'],stats=stats)),flush=True)
    return manifest


def verify(repo,out,manifest):
    verify_frozen(repo,out,manifest)
    for name,expected in manifest['aux_files'].items():
        if sha256(out/name)!=expected:raise ValueError('frozen auxiliary changed: '+name)
    for name,expected in manifest['v2_adapter_files'].items():
        if sha256(Path(manifest['v2_adapter'])/name)!=expected:raise ValueError('v2 adapter changed')


def generate(model,tokenizer,example,manifest,journal,key):
    journal.append(dict(type='generation_input_binding',key=key,prompt_sha256=digest(example['prompt']),
        manifest_sha256=sha256(Path(manifest['preflight']).parent/'manifest.json'),context_limit=32768))
    return context_generate(model,tokenizer,example,manifest['generation'],journal,key,32768)


def evaluate(model,tokenizer,examples,rows,directory,manifest,journal,state_name,reset_peak=True):
    """Same native primary call; generic denominators and explicit memory scope."""
    import torch
    from src.task3.sft_v1_evaluation import aggregate_metrics
    from src.task3.sft_v2 import cross_level_consistency
    from src.task3.pilot_training import WeightedCompletionCollator,completion_mean_losses
    binding=dict(state=state_name,example_prompt_hashes={e['example_id']:digest(e['prompt']) for e in examples},
        model_revision=manifest['config']['revision'],adapter_identity=adapter_identity(model) if hasattr(model,'peft_config') else None,
        generation=manifest['generation'],parser=manifest['parser_policy'],context=32768,manifest_sha256=sha256(directory.parent/'manifest.json'))
    if (directory/'state-binding.json').exists() and json.loads((directory/'state-binding.json').read_text())!=binding:raise ValueError('evaluation identity differs')
    directory.mkdir(parents=True,exist_ok=True)
    if not (directory/'state-binding.json').exists():write_json(directory/'state-binding.json',binding)
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
            result=prior[-1] if prior else generate(model,tokenizer,e,manifest,journal,key)
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



def train(repo,out,manifest,journal,resume=False):
    import torch
    from src.task3.sft_v1_training import smoke,new_adapter
    from src.task3.sft_v3_training import audited_train,validate_start
    verify(repo,out,manifest)
    root=repo/manifest['config']['dataset_root'];pre=Path(manifest['preflight'])
    examples={s:load_examples(root,s) for s in ('train','dev')}
    rows={s:read_jsonl(pre/f'{s}.encoded.private.jsonl') for s in examples}
    if (out/'main/training-result.json').exists():raise ValueError('main already complete; use dev stage')
    base,tokenizer=load_native(manifest,journal)
    if not (out/'smoke/complete.json').exists():
        if (out/'smoke/started.json').exists():raise ValueError('interrupted smoke requires explicit technical diagnosis')
        compat=deepcopy(manifest);compat['config']=compatibility_config(manifest['config'])
        journal.append(dict(type='smoke_recipe_compatibility',actual_epochs=1,rows=16,steps=4,reason='reuse unchanged one-epoch smoke validator; main remains two epochs'))
        base=smoke(repo,out,base,tokenizer,examples,rows,compat,journal)
    model=new_adapter(base,manifest['config'])
    initial=json.loads((out/'smoke/complete.json').read_text())['initial_adapter_identity']
    if adapter_identity(model)!=initial:raise ValueError('fresh main adapter differs from pre-smoke seeded adapter')
    write_json(out/'main-freshness.json',dict(initial_equals_pre_smoke=True,smoke_updates_discarded=True,
        optimizer_scheduler_rng='fresh Trainer/optimizer/scheduler; seed42 reset by new_adapter',v2_adapter_loaded=False))
    checkpoint=None
    if (out/'main/started.json').exists():
        if not resume:raise ValueError('explicit safe resume required')
        choices=[p for p in (out/'main').glob('checkpoint-*') if (p/'checkpoint-identity.json').exists()]
        if not choices:raise ValueError('no sealed resumable checkpoint; refusing optimizer replay')
        checkpoint=max(choices,key=lambda p:int(p.name.split('-')[-1]))
        validate_start(out/'main',checkpoint,journal,manifest['steps']['checkpoints'])
    trainer,result=audited_train(repo,out,model,tokenizer,rows['train'],rows['dev'],examples['train'],manifest,journal,resume=checkpoint)
    del trainer,model,base;gc.collect();torch.cuda.empty_cache()
    write_json(out/'status.json',dict(status='training_complete_pending_dev',epochs=2,main_optimizer_steps=result['actual_optimizer_steps']))


def checkpoint_valid(path):
    identity=json.loads((path/'checkpoint-identity.json').read_text())
    for name,expected in identity.items():
        if sha256(path/name)!=expected:raise ValueError('checkpoint changed '+str(path/name))


def dev(repo,out,manifest,journal):
    import torch
    from peft import PeftModel
    from transformers import set_seed
    verify(repo,out,manifest)
    if not (out/'main/training-result.json').exists():raise ValueError('complete both epochs before dev evaluation')
    set_seed(42);root=repo/manifest['config']['dataset_root'];pre=Path(manifest['preflight'])
    examples=load_examples(root,'dev');oracle=oracle_examples(root,examples)
    rows=read_jsonl(pre/'dev.encoded.private.jsonl');oracle_rows=read_jsonl(pre/'oracle-dev.encoded.private.jsonl')
    base,tokenizer=load_native(manifest,journal)
    states=[('base',None),('v2',Path(manifest['v2_adapter']))]+[(f'v3-epoch{i}',out/'main'/f'checkpoint-{step}') for i,step in enumerate(manifest['steps']['checkpoints'],1)]
    for state,path in states:
        if (out/f'{state}-dev/complete.json').exists() and (out/f'{state}-oracle-dev/complete.json').exists():continue
        if path:
            if state.startswith('v3'):checkpoint_valid(path)
            model=PeftModel.from_pretrained(base,str(path),is_trainable=False)
            journal.append(dict(type='adapter_loaded',role=state,path=str(path),adapter_identity=adapter_identity(model)))
        else:model=base
        evaluate(model,tokenizer,examples,rows,out/f'{state}-dev',manifest,journal,f'{state}-dev')
        evaluate(model,tokenizer,oracle,oracle_rows,out/f'{state}-oracle-dev',manifest,journal,f'{state}-oracle-dev')
        if path:base=model.unload()
        del model;gc.collect();torch.cuda.empty_cache()
    write_json(out/'status.json',dict(status='awaiting_completed_dev_agent_review',dev_primary_generations=640))


def validate_selection(repo,out,manifest):
    selection=json.loads((out/'selection.json').read_text())
    if sha256(out/'selection.json')!=json.loads((out/'selection.sha256.json').read_text())['sha256']:raise ValueError('selection seal changed')
    if (selection.get('dev_only')is not True or selection['manifest_sha256']!=sha256(out/'manifest.json')
        or selection.get('final_outputs_absent_at_selection')is not True or selection['policy']!=SELECTION_POLICY):raise ValueError('selection provenance')
    for name,expected in selection['dev_evidence'].items():
        if sha256(out/name)!=expected:raise ValueError('dev evidence changed')
    from src.task3.sft_v3 import select_checkpoint
    recomputed=select_checkpoint(selection['candidates'],selection['v2_reference'])
    if any(selection[k]!=v for k,v in recomputed.items()):raise ValueError('selection rule mismatch')
    checkpoint=out/'main'/f"checkpoint-{selection['step']}";checkpoint_valid(checkpoint)
    if str(checkpoint)!=selection['checkpoint']:raise ValueError('selected checkpoint path')
    return selection


def final(repo,out,manifest,journal):
    import torch
    from peft import PeftModel
    from transformers import set_seed
    verify(repo,out,manifest);selection=validate_selection(repo,out,manifest)
    journal.append(dict(type='observed_final_opened_after_selection',selection_sha256=sha256(out/'selection.json')))
    root=repo/manifest['config']['dataset_root'];examples=load_examples(root,'final')
    if len(examples)!=160:raise ValueError('observed-final population')
    base,tokenizer=load_native(manifest,journal);set_seed(42)
    rows,stats=encode_examples(tokenizer,examples,8192)
    final_pre=out/'final-preflight';final_pre.mkdir(exist_ok=True)
    jsonl(final_pre/'final.encoded.private.jsonl',rows);write_json(final_pre/'final.examples.private.json',examples)
    write_json(final_pre/'context32768.json',context_preflight(tokenizer,examples,manifest['generation'],32768))
    write_json(final_pre/'provenance.json',dict(selection_sha256=sha256(out/'selection.json'),
        source_records_sha256=sha256(root/'final.records.jsonl'),encoded_sha256=sha256(final_pre/'final.encoded.private.jsonl'),token_stats=stats))
    states=[('base',None),('v2',Path(manifest['v2_adapter'])),('v3-selected',Path(selection['checkpoint']))]
    for state,path in states:
        if (out/f'{state}-final/complete.json').exists():continue
        if path:model=PeftModel.from_pretrained(base,str(path),is_trainable=False)
        else:model=base
        journal.append(dict(type='final_state_identity',role=state,adapter=str(path) if path else None,
            adapter_identity=adapter_identity(model) if path else None,selection_sha256=sha256(out/'selection.json')))
        evaluate(model,tokenizer,examples,rows,out/f'{state}-final',manifest,journal,f'{state}-final')
        if path:base=model.unload()
        del model;gc.collect();torch.cuda.empty_cache()
    write_json(out/'status.json',dict(status='awaiting_completed_final_agent_review',selected_step=selection['step'],final_primary_generations=480))
