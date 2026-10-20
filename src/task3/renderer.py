"""Deterministic, closed-vocabulary projection of approved oracle findings.

No model call and no public inference. Support is conditional on the approval of
input facts; exact source binding is not independent semantic verification.
"""
from __future__ import annotations

import hashlib
import re
from src.task3.adequacy import assess_repair_action
from src.task3.compliance import check
from src.synth.compliance import level_of
from src.synth.taxonomy import LABEL_SPACE

_CJK = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')


def _units(record, findings):
    if record.source == 'public' or record.split == 'public':
        raise ValueError('oracle renderer cannot be used on public data')
    level = level_of(record.target_feedback_level)
    if level not in (1, 2, 3):
        raise ValueError('oracle renderer supports Levels 1 through 3 only')
    units = []
    seen = set()
    pids = {p.get('pid') for p in record.problems}
    for finding in findings:
        fid = finding['finding_id']
        if fid in seen:
            raise ValueError('duplicate finding support')
        seen.add(fid)
        if finding['proposed_taxonomy_label'] not in LABEL_SPACE:
            raise ValueError('unsupported taxonomy group')
        if finding['problem_id'] is not None and finding['problem_id'] not in pids:
            raise ValueError('finding problem support is absent')
        quote = finding['source_quote']
        if not quote or record.code.count(quote) != 1:
            raise ValueError('source excerpt must resolve to one exact location')
        start = record.code.index(quote)
        location = {'line_start':record.code[:start].count('\n')+1,
                    'line_end':record.code[:start+len(quote)].count('\n')+1,
                    'char_start':start,'char_end':start+len(quote)}
        fact, cause = finding['error'], finding['cause']
        if not fact.strip() or not cause.strip():
            raise ValueError('finding support must contain fact and cause')
        if _CJK.search(fact + cause):
            raise ValueError('language: unsupported CJK prose in finding')
        compiler_support = None
        if finding['proposed_taxonomy_label'] == 'Lỗi biên dịch':
            evidence = (record.provenance or {}).get('_task3_compile_check', {})
            diagnostic = evidence.get('diagnostic', record.compile_log or '')
            errors = []
            if evidence.get('status') == 'compile_error':
                for line in diagnostic.splitlines():
                    m = re.search(r':(\d+):(?:\d+:)?\s*(?:fatal )?error:', line)
                    if m and location['line_start'] <= int(m[1]) <= location['line_end']:
                        errors.append(line)
            if not errors:
                raise ValueError('compiler error evidence at the finding location is required; warning is insufficient')
            compiler_support = {'severity':'error','diagnostic_lines':errors}
        action = None
        if level == 3:
            direction = finding['permitted_repair_direction']
            if _CJK.search(direction):
                raise ValueError('language: unsupported CJK repair prose')
            recognized = assess_repair_action(record, direction, source_quote=quote)
            if recognized['kind'] != 'specific' or len(recognized['relations']) != 1:
                raise ValueError('Level 3 requires one specific source-bound repair relation')
            action = dict(recognized['relations'][0], text=direction)
        units.append({'finding_id':fid,'problem_id':finding['problem_id'],
                      'source_code_utf8_sha256':hashlib.sha256(record.code.encode()).hexdigest(),
                      'source_quote':quote,'location':location,'observed_fact':fact,'cause':cause,
                      'compiler_support':compiler_support,'repair_action':action})
    return units


def _project(level, units):
    if level == 1:
        return 'Bài làm cần được rà soát thêm.' if units else 'Cảm ơn em đã chia sẻ bài làm.'
    if not units:
        return 'Chưa có finding được duyệt để đưa ra chẩn đoán; chưa kết luận bài đúng.'
    paragraphs = []
    for unit in units:
        pid = unit['problem_id'] or 'toàn bài'
        where = f"{pid}, dòng {unit['location']['line_start']}"
        text = f"Vị trí: {where}.\nNhận định: {unit['observed_fact']}\nNguyên nhân: {unit['cause']}"
        if level == 3:
            action = unit['repair_action']
            # Preserve the approved meaning/qualifiers. Only omit disclosure metadata.
            direction = re.sub(r"\s+khi Level [1-4] cho phép\.?$", ".", action['text'])
            text += "\nHướng sửa: " + direction
        paragraphs.append(text)
    return '\n\n'.join(paragraphs)


def render_findings(record, findings):
    """Project only review-approved facts. Caller must load approval provenance."""
    units = _units(record, findings)
    level = level_of(record.target_feedback_level)
    feedback = _project(level, units)
    disclosure = check(feedback, level, version=2)
    if not disclosure.ok:
        raise ValueError('Level disclosure rejected: ' + ','.join(disclosure.violations))
    return {'renderer_version':1,'condition':'oracle_only_not_public','sample_id':record.sample_id,
            'level':level,'units':units,'feedback':feedback,
            'evidence_status':'conditional_on_reviewed_findings' if units else 'no_approved_finding_not_clean'}


def validate_rendered(record, findings, document):
    expected = render_findings(record, findings)
    if set(document) != set(expected) or any(document[k] != expected[k] for k in expected if k != 'feedback'):
        raise ValueError('unsupported content or finding support mismatch')
    if document['feedback'] != expected['feedback']:
        raise ValueError('feedback projection contains unsupported additions or omissions')
    return {'factual_support':'conditional_on_reviewed_findings',
            'supported_units':len(document['units']), 'finding_coverage':1.0 if findings else None,
            'level_compliance':True,'freeform_claims_allowed':False,'taxonomy_model_score':None}
