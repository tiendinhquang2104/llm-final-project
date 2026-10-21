#!/usr/bin/env python3
"""Offline three-arm development comparison. Never generates model outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.task3_direct_sft_report import feedback_summary, generation_summary, rate
from src.task3.frozen_eval import evaluate, output_digest


def verify_reused_outputs(expected, actual):
    if set(expected) != {'BASE', 'V1'} or expected != actual:
        raise ValueError('reused BASE/v1 output binding changed')


def production_decision(base, v1, v2):
    """Apply the pre-optimizer conjunctive rule; unknown flags fail closed."""
    def known(arm):
        return (arm.get('semantic_pending') == 0 and arm.get('reviewed') == 60
                and all(not arm.get(key, {}).get('pending', 0)
                        for key in ('l2_useful', 'l2_strict', 'l3_useful')))

    def improves(key):
        values = [rate(arm[key]) for arm in (base, v1, v2)]
        return all(x is not None for x in values) and values[2] > max(values[:2])

    floors = {ref: {metric: base['taxonomy'][ref][metric] +
                   .9 * max(0., v1['taxonomy'][ref][metric] - base['taxonomy'][ref][metric])
                   for metric in ('micro', 'macro')} for ref in ('annotation', 'source')}
    checks = dict(
        complete=all(arm.get('completed') == 60 for arm in (base, v1, v2)),
        semantic_complete=all(known(arm) for arm in (base, v1, v2)),
        taxonomy_retained=all(v2['taxonomy'][ref][metric] + 1e-12 >= floors[ref][metric]
                              for ref in floors for metric in floors[ref]),
        l2_location_cause=improves('l2_useful'),
        l2_strict=improves('l2_strict'),
        l3_cause_feasible_repair=improves('l3_useful') and v2['l3_useful']['numerator'] >= 2,
        false_claim=v2['false_claim'] <= v1['false_claim'] and v2['false_claim'] < base['false_claim'],
        l1_false_clean=v2['l1_false_clean'] <= v1['l1_false_clean'],
    )
    eligible = all(checks.values())
    return dict(eligible=eligible, checks=checks, taxonomy_floors=floors,
                public_generation_authorized=False,
                action=('eligible for reviewed production change; no public generation in this task'
                        if eligible else 'keep R15; stop further training; no public generation'))


def decision_input(report):
    feedback = report['feedback']
    tax = report['metrics']['primary']
    return dict(semantic_pending=feedback['semantic_pending'], completed=feedback['completed'],
                reviewed=feedback['reviewed'],
                taxonomy={ref: dict(micro=tax[key]['micro']['f1'], macro=tax[key]['macro']['f1'])
                          for ref, key in [('annotation', 'annotation_v2'), ('source', 'source_reference')]},
                false_claim=feedback['false_claim']['numerator'],
                l1_false_clean=feedback['l1_false_clean']['numerator'],
                l2_useful=feedback['l2_useful'], l2_strict=feedback['l2_strict'],
                l3_useful=feedback['l3_useful'])


def run():
    from scripts.task3_direct_sft_v2_prepare import verify_pilot, WORK, FROZEN, read, sha, write_new
    manifest, config, *_ = verify_pilot()
    previous = REPO/'outputs/task3/direct-sft-v1-20261021'
    folders = {'BASE': previous/'inference/arm-BASE', 'V1': previous/'inference/arm-SFT',
               'V2': WORK/'inference/arm-V2'}
    predictions = {}
    for arm, folder in folders.items():
        state = read(folder/'status.json')
        if state.get('complete') is not True or state.get('processed') != 60:
            raise ValueError('all sixty requests in all arms must finish before retrospective scoring')
        predictions[arm] = read(folder/'predictions.json')
        if len(predictions[arm]) != 60:
            raise ValueError('development prediction count changed')
    expected = manifest['reused_outputs_sha256']
    actual = {arm: {name: sha(folders[arm]/name) for name in hashes}
              for arm, hashes in expected.items()}
    verify_reused_outputs(expected, actual)
    # This source reference is used only for retrospective scoring, after v2 is complete.
    root = REPO/'outputs/task3/eval-freeze-v2-20261021/frozen'
    public = read(REPO/'reports/task3/TASK3_EVAL_V2_FREEZE_20261021.json')
    if sha(root/'reference.private.json') != public['private_files_sha256']['reference.private.json']:
        raise ValueError('sealed development reference changed')
    refs = read(root/'reference.private.json')
    inputs = read(FROZEN/'development-inputs.private.json')
    snapshot = dict(records=refs['records'], requests=[dict(request_id=r['request_id'],
                    sample_id=r['sample_id'], level=r['requested_level'], kind='primary') for r in inputs])
    reports = {}
    for arm, preds in predictions.items():
        ledger_path = WORK/'review'/f'ledger-{arm}.private.json'
        ledger = read(ledger_path)
        metrics = evaluate(snapshot, preds, ledger)
        reports[arm] = dict(metrics=metrics, feedback=feedback_summary(snapshot, preds, ledger),
                            generation=generation_summary(folders[arm], preds),
                            predictions_sha256=sha(folders[arm]/'predictions.json'),
                            ledger_sha256=sha(ledger_path),
                            reused=arm != 'V2', final_sha256={p['request_id']:
                            output_digest(p['output']) if p['status'] == 'completed' else None for p in preds})
    decisions = {arm: decision_input(report) for arm, report in reports.items()}
    result = dict(version='direct-sft-v2-20261021',
                  reference_sha256=sha(root/'reference.private.json'), reports=reports,
                  decision_inputs=decisions,
                  decision=production_decision(decisions['BASE'], decisions['V1'], decisions['V2']),
                  comparison_status='development with prior source/family/output exposure; not blind',
                  review='agent static source-grounded; not human verified; unknown remains null')
    write_new(WORK/'three-arm-results.private.json', result)
    print(json.dumps(dict(decision=result['decision'], summaries=decisions), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--score', action='store_true')
    args = parser.parse_args()
    if not args.score:
        parser.error('--score required')
    run()
