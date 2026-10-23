"""Bounded compact diagnosis, citation renderer and attributed direct rescue."""
from __future__ import annotations
import copy
import json

from src.task3 import compact as c,grounded as g
from src.task3.round15_disclosure import disclosure_violations
from src.task3.round15 import SYSTEM as DIRECT_SYSTEM,parse_response

RESCUE_SUPPORT='''Với output direct được cung cấp, xác minh độc lập bằng source và đề.
Không hợp thức hóa lỗi bịa. Chỉ trả compact diagnosis schema cho các lỗi THẬT hỗ trợ output,
hoặc clean nếu output[] được kiểm source và chưa thấy lỗi. uncertain nếu không hỗ trợ được.
Không lấy taxonomy/feedback của output làm bằng chứng. Không thêm gold hoặc lời giải mẫu.
'''+c.SYSTEM_V2
FEEDBACK_SYSTEM=g.FEEDBACK_SYSTEM+'''
Chủ đề giúp nhận xét gắn bài; không nhắc trạng thái pipeline hoặc quy trình nội bộ.
L2 chỉ diễn giải hành vi/causal conflict hiện tại, không so với phép thay thế sẽ làm đúng.
L3 nếu repair rỗng, suy ra một hướng sửa từ chẩn đoán, không thêm lỗi mới.
Không dùng một lời nhắc chung thay cho lỗi chính khi Level cho phép chẩn đoán.'''
GUARD_SYSTEM=g.GUARD_SYSTEM+'''
Phản hồi chung chung thay cho chẩn đoán ở L2+ làm main_covered=false.
L1 nhắc nhẹ đúng chủ đề/trạng thái là hợp lệ, không bắt nêu lỗi hoặc vị trí.
Clean không cần phát minh lỗi/hướng sửa. Đừng yêu cầu sửa lỗi nếu findings rỗng.'''


def failure(reason,status='generation_or_tool_failure'):
    return dict(status=status,reason=reason,selected_findings=[],findings=[],taxonomy_error=None,
                taxonomy_support={},publishable=False,provenance='model',semantic_checked=False)


def call(journal,key,messages):
    row=journal.call(key,messages)
    if row['error']:raise RuntimeError(row['error'])
    return row['raw_text']


def scope_diagnosis(unit,scope,journal,version=1):
    rejected=[];last='';best=None
    for attempt in range(1,journal.config.get('diagnosis_max_attempts',2)+1):
        key=unit['request_id']+'/diagnosis/'+scope+'/'+str(attempt)
        try:
            raw=call(journal,key,c.diagnosis_messages(unit['task'],scope,last,version))
            d=c.parse(raw,unit['task'],scope)
            if d['publishable']:
                verdict=g.strict_object(call(journal,key+'/semantic',c.semantic_messages(d,unit['task'])))
                d=c.apply_semantic(d,verdict)
            best=d
            if d['publishable']:
                d['attempt_rejections']=rejected;return d
            last='Nhận định chưa được xác minh; kiểm lại đúng source/đề. '+','.join(r['reason']for r in d['rejected'])[:180]
        except (ValueError,TypeError,KeyError,RuntimeError) as exc:last=str(exc);best=failure(last)
        rejected.append(dict(attempt=attempt,reason=last))
    best=best or failure(last);best['attempt_rejections']=rejected
    return best


def diagnose(unit,journal,version=1):
    task=g.task_payload(unit['task']);scope_list=c.scopes(task);results={};blocked=[];unassessed=[]
    prerequisite=task['grading_policy']==g.SUPPORTED_PREREQUISITE
    if prerequisite:g.require(scope_list and scope_list[0]=='P1','explicit prerequisite requires first P1')
    for index,scope in enumerate(scope_list):
        d=scope_diagnosis(unit,scope,journal,version);results[scope]=d
        if prerequisite and scope=='P1':
            if not d['publishable']:unassessed=scope_list[index+1:];break
            if d['selected_findings']:blocked=scope_list[index+1:];break
    selected=[]
    for d in results.values():
        for f in d['selected_findings']:selected.append({**f,'id':'F'+str(len(selected)+1)})
    complete=not unassessed and all(d['publishable']for d in results.values())
    status='confirmed_findings' if selected else 'reviewed_no_error_found' if complete else 'candidate_unverified'
    result=dict(status=status,reason='; '.join(d['reason']for d in results.values()),
        findings=selected,selected_findings=selected,scope=dict(assessed=list(results),blocked=blocked,unassessed=unassessed),
        coverage='all_scheduled_scopes_model_reviewed'if complete else 'partial_model_assessment',
        scope_results=results,provenance='model',semantic_checked=all(d.get('semantic_checked')for d in results.values()if d['publishable']),
        rejected=[dict(scope=s,**r)for s,d in results.items()for r in d.get('rejected',[])])
    if unassessed:result['selected_findings']=[];result['status']='candidate_unverified'
    return c.project(result)


def guard_accept(raw):return g.parse_guard(raw)['accepted']


def render(unit,d,journal,arm='C2',*,oracle=False):
    if not oracle:c.require_production(d)
    else:g.require(d.get('provenance')=='offline_oracle','explicit oracle required')
    g.require(arm in {'C1','C2'},'unknown renderer')
    context=c.topic(unit['task']);view=c.view(d,unit['level'],context)
    if arm=='C1':view={**view,'task':g.task_payload(unit['task']),'findings':d['selected_findings']}
    messages=[dict(role='system',content=FEEDBACK_SYSTEM),dict(role='user',content=json.dumps(view,ensure_ascii=False))]
    rejects=[];codes=[]
    for attempt in range(1,journal.config.get('feedback_max_attempts',2)+1):
        key=unit['request_id']+'/'+arm+'/'+str(attempt)
        retry=[dict(role='user',content='Vi phạm trước: '+','.join(codes)+'. Viết lại đúng Level từ view, không thêm chi tiết.')]if codes else []
        try:
            response=g.parse_feedback(call(journal,key,messages+retry),d,unit['level'])
            lexical=disclosure_violations(response['feedback'],unit['level'])
            if lexical:codes=['L1_DETAIL_LEAK'if unit['level']==1 else 'L2_EXPLICIT_REPAIR'if unit['level']==2 else 'FULL_SOLUTION'];raise ValueError('lexical disclosure')
            guard=None
            if arm=='C2' or not oracle:
                check=[dict(role='system',content=GUARD_SYSTEM),dict(role='user',content=json.dumps({'view':view,'response':response},ensure_ascii=False))]
                guard=g.parse_guard(call(journal,key+'/guard',check))
                if not guard['accepted']:codes=g.safe_retry_codes(guard['reason_codes'])or['UNSUPPORTED_CLAIM'];raise ValueError('semantic guard rejected')
            return dict(status='resolved',origin='offline_oracle'if oracle else 'grounded',
                output=dict(taxonomy_error=d['taxonomy_error'],feedback=response['feedback']),
                sentence_support=response['sentence_support'],taxonomy_support=d['taxonomy_support'],guard=guard,rejections=rejects)
        except (ValueError,TypeError,KeyError,RuntimeError) as exc:
            rejects.append(dict(attempt=attempt,reason=str(exc),codes=codes));codes=codes or ['SCHEMA']
    return dict(status='unresolved',origin='offline_oracle'if oracle else 'grounded',reason='feedback_exhausted',rejections=rejects)


def rescue(unit,journal):
    """Direct R15 prompt; no legacy placeholder controller, source support required."""
    rejected=[];retry=''
    for attempt in range(1,journal.config.get('rescue_max_attempts',2)+1):
        key=unit['request_id']+'/rescue/'+str(attempt)
        task=g.task_payload(unit['task']);payload={**task,'requested_level':unit['level']}
        messages=[dict(role='system',content=DIRECT_SYSTEM),dict(role='user',content=json.dumps(payload,ensure_ascii=False))]
        if retry:messages.append(dict(role='user',content='Sửa vi phạm: '+retry[:200]+'. Không đổi taxonomy thành[] để qua schema.'))
        try:
            output=parse_response(call(journal,key,messages))
            g.require(not disclosure_violations(output['feedback'],unit['level']),'direct disclosure')
            # A new source check reconstructs support; self-produced output is a claim,
            # never oracle evidence. Multi-PID direct rescue is deliberately withheld
            # until its per-scope attribution can be established safely.
            g.require(c.scopes(task)==['whole'],'multi_problem rescue requires per-scope support; unresolved')
            support_messages=[dict(role='system',content=RESCUE_SUPPORT),dict(role='user',content=json.dumps(
                {'task':task,'scope_to_review':'whole','claimed_output':output},ensure_ascii=False))]
            d=c.parse(call(journal,key+'/support',support_messages),task,'whole')
            g.require(d['publishable'] and set(d['taxonomy_error'])==set(output['taxonomy_error']),'direct taxonomy lacks source support')
            d=c.apply_semantic(d,g.strict_object(call(journal,key+'/support/semantic',c.semantic_messages(d,task))))
            g.require(d['publishable'] and set(d['taxonomy_error'])==set(output['taxonomy_error']),'direct support rejected')
            support=[dict(text=output['feedback'],finding_ids=[f['id']for f in d['selected_findings']])]
            guard=g.parse_guard(call(journal,key+'/guard',[dict(role='system',content=GUARD_SYSTEM),
                dict(role='user',content=json.dumps({'view':c.view(d,unit['level'],c.topic(task)),
                    'response':dict(feedback=output['feedback'],sentence_support=support)},ensure_ascii=False))]))
            g.require(guard['accepted'],'direct semantic guard rejected')
            return dict(status='resolved',origin='rescue',output=output,support_diagnosis=d,sentence_support=support,guard=guard,rejections=rejected)
        except (ValueError,TypeError,KeyError,RuntimeError) as exc:
            retry=str(exc);rejected.append(dict(attempt=attempt,reason=retry))
    return dict(status='unresolved',origin='rescue',reason='rescue_exhausted',rejections=rejected)


def run_unit(unit,journal,version=1):
    d=diagnose(unit,journal,version)
    grounded=render(unit,d,journal)if d['publishable']else dict(status='unresolved',origin='grounded',reason=d['status'])
    final=grounded if grounded['status']=='resolved'else rescue(unit,journal)
    return dict(request_id=unit['request_id'],sample_id=unit['sample_id'],diagnosis=d,grounded=grounded,final=final)
