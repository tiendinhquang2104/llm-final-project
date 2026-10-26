"""Real-Qwen smoke and one native Trainer trajectory, with audited checkpoints."""
from collections import Counter
import gc
import json
import math
from pathlib import Path
import time

from src.task3.sft_v1 import make_trainer, read_jsonl, sha256
from src.task3.sft_v1_experiment import Journal, preserve_rng, training_arguments, write_json
from src.task3.sft_v1_runtime import adapter_identity, evaluating, generate, gpu_cost, tensor_digest, verify_frozen


def base_fingerprint(model):
    """Frozen flags plus a deterministic sample from every base tensor (no full-weight copies)."""
    import torch
    values = {}
    for name, p in model.named_parameters():
        if 'lora_' in name:
            continue
        if p.requires_grad:
            raise ValueError('base parameter unexpectedly trainable: ' + name)
        flat = p.detach().reshape(-1)
        values[name] = tensor_digest(torch.cat((flat[:32], flat[-32:])))
    return values


def new_adapter(base, config):
    from transformers import set_seed
    from peft import LoraConfig, get_peft_model
    set_seed(config['seed'])
    r = config['training']
    peft = LoraConfig(r=r['lora_r'], lora_alpha=r['lora_alpha'], lora_dropout=r['lora_dropout'],
                      target_modules=r['target_modules'], bias='none', task_type='CAUSAL_LM')
    model = get_peft_model(base, peft)
    trainable = [name for name,p in model.named_parameters() if p.requires_grad]
    if not trainable or any('lora_' not in name for name in trainable):
        raise ValueError('only intended LoRA parameters may be trainable')
    return model


def audited_train(repo, out, model, tokenizer, train_rows, dev_rows, examples, manifest,
                  journal, kind, checkpoint_eval=None, resume=None):
    import torch
    from transformers import TrainingArguments, TrainerCallback
    from scripts.task3_sft_v1_prepare import audit_batch
    directory = out / kind; directory.mkdir(exist_ok=True)
    expected_steps = 4 if kind == 'smoke' else 160
    args = TrainingArguments(**training_arguments(manifest['config'], directory, smoke=kind=='smoke'))
    trainer = make_trainer(model, args, train_rows, dev_rows, tokenizer.pad_token_id)
    initial = adapter_identity(model)
    initial_path = directory / 'initial-adapter-identity.json'
    if resume and initial_path.exists():
        initial = json.loads(initial_path.read_text())
    frozen_base = base_fingerprint(model)
    write_json(directory / 'actual-training-arguments.json', args.to_dict())
    write_json(directory / 'peft-config.json', json.loads(json.dumps(model.peft_config['default'].to_dict(),
               default=lambda v: sorted(v) if isinstance(v,set) else str(v))))
    if not initial_path.exists():
        write_json(initial_path, initial)
    by_id = {e['example_id']:e for e in examples}
    by_row = {r['example_id']:r for r in train_rows}
    with preserve_rng():
        batch = next(iter(trainer.get_train_dataloader()))
        audit_batch(batch, by_row, by_id, tokenizer)
        ordered = sorted(train_rows,key=lambda r:len(r['input_ids']))
        stress = trainer.data_collator([ordered[0],ordered[-1]])
        pads = audit_batch(stress,by_row,by_id,tokenizer)
        write_json(directory / 'real-gpu-minibatch.json', dict(
            scope='actual Qwen PEFT Trainer dataloader before optimizer', actual_qwen_training_minibatch_checked=True,
            first={k:v.tolist() if hasattr(v,'tolist') else v for k,v in batch.items()},
            padding_tokens_checked=pads, full_json_and_ending=True, prompt_header_padding_masked=True,
            model_forward_allowed_keys=['input_ids','attention_mask','use_cache'],
            stress={k:v.tolist() if hasattr(v,'tolist') else v for k,v in stress.items()}))
    original_loss = trainer.compute_loss
    def compute_loss(model_arg, inputs, return_outputs=False, num_items_in_batch=None):
        if model_arg.training:
            for eid in inputs['example_id']:
                journal.append(dict(type='train_forward', kind=kind, example_id=eid,
                                    optimizer_step=trainer.state.global_step))
        return original_loss(model_arg, inputs, return_outputs, num_items_in_batch)
    trainer.compute_loss = compute_loss
    def forward_guard(module, args_, kwargs):
        if module.training and (args_ or set(kwargs) != {'input_ids','attention_mask','use_cache'}):
            raise ValueError('unexpected private metadata or fields in real model.forward')
    hook = model.register_forward_pre_hook(forward_guard, with_kwargs=True)
    gradients=[]; evaluation_wall=[]
    class Audit(TrainerCallback):
        def on_train_begin(self, args, state, control, **kw):
            if state.max_steps != expected_steps or len(trainer.get_train_dataloader()) != expected_steps*4:
                raise ValueError('actual Trainer schedule is not expected one-epoch steps')
            journal.append(dict(type='trainer_schedule', kind=kind, max_steps=state.max_steps,
                                rows=len(train_rows), accumulation=args.gradient_accumulation_steps,
                                model_accepts_loss_kwargs=trainer.model_accepts_loss_kwargs,
                                normalization='completion mean per example, Trainer divides by four microbatches'))
        def on_pre_optimizer_step(self, args, state, control, **kw):
            verify_frozen(repo,out,manifest)
            grads=[p.grad for p in model.parameters() if p.requires_grad and p.grad is not None]
            if not grads or not all(bool(g.isfinite().all()) for g in grads) or not any(bool(g.count_nonzero()) for g in grads):
                raise ValueError('missing/nonfinite/all-zero adapter gradients')
            row=dict(step=state.global_step+1, finite=True, nonzero_tensors=sum(bool(g.count_nonzero()) for g in grads),
                     gradient_tensors=len(grads), lr=trainer.optimizer.param_groups[0]['lr'])
            gradients.append(row); journal.append(dict(type='optimizer_intent', kind=kind, **row))
        def on_step_end(self, args, state, control, **kw):
            journal.append(dict(type='optimizer_completed', kind=kind, step=state.global_step))
        def on_log(self,args,state,control,logs=None,**kw):
            Journal(directory/'training-log.jsonl').append(dict(step=state.global_step,**(logs or {})))
        def on_save(self,args,state,control,**kw):
            path=directory/f'checkpoint-{state.global_step}'
            required=['optimizer.pt','scheduler.pt','rng_state.pth','trainer_state.json','adapter_model.safetensors']
            if any(not (path/n).exists() for n in required):
                raise ValueError('incomplete native resumable checkpoint')
            write_json(path/'checkpoint-identity.json',{n:sha256(path/n) for n in required})
            journal.append(dict(type='checkpoint_saved',kind=kind,step=state.global_step,path=str(path)))
            if checkpoint_eval:
                tick=time.perf_counter()
                checkpoint_eval(model,state.global_step)
                evaluation_wall.append(time.perf_counter()-tick)
    trainer.add_callback(Audit())
    marker=directory/'started.json'
    if marker.exists() and resume is None:
        raise ValueError('training already started; explicit safe checkpoint resume required')
    if resume:
        checkpoint_state=json.loads((Path(resume)/'trainer_state.json').read_text())
        last=max([e['step'] for e in journal.events() if e.get('type') in ('optimizer_intent','optimizer_completed') and e.get('kind')==kind],default=0)
        if last != checkpoint_state['global_step']:
            raise ValueError('journal has progress beyond checkpoint; refusing silent optimizer replay')
    else:
        write_json(marker,dict(initial_identity=initial,expected_steps=expected_steps))
    start=time.perf_counter();torch.cuda.reset_peak_memory_stats()
    try:
        result=trainer.train(resume_from_checkpoint=str(resume) if resume else None)
        torch.cuda.synchronize()
        if trainer.state.global_step != expected_steps:
            raise ValueError('main/smoke step count mismatch')
        forwards=[e['example_id'] for e in journal.events() if e.get('type')=='train_forward' and e.get('kind')==kind]
        if Counter(forwards)!=Counter({r['example_id']:1 for r in train_rows}):
            raise ValueError('training did not expose each target exactly once')
        final=adapter_identity(model)
        changed=[name for name,value in initial.items() if final[name]!=value]
        if not changed or base_fingerprint(model)!=frozen_base:
            raise ValueError('adapter did not change or frozen base changed')
        scheduler_steps=trainer.lr_scheduler.last_epoch
        optimizer_steps=max(int(v['step']) for v in trainer.optimizer.state.values() if 'step' in v)
        if scheduler_steps!=expected_steps or optimizer_steps!=expected_steps:
            raise ValueError('actual optimizer/scheduler counters mismatch')
        result=dict(status='complete',actual_optimizer_steps=trainer.state.global_step,
            actual_scheduler_steps=scheduler_steps,actual_optimizer_state_steps=optimizer_steps,
            actual_train_forward_calls=len(forwards),changed_adapter_tensors=len(changed),
            all_base_parameters_frozen=True,base_tensor_samples_unchanged=True,
            adapter_identity=final,gradients=gradients,training_metrics=result.metrics,
            checkpoint_evaluation_wall_s=sum(evaluation_wall),**gpu_cost(start))
        result['training_wall_excluding_checkpoint_evaluation_s']=result['wall_s']-sum(evaluation_wall)
        write_json(directory/'training-result.json',result)
        return trainer,result
    finally:
        hook.remove()


def smoke(repo,out,base,tokenizer,examples,rows,manifest,journal):
    import torch
    from peft import PeftModel
    selected=set(manifest['smoke_ids'])
    train=[r for r in rows['train'] if r['example_id'] in selected]
    model=new_adapter(base,manifest['config'])
    trainer,result=audited_train(repo,out,model,tokenizer,train,rows['dev'],examples['train'],manifest,journal,'smoke')
    adapter=out/'smoke'/'adapter';model.save_pretrained(adapter,safe_serialization=True);tokenizer.save_pretrained(adapter)
    initial_identity=json.loads((out/'smoke'/'initial-adapter-identity.json').read_text())
    fixed=next(e for e in examples['train'] if e['example_id']==manifest['smoke_ids'][0])
    inputs=tokenizer.apply_chat_template(fixed['prompt'],tokenize=True,add_generation_prompt=True,
                                        return_tensors='pt',return_dict=True)
    inputs={k:v.cuda() for k,v in inputs.items()}
    with evaluating(model),torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        before=model(**inputs,use_cache=False,logits_to_keep=1).logits.detach().float().cpu()
        gen_before=generate(model,tokenizer,fixed,manifest['generation'],journal,'smoke-before/'+fixed['example_id'])
    saved=adapter_identity(model)
    base=model.unload();del trainer,model;gc.collect();torch.cuda.empty_cache()
    model=PeftModel.from_pretrained(base,str(adapter),is_trainable=False)
    if adapter_identity(model)!=saved:
        raise ValueError('smoke saved/reloaded adapter tensor identity differs')
    with evaluating(model),torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        after=model(**inputs,use_cache=False,logits_to_keep=1).logits.detach().float().cpu()
        gen_after=generate(model,tokenizer,fixed,manifest['generation'],journal,'smoke-after/'+fixed['example_id'])
    atol,rtol=.002,.001
    equal=bool(torch.allclose(before,after,atol=atol,rtol=rtol))
    torch.save(dict(before=before,after=after),out/'smoke'/'reload-logits.pt')
    write_json(out/'smoke'/'reload-audit.json',dict(passed=equal,example_id=fixed['example_id'],
        logits_scope='all vocabulary logits at last prompt position',atol=atol,rtol=rtol,
        max_abs_difference=float((before-after).abs().max()),saved_adapter_tensor_identity_verified=True,
        generation_before=gen_before,generation_after=gen_after,
        exact_generation_match=gen_before['raw']==gen_after['raw']))
    if not equal:
        raise ValueError('smoke reload logits exceed frozen tolerance')
    base=model.unload();del model;gc.collect();torch.cuda.empty_cache()
    write_json(out/'smoke'/'complete.json',dict(status='complete',optimizer_steps=4,generations=2,
               initial_adapter_identity=initial_identity))
    return base
