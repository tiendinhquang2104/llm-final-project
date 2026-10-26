#!/usr/bin/env python3
"""Offline public comparison and blinded review preparation; never semantic grading.

All V2 payloads are re-parsed from raw responses with the frozen native parser.
Historical predictions come exclusively from the manifest-selected, hash-verified
candidate. No model, compiler, retries, repairs, gold labels or score estimation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.synth.feedback import FEEDBACK_LEVELS
from src.task3.schema import validate_taxonomy
from src.task3.sft_v1_evaluation import parse_response, _schema_error
from src.task3.submission import load_requested_levels

DEFAULT_OUT = 'outputs/task3/sft-v2-public-20261026-run1'
RISK_ORDER = ['empty_nonempty_taxonomy_transition', 'different_label_set', 'language_flag', 'feedback_length_over_800']


def sha(value):
    return hashlib.sha256(value).hexdigest()


def level_number(value):
    if type(value) is int and value in range(1, 5):
        return value
    if value in FEEDBACK_LEVELS:
        return FEEDBACK_LEVELS.index(value) + 1
    raise ValueError('invalid authoritative Level')


def language_flag(text):
    """Triage only: absence of Vietnamese-specific letters is not a verdict."""
    if not isinstance(text, str) or not text.strip():
        return None
    specific = 'ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ'
    return 'no_vietnamese_specific_letters' if not any(c in specific for c in text.lower()) else None


def feedback_stats(output):
    text = output.get('feedback') if isinstance(output, dict) else None
    return {'characters': len(text) if isinstance(text, str) else None,
            'words': len(text.split()) if isinstance(text, str) else None,
            'language_flag_heuristic': language_flag(text)}


def historical_output(row, labels, raw=None):
    result = {'status': 'invalid', 'payload': None, 'raw': raw if raw is not None else json.dumps(row, ensure_ascii=False), 'error': None}
    if not isinstance(row, dict) or set(row) != {'sample_id', 'output'}:
        result['error'] = 'official row must contain exactly sample_id and output'
    else:
        output = row['output']
        error = _schema_error(output, labels)
        if error:
            result['error'] = error
        else:
            try:
                validate_taxonomy(output['taxonomy_error'])
            except (ValueError, TypeError) as exc:
                result['error'] = str(exc)
            else:
                result.update(status='valid', payload=output)
    result['feedback'] = feedback_stats(result['payload'])
    return result


def _index(rows, requested, role):
    grouped = defaultdict(list)
    foreign = []
    for row in rows:
        sid = row.get('sample_id', row.get('example_id')) if isinstance(row, dict) else None
        if not isinstance(sid, str) or sid not in requested:
            if role in ('v2', 'input'):
                raise ValueError(role + ' extra or invalid exact ID: ' + str(sid))
            foreign.append(row)
            continue
        grouped[sid].append(row)
    if role in ('v2', 'input') and any(len(values) != 1 for values in grouped.values()):
        raise ValueError(role + ' duplicate ID')
    return grouped, foreign


def compare(requested, bindings, generations, comparator_rows, labels, selection, *, comparator_raw=None, fixed_only=False):
    """Return rows, aggregate summary, selected packets and a separate blind key."""
    if not isinstance(requested, dict) or not requested:
        raise ValueError('nonempty authoritative requested ID map required')
    levels = {sid: level_number(value) for sid, value in requested.items()}
    if any(not isinstance(sid, str) or not sid for sid in levels):
        raise ValueError('invalid requested ID')
    inputs, _ = _index(bindings, requested, 'input')
    if set(inputs) != set(requested):
        raise ValueError('input bindings must cover exact authoritative IDs')
    generated, _ = _index(generations, requested, 'v2')
    historical, foreign = _index(comparator_rows, requested, 'comparator')
    fixed = selection.get('ids', [])
    if not isinstance(fixed, list) or len(set(fixed)) != len(fixed) or any(s not in levels for s in fixed):
        raise ValueError('fixed review IDs must be unique authoritative IDs')
    seed = selection.get('seed')
    if not isinstance(seed, str) or not seed:
        raise ValueError('frozen review seed required')
    policy = selection.get('additional_risk_policy', {})
    if (policy.get('rank') != RISK_ORDER or policy.get('maximum') != 24 or
            policy.get('exclude_fixed_slice') is not True or policy.get('tie') != 'sha256(seed + | + sample_id)'):
        raise ValueError('risk policy differs from frozen review selection')
    rows = []
    for sid, level in levels.items():
        binding = inputs[sid][0]
        if level_number(binding.get('level', binding.get('requested_level'))) != level:
            raise ValueError('input authoritative Level mismatch: ' + sid)
        mapped = binding.get('mapped_input')
        if not isinstance(mapped, dict) or any(not isinstance(mapped.get(k), str) for k in ('code', 'statement')):
            raise ValueError('full mapped source and statement required: ' + sid)
        g = generated.get(sid, [None])[0]
        if g is not None:
            if 'example_id' in g and g['example_id'] != sid:
                raise ValueError('generation example ID disagrees with official ID: ' + sid)
            if level_number(g.get('level')) != level:
                raise ValueError('generation authoritative Level mismatch: ' + sid)
        parsed = parse_response(g.get('raw') if g else None, labels, g.get('finish_reason', 'missing') if g else 'missing')
        status = 'valid' if parsed['status'] == 'valid' else 'missing' if g is None else 'invalid'
        original_status = g.get('status') if g else None
        phase = ('preflight' if isinstance(original_status, str) and 'preflight_failure' in original_status else
                 'missing' if g is None else
                 'interrupted_or_not_called' if g.get('raw') is None else
                 'response' if status != 'valid' else None)
        v2 = {'original_generation_status': original_status, 'failure_phase': phase,
              'response_invalid': phase == 'response' and status != 'valid',
              'generation_diagnostics': {k: v for k, v in g.items() if k not in ('raw', 'parsed')} if g else None,
              'status': status, 'parse_status': parsed['status'], 'payload': parsed['parsed'],
              'raw': g.get('raw') if g else None, 'finish_reason': g.get('finish_reason') if g else 'missing',
              'error': parsed['error'], 'feedback': feedback_stats(parsed['parsed'])}
        h = historical.get(sid, [])
        if not h:
            old = {'status': 'missing', 'payload': None, 'raw': None, 'error': 'comparator ID absent', 'feedback': feedback_stats(None)}
        elif len(h) > 1:
            old = {'status': 'incompatible', 'payload': None, 'raw': (comparator_raw or {}).get(sid, json.dumps(h, ensure_ascii=False)),
                   'error': 'duplicate comparator ID; no per-ID selection permitted', 'feedback': feedback_stats(None)}
        else:
            old = historical_output(h[0], labels, (comparator_raw or {}).get(sid))
        transition = None
        changed = None
        if v2['status'] == old['status'] == 'valid':
            before = old['payload']['taxonomy_error']; after = v2['payload']['taxonomy_error']
            transition = ('nonempty' if before else 'empty') + '_to_' + ('nonempty' if after else 'empty')
            changed = set(before) != set(after)
        flags = {'empty_nonempty_taxonomy_transition': transition in ('empty_to_nonempty', 'nonempty_to_empty'),
                 'different_label_set': changed is True,
                 'language_flag': any(o['feedback']['language_flag_heuristic'] for o in (v2, old)),
                 'feedback_length_over_800': any((o['feedback']['characters'] or 0) > 800 for o in (v2, old))}
        reasons = [name for name in RISK_ORDER if flags[name]]
        rows.append({'sample_id': sid, 'level': level, 'requested_level': requested[sid], 'v2': v2, 'comparator': old,
                     'taxonomy_transition': transition, 'label_set_changed': changed,
                     'risk_reasons': reasons, 'risk_rank': RISK_ORDER.index(reasons[0]) if reasons else None,
                     'tie_sha256': sha((seed + '|' + sid).encode())})
    candidates = [] if fixed_only else [r for r in rows if r['sample_id'] not in fixed and r['risk_reasons']]
    candidates.sort(key=lambda r: (r['risk_rank'], r['tie_sha256'], r['sample_id']))
    additional = [r['sample_id'] for r in candidates[:24]]
    invalid = [r['sample_id'] for r in rows if r['v2']['response_invalid'] or r['comparator']['status'] in ('invalid', 'incompatible')]
    preflight = [r['sample_id'] for r in rows if r['v2']['failure_phase'] == 'preflight']
    missing = [r['sample_id'] for r in rows if any(r[m]['status'] == 'missing' for m in ('v2', 'comparator'))]
    groups = {'fixed': fixed, 'additional_risk': additional, 'all_invalid': invalid}
    selected_ids = set(fixed) if fixed_only else set(fixed) | set(additional) | set(invalid)
    packets = []; key = {}; all_packets = []
    for row in rows:
        sid = row['sample_id']; review_id = sha((seed + '|blind|' + sid).encode())[:24]
        order = ['v2', 'comparator'] if int(sha((seed + '|order|' + sid).encode()), 16) % 2 == 0 else ['comparator', 'v2']
        outputs = {opaque: {k: v for k, v in row[method].items() if k != 'generation_diagnostics'}
                   for opaque, method in zip(('A', 'B'), order)}
        packet = {'review_id': review_id, 'sample_id': sid, 'level': row['level'],
                  'review_groups': [name for name, ids in groups.items() if sid in ids],
                  'input': inputs[sid][0], 'outputs': outputs, 'review_status': 'pending_source_grounded_review'}
        all_packets.append(packet)
        key[review_id] = {'sample_id': sid, 'methods': dict(zip(('A', 'B'), order))}
        if sid in selected_ids:
            packets.append(packet)
    def counts(subset):
        return {method: {status: sum(r[method]['status'] == status for r in subset)
                         for status in ('valid', 'invalid', 'missing', 'incompatible')} for method in ('v2', 'comparator')}
    summary = {'targets': len(rows), 'methods': counts(rows),
               'by_level': {str(level): {'targets': sum(r['level'] == level for r in rows), 'methods': counts([r for r in rows if r['level'] == level])} for level in sorted(set(levels.values()))},
               'taxonomy_transitions': dict(Counter(r['taxonomy_transition'] for r in rows if r['taxonomy_transition'] is not None)),
               'label_set_changes': sum(r['label_set_changed'] is True for r in rows),
               'transition_denominator_two_valid': sum(r['taxonomy_transition'] is not None for r in rows),
               'comparator_foreign_records': foreign, 'comparator_foreign_count': len(foreign),
               'v2_failure_breakdown': dict(Counter(r['v2']['failure_phase'] for r in rows if r['v2']['failure_phase'])),
               'v2_original_status_counts': dict(Counter(str(r['v2']['original_generation_status']) for r in rows)),
               'v2_invalid_response_count': sum(r['v2']['response_invalid'] for r in rows),
               'structural_status_note': 'invalid denotes a recorded target without a structurally usable payload, including preflight failures; response_invalid and failure_phase separate actual response failures from uncalled targets.',
               'language_flags_are_heuristics_only': True, 'public_gold_available': False,
               'semantic_review_performed': False,
               'interpretation': 'Descriptive output comparison only; no accuracy, F1 or improvement inference. Risk review is not a representative accuracy sample.'}
    risk = {'seed': seed, 'frozen_policy': policy, 'fixed_ids': fixed, 'additional_ids': additional,
            'all_invalid_ids': invalid, 'preflight_failure_ids': preflight, 'missing_ids': missing, 'candidate_count': len(candidates),
            'unique_review_ids': [r['sample_id'] for r in rows if r['sample_id'] in selected_ids],
            'counts': {'fixed': len(fixed), 'additional_risk': len(additional), 'all_invalid': len(invalid),
                       'fixed_invalid_overlap': len(set(fixed) & set(invalid)),
                       'risk_invalid_overlap': len(set(additional) & set(invalid)), 'unique': len(selected_ids)}}
    return {'rows': rows, 'summary': summary, 'risk_selection': risk, 'packets': packets, 'blind_key': key, 'all_packets': all_packets}



def prepare_fixed_packets(requested, bindings, generations, comparator_rows, labels, selection, *, comparator_raw=None):
    """Prepare only completed fixed-slice packets during inference; select no risk cases.

    This pure helper writes nothing. Callers may persist its packets and separate
    blind key in review-progress/ while inference continues. Preflight failures,
    uncalled/interrupted slots and absent generations stay pending for this slice.
    A completed but malformed response remains reviewable with its exact raw text.
    """
    result = compare(requested, bindings, generations, comparator_rows, labels, selection,
                     comparator_raw=comparator_raw, fixed_only=True)
    ready = {r['sample_id'] for r in result['rows'] if r['v2']['raw'] is not None}
    packets = [p for p in result['packets'] if p['sample_id'] in ready]
    review_ids = {p['review_id'] for p in packets}
    return {'selection_type': 'fixed_only_inference_progress', 'packets': packets,
            'blind_key': {rid: value for rid, value in result['blind_key'].items() if rid in review_ids},
            'pending_fixed_ids': [sid for sid in selection['ids'] if sid not in ready],
            'additional_risk_selected': False, 'semantic_review_performed': False}


def exact_array(path):
    """Decode an official array and retain each original record's JSON text."""
    text = path.read_text(encoding='utf-8'); decoder = json.JSONDecoder(); index = 0
    while index < len(text) and text[index].isspace(): index += 1
    if index == len(text) or text[index] != '[':
        raise ValueError('comparator official wrapper must be a JSON array')
    index += 1; rows = []; raw = defaultdict(list)
    while True:
        while index < len(text) and text[index].isspace(): index += 1
        if index < len(text) and text[index] == ']':
            index += 1; break
        start = index; row, index = decoder.raw_decode(text, index); rows.append(row)
        sid = row.get('sample_id') if isinstance(row, dict) else None
        if isinstance(sid, str): raw[sid].append(text[start:index])
        while index < len(text) and text[index].isspace(): index += 1
        if index < len(text) and text[index] == ',':
            index += 1
        elif index < len(text) and text[index] == ']':
            index += 1; break
        else: raise ValueError('invalid comparator JSON array separator')
    if text[index:].strip(): raise ValueError('extra text after comparator array')
    # Strict JSON decode additionally rejects trailing commas accepted by loop above.
    if json.loads(text) != rows: raise ValueError('comparator decoding mismatch')
    return rows, {sid: values[0] if len(values) == 1 else values for sid, values in raw.items()}


def casebook_html(packets):
    chunks = ['<!doctype html><html lang="vi"><meta charset="utf-8"><title>Blinded public review preparation</title>',
              '<style>body{font:15px system-ui;max-width:1500px;margin:2rem auto;padding:1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f5f5;padding:1rem}.pair{display:grid;grid-template-columns:1fr 1fr;gap:1rem}article{border-top:2px solid #888;margin-top:2rem}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>',
              '<h1>Public review preparation</h1><p>Pending source-grounded review. Method identities are in a separate private key. Language flags are triage heuristics; transitions do not establish improvements.</p>']
    def block(value):
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<pre>' + html.escape(text) + '</pre>'
    for p in packets:
        inp = p['input']; mapped = inp['mapped_input']
        chunks.append('<article><h2>' + html.escape(p['sample_id']) + ' — Level ' + str(p['level']) + '</h2>')
        chunks.append(block({'review_id': p['review_id'], 'groups': p['review_groups'], 'exam_type': mapped.get('exam_type')}))
        for label, value in [('Full mapped statement', mapped['statement']), ('Original source', mapped['code']),
                             ('Mapped attributed logs', mapped.get('compile_log')), ('Dataset supplied log', inp.get('supplied_log')), ('Local syntax evidence', inp.get('local_syntax'))]:
            chunks.append('<h3>' + label + '</h3>' + block(value))
        chunks.append('<div class="pair">')
        for method in ('A', 'B'):
            o = p['outputs'][method]
            chunks.append('<section><h3>Output ' + method + '</h3>' + block({'status': o['status'], 'error': o.get('error')}))
            chunks.append('<h4>Exact raw response / historical record</h4>' + block(o['raw']))
            chunks.append('<h4>Parsed payload</h4>' + block(o['payload']) + '</section>')
        chunks.append('</div></article>')
    return '\n'.join(chunks) + '</html>\n'


def run(out):
    out = Path(out).resolve(); names = ['generations.jsonl', 'public-inputs.private.jsonl', 'requested-levels.private.json', 'review-selection.json', 'official-contract.json', 'ar15-audit/comparator-manifest.json']
    paths = {name: out / name for name in names}
    manifest = json.loads(paths['ar15-audit/comparator-manifest.json'].read_text())
    selected = manifest.get('selected')
    if selected is None:
        comparator = []; raw = {}; provenance = {'status': 'unavailable', 'selected': None}
    else:
        candidate = Path(selected['candidate_path'])
        if not candidate.is_absolute(): candidate = Path.cwd() / candidate
        if sha(candidate.read_bytes()) != selected['sha256']:
            raise ValueError('selected comparator hash mismatch')
        comparator, raw = exact_array(candidate)
        provenance = {'status': 'hash_verified', 'selected': selected, 'score_link': manifest.get('score_link')}
    requested = load_requested_levels(paths['requested-levels.private.json'])
    contract = json.loads(paths['official-contract.json'].read_text())
    if 'requested_levels' in contract and contract['requested_levels'] != requested:
        raise ValueError('official contract requested Levels differ')
    load_lines = lambda path: [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    result = compare(requested, load_lines(paths['public-inputs.private.jsonl']), load_lines(paths['generations.jsonl']),
                     comparator, contract['taxonomy_labels'], json.loads(paths['review-selection.json'].read_text()), comparator_raw=raw)
    summary = result['summary']; summary['comparator_provenance'] = provenance
    summary['input_sha256'] = {name: sha(path.read_bytes()) for name, path in paths.items()}
    summary['implementation_sha256'] = sha(Path(__file__).read_bytes())
    destination = out / 'public-comparison'
    if destination.exists(): raise FileExistsError('comparison output already exists; preserve prior artifacts')
    destination.mkdir()
    def write(name, value):
        (destination / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    def lines(name, values):
        (destination / name).write_text(''.join(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n' for value in values), encoding='utf-8')
    write('comparison.json', summary); lines('comparison.jsonl', result['rows'])
    write('risk-selection.json', result['risk_selection']); lines('blinded-review-packets.jsonl', result['packets'])
    write('blinding-key.private.json', result['blind_key'])
    (destination / 'casebook.html').write_text(casebook_html(result['all_packets']), encoding='utf-8')
    write('artifact-sha256.json', {f.name: sha(f.read_bytes()) for f in sorted(destination.iterdir()) if f.is_file()})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path(DEFAULT_OUT), help='fresh public run directory; output is its public-comparison subdirectory')
    args = parser.parse_args()
    report = run(args.out)
    print(json.dumps({'targets': report['targets'], 'methods': report['methods'], 'semantic_review_performed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
