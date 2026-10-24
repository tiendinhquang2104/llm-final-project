"""Lossless JSON transport boundary; diagnosis and strict parsing stay downstream.

Plain documents retain even their surrounding whitespace. For a fenced document,
only the opening/closing lines and outside whitespace are removed. The payload
(including its final newline, CRLF, escaping and Unicode) is never rewritten.
"""
from __future__ import annotations

import hashlib

VERSION = 'json-transport-one-envelope-v1'
PARSER_VERSION = VERSION


class TransportFailure(ValueError):
    category = 'transport'

    def __init__(self, reason):
        super().__init__(reason)
        self.details = dict(failure_kind=self.category, field_path='$', offending_value=None)


class GenerationTermination(ValueError):
    category = 'generation_termination'

    def __init__(self, reason, finish_reason=None):
        super().__init__(reason)
        self.details = dict(failure_kind=self.category, field_path='finish_reason',
                            offending_value=finish_reason)


class InfrastructureFailure(ValueError):
    category = 'infrastructure'


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def generation_text(row):
    """Check completion before any envelope or JSON parsing, including replay."""
    error = row.get('error') or row.get('runtime_error')
    if error:
        raise InfrastructureFailure(str(error))
    reason = row.get('finish_reason')
    if reason in ('backend_failure', 'runtime_error'):
        raise InfrastructureFailure('generation backend failed: ' + reason)
    if reason != 'eos' or row.get('eos_reached') is False:
        raise GenerationTermination('JSON generation did not reach EOS: ' + str(reason), reason)
    raw = row.get('raw_text')
    if not isinstance(raw, str):
        raise InfrastructureFailure('EOS generation is missing its raw response text')
    return raw


def normalize(raw: str) -> tuple[str, dict]:
    """Remove one permitted outer fence, then let v1.5 json_object validate JSON.

    This function intentionally does not repair or parse JSON. Duplicate keys,
    constants, multiple objects, non-object roots and trailing prose remain the
    responsibility of the unchanged strict object parser after this boundary.
    """
    if not isinstance(raw, str):
        raise TransportFailure('response transport must be text')
    boundary = raw.strip()
    if not boundary:
        raise TransportFailure('empty response transport')
    if boundary.startswith('`'):
        # splitlines preserves exact CRLF/body bytes; only a line terminator is
        # removed from the opening line to compare the entire fence token.
        lines = boundary.splitlines(keepends=True)
        if len(lines) < 3:
            raise TransportFailure('one complete outer JSON fence required')
        opening = lines[0].removesuffix('\n').removesuffix('\r')
        if opening.lower() not in ('```', '```json') or lines[-1] != '```':
            raise TransportFailure('opening/closing JSON fences must occupy complete lines')
        body = lines[1:-1]
        if any(line.strip().startswith('```') for line in body):
            raise TransportFailure('multiple or nested fence blocks are not accepted')
        payload = ''.join(body)
        mode, action = 'fenced_json', 'remove_single_outer_fence'
    else:
        # Reject prose/other envelopes, while leaving malformed JSON, non-object
        # JSON roots and illegal JSON constants visible to the strict parser.
        if boundary[0] not in '{["-0123456789tfnNI':
            raise TransportFailure('only a JSON document or one outer JSON fence is accepted')
        payload = raw
        mode, action = 'json_document', 'identity'
    return payload, dict(transport_mode=mode, raw_sha256=_sha(raw), payload_sha256=_sha(payload),
                         parser_version=VERSION, normalization_action=action)
