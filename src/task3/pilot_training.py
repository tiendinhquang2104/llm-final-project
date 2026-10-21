"""One frozen QLoRA pilot, completion-only equal-task objective and durable audits.

Imports of the GPU training stack are deliberately lazy. Importing this module,
tokenizing, inspecting bindings, and CPU tests cannot start an optimizer.
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

from src.task3.train import CompletionCollator, encode_completion


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def encode_pilot_examples(tokenizer, examples, max_length):
    """Encode every frozen example once; reject truncation and invalid weights."""
    rows, seen = [], set()
    audit = dict(examples=len(examples), sources=len({e['sample_id'] for e in examples}),
                 tokens=0, supervised_tokens=0, max_tokens=0, by_kind={}, truncated=False)
    if not examples:
        raise ValueError('empty pilot example split')
    for example in examples:
        eid, kind = example['example_id'], example['kind']
        if eid in seen or kind not in ('diagnostic', 'feedback'):
            raise ValueError('duplicate example ID or unknown task kind')
        seen.add(eid)
        weight = float(example['loss_weight'])
        expected = 2. if kind == 'diagnostic' else 2/3
        if not math.isclose(weight, expected, rel_tol=0, abs_tol=1e-12):
            raise ValueError('loss weight differs from fixed equal-task objective')
        row = encode_completion(tokenizer, example['messages'], example['completion'], max_length)
        row.update({key: example[key] for key in ('sample_id', 'example_id', 'kind', 'loss_weight')})
        row['example_sha256'] = _digest(example)
        tokens = len(row['input_ids'])
        supervised = sum(x != -100 for x in row['labels'][1:])
        if not row['labels'] or row['labels'][0] != -100 or supervised <= 0:
            raise ValueError('completion prompt mask or supervised tokens invalid')
        by_kind = audit['by_kind'].setdefault(kind, dict(examples=0, tokens=0, supervised_tokens=0, max_tokens=0))
        for stat in (audit, by_kind):
            stat['tokens'] += tokens
            stat['supervised_tokens'] += supervised
            stat['max_tokens'] = max(stat['max_tokens'], tokens)
        by_kind['examples'] += 1
        rows.append(row)
    audit['encoded_sha256'] = _digest(rows)
    return rows, audit


def verify_encoded_binding(tokenizer, examples, rows, sources, max_length):
    """Bind exact frozen source records and complete rendered examples to labels."""
    source_ids = [r['sample_id'] for r in sources]
    if len(source_ids) != len(set(source_ids)) or set(source_ids) != {r['sample_id'] for r in examples}:
        raise ValueError('tokenized examples do not match exact frozen source IDs')
    fresh, _ = encode_pilot_examples(tokenizer, examples, max_length)
    if fresh != rows:
        raise ValueError('encoded example/source binding changed after tokenization')
    return dict(sources=len(sources), examples=len(rows), sources_sha256=_digest(sources),
                examples_sha256=_digest(examples), encoded_sha256=_digest(rows))


class WeightedCompletionCollator:
    def __init__(self, pad_token_id):
        self.completion_collator = CompletionCollator(pad_token_id)

    def __call__(self, rows):
        import torch
        result = self.completion_collator(rows)
        result['loss_weight'] = torch.tensor([r['loss_weight'] for r in rows], dtype=torch.float32)
        result['example_id'] = [r['example_id'] for r in rows]
        return result


def completion_mean_losses(logits, labels):
    """Causal completion CE, averaged within each example, never over its prompt."""
    import torch
    from torch.nn import functional as F
    if logits.ndim != 3 or labels.shape != logits.shape[:2]:
        raise ValueError('logits and labels have incompatible shapes')
    means = []
    for predictions, targets in zip(logits[:, :-1], labels[:, 1:]):
        selected = targets != -100
        if not bool(selected.any()):
            raise ValueError('example has no supervised shifted completion tokens')
        # Select only target positions before promoting to FP32; full prompts
        # can be much longer than completions for source-bearing tasks.
        means.append(F.cross_entropy(predictions[selected].float(), targets[selected], reduction='mean'))
    return torch.stack(means)


def weighted_completion_loss(logits, labels, weights):
    losses = completion_mean_losses(logits, labels)
    weights = weights.to(device=losses.device, dtype=losses.dtype)
    if weights.shape != losses.shape or not bool(weights.isfinite().all()) or not bool((weights > 0).all()):
        raise ValueError('invalid per-example loss weights')
    return (losses * weights).mean()


def aggregate_validation(examples, losses):
    """Equal source mean of 50% diagnosis + 50% mean of feedback levels 1–3."""
    if len(examples) != len(losses) or not examples:
        raise ValueError('validation examples and losses must align')
    groups = defaultdict(lambda: defaultdict(list))
    for example, loss in zip(examples, losses):
        loss = float(loss)
        if not math.isfinite(loss):
            raise ValueError('nonfinite validation loss')
        groups[example['sample_id']][example['kind']].append(loss)
    per_source = {}
    for sid, tasks in groups.items():
        if set(tasks) != {'diagnostic', 'feedback'} or len(tasks['diagnostic']) != 1 or len(tasks['feedback']) != 3:
            raise ValueError('validation requires four examples: one diagnostic and three feedback')
        diagnostic, feedback = tasks['diagnostic'][0], sum(tasks['feedback']) / 3
        per_source[sid] = dict(loss=.5*(diagnostic+feedback), diagnostic_loss=diagnostic, feedback_loss=feedback)
    return {**{key: sum(row[key] for row in per_source.values()) / len(per_source)
               for key in ('loss', 'diagnostic_loss', 'feedback_loss')},
            'sources': len(groups), 'examples': len(examples), 'per_source': per_source}


def claim_optimizer_start(path, binding):
    """Durably consume the one-pilot allowance; failures never remove this marker."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(binding, handle, ensure_ascii=False, sort_keys=True, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def select_epoch(checkpoints):
    if not checkpoints or any(not math.isfinite(float(c['validation']['loss'])) for c in checkpoints):
        raise ValueError('checkpoint selection requires finite internal validation losses')
    return min(checkpoints, key=lambda c: (float(c['validation']['loss']), int(c['epoch'])))


def verify_before_optimizer(verify_pilot, frozen, tokenizer, rows, guard):
    current = verify_pilot()
    if _digest(current) != _digest(frozen):
        raise ValueError('frozen pilot binding changed before optimizer')
    manifest, config, examples, _, sources, registry = current
    binding = verify_encoded_binding(tokenizer, examples, rows, sources, config['max_seq_length'])
    gate = guard(sources, registry, stage='before_optimizer')
    return dict(binding=binding, guard=gate, manifest_sha256=_digest(manifest), config_sha256=_digest(config))


def evaluate_internal(model, rows, collator):
    """Evaluate TRAIN-derived validation only, without optimizer or generation."""
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


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temporary.replace(path)


def _file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _adapter_hashes(path):
    return {str(file.relative_to(path)): _file_sha(file) for file in sorted(Path(path).rglob('*')) if file.is_file()}


def _model_precision_audit(model, revision):
    import torch
    import bitsandbytes as bnb
    from src.task3.inference import inspect_model_precision
    audit = inspect_model_precision(model, load_in_4bit=True)
    layers = [layer for layer in model.modules() if isinstance(layer, bnb.nn.Linear4bit)]
    if not layers or any(layer.compute_dtype != torch.bfloat16 or
                         layer.weight.dtype != torch.uint8 or
                         layer.weight.quant_state is None or
                         layer.weight.quant_state.quant_type != 'nf4' or
                         not layer.weight.quant_state.nested for layer in layers):
        raise RuntimeError('actual quantized layers must use NF4 double quantization and BF16 compute')
    if audit['resolved_model_revision'] != revision:
        raise RuntimeError('actual model revision differs from frozen revision')
    # Transformers compensates for packed Params4bit storage in this method.
    count = int(model.num_parameters())
    if not 0 < count < 10_000_000_000:
        raise RuntimeError('base model must have fewer than 10 billion logical parameters')
    return dict(audit, actual_4bit_linear_layers=len(layers), double_quantization_verified=True,
                base_logical_parameters=count)


def run_pilot(repo, verify_pilot):
    """Run exactly the frozen two-epoch pilot. Callers must explicitly invoke it."""
    from importlib.metadata import version
    repo = Path(repo).resolve()
    frozen = verify_pilot()
    manifest, config, examples, validation, sources, registry = frozen
    output = repo / config['output_dir']
    marker = output / 'optimizer-started.json'
    if marker.exists():
        raise FileExistsError('optimizer marker exists; a second pilot or resume is forbidden')
    if int(config['epochs']) != 2 or config['checkpoint_policy'] != 'min_internal_validation_equal_task_loss_earliest_tie':
        raise ValueError('this trainer requires the frozen two-epoch internal-validation selection policy')
    attempt = output / 'attempts' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8])
    attempt.mkdir(parents=True)
    result = dict(status='setup', started_utc=datetime.now(timezone.utc).isoformat(),
                  config=config, config_sha256=_digest(config), manifest_sha256=_digest(manifest),
                  attempt_path=str(attempt), optimizer_started=False,
                  checkpoint_policy=config['checkpoint_policy'], selection_data='TRAIN-derived internal validation only',
                  implementation_sha256={str(Path(__file__).relative_to(repo)): _file_sha(__file__),
                                         'scripts/task3_pilot_train.py': _file_sha(repo/'scripts/task3_pilot_train.py')})
    started = time.perf_counter()
    torch = None
    trainer = None
    try:
        os.environ.setdefault('HF_HOME', str(repo/'outputs/task3/hf-cache'))
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        from src.task3.inference import load_tokenizer, tokenizer_metadata
        from src.task3.train import _training_gpu_preflight, _audit_lora_parameter_updates
        from src.task3.train_supplement import require_supplement_isolation
        import torch
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig, Trainer, TrainingArguments, TrainerCallback, set_seed
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        result['library_versions'] = {name: version(name) for name in ('torch', 'transformers', 'peft', 'bitsandbytes', 'accelerate', 'datasets')}
        set_seed(config['seed'])
        tokenizer = load_tokenizer(config)
        rows, train_audit = encode_pilot_examples(tokenizer, examples, config['max_seq_length'])
        val_rows, val_audit = encode_pilot_examples(tokenizer, validation, config['max_seq_length'])
        # The four-task invariant also ensures every source contributes the same mass.
        aggregate_validation(examples, [0.] * len(examples))
        aggregate_validation(validation, [0.] * len(validation))
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
        result['model_load_wall_s'] = time.perf_counter() - load_start
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
        first_gradient_gate = None
        epoch_start_exposures = Counter()
        gradient_audit = dict(steps_checked=0, finite_nonzero_steps=0)
        raw_log = attempt/'training-log.jsonl'

        class WeightedTrainer(Trainer):
            def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
                weights, labels = inputs.pop('loss_weight'), inputs.pop('labels')
                ids = inputs.pop('example_id')
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
                    first_gradient_gate = verify_before_optimizer(verify_pilot, frozen, tokenizer, rows, require_supplement_isolation)
                    _write_json(output/'first-optimizer-gate.json', first_gradient_gate)
                grads = [p.grad for p in trainable.values() if p.grad is not None]
                if not grads or not all(bool(torch.isfinite(g).all()) for g in grads):
                    raise RuntimeError('missing or nonfinite LoRA gradients')
                nonzero = any(bool(torch.count_nonzero(g)) for g in grads)
                gradient_audit['steps_checked'] += 1
                gradient_audit['finite_nonzero_steps'] += int(nonzero)
                if not nonzero:
                    raise RuntimeError('all LoRA gradients are zero before an optimizer step')

            def on_epoch_end(self, args, state, control, **kwargs):
                nonlocal epoch_start_exposures
                epoch = int(round(state.epoch))
                observed = exposures - epoch_start_exposures
                if observed != Counter({r['example_id']: 1 for r in rows}):
                    raise RuntimeError('an epoch did not consume each frozen training example exactly once')
                epoch_start_exposures = exposures.copy()
                metrics = evaluate_internal(model, val_rows, collator)
                adapter = output/f'epoch-{epoch}'/'adapter'
                model.save_pretrained(adapter, safe_serialization=True)
                tokenizer.save_pretrained(adapter)
                checkpoints.append(dict(epoch=epoch, optimizer_step=state.global_step, validation=metrics,
                    adapter_path=str(adapter), adapter_sha256=_adapter_hashes(adapter),
                    actual_example_exposures=dict(observed)))
                _write_json(output/'epoch-validation.json', checkpoints)

        args = TrainingArguments(output_dir=str(attempt/'trainer'), seed=config['seed'], data_seed=config['seed'],
            learning_rate=config['learning_rate'], num_train_epochs=config['epochs'],
            per_device_train_batch_size=config['per_device_train_batch_size'],
            gradient_accumulation_steps=config['gradient_accumulation_steps'], gradient_checkpointing=True,
            gradient_checkpointing_kwargs={'use_reentrant': False}, bf16=True, fp16=False,
            lr_scheduler_type=config['lr_scheduler_type'], warmup_ratio=config['warmup_ratio'],
            eval_strategy='no', save_strategy='no', logging_steps=1, report_to=[], push_to_hub=False,
            remove_unused_columns=False, dataloader_num_workers=0, optim='adamw_torch',
            load_best_model_at_end=False, dataloader_drop_last=False)
        trainer = WeightedTrainer(model=model, args=args, train_dataset=rows, data_collator=collator,
                                  processing_class=tokenizer, callbacks=[Audit()])
        trainer.model_accepts_loss_kwargs = False
        result['validation_before'] = evaluate_internal(model, val_rows, collator)
        result['training_arguments'] = args.to_dict()
        _write_json(attempt/'before-optimizer.json', result)
        boundary = verify_before_optimizer(verify_pilot, frozen, tokenizer, rows, require_supplement_isolation)
        # The exclusive marker is the last action before the sole train() call.
        claim_optimizer_start(marker, dict(boundary, started_utc=datetime.now(timezone.utc).isoformat()))
        result['optimizer_started'] = True
        train_start = time.perf_counter()
        trained = trainer.train()
        torch.cuda.synchronize()
        result['training_gpu_wall_s'] = time.perf_counter() - train_start
        if len(checkpoints) != 2 or [c['epoch'] for c in checkpoints] != [1, 2]:
            raise RuntimeError('pilot did not complete exactly the two frozen epochs')
        update = _audit_lora_parameter_updates(initial, model)
        if not update['finite_nonzero_lora_update'] or not gradient_audit['finite_nonzero_steps']:
            raise RuntimeError('finite nonzero LoRA gradient/update not verified')
        chosen = select_epoch(checkpoints)
        selected = output/'adapter'
        shutil.copytree(chosen['adapter_path'], selected)
        hashes = _adapter_hashes(selected)
        if hashes != chosen['adapter_sha256']:
            raise RuntimeError('selected adapter copy differs from validation-selected checkpoint')
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
        result['wall_s'] = time.perf_counter() - started
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
        if torch is not None and torch.cuda.is_available():
            result.update(peak_gpu_memory_allocated_bytes=torch.cuda.max_memory_allocated(),
                          peak_gpu_memory_reserved_bytes=torch.cuda.max_memory_reserved())
        _write_json(attempt/'result.json', result)
        _write_json(output/'training-result.json', result)
    return result
