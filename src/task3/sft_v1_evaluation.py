"""Pure, strict evaluation and complete paired casebooks for Task 3 SFT v1.

This module does not load a model or judge feedback semantics. Semantic review
requires inspecting the delivered source, specification and response together.
"""
from __future__ import annotations

from collections import Counter
from html import escape
import json
import math
from pathlib import Path
import re
import statistics


EVALUATION_POLICY = {
    'version': 'task3_sft_v1_evaluation_v1',
    'parser': {
        'accepted_finish_reason': 'eos',
        'outer_whitespace': 'strip only outside the JSON document',
        'outer_fence': 'optionally remove exactly one complete full-string ```json or ``` '
                       'fence with newline-delimited body; no prefix, suffix, or partial extraction',
        'json': 'exactly one strict JSON object; reject duplicate keys and NaN/Infinity',
        'schema': {'keys': ['taxonomy_error', 'feedback'],
                   'taxonomy_error': 'list of distinct strings in the delivered label space',
                   'feedback': 'nonempty string after whitespace check; preserve original value'},
        'repairs': 'none; never infer fields, change payload values, retry, or convert failures to clean',
        'failure_statuses': ['missing', 'timeout', 'length', 'generation_error',
                             'termination_failure', 'malformed_json', 'schema_failure'],
    },
    'taxonomy': {
        'metric_role': 'diagnostic; not the official Task 3 score',
        'unit': 'target; all four Levels share one source and are not independent programs',
        'valid_only': 'micro TP/FP/FN restricted to valid outputs; report valid target denominator',
        'all_targets_conservative': 'micro TP/FP from valid outputs; invalid faulty targets '
                                    'contribute every gold label as FN; invalid clean targets '
                                    'remain failures, never clean predictions',
        'exact_match': 'set equality on valid outputs only, divided by every target including invalids',
        'clean_false_alarms': 'nonempty valid taxonomy on gold-clean targets / all gold-clean '
                              'targets; invalid counts separate; source rate counts any Level alarm',
        'zero_denominator': 'null for undefined ratios, including F1 when TP+FP+FN is zero',
    },
    'feedback_quality': {
        'review_type': 'agent_review_not_independent_or_official',
        'method': 'source-grounded side-by-side agent review, never exact gold wording or keyword matching',
        'unit': 'each target response; retain target/source/Level denominators',
        'valid_without_review': 'pending_source_grounded_review',
        'invalid_output': 'not_evaluable for every semantic dimension; retain in all totals',
        'evidence': 'record source/specification evidence and response excerpts for each finding; '
                    'do not infer semantic correctness from taxonomy match or lower loss',
        'dimensions': {
            'diagnosis_supported': 'whether claimed behavior/defects follow from source and specification',
            'location_and_condition': 'incorrect location or omitted triggering condition; preserve '
                                      'essential conditions rather than accepting a vague diagnosis',
            'unsupported_defects': 'invented requirements, unsupported defects, and false alarms on clean code',
            'level_compliance': 'apply the exact delivered requested-Level contract below',
            'vietnamese_compliance': 'feedback prose in Vietnamese; code and identifiers are permitted',
            'l3_repair_direction': 'for Level 3, concrete useful correct repair direction without '
                                   'a complete solution; other Levels not_applicable',
            'l4_solution_quality': 'for Level 4, explain and provide complete correct C++11 solution '
                                   'with submission mode respected; retain valid code when clean; '
                                   'other Levels not_applicable',
        },
        'dimension_verdicts': ['pass', 'fail', 'uncertain', 'not_applicable', 'not_evaluable'],
        'level_contract': {
            '1': 'brief status or praise only; no location, cause, repair or code',
            '2': 'one concise Vietnamese sentence identifying faulty location and cause; '
                 'describing faulty behavior is allowed even when a learner can infer a fix; '
                 'no repair instruction, replacement expression or code snippet',
            '3': 'diagnosis plus concrete repair direction; no complete solution',
            '4': 'explanation and complete corrected solution; clean inputs explain the approach '
                 'and retain valid code; respect function-only versus full-program requirements',
        },
    },
}

_OUTER_FENCE = re.compile(r'\A```(?:json)?[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```\Z')
_OUTPUT_KEYS = {'taxonomy_error', 'feedback'}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('non-finite JSON constant: ' + value)


def _schema_error(value, labels=None):
    if not isinstance(value, dict) or set(value) != _OUTPUT_KEYS:
        return 'expected exactly taxonomy_error and feedback keys'
    taxonomy = value['taxonomy_error']
    if not isinstance(taxonomy, list) or any(not isinstance(label, str) for label in taxonomy):
        return 'taxonomy_error must be a list of strings'
    if len(set(taxonomy)) != len(taxonomy):
        return 'duplicate taxonomy label'
    if labels is not None and any(label not in labels for label in taxonomy):
        return 'taxonomy label outside delivered label space'
    if not isinstance(value['feedback'], str) or not value['feedback'].strip():
        return 'feedback must be a nonempty string'
    return None


def parse_response(raw: str, labels: list[str], finish_reason: str = 'eos') -> dict:
    """Parse a full response without payload repair, preserving invalid termination."""
    reasons = {'timeout': 'timeout', 'max_time': 'timeout',
               'length': 'length', 'max_new_tokens': 'length', 'max_length': 'length',
               'generation_error': 'generation_error', 'error': 'generation_error',
               'exception': 'generation_error', 'missing': 'missing'}
    if finish_reason != 'eos':
        return dict(status=reasons.get(finish_reason, 'termination_failure'), parsed=None,
                    error='generation did not end with EOS', outer_fence_removed=False)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return dict(status='missing', parsed=None, error='empty or absent response', outer_fence_removed=False)
    if not isinstance(raw, str):
        return dict(status='malformed_json', parsed=None, error='response is not text', outer_fence_removed=False)
    text = raw.strip()
    match = _OUTER_FENCE.fullmatch(text)
    if match:
        text = match.group('body')
    try:
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        return dict(status='malformed_json', parsed=None, error=str(exc), outer_fence_removed=bool(match))
    error = _schema_error(value, labels)
    if error:
        return dict(status='schema_failure', parsed=None, error=error, outer_fence_removed=bool(match))
    return dict(status='valid', parsed=value, error=None, outer_fence_removed=bool(match))


def _align(examples, generations):
    """Refuse duplicate/misaligned rows and explicitly retain absent generations."""
    by_id = {}
    for example in examples:
        eid = example['example_id']
        if eid in by_id:
            raise ValueError('duplicate target: ' + eid)
        if type(example['level']) is not int or example['level'] not in (1, 2, 3, 4):
            raise ValueError('invalid requested Level: ' + eid)
        gold = json.loads(example['completion'], object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
        if _schema_error(gold):
            raise ValueError('invalid reference output: ' + eid)
        by_id[eid] = (example, gold)
    rows = {}
    for row in generations:
        eid = row['example_id']
        if eid not in by_id or eid in rows:
            raise ValueError('duplicate or foreign generation: ' + eid)
        example = by_id[eid][0]
        if row.get('sample_id') != example['sample_id'] or row.get('level') != example['level']:
            raise ValueError('generation source/Level mismatch: ' + eid)
        if not isinstance(row.get('status'), str) or not row['status']:
            raise ValueError('missing generation status: ' + eid)
        if row['status'] == 'valid':
            if row.get('finish_reason') != 'eos' or _schema_error(row.get('parsed')):
                raise ValueError('valid generation has invalid parsed payload/termination: ' + eid)
        elif row.get('parsed') is not None:
            raise ValueError('invalid generation must have parsed=None: ' + eid)
        rows[eid] = row
    return [(example, gold, rows.get(eid, dict(example_id=eid, sample_id=example['sample_id'],
             level=example['level'], raw=None, parsed=None, status='missing', finish_reason='missing',
             input_tokens=None, output_tokens=None, wall_s=None)))
            for eid, (example, gold) in by_id.items()]


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _micro(tp, fp, fn, targets, invalid):
    return dict(tp=tp, fp=fp, fn=fn, precision=_ratio(tp, tp + fp), recall=_ratio(tp, tp + fn),
                f1=_ratio(2 * tp, 2 * tp + fp + fn), targets=targets, invalid_targets=invalid)


def _summary(values):
    values = [v for v in values if v is not None]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
           for v in values):
        raise ValueError('cost/length measurements must be finite nonnegative numbers or None')
    return dict(count=len(values), sum=sum(values), mean=statistics.mean(values) if values else None,
                median=statistics.median(values) if values else None,
                min=min(values) if values else None, max=max(values) if values else None)


def _aggregate(aligned):
    n = len(aligned)
    valid = sum(row['status'] == 'valid' for _, _, row in aligned)
    tp = fp = fn = invalid_fn = exact = 0
    source_validity, clean_sources, alarm_sources, invalid_clean_sources = {}, set(), set(), set()
    clean_targets = clean_invalid = clean_alarm = 0
    for example, gold, row in aligned:
        sid = example['sample_id']
        is_valid = row['status'] == 'valid'
        source_validity.setdefault(sid, []).append(is_valid)
        expected = set(gold['taxonomy_error'])
        if is_valid:
            predicted = set(row['parsed']['taxonomy_error'])
            tp += len(expected & predicted)
            fp += len(predicted - expected)
            fn += len(expected - predicted)
            exact += predicted == expected
        else:
            invalid_fn += len(expected)
        if not expected:
            clean_targets += 1
            clean_sources.add(sid)
            if not is_valid:
                clean_invalid += 1
                invalid_clean_sources.add(sid)
            elif row['parsed']['taxonomy_error']:
                clean_alarm += 1
                alarm_sources.add(sid)
    return dict(
        targets=n, sources=len(source_validity), valid_outputs=valid, invalid_outputs=n - valid,
        valid_output_coverage=_ratio(valid, n),
        status_counts=dict(Counter(row['status'] for _, _, row in aligned)),
        source_coverage=dict(sources_all_targets_valid=sum(all(v) for v in source_validity.values()),
                             sources_with_any_valid=sum(any(v) for v in source_validity.values()),
                             sources_with_any_invalid=sum(not all(v) for v in source_validity.values())),
        taxonomy=dict(valid_only=_micro(tp, fp, fn, valid, 0),
                      all_targets_conservative=_micro(tp, fp, fn + invalid_fn, n, n - valid),
                      exact_match_all_targets=dict(correct=exact, denominator=n, rate=_ratio(exact, n))),
        clean_false_alarms=dict(
            targets=dict(false_alarms=clean_alarm, denominator=clean_targets, invalid=clean_invalid,
                         valid=clean_targets - clean_invalid, rate=_ratio(clean_alarm, clean_targets)),
            sources=dict(false_alarms=len(alarm_sources), denominator=len(clean_sources),
                         with_invalid=len(invalid_clean_sources), rate=_ratio(len(alarm_sources), len(clean_sources)))),
        feedback_quality=dict(review_type=EVALUATION_POLICY['feedback_quality']['review_type'],
                              reviewed=0, pending_source_grounded_review=valid, not_evaluable=n - valid),
        lengths=dict(raw_characters=_summary([len(row['raw']) if isinstance(row.get('raw'), str) else None
                                              for _, _, row in aligned]),
                     feedback_characters=_summary([len(row['parsed']['feedback'])
                                                    for _, _, row in aligned if row['status'] == 'valid']),
                     feedback_words=_summary([len(row['parsed']['feedback'].split())
                                               for _, _, row in aligned if row['status'] == 'valid'])),
        costs={key: _summary([row.get(key) for _, _, row in aligned])
               for key in ('input_tokens', 'output_tokens', 'wall_s')},
    )


def aggregate_metrics(examples: list[dict], generations: list[dict]) -> dict:
    """Report all-target and per-Level diagnostics; never guess semantic quality."""
    aligned = _align(examples, generations)
    result = _aggregate(aligned)
    result['denominator_policy'] = EVALUATION_POLICY['taxonomy']
    result['by_level'] = {str(level): _aggregate([item for item in aligned if item[0]['level'] == level])
                          for level in range(1, 5)}
    return result


def _pre(value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    return '<pre>' + escape(value) + '</pre>'


def write_casebook(path: Path, examples: list[dict], generations_by_state: dict[str, list[dict]],
                   losses_by_state: dict | None = None) -> None:
    """Save every target, native prompt, gold and state output in escaped paired HTML.

    Casebooks are local review artifacts. Reference targets are shown separately
    from the unchanged native system/user messages used for generation.
    """
    states = list(generations_by_state)
    aligned = {state: _align(examples, generations_by_state[state]) for state in states}
    # Still validate targets for an empty state map.
    references = _align(examples, [])
    status_options = sorted({row['status'] for rows in aligned.values() for _, _, row in rows})
    parts = ['<!doctype html><html lang="vi"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<title>Task 3 SFT v1 paired casebook</title>',
             '<style>body{font:15px system-ui;margin:24px;background:#f6f7f9;color:#172033}'
             'header{position:sticky;top:0;background:#f6f7f9;padding:12px 0;z-index:1}'
             'section{background:white;border:1px solid #ccd2dc;border-radius:8px;padding:16px;margin:20px 0}'
             'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5f7;padding:12px}'
             '.paired{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}'
             'article{border:1px solid #ccd2dc;padding:12px;min-width:0}input,select{padding:8px;margin:4px}'
             '[hidden]{display:none!important}.status{font-weight:700}h2{overflow-wrap:anywhere}</style>',
             '<header><h1>Task 3 SFT v1 paired casebook</h1>',
             f'<p>{len(examples)} targets / {len({e["sample_id"] for e in examples})} sources; '
             'four Levels may share a source. Taxonomy metrics are diagnostic. '
             'Semantic verdicts require source-grounded agent review, '
             'not independent human or official grader review.</p>',
             '<input id="search" type="search" placeholder="Search ID, source, prompt or output" '
             'aria-label="Search casebook">',
             '<select id="level" aria-label="Filter Level"><option value="">All Levels</option>'
             '<option value="1">L1</option><option value="2">L2</option>'
             '<option value="3">L3</option><option value="4">L4</option></select>',
             '<select id="status" aria-label="Filter status"><option value="">All statuses</option>',
             *[f'<option value="{escape(status, quote=True)}">{escape(status)}</option>' for status in status_options],
             '</select><span id="visible"></span></header>',
             '<details><summary>Frozen parser, denominator and semantic review policy</summary>',
             _pre(EVALUATION_POLICY), '</details>']
    if losses_by_state is not None:
        parts.extend(['<details open><summary>Teacher-forced equal-example losses by state</summary>',
                      _pre(losses_by_state), '</details>'])
    for index, (example, gold, _) in enumerate(references):
        statuses = [aligned[state][index][2]['status'] for state in states]
        parts.extend([f'<section class="case" data-level="{example["level"]}" '
                      f'data-statuses="{escape(" ".join(statuses), quote=True)}">',
                      f'<h2>{escape(example["example_id"])} · source {escape(example["sample_id"])} '
                      f'· L{example["level"]}</h2>',
                      '<details><summary>Complete native model prompt: specification and source</summary>'])
        for message in example['prompt']:
            parts.extend([f'<h3>{escape(message["role"])}</h3>', _pre(message['content'])])
        parts.extend(['</details><details><summary>Gold target (private reference, separate from model prompt)</summary>',
                      _pre(gold), '</details><div class="paired">'])
        for state in states:
            row = aligned[state][index][2]
            quality = 'pending_source_grounded_review' if row['status'] == 'valid' else 'not_evaluable'
            parts.extend(['<article>', f'<h3>{escape(str(state))}</h3>',
                          f'<p class="status">{escape(row["status"])} · finish: '
                          f'{escape(str(row.get("finish_reason")))}</p>',
                          '<h4>Raw response</h4>', _pre(row.get('raw')),
                          '<h4>Parsed payload</h4>', _pre(row.get('parsed')),
                          f'<p>Semantic review: {quality}</p>',
                          '<h4>Recorded generation costs</h4>',
                          _pre({key: row.get(key) for key in ('input_tokens', 'output_tokens', 'wall_s')}),
                          '</article>'])
        parts.extend(['</div></section>'])
    parts.append('''<script>
const search = document.getElementById('search');
const level = document.getElementById('level');
const status = document.getElementById('status');
const cases = Array.from(document.querySelectorAll('section.case'));
function filterCases() {
  const query = search.value.toLocaleLowerCase();
  let shown = 0;
  for (const item of cases) {
    const match = (!level.value || item.dataset.level === level.value)
      && (!status.value || item.dataset.statuses.split(' ').includes(status.value))
      && (!query || item.textContent.toLocaleLowerCase().includes(query));
    item.hidden = !match;
    if (match) shown++;
  }
  document.getElementById('visible').textContent = shown + ' / ' + cases.length + ' targets';
}
search.addEventListener('input', filterCases);
level.addEventListener('change', filterCases);
status.addEventListener('change', filterCases);
filterCases();
</script></html>''')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(parts), encoding='utf-8')
