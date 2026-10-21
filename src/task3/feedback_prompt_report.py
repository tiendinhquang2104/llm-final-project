"""Evidence validation and frozen paired feedback gates (taxonomy-independent)."""
from __future__ import annotations


def validate_reviews(inputs, outputs, reviews):
    sources={r['sample_id']:r for r in inputs}
    expected={(sid,arm) for arm,items in outputs.items() for sid in items}
    seen=set()
    if any(set(items)!=set(sources) for items in outputs.values()):raise ValueError('outputs incomplete')
    for r in reviews:
        key=(r['sample_id'],r['arm'])
        if key in seen or key not in expected:raise ValueError('duplicate or unexpected review')
        seen.add(key)
        if r['output_quote']!=outputs[r['arm']][r['sample_id']]:raise ValueError('review/output binding mismatch')
        if r['source_evidence']['quote'] not in sources[r['sample_id']]['code']:raise ValueError('source evidence binding mismatch')
        if r['score'] not in (0,.5,1):raise ValueError('invalid proxy score')
    if seen!=expected:raise ValueError('missing paired review')


def paired(reviews,candidate='C'):
    by={a:{r['sample_id']:r for r in reviews if r['arm']==a} for a in ('A',candidate)}
    if set(by['A'])!=set(by[candidate]):raise ValueError('paired IDs differ')
    values=[]
    for sid,a in by['A'].items():
        b=by[candidate][sid]
        if a['level']!=b['level']:raise ValueError('paired Level mismatch')
        values.append((a['level'],(b['score']>a['score'])-(b['score']<a['score'])))
    def counts(v):
        return {'n':len(v),'wins':sum(x==1 for x in v),'losses':sum(x==-1 for x in v),
                'ties':sum(x==0 for x in v),'net':sum(v)}
    result=counts([v for _,v in values])
    result['per_level']={str(l):counts([v for lev,v in values if lev==l]) for l in range(1,5)}
    return result


def decision(reviews,*,complete,candidate='C'):
    result=paired(reviews,candidate)
    a=[r for r in reviews if r['arm']=='A'];b=[r for r in reviews if r['arm']==candidate]
    checks={
      'all_complete_valid':bool(complete),
      'no_l1_l2_repair_disclosure':not any(r['level']<=2 and r.get('repair_disclosure') for r in b),
      'false_technical_claim_not_increased':sum(bool(r.get('false_technical_claim')) for r in b)<=sum(bool(r.get('false_technical_claim')) for r in a),
      'net_wins_ge6':result['net']>=6,
      'l2_net_ge3':result['per_level']['2']['net']>=3,
      'l3_net_ge1':result['per_level']['3']['net']>=1,
      'l1_false_clean_not_increased':sum(bool(r.get('false_clean')) for r in b if r['level']==1)<=sum(bool(r.get('false_clean')) for r in a if r['level']==1),
      'no_unresolved_material_unknown':not any(r.get('unknown') for r in reviews)}
    return {'eligible':all(checks.values()),'checks':checks,'paired':result,
            'action':'candidate for independent review before public only' if all(checks.values()) else 'retain R15; stop before public'}


def audit_payload(payload):
    """Read-only audit of actual frozen journals; never changes a model prompt.

    R15's renderer is intentionally frozen. This validator closes the nested
    metadata contract gap for experiment verification, not arbitrary rendering.
    """
    allowed={'statement','code','problems','grading_policy','compiler','requested_level'}
    if set(payload)!=allowed:raise ValueError('unexpected model-input fields')
    if any(not isinstance(payload[k],str) for k in ('statement','code','grading_policy')):
        raise ValueError('model metadata must be scalar text; no nested annotation')
    if type(payload['requested_level']) is not int or payload['requested_level'] not in range(1,5):
        raise ValueError('invalid requested Level')
    if not isinstance(payload['problems'],list):raise ValueError('invalid problem metadata')
    for problem in payload['problems']:
        if not isinstance(problem,dict) or set(problem)-{'pid','statement','prototype'} or any(not isinstance(x,str) for x in problem.values()):
            raise ValueError('problem metadata must be whitelisted scalar text')
    compiler=payload['compiler']
    if not isinstance(compiler,dict) or set(compiler)!={'status','diagnostic'} or any(not isinstance(x,str) for x in compiler.values()):
        raise ValueError('invalid compiler payload')
