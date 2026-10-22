import json
from src.task3.round23_audit import normalize_old_attempt, independent_flags


def test_old_normalization_fills_only_stdin_files_and_source_whitespace():
    raw={'status':'defect','quote':'cout << 0;','input':{'stdin':'2'},'taxonomy_error':['Lỗi logic']}
    changed,edits=normalize_old_attempt(json.dumps(raw),'cout<<0;',stdin_only=True)
    assert changed['quote']=='cout<<0;' and changed['input']['files']=={}
    assert set(edits)=={'source_whitespace','stdin_empty_files'}
    assert 'predicted_expected'not in changed
    changed,_=normalize_old_attempt(json.dumps(raw),'cout<<0;',stdin_only=False)
    assert 'files'not in changed['input']


def test_categories_overlap_and_do_not_select_best_attempt():
    s={'input_valid':True,'actual_correct':False,'expected_correct':False,'distinguishes':False}
    flags=independent_flags(s,'mutant')
    assert flags['valid_but_nondistinguishing'] and flags['actual_wrong'] and flags['expected_wrong']
    assert independent_flags({'input_valid':False,'actual_correct':None,'expected_correct':None,'distinguishes':False},'base')['out_of_domain']
    missing=independent_flags({'input_valid':False,'actual_correct':None,'expected_correct':None,'distinguishes':False,'reason':'missing_or_uncertain_prediction'},'mutant')
    assert missing['input_unavailable'] and not missing['out_of_domain']


def test_mechanical_old_view_preserves_literal_thinking_text():
    raw={'input':{'stdin':'2'},'predicted_actual':'<think>literal</think>0'}
    normalized,_=normalize_old_attempt(json.dumps(raw),'cout<<0;',stdin_only=True)
    assert normalized['predicted_actual']==raw['predicted_actual']
