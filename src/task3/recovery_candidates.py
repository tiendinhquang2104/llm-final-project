"""Deterministic exact original-document span candidates for field recovery.

All original source-catalog documents participate, including diagnostics omitted
from older prompt projections. No model, gold annotation, reviewer text or sample
ID determines the catalog or its ranking. Line windows are deliberately explicit
rather than a claim of C++ AST parsing. Candidates suggest evidence; choosing a
syntactically valid range alone does not establish that a diagnosis is supported.
"""
from __future__ import annotations

import json
import re

from src.task3 import source_refs as refs

VERSION = 'completion16-original-span-windows-v1'
WINDOW_LINES = 4
LOG_SOURCES = ('provided_compile_log', 'local_compile_log')
_DIAGNOSTIC = re.compile(r':\d+(?::\d+)?:\s*(?:fatal error|error|warning|note):', re.I)
_PRIMARY = re.compile(r'(?:^|:\s*)(?:fatal error|error):', re.I)
_CONTEXT = re.compile(r'^\s*(?:\d+\s*\||\||[~^][~^\s]*$)')
_IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z_0-9]*')
_STOP = set('a an the of in on to is are was not no for at and or function line code error '
            'return int void float double char bool const std using namespace include '
            'dòng hàm lỗi thiếu không được'.split())


def _digest(value):
    return refs.source_sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def _candidate_id(source, document_sha256, start, end):
    return 'span-' + _digest([source, document_sha256, start, end])


def _checked_sources(unit):
    catalog = unit['source_catalog']
    for source, document in catalog.items():
        if (document['sha256'] != refs.source_sha(document['text'])
                or document['line_count'] != len(document['text'].splitlines(keepends=True))):
            raise ValueError('original source catalog hash/line count mismatch: ' + source)
    return catalog


def build_catalog(unit) -> list[dict]:
    """Cover every available line with short exact contiguous windows.

    Non-overlapping four-line fallback windows guarantee complete coverage even
    for damaged syntax. Student lines additionally receive centered three-line
    contexts. Compiler diagnostics receive their own primary/note plus adjacent
    source/caret context, capped at six lines. No range is inferred from an old
    model-provided coordinate, and identical document/range IDs never change.
    """
    result = []
    for source, document in sorted(_checked_sources(unit).items()):
        lines = document['text'].splitlines(keepends=True)
        ranges = {}
        # Specific compiler blocks first so duplicate fallback ranges keep the
        # more descriptive boundary marker. Both remain exact original ranges.
        if source in LOG_SOURCES:
            for index, line in enumerate(lines):
                if not _DIAGNOSTIC.search(line):
                    continue
                end = index + 1
                while end < min(len(lines), index + 6) and _CONTEXT.match(lines[end]):
                    end += 1
                if (end == index + 1 and end + 1 < len(lines)
                        and re.match(r'^\s*[~^][~^\s]*$', lines[end + 1].rstrip('\r\n'))
                        and not _DIAGNOSTIC.search(lines[end])):
                    end += 2
                kind = 'compiler_primary_context' if _PRIMARY.search(line) else 'compiler_note_context'
                ranges[(index + 1, end)] = kind
        for start in range(1, len(lines) + 1, WINDOW_LINES):
            ranges.setdefault((start, min(start + WINDOW_LINES - 1, len(lines))), 'contiguous_line_window')
        if source == 'code':
            for index, line in enumerate(lines):
                if line.strip():
                    ranges.setdefault((max(1, index), min(len(lines), index + 2)),
                                      'approximate_statement_context')
        for (start, end), kind in sorted(ranges.items()):
            span = refs.extract(unit['source_catalog'], dict(source=source, start_line=start, end_line=end))
            result.append(dict(candidate_id=_candidate_id(source, document['sha256'], start, end),
                               **span, text_sha256=refs.source_sha(span['text']), boundary_kind=kind))
    return result


def refs_for(candidate) -> list[dict]:
    """Map a selected immutable candidate to exact original coordinates only."""
    return [{key: candidate[key] for key in ('source', 'start_line', 'end_line')}]


def _identifiers(text):
    return {word.casefold() for word in _IDENTIFIER.findall(text) if word.casefold() not in _STOP}


def rank_candidates(catalog, finding, unit) -> list[dict]:
    """Stable relevance ranking from claim location/error and original positions.

    Location identifiers are weighted above error prose. Explicit source line
    positions contribute relevance without any clamping, offset or automatic
    evidence acceptance. Primary student diagnostics precede header overload
    notes. Stable source/range/ID ties make input catalog order irrelevant.
    """
    _checked_sources(unit)
    location = finding.get('location', '')
    error = finding.get('error', '')
    location = location if isinstance(location, str) else json.dumps(location, ensure_ascii=False, sort_keys=True)
    error = error if isinstance(error, str) else json.dumps(error, ensure_ascii=False, sort_keys=True)
    location_words, error_words = _identifiers(location), _identifiers(error)
    positions = {int(n) for n in re.findall(r'(?:\bline\s*|dòng\s*|:\s*)(\d+)\b', location, re.I)}

    def key(candidate):
        text, source = candidate['text'], candidate['source']
        words = _identifiers(text)
        relevance = 8 * len(words & location_words) + 3 * len(words & error_words)
        if source == 'code':
            position_match = any(candidate['start_line'] <= p <= candidate['end_line'] for p in positions)
        else:
            diagnostic_positions = {int(n) for n in re.findall(r':(\d+)(?::\d+)?:\s*(?:fatal error|error|warning|note):', text, re.I)}
            position_match = bool(diagnostic_positions & positions)
        relevance += 12 * position_match
        primary = bool(_PRIMARY.search(text))
        student_primary = primary and bool(re.search(r'(?:<stdin>|(?:^|[\s/])(?:main|student|submission)\.c(?:pp|c|xx)?):', text, re.M))
        header_note = source in LOG_SOURCES and not primary and bool(re.search(r'/usr/|/include/|\bcandidate:', text))
        relevance += 10 * student_primary + 4 * primary - 8 * header_note
        # Prefer concise groups when equally relevant; fallback coverage remains
        # in the catalog and is eligible for deterministic subsequent pages.
        width = candidate['end_line'] - candidate['start_line'] + 1
        return (header_note, -relevance, not student_primary, source != 'code', width,
                source, candidate['start_line'], candidate['end_line'], candidate['candidate_id'])

    return sorted(catalog, key=key)


def page_candidates(ranked, page: int, page_size=16) -> list[dict]:
    """Return a disjoint page; callers budget at most pages zero and one."""
    if type(page) is not int or page < 0 or type(page_size) is not int or not 1 <= page_size <= 16:
        raise ValueError('nonnegative integer page and page size 1–16 required')
    start = page * page_size
    return ranked[start:start + page_size]


def _ranges(numbers):
    result = []
    for number in sorted(numbers):
        if result and number == result[-1][1] + 1:
            result[-1][1] = number
        else:
            result.append([number, number])
    return result


def candidate_view(unit, candidates) -> dict:
    """Audit one new selector call: full code plus selected non-code snippets.

    The caller must actually present full code and these candidate texts. Original
    logs are not marked presented merely because their catalog is available. This
    fresh value never mutates a historical prompt/view or the original documents.
    """
    catalog = _checked_sources(unit)
    selected = {source: set() for source in catalog}
    if 'code' in catalog:
        selected['code'].update(range(1, catalog['code']['line_count'] + 1))
    for candidate in candidates:
        span = refs.extract(catalog, refs_for(candidate)[0])
        expected_id = _candidate_id(span['source'], span['document_sha256'], span['start_line'], span['end_line'])
        if (candidate.get('candidate_id') != expected_id or candidate.get('text') != span['text']
                or candidate.get('document_sha256') != span['document_sha256']
                or candidate.get('text_sha256') != refs.source_sha(span['text'])):
            raise ValueError('candidate does not match original source document/range')
        selected[span['source']].update(range(span['start_line'], span['end_line'] + 1))
    sources = {}
    for source, document in catalog.items():
        omitted = set(range(1, document['line_count'] + 1)) - selected[source]
        sources[source] = dict(sha256=document['sha256'], line_count=document['line_count'],
                               full_log_sha256=document['sha256'] if source in LOG_SOURCES else None,
                               presented_ranges=_ranges(selected[source]), omitted_ranges=_ranges(omitted),
                               presented_line_count=len(selected[source]), omitted_line_count=len(omitted))
    return dict(version=VERSION, sources=sources,
                candidate_ids=[c['candidate_id'] for c in candidates],
                candidate_sha256=_digest(candidates),
                original_source_hashes={source: doc['sha256'] for source, doc in catalog.items()},
                provenance_policy='new call only; full code and selected original-document ranges must be presented')
