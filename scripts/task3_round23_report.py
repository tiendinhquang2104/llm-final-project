#!/usr/bin/env python3
"""Recompute Round23 paired metrics from all sealed post-inference ID evidence."""
from pathlib import Path
import json
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.feedback_prompt import verify_seal,sha
from src.task3.dataset import write_json
from src.task3.round23_metrics import aggregate
ROOT=REPO/'outputs/task3/round23-20261022'


def main():
    verify_seal(ROOT/'pre-inference-freeze.json');verify_seal(ROOT/'post-inference-review-freeze.json')
    rows=json.loads((ROOT/'id-metrics.private.json').read_text());selection={r['sample_id']:r for r in json.loads((ROOT/'frozen-selection.private.json').read_text())}
    for row in rows:
        r=selection[row['sample_id']]
        if any(row[k]!=r[k]for k in ['pair_id','role','family','split','source_sha256']):raise ValueError('row differs from frozen selection')
    cfg=json.loads((ROOT/'resolved-config.json').read_text());result=aggregate(rows,cfg['candidate']['gate'])
    calls={}
    for name,path,stage in [('R15',ROOT/'R15/attempts.jsonl',None),('shared_self',ROOT/'diagnosis-attempts.jsonl','shared_prediction'),('execution_marginal',ROOT/'diagnosis-attempts.jsonl','execution_continuation')]:
        values=[json.loads(l)for l in path.read_text().splitlines()]
        if stage:values=[r for r in values if r['stage']==stage]
        attempted=[r for r in values if r.get('generation_attempted',True)]
        calls[name]={'calls':len(attempted),'journal_rows':len(values),'preflight_failures':len(values)-len(attempted),'output_tokens':sum(r.get('output_tokens',0)for r in attempted),'latency_s':sum(r.get('latency_s',0)for r in attempted),'runtime_errors':sum(bool(r.get('runtime_error'))for r in attempted)}
    result.update(calls=calls,freeze_sha256=sha(ROOT/'pre-inference-freeze.json'),review_sha256=sha(ROOT/'post-inference-review-freeze.json'),R22_audit=json.loads((ROOT/'r22-offline-summary.json').read_text()),renderer_run=False)
    write_json(ROOT/'metrics.json',result);write_json(REPO/'reports/task3/TASK3_ROUND23_RESULTS_20261022.json',result)
    print(json.dumps({'evaluation':result['splits']['evaluation'],'gates':result['gates'],'calls':calls},ensure_ascii=False));return 0

if __name__=='__main__':raise SystemExit(main())
