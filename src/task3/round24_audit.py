"""Additional review proof/provenance checks; no claim of automatic semantic verification."""
from dataclasses import replace
from src.task3.round15 import query_payload


def validate_defect_links(review,reference,code):
    defects={d['defect_id']:d for d in reference['defects']}
    for claim in review['claims']:
        credited=claim['defect_ids'];links=claim.get('defect_evidence',[])
        if len(credited)!=len(set(credited))or len(links)!=len(credited):raise ValueError('every credited defect needs a unique proof')
        if {l['defect_id']for l in links}!=set(credited):raise ValueError('proof/credited ID mismatch')
        for link in links:
            d=defects.get(link['defect_id'])
            if d is None or link['source_quote']!=d['source_quote']or link['source_quote']not in code:raise ValueError('proof source does not match credited frozen defect')
            if not isinstance(link.get('causal_link'),str)or not link['causal_link'].strip():raise ValueError('reviewer causal explanation required')
    return True


def audit_model_payload(payload,original,level):
    projected=replace(original,target_feedback_level=original.level_definitions[level-1]['level'])if original.level_definitions else original
    expected=query_payload(projected);expected['requested_level']=level
    if payload!=expected:raise ValueError('full model payload differs from selected original task/source/compiler/Level')
    return True


def audit_completion(ids,outputs,traces,errors):
    if set(outputs)!=set(traces)or set(outputs)&set(errors)or set(outputs)|set(errors)!=set(ids):raise ValueError('missing/overlapping native output trace or error')
    return True
