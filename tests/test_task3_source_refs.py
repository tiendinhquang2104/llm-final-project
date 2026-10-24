import copy
import json
import pytest
from src.task3 import source_refs as refs


def catalog(code='\tint café = 1\r\n  return café\n'):
    return refs.build_catalog(code, provided_compile_log='header\n<stdin>:13: error: expected ;\n',
                              test_report={'cases':[{'output':'x','expected':'y','feedback':'SECRET'}]})


def test_exact_lines_and_numbered_view():
    c=catalog(); d=c['code']
    assert d['line_count']==2
    assert refs.extract(c,{'source':'code','start_line':1,'end_line':2})['text']==d['text']
    assert refs.extract(c,{'source':'code','start_line':2,'end_line':2})['text']=='  return café\n'
    assert refs.numbered(d)=='1 | \tint café = 1\r\n2 |   return café\n'
    assert catalog('')['code']['line_count']==0
    assert catalog('x\n')['code']['line_count']==1
    assert catalog('x')['code']['line_count']==1
    assert 'SECRET' not in c['provided_test_report']['text']
    assert '"output":"x"' in c['provided_test_report']['text']


def test_diagnostic_line_not_embedded_cpp_line():
    c=catalog(); r={'source':'provided_compile_log','start_line':2,'end_line':2}
    assert refs.extract(c,r)['text']=='<stdin>:13: error: expected ;\n'
    with pytest.raises(refs.ReferenceFailure):refs.extract(c,{**r,'start_line':13,'end_line':13})


@pytest.mark.parametrize('change',[
    {'source':'other-sample/code'},{'source':'/tmp/source.cpp'}, {'start_line':0}, {'start_line':-1},
    {'start_line':2,'end_line':1},{'end_line':3}, {'start_line':'1'}, {'end_line':1.0},
    {'start_line':True},{'end_line':False},{'quote':'forged'},
])
def test_invalid_reference_has_structured_field_failure(change):
    r={'source':'code','start_line':1,'end_line':1,**change}
    with pytest.raises(refs.ReferenceFailure) as e:refs.extract(catalog(),r,path='findings[0].evidence_refs[0]')
    assert e.value.details['failure_kind']=='reference_contract'
    assert e.value.details['field_path'].startswith('findings[0].evidence_refs[0]')
    assert e.value.details['allowed_sources']['code']==2
    assert 'parser_position' not in e.value.details


@pytest.mark.parametrize('missing',['source','start_line','end_line'])
def test_missing_reference_key(missing):
    r={'source':'code','start_line':1,'end_line':1};del r[missing]
    with pytest.raises(refs.ReferenceFailure):refs.extract(catalog(),r)


def test_span_does_not_insert_missing_semicolon_and_tamper_is_rejected():
    c=catalog('int f(){ return 1 }');r={'source':'code','start_line':1,'end_line':1}
    spans,evidence=refs.derive(c,[r]); assert spans[0]['text']=='int f(){ return 1 }'
    assert ';' not in evidence
    assert refs.validate_spans(c,[r],spans,evidence) is None
    for key in ['text','document_sha256']:
        broken=copy.deepcopy(spans);broken[0][key]='tampered'
        with pytest.raises(ValueError):refs.validate_spans(c,[r],broken,evidence)
