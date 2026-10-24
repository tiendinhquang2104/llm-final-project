#!/usr/bin/env python3
"""Replay structural checks on a private audit ZIP; no model, no prediction edits."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.task3 import arm_d_plus as plus
from src.task3.grounded import strict_object


def audit_archive(path):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        units = json.loads(archive.read('units.private.json'))
        results = json.loads(archive.read('results.private.json'))
        calls = [json.loads(line) for line in archive.read('attempts.jsonl').decode('utf-8').splitlines()]
    by_id = {u['sample_id']: u for u in units}
    if len(by_id) != len(units):
        raise ValueError('duplicate input IDs')
    placeholders, quotes, rejected = set(), set(), set()
    placeholder_count = quote_count = total = empty_quotes = 0
    for row in results:
        findings = (row.get('stage1') or {}).get('findings', [])
        unit = by_id[row['sample_id']]
        sources = plus._evidence_sources(unit)
        for finding in findings:
            total += 1
            try:
                plus.parse_findings(json.dumps({'findings': [finding]}))
            except plus.StageFailure as exc:
                if 'placeholder' in str(exc):
                    placeholder_count += 1
                    placeholders.add(row['sample_id'])
            quote = finding['evidence'].replace('\r\n', '\n')
            if not quote.strip():
                empty_quotes += 1
            elif not any(quote in source for source in sources):
                quote_count += 1
                quotes.add(row['sample_id'])
        if row.get('stage1') is not None:
            try:
                plus.parse_findings(json.dumps({'findings': findings}), unit)
            except ValueError:
                rejected.add(row['sample_id'])
    invalid_json = identical_retries = 0
    previous = {}
    for call in calls:
        if call['stage'] == 'resolver':
            continue
        raw = call.get('raw_text')
        if raw is not None:
            try:
                strict_object(raw)
            except ValueError:
                invalid_json += 1
        key = (call['sample_id'], call['stage'])
        if call.get('attempt') and raw is not None and previous.get(key) == raw:
            identical_retries += 1
        previous[key] = raw
    level1 = [c for c in calls if c['stage'] == 'feedback' and by_id[c['sample_id']]['level'] == 1]
    return {
        'audit_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'checked_contract': plus.VERSION, 'new_inference_performed': False,
        'expected': len(units), 'recorded_resolved': sum(r['status'] == 'resolved' for r in results),
        'requested_levels': dict(Counter(u['level'] for u in units)), 'recorded_findings': total,
        'placeholder_findings': placeholder_count, 'placeholder_samples': len(placeholders),
        'nonverbatim_findings': quote_count, 'nonverbatim_samples': len(quotes),
        'empty_quote_findings': empty_quotes,
        'samples_rejected_by_current_contract': len(rejected),
        'invalid_json_responses': invalid_json, 'identical_retry_responses': identical_retries,
        'level1_renderer_calls_in_recording': len(level1),
        'level1_renderer_input_tokens_in_recording': sum(c['input_tokens'] for c in level1),
        'level1_renderer_output_tokens_in_recording': sum(c.get('output_tokens') or 0 for c in level1),
        'interpretation': 'Historical structural audit only. A nonverbatim quote is not proof of a false diagnosis. '
                          'Rejection counts are not predictions of new-model completion or accuracy.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit_zip', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_archive(args.audit_zip), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
