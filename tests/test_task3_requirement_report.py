import pytest
from scripts.task3_requirement_report import summarize_semantics, validate_pairs


def row(sid,arm,status,flags,level=2):
    return dict(sample_id=sid,arm=arm,reference_status=status,level=level,
      completion=True,fallback_used=False,flags=flags,stratum='new')


def test_uncertain_and_unresolved_are_not_silently_clean_or_pass():
    rows=[row('u','R15','uncertain',{'false_technical_claim':None,'level_violation':None}),
          row('c','R15','clean',{'false_technical_claim':False,'level_violation':False})]
    out={'u':{'taxonomy_error':[]},'c':{'taxonomy_error':[]}}
    m=summarize_semantics(rows,out)
    assert m['source_uncertain']==1 and m['clean_support']==1
    assert m['clean_nonempty_taxonomy']['numerator']==0
    assert m['false_technical_claim']['unknown']==1
    assert m['false_technical_claim']['denominator']==1


def test_fallback_stays_in_whole_set_semantic_denominator():
    r=row('x','candidate','defect',{'location_correct':True,'cause_correct':True,'false_technical_claim':False,
       'main_defect_missed':False,'false_clean_praise':False,'level_violation':False})
    r['fallback_used']=True
    m=summarize_semantics([r],{'x':{'taxonomy_error':['Lỗi logic']}})
    assert m['requested']==1 and m['fallback']['numerator']==1
    assert m['location_and_cause']['numerator']==1


def test_paired_levels_and_id_sets_must_match():
    rows=[row('x','R15','defect',{},2),row('x','candidate','defect',{},3)]
    with pytest.raises(ValueError,match='Level'):validate_pairs(rows)
    with pytest.raises(ValueError,match='ID'):validate_pairs(rows[:1])
