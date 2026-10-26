"""GPU evaluation, durable single-attempt generation and immutable experiment freeze."""
from contextlib import contextmanager
from importlib.metadata import version
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

from src.task3.sft_v1 import load_split, read_jsonl, sha256, verify_checksums
from src.task3.sft_v1_experiment import Journal, preserve_rng, smoke_ids, training_arguments, write_json


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def tensor_digest(tensor):
    return hashlib.sha256(tensor.detach().cpu().contiguous().view(__import__('torch').uint8).numpy().tobytes()).hexdigest()


def adapter_identity(model):
    from peft import get_peft_model_state_dict
    return {k: tensor_digest(v) for k, v in get_peft_model_state_dict(model).items()}


@contextmanager
def evaluating(model):
    training = model.training
    with preserve_rng():
        try:
            model.eval()
            yield
        finally:
            model.train(training)


def freeze(repo, out, config_path, reuse, request):
    import yaml
    from transformers import AutoTokenizer
    from src.task3.sft_v1_evaluation import EVALUATION_POLICY
    config = yaml.safe_load(config_path.read_text())
    training_arguments(config, out / 'main')
    if config['model_id'] != 'Qwen/Qwen2.5-Coder-7B-Instruct' or config['revision'] != 'c03e6d358207e414f1eca0bb1891e29f1db0e242':
        raise ValueError('unexpected model/revision')
    if subprocess.check_output(['git', 'branch', '--show-current'], cwd=repo, text=True).strip() != config['required_branch']:
        raise ValueError('wrong worktree branch')
    root = repo / config['dataset_root']
    verify_checksums(root, config['checksum_manifest_sha256'])
    archive = repo.parent / 'task3-sft-v1.zip'
    if sha256(archive) != config['archive_sha256']:
        raise ValueError('archive checksum mismatch')
    previous = json.loads((reuse / 'actual-config.json').read_text())
    for name, expected in json.loads((reuse / 'artifact-sha256.json').read_text()).items():
        if sha256(reuse / name) != expected:
            raise ValueError('cached preparation artifact changed: ' + name)
    for name, expected in previous['implementation_sha256'].items():
        if sha256(repo / name) != expected:
            raise ValueError('preparation code identity differs: ' + name)
    tokenizer = AutoTokenizer.from_pretrained(config['tokenizer_local'], revision=config['revision'],
                                              local_files_only=True, trust_remote_code=False)
    if hashlib.sha256(tokenizer.chat_template.encode()).hexdigest() != previous['tokenizer']['chat_template_sha256']:
        raise ValueError('cached chat template differs')
    examples = {split: load_split(root, split) for split in ('train', 'dev', 'test')}
    encoded = {s: read_jsonl(reuse / (s + '.encoded.private.jsonl')) for s in examples}
    for split in examples:
        if [r['example_id'] for r in encoded[split]] != [e['example_id'] for e in examples[split]]:
            raise ValueError('cached example IDs differ')
    if {s: len(v) for s, v in examples.items()} != {'train': 640, 'dev': 80, 'test': 80}:
        raise ValueError('wrong native dataset counts')
    code_paths = ['src/task3/sft_v1.py', 'src/task3/sft_v1_experiment.py', 'src/task3/sft_v1_runtime.py',
                  'src/task3/sft_v1_training.py', 'src/task3/sft_v1_evaluation.py',
                  'src/task3/train.py', 'src/task3/pilot_training.py',
                  'scripts/task3_sft_v1_experiment.py', 'scripts/task3_sft_v1_prepare.py']
    manifest = dict(config=config, config_sha256=sha256(config_path),
        code={p: sha256(repo / p) for p in code_paths},
        head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        git_status=subprocess.check_output(['git', 'status', '--porcelain', '-uall'], cwd=repo, text=True),
        dataset={p: sha256(root / p) for p in ('SHA256SUMS', 'split-manifest.json', 'SYSTEM_PROMPT.txt',
            'label_space.json', 'train.sft.jsonl', 'dev.sft.jsonl', 'test.sft.jsonl')},
        preflight=str(reuse), preflight_sha256=sha256(reuse / 'actual-config.json'),
        encoded={s: sha256(reuse / (s + '.encoded.private.jsonl')) for s in examples},
        tokenizer=previous['tokenizer'], prompt_policy=config['prompt_policy'],
        evaluation_policy=EVALUATION_POLICY,
        versions={n: version(n) for n in ('torch', 'transformers', 'peft', 'bitsandbytes', 'accelerate', 'datasets', 'pyyaml')},
        model_settings=dict(model_id=config['model_id'], revision=config['revision'], load_in_4bit=True,
                            quant_type='nf4', double_quant=True, compute_dtype='bfloat16', single_gpu=0),
        generation=dict(do_sample=False, concurrency=1, max_new_tokens={'1':1024,'2':1024,'3':1024,'4':1536},
                        max_time=45., eos_token_id=tokenizer.eos_token_id, pad_token_id=tokenizer.pad_token_id),
        main_training_arguments=training_arguments(config, out / 'main'),
        smoke_training_arguments=training_arguments(config, out / 'smoke', smoke=True),
        steps=dict(smoke=4, main=160, checkpoints=[80,160]),
        call_budget=dict(primary=400, smoke=2, total=402), smoke_ids=smoke_ids(examples['train']),
        smoke_reload_tolerances=dict(atol=.002,rtol=.001,logits='all vocabulary at last prompt position'),
        selection_rule='minimum_fixed_dev_equal_example_completion_loss_earliest_exact_tie',
        request_sha256=sha256(request))
    if manifest['versions'] != previous['versions']:
        raise ValueError('dependencies differ from cached preparation')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'request.txt').write_bytes(request.read_bytes())
    write_json(out / 'manifest.json', manifest)
    write_json(out / 'manifest.sha256.json', {'sha256':sha256(out / 'manifest.json')})
    return manifest, tokenizer, examples, encoded


def verify_frozen(repo, out, manifest):
    if sha256(out / 'manifest.json') != json.loads((out / 'manifest.sha256.json').read_text())['sha256']:
        raise ValueError('immutable manifest changed')
    for name, expected in manifest['code'].items():
        if sha256(repo / name) != expected:
            raise ValueError('frozen code changed: ' + name)
    root = repo / manifest['config']['dataset_root']
    for name, expected in manifest['dataset'].items():
        if sha256(root / name) != expected:
            raise ValueError('frozen data changed: ' + name)
    for split,expected in manifest['encoded'].items():
        if sha256(Path(manifest['preflight'])/(split+'.encoded.private.jsonl'))!=expected:
            raise ValueError('frozen encoded split changed: '+split)
    if {n:version(n) for n in manifest['versions']}!=manifest['versions']:
        raise ValueError('frozen dependency versions changed')
    snapshot=Path(manifest['config']['tokenizer_local'])
    for name,expected in manifest['tokenizer']['files'].items():
        if sha256(snapshot/name)!=expected:
            raise ValueError('frozen tokenizer file changed: '+name)


def gpu_cost(start):
    import torch
    torch.cuda.synchronize()
    return dict(wall_s=time.perf_counter() - start, peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_reserved_bytes=torch.cuda.max_memory_reserved())


def generate(model, tokenizer, example, settings, journal, key):
    """Exactly one prompt-only call. A prior unresolved reservation is never retried."""
    import torch
    from src.task3.sft_v1_evaluation import parse_response
    labels = json.loads(example['prompt'][0]['content'].split('Allowed taxonomy labels: ', 1)[1])
    base = dict(example_id=example['example_id'], sample_id=example['sample_id'], level=example['level'])
    if key in journal.reserved():
        journal.append(dict(type='generation_interrupted_unknown',key=key))
        return dict(base, raw='', parsed=None, status='missing', finish_reason='interrupted_unknown',
                    input_tokens=0, output_tokens=0, wall_s=0., call_count_uncertain=True)
    inputs = tokenizer.apply_chat_template(example['prompt'], tokenize=True, add_generation_prompt=True,
                                           return_tensors='pt', return_dict=True)
    limit = settings['max_new_tokens'][str(example['level'])]
    if inputs['input_ids'].shape[1] + limit > 8192:
        raise ValueError('prompt plus generation allowance exceeds frozen context')
    inputs = {k:v.to('cuda:0') for k,v in inputs.items()}
    journal.reserve(key, 402)
    start = time.perf_counter()
    try:
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            output = model.generate(**inputs, do_sample=False, num_beams=1, max_new_tokens=limit,
                                    max_time=settings['max_time'], eos_token_id=settings['eos_token_id'],
                                    pad_token_id=settings['pad_token_id'], use_cache=True)
        torch.cuda.synchronize()
        tail = output[0, inputs['input_ids'].shape[1]:].tolist()
        wall = time.perf_counter() - start
        eos = bool(tail and tail[-1] == settings['eos_token_id'])
        reason = 'eos' if eos else 'length' if len(tail) >= limit else 'timeout' if wall >= settings['max_time'] else 'generation_error'
        raw = tokenizer.decode(tail, skip_special_tokens=True)
        parsed = parse_response(raw, labels, reason)
        result = dict(base, **parsed, raw=raw, finish_reason=reason, input_tokens=inputs['input_ids'].shape[1],
                      output_tokens=len(tail), wall_s=wall)
    except Exception as exc:
        if isinstance(exc, torch.cuda.OutOfMemoryError):
            raise
        result = dict(base, raw='', parsed=None, status='generation_error', finish_reason='generation_error',
                      input_tokens=inputs['input_ids'].shape[1], output_tokens=0,
                      wall_s=time.perf_counter()-start, error=str(exc))
    journal.append(dict(type='generation_completed', key=key, result=result))
    return result


def evaluate(model, tokenizer, examples, rows, directory, manifest, journal, state_name):
    import torch
    from src.task3.pilot_training import WeightedCompletionCollator, completion_mean_losses
    from src.task3.sft_v1_evaluation import aggregate_metrics, write_casebook
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / 'complete.json').exists():
        return json.loads((directory / 'complete.json').read_text())
    collator = WeightedCompletionCollator(tokenizer.pad_token_id)
    losses = read_jsonl(directory / 'losses.jsonl') if (directory / 'losses.jsonl').exists() else []
    done_loss = {r['example_id'] for r in losses}
    generations = read_jsonl(directory / 'generations.jsonl') if (directory / 'generations.jsonl').exists() else []
    done_generation = {r['example_id'] for r in generations}
    start = time.perf_counter(); torch.cuda.reset_peak_memory_stats()
    with evaluating(model):
        for row in rows:
            if row['example_id'] in done_loss:
                continue
            batch = collator([row]); tick = time.perf_counter()
            inputs = {k: batch[k].to('cuda:0') for k in ('input_ids','attention_mask')}
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                output = model(**inputs, use_cache=False)
                loss = float(completion_mean_losses(output.logits, batch['labels'].to('cuda:0'))[0])
            torch.cuda.synchronize()
            if not math.isfinite(loss):
                raise ValueError('nonfinite evaluation loss')
            result = dict(example_id=row['example_id'], level=row['level'], loss=loss,
                          completion_tokens=sum(x!=-100 for x in row['labels']), wall_s=time.perf_counter()-tick)
            Journal(directory / 'losses.jsonl').append(result); losses.append(result)
            del output, batch, inputs
        for example in examples:
            if example['example_id'] in done_generation:
                continue
            key = state_name + '/' + example['example_id']
            prior = [e['result'] for e in journal.events() if e.get('type')=='generation_completed' and e.get('key')==key]
            result = prior[-1] if prior else generate(model, tokenizer, example, manifest['generation'], journal, key)
            Journal(directory / 'generations.jsonl').append(result); generations.append(result)
            print(json.dumps(dict(phase=state_name, generated=len(generations), id=example['example_id'],
                                  status=result['status'], tokens=result['output_tokens']), ensure_ascii=False), flush=True)
    if len(losses) != len(examples) or len(generations) != len(examples):
        raise ValueError('incomplete or duplicate evaluation rows')
    summary = dict(mean_loss=sum(r['loss'] for r in losses)/len(losses),
        by_level_loss={str(level):sum(r['loss'] for r in losses if r['level']==level)/20 for level in range(1,5)},
        metrics=aggregate_metrics(examples, generations),
        teacher_forced=dict(forwards=len(losses), wall_s=sum(r['wall_s'] for r in losses)),
        generation=dict(calls=len(generations), wall_s=sum(r['wall_s'] for r in generations)), **gpu_cost(start))
    write_casebook(directory / 'casebook.html', examples, {state_name:generations})
    write_json(directory / 'complete.json', summary)
    return summary
