"""Bounded v2 main trajectory using the audited v1 native Trainer components.

Smoke remains in sft_v1_training. The historical selection configuration field
is accepted only by the unchanged recipe validator; selection is external.
"""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import time

from src.task3.sft_v1 import make_trainer, sha256
from src.task3.sft_v1_experiment import Journal, preserve_rng, training_arguments, write_json
from src.task3.sft_v1_runtime import adapter_identity, gpu_cost, verify_frozen
from src.task3.sft_v1_training import base_fingerprint, new_adapter


EXPECTED_ROWS = 960
EXPECTED_STEPS = 240
SAVE_STEPS = (120, 240)
CHECKPOINT_FILES = ('optimizer.pt', 'scheduler.pt', 'rng_state.pth', 'trainer_state.json',
                    'adapter_model.safetensors', 'adapter_config.json')


def main_training_arguments(config, directory):
    """Apply the exact v1 recipe; only the authorized save interval changes."""
    values = training_arguments(config, directory, smoke=False)
    values['save_steps'] = 120
    return values


def validate_rows(rows):
    if len(rows) != EXPECTED_ROWS:
        raise ValueError('main requires exactly 960 targets')
    if len({r['example_id'] for r in rows}) != EXPECTED_ROWS:
        raise ValueError('all 960 target IDs must be unique')
    sources = defaultdict(list)
    for row in rows:
        if row.get('loss_weight') != 1.:
            raise ValueError('main requires equal-example weight one')
        sources[row['sample_id']].append(row['level'])
    if len(sources) != 240 or any(sorted(levels) != [1,2,3,4] for levels in sources.values()):
        raise ValueError('main requires 240 sources with all four Levels once')


def validate_start(directory, resume, journal, kind='main'):
    """Reject overwrite and optimizer replay before creating or modifying artifacts."""
    directory = Path(directory)
    events = [e for e in journal.events() if e.get('kind') == kind]
    if resume is None:
        if directory.exists() and any(directory.iterdir()):
            raise ValueError('main already contains outputs; explicit safe checkpoint resume required')
        if any(e.get('type') in ('train_forward','optimizer_intent','optimizer_completed') for e in events):
            raise ValueError('journal already contains training progress')
        return 0
    checkpoint = Path(resume).resolve()
    if checkpoint.parent != directory.resolve():
        raise ValueError('resume checkpoint must be inside this main output directory')
    if not (directory/'started.json').is_file() or not (directory/'initial-adapter-identity.json').is_file():
        raise ValueError('resume requires original main start and adapter identity')
    identity_path = checkpoint/'checkpoint-identity.json'
    if not identity_path.is_file():
        raise ValueError('resume checkpoint identity missing')
    identity = json.loads(identity_path.read_text())
    if set(identity) != set(CHECKPOINT_FILES):
        raise ValueError('resume checkpoint identity file set differs')
    for name, expected in identity.items():
        if not (checkpoint/name).is_file() or sha256(checkpoint/name) != expected:
            raise ValueError('resume checkpoint identity changed: ' + name)
    state = json.loads((checkpoint/'trainer_state.json').read_text())
    step = state.get('global_step')
    if type(step) is not int or step not in SAVE_STEPS or checkpoint.name != f'checkpoint-{step}':
        raise ValueError('resume checkpoint is outside the authorized schedule')
    progress = {kind_: [e['step'] for e in events if e.get('type') == kind_]
                for kind_ in ('optimizer_intent','optimizer_completed')}
    expected_steps = list(range(1, step+1))
    if any(values != expected_steps for values in progress.values()):
        raise ValueError('journal progress differs from checkpoint or extends beyond checkpoint; refusing optimizer replay')
    return step


def audited_train(repo, out, model, tokenizer, train_rows, dev_rows, examples, manifest,
                  journal, kind='main', checkpoint_eval=None, resume=None):
    import torch
    from transformers import TrainingArguments, TrainerCallback
    from scripts.task3_sft_v1_prepare import audit_batch

    if kind != 'main':
        raise ValueError('v2 module handles main only; reuse the original v1 smoke')
    repo, out = Path(repo), Path(out)
    directory = out/kind
    validate_rows(train_rows)
    resumed_step = validate_start(directory, resume, journal, kind)
    by_id = {e['example_id']:e for e in examples}
    by_row = {r['example_id']:r for r in train_rows}
    if len(by_id) != len(examples) or set(by_id) != set(by_row):
        raise ValueError('training examples and encoded targets must bind one-to-one')
    if set(by_row) & {r['example_id'] for r in dev_rows}:
        raise ValueError('train and dev target IDs overlap')
    verify_frozen(repo,out,manifest)
    args = TrainingArguments(**main_training_arguments(manifest['config'], directory))
    if not args.skip_memory_metrics:
        raise ValueError('Trainer memory tracker must remain disabled to preserve whole-main peak counters')
    trainer = make_trainer(model, args, train_rows, dev_rows, tokenizer.pad_token_id)
    initial_path = directory/'initial-adapter-identity.json'
    initial = json.loads(initial_path.read_text()) if resume else adapter_identity(model)
    frozen_base = base_fingerprint(model)
    fingerprint_path = directory/'frozen-base-fingerprint.json'
    if resume and (not fingerprint_path.exists() or json.loads(fingerprint_path.read_text()) != frozen_base):
        raise ValueError('resumed frozen base differs from original main fingerprint')
    prior_forwards = [e['example_id'] for e in journal.events()
                      if e.get('type') == 'train_forward' and e.get('kind') == kind]
    if (len(prior_forwards) != resumed_step*4 or len(set(prior_forwards)) != len(prior_forwards)
            or not set(prior_forwards) <= set(by_row)):
        raise ValueError('resume target-exposure journal is inconsistent with optimizer progress')
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory/'actual-training-arguments.json',args.to_dict())
    write_json(directory/'peft-config.json',json.loads(json.dumps(model.peft_config['default'].to_dict(),
               default=lambda v:sorted(v) if isinstance(v,set) else str(v))))
    if not resume:
        write_json(initial_path,initial)
        write_json(fingerprint_path,frozen_base)
    with preserve_rng():
        batch = next(iter(trainer.get_train_dataloader()))
        audit_batch(batch,by_row,by_id,tokenizer)
        ordered = sorted(train_rows,key=lambda r:len(r['input_ids']))
        stress = trainer.data_collator([ordered[0],ordered[-1]])
        pads = audit_batch(stress,by_row,by_id,tokenizer)
        write_json(directory/('resumed-real-gpu-minibatch.json' if resume else 'real-gpu-minibatch.json'),dict(
            scope='actual Qwen PEFT Trainer dataloader before optimizer',
            actual_qwen_training_minibatch_checked=True,
            first={k:v.tolist() if hasattr(v,'tolist') else v for k,v in batch.items()},
            padding_tokens_checked=pads,full_json_and_ending=True,prompt_header_padding_masked=True,
            model_forward_allowed_keys=['input_ids','attention_mask','use_cache'],
            stress={k:v.tolist() if hasattr(v,'tolist') else v for k,v in stress.items()}))
    original_loss = trainer.compute_loss
    def compute_loss(model_arg,inputs,return_outputs=False,num_items_in_batch=None):
        if model_arg.training:
            audit_batch(inputs,by_row,by_id,tokenizer)
            for eid in inputs['example_id']:
                journal.append(dict(type='train_forward',kind=kind,example_id=eid,
                                    optimizer_step=trainer.state.global_step))
        value = original_loss(model_arg,inputs,return_outputs,num_items_in_batch)
        loss = value[0] if return_outputs else value
        if not bool(torch.isfinite(loss.detach()).all()):
            raise ValueError('nonfinite assistant-completion loss')
        return value
    trainer.compute_loss = compute_loss
    def forward_guard(module,args_,kwargs):
        if module.training and (args_ or set(kwargs) != {'input_ids','attention_mask','use_cache'}):
            raise ValueError('unexpected private metadata or fields in real model.forward')
    hook = model.register_forward_pre_hook(forward_guard,with_kwargs=True)
    gradients=[];evaluation_wall=[]
    class Audit(TrainerCallback):
        def on_train_begin(self,args,state,control,**kw):
            if (state.max_steps != EXPECTED_STEPS or len(trainer.get_train_dataloader()) != EXPECTED_ROWS
                    or args.gradient_accumulation_steps != 4 or args.world_size != 1):
                raise ValueError('actual Trainer schedule differs from 960 targets and 240 accumulated steps')
            journal.append(dict(type='trainer_schedule',kind=kind,max_steps=state.max_steps,
                rows=len(train_rows),accumulation=args.gradient_accumulation_steps,resumed_from_step=resumed_step,
                model_accepts_loss_kwargs=trainer.model_accepts_loss_kwargs,
                normalization='completion mean per example, Trainer divides by four microbatches'))
        def on_pre_optimizer_step(self,args,state,control,**kw):
            verify_frozen(repo,out,manifest)
            grads=[p.grad for p in model.parameters() if p.requires_grad and p.grad is not None]
            if not grads or not all(bool(g.isfinite().all()) for g in grads) or not any(bool(g.count_nonzero()) for g in grads):
                raise ValueError('missing/nonfinite/all-zero adapter gradients')
            row=dict(step=state.global_step+1,finite=True,
                     nonzero_tensors=sum(bool(g.count_nonzero()) for g in grads),
                     gradient_tensors=len(grads),lr=trainer.optimizer.param_groups[0]['lr'])
            if not math.isfinite(row['lr']):raise ValueError('nonfinite optimizer learning rate')
            gradients.append(row);journal.append(dict(type='optimizer_intent',kind=kind,**row))
        def on_step_end(self,args,state,control,**kw):
            journal.append(dict(type='optimizer_completed',kind=kind,step=state.global_step,
                peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_reserved_bytes=torch.cuda.max_memory_reserved()))
        def on_log(self,args,state,control,logs=None,**kw):
            Journal(directory/'training-log.jsonl').append(dict(step=state.global_step,**(logs or {})))
        def on_save(self,args,state,control,**kw):
            if state.global_step not in SAVE_STEPS:raise ValueError('checkpoint outside steps120/240')
            path=directory/f'checkpoint-{state.global_step}'
            if any(not (path/name).is_file() for name in CHECKPOINT_FILES):
                raise ValueError('incomplete native resumable checkpoint')
            write_json(path/'checkpoint-identity.json',{name:sha256(path/name) for name in CHECKPOINT_FILES})
            journal.append(dict(type='checkpoint_saved',kind=kind,step=state.global_step,path=str(path)))
            if checkpoint_eval:
                tick=time.perf_counter()
                try:
                    with preserve_rng():checkpoint_eval(model,state.global_step)
                finally:
                    elapsed=time.perf_counter()-tick;evaluation_wall.append(elapsed)
                    journal.append(dict(type='checkpoint_evaluation_wall',kind=kind,step=state.global_step,wall_s=elapsed))
    trainer.add_callback(Audit())
    if not resume:
        write_json(directory/'started.json',dict(initial_identity=initial,expected_steps=EXPECTED_STEPS,
            target_count=EXPECTED_ROWS,checkpoints=list(SAVE_STEPS)))
    # Exactly one reset in this module, immediately before the main Trainer call.
    # Nested checkpoint evaluation is required to retain these global counters.
    start=time.perf_counter();torch.cuda.reset_peak_memory_stats()
    try:
        trained=trainer.train(resume_from_checkpoint=str(resume) if resume else None)
        torch.cuda.synchronize()
        if trainer.state.global_step != EXPECTED_STEPS:raise ValueError('main step count mismatch')
        events=[e for e in journal.events() if e.get('kind')==kind]
        forwards=[e['example_id'] for e in events if e.get('type')=='train_forward']
        if Counter(forwards) != Counter({r['example_id']:1 for r in train_rows}):
            raise ValueError('training did not expose each of 960 targets exactly once')
        for event_type in ('optimizer_intent','optimizer_completed'):
            if [e['step'] for e in events if e.get('type')==event_type] != list(range(1,EXPECTED_STEPS+1)):
                raise ValueError('optimizer journal does not contain exactly 240 ordered steps')
        if [e['step'] for e in events if e.get('type')=='checkpoint_saved'] != list(SAVE_STEPS):
            raise ValueError('main checkpoints do not match exactly steps120/240')
        final=adapter_identity(model)
        if set(final)!=set(initial):raise ValueError('adapter tensor names changed')
        changed=[name for name,value in initial.items() if final[name]!=value]
        if not changed or base_fingerprint(model)!=frozen_base:
            raise ValueError('adapter did not change or frozen base changed')
        scheduler_steps=trainer.lr_scheduler.last_epoch
        optimizer_steps=[int(v['step']) for v in trainer.optimizer.state.values() if 'step' in v]
        if scheduler_steps!=EXPECTED_STEPS or not optimizer_steps or set(optimizer_steps)!={EXPECTED_STEPS}:
            raise ValueError('actual optimizer/scheduler counters mismatch')
        cost=gpu_cost(start)
        result=dict(status='complete',actual_optimizer_steps=trainer.state.global_step,
            actual_scheduler_steps=scheduler_steps,actual_optimizer_state_steps=EXPECTED_STEPS,
            actual_train_forward_calls=len(forwards),changed_adapter_tensors=len(changed),
            all_base_parameters_frozen=True,base_tensor_samples_unchanged=True,adapter_identity=final,
            gradients=[{k:e[k] for k in ('step','finite','nonzero_tensors','gradient_tensors','lr')}
                       for e in events if e.get('type')=='optimizer_intent'],
            training_metrics=trained.metrics,resumed_from_step=resumed_step,
            checkpoint_evaluation_wall_s=sum(evaluation_wall),
            wall_measurement_scope='Current main Trainer invocation; wall excluding evaluation subtracts both nested checkpoint callbacks in this invocation.',
            peak_memory_scope='Entire main Trainer interval in this process, including nested checkpoint evaluation; one reset before train.',
            peak_counter_resets_this_invocation=1,**cost)
        result['training_wall_excluding_checkpoint_evaluation_s']=cost['wall_s']-sum(evaluation_wall)
        result['trajectory_observed_peak_allocated_bytes']=max([cost['peak_allocated_bytes']]+
            [e['peak_allocated_bytes'] for e in events if 'peak_allocated_bytes' in e])
        result['trajectory_observed_peak_reserved_bytes']=max([cost['peak_reserved_bytes']]+
            [e['peak_reserved_bytes'] for e in events if 'peak_reserved_bytes' in e])
        result['trajectory_peak_scope']='Current whole-main interval plus persisted step-boundary peaks from earlier resumed intervals; an interrupted interval after its last journal entry is not recoverable.'
        write_json(directory/'training-result.json',result)
        return trainer,result
    finally:
        hook.remove()
