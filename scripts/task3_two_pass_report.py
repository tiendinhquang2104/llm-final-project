#!/usr/bin/env python3
"""Offline packets and scoring for this complete development run; no model calls."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.task3.dataset import write_json
from src.task3.level_blind import read, sha
from src.task3.grounded_metrics import taxonomy_metrics
from src.synth.taxonomy import LABEL_SPACE

OUT = ROOT / 'outputs/task3/two-pass-20261023'
REVIEW = OUT / 'review'


def verify_source_seal():
    seal = read(REVIEW / 'source-seal.json')
    assert seal['source_before_outputs_and_gold']
    assert set(seal['hashes']) == {'source-a.private.json', 'source-b.private.json'}
    for name, h in seal['hashes'].items():
        assert sha(REVIEW / name) == h, name
    return seal


def packets():
    """Run once, after source-first seals; reviewers must not inspect the key."""
    if (REVIEW / 'blind-key.private.json').exists():
        raise ValueError('Review packet already frozen')
    seal = verify_source_seal()
    # Independently bind the exact source records, irrespective of seal layout.
    source_a = read(REVIEW / 'source-a.private.json')
    source_b = read(REVIEW / 'source-b.private.json')
    assert source_a['output_unseen'] and source_b['output_unseen'] and seal
    units = read(OUT / 'units.private.json')
    control = {r['sample_id']: r['output'] for r in read(OUT / 'control.private.json')}
    candidate = {r['sample_id']: r['output'] for r in read(OUT / 'B/results.private.json')}
    rng = random.Random(2026102302)
    cases, key = [], {}
    for unit in units:
        sid = unit['sample_id']
        arms = [('R15', control[sid]), ('two_pass', candidate[sid])]
        rng.shuffle(arms)
        outputs = []
        for arm, output in arms:
            oid = hashlib.sha256((sid + ':' + arm + ':blind-v1').encode()).hexdigest()[:16]
            key[oid] = {'sample_id': sid, 'arm': arm}
            outputs.append({'output_id': oid, 'output': output})
        cases.append({'sample_id': sid, 'level': unit['level'], 'task': unit['task'], 'outputs': outputs})
    policy = {
        'instructions': 'Read your already sealed source diagnosis first. Score each anonymous output independently. Do not read blind key, original gold, raw generation, notes, prior reviews or infer branch identity. No model generation or source execution.',
        'official_levels': read(OUT / 'frozen/level-definitions.json'),
        'rubric': {
            'finding_supported': 'true only if ALL substantive feedback claims agree with source; false if any unsupported claim',
            'main_covered': 'main defect recognized; for source-correct case, warranted praise; L1 broad warranted warning counts',
            'false_claim': 'any substantive false/unsupported claim, including fabricated successful execution/reviewer context',
            'consistent': 'feedback agrees with final taxonomy, including empty taxonomy',
            'level_ok': 'L1 no location/cause/repair; L2 location+cause without concrete or implicit repair; L3 diagnosis+feasible repair direction, no full solution. For clean source brief warranted praise is appropriate at any Level.',
            'l2_repair_leak': 'boolean for L2, null otherwise. Naming the current erroneous token/location is not automatically a repair. Explicit replacement or instruction to insert/remove/change is a leak, including natural-language equivalents.',
            'l3_actionable': 'boolean for L3 erroneous source; null otherwise. Missing syntax token diagnosis that directly enables local correction counts; generic study/check advice alone does not.',
            'natural': 'natural comprehensible Vietnamese appropriate to the actual task',
            'generic_only': 'true only if no useful source-grounded assessment; L1 general warranted hint is not automatically generic failure',
            'disputed': 'record uncertainty; do not force unsupported credit',
            'evidence': 'list of {source_quote, feedback_quote, reason}; exact substrings of source/statement/grading_policy and output feedback',
        },
        'response_schema': {'reviewer': 'A or B', 'cases': [{'sample_id': '...', 'outputs': [{'output_id': '...', 'finding_supported': True, 'main_covered': True, 'false_claim': False, 'consistent': True, 'level_ok': True, 'l2_repair_leak': None, 'l3_actionable': None, 'natural': True, 'generic_only': False, 'disputed': False, 'evidence': [], 'reason': 'brief source-grounded reason'}]}]},
    }
    for who, ids in [('a', {u['sample_id'] for u in units}), ('b', {c['sample_id'] for c in source_b['cases']})]:
        write_json(REVIEW / f'paired-packet-{who}.private.json', {**policy, 'cases': [c for c in cases if c['sample_id'] in ids]})
    write_json(REVIEW / 'blind-key.private.json', key)
    names = ['paired-packet-a.private.json', 'paired-packet-b.private.json', 'blind-key.private.json', 'source-a.private.json', 'source-b.private.json', 'source-seal.json']
    write_json(REVIEW / 'packet-seal.json', {n: sha(REVIEW / n) for n in names})
    print(json.dumps({'A_cases': len(cases), 'B_cases': len(source_b['cases']), 'sealed': True}))


def validate_review(path, packet):
    review = read(path)
    cases = {c['sample_id']: c for c in review['cases']}
    assert len(cases) == len(review['cases']) == len(packet['cases'])
    assert set(cases) == {c['sample_id'] for c in packet['cases']}
    for c in packet['cases']:
        rows = {o['output_id']: o for o in cases[c['sample_id']]['outputs']}
        assert len(rows) == len(cases[c['sample_id']]['outputs']) == 2
        assert set(rows) == {o['output_id'] for o in c['outputs']}
        source = '\n'.join(str(c['task'].get(k, '')) for k in ['statement', 'code', 'grading_policy'])
        for o in c['outputs']:
            r = rows[o['output_id']]
            for name in ['finding_supported', 'main_covered', 'false_claim', 'consistent', 'level_ok', 'natural', 'generic_only', 'disputed']:
                assert type(r[name]) is bool, (path, name)
            for name in ['l2_repair_leak', 'l3_actionable']:
                assert r[name] is None or type(r[name]) is bool
            assert (r['l2_repair_leak'] is not None) == (c['level'] == 2)
            for e in r['evidence']:
                assert e['source_quote'] in source, (path, c['sample_id'], e['source_quote'])
                assert e['feedback_quote'] in o['output']['feedback'], (path, c['sample_id'], e['feedback_quote'])
    return review


def extra_packet():
    source = read(REVIEW / 'source-b-extra.private.json')
    assert source['output_unseen']
    wanted = {c['sample_id'] for c in source['cases']}
    packet = read(REVIEW / 'paired-packet-a.private.json')
    packet['cases'] = [c for c in packet['cases'] if c['sample_id'] in wanted]
    assert len(packet['cases']) == len(wanted)
    path = REVIEW / 'paired-packet-b-extra.private.json'
    assert not path.exists()
    write_json(path, packet)
    write_json(REVIEW / 'extra-packet-seal.json', {'source_sha256': sha(REVIEW / 'source-b-extra.private.json'), 'packet_sha256': sha(path)})


def seal_reviews():
    for name, h in read(REVIEW / 'packet-seal.json').items():
        assert sha(REVIEW / name) == h, name
    paths = ['source-a.private.json', 'source-b.private.json', 'paired-a.private.json', 'paired-b.private.json']
    for who in ['a', 'b']:
        validate_review(REVIEW / f'paired-{who}.private.json', read(REVIEW / f'paired-packet-{who}.private.json'))
    if (REVIEW / 'paired-b-extra.private.json').exists():
        assert sha(REVIEW / 'source-b-extra.private.json') == read(REVIEW / 'extra-packet-seal.json')['source_sha256']
        assert sha(REVIEW / 'paired-packet-b-extra.private.json') == read(REVIEW / 'extra-packet-seal.json')['packet_sha256']
        validate_review(REVIEW / 'paired-b-extra.private.json', read(REVIEW / 'paired-packet-b-extra.private.json'))
        paths += ['source-b-extra.private.json', 'paired-b-extra.private.json', 'extra-packet-seal.json', 'paired-packet-b-extra.private.json']
    target = REVIEW / 'paired-seal.json'
    assert not target.exists(), 'paired review already sealed'
    write_json(target, {'authority': 'independent offline Codex reviewers, not human verification',
                        'packet_seal_sha256': sha(REVIEW / 'packet-seal.json'),
                        'hashes': {p: sha(REVIEW / p) for p in paths}})
    print(json.dumps({'paired_sealed': True, 'sha256': sha(target)}))


def attribution_packet():
    assert (REVIEW / 'paired-seal.json').exists()
    units = {u['sample_id']: u for u in read(OUT / 'units.private.json')}
    write_json(REVIEW / 'attribution-packet.private.json', {
        'policy': 'Only after paired review sealed. Inspect stage1 predicted notes against source, then actual final feedback. No gold or R15. This is offline causal attribution, never inference or prompt revision.',
        'cases': [{'unit': units[r['sample_id']], 'stage1': r['stage1'], 'feedback': r['output']['feedback']}
                  for r in read(OUT / 'B/results.private.json')],
        'schema': {'cases': [{'sample_id': '...', 'notes_supported': True, 'follows_false_note': False,
                             'new_stage2_false_claim': False, 'self_corrected_bad_note': False,
                             'stage2_repair_leak': False, 'reason': 'source-grounded explanation',
                             'evidence': [{'source_quote': '...', 'note_quote': '...', 'feedback_quote': '...', 'reason': '...'}]}]}})


def score():
    from scripts.task3_two_pass import verify
    verify()
    seal = read(REVIEW / 'paired-seal.json')
    assert sha(REVIEW / 'packet-seal.json') == seal['packet_seal_sha256']
    for n, h in read(REVIEW / 'packet-seal.json').items():
        assert sha(REVIEW / n) == h, n
    verify_source_seal()
    for n, h in seal['hashes'].items():
        assert sha(REVIEW / n) == h, n
    extras = ['source-b-extra.private.json', 'paired-b-extra.private.json', 'extra-packet-seal.json', 'paired-packet-b-extra.private.json']
    for n in extras:
        assert (REVIEW / n).exists() == (n in seal['hashes']), 'unsealed extra artifact: ' + n
    assert len({n in seal['hashes'] for n in extras}) == 1, 'incomplete extra review'
    units = read(OUT / 'units.private.json')
    key = read(REVIEW / 'blind-key.private.json')
    candidate = {r['sample_id']: r for r in read(OUT / 'B/results.private.json')}
    control = {r['sample_id']: r for r in read(OUT / 'control.private.json')}
    ids = {u['sample_id'] for u in units}
    assert set(candidate) == set(control) == ids
    assert len(candidate) == len(read(OUT / 'B/results.private.json'))
    packet = read(REVIEW / 'paired-packet-a.private.json')
    assert {c['sample_id'] for c in packet['cases']} == ids
    assert len(key) == 2 * len(units)
    seen = set()
    byunit = {u['sample_id']: u for u in units}
    for c in packet['cases']:
        u = byunit[c['sample_id']]
        assert c['task'] == u['task'] and c['level'] == u['level']
        for o in c['outputs']:
            k = key[o['output_id']]
            assert k['sample_id'] == c['sample_id'] and k['arm'] in ['R15', 'two_pass']
            assert (k['sample_id'], k['arm']) not in seen
            seen.add((k['sample_id'], k['arm']))
            current = control[c['sample_id']]['output'] if k['arm'] == 'R15' else candidate[c['sample_id']]['output']
            assert current == o['output'], 'current output differs from reviewed packet'
    assert seen == {(sid, arm) for sid in ids for arm in ['R15', 'two_pass']}
    source = {'A': {r['sample_id']: r for r in read(REVIEW / 'source-a.private.json')['cases']},
              'B': {r['sample_id']: r for r in read(REVIEW / 'source-b.private.json')['cases']}}
    if (REVIEW / 'source-b-extra.private.json').exists():
        source['B'].update({r['sample_id']: r for r in read(REVIEW / 'source-b-extra.private.json')['cases']})
    assert set(source['A']) == ids and set(source['B']) <= ids
    reviews = {}
    for n, who in [('paired-a.private.json', 'A'), ('paired-b.private.json', 'B'), ('paired-b-extra.private.json', 'B')]:
        if not (REVIEW / n).exists():
            continue
        for c in read(REVIEW / n)['cases']:
            for o in c['outputs']:
                k = key[o['output_id']]
                assert k['sample_id'] == c['sample_id']
                reviews[(c['sample_id'], k['arm'], who)] = o
    # Gold is opened only here, after source and paired review seals.
    parent = ROOT / 'outputs/task3/eval-freeze-v2-20261021/frozen'
    dev = {r['sample_id']: r['annotation_v2'] for r in read(parent / 'train-eligible.private.json')}
    ev = {r['sample_id']: r['annotation_v2'] for r in read(parent / 'reference.private.json')['records']}
    selection = read(OUT / 'selection.private.json')
    gold = {r['sample_id']: (dev if r['old_split'] == 'development' else ev)[r['sample_id']] for r in selection['IDs']}
    rows = []
    good = ['finding_supported', 'main_covered', 'consistent', 'level_ok', 'natural']
    bad = ['false_claim', 'generic_only', 'disputed']
    for u in units:
        sid = u['sample_id']
        refs = [source[w][sid] for w in ['A', 'B'] if sid in source[w]]
        source_disputed = any(r['source_disputed'] for r in refs) or any(set(r['source_taxonomy']) != set(refs[0]['source_taxonomy']) for r in refs)
        row = {'sample_id': sid, 'level': u['level'], 'original_gold': gold[sid],
               'source_taxonomy_A': source['A'][sid]['source_taxonomy'],
               'source_taxonomy_B': source['B'].get(sid, {}).get('source_taxonomy'),
               'source_disputed': source_disputed, 'gold_disagreement': set(gold[sid]) != set(refs[0]['source_taxonomy']), 'arms': {}}
        for arm, output in [('R15', control[sid]['output']), ('two_pass', candidate[sid].get('output'))]:
            rs = [reviews[(sid, arm, w)] for w in ['A', 'B'] if (sid, arm, w) in reviews]
            r = {k: all(x[k] for x in rs) for k in good}
            r.update({k: any(x[k] for x in rs) for k in bad})
            r['l2_repair_leak'] = any(x['l2_repair_leak'] is True for x in rs) if u['level'] == 2 else None
            r['l2_repair_leak_confirmed'] = len(rs) >= 2 and all(x['l2_repair_leak'] is True for x in rs) if u['level'] == 2 else None
            actions = [x['l3_actionable'] for x in rs if x['l3_actionable'] is not None]
            r['l3_actionable'] = all(actions) if actions else None
            tax = output['taxonomy_error'] if output else None
            exact = tax is not None and all(set(tax) == set(ref['source_taxonomy']) for ref in refs)
            feedback_ok = all(r[k] for k in good) and not any(r[k] for k in bad)
            placeholder = bool(output and output['feedback'].strip().rstrip('.').casefold() in ['chương trình cần được kiểm tra lại', 'chương trình cần kiểm tra lại'])
            feedback_ok = feedback_ok and not placeholder
            r.update(completed=output is not None, taxonomy=tax, taxonomy_exact_original=tax is not None and set(tax) == set(gold[sid]),
                     taxonomy_exact_source=exact, source_disputed=source_disputed, feedback_pass=feedback_ok,
                     strict_joint=bool(output and exact and not source_disputed and feedback_ok),
                     reviewer_count=len(rs), instruction_placeholder_only=placeholder,
                     reviewer_disagreements=[k for k in good + bad + ['l2_repair_leak', 'l3_actionable'] if len({x[k] for x in rs}) > 1],
                     review_A_only_joint=bool(output and set(tax) == set(source['A'][sid]['source_taxonomy']) and not source['A'][sid]['source_disputed'] and all(rs[0][k] for k in good) and not any(rs[0][k] for k in bad)))
            row['arms'][arm] = r
        row['strict_joint_delta'] = int(row['arms']['two_pass']['strict_joint']) - int(row['arms']['R15']['strict_joint'])
        row['taxonomy_exact_delta_original'] = int(row['arms']['two_pass']['taxonomy_exact_original']) - int(row['arms']['R15']['taxonomy_exact_original'])
        rows.append(row)
    summary = {'IDs': len(units), 'data_role': 'prior-exposed synthetic development, not fresh or public evaluation', 'arms': {}}
    for arm in ['R15', 'two_pass']:
        rr = [r['arms'][arm] for r in rows]
        per_level = {}
        for level in [1, 2, 3]:
            subset = [r['arms'][arm] for r in rows if r['level'] == level]
            per_level[str(level)] = {'n': len(subset), **{k: sum(r[k] is True for r in subset) for k in good + bad + ['feedback_pass', 'strict_joint', 'l2_repair_leak', 'l2_repair_leak_confirmed', 'l3_actionable']},
                                     'actionable_eligible': sum(r['l3_actionable'] is not None for r in subset)}
        summary['arms'][arm] = {'completed': sum(r['completed'] for r in rr), 'unresolved': sum(not r['completed'] for r in rr), 'R15_fallback': 0,
                                'taxonomy_original': taxonomy_metrics([gold[u['sample_id']] for u in units], [r['taxonomy'] for r in rr]),
                                'taxonomy_source_A_sensitivity': taxonomy_metrics([source['A'][u['sample_id']]['source_taxonomy'] for u in units], [r['taxonomy'] for r in rr]),
                                **{k: sum(r[k] is True for r in rr) for k in good + bad + ['feedback_pass', 'strict_joint', 'review_A_only_joint']}, 'per_level': per_level}
    attempts = [json.loads(x) for x in (OUT / 'B/attempts.jsonl').read_text().splitlines()]
    expected = [(u['sample_id'], stage) for u in units for stage in ['taxonomy', 'feedback']]
    assert [(r['sample_id'], r['stage']) for r in attempts] == expected
    from src.task3 import two_pass as t
    definitions = read(OUT / 'frozen/level-definitions.json')
    reservations = [json.loads(x) for x in (OUT / 'B/reservations.jsonl').read_text().splitlines()]
    assert [(r['sample_id'], r['stage']) for r in reservations] == expected
    for a in attempts:
        u = byunit[a['sample_id']]
        r = candidate[a['sample_id']]
        if a['stage'] == 'taxonomy':
            assert t.parse_taxonomy(a['raw_text']) == r['stage1']
            assert a['messages'] == t.messages_taxonomy(u)
        else:
            assert t.parse_feedback(a['raw_text']) == r['output']['feedback']
            assert a['messages'] == t.messages_feedback(u, r['stage1'], definitions)
    assert all(candidate[u['sample_id']]['output']['taxonomy_error'] == candidate[u['sample_id']]['stage1']['taxonomy_error'] for u in units)
    def cost(trace):
        return {'calls': len(trace), **{k: sum(r[k] for r in trace) for k in ['input_tokens', 'output_tokens', 'latency_s']}}
    old = read(OUT / 'control-runtime.private.json')
    assert len(old) == len(units) and {r['sample_id'] for r in old} == ids
    summary['cost'] = {'R15_historical': cost(old), 'R15_fresh_calls': 0, 'two_pass': cost(attempts),
                       'stage1': cost([r for r in attempts if r['stage'] == 'taxonomy']),
                       'stage2': cost([r for r in attempts if r['stage'] == 'feedback']),
                       'comparison_limit': 'R15 historical cached run; timings not a contemporaneous controlled speed benchmark'}
    assert all(r['calls'] == 1 and not r['fallback_used'] for r in old)
    summary['run'] = read(OUT / 'run.private.json')
    summary['pairing'] = {'wins': sum(r['strict_joint_delta'] > 0 for r in rows), 'losses': sum(r['strict_joint_delta'] < 0 for r in rows), 'ties': sum(r['strict_joint_delta'] == 0 for r in rows),
                          'source_disputes': [r['sample_id'] for r in rows if r['source_disputed']],
                          'gold_disagreements': [r['sample_id'] for r in rows if r['gold_disagreement']]}
    attribution = read(REVIEW / 'attribution-a.private.json')
    attrs = {r['sample_id']: r for r in attribution['cases']}
    assert len(attrs) == len(units) and set(attrs) == {u['sample_id'] for u in units}
    for row in rows:
        a = attrs[row['sample_id']]
        u = next(u for u in units if u['sample_id'] == row['sample_id'])
        generated = candidate[row['sample_id']]
        source_text = '\n'.join(str(u['task'].get(k, '')) for k in ['statement', 'code', 'grading_policy'])
        notes = '\n'.join(i['note'] for i in generated['stage1']['issues'])
        for e in a['evidence']:
            assert e['source_quote'] in source_text
            assert e['note_quote'] in notes
            assert e['feedback_quote'] in generated['output']['feedback']
        for k in ['notes_supported', 'follows_false_note', 'new_stage2_false_claim', 'self_corrected_bad_note', 'stage2_repair_leak']:
            assert type(a[k]) is bool
        row['stage_attribution'] = {k: a[k] for k in ['notes_supported', 'follows_false_note', 'new_stage2_false_claim', 'self_corrected_bad_note', 'stage2_repair_leak']}
        row['stage1_taxonomy_issue_label_mismatch'] = set(candidate[row['sample_id']]['stage1']['taxonomy_error']) != {i['label'] for i in candidate[row['sample_id']]['stage1']['issues']}
    summary['stage_attribution_counts'] = {k: sum(r['stage_attribution'][k] for r in rows) for k in rows[0]['stage_attribution']}
    cfg = read(ROOT / 'configs/task3/two_pass_20261023.json')['development_continue_gate']
    a, b = [summary['arms'][arm] for arm in ['R15', 'two_pass']]
    rare = [x for x in LABEL_SPACE if x not in ['Lỗi logic', 'Lỗi biên dịch', 'Lỗi nhập/xuất']]
    checks = {'completion': b['completed'] >= cfg['minimum_completed'], 'strict_joint_gain': b['strict_joint'] >= a['strict_joint'] + cfg['minimum_strict_joint_gain'],
              'micro_f1': b['taxonomy_original']['micro_f1'] >= a['taxonomy_original']['micro_f1'] - cfg['maximum_micro_f1_drop'],
              'false_claims': b['false_claim'] <= a['false_claim'], 'no_confirmed_L2_repair_leak': b['per_level']['2']['l2_repair_leak_confirmed'] == 0,
              'rare_TP': all(b['taxonomy_original']['per_label'][x]['TP'] >= a['taxonomy_original']['per_label'][x]['TP'] for x in rare)}
    summary['continue_gate'] = {'passed': all(checks.values()), 'checks': checks, 'configuration': cfg}
    summary['decision'] = 'retain_R15_stop_after_development' if not all(checks.values()) else 'eligible_for_separate_internal_evaluation'
    summary['per_ID'] = rows
    summary['selection'] = {'policy': selection['policy'], 'train_style_reference_ids': selection['train_style_reference_ids'],
                             'IDs': [{**{k: r[k] for k in ['sample_id', 'old_split', 'source_sha256', 'exposure']}, 'requested_level': byunit[r['sample_id']]['level']} for r in selection['IDs']]}
    summary['provenance'] = {'initial_HEAD': read(OUT / 'frozen/freeze.json')['initial_head'], 'freeze_sha256': sha(OUT / 'frozen/freeze.json'),
                             'prompt_sha256': read(OUT / 'frozen/freeze.json')['prompt_sha256'], 'selection_seal_sha256': sha(OUT / 'selection-seal.json'),
                             'source_seal_sha256': sha(REVIEW / 'source-seal.json'), 'paired_seal_sha256': sha(REVIEW / 'paired-seal.json'),
                             'attribution_sha256': sha(REVIEW / 'attribution-a.private.json'), 'validator_sha256': sha(OUT / 'validator.log'),
                             'predictions_sha256': sha(OUT / 'B/predictions.json'),
                             'attempts_sha256': sha(OUT / 'B/attempts.jsonl'), 'reservations_sha256': sha(OUT / 'B/reservations.jsonl'),
                             'control_runtime_sha256': sha(OUT / 'control-runtime.private.json')}
    write_json(ROOT / 'reports/task3/TASK3_TWO_PASS_METRICS_20261023.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ['per_ID', 'arms', 'run']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['packets', 'extra-packet', 'seal', 'attribution-packet', 'score'])
    args = parser.parse_args()
    {'packets': packets, 'extra-packet': extra_packet, 'seal': seal_reviews, 'attribution-packet': attribution_packet, 'score': score}[args.phase]()
