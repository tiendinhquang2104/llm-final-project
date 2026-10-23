"""Fixed ten-label metrics and source-reviewed joint proxy (not leaderboard)."""
from __future__ import annotations
from src.synth.taxonomy import LABEL_SPACE
from src.task3.schema import validate_taxonomy


def taxonomy_metrics(references,predictions):
    if len(references)!=len(predictions) or not references:raise ValueError('same nonempty ID denominator required')
    for x in references:validate_taxonomy(x)
    for x in predictions:
        if x is not None:validate_taxonomy(x)
    per={};n=len(references)
    for label in LABEL_SPACE:
        tp=sum(label in a and b is not None and label in b for a,b in zip(references,predictions))
        fp=sum(label not in a and b is not None and label in b for a,b in zip(references,predictions))
        fn=sum(label in a and (b is None or label not in b) for a,b in zip(references,predictions))
        per[label]=dict(support=tp+fn,TP=tp,FP=fp,FN=fn,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0)
    tp=sum(r['TP']for r in per.values());fp=sum(r['FP']for r in per.values());fn=sum(r['FN']for r in per.values())
    empty=sum(p==[]for p in predictions)
    return dict(samples=n,valid=sum(p is not None for p in predictions),invalid=sum(p is None for p in predictions),
          exact_count=sum(b is not None and set(a)==set(b)for a,b in zip(references,predictions)),
          exact_match=sum(b is not None and set(a)==set(b)for a,b in zip(references,predictions))/n,
          TP=tp,FP=fp,FN=fn,micro_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0,
          macro_f1=sum(r['f1']for r in per.values())/10,per_label=per,
          empty_predictions=empty,empty_rate=empty/n,false_clean=sum(bool(a) and b==[]for a,b in zip(references,predictions)))


def joint_pass(review,completed):
    return bool(completed and review and review['finding_supported']=='yes'
                and not review['taxonomy_missing'] and not review['taxonomy_extra']
                and review['main_error_covered_in_feedback']=='yes' and review['feedback_false_claim']=='no'
                and review['feedback_taxonomy_consistent']=='yes' and review['level_compliant']=='yes')


def winner_gate(base,candidate,config):
    checks=dict(complete=candidate['completed']==base['completed']==60,
                no_serious_leak=candidate['serious_L1_L2_leaks']==0,
                joint_gain=candidate['joint_pass']>=base['joint_pass']+config['minimum_joint_gain_samples'],
                taxonomy_not_materially_worse=candidate['micro_f1']>=base['micro_f1']-config['maximum_micro_f1_drop'],
                false_claims_not_increased=candidate['false_claims']<=base['false_claims'],
                false_clean_not_increased=candidate['false_clean']<=base['false_clean'],
                rare_tp_not_reduced=all(candidate['rare_tp'].get(k,0)>=v for k,v in base['rare_tp'].items()))
    return dict(passed=all(checks.values()),checks=checks)
