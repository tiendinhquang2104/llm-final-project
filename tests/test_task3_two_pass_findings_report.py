"""Offline rubric math uses full denominators, including unresolved clean cases."""
import importlib
import pytest

@pytest.fixture
def r():
    class Lazy:
        def __getattr__(self,n):
            try:return getattr(importlib.import_module('scripts.task3_two_pass_findings_report'),n)
            except ModuleNotFoundError:pytest.fail('findings report missing')
    return Lazy()


def good():return {'factual':True,'main_covered':True,'level_ok':True,'natural_role':True,'false_claim':False,'addresses_ban':False,'self_reference':False,'meta':False,'placeholder_only':False,'l1_detail_leak':False,'l2_repair_leak':None,'l3_actionable':None,'disputed':False}


def test_joint_gold_and_source_remain_separate(r):
    x=r.assess({'taxonomy_error':['Lỗi logic'],'feedback':'x'},[],[['Lỗi logic']], [good()])
    assert x['feedback_pass']is True and x['joint_gold']is False and x['joint_source']is True


def test_unresolved_clean_never_joint_credit(r):
    x=r.assess(None,[],[[]],[good()])
    assert not x['joint_gold']and not x['joint_source']and not x['feedback_pass']


def test_disputed_review_conservative_and_no_pronoun_count_gate(r):
    a=good();b=good();b['l1_detail_leak']=True;b['level_ok']=False
    x=r.assess({'taxonomy_error':[],'feedback':'Technical sentence without pronoun'},[],[[]],[a,b])
    assert not x['feedback_pass']and x['l1_detail_leak']is True
    x=r.assess({'taxonomy_error':[],'feedback':'Technical sentence without pronoun'},[],[[]],[a])
    assert x['feedback_pass']and x['joint_gold']


def test_bad_role_blocks_joint_even_factual(r):
    a=good();a['addresses_ban']=True
    x=r.assess({'taxonomy_error':[],'feedback':'Bạn làm đúng'},[],[[]],[a])
    assert not x['feedback_pass']and not x['joint_gold']

@pytest.mark.parametrize('mode',['unresolved_stage1','reordered_results'])
def test_score_full_artifacts_handle_failures_and_id_order(r,tmp_path,monkeypatch,mode):
    from scripts import task3_two_pass_findings_report as module
    from src.task3.dataset import write_json
    units=[{'sample_id':sid,'family':'TEST','level':1,'provenance':{'code_sha256':sid}}for sid in ['A','B']]
    gold=[{'sample_id':'A','taxonomy_error':[]},{'sample_id':'B','taxonomy_error':['Lỗi logic']}]
    unresolved=mode=='unresolved_stage1'
    rows=[{'sample_id':x['sample_id'],'status':'unresolved'if unresolved else'resolved','stage1':None,
           'output':None if unresolved else {'taxonomy_error':x['taxonomy_error'],'feedback':'text'}}for x in gold]
    source={'a':{x['sample_id']:{'source_taxonomy':x['taxonomy_error'],'source_disputed':False,'findings':[]}for x in gold}}
    arms={a:{x['sample_id']:x for x in rows}for a in module.ARMS}
    reviews={(u['sample_id'],a,'a'):good()for u in units for a in module.ARMS}
    for a in module.ARMS:write_json(tmp_path/a/'results.private.json',list(reversed(rows)))
    write_json(tmp_path/'A/traces.json',[]);write_json(tmp_path/'gold.private.json',gold)
    for name in ['packet-seal.json','source-seal.json']:write_json(tmp_path/'review'/name,{})
    for who in ['a','b']:write_json(tmp_path/f'review/paired-{who}.private.json',{})
    write_json(tmp_path/'frozen/freeze.json',{});write_json(tmp_path/'selection-seal.json',{})
    write_json(tmp_path/'review/attribution-a.private.json',{'cases':[{'sample_id':u['sample_id'],'findings':[],'detected_reference_indices':[],
          'main_detected':False,'stage2_faithful':False,'inherited_false_claims':0,'new_false_claims':0}for u in units]})
    monkeypatch.setattr(module,'validate_reviews',lambda out:(units,arms,{},reviews,source))
    monkeypatch.setattr(module,'ROOT',tmp_path)
    module.score(tmp_path)
    import json
    summary=json.loads((tmp_path/'metrics.private.json').read_text())
    assert summary['samples']==2
    for a in module.ARMS:
        assert summary['arms'][a]['taxonomy']['exact_count']==(0 if unresolved else 2)
        assert summary['arms'][a]['unresolved']==(2 if unresolved else 0)

@pytest.mark.parametrize('change',[{'detected_reference_indices':[0,0]},{'detected_reference_indices':[9]},{'detected_reference_indices':[True]},
    {'main_detected':1},{'stage2_faithful':1},{'inherited_false_claims':-1},{'new_false_claims':True}])
def test_attribution_validation_rejects_inflated_or_untyped_credit(r,change):
    case={'findings':[],'detected_reference_indices':[0],'main_detected':True,'stage2_faithful':True,'inherited_false_claims':0,'new_false_claims':0}
    case.update(change)
    with pytest.raises(ValueError):r.validate_attribution(case,1,True)


def test_unresolved_stage2_cannot_receive_faithfulness_credit(r):
    case={'findings':[],'detected_reference_indices':[],'main_detected':False,'stage2_faithful':True,'inherited_false_claims':0,'new_false_claims':0}
    with pytest.raises(ValueError):r.validate_attribution(case,0,False)


def test_duplicate_source_reviews_rejected(r):
    with pytest.raises(ValueError):r.unique_cases([{'sample_id':'A'},{'sample_id':'A'}],{'A','B'})
