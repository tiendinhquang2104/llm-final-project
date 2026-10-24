import copy
import json
from unittest.mock import patch
import pytest
from src.task3.compiler import check_cpp_syntax, MAX_SOURCE_CHARS, MAX_DIAGNOSTIC_CHARS
from src.task3 import compiler_evidence as ce
from tests.test_task3_arm_d_plus import unit


def test_real_compiler_accepts_function_only_and_rejects_missing_semicolon():
    good='int f(){ return 1; }\n';bad='int f(){ return 1 }\n'
    assert check_cpp_syntax(good,standard='c++11',full_diagnostics=True)['status']=='compiled'
    r=check_cpp_syntax(bad,standard='c++11',full_diagnostics=True)
    assert r['status']=='compile_error' and r['returncode']!=0
    assert r['stderr_full'] and '-std=c++11' in r['command']
    assert r['capture_complete'] is True and r['diagnostic_truncated'] is False


def test_warnings_not_errors_and_full_capture_compatible(tmp_path):
    p=tmp_path/'compiler';p.write_text('#!/bin/sh\nprintf "warning: issue\\n" >&2\nexit 0\n');p.chmod(0o700)
    r=check_cpp_syntax('int f(){}',compiler=str(p),standard='c++11',full_diagnostics=True)
    assert r['status']=='compiled' and 'warning' in r['diagnostic']
    p.write_text('#!/bin/sh\nhead -c 12000 /dev/zero | tr "\\000" x >&2\nexit 1\n')
    r=check_cpp_syntax('',compiler=str(p))
    assert len(r['diagnostic'])==MAX_DIAGNOSTIC_CHARS and r['diagnostic_truncated'] is True
    assert len(r['stderr_full'])==12000
    assert len(check_cpp_syntax('',compiler=str(p),full_diagnostics=True)['diagnostic'])==12000


def test_distinct_failure_states(tmp_path):
    assert check_cpp_syntax('x'*(MAX_SOURCE_CHARS+1))['status']=='source_too_large'
    assert check_cpp_syntax('',compiler='/missing/compiler')['status']=='unavailable'
    p=tmp_path/'slow';p.write_text('#!/bin/sh\nsleep 1\n');p.chmod(0o700)
    assert check_cpp_syntax('',compiler=str(p),timeout_s=.01)['status']=='timeout'


def test_enrichment_cache_preserves_inputs_and_stable_identity(tmp_path):
    u=unit();u['task']['compile_log']='original log';original=copy.deepcopy(u)
    second=copy.deepcopy(u);second['sample_id']='repeated'; second['level']=3
    enriched,audit=ce.prepare([u,second],tmp_path)
    assert u==original
    assert enriched[0]['task']['compile_log']=='original log'
    assert enriched[0]['local_compiler']['standard']=='c++11'
    assert enriched[0]['local_compiler']['program_executed'] is False
    assert audit['cache_hits']==1 and audit['compiler_calls']==1
    assert audit['samples'][1]['cache_hit'] is True
    resumed,_=ce.prepare([u,second],tmp_path)
    assert resumed==enriched
    assert enriched[0]['local_compiler']['source_sha256']==ce.source_sha(u['task']['code'])


def test_key_binds_all_compiler_options():
    tool={'executable':'/a','version':'v','environment':{'CPATH':'a'}}
    base=ce.cache_identity('x','c++11',tool,5)
    assert all(ce.cache_identity(code,std,t,timeout)!=base for code,std,t,timeout in [
        ('y','c++11',tool,5),('x','c++17',tool,5),('x','c++11',{**tool,'version':'v2'},5),
        ('x','c++11',{**tool,'executable':'/b'},5),('x','c++11',{**tool,'environment':{}},5),('x','c++11',tool,4)])


def test_standard_resolution_and_conflicts():
    u=unit();assert ce.resolve_standard(u)=='c++11'
    u['task']['exam_metadata']={'cpp_standard':'c++17'};assert ce.resolve_standard(u)=='c++17'
    u['task']['input_metadata']={'standard':'c++11'}
    with pytest.raises(ValueError,match='conflicting'):ce.resolve_standard(u)
    u['task']['input_metadata']={'standard':'c++20'}
    with pytest.raises(ValueError,match='unsupported'):ce.resolve_standard(u)


def test_unavailable_prerequisite_fails_before_model(tmp_path):
    with patch.object(ce,'toolchain',return_value=None):
        with pytest.raises(ValueError,match='compiler prerequisite'):ce.prepare([unit()],tmp_path)


def test_timeout_preserves_both_partial_streams():
    import subprocess
    error=subprocess.TimeoutExpired(['compiler'],.1,output=b'partial stdout\n',stderr=b'partial stderr\n')
    with patch('src.task3.compiler.subprocess.run',side_effect=error):
        r=check_cpp_syntax('x',compiler='/compiler',timeout_s=.1,full_diagnostics=True)
    assert r['stdout_full']=='partial stdout\n' and r['stderr_full']=='partial stderr\n'
    assert r['capture_complete'] is False
