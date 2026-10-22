"""Preregistered claim/coverage/Level accounting; no data loading or model calls."""

def summarize_review(review,reference,*,level,eligible):
    claims=review['claims'];functional={d['defect_id']for d in reference['defects']if d['kind']=='functional'}if reference.get('functional_defect',True)is not None else set()
    found=set().union(*(set(c['defect_ids'])for c in claims if c['verdict']=='supported'))if claims and eligible else set()
    found&=functional
    supported=sum(c['verdict']=='supported'for c in claims)if eligible else 0
    return {'claims':len(claims),'supported_claims':supported,'false_claims':sum(c['verdict']=='false'for c in claims),'unsupported_claims':sum(c['verdict']=='unsupported'for c in claims),'unknown_claims':sum(c['verdict']=='unknown'for c in claims),'claim_precision':supported/len(claims)if claims else None,'defects_total':len(functional)if level>=2 else None,'defects_found':len(found)if level>=2 else None,'found_defect_ids':sorted(found)if level>=2 else [],'omitted_defect_ids':sorted(functional-found)if level>=2 else [],'level_compliant':bool(eligible and review['level_compliant']),'useful_feedback':bool(eligible and review['useful_feedback'])}


def research_gate(control,candidate):
    retained=all(set(found)<=set(candidate['found_by_ID'].get(sid,[]))for sid,found in control['found_by_ID'].items())
    def not_lower(key):
        return control[key]is not None and candidate[key]is not None and candidate[key]>=control[key]
    checks={'fewer_false_accusations':candidate['false_accusations']<control['false_accusations'],'retain_each_control_defect':retained,'no_lower_defect_recall':candidate['defects_found']>=control['defects_found'],'zero_L1_disclosure':candidate['L1_disclosure']==0,'zero_L2_repair':candidate['L2_repair']==0,'more_useful_L3':candidate['L3_useful']>control['L3_useful'],'original_taxonomy_not_lower':not_lower('original_micro_f1'),'agent_taxonomy_not_lower':not_lower('agent_micro_f1'),'no_invalid_fallback_unknown':candidate['invalid_fallback_unknown']==0}
    return {'passed':all(checks.values()),'checks':checks}
