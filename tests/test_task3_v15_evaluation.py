import copy
import json
import pytest
from src.task3 import v15_evaluation as ev
from src.task3.dataset import write_json
from src.task3.level_blind import sha


def test_eight_distinct_projected_reviewed_fixtures():
    fixtures=ev.load_fixtures()
    assert len(fixtures)==8 and len({json.dumps(ev.projection(c),sort_keys=True) for c in fixtures})==8
    assert sum(not c['findings'] for c in fixtures)==1
    assert all('source' not in ev.projection(c) for c in fixtures)
    for c in fixtures:
        assert c['source_sha256'] and c['expectations']
        for f in c['findings']:assert set(f)=={'problem_id','kind','location','error','labels','evidence_refs'}


def test_frozen_policy_checks_metrics_and_clean_cases(tmp_path):
    ids=['a','b'];gold=[{'sample_id':'a','taxonomy_error':['Lỗi vòng lặp']},{'sample_id':'b','taxonomy_error':[]}]
    write_json(tmp_path/'gold.json',gold)
    base=[{'sample_id':'a','status':'resolved','output':{'taxonomy_error':['Lỗi vòng lặp'],'feedback':'x'}},
          {'sample_id':'b','status':'resolved','output':{'taxonomy_error':[],'feedback':'x'}}]
    write_json(tmp_path/'D.json',base)
    p=ev.freeze_policy(tmp_path/'gold.json',{'D':tmp_path/'D.json'},ids,expected=2)
    assert p['thresholds']['micro_f1']==1 and p['thresholds']['macro_f1']==.1
    assert p['thresholds']['clean_false_alarms']==0 and p['clean_ids']==['b']
    assert p['numerical_tolerance']==1e-12 and p['baseline_bindings']['D']['sha256']==sha(tmp_path/'D.json')
    changed=copy.deepcopy(base);changed[1]['output']['taxonomy_error']=['Lỗi vòng lặp']
    metrics=ev.comparison(gold,{'D':base,'v15':changed})
    assert metrics['all']['v15']['clean_false_alarms']==1
    assert ev.metric_checks(p,metrics['all']['v15'])=={'micro_f1':False,'macro_f1':False,'clean_false_alarms':False}


def test_output_review_is_bound_to_exact_hash():
    output={'case_id':'x','status':'resolved','feedback':'Một vấn đề.'}
    r=ev.review_binding(output,{'factual_fidelity':True,'location_cause':True,'level2_disclosure':True,'style':True},'agent','automated qualitative review')
    assert ev.validate_review(output,r)
    with pytest.raises(ValueError):ev.validate_review({**output,'feedback':'changed'},r)


def test_internal_reviews_require_explicit_judgments_and_known_kind_checks():
    result={'sample_id':'x','status':'resolved','output':{'feedback':'x'}}
    sparse={**ev.review_binding(result,{},'agent','static review'), 'sample_id':'x'}
    with pytest.raises(ValueError,match='review'):ev.validate_internal_review(result,sparse)
    complete={**ev.review_binding(result,{k:'pass' for k in ev.INTERNAL_DIMENSIONS},'agent','static review',reasons=['Source inspected.']),
              'sample_id':'x','known_failures':[], 'known_kind_checks':{k:False for k in ev.KNOWN_KINDS}}
    assert ev.validate_internal_review(result,complete)
    for key in ev.KNOWN_KINDS:
        missing=copy.deepcopy(complete);del missing['known_kind_checks'][key]
        with pytest.raises(ValueError):ev.validate_internal_review(result,missing)
    missing=copy.deepcopy(complete);missing['known_kind_checks']['false_initialization']=False;missing['known_failures']=['false_initialization']
    with pytest.raises(ValueError):ev.validate_internal_review(result,missing)


def test_renderer_review_rejects_duplicate_or_missing_frozen_cases(tmp_path):
    rows=[];reviews=[]
    for version in ('v14','v15'):
        for c in ev.load_fixtures():
            row=dict(prompt_version=version,case_id=c['case_id'],status='resolved',feedback='Một chẩn đoán.',failure=None)
            rows.append(row);reviews.append(dict(prompt_version=version,case_id=c['case_id'],**ev.review_binding(row,
                {k:True for k in ('factual_fidelity','location_cause','level2_disclosure','empty_findings','style')},'agent','static review',['supported'])))
    write_json(tmp_path/'renderer-eval/outputs.private.json',rows);write_json(tmp_path/'renderer-eval/reviews.private.json',reviews)
    assert ev.renderer_reviews(tmp_path)['new_prompt_all_eight_pass']
    rows[-1]=copy.deepcopy(rows[-2]);write_json(tmp_path/'renderer-eval/outputs.private.json',rows)
    with pytest.raises(ValueError,match='unique|exact'):ev.renderer_reviews(tmp_path)
