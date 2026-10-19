"""Mechanical completion signals only; never a diagnosis or pedagogical grade."""
from __future__ import annotations

import re


def inspect_generation(text, *, output_tokens, max_new_tokens, finish_reason=None, eos_reached=None):
    cap = output_tokens >= max_new_tokens
    signals = []
    if cap:
        signals.append("token_cap_reached")
    # Match closing fence character and minimum length; mixed markers never close.
    opened = None
    code_lines = []
    blocks = []
    for line in text.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if opened is None:
            if marker:
                opened = (marker[1][0], len(marker[1]), marker[2].strip().lower())
                code_lines = []
        elif marker and marker[1][0] == opened[0] and len(marker[1]) >= opened[1] and not marker[2].strip():
            blocks.append((opened[2], "\n".join(code_lines)))
            opened = None
        else:
            code_lines.append(line)
    unclosed = opened is not None
    if unclosed:
        signals.append("unclosed_code_fence")
    unbalanced = False
    for language, code in blocks:
        if language not in ('cpp', 'c++', 'cxx', 'c', ''):
            continue
        lexical = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/', '', code, flags=re.S)
        depth = 0
        for char in lexical:
            depth += (char == '{') - (char == '}')
            if depth < 0:
                unbalanced = True
        unbalanced |= depth != 0
    if unbalanced:
        signals.append("unbalanced_code_braces")
    cutoff = finish_reason == 'length' or (cap and eos_reached is not True)
    if cutoff:
        signals.append("length_stop_or_cap_without_observed_eos")
    if text.rstrip() and text.rstrip()[-1].isalnum():
        signals.append("unfinished_sentence_review_candidate")
    return {"token_cap_reached": cap, "finish_reason": finish_reason or 'unknown', "eos_reached": eos_reached, "finish_reason_source": 'backend_token_ids_and_limit' if finish_reason else 'not_available', "signals": signals, "mechanically_complete": not (unclosed or unbalanced or cutoff), "semantic_quality": "NOT_MEASURED"}
