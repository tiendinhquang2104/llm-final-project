"""Additive bounded audit of exact unfenced L4 code; never a primary metric.

This policy was introduced after observing complete bare-code output. Read-only
eligibility comes from the original fenced audit. That audit stays untouched.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.task3_sft_v1_l4_audit import (
    CppSandbox, DATASET, LIMITS, MAX_TARGETS, STATES, TEMPLATE,
    completed_state_rows, json_sha256, load_cases, parse_response,
    sha256, submission_source, test_status, write_json,
)

POLICY = dict(
    version='task3_sft_v1_l4_unfenced_supplement_v1',
    role='supplemental bounded unfenced-code check, not official semantic grader',
    introduced_after_observing_bare_code_format=True,
    part_of_primary_metric=False,
    claim='Passing finite authored cases is bounded executable evidence, not proof of full correctness.',
    eligibility='Completed primary state; valid L4 generation; original fenced-audit status is '
                'not_extractable and original compile is null. All other targets are excluded.',
    extraction='Reject any feedback containing ``` anywhere. Select the first line matching optional '
               'spaces/tabs followed by #include with a word boundary. Preserve the exact substring '
               'from the start of that line through the original end. Require the last nonblank '
               'line to end in } after ignoring only trailing whitespace for that check. '
               'No code repair, normalization, trimming, brace insertion, or prose removal after the code.',
    harness='Preserve original authored harness: unchanged code + newline + harness when nonempty; '
            'full programs remain unchanged.',
    checker='Original exact_bytes equality or tokens whitespace split equality.',
    retries=0, max_l4_targets=MAX_TARGETS, states=list(STATES),
    resume='Skip every existing target result, including started_no_retry after interruption.',
    limits=LIMITS, compiler_flags=['-std=c++11', '-O0', '-fmax-errors=3'],
    isolation='Existing CppSandbox chroot, uid/gid/capability drop, seccomp, rlimits; no VM boundary.',
    model_calls=0, gpu_calls=0,
)


def extract_unfenced(feedback: str) -> dict:
    reason = None
    match = re.search(r'(?m)^[ \t]*#include\b', feedback)
    code = feedback[match.start():] if match else None
    if '```' in feedback:
        reason = 'feedback contains a backtick code fence'
    elif match is None:
        reason = 'no include directive at the beginning of a line'
    elif not code.rstrip().endswith('}'):
        reason = 'last nonblank line does not end in a closing brace'
    return dict(status='not_extractable' if reason else 'extracted',
                code=None if reason else code, reason=reason)


def audit_target(row: dict, case: dict, original: dict, state_dir: Path, sandbox) -> dict | None:
    if row['status'] != 'valid' or row['level'] != 4 or original.get('status') != 'not_extractable':
        return None
    if original.get('compile') is not None:
        raise ValueError('original not_extractable result unexpectedly contains compilation')
    eid = row['example_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', eid):
        raise ValueError('unsafe target ID')
    provenance = dict(example_id=eid, sample_id=row['sample_id'], generation_sha256=json_sha256(row),
                      case_sha256=json_sha256(case), original_result_sha256=json_sha256(original))
    if any(original.get(key) != provenance[key] for key in ('example_id', 'sample_id', 'generation_sha256', 'case_sha256')):
        raise ValueError('original evidence mismatch or generation/case changed: ' + eid)
    directory = state_dir / eid
    path = directory / 'result.json'
    if path.exists():
        result = json.loads(path.read_text(encoding='utf-8'))
        if any(result.get(key) != value for key, value in provenance.items()):
            raise ValueError('supplemental audit evidence changed: ' + eid)
        return result
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    result = dict(**provenance, status='started_no_retry', compile=None,
                  tests=[dict(test_index=i, **test, status='not_run', passed=False)
                         for i, test in enumerate(case['tests'])],
                  checker=case['checker'], harness_sha256=sha256(case['harness'].encode()),
                  submission_mode='function_only' if case['harness'] else 'full_program',
                  policy_role=POLICY['role'], part_of_primary_metric=False, claim=POLICY['claim'])
    write_json(path, result, exclusive=True)
    parsed = parse_response(row.get('raw'), None, row.get('finish_reason'))
    if parsed['status'] != 'valid' or parsed['parsed'] != row.get('parsed'):
        result.update(status='not_evaluable', reason='valid payload/termination failed revalidation')
        write_json(path, result)
        return result
    extraction = extract_unfenced(row['parsed']['feedback'])
    result['extraction'] = extraction
    if extraction['status'] != 'extracted':
        result.update(status='not_extractable', reason=extraction['reason'])
        write_json(path, result)
        return result
    code = extraction['code']
    source = submission_source(code, case['harness'])
    (directory / 'extracted.cpp').write_bytes(code.encode())
    (directory / 'compiled.cpp').write_bytes(source.encode())
    result.update(extracted_sha256=sha256(code.encode()), compiled_sha256=sha256(source.encode()))
    write_json(path, result)
    try:
        jail, compiled = sandbox.compile(source, directory / 'jails')
        result.update(compile=dict(**compiled, limits=LIMITS['compile']), jail=str(jail))
        write_json(path, result)
        if compiled['timeout'] or compiled['returncode'] != 0:
            result['status'] = 'compile_timeout' if compiled['timeout'] else 'compile_error'
        else:
            for test in result['tests']:
                executed = sandbox.run(jail, stdin=test['input'])
                status = test_status(executed, test['expected'], case['checker'])
                test.update(**executed, status=status, passed=status == 'pass', limits=LIMITS['run'])
                write_json(path, result)
            result['status'] = ('all_authored_tests_passed' if all(t['passed'] for t in result['tests'])
                                else 'authored_test_failure')
    except Exception as exc:
        result.update(status='audit_error', reason=f'{type(exc).__name__}: {exc}')
    write_json(path, result)
    return result


def execute(run: Path) -> dict:
    run = run.resolve(strict=True)
    root = run / 'l4-unfenced-audit'
    if root.is_symlink():
        raise ValueError('audit root must not be a symlink')
    root.mkdir(mode=0o700, exist_ok=True)
    with (root / 'audit.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cases = load_cases()
        original_policy = run / 'l4-audit/policy-and-provenance.json'
        manifest = dict(policy=POLICY, run=str(run), script_sha256=sha256(Path(__file__).read_bytes()),
            original_audit_script_sha256=sha256((REPO / 'scripts/task3_sft_v1_l4_audit.py').read_bytes()),
            original_audit_policy_sha256=sha256(original_policy.read_bytes()),
            sandbox_module_sha256=sha256((REPO / 'src/task3/cpp_sandbox.py').read_bytes()),
            parser_module_sha256=sha256((REPO / 'src/task3/sft_v1_evaluation.py').read_bytes()),
            cases_sha256=sha256((DATASET / 'cases.private.json').read_bytes()), template=str(TEMPLATE),
            template_ready_sha256=sha256((TEMPLATE / 'READY.json').read_bytes()))
        policy_path = root / 'policy-and-provenance.json'
        if policy_path.exists():
            if json.loads(policy_path.read_text(encoding='utf-8')) != manifest:
                raise ValueError('supplemental policy/code/data/template changed; refusing to resume')
        else:
            if any(root.glob('*/**/result.json')):
                raise ValueError('supplemental results lack original policy/provenance')
            write_json(policy_path, manifest, exclusive=True)
            write_json(root / 'created.json', dict(utc=datetime.now(timezone.utc).isoformat(),
                introduced_after_observing_bare_code_format=True, part_of_primary_metric=False), exclusive=True)
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
                    states[state] = dict(status='unavailable_or_incomplete', primary_l4_targets=0)
                    continue
                total += len(rows)
                if total > MAX_TARGETS:
                    raise ValueError('L4 target budget exceeds 100')
                results, excluded = [], Counter()
                for row in rows:
                    original_path = run / 'l4-audit' / state / row['example_id'] / 'result.json'
                    if not original_path.is_file():
                        excluded['original_result_unavailable'] += 1
                        continue
                    original = json.loads(original_path.read_text(encoding='utf-8'))
                    result = audit_target(row, cases[row['sample_id']], original, root / state, sandbox)
                    if result is None:
                        excluded['original_' + original['status']] += 1
                    else:
                        results.append(result)
                state_summary = dict(status='audited', primary_l4_targets=len(rows),
                    eligible_targets=len(results), excluded_counts=dict(excluded),
                    generation_file_sha256=sha256((run / state / 'generations.jsonl').read_bytes()),
                    completion_file_sha256=sha256((run / state / 'complete.json').read_bytes()),
                    status_counts=dict(Counter(r['status'] for r in results)),
                    compile_calls=sum(r['compile'] is not None for r in results),
                    runtime_calls=sum(t.get('executed', False) for r in results for t in r['tests']),
                    test_status_counts=dict(Counter(t['status'] for r in results for t in r['tests'])),
                    results=[str((root / state / r['example_id'] / 'result.json').relative_to(root)) for r in results])
                states[state] = state_summary
                (root / state).mkdir(exist_ok=True)
                write_json(root / state / 'summary.json', state_summary)
            summary = dict(utc=datetime.now(timezone.utc).isoformat(), role=POLICY['role'], claim=POLICY['claim'],
                part_of_primary_metric=False, introduced_after_observing_bare_code_format=True,
                policy_and_provenance_sha256=sha256(policy_path.read_bytes()), states=states,
                primary_l4_targets_seen=total, maximum_l4_targets=MAX_TARGETS,
                all_primary_states_available=all(s['status'] == 'audited' for s in states.values()),
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
