"""Supplemental unfenced extraction checks; no privileged jail setup."""
import importlib
import json

import pytest


def audit_module():
    return importlib.import_module('scripts.task3_sft_v1_l4_unfenced_audit')


def test_extract_exact_substring_from_first_include_through_original_end():
    feedback = 'Giải thích trước mã.\r\n\r\n  #include <iostream>\r\nint main() { }\r\n \r\n'
    assert audit_module().extract_unfenced(feedback) == dict(
        status='extracted', code='  #include <iostream>\r\nint main() { }\r\n \r\n', reason=None)


def test_extract_keeps_every_include_and_code_character_without_repairs():
    feedback = 'Cách giải:\n#include<vector>\n#include <iostream>\nint main(){std::cout << 4;}   \n\n'
    assert audit_module().extract_unfenced(feedback)['code'] == (
        '#include<vector>\n#include <iostream>\nint main(){std::cout << 4;}   \n\n')


@pytest.mark.parametrize('feedback', [
    'int main() {}',
    'Mã #include <iostream>\nint main() {}',
    '#included <iostream>\nint main() {}',
    '#include <iostream>\nint main() {',
    '#include <iostream>\nint main() {}\nĐoạn mã đã được sửa.',
    '```cpp\n#include <iostream>\nint main() {}\n```',
    'Có ``` trong giải thích.\n#include <iostream>\nint main() {}',
])
def test_extract_rejects_fences_no_include_or_incomplete_trailing_code(feedback):
    result = audit_module().extract_unfenced(feedback)
    assert result['status'] == 'not_extractable'
    assert result['code'] is None
    assert result['reason']


def row(status='valid'):
    feedback = 'Giải thích.\n#include <iostream>\nint main() { std::cout << 7; }\n'
    parsed = dict(taxonomy_error=[], feedback=feedback) if status == 'valid' else None
    return dict(example_id='S-L4', sample_id='S', level=4, status=status, parsed=parsed,
                finish_reason='eos' if status == 'valid' else 'length', raw=json.dumps(parsed))


def case():
    return dict(sample_id='S', harness='', checker='tokens', tests=[dict(input='1\n', expected='7\n')])


def original_result(generation):
    from scripts.task3_sft_v1_l4_audit import json_sha256
    return dict(example_id='S-L4', sample_id='S', status='not_extractable', compile=None,
                generation_sha256=json_sha256(generation), case_sha256=json_sha256(case()))


@pytest.mark.parametrize('original_status', [
    'all_authored_tests_passed', 'compile_error', 'authored_test_failure', 'started_no_retry', 'not_evaluable',
])
def test_previously_checked_or_ineligible_targets_are_skipped_without_writes(tmp_path, original_status):
    result = audit_module().audit_target(row(), case(), dict(status=original_status), tmp_path, None)
    assert result is None
    assert list(tmp_path.iterdir()) == []


def test_invalid_generation_cannot_enter_supplement_even_if_original_says_unextractable(tmp_path):
    generation = row('length')
    assert audit_module().audit_target(generation, case(), original_result(generation), tmp_path, None) is None
    assert list(tmp_path.iterdir()) == []


def test_existing_supplement_started_result_is_never_retried(tmp_path):
    module = audit_module()
    generation = row()
    original = original_result(generation)
    target = tmp_path / 'S-L4'
    target.mkdir()
    result = dict(example_id='S-L4', sample_id='S', status='started_no_retry',
                  generation_sha256=module.json_sha256(generation), case_sha256=module.json_sha256(case()),
                  original_result_sha256=module.json_sha256(original))
    (target / 'result.json').write_text(json.dumps(result))
    assert module.audit_target(generation, case(), original, tmp_path, None) == result
    assert not (target / 'extracted.cpp').exists()


def test_stale_original_evidence_refuses_execution(tmp_path):
    original = original_result(row())
    original['generation_sha256'] = 'wrong'
    with pytest.raises(ValueError, match='changed|mismatch'):
        audit_module().audit_target(row(), case(), original, tmp_path, None)
    assert list(tmp_path.iterdir()) == []


def test_original_harness_and_unchanged_unfenced_code_are_compiled_once(tmp_path):
    module = audit_module()
    generation = row()
    authored = case()
    authored['harness'] = '// original authored harness\n'
    original = original_result(generation)
    original['case_sha256'] = module.json_sha256(authored)

    class Sandbox:
        def compile(self, code, parent):
            assert code == '#include <iostream>\nint main() { std::cout << 7; }\n\n// original authored harness\n'
            return parent / 'jail-test', dict(status='pass', returncode=0, stdout='', stderr='',
                timeout=False, latency_s=0.1, isolation='chroot_uid_seccomp_rlimits', executed=True)

        def run(self, jail, stdin):
            return dict(returncode=0, stdout='7', stderr='', timeout=False, latency_s=0.1,
                        isolation='chroot_uid_seccomp_rlimits', executed=True)

    result = module.audit_target(generation, authored, original, tmp_path, Sandbox())
    assert result['status'] == 'all_authored_tests_passed'
    assert result['tests'][0]['status'] == 'pass'
    assert (tmp_path / 'S-L4/extracted.cpp').read_bytes() == b'#include <iostream>\nint main() { std::cout << 7; }\n'
    assert module.audit_target(generation, authored, original, tmp_path, None) == result
