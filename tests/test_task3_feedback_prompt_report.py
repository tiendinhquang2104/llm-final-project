"""Reporting gates fail closed on missing/unknown evidence and incomplete pairs."""
import pytest


def api():
    from src.task3 import feedback_prompt_report
    return feedback_prompt_report


def row(sid,arm,level=2,score=1,**kw):
    return dict(dict(sample_id=sid,arm=arm,level=level,score=score,clean=False,
                output_quote='diagnosis',source_evidence={'quote':'return 0;'},
                false_technical_claim=False,false_clean=False,repair_disclosure=False,
                unknown=False),**kw)


def test_missing_pair_duplicate_or_wrong_evidence_binding_rejected():
    m=api();inputs=[{'sample_id':'id','code':'return 0;'}];outputs={'A':{'id':'diagnosis'},'C':{'id':'diagnosis'}}
    complete=[row('id','A'),row('id','C')]
    m.validate_reviews(inputs,outputs,complete)
    for bad in [complete[:1],complete+complete[:1],[dict(complete[0],output_quote='edited'),complete[1]]]:
        with pytest.raises(ValueError):m.validate_reviews(inputs,outputs,bad)


def test_proxy_net_thresholds_cannot_be_replaced_by_valid_schema_or_mean():
    m=api();v=[]
    for l in range(1,5):
        for i in range(12):v.extend([row(f'{l}-{i}','A',l,0),row(f'{l}-{i}','C',l,1)])
    assert m.decision(v,complete=True)['eligible']
    next(r for r in v if r['arm']=='C' and r['level']==2)['repair_disclosure']=True
    assert not m.decision(v,complete=True)['eligible']


def test_unknown_or_incomplete_always_retains_control():
    m=api();v=[row('id','A'),row('id','C',unknown=True)]
    assert not m.decision(v,complete=True)['eligible']
    assert not m.decision(v,complete=False)['eligible']


def test_paired_level_results_use_score_comparisons_not_taxonomy():
    m=api();v=[row('id','A',2,.5),row('id','C',2,1),row('other','A',3,1),row('other','C',3,0)]
    s=m.paired(v)
    assert (s['wins'],s['losses'],s['ties'],s['net'])==(1,1,0,0)
    assert s['per_level']['2']['net']==1 and s['per_level']['3']['net']==-1


def test_rendered_payload_audit_rejects_nested_teacher_even_in_allowed_fields():
    m=api();good={'statement':'task','code':'int main(){}','problems':[],'grading_policy':'policy',
                'compiler':{'status':'unavailable','diagnostic':''},'requested_level':2}
    m.audit_payload(good)
    for key,value in [('grading_policy',{'teacher':{'feedback':'secret'}}),
                      ('problems',[{'pid':'P1','statement':{'reference_finding':'secret'}}])]:
        with pytest.raises(ValueError):m.audit_payload(dict(good,**{key:value}))
