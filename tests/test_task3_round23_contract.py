import json
import pytest
from src.task3.round23_contract import parse_diagnosis, source_spans, pack_input, validate_input


def scope(kind='scalar',**kw):return {'kind':kind,'lo':0,'hi':10,**kw}
def answer(**kw):return dict(status='defect',span='cout << 0;',input='2',actual='0',expected='2',mechanism='Prints a constant.',taxonomy_error=['Lỗi logic'],**kw)


def test_source_whitespace_preserves_literals_and_operators():
    assert source_spans('int main(){cout<<0;}','cout << 0;')
    assert not source_spans('cout<<"a b";','cout << "ab";')
    assert not source_spans('a + + b','a++b')


def test_stdin_and_csv_machine_fields_from_one_scope():
    assert pack_input(scope(),'2')=={'stdin':'2','files':{}}
    s=scope('csv',filename='cnt.csv',rows_max=6,value_lo=-9,value_hi=9)
    assert pack_input(s,'1,2\n')=={'stdin':'','files':{'cnt.csv':'1,2\n'}}
    assert validate_input(s,'1,2\n') is None
    assert validate_input(s,'1,2\r\n3,4\r\n') is None
    for text in ['1 2','1,20','١,2','1,2\x1c','1,2\r3,4','1,2\v3,4','1,2\n\n']:
        with pytest.raises(ValueError):validate_input(s,text)


def test_only_deterministic_normalization_and_official_taxonomy():
    p=parse_diagnosis('```json\n'+json.dumps(answer())+'\n```','int main(){cout<<0;}',scope())
    assert p['input']=={'stdin':'2','files':{}} and p['span_matches']
    bad=answer();bad['taxonomy_error']=['logic']
    with pytest.raises(ValueError):parse_diagnosis(json.dumps(bad),'cout<<0;',scope())
    bad=answer();del bad['expected']
    with pytest.raises(ValueError):parse_diagnosis(json.dumps(bad),'cout<<0;',scope())


def test_continuation_input_cannot_change_observed_input():
    raw=answer();raw['input']='3'
    with pytest.raises(ValueError):parse_diagnosis(json.dumps(raw),'cout<<0;',scope(),fixed_input='2')
    del raw['input']
    p=parse_diagnosis(json.dumps(raw),'cout<<0;',scope(),fixed_input='2')
    assert p['input_text']=='2'


def test_uncertain_remains_uncertain_and_never_becomes_clean():
    p=parse_diagnosis('{"status":"uncertain","taxonomy_error":[]}', 'cout<<0;',scope())
    assert p['status']=='uncertain'
    raw=answer();raw['status']='no_defect_in_scope'
    with pytest.raises(ValueError):parse_diagnosis(json.dumps(raw),'cout<<0;',scope())


def test_array_unique_scope_is_an_input_constraint_not_an_oracle():
    s={'kind':'array','min_items':2,'max_items':6,'value_lo':-9,'value_hi':9,'unique':True}
    assert validate_input(s,'2 1 2') is None
    with pytest.raises(ValueError):validate_input(s,'2 1 1')


def test_duplicate_semantic_keys_are_rejected_not_resolved_by_last_value():
    raw=json.dumps(answer()).replace('"actual": "0"','"actual": "2", "actual": "0"')
    with pytest.raises(ValueError):parse_diagnosis(raw,'cout<<0;',scope())


def test_outer_thinking_is_serialization_but_think_tags_in_literals_are_data():
    value=answer();value.update(span='cout<<"<think>literal</think>";',actual='<think>literal</think>')
    parsed=parse_diagnosis('<think>outside</think>'+json.dumps(value),'cout<<"<think>literal</think>";',scope())
    assert parsed['actual']=='<think>literal</think>'


def test_literal_suffix_is_not_equivalent_to_separate_identifier():
    assert not source_spans('cout<<"x" _suffix;','cout<<"x"_suffix;')
