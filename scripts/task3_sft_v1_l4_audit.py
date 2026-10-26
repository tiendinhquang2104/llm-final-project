"""Supplemental bounded L4 code checks; no model calls or semantic grading.

Run with the existing Task 3 virtualenv and --run <experiment directory>.
Only completed primary states are read. Every target is attempted at most once,
including interrupted attempts. All writable artifacts and jails stay below
<run>/l4-audit; the trusted sandbox template is only read/hardlinked.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.task3.cpp_sandbox import CppSandbox
from src.task3.sft_v1_evaluation import parse_response

STATES = ('base-dev', 'step-80-dev', 'step-160-dev', 'base-test', 'selected-test')
TEMPLATE = Path('/workspace/llm-final-project/outputs/task3/round23-20261022/sandbox-template')
DATASET = REPO / 'data/raw/task3-sft-v1'
MAX_TARGETS = 100
LIMITS = {
    'compile': dict(wall_seconds=10, cpu_soft_seconds=4, cpu_hard_seconds=5,
                    address_space_mib=512, processes=4, open_files=64,
                    per_output_file_bytes=8 << 20, captured_stream_bytes=65536),
    'run': dict(wall_seconds=2, cpu_soft_seconds=1, cpu_hard_seconds=2,
                address_space_mib=512, processes=1, open_files=64,
                per_output_file_bytes=65536, captured_stream_bytes=65536),
}
POLICY = dict(
    version='task3_sft_v1_l4_bounded_audit_v1',
    role='supplemental bounded code check, not official semantic grader',
    claim='Passing finite authored tests is bounded executable evidence, not proof of full correctness.',
    extraction='Exactly one complete backtick-fenced block, tagged cpp/c++/cxx or bare; '
               'preserve its body unchanged. Missing, multiple, unsupported or empty blocks are not_extractable.',
    invalid_generation='not_evaluable; never infer or repair code from invalid output',
    harness='Nonempty original authored harness means function-only submission: unchanged code + newline + '
            'unchanged harness, equivalent to bundled verifier inclusion. Full programs are unchanged.',
    checker='Use the original case exact_bytes equality or tokens whitespace split equality.',
    retries=0,
    resume='Existing result files are immutable on resume, including started_no_retry after interruption.',
    states=list(STATES), max_l4_targets=MAX_TARGETS,
    compiler_flags=['-std=c++11', '-O0', '-fmax-errors=3'],
    limits=LIMITS,
    isolation='Existing CppSandbox chroot + uid/gid/capability drop + seccomp + rlimits; '
              'not a kernel/VM boundary or multi-tenant service.',
    sanitizer='none; existing sandbox compiler profile is preserved',
    model_calls=0, gpu_calls=0,
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_sha256(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode())


def write_json(path: Path, value, *, exclusive=False) -> None:
    """Durably reserve an attempt before execution; atomically save its progress."""
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    target = path if exclusive else path.with_name(path.name + '.tmp')
    with target.open('x' if exclusive else 'w', encoding='utf-8') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    if not exclusive:
        target.replace(path)


def extract_cpp(feedback: str) -> dict:
    fence_lines = list(re.finditer(r'(?m)^[ \t]*```[^\r\n]*(?:\r?\n|\Z)', feedback))
    match = re.search(r'(?ms)^[ \t]*```([^`\r\n]*)\r?\n(.*?)^[ \t]*```[ \t]*(?:\r?\n|\Z)', feedback)
    reason = None
    if len(fence_lines) != 2 or match is None:
        reason = 'expected exactly one complete fenced code block'
    elif match.group(1).strip().lower() not in ('', 'cpp', 'c++', 'cxx'):
        reason = 'unsupported code fence language'
    elif not match.group(2).strip():
        reason = 'empty code block'
    return dict(status='not_extractable' if reason else 'extracted',
                code=None if reason else match.group(2), reason=reason)


def submission_source(code: str, harness: str) -> str:
    return code + '\n' + harness if harness else code


def output_matches(stdout: str, expected: str, checker: str) -> bool:
    if checker == 'exact_bytes':
        return stdout == expected
    if checker == 'tokens':
        return stdout.split() == expected.split()
    raise ValueError('unsupported authored checker: ' + checker)


def test_status(run: dict, expected: str, checker: str) -> str:
    if run['timeout']:
        return 'timeout'
    if run['returncode'] != 0:
        return 'runtime_error'
    return 'pass' if output_matches(run['stdout'], expected, checker) else 'wrong_answer'


def completed_state_rows(run: Path, state: str, cases: dict) -> list[dict] | None:
    directory = run / state
    if not (directory / 'complete.json').is_file():
        return None
    split = 'dev' if state.endswith('-dev') else 'test'
    expected = {f'{sid}-L{level}': (sid, level)
                for sid, case in cases.items() if case['split'] == split for level in range(1, 5)}
    rows, seen = [], set()
    for line in (directory / 'generations.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        eid = row['example_id']
        if eid in seen or expected.get(eid) != (row.get('sample_id'), row.get('level')):
            raise ValueError('duplicate or alignment mismatch in ' + state + '/' + eid)
        seen.add(eid)
        rows.append(row)
    if seen != set(expected):
        raise ValueError('incomplete generation alignment despite completion marker: ' + state)
    return [row for row in rows if row['level'] == 4]


def audit_target(row: dict, case: dict, state_dir: Path, sandbox) -> dict:
    eid = row['example_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', eid):
        raise ValueError('unsafe target ID')
    directory = state_dir / eid
    result_path = directory / 'result.json'
    provenance = dict(example_id=eid, sample_id=row['sample_id'],
                      generation_sha256=json_sha256(row), case_sha256=json_sha256(case))
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding='utf-8'))
        if any(result.get(key) != value for key, value in provenance.items()):
            raise ValueError('generation or authored case changed since first attempt: ' + eid)
        return result
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    result = dict(**provenance, status='started_no_retry', generation_status=row['status'],
                  compile=None, tests=[dict(test_index=i, **test, status='not_run', passed=False)
                                      for i, test in enumerate(case['tests'])],
                  checker=case['checker'], harness_sha256=sha256(case['harness'].encode()),
                  submission_mode='function_only' if case['harness'] else 'full_program',
                  policy_role=POLICY['role'], claim=POLICY['claim'])
    write_json(result_path, result, exclusive=True)
    if row['status'] != 'valid':
        result.update(status='not_evaluable', reason='generation status is ' + row['status'])
        write_json(result_path, result)
        return result
    parsed = parse_response(row.get('raw'), None, row.get('finish_reason'))
    if parsed['status'] != 'valid' or parsed['parsed'] != row.get('parsed'):
        result.update(status='not_evaluable', reason='valid generation payload/termination failed revalidation')
        write_json(result_path, result)
        return result
    extraction = extract_cpp(row['parsed']['feedback'])
    result['extraction'] = extraction
    if extraction['status'] != 'extracted':
        result.update(status='not_extractable', reason=extraction['reason'])
        write_json(result_path, result)
        return result
    code = extraction['code']
    source = submission_source(code, case['harness'])
    (directory / 'extracted.cpp').write_bytes(code.encode())
    (directory / 'compiled.cpp').write_bytes(source.encode())
    result.update(extracted_sha256=sha256(code.encode()), compiled_sha256=sha256(source.encode()))
    write_json(result_path, result)
    try:
        jail, compiled = sandbox.compile(source, directory / 'jails')
        result.update(compile=dict(**compiled, limits=LIMITS['compile']), jail=str(jail))
        write_json(result_path, result)
        if compiled['timeout'] or compiled['returncode'] != 0:
            result.update(status='compile_timeout' if compiled['timeout'] else 'compile_error')
        else:
            for test in result['tests']:
                executed = sandbox.run(jail, stdin=test['input'])
                status = test_status(executed, test['expected'], case['checker'])
                test.update(**executed, status=status, passed=status == 'pass', limits=LIMITS['run'])
                write_json(result_path, result)
            result['status'] = ('all_authored_tests_passed' if all(t['passed'] for t in result['tests'])
                                else 'authored_test_failure')
    except Exception as exc:
        result.update(status='audit_error', reason=f'{type(exc).__name__}: {exc}')
    write_json(result_path, result)
    return result


def load_cases() -> dict:
    cases = {}
    for case in json.loads((DATASET / 'cases.private.json').read_text(encoding='utf-8')):
        sid = case['sample_id']
        if sid in cases:
            raise ValueError('duplicate authored source: ' + sid)
        source = (DATASET / case['code_file']).resolve()
        if not source.is_relative_to(DATASET / 'sources'):
            raise ValueError('authored source outside sources directory')
        if sha256(source.read_bytes()) != case['source_sha256']:
            raise ValueError('authored source checksum mismatch: ' + sid)
        if case['checker'] not in ('tokens', 'exact_bytes') or not case['tests']:
            raise ValueError('unsupported/empty authored tests: ' + sid)
        cases[sid] = case
    count = sum(sum(case['split'] == ('dev' if state.endswith('-dev') else 'test')
                    for case in cases.values()) for state in STATES)
    if count > MAX_TARGETS:
        raise ValueError('L4 target budget exceeds 100')
    return cases


def execute(run: Path) -> dict:
    run = run.resolve(strict=True)
    root = run / 'l4-audit'
    if root.is_symlink():
        raise ValueError('audit root must not be a symlink')
    root.mkdir(mode=0o700, exist_ok=True)
    with (root / 'audit.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cases = load_cases()
        manifest = dict(policy=POLICY, run=str(run), script_sha256=sha256(Path(__file__).read_bytes()),
                        sandbox_module_sha256=sha256((REPO / 'src/task3/cpp_sandbox.py').read_bytes()),
                        cases_sha256=sha256((DATASET / 'cases.private.json').read_bytes()),
                        template=str(TEMPLATE), template_ready_sha256=sha256((TEMPLATE / 'READY.json').read_bytes()))
        policy_path = root / 'policy-and-provenance.json'
        if policy_path.exists():
            if json.loads(policy_path.read_text(encoding='utf-8')) != manifest:
                raise ValueError('audit policy/code/data/template changed; refusing to resume')
        else:
            if any(root.glob('*/**/result.json')):
                raise ValueError('result files exist without the original policy/provenance')
            write_json(policy_path, manifest, exclusive=True)
        scratch = root / 'tmp'
        scratch.mkdir(mode=0o700, exist_ok=True)
        old_tempdir = tempfile.tempdir
        tempfile.tempdir = str(scratch)
        try:
            sandbox = CppSandbox(TEMPLATE)
            states = {}
            total = 0
            for state in STATES:
                rows = completed_state_rows(run, state, cases)
                if rows is None:
                    states[state] = dict(status='unavailable_or_incomplete', targets_checked=0)
                    continue
                total += len(rows)
                if total > MAX_TARGETS:
                    raise ValueError('L4 target budget exceeds 100')
                results = [audit_target(row, cases[row['sample_id']], root / state, sandbox) for row in rows]
                state_summary = dict(status='audited', targets_checked=len(results),
                    generation_file_sha256=sha256((run / state / 'generations.jsonl').read_bytes()),
                    completion_file_sha256=sha256((run / state / 'complete.json').read_bytes()),
                    status_counts=dict(Counter(r['status'] for r in results)),
                    compile_calls=sum(r.get('compile') is not None for r in results),
                    runtime_calls=sum(t.get('executed', False) for r in results for t in r.get('tests', [])),
                    test_status_counts=dict(Counter(t['status'] for r in results for t in r.get('tests', []))),
                    results=[str((root / state / row['example_id'] / 'result.json').relative_to(root)) for row in rows])
                states[state] = state_summary
                write_json(root / state / 'summary.json', state_summary)
            summary = dict(utc=datetime.now(timezone.utc).isoformat(), role=POLICY['role'], claim=POLICY['claim'],
                           policy_and_provenance_sha256=sha256(policy_path.read_bytes()), states=states,
                           l4_targets_checked=total, maximum_l4_targets=MAX_TARGETS,
                           all_primary_states_available=all(v['status'] == 'audited' for v in states.values()),
                           model_calls=0, gpu_calls=0)
            invocation = len(list(root.glob('invocation-*.json'))) + 1
            write_json(root / f'invocation-{invocation:04d}.json', summary, exclusive=True)
            write_json(root / 'summary.json', summary)
            return summary
        finally:
            tempfile.tempdir = old_tempdir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.run), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
