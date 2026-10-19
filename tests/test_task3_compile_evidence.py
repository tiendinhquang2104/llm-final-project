import os
from pathlib import Path

from src.task3.compiler import check_cpp_syntax


def test_syntax_check_reports_real_compiler_diagnostic_and_bounds_execution(tmp_path):
    compiler = tmp_path / 'fake-c++'
    compiler.write_text('#!/bin/sh\necho "stdin.cpp:1: error: undeclared cnt" >&2\nexit 1\n')
    compiler.chmod(0o700)
    result = check_cpp_syntax('int main(){ return cnt; }', compiler=str(compiler), timeout_s=1)
    assert result['status'] == 'compile_error'
    assert 'undeclared cnt' in result['diagnostic']
    assert result['command'][-1] == '-'


def test_syntax_check_distinguishes_clean_code_from_unavailable_and_timeout(tmp_path):
    clean = tmp_path / 'clean-c++'
    clean.write_text('#!/bin/sh\ncat >/dev/null\nexit 0\n')
    clean.chmod(0o700)
    assert check_cpp_syntax('int main() {}', compiler=str(clean))['status'] == 'compiled'
    assert check_cpp_syntax('int main() {}', compiler='/missing/compiler')['status'] == 'unavailable'
    slow = tmp_path / 'slow-c++'
    slow.write_text('#!/bin/sh\nsleep 2\n')
    slow.chmod(0o700)
    assert check_cpp_syntax('int main() {}', compiler=str(slow), timeout_s=0.05)['status'] == 'timeout'


def test_syntax_check_can_target_cpp11_and_keeps_first_diagnostic(tmp_path):
    compiler = tmp_path / 'diagnostics-c++'
    compiler.write_text('#!/bin/sh\nprintf "first diagnostic\\nsecond diagnostic\\n" >&2\nexit 1\n')
    compiler.chmod(0o700)
    result = check_cpp_syntax('int main() {}', compiler=str(compiler), standard='c++11')
    assert '-std=c++11' in result['command']
    assert result['diagnostic'].startswith('first diagnostic')
