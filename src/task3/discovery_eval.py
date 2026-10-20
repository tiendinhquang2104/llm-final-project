"""Train-only evaluation helpers; labels stay outside DiscoveryInput."""
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter
from src.synth.taxonomy import LABEL_SPACE
from src.task3.schema import code_hash
from src.task3.discovery import DiscoveryInput


def assert_isolated(development, check):
    for key in ('exam','group'):
        if {getattr(c,key) for c in development}&{getattr(c,key) for c in check}:
            raise ValueError('development/check problem or group overlap')
    for renamed in (False,True):
        if {code_hash(c.code,renamed=renamed) for c in development}&{code_hash(c.code,renamed=renamed) for c in check}:
            raise ValueError('development/check canonical code overlap')


def load_train_rows(root,split):
    if split not in {'real-train','synthetic-train'}:raise ValueError('train-only runner')
    rows=[json.loads(line)['record'] for line in (Path(root)/f'{split}.jsonl').read_text().splitlines() if line.strip()]
    if any(row['split']!=split or row['source'] not in {'real','synthetic'} for row in rows):
        raise ValueError('record split/source mismatch')
    return rows


def inference_input(row,compiler):
    # Explicit allowlist: not dataclass expansion or arbitrary record provenance.
    return DiscoveryInput(code=row['code'],statement=row['statement'],
        problems=tuple({k:p[k] for k in ('pid','prototype') if k in p} for p in row.get('problems',[])),
        compiler_status=compiler['status'],compiler_diagnostic=compiler['diagnostic'])


def score_findings(expected,predicted):
    """Group+overlapping span matching on manually annotated artificial cases.

    This is not a general semantic verifier. Correctness of the annotation and
    expected mechanism needs independent inspection; taxonomy agreement alone
    is explicitly insufficient, and no finding metric is assigned to real data.
    """
    matched=set();by_group={g:{'tp':0,'fp':0,'fn':0} for g in LABEL_SPACE}
    for p in predicted:
        ps=p['source_span'];group=p['taxonomy_group']
        index=next((i for i,e in enumerate(expected) if i not in matched and e['taxonomy_group']==group and max(ps['start'],e['source_span']['start'])<min(ps['end'],e['source_span']['end'])),None)
        if index is None:by_group[group]['fp']+=1
        else:matched.add(index);by_group[group]['tp']+=1
    for i,e in enumerate(expected):
        if i not in matched:by_group[e['taxonomy_group']]['fn']+=1
    return {'metric_kind':'taxonomy_and_span_agreement_not_semantic_correctness', 'tp':sum(x['tp'] for x in by_group.values()),'fp':sum(x['fp'] for x in by_group.values()),
            'fn':sum(x['fn'] for x in by_group.values()),'by_group':by_group,
            'label_exact':{e['taxonomy_group'] for e in expected}=={p['taxonomy_group'] for p in predicted}}


def label_metrics(rows):
    groups={}
    for group in LABEL_SPACE:
        tp=sum(group in r['predicted'] and group in r['expected'] for r in rows)
        fp=sum(group in r['predicted'] and group not in r['expected'] for r in rows)
        fn=sum(group not in r['predicted'] and group in r['expected'] for r in rows)
        groups[group]={'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None}
    return {'records':len(rows),'per_group':groups,'label_set_exact_observed':sum(set(r['predicted'])==set(r['expected']) for r in rows),
            'note':'unknown treated as no predicted positives for recall bookkeeping only, never exported as []'}
