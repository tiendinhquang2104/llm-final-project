"""Round 12 contracts: artificial code/facts only, independent of real-val wording."""
from copy import deepcopy
from dataclasses import replace
import pytest
from tests.test_task3_dataset import record

BOUND_CODE = 'int main(){int digitsReady=4; for(int k=0;k<ceiling;k++){}}'
FACT = {'finding_id':'TEST-bound','problem_id':None,'proposed_taxonomy_label':'Lỗi biên dịch',
        'source_quote':'for(int k=0;k<ceiling;k++)',
        'error':'Tên ceiling chưa có khai báo.',
        'cause':'Cận lặp sử dụng tên chưa được khai báo trong scope.',
        'permitted_repair_direction':'Dùng digitsReady làm cận vòng lặp.'}

def bound_record(level=3):
    return replace(record('TEST-BOUND'),code=BOUND_CODE,compile_log="fixture.cpp:1:42: error: 'ceiling' was not declared",provenance={'_task3_compile_check':{'status':'compile_error'}},target_feedback_level={1:'Level 1 - Gợi ý nhẹ',2:'Level 2 - Chẩn đoán',3:'Level 3 - Gợi ý sửa'}[level])

def test_structured_renderer_api_exists():
    from src.task3 import renderer
    assert callable(renderer.render_findings)

@pytest.mark.parametrize('text,want',[
 ('Biến ceiling chưa khai báo. Hướng sửa: Khai báo ceiling trước khi sử dụng.', 'generic'),
 ('Biến ceiling chưa khai báo. Hướng sửa: Khai báo ceiling bằng digitsReady trước vòng lặp.', 'specific'),
 ('Biến ceiling chưa khai báo. Hướng sửa:\nDùng digitsReady làm cận vòng lặp.', 'specific'),
 ('Biến ceiling chưa khai báo. Đổi ceiling thành digitsReady ở cận vòng lặp.', 'specific'),
 ('Biến ceiling chưa khai báo. Cần kiểm tra lại biến ceiling.', 'generic'),
 ('Biến ceiling chưa khai báo. Hướng sửa: Khai báo ceiling bằng 1.', 'generic'),
 ('Biến ceiling chưa khai báo. Hướng sửa: Dùng inventedDigits làm cận vòng lặp.', 'generic'),
 ('Lỗi chưa khai báo. Hướng sửa:\n```cpp\nint main(){int ceiling=4;return 0;}\n```', 'complete_solution'),
])
def test_action_relations_distinguish_specific_generic_and_solution(text,want):
    from src.task3.adequacy import assess_repair_action
    assert assess_repair_action(bound_record(),text)['kind']==want


def test_renderer_preserves_facts_and_exact_provenance_without_model_invention():
    from src.task3.renderer import render_findings,validate_rendered
    r=bound_record();doc=render_findings(r,[FACT])
    assert doc['units'][0]['observed_fact']==FACT['error']
    assert doc['units'][0]['cause']==FACT['cause']
    assert doc['units'][0]['location']['line_start']==1
    action=doc['units'][0]['repair_action']
    assert action['target']=='ceiling' and action['reference']=='digitsReady'
    assert action['text']==FACT['permitted_repair_direction']
    assert 'ceiling' in doc['feedback'] and 'digitsReady' in doc['feedback']
    assert validate_rendered(r,[FACT],doc)['finding_coverage']==1
    bad=deepcopy(doc);bad['units'][0]['observed_fact']+=' Hàm main bị thiếu.'
    with pytest.raises(ValueError,match='support'):validate_rendered(r,[FACT],bad)
    bad=deepcopy(doc);bad['feedback']+=' Em đã làm đúng toàn bộ.'
    with pytest.raises(ValueError,match='projection'):validate_rendered(r,[FACT],bad)


def test_level_projection_hides_details_at_level1_and_repairs_at_level2():
    from src.task3.renderer import render_findings
    d1=render_findings(bound_record(1),[FACT]);d2=render_findings(bound_record(2),[FACT])
    assert 'ceiling' not in d1['feedback'] and 'digitsReady' not in d1['feedback']
    assert 'dòng' not in d1['feedback'].lower()
    assert FACT['cause'] in d2['feedback']
    assert 'digitsReady' not in d2['feedback'] and 'Hướng sửa' not in d2['feedback']
    assert d2['units'][0]['repair_action'] is None


def test_literal_parameter_and_nonprogress_loop_coverage():
    from src.task3.renderer import render_findings,validate_rendered
    code='void read(string path){f.open("path");}\nvoid visit(Node* walk){while(walk){touch(walk);}}'
    facts=[dict(FACT,finding_id='TEST-literal',source_quote='f.open("path");',error='Mở literal thay vì giá trị tham số.',cause='Chuỗi tên không dùng tham số path.',proposed_taxonomy_label='Lỗi hard-code'),
           dict(FACT,finding_id='TEST-progress',source_quote='while(walk){touch(walk);}',error='Vòng lặp không tiến.',cause='walk không thay đổi trong thân vòng lặp.',proposed_taxonomy_label='Lỗi vòng lặp')]
    r=replace(bound_record(2),code=code);doc=render_findings(r,facts)
    assert len(doc['units'])==2
    assert validate_rendered(r,facts,doc)['finding_coverage']==1
    assert facts[0]['cause'] in doc['feedback'] and facts[1]['cause'] in doc['feedback']


def test_renderer_refuses_generic_repair_cjk_and_unbound_source():
    from src.task3.renderer import render_findings
    for change,reason in [({'permitted_repair_direction':'Khai báo ceiling.'},'specific'),
                          ({'error':'Lỗi 未声明'},'language'),({'source_quote':'NOT PRESENT'},'source')]:
        with pytest.raises(ValueError,match=reason):render_findings(bound_record(),[dict(FACT,**change)])


def test_renderer_does_not_infer_cleanliness_from_no_findings_or_accept_public():
    from src.task3.renderer import render_findings
    d=render_findings(bound_record(1),[])
    assert d['evidence_status']=='no_approved_finding_not_clean'
    assert 'đúng' not in d['feedback']
    with pytest.raises(ValueError,match='public'):
        render_findings(replace(bound_record(),source='public',split='public',gold_taxonomy=None,gold_feedback=None),[FACT])


def test_renderer_compile_support_uses_error_line_never_warning_alone():
    from src.task3.renderer import render_findings
    code='int main(){int unused; int a=missing;}'
    fact=dict(FACT,source_quote='missing',error='Tên missing chưa được khai báo.',cause='Dùng tên không có khai báo.')
    for diagnostic,want in [('x:1: warning: unused variable unused\nx:1: error: missing was not declared',True),('x:1: warning: missing may be uninitialized',False)]:
        r=replace(bound_record(2),code=code,compile_log=diagnostic,provenance={'_task3_compile_check':{'status':'compile_error' if want else 'compiled','diagnostic':diagnostic}})
        if want:
            d=render_findings(r,[fact]);assert d['units'][0]['compiler_support']['severity']=='error'
        else:
            with pytest.raises(ValueError,match='compiler'):render_findings(r,[fact])

@pytest.mark.parametrize('change',[
    'extra_fact','changed_cause','wrong_problem','wrong_line','wrong_reference','unverified_praise','cjk_fact','cjk_feedback',
])
def test_structured_support_rejects_invented_claims_and_praise(change):
    from src.task3.renderer import render_findings,validate_rendered
    r=bound_record();doc=render_findings(r,[FACT])
    if change=='extra_fact':doc['units'][0]['observed_fact']+=' Hàm main không tồn tại.'
    if change=='changed_cause':doc['units'][0]['cause']='Compiler warning chứng minh bài sai.'
    if change=='wrong_problem':doc['units'][0]['problem_id']='INVENTED'
    if change=='wrong_line':doc['units'][0]['location']['line_start']=999
    if change=='wrong_reference':doc['units'][0]['repair_action']['reference']='k'
    if change=='unverified_praise':doc['feedback']+=' Bài làm hoàn toàn chính xác.'
    if change=='cjk_fact':doc['units'][0]['observed_fact']+=' 未声明'
    if change=='cjk_feedback':doc['feedback']+=' 正确'
    with pytest.raises(ValueError):validate_rendered(r,[FACT],doc)


def test_cjk_source_literal_is_not_cjk_feedback_prose():
    from src.task3.renderer import render_findings
    r=replace(bound_record(2),code='void f(string path){input.open("标签");}')
    fact=dict(FACT,source_quote='input.open("标签");',proposed_taxonomy_label='Lỗi hard-code',
              error='Tên file là một literal.',cause='Không sử dụng tham số path.')
    doc=render_findings(r,[fact])
    assert '标签' in doc['units'][0]['source_quote']
    assert '标签' not in doc['feedback']


def test_specific_repair_does_not_echo_level_metadata_into_feedback():
    from src.task3.renderer import render_findings
    fact=dict(FACT,permitted_repair_direction='Dùng digitsReady làm cận vòng lặp khi Level 3 cho phép.')
    doc=render_findings(bound_record(),[fact])
    assert 'Level' not in doc['feedback']
    assert 'ceiling' in doc['feedback'] and 'digitsReady' in doc['feedback']


def test_quality_v4_accepts_source_relation_and_rejects_generic_without_changing_legacy():
    from src.task3.quality_review import quality_review_flags
    r=bound_record()
    good='Biến ceiling chưa được khai báo. Hướng sửa: Khai báo ceiling bằng digitsReady trước vòng lặp.'
    vague='Biến ceiling chưa được khai báo. Hướng sửa: Khai báo ceiling trước khi sử dụng.'
    assert 'LEVEL3_DIRECTION_REVIEW_CANDIDATE' in quality_review_flags(r,good,version=2)['flags']
    assert 'LEVEL3_DIRECTION_REVIEW_CANDIDATE' not in quality_review_flags(r,good,version=4)['flags']
    assert 'LEVEL3_DIRECTION_REVIEW_CANDIDATE' in quality_review_flags(r,vague,version=4)['flags']


def test_pipeline_v4_repair_relation_is_explicit_opt_in_and_fail_closed():
    from src.task3.pipeline import infer
    from src.task3.inference import Generation,MockTokenizer
    class Backend:
        tokenizer=MockTokenizer()
        def __init__(self,text):self.text=text
        def generate(self,messages,config):return Generation(self.text,40,.01,'eos',True)
    good='Biến ceiling chưa được khai báo. Hướng sửa: Khai báo ceiling bằng digitsReady trước vòng lặp.'
    config={'context_limit':20000,'guard_policy_version':2,'adequacy_retry_policy_version':1,
            'quality_review_policy_version':4,'max_retries':0}
    out,_=infer([bound_record()],Backend(good),config,'gold')
    assert out[0]['output']['feedback']==good
    vague='Biến ceiling chưa được khai báo. Hướng sửa: Khai báo ceiling trước khi sử dụng.'
    with pytest.raises(RuntimeError,match='refusing generic fallback'):
        infer([bound_record()],Backend(vague),config,'gold')


def test_comment_only_reference_does_not_make_an_action_specific():
    from src.task3.adequacy import assess_repair_action
    r=replace(bound_record(),code=BOUND_CODE+' // int phantomCount=5;')
    text='Biến ceiling chưa khai báo. Hướng sửa: Dùng phantomCount làm cận vòng lặp.'
    assert assess_repair_action(r,text)['kind']=='generic'


def test_level2_does_not_render_an_imperative_smuggled_in_cause():
    from src.task3.renderer import render_findings
    with pytest.raises(ValueError,match='Level disclosure'):
        render_findings(bound_record(2),[dict(FACT,cause='Cần thay ceiling bằng digitsReady.')])


def test_specific_action_does_not_validate_an_added_false_diagnosis():
    from src.task3.adequacy import assess_repair_action
    from src.task3.renderer import render_findings,validate_rendered
    r=bound_record()
    text='Hàm main không có trong mã. Hướng sửa: Khai báo ceiling bằng digitsReady trước vòng lặp.'
    action=assess_repair_action(r,text)
    assert action['kind']=='specific'
    assert action['factual_support']=='not_assessed'
    doc=render_findings(r,[FACT]);doc['feedback']=text
    with pytest.raises(ValueError,match='projection'):validate_rendered(r,[FACT],doc)


def test_oracle_cli_refuses_output_outside_ignored_outputs_before_reading_inputs(tmp_path):
    import subprocess,sys
    from pathlib import Path
    repo=Path(__file__).resolve().parents[1]
    out=tmp_path/'forbidden'
    proc=subprocess.run([sys.executable,str(repo/'scripts/task3_render_oracle.py'),
        '--config','ABSENT','--findings','ABSENT','--output-dir',str(out)],capture_output=True,text=True)
    assert proc.returncode==2
    assert 'private oracle artifacts' in proc.stderr
    assert not out.exists()


def test_oracle_cli_preserves_existing_artifacts():
    import subprocess,sys,tempfile
    from pathlib import Path
    repo=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(dir=repo/'outputs') as dirname:
        out=Path(dirname);sentinel=out/'preserve.txt';sentinel.write_text('preserve')
        proc=subprocess.run([sys.executable,str(repo/'scripts/task3_render_oracle.py'),
            '--config','ABSENT','--findings','ABSENT','--output-dir',str(out)],capture_output=True,text=True)
        assert proc.returncode==2
        assert 'already exists' in proc.stderr
        assert sentinel.read_text()=='preserve'

@pytest.mark.parametrize('direction',[
    'Không dùng digitsReady làm cận vòng lặp.',
    'Dùng digitsReady trừ 1 làm cận vòng lặp.',
    'Gán digitsReady bằng ceiling.',
])
def test_approved_action_is_never_reversed_or_arithmetic_simplified(direction):
    from src.task3.adequacy import assess_repair_action
    from src.task3.renderer import render_findings
    assert assess_repair_action(bound_record(),direction)['kind']!='specific'
    with pytest.raises(ValueError,match='specific'):
        render_findings(bound_record(),[dict(FACT,permitted_repair_direction=direction)])


def test_renderer_preserves_approved_repair_qualifiers_instead_of_rewriting_them():
    from src.task3.renderer import render_findings
    direction='Dùng digitsReady làm cận vòng lặp sau khi xác nhận giá trị đếm đã sẵn sàng.'
    doc=render_findings(bound_record(),[dict(FACT,permitted_repair_direction=direction)])
    assert direction in doc['feedback']


def test_positive_repair_explanation_does_not_become_a_negated_action():
    from src.task3.adequacy import assess_repair_action
    text='Biến ceiling chưa được khai báo. Đổi tên biến ceiling thành digitsReady để tránh hiểu lầm.'
    assert assess_repair_action(bound_record(),text)['kind']=='specific'


def test_existing_value_role_descriptor_does_not_depend_on_one_annotation_phrase():
    from src.task3.adequacy import assess_repair_action
    text='Biến ceiling chưa được khai báo. Hướng sửa: Dùng validated-count digitsReady làm cận vòng lặp.'
    assert assess_repair_action(bound_record(),text)['kind']=='specific'
