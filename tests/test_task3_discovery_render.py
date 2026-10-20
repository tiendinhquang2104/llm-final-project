from copy import deepcopy
import pytest
from tests.test_task3_discovery import inp,literal_input
from src.task3.discovery import discover


def test_renderer_needs_verified_cause_not_just_source_quote():
    from src.task3.discovery_render import render
    item=literal_input();fs=discover(item)['findings'];bad=deepcopy(fs)
    bad[0]['cause']='Compiler warning proves algorithm wrong.'
    with pytest.raises(ValueError):render(item,bad,2)


@pytest.mark.parametrize('level',[1,2,3])
def test_level_projection_and_specific_repair(level):
    from src.task3.discovery_render import render
    item=literal_input();out=render(item,discover(item)['findings'],level)
    assert out['status']=='rendered'
    text=out['feedback']
    if level==1:assert 'route' not in text and 'dòng' not in text
    if level==2:assert 'Hướng sửa' not in text and 'Nguyên nhân' in text
    if level==3:assert 'Hướng sửa' in text and 'tham số route' in text and '```' not in text


def test_correct_finding_without_verified_action_cannot_finish_level3():
    from src.task3.discovery_render import render
    item=inp('int main(){return absent;}',status='compile_error',diagnostic='<stdin>:1:19: error: absent not declared')
    out=render(item,discover(item)['findings'],3)
    assert out['status']=='blocked' and out['reason']=='missing_verified_repair'


def test_level4_requires_entire_solution_certificate_not_merely_compilable_patch():
    from src.task3.discovery_render import render
    item=literal_input()
    out=render(item,discover(item)['findings'],4)
    assert out['status']=='blocked' and out['reason']=='no_complete_solution_certificate'
    item=inp('int main(){return 2;}',statement='Program exit status must be 7.')
    out=render(item,discover(item)['findings'],4)
    assert out['status']=='rendered' and 'return 7;' in out['feedback']
    assert out['complete_solution_scope']=='bounded_exit_status'


def test_compilation_never_certifies_complete_solution_and_foreign_claim_cannot_bypass_level4():
    from src.task3.discovery_render import render
    item=inp('int main(){return 2;}',statement='Program exit status must be 7.')
    fs=discover(item)['findings']
    with pytest.raises(ValueError):render(item,[dict(fs[0],cause='Everything else is correct.')],4)
    assert render(inp(),[],4)['status']=='blocked'


def test_unknown_completion_is_explicit_and_partial_never_exportable_submission():
    from src.task3.discovery_render import complete
    item=inp()
    strict=complete(item,2,policy='abstain')
    assert strict['submission'] is None and strict['taxonomy'] is None
    item=literal_input()
    strict=complete(item,2,policy='abstain')
    partial=complete(item,2,policy='supported_partial')
    assert strict['submission'] is None
    assert partial['taxonomy']==['Lỗi hard-code'] and partial['submission'] is None
    assert partial['coverage_complete'] is False and partial['feedback']
    assert complete(inp(),1,policy='supported_partial')['taxonomy'] is None


def test_empty_labels_require_bounded_proof_not_absence_of_findings():
    from src.task3.discovery_render import complete
    item=inp('int main(){return 0;}',statement='Program exit status must be 0.')
    out=complete(item,4,policy='abstain')
    assert out['submission']['taxonomy_error']==[] and out['coverage_complete']
    assert out['submission']['feedback']
    with pytest.raises(ValueError):complete(item,4,policy='fallback_B')


def test_complete_level4_and_literal_patch_compile_as_artificial_cpp11():
    import re
    from src.task3.compiler import check_cpp_syntax
    from src.task3.discovery_render import render
    item=inp('int main(){return 2;}',statement='Program exit status must be 010.')
    output=render(item,discover(item)['findings'],4)
    code=re.search(r'```cpp\n(.*?)\n```',output['feedback'],re.S)[1]
    checked=check_cpp_syntax(code,standard='c++11')
    if checked['status']=='unavailable':pytest.skip('C++ compiler unavailable')
    assert checked['status']=='compiled'
    assert 'return 10;' in code
    item=literal_input();action=discover(item)['findings'][0]['repair_action']
    patched=item.code[:action['span_start']]+action['replacement']+item.code[action['span_end']:]
    assert check_cpp_syntax(patched,standard='c++11')['status']=='compiled'
