"""Explicit v2 identity guard; v1 signatures and gate remain read only."""
from copy import deepcopy

from src.task3.direct_sft_data import (VERSION as V1_VERSION, NEAR_THRESHOLD,
    require_direct_isolation, signature, _conflicts)

VERSION = 'direct-sft-v2-20261021'


def require_direct_v2_isolation(rows, registry, *, stage, validation_sources=()):
    """Guard actual optimizer bytes against opaque protection and fixed old val."""
    if registry.get('version') != VERSION:
        raise ValueError('wrong v2 registry version')
    if registry.get('near_threshold') != NEAR_THRESHOLD:
        raise ValueError('v2 near threshold drift')
    protected_validation = [signature(row) for row in validation_sources]
    for row in rows:
        reasons, _ = _conflicts(signature(row), protected_validation)
        if reasons:
            raise ValueError('old validation source leakage: ' + ','.join(reasons))
    # Adapter has one explicit purpose: apply the unchanged v1 identity semantics
    # to a copied v2 registry, never mutate the sealed registry or module globals.
    compatible = deepcopy(registry)
    compatible['version'] = V1_VERSION
    result = require_direct_isolation(rows, compatible, stage=stage)
    return dict(result, version=VERSION, fixed_validation_protected=len(protected_validation))
