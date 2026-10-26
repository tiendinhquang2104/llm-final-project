#!/usr/bin/env python3
"""Verify frozen context32768 public artifacts offline, without model/GPU/compiler calls.

Run after export. --write-report creates final-integrity.json only once, or accepts
an existing byte-value-equivalent report; it never overwrites a prior report.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
DEFAULT_OUT = REPO / 'outputs/task3/sft-v2-public-context32768-20261026-run1'

from src.task3.sft_v1 import read_jsonl
from src.task3.sft_v1_runtime import digest
from src.task3.sft_v1_evaluation import parse_response
from src.task3.sft_v2_runtime import verify_model_files
from src.task3.sft_v2_public_context_runtime import (
    CONTEXT, METHOD, PUBLIC, OLD, load, verify, recover, normalized,
)
from src.task3.public_contract import verify_public_contract
from src.task3.submission import validate_submission


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timestamp must have timezone')
    return result


def amount(values):
    known = [v for v in values if type(v) in (int, float) and math.isfinite(v) and v >= 0]
    return dict(known_sum=sum(known), known_count=len(known), unknown_count=len(values)-len(known),
                total=sum(known) if len(known) == len(values) else None)


class Checks:
    def __init__(self):
        self.rows = []

    def require(self, name, condition, details=None):
        self.rows.append(dict(name=name, passed=bool(condition), details=details))
        return bool(condition)

    def call(self, name, function):
        try:
            value = function()
        except Exception as exc:
            self.rows.append(dict(name=name, passed=False, error=f'{type(exc).__name__}: {exc}'))
            return None
        self.rows.append(dict(name=name, passed=True))
        return value


def build_report(out):
    out = Path(out).resolve()
    if not out.is_relative_to(REPO / 'outputs/task3'):
        raise ValueError('run must be inside this worktree outputs/task3')
    marker_path = out / 'generation-complete.json'
    validation_path = out / 'submission/validation.json'
    candidates = [out / 'submission/predictions.json', out / 'submission/partial.predictions.json']
    if not marker_path.is_file() or not validation_path.is_file() or not any(p.is_file() for p in candidates):
        raise FileNotFoundError('final verification requires generation-complete.json and exported complete/partial submission with validation.json')
    checks = Checks()
    frozen = checks.call('frozen_code_inputs_selection_and_all_historical_hashes', lambda: verify(REPO, out))
    if frozen is None:
        return dict(version='task3-context32768-offline-integrity-v1', complete_export=False,
                    all_checks_passed=False, checks=checks.rows,
                    failed_checks=[r['name'] for r in checks.rows if not r['passed']],
                    verifier_sha256=sha(__file__), run=str(out))
    freeze, manifest, preservation = frozen
    freeze_hash = sha(out / 'freeze.json')
    contract = checks.call('authoritative_public_contract_archive_and_requested_levels', lambda: verify_public_contract(PUBLIC))
    if contract is None:
        requested = load(out / 'requested-levels.private.json')
        labels = load(out / 'official-contract.json')['taxonomy_labels']
    else:
        requested = contract['requested_levels']
        labels = contract['taxonomy_labels']
    official_ids = list(requested)
    requested_counts = dict(Counter(int(level[6]) for level in requested.values()))
    checks.require('official328_and_level115_163_50_0', len(requested) == 328 and
                   {level: requested_counts.get(level, 0) for level in (1, 2, 3, 4)} == {1:115, 2:163, 3:50, 4:0})
    checks.require('freeze_and_saved_requested_order_are_authoritative',
                   freeze['ordered_requested_ids'] == official_ids and load(out / 'requested-levels.private.json') == requested)
    checks.call('actual_seven_pinned_model_file_hashes', lambda: verify_model_files(manifest))
    snapshot = Path(manifest['config']['tokenizer_local'])
    config = load(snapshot / 'config.json')
    tokenizer_config = load(snapshot / 'tokenizer_config.json')
    checks.require('context32768_model_tokenizer_and_unscaled_original_rope',
                   CONTEXT == freeze['context_limit'] == freeze['config']['context_limit'] == config['max_position_embeddings'] == 32768
                   and tokenizer_config['model_max_length'] >= 32768 and config['rope_theta'] == 1000000.0
                   and config.get('rope_scaling') is None and not config.get('use_sliding_window'))
    checks.require('pinned_model_revision_and_selected240_unchanged',
                   freeze['config']['model_id'] == manifest['config']['model_id'] == 'Qwen/Qwen2.5-Coder-7B-Instruct'
                   and freeze['config']['revision'] == manifest['config']['revision'] == 'c03e6d358207e414f1eca0bb1891e29f1db0e242'
                   and load(REPO / 'outputs/task3/sft-v2-qlora-20261026-run1/selection.json')['step'] == 240)
    old_freeze = load(REPO / OLD / 'public-freeze.json')
    checks.require('generation_settings_and_prompt_files_unchanged_from8192',
                   freeze['generation'] == old_freeze['generation']
                   and (out / 'examples.private.jsonl').read_bytes() == (REPO / OLD / 'examples.private.jsonl').read_bytes()
                   and (out / 'public-inputs.private.jsonl').read_bytes() == (REPO / OLD / 'public-inputs.private.jsonl').read_bytes())
    checks.require('new_method_and_exact328_call_ceiling',
                   freeze['method'] == METHOD == 'task3-sft-v2-step240-native-public-context32768-v1'
                   and freeze['maximum_physical_calls'] == 328 and freeze['one_attempt'] is True)
    preflight = load(out / 'context-preflight.json')
    examples = read_jsonl(out / 'examples.private.jsonl')
    equivalents = load(out / 'prompt-equivalence.json')
    pf = {r['sample_id']: r for r in preflight}
    ex = {r['sample_id']: r for r in examples}
    checks.require('preflight_examples_equivalence_exact_authoritative_coverage',
                   len(preflight) == len(pf) == len(examples) == len(ex) == len(equivalents) == 328
                   and [r['sample_id'] for r in examples] == official_ids
                   and [r['sample_id'] for r in preflight] == official_ids
                   and [r['sample_id'] for r in equivalents] == official_ids)
    bad_preflight = []
    for sid in official_ids:
        p, e = pf.get(sid, {}), ex.get(sid, {})
        level = int(requested[sid][6])
        if (p.get('status') != 'evaluable' or p.get('level') != level or e.get('level') != level
                or p.get('context_limit') != 32768 or p.get('allowance') != freeze['generation']['max_new_tokens'][str(level)]
                or p.get('total_tokens') != p.get('prompt_tokens', -1) + p.get('allowance', -1)
                or p.get('total_tokens', 999999) > 32768 or p.get('prompt_sha256') != digest(e.get('prompt'))):
            bad_preflight.append(sid)
    checks.require('all328_full_prompt_budget_level_and_hash_bindings', not bad_preflight, bad_preflight)
    checks.require('all328_frozen_prompt_byte_and_token_equivalence', all(
        r.get('identical_prompt_bytes') is True and r.get('identical_token_ids') is True
        and r.get('prompt_sha256') == pf.get(r['sample_id'], {}).get('prompt_sha256')
        and r.get('tokens') == pf.get(r['sample_id'], {}).get('prompt_tokens') for r in equivalents))
    recovered = checks.call('strict_bound_journal_recovery_method_prompt_and_freeze', lambda: recover(out, freeze))
    if recovered is None:
        events, results, journal_rows = [], {}, []
    else:
        recovered_examples, journal, results = recovered
        events = journal.events()
        journal_rows = normalized(out, recovered_examples, results)
    saved_rows = read_jsonl(out / 'generations.jsonl')
    checks.require('normalized_output_equals_durable_journal_reconstruction', saved_rows == journal_rows)
    checks.require('normalized_order_exact_authoritative', [r['sample_id'] for r in saved_rows] == official_ids)
    reservations = [e for e in events if e.get('type') == 'generation_reserved']
    completions = [e for e in events if e.get('type') == 'generation_completed']
    reservation_ids = [e['key'] for e in reservations]
    completion_ids = [e['key'] for e in completions]
    uncertain = sorted(set(reservation_ids) - set(completion_ids))
    allocation = [e for e in events if e.get('type') == 'public_input_allocation_failed']
    uncalled = [sid for sid in official_ids if sid not in set(reservation_ids)]
    checks.require('physical_reservations_unique_at_most328',
                   len(reservation_ids) == len(set(reservation_ids)) <= 328 and set(reservation_ids) <= set(official_ids))
    checks.require('completed_calls_unique_reserved_and_at_most328',
                   len(completion_ids) == len(set(completion_ids)) <= 328 and set(completion_ids) <= set(reservation_ids))
    checks.require('all328_fresh_primary_calls_completed', len(reservations) == len(completions) == 328
                   and not uncertain and not uncalled, dict(reserved=len(reservations), completed=len(completions),
                                                         uncertain_ids=uncertain, uncalled_ids=uncalled))
    longest = max(preflight, key=lambda p: p['prompt_tokens'])['sample_id']
    scheduled = load(out / 'generation-order.json')
    expected_schedule = [longest] + [sid for sid in official_ids if sid != longest]
    checks.require('longest_first_primary_retained_and_frozen_schedule_followed',
                   scheduled['ids'] == freeze['generation_order'] == expected_schedule
                   and scheduled['first_primary'] == longest
                   and reservation_ids == expected_schedule[:len(reservation_ids)]
                   and (not completion_ids or completion_ids[0] == longest))
    time_failures = []
    frozen_time = utc(freeze['created_utc'])
    previous_time = None
    for i, event in enumerate(events):
        try:
            stamp = utc(event['utc'])
            if stamp < frozen_time or (previous_time is not None and stamp < previous_time):
                time_failures.append(i)
            previous_time = stamp
        except (KeyError, TypeError, ValueError):
            time_failures.append(i)
    checks.require('all_journal_events_after_freeze_and_chronological', not time_failures, time_failures)
    bad_rows, valid_ids, payloads = [], [], {}
    for row in saved_rows:
        sid = row['sample_id']; p = pf.get(sid, {})
        binding = (row.get('level') == int(requested.get(sid, 'Level 0')[6])
                   and row.get('example_id') == sid and row.get('prompt_sha256') == p.get('prompt_sha256')
                   and row.get('method') == METHOD and row.get('runtime_identity_sha256') == freeze_hash)
        if sid in set(completion_ids):
            binding = binding and row.get('input_tokens') == p.get('prompt_tokens')
        parsed = parse_response(row.get('raw'), labels, row.get('finish_reason', 'missing'))
        if parsed['status'] != row.get('status') or parsed.get('parsed') != row.get('parsed') or not binding:
            bad_rows.append(sid)
        if parsed['status'] == 'valid':
            valid_ids.append(sid); payloads[sid] = parsed['parsed']
    checks.require('every_result_level_tokens_identity_and_raw_reparse', not bad_rows, bad_rows)
    marker = load(marker_path)
    marker_fields = dict(expected=328, normalized=len(saved_rows), physical_reservations=len(reservations),
                         status_counts=dict(Counter(r.get('status') for r in saved_rows)),
                         journal_sha256=sha(out / 'generation-journal.jsonl'))
    checks.require('generation_complete_marker_matches_actual_evidence', all(marker.get(k) == v for k, v in marker_fields.items()), marker_fields)
    runtime_events = [e for e in events if e.get('type') == 'public_model_and_adapter_load_completed']
    checks.require('actual_loaded_runtime32768_sdpa_unscaled_cache_and_device', bool(runtime_events) and all(
        e.get('model_max_position_embeddings') == 32768 and e.get('rope_theta') == 1000000.0
        and e.get('rope_scaling') is None and e.get('attention') == 'sdpa'
        and e.get('effective_generation_use_cache') is True and e.get('device') == 'cuda:0'
        and e.get('adapter') == freeze['adapter_files'] for e in runtime_events))
    validation = load(validation_path)
    complete = validation.get('complete_export') is True
    candidate = out / 'submission' / ('predictions.json' if complete else 'partial.predictions.json')
    actual = load(candidate)
    checks.require('export_file_is_complete_or_explicitly_partial',
                   len([p for p in candidates if p.exists()]) == 1
                   and complete == (len(valid_ids) == 328)
                   and (complete or (out / 'submission/unresolved.json').is_file()))
    eligible = requested if complete else {sid:requested[sid] for sid in valid_ids}
    official_validation = checks.call('official_validator_on_actual_saved_candidate_bytes',
        lambda: validate_submission(candidate, eligible)) if eligible else None
    if not eligible:
        checks.require('empty_partial_is_actual_empty_json_array', actual == [])
    expected_candidate = [dict(sample_id=sid, output=payloads[sid]) for sid in official_ids if sid in payloads]
    checks.require('candidate_exactly_original_raw_payloads_in_authoritative_order', actual == expected_candidate)
    checks.require('validation_sidecar_matches_actual_bytes_and_denominators',
                   validation.get('expected') == 328 and validation.get('valid') == len(actual)
                   and validation.get('unresolved') == 328-len(actual)
                   and validation.get('sha256') == sha(candidate)
                   and validation.get('saved_bytes_validated') is True)
    if not complete:
        unresolved_rows = load(out / 'submission/unresolved.json')
        checks.require('partial_export_lists_every_unresolved_id_once',
                       [r['sample_id'] for r in unresolved_rows] == [sid for sid in official_ids if sid not in payloads])
    copy_path = REPO / 'submission-candidates/sft-v2-context32768/predictions.json'
    if complete:
        checks.require('convenient_copy_exists_and_is_byte_identical',
                       copy_path.is_file() and copy_path.read_bytes() == candidate.read_bytes())
        copy_sidecar = checks.call('convenient_copy_sidecar_readable', lambda: load(out / 'convenient-copy.json'))
        if copy_sidecar is not None:
            checks.require('convenient_copy_sidecar_matches_actual_hash_size_and_path',
                           copy_sidecar.get('path') == str(copy_path) and copy_sidecar.get('sha256') == sha(copy_path)
                           and copy_sidecar.get('bytes') == copy_path.stat().st_size and copy_sidecar.get('byte_identical') is True)
    completed_results = [e['result'] for e in completions]
    phases = [e for e in events if e.get('type') in ('public_generation_phase_completed', 'public_generation_phase_aborted')]
    costs = dict(attempted_physical_reservations=len(reservations), completed_calls=len(completions),
        valid_outputs=len(valid_ids), uncertain_call_ids=uncertain, uncalled_ids=uncalled,
        unreserved_allocation_failures=len(allocation),
        input_tokens=amount([r.get('input_tokens') for r in completed_results] + [None]*len(uncertain)),
        output_tokens=amount([None if r.get('output_cost_unknown') or (r.get('status')=='generation_error' and r.get('output_tokens')==0)
                              else r.get('output_tokens') for r in completed_results] + [None]*len(uncertain)),
        per_call_wall_s=amount([r.get('wall_s') for r in completed_results] + [None]*len(uncertain)),
        combined_load_wall_s=amount([e.get('wall_s') for e in runtime_events]),
        generation_phase_wall_s=amount([e.get('wall_s') for e in phases]),
        phase_evidence=phases, measurement_scope='Recorded CUDA allocated/reserved peaks over whole generation phase after load; no CUDA query by verifier.')
    artifacts = ['freeze.json','generation-order.json','context-preflight.json','prompt-equivalence.json',
                 'generation-journal.jsonl','generations.jsonl','generation-complete.json','submission/validation.json',
                 str(candidate.relative_to(out))]
    optional = {}
    for name in ['analysis.json','costs.json']:
        path = out / name
        if path.exists():
            optional[name] = dict(sha256=sha(path), top_level_keys=list(load(path)))
            artifacts.append(name)
    report = dict(version='task3-context32768-offline-integrity-v1', run=str(out), method=METHOD,
        freeze_sha256=freeze_hash, complete_export=complete, expected=328, valid_outputs=len(valid_ids),
        candidate=dict(path=str(candidate), sha256=sha(candidate), bytes=candidate.stat().st_size,
                       official_validation=official_validation),
        convenient_copy=dict(path=str(copy_path), sha256=sha(copy_path), bytes=copy_path.stat().st_size) if complete and copy_path.is_file() else None,
        all_checks_passed=all(r['passed'] for r in checks.rows), checks=checks.rows,
        failed_checks=[r['name'] for r in checks.rows if not r['passed']], preservation=preservation,
        costs=costs, optional_analysis_evidence=optional,
        input_sha256={n:sha(out/n) for n in artifacts}, verifier_sha256=sha(__file__),
        no_model_gpu_or_compiler_calls=True, exported_locally=True, submitted=False,
        limitation='Artifact integrity and official structure do not establish semantic diagnosis correctness or a public accuracy/F1 score.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--write-report', action='store_true')
    args = parser.parse_args()
    report = build_report(args.out)
    if args.write_report:
        destination = args.out.resolve() / 'final-integrity.json'
        if destination.exists():
            if load(destination) != report:
                raise FileExistsError('final-integrity.json exists with different verification evidence; never overwrite')
        else:
            raw = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
            with destination.open('x', encoding='utf-8') as stream:
                stream.write(raw)
    print(json.dumps(dict(all_checks_passed=report['all_checks_passed'], expected=report.get('expected'),
        valid_outputs=report.get('valid_outputs'), complete_export=report['complete_export'],
        failed_checks=report['failed_checks'], candidate=report.get('candidate'),
        report=str(args.out.resolve()/'final-integrity.json') if args.write_report else None), ensure_ascii=False))
    return 0 if report['all_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
