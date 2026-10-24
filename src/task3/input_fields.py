"""Positive task-metadata projection; annotation fields never enter model inputs."""
from __future__ import annotations

METADATA_FIELDS = (
    'note', 'language', 'cpp_standard', 'standard', 'constraints', 'io_mode',
    'input_specification', 'output_specification', 'input_spec', 'output_spec',
    'input_format', 'output_format', 'input', 'output', 'data_file',
    'requirements', 'restrictions', 'implementation_restrictions',
    'forbidden_functions', 'prohibited_functions', 'prohibited_features',
    'prerequisites', 'is_prerequisite_for',
)
PROBLEM_FIELDS = ('pid', 'statement', 'prototype', *METADATA_FIELDS)
POLICY_FIELDS = ('prerequisites', 'prerequisite', 'dependencies', 'description',
                 'requirements', 'restrictions', 'implementation_restrictions',
                 'forbidden_functions', 'prohibited_functions')
# Nested structured input values can contain named dimensions/problem IDs, but
# they cannot reintroduce targets hidden below an otherwise allowed field.
ANNOTATION_FIELDS = frozenset({
    'taxonomy_error', 'feedback', 'gold_taxonomy', 'gold_feedback', 'output',
    'rubric', 'score', 'scores', 'label', 'labels', 'teacher_feedback',
    'reference_solution', 'solution', 'expected_taxonomy',
})


def input_value(value, *, allow_output=False):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [input_value(v, allow_output=allow_output) for v in value]
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise ValueError('metadata object keys must be text')
        return {k: input_value(v, allow_output=allow_output) for k, v in value.items()
                if k.casefold() not in ANNOTATION_FIELDS or (allow_output and k == 'output')}
    raise ValueError('unsupported input metadata type')


def project(value, fields, *, allow_output=False):
    if not isinstance(value, dict):
        raise ValueError('input metadata must be an object')
    return {k: input_value(value[k], allow_output=allow_output) for k in fields if k in value}


def policy_value(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return project(value, POLICY_FIELDS)
