"""Train-only selection and diversity validation for the single Round17 run."""
from collections import Counter
from src.synth.taxonomy import LABEL_SPACE
from src.task3.schema import code_hash


def identities(record):
    return {'id':record.sample_id,'group':record.group_key or record.original_submission_id,
            'code':code_hash(record.code),'renamed':code_hash(record.code,renamed=True)}


def select_development(pool,previous,*,quota=None):
    quota=quota or {1:4,2:8,3:8,4:4}
    forbidden={key:{identities(r)[key] for r in previous} for key in ('id','group','code','renamed')}
    candidates=[r for r in pool if not any(identities(r)[k] in forbidden[k] for k in forbidden)]
    used={k:set() for k in forbidden};chosen=[];covered=set();families=Counter()
    # Protect scarce L4, then L1; prioritise useful L2/L3 error coverage.
    for level in (4,1,2,3):
        for position in range(quota.get(level,0)):
            eligible=[r for r in candidates if int(r.target_feedback_level[6])==level
                and families[r.exam_id]<3 and not any(identities(r)[k] in used[k] for k in used)]
            if not eligible:raise ValueError(f'insufficient independent development Level {level}')
            clean_count=2 if level==1 else 1 if level in (2,3) else 0
            want_clean=position<clean_count
            preferred=[r for r in eligible if bool(not r.gold_taxonomy)==want_clean]
            eligible=preferred or eligible
            row=min(eligible,key=lambda r:(-len(set(r.gold_taxonomy)-covered),families[r.exam_id],len(r.gold_taxonomy),r.sample_id))
            chosen.append(row);covered.update(row.gold_taxonomy);families[row.exam_id]+=1
            for k,value in identities(row).items():used[k].add(value)
    chosen.sort(key=lambda r:(int(r.target_feedback_level[6]),r.sample_id))
    return chosen,{'selected_ids':[r.sample_id for r in chosen],
        'selection_rule':'v2 gold only for development stratification; no feedback or model outputs; scarce L4 then 2 clean L1, prefer one clean L2/L3; cover labels and balance families; lexicographic tie-break',
        'per_level':dict(Counter(r.target_feedback_level for r in chosen)),
        'per_family':dict(Counter(r.exam_id for r in chosen)),
        'official_labels':list(LABEL_SPACE),'missing_labels':[l for l in LABEL_SPACE if l not in covered],
        'label_support':{l:sum(l in r.gold_taxonomy for r in chosen) for l in LABEL_SPACE},
        'excluded_round16_identity_count':len(pool)-len(candidates),
        'new_vs_round16':'no shared ID/group/exact or identifier-renamed code; task families were used in R15/R16 and R13 saw corpus, not blind',
        'selection_identity':[identities(r) for r in chosen]}


def validate_bank(bank,evaluation):
    if len(bank)!=8 or Counter(e['level'] for e in bank)!={1:2,2:2,3:2,4:2}:raise ValueError('eight entries, two per Level required')
    if len({e['provenance']['family'] for e in bank})!=8:raise ValueError('bank family reuse across entries')
    if len({code_hash(e['code'],renamed=True) for e in bank})!=8:raise ValueError('bank source reuse across entries')
    eval_families={r.exam_id for r in evaluation}
    forbidden={code_hash(r.code,renamed=True) for r in evaluation}
    for ex in bank:
        if ex['provenance']['family'] in eval_families:raise ValueError('bank/evaluation family collision')
        if code_hash(ex['code'],renamed=True) in forbidden:raise ValueError('bank/evaluation source collision')
    return bank
