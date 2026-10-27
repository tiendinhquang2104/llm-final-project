"""Pure crossover summaries and exact source/Level paired comparisons.

No model calls or semantic guessing. Unknown semantic verdicts remain uncertain;
invalid outputs remain in every primary denominator.
"""
from collections import Counter
import json
from src.task3.sft_v3 import summarize as v3_summary, joint_success
from src.task3.sft_v1_evaluation import aggregate_metrics
from src.task3.prompt_crossover import AXES
VERDICTS = ('pass', 'fail', 'uncertain', 'not_applicable', 'not_evaluable')
ASSESSMENT = ('diagnosis_supported', 'coverage', 'factual_fidelity')


def _valid(row):
    return row['status'] == 'valid'


def _labels(row):
    return sorted(set(row['parsed']['taxonomy_error'])) if _valid(row) else None


def _compatible(row):
    axes = dict(row['axes'])
    axes['level_compliance'] = axes.get('disclosure_compliance')
    return dict(row, axes=axes)


def successful_feedback(row):
    """v3 joint gates plus required content; false praise cannot succeed."""
    if not _valid(row) or row['axes'].get('required_content') != 'pass':
        return False
    if bool(_labels(row)) != row['faulty']:
        return False
    return joint_success(row['status'], row['level'], row['faulty'],
                         _compatible(row)['axes'], row.get('code_verdict', 'absent'))


def summarize(rows):
    rows = list(rows)
    result = v3_summary([_compatible(r) for r in rows])
    clean = [r for r in rows if not r['faulty']]
    faulty = [r for r in rows if r['faulty']]
    result.update(valid=result['targets'] - result['invalid'],
        clean_sources=len({r['sample_id'] for r in clean}),
        faulty_sources=len({r['sample_id'] for r in faulty}),
        disclosure_compliant=sum(_valid(r) and r['axes'].get('disclosure_compliance') == 'pass' for r in rows),
        required_content_met=sum(_valid(r) and r['axes'].get('required_content') == 'pass' for r in rows),
        official_level_complete=sum(_valid(r) and all(r['axes'].get(k) == 'pass' for k in
            ('disclosure_compliance', 'required_content')) for r in rows),
        successful_feedback=sum(successful_feedback(r) for r in rows),
        clean_successful=sum(successful_feedback(r) for r in clean),
        faulty_successful=sum(successful_feedback(r) for r in faulty),
        axes={k:{v:sum(r['axes'].get(k, 'not_evaluable') == v for r in rows) for v in VERDICTS} for k in AXES},
        code_verdicts=dict(Counter(r.get('code_verdict', 'absent') for r in rows)),
        status_counts=dict(Counter(r['status'] for r in rows)))
    result['faulty_missed_defect_rate_with_invalid'] = result['faulty_misses_with_invalid']/len(faulty) if faulty else None
    result['balanced_success'] = ((result['clean_successful']/len(clean) + result['faulty_successful']/len(faulty))/2
        if clean and faulty else result['successful_feedback']/len(rows) if rows else 0.)
    # Keep old count names compatible, while applying the complete current gates.
    result.update(joint_successful=result['successful_feedback'], clean_joint=result['clean_successful'],
                  faulty_joint=result['faulty_successful'], balanced_joint=result['balanced_success'])
    examples = [dict(example_id=r['example_id'],sample_id=r['sample_id'],level=r['level'],
        completion=json.dumps(dict(taxonomy_error=r['gold_taxonomy'], feedback='private reference'))) for r in rows]
    result['taxonomy_auxiliary'] = aggregate_metrics(examples, rows)
    result['taxonomy_auxiliary'].pop('feedback_quality', None)
    for level in result['taxonomy_auxiliary']['by_level'].values():
        level.pop('feedback_quality', None)
    return result


def _conjunction(values):
    # An unknown essential axis cannot silently become a definite loss.
    if any(v not in ('pass', 'fail') for v in values):
        return None
    return all(v == 'pass' for v in values)


def semantic_value(row, metric):
    if not _valid(row):
        return None
    axes = row['axes']
    if metric == 'assessment':
        return _conjunction([axes.get(k) for k in ASSESSMENT])
    if metric == 'l3_repair_direction' and (row['level'] != 3 or not row['faulty']):
        return 'not_applicable'
    if metric != 'successful_feedback':
        return _conjunction([axes.get(metric)])
    needed = list(ASSESSMENT) + ['disclosure_compliance', 'required_content', 'vietnamese_compliance']
    if row['faulty'] and row['level'] > 1:
        needed.append('location_and_condition')
    if row['faulty'] and row['level'] == 3:
        needed.append('l3_repair_direction')
    if row['level'] == 4:
        needed.append('l4_usefulness')
    if _conjunction([axes.get(k) for k in needed]) is None or row.get('code_verdict','absent') not in ('pass','absent','fail'):
        return None
    return successful_feedback(row)


def _outcome(a, b):
    if a is None or b is None:
        return 'uncertain'
    if a == b:
        return 'tie'
    if 'not_applicable' in (a, b):
        return 'uncertain'
    return 'win' if b else 'loss'


SEMANTIC = ('assessment','disclosure_compliance','required_content','l3_repair_direction','successful_feedback')


def _index(rows):
    result = {}
    bindings = set()
    for row in rows:
        eid = row['example_id']; binding = (row['sample_id'],row['level'])
        if eid in result or binding in bindings:
            raise ValueError('duplicate target/source-Level: ' + eid)
        if type(row['level']) is not int or row['level'] not in (1,2,3,4):
            raise ValueError('invalid Level: ' + eid)
        result[eid] = row; bindings.add(binding)
    return result


def _paired_summary(pairs):
    tax = Counter(); presence = Counter(); validity = Counter()
    semantic = {k:{v:0 for v in ('win','loss','tie','uncertain')} for k in SEMANTIC}
    for a,b in pairs:
        labels_a, labels_b = _labels(a), _labels(b)
        tax[(None if labels_a is None else tuple(labels_a),None if labels_b is None else tuple(labels_b))] += 1
        presence[('invalid' if labels_a is None else 'nonempty' if labels_a else 'empty',
                  'invalid' if labels_b is None else 'nonempty' if labels_b else 'empty')] += 1
        validity[(a['status'],b['status'])] += 1
        for metric in SEMANTIC:
            semantic[metric][_outcome(semantic_value(a, metric),semantic_value(b, metric))] += 1
    def transitions(counts):
        return [dict(before=list(a) if isinstance(a,tuple) else a,
                     after=list(b) if isinstance(b,tuple) else b,count=n)
                for (a,b),n in sorted(counts.items(),key=lambda x:json.dumps(x[0],ensure_ascii=False))]
    return dict(targets=len(pairs),sources=len({a['sample_id'] for a,b in pairs}),
        taxonomy_transitions=transitions(tax),error_presence_transitions=transitions(presence),
        validity_transitions=transitions(validity),semantic=semantic)


def paired_analysis(before, after):
    """Require identical IDs and evaluation bindings, preserving full transitions."""
    left,right = _index(before),_index(after)
    if set(left) != set(right):
        raise ValueError('foreign or missing paired IDs')
    pairs = [(left[k],right[k]) for k in sorted(left)]
    for a,b in pairs:
        if any(a.get(k) != b.get(k) for k in ('sample_id','level','faulty','family_id')) or set(a['gold_taxonomy']) != set(b['gold_taxonomy']):
            raise ValueError('paired source/Level/gold binding mismatch: ' + a['example_id'])
    def group(level=None,faulty=None):
        return _paired_summary([(a,b) for a,b in pairs if (level is None or a['level']==level) and
                               (faulty is None or a['faulty']==faulty)])
    return dict(overall=group(),by_level={str(l):group(level=l) for l in (1,2,3,4)},
        by_status={n:group(faulty=f) for n,f in [('clean',False),('faulty',True)]},
        by_level_status={str(l):{n:group(level=l,faulty=f) for n,f in [('clean',False),('faulty',True)]} for l in (1,2,3,4)},
        per_target=[dict(example_id=a['example_id'],sample_id=a['sample_id'],level=a['level'],faulty=a['faulty'],
            before_taxonomy=_labels(a),after_taxonomy=_labels(b),before_status=a['status'],after_status=b['status'],
            semantic={k:_outcome(semantic_value(a,k),semantic_value(b,k)) for k in SEMANTIC}) for a,b in pairs])
