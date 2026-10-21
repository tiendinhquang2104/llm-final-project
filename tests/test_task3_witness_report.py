import copy
import pytest
from scripts.task3_witness_report import apply_addendum, validate_membership, execution_summary, witness_success


def packet():
    pairs=[];selection=[]
    for i in range(24):
        p={'pair':{'pair_id':str(i),'family':f'family{i}','split':'development' if i<6 else 'evaluation','ids':{}},'members':{}}
        for role in ['base','mutant']:
            sid=f'{i}-{role}';p['pair']['ids'][role]=sid
            p['members'][role]={'sample_id':sid,'review':{'diagnosis':{'raw_first_requirement_paraphrase':True}}}
            selection.append({'sample_id':sid,'pair_id':str(i),'family':f'family{i}','split':p['pair']['split'],'member_private':role})
        pairs.append(p)
    return pairs,selection


def test_addendum_applied_without_mutating_sealed_packet_and_bound_to_parent():
    pairs,_=packet();old=copy.deepcopy(pairs)
    add={'parent_review_sha256':'hash','changes':[{'sample_id':'0-base','pair_id':'0','member':'base','diagnosis_flag_patch':{'raw_first_requirement_paraphrase':False}}]}
    new=apply_addendum(pairs,add,'hash')
    assert new[0]['members']['base']['review']['diagnosis']['raw_first_requirement_paraphrase'] is False
    assert pairs==old
    with pytest.raises(ValueError):apply_addendum(pairs,add,'wrong')
    add['changes'][0]['sample_id']='unknown'
    with pytest.raises(ValueError):apply_addendum(pairs,add,'hash')


def test_membership_checks_unique_ids_role_family_and_split():
    pairs,selection=packet();validate_membership(pairs,selection)
    for mutate in [lambda p:p[1]['members']['base'].update(sample_id='0-base'),lambda p:p[0]['pair'].update(family='wrong'),lambda p:p[0]['pair'].update(split='evaluation')]:
        bad=copy.deepcopy(pairs);mutate(bad)
        with pytest.raises(ValueError):validate_membership(bad,selection)


def test_execution_claims_are_recomputed_from_captured_results():
    case={'expected_stdout':'2','actual':{'executed':True,'returncode':0,'timeout':False,'stdout':'2'}}
    base={'compiler':{'status':'pass'},'cases':[case]};mutant=copy.deepcopy(base);mutant['cases'][0]['actual']['stdout']='1'
    p={'pair':{'tests':[{'expected_stdout':'2'}]},'hidden_execution':{'members':{'base':base,'mutant':mutant}}}
    assert execution_summary([p])['baseline_test_match'] is True
    assert execution_summary([p])['all_mutants_have_verified_witness_or_diagnostic'] is True
    base['cases'][0]['actual']['stdout']='3'
    with pytest.raises(ValueError):execution_summary([p])


def test_clean_decision_cannot_pass_on_a_witness_that_contradicts_it():
    score={'input_valid':True,'actual_correct':True,'expected_correct':True,'distinguishes':True}
    assert not witness_success('no_defect_in_scope',score,True,None)
    score['distinguishes']=False
    assert witness_success('no_defect_in_scope',score,True,None)
