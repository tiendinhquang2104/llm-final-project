"""Generic one-forward-pass finite choices; raw logits are not confidence.

The existing official taxonomy resolver is intentionally independent. This
module performs no API call, generation, journaling, retry or context trimming.
The caller owns durable reservations and actual-prompt context validation.
"""
from __future__ import annotations

import time

VERSION = 'completion16-finite-logits-v1'


def choice_token_ids(tokenizer, codes: list[str]) -> list[int]:
    """Verify 1–17 distinct A–Q transport symbols against this tokenizer."""
    if (not isinstance(codes, list) or not 1 <= len(codes) <= 17
            or any(not isinstance(code, str) or len(code) != 1 or not 'A' <= code <= 'Q' for code in codes)
            or len(set(codes)) != len(codes)):
        raise ValueError('finite choices require 1–17 distinct A–Q codes')
    special = set(getattr(tokenizer, 'all_special_ids', []))
    special.add(getattr(tokenizer, 'unk_token_id', None))
    ids = []
    for code in codes:
        encoded = tokenizer.encode(code, add_special_tokens=False)
        if (len(encoded) != 1 or type(encoded[0]) is not int
                or not 0 <= encoded[0] < len(tokenizer) or encoded[0] in special
                or tokenizer.decode(encoded) != code):
            raise RuntimeError('finite-choice code is not a valid single token: ' + code)
        ids.append(encoded[0])
    if len(set(ids)) != len(ids):
        raise RuntimeError('finite-choice codes must have distinct token IDs')
    return ids


def select(backend, messages, choices: dict) -> dict:
    """Restrict next-token logits to choices, retaining the exact mapped value.

    Dict insertion order is the disclosed tie break. A None/sentinel value is
    returned unchanged; interpreting it and any bounded follow-up is the caller's
    responsibility. Scores follow the same order as token_ids and choices.
    """
    if not isinstance(choices, dict):
        raise ValueError('finite choices must be a code-to-value dict')
    codes = list(choices)
    ids = choice_token_ids(backend.tokenizer, codes)
    torch = backend.torch
    inputs = backend.tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors='pt', return_dict=True
    ).to(backend.model.device)
    input_tokens = int(inputs['input_ids'].shape[-1])
    cuda = str(backend.model.device).startswith('cuda')
    if cuda:
        torch.cuda.synchronize()
    started = time.perf_counter()
    with torch.inference_mode():
        output = backend.model(**inputs, use_cache=False, logits_to_keep=1)
        if max(ids) >= output.logits.shape[-1]:
            raise RuntimeError('finite-choice token outside model logits vocabulary')
        scores = output.logits[0, -1, ids].float()
        if not bool(torch.isfinite(scores).all()):
            raise RuntimeError('nonfinite constrained-choice logits')
        selected = int(torch.argmax(scores).item())
        score_values = scores.cpu().tolist()
    if cuda:
        torch.cuda.synchronize()
    code = codes[selected]
    return dict(code=code, value=choices[code], scores=score_values, token_ids=ids,
                score_kind='restricted raw logits; not probability of diagnostic correctness',
                finish_reason='constrained_choice', forward_passes=1,
                latency_s=time.perf_counter() - started, input_tokens=input_tokens, output_tokens=0)
