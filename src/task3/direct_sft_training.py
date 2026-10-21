"""One frozen direct QLoRA pilot, completion-only loss and durable audits.

No GPU stack is imported until run_direct_sft is explicitly called. This module
never runs the legacy diagnostic/feedback trainer or its family exclusion gate.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time
import traceback
from uuid import uuid4

from src.task3.train import encode_completion
from src.task3.pilot_training import (
    WeightedCompletionCollator, completion_mean_losses, weighted_completion_loss,
    claim_optimizer_start, select_epoch, _digest, _write_json, _file_sha,
    _adapter_hashes, _model_precision_audit,
)

CHECKPOINT_POLICY = 'min_internal_validation_equal_source_loss_earliest_tie'


def validate_frozen_config(config):
    """Reject overrides, adapters and resumes before importing the training stack."""
    expected = dict(model_id='Qwen/Qwen2.5-Coder-7B-Instruct',
        revision='c03e6d358207e414f1eca0bb1891e29f1db0e242', seed=42,
        load_in_4bit=True, max_seq_length=8192, lora_r=16, lora_alpha=32,
        lora_dropout=.05, learning_rate=1e-4, epochs=2,
        per_device_train_batch_size=1, gradient_accumulation_steps=4,
        lr_scheduler_type='cosine', warmup_ratio=.03,
        target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
        checkpoint_policy=CHECKPOINT_POLICY,
        work_dir='outputs/task3/direct-sft-v1-20261021',
        output_dir='outputs/task3/direct-sft-v1-20261021/training',
        loss_weights={'direct': 1.})
    for key, value in expected.items():
        if key not in config or config[key] != value:
            raise ValueError('direct SFT differs from frozen configuration: ' + key)
    for key in ('adapter', 'staged_adapter', 'resume', 'resume_from_checkpoint'):
        if config.get(key):
            raise ValueError('existing adapter and resume are forbidden: ' + key)


def encode_direct_examples(tokenizer, examples, max_length=8192):
    """Render exact final-only targets; never truncate a prompt or completion."""
    if not examples:
        raise ValueError('empty direct SFT example split')
    rows, seen = [], set()
    audit = dict(examples=len(examples), sources=len({e['sample_id'] for e in examples}),
                 tokens=0, supervised_tokens=0, max_tokens=0, by_kind={}, truncated=False)
    for example in examples:
        eid = example['example_id']
        if eid in seen:
            raise ValueError('duplicate direct example ID')
        seen.add(eid)
        if example['kind'] != 'direct' or float(example['loss_weight']) != 1.:
            raise ValueError('direct SFT requires kind=direct and loss_weight=1')
        try:
            target = json.loads(example['completion'])
        except (ValueError, TypeError) as exc:
            raise ValueError('direct completion must be final two-field JSON') from exc
        if (not isinstance(target, dict) or set(target) != {'taxonomy_error', 'feedback'}
                or not isinstance(target['taxonomy_error'], list)
                or not isinstance(target['feedback'], str) or not target['feedback'].strip()):
            raise ValueError('direct completion requires only taxonomy_error and nonempty feedback')
        row = encode_completion(tokenizer, example['messages'], example['completion'], max_length)
        row.update({key: example[key] for key in ('sample_id', 'example_id', 'kind', 'loss_weight')})
        row['example_sha256'] = _digest(example)
        tokens = len(row['input_ids'])
        supervised = sum(x != -100 for x in row['labels'][1:])
        if not row['labels'] or row['labels'][0] != -100 or supervised <= 0:
            raise ValueError('completion prompt mask or supervised tokens invalid')
        by_kind = audit['by_kind'].setdefault('direct', dict(examples=0, tokens=0, supervised_tokens=0, max_tokens=0))
        for stat in (audit, by_kind):
            stat['tokens'] += tokens
            stat['supervised_tokens'] += supervised
            stat['max_tokens'] = max(stat['max_tokens'], tokens)
        by_kind['examples'] += 1
        rows.append(row)
    audit['encoded_sha256'] = _digest(rows)
    return rows, audit


def verify_encoded_binding(tokenizer, examples, rows, sources, max_length):
    """Recompute actual source bytes and complete masked tensors at each boundary."""
    source_ids = [r['sample_id'] for r in sources]
    if len(source_ids) != len(set(source_ids)) or set(source_ids) != {e['sample_id'] for e in examples}:
        raise ValueError('tokenized examples do not match exact frozen source IDs')
    by_id = {r['sample_id']: r for r in sources}
    for example in examples:
        code = by_id[example['sample_id']].get('code')
        if not isinstance(code, str) or example.get('source_sha256') != hashlib.sha256(code.encode()).hexdigest():
            raise ValueError('example does not bind actual frozen source bytes')
    fresh, _ = encode_direct_examples(tokenizer, examples, max_length)
    if fresh != rows:
        raise ValueError('encoded example/source binding changed after tokenization')
    return dict(sources=len(sources), examples=len(rows), sources_sha256=_digest(sources),
                examples_sha256=_digest(examples), encoded_sha256=_digest(rows))


def aggregate_validation(examples, losses):
    """Mean final-completion loss within each SOURCE, then equal mean of sources."""
    if len(examples) != len(losses) or not examples:
        raise ValueError('validation examples and losses must align')
    groups = defaultdict(list)
    for example, loss in zip(examples, losses):
        if example['kind'] != 'direct' or float(example['loss_weight']) != 1.:
            raise ValueError('validation requires direct unit-weight examples')
        loss = float(loss)
        if not math.isfinite(loss):
            raise ValueError('nonfinite validation loss')
        groups[example['sample_id']].append(loss)
    per_source = {sid: dict(loss=sum(values)/len(values), examples=len(values))
                  for sid, values in groups.items()}
    return dict(loss=sum(row['loss'] for row in per_source.values())/len(per_source),
                sources=len(per_source), examples=len(examples), per_source=per_source)


def verify_before_optimizer(verify_pilot, frozen, tokenizer, rows, guard, *,
                            validation_rows=None, boundary='before_optimizer_setup'):
    """Check frozen bytes and the NEW direct policy before setup and first step."""
    current = verify_pilot()
    if _digest(current) != _digest(frozen):
        raise ValueError('frozen direct pilot binding changed before optimizer')
    manifest, config, examples, validation, sources, registry = current
    validate_frozen_config(config)
    binding = verify_encoded_binding(tokenizer, examples, rows, sources, config['max_seq_length'])
    if validation:
        fresh_validation, _ = encode_direct_examples(tokenizer, validation, config['max_seq_length'])
        if fresh_validation != validation_rows:
            raise ValueError('validation encoded binding changed before optimizer')
    gate = guard(sources, registry, stage='before_optimizer')
    return dict(binding=binding, guard=gate, boundary=boundary,
                validation_encoded_sha256=_digest(validation_rows),
                manifest_sha256=_digest(manifest), config_sha256=_digest(config))


def audit_unadapted_base(model):
    """Reject preloaded adapters before creating the sole new LoRA adapter."""
    if (getattr(model, 'peft_config', None) or getattr(model, '_hf_peft_config_loaded', False)
            or any('lora_' in name for name, _ in model.named_parameters())):
        raise RuntimeError('base model contains preexisting PEFT adapter weights')
    return dict(preexisting_adapter=False, base_model_class=type(model).__name__)


def evaluate_internal(model, rows, collator):
    """Evaluate TRAIN-derived validation without optimizer, gradients or generation."""
    import torch
    device = next(model.parameters()).device
    training = model.training
    losses = []
    model.eval()
    try:
        with torch.inference_mode():
            for row in rows:
                batch = collator([row])
                inputs = {key: batch[key].to(device) for key in ('input_ids', 'attention_mask')}
                context = torch.autocast('cuda', dtype=torch.bfloat16) if device.type == 'cuda' else nullcontext()
                with context:
                    output = model(**inputs, use_cache=False)
                    losses.extend(completion_mean_losses(output.logits, batch['labels'].to(device)).tolist())
                del output, batch, inputs
    finally:
        model.train(training)
    return aggregate_validation(rows, losses)


def run_direct_sft(repo, verify_pilot):
    """Run the sole authorized direct two-epoch pilot; no overrides or resume."""
    from importlib.metadata import version
    repo = Path(repo).resolve()
    frozen = verify_pilot()
    manifest, config, examples, validation, sources, registry = frozen
    validate_frozen_config(config)
    output = repo/config['output_dir']
    marker = output/'optimizer-started.json'
    if marker.exists():
        raise FileExistsError('optimizer marker exists; second direct pilot or resume forbidden')
    attempt = output/'attempts'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8])
    attempt.mkdir(parents=True)
    result = dict(status='setup', started_utc=datetime.now(timezone.utc).isoformat(),
        config=config, config_sha256=_digest(config), manifest_sha256=_digest(manifest),
        attempt_path=str(attempt), optimizer_started=False, objective='direct final JSON completion only',
        checkpoint_policy=CHECKPOINT_POLICY, selection_data='TRAIN-derived internal validation only',
        implementation_sha256={str(Path(__file__).relative_to(repo)): _file_sha(__file__),
                               'scripts/task3_direct_sft_train.py': _file_sha(repo/'scripts/task3_direct_sft_train.py')})
    started = time.perf_counter()
    torch = trainer = None
    try:
        os.environ.setdefault('HF_HOME', str(repo/'outputs/task3/hf-cache'))
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        from src.task3.inference import tokenizer_metadata
        from src.task3.train import _training_gpu_preflight, _audit_lora_parameter_updates
        from src.task3.direct_sft_data import require_direct_isolation
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, Trainer, TrainingArguments, TrainerCallback, set_seed
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        result['library_versions'] = {name: version(name) for name in
                                     ('torch', 'transformers', 'peft', 'bitsandbytes', 'accelerate', 'datasets')}
        set_seed(config['seed'])
        tokenizer = AutoTokenizer.from_pretrained(config['model_id'], revision=config['revision'],
                                                   trust_remote_code=False, local_files_only=True)
        tokenizer._task3_revision = config['revision']
        if not tokenizer.chat_template:
            raise ValueError('real tokenizer has no chat template')
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        rows, train_audit = encode_direct_examples(tokenizer, examples, config['max_seq_length'])
        val_rows, val_audit = encode_direct_examples(tokenizer, validation, config['max_seq_length'])
        aggregate_validation(examples, [0.]*len(examples))
        aggregate_validation(validation, [0.]*len(validation))
        if {r['sample_id'] for r in rows} & {r['sample_id'] for r in val_rows}:
            raise ValueError('train and validation source IDs overlap')
        binding = verify_encoded_binding(tokenizer, examples, rows, sources, config['max_seq_length'])
        result.update(tokenizer=tokenizer_metadata(tokenizer), binding=binding,
                      token_audit=dict(train=train_audit, validation=val_audit))
        _write_json(output/'token-audit.json', result['token_audit'])
        gpu = _training_gpu_preflight(torch, dict(config, single_gpu=True, require_bf16=True, expected_gpu_name='5090'))
        result['gpu_preflight'] = gpu
        torch.cuda.reset_peak_memory_stats()
        load_start = time.perf_counter()
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                  bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
        base = AutoModelForCausalLM.from_pretrained(config['model_id'], revision=config['revision'],
            trust_remote_code=False, local_files_only=True, quantization_config=quant,
            device_map={'': gpu['selected_device']}, torch_dtype=torch.bfloat16)
        result['model_load_wall_s'] = time.perf_counter()-load_start
        result['unadapted_base_audit'] = audit_unadapted_base(base)
        result['precision_audit'] = _model_precision_audit(base, config['revision'])
        base.config.use_cache = False
        base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True)
        model = get_peft_model(base, LoraConfig(r=config['lora_r'], lora_alpha=config['lora_alpha'],
            lora_dropout=config['lora_dropout'], target_modules=config['target_modules'], bias='none', task_type='CAUSAL_LM'))
        trainable = {n: p for n, p in model.named_parameters() if p.requires_grad}
        if not trainable or any('lora_' not in name for name in trainable):
            raise RuntimeError('only LoRA parameters may be trainable')
        initial = {n: p.detach().clone() for n, p in trainable.items()}
        result['trainable_parameters'] = sum(p.numel() for p in trainable.values())
        collator = WeightedCompletionCollator(tokenizer.pad_token_id)
        checkpoints, exposures = [], Counter()
        epoch_start_exposures = Counter()
        first_gradient_gate = None
        gradient_audit = dict(steps_checked=0, finite_nonzero_steps=0)
        raw_log = attempt/'training-log.jsonl'

        class DirectTrainer(Trainer):
            def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
                weights, labels = inputs.pop('loss_weight'), inputs.pop('labels')
                ids = inputs.pop('example_id')
                if not bool((weights == 1).all()):
                    raise ValueError('direct training weights must all equal one')
                if model.training:
                    exposures.update(ids)
                outputs = model(**inputs, use_cache=False)
                loss = weighted_completion_loss(outputs.logits, labels, weights)
                return (loss, outputs) if return_outputs else loss

        class Audit(TrainerCallback):
            def on_log(self, args, state, control, logs=None, **kwargs):
                with raw_log.open('a') as handle:
                    handle.write(json.dumps(dict(step=state.global_step, epoch=state.epoch, logs=logs), allow_nan=False)+'\n')

            def on_pre_optimizer_step(self, args, state, control, **kwargs):
                nonlocal first_gradient_gate
                if first_gradient_gate is None:
                    first_gradient_gate = verify_before_optimizer(verify_pilot, frozen, tokenizer, rows,
                        require_direct_isolation, validation_rows=val_rows, boundary='first_optimizer_step')
                    _write_json(output/'first-optimizer-gate.json', first_gradient_gate)
                grads = [p.grad for p in trainable.values() if p.grad is not None]
                if not grads or not all(bool(torch.isfinite(g).all()) for g in grads):
                    raise RuntimeError('missing or nonfinite LoRA gradients')
                nonzero = any(bool(torch.count_nonzero(g)) for g in grads)
                gradient_audit['steps_checked'] += 1
                gradient_audit['finite_nonzero_steps'] += int(nonzero)
                if not nonzero:
                    raise RuntimeError('all LoRA gradients are zero before optimizer step')

            def on_epoch_end(self, args, state, control, **kwargs):
                nonlocal epoch_start_exposures
                epoch = int(round(state.epoch))
                observed = exposures-epoch_start_exposures
                if observed != Counter({r['example_id']: 1 for r in rows}):
                    raise RuntimeError('epoch did not consume each frozen training example exactly once')
                epoch_start_exposures = exposures.copy()
                metrics = evaluate_internal(model, val_rows, collator)
                adapter = output/f'epoch-{epoch}'/'adapter'
                model.save_pretrained(adapter, safe_serialization=True)
                tokenizer.save_pretrained(adapter)
                checkpoints.append(dict(epoch=epoch, optimizer_step=state.global_step, validation=metrics,
                    adapter_path=str(adapter), adapter_sha256=_adapter_hashes(adapter),
                    actual_example_exposures=dict(observed)))
                _write_json(output/'epoch-validation.json', checkpoints)

        # This runs before Trainer construction, hence before optimizer setup.
        setup_gate = verify_before_optimizer(verify_pilot, frozen, tokenizer, rows,
            require_direct_isolation, validation_rows=val_rows, boundary='before_optimizer_setup')
        result['before_optimizer_setup_gate'] = setup_gate
        _write_json(output/'before-optimizer-setup-gate.json', setup_gate)
        args = TrainingArguments(output_dir=str(attempt/'trainer'), seed=config['seed'], data_seed=config['seed'],
            learning_rate=config['learning_rate'], num_train_epochs=config['epochs'],
            per_device_train_batch_size=config['per_device_train_batch_size'],
            gradient_accumulation_steps=config['gradient_accumulation_steps'], gradient_checkpointing=True,
            gradient_checkpointing_kwargs={'use_reentrant': False}, bf16=True, fp16=False,
            lr_scheduler_type=config['lr_scheduler_type'], warmup_ratio=config['warmup_ratio'],
            eval_strategy='no', save_strategy='no', logging_steps=1, report_to=[], push_to_hub=False,
            remove_unused_columns=False, dataloader_num_workers=0, optim='adamw_torch',
            load_best_model_at_end=False, dataloader_drop_last=False)
        trainer = DirectTrainer(model=model, args=args, train_dataset=rows, data_collator=collator,
                                processing_class=tokenizer, callbacks=[Audit()])
        trainer.model_accepts_loss_kwargs = False
        result['validation_before'] = evaluate_internal(model, val_rows, collator)
        result['training_arguments'] = args.to_dict()
        _write_json(attempt/'before-optimizer.json', result)
        boundary = verify_before_optimizer(verify_pilot, frozen, tokenizer, rows,
            require_direct_isolation, validation_rows=val_rows, boundary='before_train')
        train_start = time.perf_counter()
        # Exclusive and durable: this allowance is consumed even if train raises.
        claim_optimizer_start(marker, dict(boundary, started_utc=datetime.now(timezone.utc).isoformat()))
        trained = trainer.train()
        result['optimizer_started'] = True
        torch.cuda.synchronize()
        result['training_gpu_wall_s'] = time.perf_counter()-train_start
        if len(checkpoints) != 2 or [c['epoch'] for c in checkpoints] != [1, 2]:
            raise RuntimeError('direct pilot did not complete exactly two frozen epochs')
        update = _audit_lora_parameter_updates(initial, model)
        if not update['finite_nonzero_lora_update'] or not gradient_audit['finite_nonzero_steps']:
            raise RuntimeError('finite nonzero LoRA gradient/update not verified')
        chosen = select_epoch(checkpoints)
        selected = output/'adapter'
        shutil.copytree(chosen['adapter_path'], selected)
        hashes = _adapter_hashes(selected)
        if hashes != chosen['adapter_sha256']:
            raise RuntimeError('selected adapter differs from validation-selected checkpoint')
        result.update(status='complete', optimizer_steps=trainer.state.global_step,
            train_metrics=trained.metrics, history=trainer.state.log_history, gradient_audit=gradient_audit,
            parameter_update_audit=update, epoch_checkpoints=checkpoints, selected_epoch=chosen['epoch'],
            selected_validation_loss=chosen['validation']['loss'], selected_adapter_path=str(selected),
            adapter_path=str(selected), selected_adapter_sha256=hashes['adapter_model.safetensors'],
            selected_adapter_files_sha256=hashes, actual_example_exposures=dict(exposures),
            actual_train_examples=len(rows)*2, actual_train_tokens=train_audit['tokens']*2,
            actual_train_supervised_tokens=train_audit['supervised_tokens']*2,
            first_optimizer_gate=first_gradient_gate)
        verify_pilot()
    except BaseException as exc:
        result.update(status='failed' if marker.exists() else 'setup_failed',
            optimizer_started=marker.exists(), error=repr(exc), traceback=traceback.format_exc(),
            optimizer_steps=int(trainer.state.global_step) if trainer is not None else 0)
        raise
    finally:
        result['wall_s'] = time.perf_counter()-started
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
        if torch is not None and torch.cuda.is_available():
            result.update(peak_gpu_memory_allocated_bytes=torch.cuda.max_memory_allocated(),
                          peak_gpu_memory_reserved_bytes=torch.cuda.max_memory_reserved())
        _write_json(attempt/'result.json', result)
        _write_json(output/'training-result.json', result)
    return result


# Preparation and reporting may use the conventional name without old runner access.
run_pilot = run_direct_sft
