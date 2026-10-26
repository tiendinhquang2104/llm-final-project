"""Controlled, journaled first QLoRA experiment for the native SFT v1 task."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    temp.replace(path)


class Journal:
    def __init__(self, path):
        self.path = Path(path)

    def events(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()] if self.path.exists() else []

    def append(self, event):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(), **event),
                               ensure_ascii=False, allow_nan=False) + '\n')
            f.flush(); os.fsync(f.fileno())

    def reserved(self):
        return {e['key'] for e in self.events() if e.get('type') == 'generation_reserved'}

    def reserve(self, key, budget):
        reserved = self.reserved()
        if key in reserved:
            raise ValueError('generation already reserved: ' + key)
        if len(reserved) >= budget:
            raise ValueError('generation budget exhausted')
        self.append(dict(type='generation_reserved', key=key))


def capture_rng():
    import numpy as np
    import torch
    return dict(python=random.getstate(), numpy=np.random.get_state(), torch=torch.get_rng_state(),
                cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [])


def restore_rng(state):
    import numpy as np
    import torch
    random.setstate(state['python']); np.random.set_state(state['numpy'])
    torch.set_rng_state(state['torch'].cpu())
    if state['cuda']:
        torch.cuda.set_rng_state_all([s.cpu() for s in state['cuda']])


@contextmanager
def preserve_rng():
    state = capture_rng()
    try:
        yield
    finally:
        restore_rng(state)


def select_checkpoint(base_loss, losses):
    if set(losses) != {80, 160} or not all(math.isfinite(v) for v in [base_loss, *losses.values()]):
        raise ValueError('selection requires finite base and both fixed-dev losses')
    step = min(losses, key=lambda k: (losses[k], k))
    return dict(step=step, dev_loss=losses[step], base_dev_loss=base_loss,
                rule='minimum_fixed_dev_equal_example_completion_loss_earliest_exact_tie',
                improves_base_dev_loss=losses[step] < base_loss,
                promotion_decision='separate_source_grounded_quality_review_required')


def smoke_ids(examples):
    sources = {}
    for e in examples:
        sources[e['sample_id']] = not json.loads(e['completion'])['taxonomy_error']
    rng = random.Random(42)
    chosen = set(rng.sample(sorted(s for s, clean in sources.items() if clean), 2)
                 + rng.sample(sorted(s for s, clean in sources.items() if not clean), 2))
    return [e['example_id'] for e in examples if e['sample_id'] in chosen]


def pending_checkpoint_evaluations(resume_step, complete_steps):
    return [step for step in (80,160) if step<=resume_step and step not in complete_steps]


def training_arguments(config, out, smoke=False):
    from src.task3.sft_v1 import validate_data_policy
    validate_data_policy(config)
    expected = dict(max_seq_length=8192, epochs=1, per_device_train_batch_size=1,
        gradient_accumulation_steps=4, learning_rate=2e-5, optim='adamw_torch', weight_decay=0.,
        max_grad_norm=1., lr_scheduler_type='cosine', warmup_ratio=.03, precision='bf16',
        quantization='nf4_double_quant_bf16_compute', load_in_4bit=True,
        lora_r=16, lora_alpha=32, lora_dropout=.05,
        target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
        gradient_checkpointing=True, gradient_checkpointing_use_reentrant=False, packing=False,
        remove_unused_columns=False, loss='equal_example_mean_of_assistant_completion_cross_entropy',
        loss_weight=1., sampling='one_seeded_shuffle_of_train_rows_without_replacement',
        checkpoint_selection='fixed_dev_equal_example_completion_loss_earliest_tie')
    recipe = config['training']
    for key in set(recipe) | set(expected):
        if key not in expected or recipe.get(key) != expected[key]:
            raise ValueError('unsupported or changed training setting: ' + key)
    if config['seed'] != 42:
        raise ValueError('seed must be 42')
    return dict(output_dir=str(out), seed=config['seed'], data_seed=config['seed'],
        num_train_epochs=recipe['epochs'], per_device_train_batch_size=recipe['per_device_train_batch_size'],
        per_device_eval_batch_size=1, gradient_accumulation_steps=recipe['gradient_accumulation_steps'],
        learning_rate=recipe['learning_rate'], optim=recipe['optim'], weight_decay=recipe['weight_decay'],
        max_grad_norm=recipe['max_grad_norm'], lr_scheduler_type=recipe['lr_scheduler_type'],
        warmup_ratio=recipe['warmup_ratio'], bf16=True, fp16=False,
        gradient_checkpointing=recipe['gradient_checkpointing'],
        gradient_checkpointing_kwargs={'use_reentrant': recipe['gradient_checkpointing_use_reentrant']},
        remove_unused_columns=recipe['remove_unused_columns'], eval_strategy='no',
        save_strategy='no' if smoke else 'steps', save_steps=80, save_only_model=False,
        logging_steps=1, report_to=[], push_to_hub=False, dataloader_num_workers=0,
        dataloader_drop_last=False, disable_tqdm=True, load_best_model_at_end=False,
        save_safetensors=True, label_names=['labels'])


def run(repo, out, config_path, reuse, request, resume=False):
    import gc
    import time
    import torch
    from peft import PeftModel, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from src.task3.sft_v1 import load_split, read_jsonl, sha256, verify_checksums
    from src.task3.pilot_training import _model_precision_audit
    from src.task3.sft_v1_runtime import freeze, verify_frozen, evaluate, adapter_identity
    from src.task3.sft_v1_training import smoke, new_adapter, audited_train
    from src.task3.sft_v1_evaluation import write_casebook
    if resume:
        manifest=json.loads((out/'manifest.json').read_text());verify_frozen(repo,out,manifest)
        config=manifest['config'];root=repo/config['dataset_root']
        tokenizer=AutoTokenizer.from_pretrained(config['tokenizer_local'],local_files_only=True,trust_remote_code=False)
        examples={s:load_split(root,s) for s in ('train','dev','test')}
        reuse=Path(manifest['preflight'])
        rows={s:read_jsonl(reuse/(s+'.encoded.private.jsonl')) for s in examples}
    else:
        manifest,tokenizer,examples,rows=freeze(repo,out,config_path,reuse,request)
        config=manifest['config']
    journal=Journal(out/'journal.jsonl');journal.append(dict(type='execution_started',resume=resume))
    write_json(out/'status.json',dict(status='running',phase='model_load'))
    start=time.perf_counter()
    try:
        if torch.cuda.device_count()!=1 or not torch.cuda.is_bf16_supported():
            raise ValueError('one BF16-capable GPU required')
        torch.cuda.set_device(0)
        tick=time.perf_counter();journal.append(dict(type='base_model_load_started'))
        base=AutoModelForCausalLM.from_pretrained(config['model_id'],revision=config['revision'],
            cache_dir=str(Path(config['tokenizer_local']).parents[2]),local_files_only=True,trust_remote_code=False,
            quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
                bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16),
            dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa')
        precision=_model_precision_audit(base,config['revision'])
        base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=True,
                                            gradient_checkpointing_kwargs={'use_reentrant':False})
        base.config.use_cache=False
        journal.append(dict(type='base_model_load_completed',wall_s=time.perf_counter()-tick,precision=precision))
        write_json(out/'model-audit.json',dict(precision=precision,gpu=torch.cuda.get_device_name(0),
            parameters_frozen=all(not p.requires_grad for p in base.parameters()),
            quantization='NF4 double quantized base; BF16 compute, not all weights stored BF16',
            preparation='prepare_model_for_kbit_training applied before baseline and adapters'))
        verify_frozen(repo,out,manifest)
        write_json(out/'status.json',dict(status='running',phase='base-dev'))
        baseline=evaluate(base,tokenizer,examples['dev'],rows['dev'],out/'base-dev',manifest,journal,'base-dev')
        if not (out/'smoke'/'complete.json').exists():
            if (out/'smoke'/'started.json').exists():
                raise ValueError('interrupted disposable smoke needs explicit diagnosis, not silent restart')
            write_json(out/'status.json',dict(status='running',phase='smoke'))
            base=smoke(repo,out,base,tokenizer,examples,rows,manifest,journal)
        write_json(out/'status.json',dict(status='running',phase='main'))
        if not (out/'main'/'training-result.json').exists():
            model=new_adapter(base,config)
            fresh=adapter_identity(model)
            smoke_initial=json.loads((out/'smoke'/'complete.json').read_text())['initial_adapter_identity']
            if fresh!=smoke_initial:
                raise ValueError('main initial adapter is not the fresh seeded pre-smoke state')
            write_json(out/'main-freshness.json',dict(passed=True,initial_equals_pre_smoke=True,
                smoke_updates_not_carried=True,optimizer_and_scheduler='new native Trainer instances',initial_identity=fresh))
            def checkpoint_eval(m,step):
                evaluate(m,tokenizer,examples['dev'],rows['dev'],out/f'step-{step}-dev',manifest,journal,f'step-{step}-dev')
            checkpoint=None
            if (out/'main'/'started.json').exists():
                if not resume:
                    raise ValueError('explicit resume required')
                candidates=[p for p in (out/'main').glob('checkpoint-*') if (p/'checkpoint-identity.json').exists()]
                if not candidates:
                    raise ValueError('no complete checkpoint; refusing to repeat main trajectory')
                checkpoint=max(candidates,key=lambda p:int(p.name.split('-')[-1]))
                for name,expected in json.loads((checkpoint/'checkpoint-identity.json').read_text()).items():
                    if sha256(checkpoint/name)!=expected:
                        raise ValueError('resume checkpoint changed')
                from safetensors.torch import load_file
                from peft import set_peft_model_state_dict
                complete_steps={s for s in (80,160) if (out/f'step-{s}-dev'/'complete.json').exists()}
                for step in pending_checkpoint_evaluations(int(checkpoint.name.split('-')[-1]),complete_steps):
                    path=out/'main'/f'checkpoint-{step}'/'adapter_model.safetensors'
                    set_peft_model_state_dict(model,load_file(str(path)))
                    checkpoint_eval(model,step)
            trainer,_=audited_train(repo,out,model,tokenizer,rows['train'],rows['dev'],examples['train'],
                                    manifest,journal,'main',checkpoint_eval,checkpoint)
            del trainer;gc.collect();torch.cuda.empty_cache()
        else:
            model=PeftModel.from_pretrained(base,str(out/'main'/'checkpoint-160'),is_trainable=False)
            journal.append(dict(type='adapter_loaded',role='completed_main_step160'))
        losses={step:json.loads((out/f'step-{step}-dev'/'complete.json').read_text())['mean_loss'] for step in (80,160)}
        selection=select_checkpoint(baseline['mean_loss'],losses)
        selection['checkpoint']=str(out/'main'/f"checkpoint-{selection['step']}")
        if (out/'selection.json').exists() and json.loads((out/'selection.json').read_text())!=selection:
            raise ValueError('persisted checkpoint selection differs')
        write_json(out/'selection.json',selection)
        journal.append(dict(type='selection_persisted',step=selection['step']))
        write_json(out/'status.json',dict(status='running',phase='test-after-selection'))
        with model.disable_adapter():
            evaluate(model,tokenizer,examples['test'],rows['test'],out/'base-test',manifest,journal,'base-test')
        base=model.unload();del model;gc.collect();torch.cuda.empty_cache()
        model=PeftModel.from_pretrained(base,selection['checkpoint'],is_trainable=False)
        journal.append(dict(type='adapter_loaded',role='selected_test',step=selection['step']))
        evaluate(model,tokenizer,examples['test'],rows['test'],out/'selected-test',manifest,journal,'selected-test')
        for split,names in [('dev',['base-dev','step-80-dev','step-160-dev']),('test',['base-test','selected-test'])]:
            write_casebook(out/(split+'-paired.html'),examples[split],
                {name:read_jsonl(out/name/'generations.jsonl') for name in names},
                {name:json.loads((out/name/'complete.json').read_text())['mean_loss'] for name in names})
        verify_frozen(repo,out,manifest)
        verify_checksums(repo/config['dataset_root'])
        events=journal.events()
        counts=dict(base_model_loads=sum(e.get('type')=='base_model_load_completed' for e in events),
            primary_generations=sum(e.get('type')=='generation_completed' and not e['key'].startswith('smoke-') for e in events),
            smoke_generations=sum(e.get('type')=='generation_completed' and e['key'].startswith('smoke-') for e in events),
            smoke_optimizer_steps=sum(e.get('type')=='optimizer_completed' and e.get('kind')=='smoke' for e in events),
            main_optimizer_steps=sum(e.get('type')=='optimizer_completed' and e.get('kind')=='main' for e in events))
        counts['primary_reservations']=sum(e.get('type')=='generation_reserved' and not e['key'].startswith('smoke-') for e in events)
        counts['smoke_reservations']=sum(e.get('type')=='generation_reserved' and e['key'].startswith('smoke-') for e in events)
        counts['generations_with_uncertain_completion']=sum(e.get('type')=='generation_interrupted_unknown' for e in events)
        if counts['primary_reservations']!=400 or counts['smoke_reservations']!=2 or counts['main_optimizer_steps']!=160 or counts['smoke_optimizer_steps']!=4:
            raise ValueError('actual counts differ from authorized experiment')
        summaries={name:json.loads((out/name/'complete.json').read_text()) for name in
                   ('base-dev','step-80-dev','step-160-dev','base-test','selected-test')}
        write_json(out/'execution-result.json',dict(status='execution_complete_quality_review_pending',counts=counts,
                   selection=selection,evaluations=summaries,process_wall_s=time.perf_counter()-start))
        write_json(out/'status.json',dict(status='execution_complete_quality_review_pending',counts=counts))
        print(json.dumps(dict(execution_complete=True,counts=counts,selection=selection),ensure_ascii=False,indent=2),flush=True)
    except Exception as exc:
        journal.append(dict(type='technical_failure',error=str(exc)))
        write_json(out/'status.json',dict(status='technical_failure',error=str(exc)))
        raise
