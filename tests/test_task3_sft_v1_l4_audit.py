"""Bounded audit policy tests; no compiler, root jail, model, or GPU needed."""
import importlib
import json
from pathlib import Path

import pytest


def audit_module():
    return importlib.import_module('scripts.task3_sft_v1_l4_audit')


@pytest.mark.parametrize('language', ['cpp', 'c++', 'cxx', '', 'CPP'])
def test_extract_preserves_code_bytes_inside_one_supported_fence(language):
    result = audit_module().extract_cpp('Giải thích.\r\n```' + language + '\r\n  int f() { return 1; }\r\n\r\n```\r\n')
    assert result == dict(status='extracted', code='  int f() { return 1; }\r\n\r\n', reason=None)


@pytest.mark.parametrize('feedback', [
    'int main() {}',
    '```python\nprint(1)\n```',
    '```cpp\nint main() {}',
    '```cpp\nint main() {}\n```\n```cpp\nint f() {}\n```',
    '```cpp\nint main() {}\n```\n```text\nexample\n```',
    '```cpp\n\n```',
])
def test_extract_refuses_absent_ambiguous_unsupported_or_incomplete_code(feedback):
    result = audit_module().extract_cpp(feedback)
    assert result['status'] == 'not_extractable'
    assert result['code'] is None
    assert result['reason']


def test_function_submission_uses_exact_original_harness_after_unchanged_code():
    code = '#include <vector>\nint solve(int x) { return x; }\n'
    harness = '#include <iostream>\nint main() { std::cout << solve(7); }\n'
    assert audit_module().submission_source(code, harness) == code + '\n' + harness


def test_full_program_is_unchanged():
    code = '  int main(){return 0;}\r\n'
    assert audit_module().submission_source(code, '') == code


@pytest.mark.parametrize('stdout,expected,checker,want', [
    ('1  2\n', '1\t2 ', 'tokens', True),
    ('1  2\n', '1 2\n', 'exact_bytes', False),
    ('1 2\n', '1 2\n', 'exact_bytes', True),
    ('12\n', '1 2\n', 'tokens', False),
])
def test_checker_respects_authored_whitespace_contract(stdout, expected, checker, want):
    assert audit_module().output_matches(stdout, expected, checker) is want


def test_unknown_checker_refuses_to_guess():
    with pytest.raises(ValueError, match='checker'):
        audit_module().output_matches('x', 'x', 'custom')


@pytest.mark.parametrize('returncode,timeout,stdout,want', [
    (0, False, '7\n', 'pass'),
    (0, False, '8\n', 'wrong_answer'),
    (1, False, '7\n', 'runtime_error'),
    (0, True, '7\n', 'timeout'),
])
def test_run_failure_cannot_pass_merely_because_stdout_matches(returncode, timeout, stdout, want):
    run = dict(returncode=returncode, timeout=timeout, stdout=stdout, stderr='', latency_s=0.1,
               isolation='chroot_uid_seccomp_rlimits', executed=True)
    assert audit_module().test_status(run, '7\n', 'tokens') == want


def test_incomplete_state_is_skipped_without_reading_live_jsonl(tmp_path):
    state = tmp_path / 'base-dev'
    state.mkdir()
    (state / 'generations.jsonl').write_text('{unfinished')
    assert audit_module().completed_state_rows(tmp_path, 'base-dev', {}) is None


def test_completed_state_rejects_duplicate_or_misaligned_generations(tmp_path):
    state = tmp_path / 'base-dev'
    state.mkdir()
    (state / 'complete.json').write_text('{}')
    cases = {'S': dict(sample_id='S', split='dev')}
    rows = [dict(example_id=f'S-L{level}', sample_id='S', level=level) for level in range(1, 5)]
    rows[-1] = dict(example_id='S-L1', sample_id='S', level=4)
    (state / 'generations.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    with pytest.raises(ValueError, match='duplicate|alignment'):
        audit_module().completed_state_rows(tmp_path, 'base-dev', cases)


def generation(status='valid', feedback='```cpp\nint main() {}\n```'):
    parsed = dict(taxonomy_error=[], feedback=feedback) if status == 'valid' else None
    return dict(example_id='S-L4', sample_id='S', level=4, status=status, parsed=parsed,
                finish_reason='eos' if status == 'valid' else 'length', raw=json.dumps(parsed))


def authored_case():
    return dict(sample_id='S', harness='', checker='tokens', tests=[dict(input='1\n', expected='7\n')])


def test_invalid_generation_is_not_evaluable_and_never_compiled(tmp_path):
    result = audit_module().audit_target(generation('length'), authored_case(), tmp_path, None)
    assert result['status'] == 'not_evaluable'
    assert result['compile'] is None
    assert result['tests'][0]['status'] == 'not_run'


def test_missing_code_has_explicit_result_without_compile(tmp_path):
    result = audit_module().audit_target(generation(feedback='Bài làm đúng.'), authored_case(), tmp_path, None)
    assert result['status'] == 'not_extractable'
    assert result['compile'] is None


def test_existing_started_result_is_skipped_without_retry(tmp_path):
    target = tmp_path / 'S-L4'
    target.mkdir()
    row = generation()
    result = dict(example_id='S-L4', sample_id='S', generation_sha256=audit_module().json_sha256(row),
                  case_sha256=audit_module().json_sha256(authored_case()), status='started_no_retry')
    (target / 'result.json').write_text(json.dumps(result))
    assert audit_module().audit_target(row, authored_case(), tmp_path, None) == result
    assert not (target / 'extracted.cpp').exists()


def test_changed_generation_cannot_reuse_old_result(tmp_path):
    module = audit_module()
    module.audit_target(generation('length'), authored_case(), tmp_path, None)
    with pytest.raises(ValueError, match='changed'):
        module.audit_target(generation(feedback='different'), authored_case(), tmp_path, None)


def test_compile_and_authored_tests_are_persisted_without_repair(tmp_path):
    class Sandbox:
        def compile(self, code, parent):
            assert code == 'int main() {}\n'
            assert Path(parent).is_relative_to(tmp_path)
            assert json.loads((tmp_path / 'S-L4/result.json').read_text())['status'] == 'started_no_retry'
            return Path(parent) / 'jail-test', dict(status='pass', returncode=0, stdout='', stderr='',
                timeout=False, latency_s=0.1, isolation='chroot_uid_seccomp_rlimits', executed=True)

        def run(self, jail, stdin):
            assert stdin == '1\n'
            return dict(returncode=0, stdout='7\n', stderr='', timeout=False, latency_s=0.1,
                        isolation='chroot_uid_seccomp_rlimits', executed=True)

    result = audit_module().audit_target(generation(), authored_case(), tmp_path, Sandbox())
    assert result['status'] == 'all_authored_tests_passed'
    assert result['tests'][0]['expected'] == '7\n'
    assert result['tests'][0]['stdout'] == '7\n'
    assert result['tests'][0]['status'] == 'pass'
    assert (tmp_path / 'S-L4/extracted.cpp').read_bytes() == b'int main() {}\n'
    assert json.loads((tmp_path / 'S-L4/result.json').read_text()) == result
