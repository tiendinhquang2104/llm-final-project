"""Before-model compiler enrichment. Original dataset units remain untouched."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from src.task3 import compiler
from src.task3.dataset import read_json, write_json
from src.task3.two_pass import append
from src.task3.level_blind import digest
from src.task3.source_refs import source_sha, build_catalog, VERSION as SOURCE_VERSION

VERSION = 'local-syntax-cpp11-cache-v1'
FLAGS = ['-fsyntax-only', '-fno-diagnostics-color', '-x', 'c++', '-']
ENV_KEYS = ('PATH', 'CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'GCC_EXEC_PREFIX',
            'COMPILER_PATH', 'LIBRARY_PATH', 'SDKROOT', 'SOURCE_DATE_EPOCH')


def toolchain():
    selected = next((shutil.which(n) for n in ('g++', 'clang++', 'c++') if shutil.which(n)), None)
    if selected is None:
        return None
    selected = str(Path(selected).resolve())
    result = subprocess.run([selected, '--version'], capture_output=True, text=True, timeout=5,
                            env={**os.environ, 'LC_ALL': 'C', 'LANG': 'C'}, check=False)
    if result.returncode:
        raise ValueError('compiler prerequisite: version probe failed')
    return dict(executable=selected, version=result.stdout+result.stderr,
                executable_sha256=__import__('hashlib').sha256(Path(selected).read_bytes()).hexdigest(),
                environment={**{k: os.environ.get(k) for k in ENV_KEYS}, 'LC_ALL': 'C', 'LANG': 'C'})


def resolve_standard(unit):
    values = []
    def explicit(value):
        if value is None:
            return
        normalized = str(value).lower().replace(' ', '').replace('gnu++', 'c++')
        aliases = {'cpp11':'c++11', 'cpp17':'c++17', '11':'c++11', '17':'c++17'}
        normalized = aliases.get(normalized, normalized)
        if normalized not in {'c++11', 'c++17'}:
            raise ValueError('unsupported explicit C++ standard: '+str(value))
        values.append(normalized)
    def visit(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in ('standard', 'cpp_standard'):
                    explicit(v)
                elif k in ('language', 'note') and isinstance(v, str):
                    for match in re.findall(r'(?:c\+\+|gnu\+\+|cpp)\s*(\d+)', v, re.I):
                        explicit('c++'+match)
                elif isinstance(v, (dict, list)):
                    visit(v)
        elif isinstance(value, list):
            for v in value:visit(v)
    task=unit['task']
    visit({k:task[k] for k in ('language','standard','cpp_standard','note','exam_metadata','input_metadata','problems') if k in task})
    if len(set(values)) > 1:
        raise ValueError('conflicting explicit C++ standards')
    return next(iter(values), 'c++11')


def cache_identity(code, standard, tool, timeout_s):
    return dict(version=VERSION, source_sha256=source_sha(code), standard=standard,
                toolchain=tool, flags=[f'-std={standard}', *FLAGS], timeout_s=timeout_s,
                max_source_chars=compiler.MAX_SOURCE_CHARS, full_diagnostics=True,
                capture_policy='complete stdout/stderr; timeout partial marked incomplete',
                runner_sha256=source_sha(Path(compiler.__file__).read_text()))


def prepare(units, out, *, timeout_s=5):
    out = Path(out); cache = out/'compiler-cache'; cache.mkdir(parents=True, exist_ok=True)
    tool = toolchain()
    if tool is None:
        write_json(out/'compiler-prerequisite-failure.json', {'status':'unavailable', 'program_executed':False})
        raise ValueError('compiler prerequisite: unavailable; no model inference allowed')
    fingerprint = digest(tool)
    enriched, audit = [], dict(version=VERSION, toolchain=tool, compiler_calls=0, cache_hits=0, compiler_latency_s=0., samples=[])
    for unit in units:
        u = copy.deepcopy(unit); code = u['task']['code']; standard = resolve_standard(u)
        identity = cache_identity(code, standard, tool, timeout_s); key = digest(identity); path = cache/(key+'.json')
        hit = path.exists()
        if hit:
            saved = read_json(path)
            if saved['identity'] != identity or saved['result_sha256'] != digest(saved['result']):
                raise ValueError('compiler cache identity/result drift')
            result = saved['result']; audit['cache_hits'] += 1
        else:
            result = compiler.check_cpp_syntax(code, compiler=tool['executable'], standard=standard,
                                               timeout_s=timeout_s, full_diagnostics=True)
            elapsed = result.pop('latency_s'); audit['compiler_calls'] += 1; audit['compiler_latency_s'] += elapsed
            write_json(path, dict(identity=identity, result=result, result_sha256=digest(result)))
        status = result['status']
        # A missing header is an unresolved dependency, not student syntax evidence.
        if status == 'compile_error' and (re.search(r'fatal error:.*(?:No such file|file not found)',result['diagnostic'])
                                           or not result['diagnostic'].strip()):
            status = 'dependency_failure'
        metadata = dict(status=status, returncode=result.get('returncode'), standard=standard,
                        program_executed=False, source_sha256=source_sha(code), toolchain_fingerprint=fingerprint,
                        cache_key=key, diagnostic_source_id='local_compile_log',
                        capture_complete=result.get('capture_complete',False), diagnostic_truncated=result.get('diagnostic_truncated',False))
        u['local_compiler'] = metadata
        u['source_catalog'] = build_catalog(code, provided_compile_log=u['task'].get('compile_log'),
                                           local_compile_log=result.get('diagnostic'), test_report=u['task'].get('test_report'))
        u['source_map_version'] = SOURCE_VERSION
        enriched.append(u)
        audit['samples'].append(dict(sample_id=u['sample_id'], cache_hit=hit, **metadata))
    append(out/'compiler-invocations.private.jsonl',audit)
    invocations=[json.loads(line) for line in (out/'compiler-invocations.private.jsonl').read_text().splitlines()]
    write_json(out/'compiler-audit.private.json',{**audit,'cumulative_compiler_calls':sum(a['compiler_calls'] for a in invocations),
        'cumulative_cache_hits':sum(a['cache_hits'] for a in invocations),'cumulative_compiler_latency_s':sum(a['compiler_latency_s'] for a in invocations)})
    if any(u['local_compiler']['status'] not in ('compiled','compile_error') for u in enriched):
        raise ValueError('compiler prerequisite: non-student failure; see compiler-audit.private.json')
    stable = {'units':enriched, 'identity':digest(enriched)}
    path=out/'enriched-inputs.private.json'
    if path.exists() and read_json(path)!=stable:
        raise ValueError('saved evidence/source-map identity drift')
    write_json(path,stable)
    write_json(out/'source-catalog.private.json',{u['sample_id']:u['source_catalog'] for u in enriched})
    return enriched,audit
