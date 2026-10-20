"""Structured projection and explicit abstention; independent of oracle files/v4.

`project` is the evidence-authority boundary, shared by the artificial oracle
control and verified predictions. Inference must call `render`, which rederives
all claims. Oracle controls are never routed into `complete`.
"""
from __future__ import annotations
import re
from src.synth.taxonomy import LABEL_SPACE
from src.task3.compliance import check
from src.task3.discovery import discover, validate_finding
from src.task3.renderer import _project


def project(item, findings, level):
    """Project an externally certified contract; does not establish its truth."""
    if level not in (1,2,3,4):raise ValueError('Level outside 1..4')
    units=[]
    for f in findings:
        span=f['source_span']
        if f['status']!='supported_error' or f['taxonomy_group'] not in LABEL_SPACE:
            raise ValueError('only certified official-group findings can be projected')
        if not (0<=span['start']<span['end']<=len(item.code)) or item.code[span['start']:span['end']]!=span['quote']:
            raise ValueError('invalid source binding')
        if span['line_start']!=item.code[:span['start']].count('\n')+1 or span['line_end']!=item.code[:span['end']].count('\n')+1:
            raise ValueError('invalid line binding')
        if f['problem_id'] is not None and f['problem_id'] not in {p['pid'] for p in item.problems}:
            raise ValueError('unknown problem id')
        if not f['observed_fact'].strip() or not f['cause'].strip() or not f['evidence']:
            raise ValueError('missing claim/evidence')
        action=f['repair_action']
        if level==3 and (not action or not action['target'] or not action['reference']):
            return {'status':'blocked','reason':'missing_verified_repair'}
        units.append({'problem_id':f['problem_id'],'location':span,'observed_fact':f['observed_fact'],
                      'cause':f['cause'],'repair_action':action})
    if level==4:
        # Complete only under an exhaustive, intentionally tiny specification.
        result=discover(item);cert=result['certificate']
        if cert is None or len(findings) != int(cert['required'] != cert['observed']) or any(f['taxonomy_group'] != 'Lỗi logic' or f['source_span']['quote'] != str(cert['observed']) for f in findings):
            return {'status':'blocked','reason':'no_complete_solution_certificate'}
        fixed=f"int main(){{return {cert['required']};}}"
        text=f"Đề yêu cầu trạng thái trả về {cert['required']}. Lời giải cho toàn bộ đặc tả giới hạn này:\n```cpp\n{fixed}\n```"
        return {'status':'rendered','feedback':text,'complete_solution_scope':'bounded_exit_status'}
    if not findings and level>1:
        return {'status':'blocked','reason':'no_supported_finding_or_clean_certificate'}
    text=_project(level,units)
    if re.search(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]',text):
        return {'status':'blocked','reason':'non_vietnamese_cjk_prose'}
    guard=check(text,level,version=2)
    if not guard.ok:return {'status':'blocked','reason':'level_disclosure:'+','.join(guard.violations)}
    return {'status':'rendered','feedback':text,'complete_solution_scope':None}


def render(item, findings, level):
    for f in findings:validate_finding(item,f)
    if findings!=discover(item)['findings']:
        raise ValueError('predicted rendering requires complete selected finding set')
    return project(item,findings,level)


def complete(item,level,*,policy='abstain'):
    """Never coerce unknown to [] or silently export incomplete label lists.

    supported_partial allows inspecting usable evidence/feedback; it is not an
    export fallback. Only exhaustive bounded certificates permit submissions.
    """
    if policy not in {'abstain','supported_partial'}:raise ValueError('unknown completion policy')
    result=discover(item);out=render(item,result['findings'],level)
    allowed=result['coverage_complete'] and out['status']=='rendered'
    partial=policy=='supported_partial' and result['findings'] and out['status']=='rendered'
    return {'submission':{'taxonomy_error':result['taxonomy'],'feedback':out['feedback']} if allowed else None,
            'taxonomy':result['taxonomy'] if allowed or partial else None,
            'feedback':out.get('feedback') if allowed or partial else None,
            'coverage_complete':result['coverage_complete'],
            'status':'complete' if allowed else 'partial_not_exportable' if partial else 'abstain',
            'reason':None if allowed else out.get('reason') or result['unknown_reason']}
