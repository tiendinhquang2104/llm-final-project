"""Exact per-sample documents and inclusive 1-based source coordinates.

Structured test reports: sanitized recursively, UTF-8 JSON, sorted keys,
ensure_ascii=False, separators=(',', ':'). No synthetic final line is added.
"""
from __future__ import annotations
import hashlib
import json
from src.task3.input_fields import input_value

VERSION = 'source-catalog-lines-v1'
REFERENCE_KEYS = {'source', 'start_line', 'end_line'}


def source_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class ReferenceFailure(ValueError):
    category = 'reference_contract'
    def __init__(self, reason, path, value, catalog):
        super().__init__(reason)
        self.details = dict(failure_kind=self.category, field_path=path, offending_value=value,
                            allowed_sources={k: v['line_count'] for k, v in catalog.items()})


def build_catalog(code, *, provided_compile_log=None, local_compile_log=None, test_report=None):
    documents = {'code': code}
    for name, text in [('provided_compile_log', provided_compile_log), ('local_compile_log', local_compile_log)]:
        if text:
            documents[name] = text
    if test_report is not None:
        sanitized = input_value(test_report, allow_output=True)
        documents['provided_test_report'] = sanitized if isinstance(sanitized, str) else json.dumps(
            sanitized, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    catalog = {}
    for name, text in documents.items():
        if not isinstance(text, str):
            raise ValueError('source document must be text: '+name)
        catalog[name] = dict(text=text, sha256=source_sha(text), line_count=len(text.splitlines(keepends=True)))
    return catalog


def numbered(document):
    return ''.join(f'{i} | {line}' for i, line in enumerate(document['text'].splitlines(keepends=True), 1))


def extract(catalog, ref, path='evidence_refs[0]'):
    def fail(reason, field='', value=None):
        raise ReferenceFailure(reason, path+field, ref if value is None else value, catalog)
    if not isinstance(ref, dict) or set(ref) != REFERENCE_KEYS:
        fail('reference must contain exactly source, start_line, end_line')
    source = ref['source']
    if not isinstance(source, str) or source not in catalog:
        fail('unknown source ID', '.source', source)
    for field in ('start_line', 'end_line'):
        if type(ref[field]) is not int:
            fail('reference line must be an integer excluding bool', '.'+field, ref[field])
    start, end = ref['start_line'], ref['end_line']
    if not 1 <= start <= catalog[source]['line_count']:
        fail('start_line outside source lines', '.start_line', start)
    if not start <= end <= catalog[source]['line_count']:
        fail('end_line reversed or outside source lines', '.end_line', end)
    document = catalog[source]
    return {**ref, 'document_sha256': document['sha256'],
            'text': ''.join(document['text'].splitlines(keepends=True)[start-1:end])}


def derive(catalog, references, path='evidence_refs'):
    spans = [extract(catalog, r, f'{path}[{i}]') for i, r in enumerate(references)]
    evidence = '\n'.join(f"[{s['source']}:{s['start_line']}-{s['end_line']}]\n{s['text']}" for s in spans)
    return spans, evidence


def validate_spans(catalog, references, spans, evidence):
    expected_spans, expected_evidence = derive(catalog, references)
    if expected_spans != spans or expected_evidence != evidence:
        raise ValueError('normalized source hashes/spans/evidence mismatch')
