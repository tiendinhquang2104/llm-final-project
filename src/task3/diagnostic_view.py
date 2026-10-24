"""Deterministic log-only evidence projection with original line provenance.

Student code and every non-log requirement retain their original payload. This
module does not mutate units, compile source, deduplicate conflicting logs or
renumber excerpts. Full source catalogs remain the extraction authority.
"""
from __future__ import annotations

import copy
import json
import re
from collections import deque

from src.task3 import source_refs as refs

VERSION = 'diagnostic-primary-original-lines-v1'
LOG_SOURCES = ('provided_compile_log', 'local_compile_log')
_PRIMARY = re.compile(r'(?:^|:\s*)(?:fatal error|error|warning):', re.IGNORECASE)
_DIAGNOSTIC = re.compile(r':\d+(?::\d+)?:\s*(?:fatal error|error|warning|note):')
_GCC_CONTEXT = re.compile(r'^\s*(?:\d+\s*\||\|)')
_CARET = re.compile(r'^\s*[~^][~^\s]*$')


class ContextFailure(ValueError):
    category = 'context'


def _count(tokenizer, messages):
    return len(tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))


def _ranges(numbers):
    result = []
    for number in sorted(numbers):
        if result and result[-1][1] + 1 == number:
            result[-1][1] = number
        else:
            result.append([number, number])
    return result


def _primary_context(lines, index):
    """One compiler primary plus immediately associated source/caret lines."""
    chosen = {index + 1}
    if index and re.search(r': (?:In |At global scope)', lines[index - 1]):
        chosen.add(index)
    following = index + 1
    while following < min(len(lines), index + 5) and _GCC_CONTEXT.match(lines[following]):
        chosen.add(following + 1)
        following += 1
    # Clang emits unnumbered source followed by a caret. Require that pair rather
    # than treating arbitrary header/template prose as student-source context.
    if (following == index + 1 and following + 1 < len(lines)
            and _CARET.match(lines[following + 1].rstrip('\r\n'))
            and not _DIAGNOSTIC.search(lines[following])):
        chosen.update((following + 1, following + 2))
    return chosen


def _spread(values):
    """Select across the full log when not every primary fits (never prefix-only)."""
    if not values:
        return []
    order, used = [], set()
    for pos in (0, len(values) - 1):
        if pos not in used:
            order.append(values[pos]); used.add(pos)
    queue = deque([(0, len(values) - 1)])
    while queue:
        left, right = queue.popleft()
        if left > right:
            continue
        mid = (left + right) // 2
        if mid not in used:
            order.append(values[mid]); used.add(mid)
        queue.extend(((left, mid - 1), (mid + 1, right)))
    return order


def _source_audit(catalog, selected, primaries):
    result = {}
    for source, document in catalog.items():
        all_lines = set(range(1, document['line_count'] + 1))
        presented = selected.get(source, all_lines)
        primary = set(primaries.get(source, {}))
        result[source] = dict(sha256=document['sha256'], full_log_sha256=document['sha256']
                              if source in LOG_SOURCES else None,
                              line_count=document['line_count'], presented_ranges=_ranges(presented),
                              omitted_ranges=_ranges(all_lines - presented),
                              presented_line_count=len(presented), omitted_line_count=len(all_lines - presented),
                              primary_total_count=len(primary), primary_presented_count=len(primary & presented))
    return result


def prepare_messages(unit, messages, tokenizer, output_allowance, context_limit):
    """Return model messages and a private audit, projecting logs only on overflow.

    Reserve up to output_allowance+512 extra tokens for one targeted correction
    where the primary evidence allows it. The caller still checks the *actual*
    correction prompt, since a response's escaped representation can be larger.
    """
    if type(output_allowance) is not int or output_allowance < 0 or type(context_limit) is not int or context_limit <= 0:
        raise ValueError('nonnegative output allowance and positive context limit required')
    catalog = unit['source_catalog']
    original_tokens = _count(tokenizer, messages)
    primaries, lines_by_source = {}, {}
    for source in LOG_SOURCES:
        if source not in catalog:
            continue
        lines = catalog[source]['text'].splitlines(keepends=True)
        lines_by_source[source] = lines
        primaries[source] = {i + 1: _primary_context(lines, i) for i, line in enumerate(lines) if _PRIMARY.search(line)}

    def finish(current, selected, applied, reserve):
        source_audit = _source_audit(catalog, selected, primaries)
        incomplete = any(d['primary_presented_count'] < d['primary_total_count'] for d in source_audit.values())
        tokens = _count(tokenizer, current)
        audit = dict(version=VERSION, selection_applied=applied,
                     selection_reason='actual_prompt_plus_output_exceeds_context' if applied else 'original_prompt_fits',
                     sources=source_audit, incomplete_diagnostic_coverage=incomplete,
                     local_compiler=copy.deepcopy(unit.get('local_compiler', {})),
                     supplied_compiler=copy.deepcopy(unit.get('task', {}).get('compiler', {})),
                     provenance_policy='supplied/local logs remain separate; no message fusion or semantic disagreement inference',
                     token_accounting=dict(original_prompt_tokens=original_tokens, presented_prompt_tokens=tokens,
                                           output_allowance=output_allowance, context_limit=context_limit,
                                           correction_reserve_tokens=reserve,
                                           unused_context_tokens=context_limit - output_allowance - tokens),
                     original_messages_sha256=refs.source_sha(json.dumps(messages, ensure_ascii=False, sort_keys=True)),
                     presented_messages_sha256=refs.source_sha(json.dumps(current, ensure_ascii=False, sort_keys=True)))
        return current, audit

    if original_tokens + output_allowance <= context_limit:
        reserve = min(output_allowance + 512, context_limit - original_tokens - output_allowance)
        return finish(messages, {}, False, reserve)
    if not lines_by_source:
        raise ContextFailure('full code/requirements plus output exceed context; no diagnostic logs can be projected')
    # Locate the v1.5 system/user JSON payload. Correction messages appended later
    # stay untouched; they do not become a second evidence source.
    payload_index = None
    for index, message in enumerate(messages):
        if message.get('role') != 'user':
            continue
        try:
            value = json.loads(message['content'])
        except (TypeError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        source_payload = value if isinstance(value.get('sources'), dict) else value.get('task')
        if isinstance(source_payload, dict) and isinstance(source_payload.get('sources'), dict):
            payload_index, original_payload = index, value
            nested_task = source_payload is not value
            original_source_payload = source_payload
            break
    if payload_index is None:
        raise ContextFailure('v1.5 source-catalog user payload required for diagnostic projection')
    for source, document in catalog.items():
        shown = original_source_payload['sources'].get(source)
        if not isinstance(shown, dict) or shown.get('numbered_text') != refs.numbered(document):
            raise ContextFailure('diagnostic projection requires the complete original source view: ' + source)

    def render(selected):
        payload = copy.deepcopy(original_payload)
        source_payload = payload['task'] if nested_task else payload
        incomplete = any(set(groups) - selected[source] for source, groups in primaries.items())
        source_payload['diagnostic_view'] = dict(
            version=VERSION,
            notice='This is a selected diagnostic view, not the full compiler log. Original document line numbers are retained. '
                   'Reference only presented ranges. Full code and requirements remain unchanged. '
                   'Do not claim exhaustive compiler analysis when coverage is incomplete.',
            incomplete_diagnostic_coverage=incomplete,
            sources={source: dict(presented_ranges=_ranges(selected[source]),
                                  omitted_line_count=len(lines_by_source[source]) - len(selected[source]))
                     for source in lines_by_source})
        for source, lines in lines_by_source.items():
            source_payload['sources'][source]['numbered_text'] = ''.join(
                f'{number} | {lines[number - 1]}' for number in sorted(selected[source]))
        # v1.5's legacy projection omits toolchain identity; preserve it on the
        # selected view as well as in the private audit without exposing gold.
        tool = unit.get('local_compiler', {}).get('toolchain_fingerprint')
        if tool:
            source_payload.setdefault('local_compiler', {})['toolchain_fingerprint'] = tool
        current = copy.deepcopy(messages)
        current[payload_index]['content'] = json.dumps(payload, ensure_ascii=False)
        return current

    empty = {source: set() for source in lines_by_source}
    budget = context_limit - output_allowance
    if _count(tokenizer, render(empty)) > budget:
        raise ContextFailure('full code/requirements and projection metadata plus output exceed context; source not trimmed')
    all_groups = {source: set().union(*groups.values()) if groups else set()
                  for source, groups in primaries.items()}
    full_primary_view = render(all_groups)
    full_primary_tokens = _count(tokenizer, full_primary_view)
    if full_primary_tokens <= budget:
        reserve = min(output_allowance + 512, budget - full_primary_tokens)
        return finish(full_primary_view, all_groups, True, reserve)
    # Prefer primary diagnostics across the complete logs before any notes.
    primary_only = {source: set(groups) for source, groups in primaries.items()}
    primary_tokens = _count(tokenizer, render(primary_only))
    if primary_tokens <= budget:
        selected = primary_only
        for source, groups in primaries.items():
            for number in _spread(sorted(groups)):
                trial = {name: set(values) for name, values in selected.items()}
                trial[source].update(groups[number])
                if _count(tokenizer, render(trial)) <= budget:
                    selected = trial
    else:
        selected = empty
        # Round-robin provenance prevents a large supplied log starving local
        # evidence, while spread ordering retains late diagnostics.
        ordered = {source: deque(_spread(sorted(groups))) for source, groups in primaries.items()}
        while any(ordered.values()):
            for source, queue in ordered.items():
                if not queue:
                    continue
                number = queue.popleft()
                trial = {name: set(values) for name, values in selected.items()}
                trial[source].update(primaries[source][number])
                if _count(tokenizer, render(trial)) <= budget:
                    selected = trial
        # If context makes every group too large, still try the primaries alone.
        if not any(selected.values()):
            for source, groups in primaries.items():
                for number in _spread(sorted(groups)):
                    trial = {name: set(values) for name, values in selected.items()}
                    trial[source].add(number)
                    if _count(tokenizer, render(trial)) <= budget:
                        selected = trial
    current = render(selected)
    return finish(current, selected, True, min(output_allowance + 512, budget - _count(tokenizer, current)))


def validate_presented_refs(findings, view_audit, unit):
    """Reject any valid original log coordinate absent from this call's view."""
    catalog = unit['source_catalog']
    audited = view_audit.get('sources', {})
    for source, document in catalog.items():
        if (source not in audited or audited[source].get('sha256') != document['sha256']
                or audited[source].get('line_count') != document['line_count']):
            raise ValueError('diagnostic view/source catalog identity mismatch: ' + source)
    for i, finding in enumerate(findings):
        for j, ref in enumerate(finding['evidence_refs']):
            path = f'findings[{i}].evidence_refs[{j}]'
            refs.extract(catalog, ref, path)
            source = ref['source']
            if source not in LOG_SOURCES:
                continue
            ranges = audited[source]['presented_ranges']
            if not any(start <= ref['start_line'] <= ref['end_line'] <= end for start, end in ranges):
                exc = refs.ReferenceFailure('log reference contains lines not presented to this detector call', path, ref, catalog)
                exc.details['presented_ranges'] = copy.deepcopy(ranges)
                raise exc
    return findings
