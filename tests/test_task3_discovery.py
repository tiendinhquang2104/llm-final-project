"""Artificial training contracts; no student submissions or evaluation IDs."""
import inspect
from dataclasses import replace
import pytest
from src.synth.taxonomy import LABEL_SPACE


def inp(code='int main(){return 0;}', statement='Return zero.', problems=(), status='compiled', diagnostic=''):
    from src.task3.discovery import DiscoveryInput
    return DiscoveryInput(code=code, statement=statement, problems=tuple(problems),
                          compiler_status=status, compiler_diagnostic=diagnostic)


def test_input_boundary_has_no_gold_or_teacher_fields():
    from src.task3.discovery import DiscoveryInput, discover
    assert set(inspect.signature(DiscoveryInput).parameters)=={'code','statement','problems','compiler_status','compiler_diagnostic'}
    assert set(inspect.signature(discover).parameters)=={'item'}
    with pytest.raises(TypeError): DiscoveryInput(code='',statement='',gold_taxonomy=[])


def test_compiled_and_warning_only_are_unknown_never_clean():
    from src.task3.discovery import discover
    for status,diag in [('compiled',''),('compiled','<stdin>:1:12: warning: unused variable')]:
        result=discover(inp(status=status,diagnostic=diag))
        assert result['status']=='unknown' and result['findings']==[]
        assert result['taxonomy'] is None and result['coverage_complete'] is False


def test_error_and_warning_keep_separate_severity_and_source_binding():
    from src.task3.discovery import discover,validate_finding
    item=inp('int main(){return absent;}', status='compile_error', diagnostic='<stdin>:1:5: warning: unused variable\n<stdin>:1:19: error: absent was not declared in this scope')
    result=discover(item)
    assert len(result['findings'])==1
    f=result['findings'][0]
    assert f['status']=='supported_error' and f['taxonomy_group']==LABEL_SPACE[0]
    assert f['evidence']['diagnostics']==['<stdin>:1:19: error: absent was not declared in this scope']
    assert validate_finding(item,f)
    assert result['coverage_complete'] is False


def literal_input():
    return inp('#include <fstream>\n#include <string>\nvoid load(std::string route){std::ifstream stream("route");}',
               'Read the file whose path is parameter route.', [{'pid':'Q1','prototype':'void load(std::string route);'}])


def test_literal_verification_requires_statement_and_parameter_relation():
    from src.task3.discovery import discover,validate_finding
    item=literal_input(); r=discover(item)
    assert len(r['findings'])==1
    f=r['findings'][0]
    assert f['problem_id']=='Q1' and f['taxonomy_group']=='Lỗi hard-code'
    assert f['repair_action']['target']=='"route"' and f['repair_action']['reference']=='route'
    assert validate_finding(item,f)
    for changed in [replace(item,statement='Read a fixed resource.'),replace(item,code=item.code.replace('std::string route','std::string other'))]:
        out=discover(changed)
        assert not out['findings'] and out['rejected_candidates']


def test_quote_does_not_verify_fabricated_cause_or_modified_evidence():
    from src.task3.discovery import discover,validate_finding
    item=literal_input(); f=discover(item)['findings'][0]
    with pytest.raises(ValueError):validate_finding(item,dict(f,cause='Hàm main bị thiếu.'))
    with pytest.raises(ValueError):validate_finding(item,dict(f,taxonomy_group='Lỗi thuật toán'))
    with pytest.raises(ValueError):validate_finding(item,dict(f,evidence={'rule':'trusted_quote'}))


@pytest.mark.parametrize('body,supported', [('total++;',True),('cursor--;',False),('touch(cursor);',False),('break;',False),('return;',False)])
def test_nonprogress_requires_restricted_invariant_body(body,supported):
    from src.task3.discovery import discover
    item=inp('void scan(int cursor){unsigned total=0; while(cursor){'+body+'}}',statement='scan must terminate for any cursor.')
    out=discover(item)
    assert bool(out['findings']) is supported
    if supported:
        assert out['findings'][0]['taxonomy_group']=='Lỗi vòng lặp'
        assert 'nếu' in out['findings'][0]['cause'].lower()
    else:assert out['rejected_candidates']


def test_comment_literal_and_preprocessor_do_not_manufacture_semantics():
    from src.task3.discovery import discover
    for code in ['// while(cursor){total++;}\nint main(){return 0;}',
                 'const char* msg="while(cursor){total++;}";',
                 '#define total cursor\nvoid f(int cursor){int total=0;while(cursor){total++;}}']:
        assert discover(inp(code))['findings']==[]


def test_invalid_compiler_locations_and_external_header_are_not_source_findings():
    from src.task3.discovery import discover
    for diag in ['/usr/include/a.h:1:2: error: failure','<stdin>:90:2: error: failure','<stdin>:1:2: warning: failure']:
        out=discover(inp(status='compile_error',diagnostic=diag))
        assert not out['findings'] and out['status']=='unknown'


def test_all_official_groups_are_in_schema_not_claimed_supported():
    from src.task3.discovery import SUPPORTED_GROUPS
    assert set(SUPPORTED_GROUPS) < set(LABEL_SPACE)


def test_octal_literal_cannot_create_decimal_complete_or_clean_certificate():
    from src.task3.discovery import discover
    out=discover(inp('int main(){return 010;}',statement='Program exit status must be 10.'))
    assert out['certificate'] is None and out['taxonomy'] is None


def test_raw_string_call_is_data_and_negated_or_conflicting_statement_is_not_entailment():
    from src.task3.discovery import discover
    item=literal_input()
    fake='#include <string>\nvoid load(std::string route){auto text=R"tag(std::ifstream stream("route"))tag";}'
    assert not discover(replace(item,code=fake))['findings']
    for statement in ['Do not '+item.statement,'Ignore this example: '+item.statement,item.statement+' Actually always open a fixed file.']:
        out=discover(replace(item,statement=statement))
        assert not out['findings'] and out['rejected_candidates']


def test_open_method_name_is_not_evidence_of_file_io():
    from src.task3.discovery import discover
    item=literal_input()
    code='#include <fstream>\n#include <string>\nstruct Note { void open(const char*) {} }; Note note;\nvoid load(std::string route){note.open("route"); std::ifstream stream(route);}'
    out=discover(replace(item,code=code))
    assert not out['findings'] and out['rejected_candidates']


def test_proven_ifstream_receiver_can_open_literal():
    from src.task3.discovery import discover
    item=literal_input()
    code='#include <fstream>\n#include <string>\nvoid load(std::string route){std::ifstream stream;stream.open("route");}'
    assert discover(replace(item,code=code))['findings']


def test_loop_invariant_is_not_error_when_valid_input_cannot_enter_loop():
    from src.task3.discovery import discover
    code='void scan(int cursor){unsigned total=0;while(cursor){total++;}}'
    out=discover(inp(code,statement='cursor is always 0; scan must return immediately.'))
    assert not out['findings'] and out['rejected_candidates']


def test_spec_decimal_is_rendered_as_canonical_cpp_decimal_and_loop_cause_is_qualified():
    from src.task3.discovery import discover
    item=inp('int main(){return 2;}',statement='Program exit status must be 010.')
    f=discover(item)['findings'][0]
    assert f['repair_action']['replacement']=='10'
    code='void scan(int cursor){unsigned total=0;while(cursor){total++;}}'
    f=discover(inp(code,statement='scan must terminate for any cursor.'))['findings'][0]
    assert 'không kết thúc' not in f['cause']
    assert 'C++11' in f['cause'] and 'không bảo đảm' in f['cause']


def test_nested_std_namespace_cannot_certify_standard_stream_identity():
    from src.task3.discovery import discover
    item=literal_input()
    code='namespace app { namespace std { struct string {}; struct ifstream { ifstream(const char*) {} }; } void load(std::string route){std::ifstream stream("route");} }'
    out=discover(replace(item,code=code))
    assert not out['findings'] and out['rejected_candidates']


def test_line_directive_prevents_forged_physical_diagnostic_span():
    from src.task3.discovery import discover
    code='#line 1 "<stdin>"\nint main(){return missing;}'
    out=discover(inp(code,status='compile_error',diagnostic='<stdin>:1:19: error: missing not declared'))
    assert not out['findings'] and out['rejected_candidates']
