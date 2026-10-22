"""Preregistered all-ID paired accounting and renderer gate, no model calls."""
from collections import Counter,defaultdict


def validate_rows(rows):
    if len(rows)!=80 or len({r['sample_id']for r in rows})!=80:raise ValueError('80 unique IDs required')
    pairs=defaultdict(list)
    for r in rows:pairs[r['pair_id']].append(r)
    if len(pairs)!=40 or any(len(p)!=2 or {r['role']for r in p}!={'base','mutant'}or len({r['split']for r in p})!=1 for p in pairs.values()):raise ValueError('40 complete same-split pairs required')
    if Counter(p[0]['split']for p in pairs.values())!={'development':24,'evaluation':16}:raise ValueError('24/16 split required')


def pair_counts(rows,arm,field,split):
    grouped=defaultdict(list)
    for r in rows:
        if split=='all'or r['split']==split:grouped[r['pair_id']].append(r)
    successes=sum(len(p)==2 and all(r['arms'][arm][field]is True for r in p)for p in grouped.values())
    return {'pairs':len(grouped),'successes':successes,'accuracy':successes/len(grouped)if grouped else None}


def gate_result(config,baseline_pairs,candidate_pairs,trustworthy_mutants,false_clean,baseline_false_clean):
    checks={'minimum_pairs':candidate_pairs>=config['minimum_strict_pair_successes'],
            'gain_over_control':candidate_pairs-baseline_pairs>=config['minimum_gain_over_R15_exact_taxonomy_pairs'],
            'trustworthy_mutants':trustworthy_mutants>=config['minimum_trustworthy_mutant_witnesses'],
            'no_additional_false_clean':false_clean-baseline_false_clean<=config['additional_mutant_false_clean_allowed']}
    return {'passed':all(checks.values()),'checks':checks,'baseline_pairs':baseline_pairs,'strict_pairs':candidate_pairs,'trustworthy_mutants':trustworthy_mutants,'false_clean':false_clean,'baseline_false_clean':baseline_false_clean}


def trustworthy_witness(score):
    return all(score[k]is True for k in ['input_valid','actual_correct','expected_correct','distinguishes'])


def aggregate(rows,gate):
    validate_rows(rows);metrics={}
    for split in ['all','development','evaluation']:
        subset=[r for r in rows if split=='all'or r['split']==split];arms={}
        for arm in ['R15','self','execution']:
            values=[r['arms'][arm]for r in subset]
            arms[arm]={'IDs':len(values),'content_pairs':pair_counts(rows,arm,'content_success',split),'strict_pairs':pair_counts(rows,arm,'strict_success',split),
                'status_counts':dict(Counter(v['status']for v in values)),'taxonomy_exact':sum(v['taxonomy_exact']is True for v in values),'mechanism_correct':sum(v['mechanism_correct']is True for v in values),
                'false_clean_mutants':sum(r['role']=='mutant'and r['arms'][arm]['false_clean']for r in subset),'false_accusation_bases':sum(r['role']=='base'and r['arms'][arm]['false_accusation']for r in subset)}
            if arm!='R15':
                arms[arm]['witness']={k:sum(v['witness'][k]is True for v in values)for k in ['input_valid','distinguishes','actual_correct','expected_correct']}
                arms[arm]['witness']['trustworthy_mutants']=sum(r['role']=='mutant'and trustworthy_witness(r['arms'][arm]['witness'])for r in subset)
                arms[arm]['witness']['actual_is_supplied_observation']=arm=='execution'
        metrics[split]=arms
    evaluation=metrics['evaluation'];gates={}
    for arm in ['self','execution']:
        a=evaluation[arm];b=evaluation['R15']
        gates[arm]=gate_result(gate,b['content_pairs']['successes'],a['strict_pairs']['successes'],a['witness']['trustworthy_mutants'],a['false_clean_mutants'],b['false_clean_mutants'])
    return {'splits':metrics,'gates':gates,'renderer_permitted':any(g['passed']for g in gates.values()),'authority':'agent source review, not human-verified','execution_caveat':'Continuation actual is supplied evidence; shared first-call actual is the independent prediction. Extra-call benefit is not separately isolated.'}
