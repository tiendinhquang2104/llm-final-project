"""Explicit-context native generation; historically frozen generator remains untouched.

The function below retains the original generate body; only its guard receives
an explicit positive context_limit. All decoding/parser/one-attempt behavior is
unchanged. Runtime preparation and freeze are in the companion CLI module.
"""
import json
import time
from src.task3.sft_v2_public import context_preflight


def preflight(tokenizer,examples,settings,context_limit):
    return context_preflight(tokenizer,examples,settings,context=context_limit)


def generate(model, tokenizer, example, settings, journal, key, context_limit):
    """Exactly one prompt-only call. A prior unresolved reservation is never retried."""
    if type(context_limit) is not int or context_limit < 1: raise ValueError("positive explicit inference context required")
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
    if inputs['input_ids'].shape[1] + limit > context_limit:
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

