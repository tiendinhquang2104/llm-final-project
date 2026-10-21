"""Artificial TRAIN-only fixtures: never open experiment/evaluation source."""
import json
import pytest
from scripts.task3_contract_v1_replay import parse_fenced_object, replay, summarize, taxonomy_match

LABEL = 'Lỗi logic'
CODE = 'int helper(){ return 7; }\nint main(){\n int i=0;\n while(i<3){}\n}\n'

def raw(quote='while(i<3){}', location=None, **changes):
    value = dict(status='defective', taxonomy_error=[LABEL], findings=[dict(label=LABEL, quote=quote, location=location or {'function':'main','line':4}, cause_vi='Biến điều khiển không cập nhật.')])
    value.update(changes)
    return '```json\n'+json.dumps(value,ensure_ascii=False)+'\n```'

@pytest.mark.parametrize('text', ['{}', 'hello\n```json\n{}\n```', '```json\n{}\n```\nafter', '```json\n{}\n```\n```json\n{}\n```', '```json\n{} {}\n```', '```json\n[]\n```', '```python\n{}\n```', '```json\n{}', '```json\n{"x":1,"x":2}\n```', '```json\n{"x":NaN}\n```'])
def test_reject_wrappers_and_non_objects(text):
    with pytest.raises(ValueError): parse_fenced_object(text)

def test_exact_fence_accepts_whitespace():
    assert parse_fenced_object(' \n```json\n{"a":1}\n```\n ') == {'a':1}

def test_multiline_json_string_fence_text_is_data():
    assert parse_fenced_object('```json\n{"x":"``` is data"}\n```')['x']=='``` is data'

def test_all_stages_and_original_location_retained():
    row=replay(raw(),CODE)
    assert all(row['passed'].values())
    assert row['diagnosis']['findings'][0]['location']=={'function':'main','line':4}
    assert row['reachability']=='unverified'
    assert row['semantic_correctness']=='unverified'

def test_wrong_line_not_repaired():
    row=replay(raw(location={'line':3}),CODE)
    assert row['first_reject_reason']=='location:line_mismatch'
    assert row['diagnosis']['findings'][0]['location']=={'line':3}
    assert row['quote_facts'][0]['occurrences'][0]['line_start']==4

def test_wrong_function():
    row=replay(raw(location={'function':'helper','line':4}),CODE)
    assert row['first_reject_reason']=='location:function_mismatch'

def test_unknown_function_scope_is_unverified():
    row=replay(raw(quote='int i;',location={'function':'main','line':1}),'int i;')
    assert row['passed']['location']
    assert row['location_verification']=='unverified'

def test_multiple_occurrences_require_joint_line_function_match():
    code='int helper(){return 7;}\nint main(){return 7;}\n'
    assert replay(raw(quote='return 7;',location={'function':'main','line':2}),code)['passed']['location']
    assert replay(raw(quote='return 7;',location={'function':'main','line':1}),code)['first_reject_reason']=='location:inconsistent_claims'

def test_string_line_claim_and_cause_claim():
    assert replay(raw(location='main, dòng 4'),CODE)['passed']['location']
    assert replay(raw(location='main, dòng 2'),CODE)['first_reject_reason']=='location:line_mismatch'
    value=parse_fenced_object(raw());value['findings'][0]['cause_vi']='Lỗi tại dòng 2.'
    assert replay('```json\n'+json.dumps(value)+'\n```',CODE)['first_reject_reason']=='location:line_mismatch'

def test_range_end_claim():
    code='int main(){\nwhile(1){\n}\n}\n'
    assert replay(raw(quote='while(1){\n}',location={'start_line':2,'end_line':3}),code)['passed']['location']
    assert replay(raw(quote='while(1){\n}',location={'start_line':2,'end_line':4}),code)['first_reject_reason']=='location:line_mismatch'

@pytest.mark.parametrize('location',[{'line':True},{'line':0},{'line':'4'},{'unknown':4},{'function':3},{},42])
def test_invalid_location_claim_shape(location):
    text=raw();value=parse_fenced_object(text);value['findings'][0]['location']=location
    assert not replay('```json\n'+json.dumps(value)+'\n```',CODE)['passed']['shape']

def test_empty_stdout_no_evidence_required():
    assert replay(raw(quote='int main(){}',location={'line':1}),'int main(){}')['passed']['location']

def test_comment_reject_but_literal_and_uncalled_helper_not_proof():
    assert replay(raw(quote='broken();',location={'line':1}),'// broken();\nint main(){}')['first_reject_reason']=='quote:comment_only'
    literal=replay(raw(quote='fixed.csv',location={'line':1}),'int main(){open("fixed.csv");}')
    assert literal['passed']['quote'] and literal['reachability']=='unverified'
    helper=replay(raw(quote='return 7;',location={'function':'helper','line':1}),CODE)
    assert helper['passed']['location'] and helper['reachability']=='unverified'

def test_unknown_preprocessor_never_claims_active_proof():
    row=replay(raw(quote='bad();',location={'line':2}),'#if 0\nbad();\n#endif')
    assert row['passed']['quote'] and row['reachability']=='unverified'

@pytest.mark.parametrize('changes',[dict(status='unknown'),dict(taxonomy_error=['made up']),dict(taxonomy_error=[]),dict(status='clean'),dict(taxonomy_error=[LABEL,LABEL])])
def test_labels_status_reject(changes):
    assert not replay(raw(**changes),CODE)['passed']['labels_status']

def test_uncertain_empty_vacuous_quote_not_clean():
    row=replay(raw(status='uncertain',taxonomy_error=[],findings=[]),CODE)
    assert all(row['passed'].values()) and row['quote_bearing'] is False
    assert row['diagnosis']['status']=='uncertain'

def test_quote_missing_and_first_rejection():
    row=replay(raw(quote='absent',location={'line':99}),CODE)
    assert row['first_reject_reason']=='quote:not_found'
    assert row['passed']['location'] is False

def test_summary_cumulative_denominators():
    summary=summarize([replay(raw(),CODE),replay('{}',CODE),replay(raw(location={'line':2}),CODE)])
    assert summary['cumulative_pass']==dict(parse=2,shape=2,labels_status=2,quote=2,location=1)
    assert sum(summary['first_reject_reasons'].values())==2

def test_unresolved_reference_is_not_empty_clean():
    assert taxonomy_match([],None) is None
    assert taxonomy_match([],[]) is True

def test_numeric_string_is_original_line_claim_not_unverified():
    assert replay(raw(location='4'),CODE)['passed']['location']
    assert replay(raw(location='3'),CODE)['first_reject_reason']=='location:line_mismatch'

def test_numeric_range_is_original_start_and_end_not_repaired():
    code='int main(){\nwhile(1){\n}\n}\n'
    assert replay(raw(quote='while(1){\n}',location='2-3'),code)['passed']['location']
    assert replay(raw(quote='while(1){\n}',location='1-4'),code)['first_reject_reason']=='location:line_mismatch'

def test_cause_function_claim_conflicting_with_location():
    value=parse_fenced_object(raw());value['findings'][0]['cause_vi']='Lỗi trong hàm helper.'
    row=replay('```json\n'+json.dumps(value)+'\n```',CODE)
    assert row['first_reject_reason']=='location:function_mismatch'

def test_repeated_quote_comment_at_claimed_line_not_code_proof():
    code='// return 7;\nint main(){return 7;}\n'
    row=replay(raw(quote='return 7;',location={'line':1}),code)
    assert row['first_reject_reason']=='location:comment_only_at_claimed_location'

def test_negated_function_prose_not_invented_name():
    value=parse_fenced_object(raw());value['findings'][0]['cause_vi']='Hàm không cập nhật biến.'
    assert replay('```json\n'+json.dumps(value)+'\n```',CODE)['passed']['location']

def test_unknown_explicit_function_call_in_location_is_not_ignored():
    assert replay(raw(location='not_main(), dòng 4'),CODE)['first_reject_reason']=='location:function_mismatch'

def test_location_failure_is_reached_and_mismatch():
    assert replay(raw(location={'line':2}),CODE)['location_verification']=='mismatch'

def test_loader_preserves_parse_and_shape_failures(tmp_path, monkeypatch):
    import scripts.task3_contract_v1_replay as module
    frozen=tmp_path/'frozen'; frozen.mkdir()
    inference=tmp_path/'inference/arm-SHORT';inference.mkdir(parents=True)
    inputs=[]; refs=[]; selected=[]; generations=[]
    for i in range(30):
        sid=f'ARTIFICIAL-{i:03d}';rid=sid+'@L1';code='int main(){}'
        inputs.append(dict(sample_id=sid,request_id=rid,requested_level=1,task=dict(code=code)))
        refs.append(dict(sample_id=sid,code=code,source_sha256=module.sha_bytes(code.encode()),taxonomy_annotation=[],source_reference=None))
        selected.append(dict(sample_id=sid,level='L1'))
        text='{}' if i%2 else '```json\n{}\n```'
        generations.append(dict(request_id=rid,stage='diagnosis',raw_text=text,raw_sha256=module.sha_bytes(text.encode())))
    for name,data in [('inputs.private.json',inputs),('reference.private.json',dict(records=refs)),('selection.private.json',dict(selected=selected))]:
        (frozen/name).write_text(json.dumps(data))
    (frozen/'seal.json').write_text(json.dumps(dict(files_sha256={p.name:module.sha(p) for p in frozen.iterdir()})))
    (inference/'generations.jsonl').write_text('\n'.join(json.dumps(r) for r in generations))
    monkeypatch.setattr(module,'ORIGINAL',tmp_path)
    rows=module.load_original()
    assert module.summarize(rows)['cumulative_pass']==dict(parse=15,shape=0,labels_status=0,quote=0,location=0)
    assert all(row['raw_taxonomy_source_match'] is None for row in rows)

def test_generic_vietnamese_helper_noun_is_unverified_not_function_mismatch():
    value=parse_fenced_object(raw());value['findings'][0]['cause_vi']='Hàm con không cập nhật biến.'
    row=replay('```json\n'+json.dumps(value)+'\n```',CODE)
    assert row['passed']['location'] and row['location_verification']=='unverified'

def test_control_condition_is_not_function_name():
    assert replay(raw(location='while(i<3), dòng 4'),CODE)['passed']['location']

def review_fixture():
    case=dict(sample_id='ARTIFICIAL',request_id='fixture@L1',source_sha256='s',raw_sha256='r',requested_level=1,passed={s:True for s in ['parse','shape','labels_status','quote','location']},raw_taxonomy_annotation_match=False,raw_taxonomy_source_match=None,diagnosis=parse_fenced_object(raw()))
    ref=dict(sample_id='ARTIFICIAL',defect_status='defect',taxonomy_annotation=[],source_reference=None)
    row=dict(sample_id='ARTIFICIAL',request_id='fixture@L1',source_sha256='s',raw_sha256='r',reviewer='agent static',human_verified=False,taxonomy_annotation_match=False,taxonomy_source_review_match=None,status_correct=True,raw_status='defective',main_mechanism='wrong',quote_active=True,location_correct=True,fabricated_data_or_arithmetic=False,main_error_omitted=True,correct_mechanism_wrong_coordinate_or_format=False,false_positive_on_scoped_clean=False)
    return case,ref,row

def test_review_binding_null_and_summary():
    from scripts.task3_contract_v1_replay import combine_reviews,semantic_summary
    case,ref,row=review_fixture()
    merged=combine_reviews([row],[case],[ref])
    assert merged[0]['source_reference_unresolved']
    assert semantic_summary(merged)['taxonomy_source_exact']==dict(true=0,false=0,null=1)

@pytest.mark.parametrize('mutation',[{'raw_sha256':'other'},{'request_id':'other'},{'human_verified':True},{'taxonomy_source_review_match':True}])
def test_review_rejects_stale_or_forced_reference(mutation):
    from scripts.task3_contract_v1_replay import combine_reviews
    case,ref,row=review_fixture();row.update(mutation)
    with pytest.raises(ValueError): combine_reviews([row],[case],[ref])

def test_adjudication_keeps_original_verdict_and_explicit_rationale():
    from scripts.task3_contract_v1_replay import combine_reviews
    case,ref,row=review_fixture()
    change=dict(sample_id='ARTIFICIAL',changes=dict(main_mechanism='partial'),rationale='Manual static boundary judgment.')
    merged=combine_reviews([row],[case],[ref],[change])
    assert merged[0]['adjudication']['before']['main_mechanism']=='wrong'
    assert row['main_mechanism']=='wrong'
