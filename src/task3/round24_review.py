"""Source-bound review accounting, preserving original/disputed/human authorities."""
from src.synth.taxonomy import LABEL_SPACE
from src.task3.schema import validate_taxonomy


def taxonomy_metrics(pairs):
    counts={label:dict(TP=0,FP=0,FN=0,TN=0)for label in LABEL_SPACE};exact=invalid=0
    for row in pairs:
        reference=set(validate_taxonomy(row['reference']));prediction=row['prediction']
        if prediction is None:invalid+=1;predicted=set()
        else:predicted=set(validate_taxonomy(prediction));exact+=predicted==reference
        for label in LABEL_SPACE:
            key='TP'if label in predicted and label in reference else 'FP'if label in predicted else 'FN'if label in reference else 'TN';counts[label][key]+=1
    def rates(tp,fp,fn):
        return {'precision':tp/(tp+fp)if tp+fp else None,'recall':tp/(tp+fn)if tp+fn else None,'f1':2*tp/(2*tp+fp+fn)if 2*tp+fp+fn else None}
    for c in counts.values():c.update(rates(c['TP'],c['FP'],c['FN']))
    sums={k:sum(c[k]for c in counts.values())for k in ['TP','FP','FN']};micro=rates(sums['TP'],sums['FP'],sums['FN'])
    supported=[c['f1']if c['f1']is not None else 0 for c in counts.values()if c['TP']+c['FN']>0]
    return {'n':len(pairs),'exact':exact,'exact_accuracy':exact/len(pairs)if pairs else None,'invalid':invalid,'micro_precision':micro['precision'],'micro_recall':micro['recall'],'micro_f1':micro['f1'],'macro_f1_supported_labels':sum(supported)/len(supported)if supported else None,'supported_labels':len(supported),'per_label':counts,'invalid_policy':'Invalid output has no usable labels and cannot be exact, including empty reference.'}


def validate_reference(reference,code):
    status=reference['taxonomy_status']
    if status not in ['confirmed','disputed','unknown']:raise ValueError('unknown reference status')
    if status=='confirmed':validate_taxonomy(reference['reference_taxonomy'])
    elif reference['reference_taxonomy']is not None:raise ValueError('disputed/unknown cannot supply canonical exact reference')
    if reference['functional_defect']is not None and type(reference['functional_defect'])is not bool:raise ValueError('functional status must be bool/null')
    seen=set()
    for defect in reference['defects']:
        if defect['defect_id']in seen:raise ValueError('duplicate defect ID')
        seen.add(defect['defect_id'])
        if not defect['source_quote']or defect['source_quote']not in code:raise ValueError('unbound source evidence')
        for labels in defect['taxonomy_options']:validate_taxonomy(labels)
    return reference


def validate_claim_review(review,output,code,reference):
    ids={d['defect_id']for d in reference['defects']}
    for claim in review['claims']:
        if not claim['feedback_quote']or claim['feedback_quote']not in output['feedback']:raise ValueError('unbound feedback quote')
        if not claim['source_quote']or claim['source_quote']not in code:raise ValueError('unbound source quote')
        if claim['verdict']not in ['supported','false','unsupported','unknown']:raise ValueError('unknown claim verdict')
        if not set(claim['defect_ids'])<=ids:raise ValueError('unknown covered defect')
        if claim['verdict']!='supported'and claim['defect_ids']:raise ValueError('incorrect claim cannot cover defect')
    return review


def public_decision(*,research_passed,independent_confirmation,human_decisions,unresolved_disputes):
    checks={'research_gate':bool(research_passed),'independent_confirmation':bool(independent_confirmation),'actual_human_confirmation':bool(human_decisions)and all(r.get('human_verified')is True for r in human_decisions),'no_unresolved_disputes':unresolved_disputes==0}
    return {'production':'R15','select_public_candidate':all(checks.values()),'checks':checks,'action':'retain R15; no public selection or submission in this experiment'}


def validate_projection(records,sources,*,expected_levels=(1,2,3)):
    """Bind every model query to selected train source, with no annotation fields."""
    by={s['record']['sample_id']:s for s in sources};seen=set();levels={sid:set()for sid in by}
    for r in records:
        if r['sample_id']in seen:raise ValueError('duplicate query ID')
        seen.add(r['sample_id']);source=by.get(r['original_submission_id'])
        if source is None:raise ValueError('not selected train source')
        original=source['record']
        if original['source']not in ['real','synthetic']or any(r[k]!=original[k]for k in ['source','code','exam_id']):raise ValueError('source projection mismatch')
        if r['gold_taxonomy']is not None or r['gold_feedback']is not None:raise ValueError('gold in model record')
        if r['split']!='round24-'+source['split']:raise ValueError('source/Level crossed split')
        level=int(r['target_feedback_level'][6])
        if level not in expected_levels or level in levels[r['original_submission_id']]:raise ValueError('duplicate/unexpected Level')
        levels[r['original_submission_id']].add(level)
    if any(v!=set(expected_levels)for v in levels.values()):raise ValueError('incomplete source Levels')
    return True
