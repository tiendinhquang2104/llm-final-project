"""Protocol regressions: leakage and missing outputs must never earn clean credit."""
import pytest
from src.task3 import paired_review as p


def test_missing_and_fallback_cannot_earn_exact_clean():
    labels=['Lỗi logic','Lỗi style']
    rows=[{'gold':[], 'output':None}, {'gold':[], 'output':{'taxonomy_error':[]}, 'fallback':True},
          {'gold':['Lỗi logic'], 'output':{'taxonomy_error':['Lỗi logic']}}]
    m=p.taxonomy_metrics(rows,labels)
    assert m['exact']==1 and m['complete']==2 and m['eligible']==1
    assert m['zero_support_labels']==['Lỗi style'] and m['micro_f1']==1
    assert m['macro_f1_all']==0.5 and m['macro_f1_supported']==1


def test_missed_labels_stay_false_negative_when_output_missing():
    m=p.taxonomy_metrics([{'gold':['Lỗi logic'],'output':None}],['Lỗi logic'])
    assert m['per_label']['Lỗi logic']=={'support':1,'TP':0,'FP':0,'FN':1}


def test_blinding_keeps_whole_pair_and_hides_names():
    sources=[{'sample_id':'s1','source_sha256':'a','requested_level':2}]
    outputs={'R15':{'s1':{'taxonomy_error':['Lỗi logic'],'feedback':'A'}},
             'SFT':{'s1':{'taxonomy_error':[],'feedback':'B'}}}
    packet,key=p.blind_pairs(sources,outputs,seed=42)
    assert {r['output']['feedback']for r in packet}=={'A','B'}
    assert all(set(r)=={'sample_id','source_sha256','requested_level','candidate_id_blinded','output'}for r in packet)
    assert all(r['output']==outputs[key[r['candidate_id_blinded']]]['s1']for r in packet)
    assert not any(name in str(packet)for name in ['R15','SFT'])


def test_reject_duplicate_and_missing_review_rows():
    pairs=[{'sample_id':'x','candidate_id_blinded':'b','source_sha256':'h','requested_level':1}]
    with pytest.raises(ValueError):p.validate_review([],pairs)
    r={**pairs[0], 'source_findings':[], 'taxonomy_review':{}, 'feedback_review':{'usefulness':'0'}}
    assert p.validate_review([r],pairs)
    with pytest.raises(ValueError):p.validate_review([r,r],pairs)
    with pytest.raises(ValueError):p.validate_review([{**r,'source_sha256':'wrong'}],pairs)


def test_source_leakage_includes_renaming_and_near_variants():
    a={'sample_id':'a','code':'int f(int n){int s=0;for(int i=0;i<n;++i)s+=i;return s;}'}
    b={'sample_id':'b','code':'int g(int x){int total=0;for(int j=0;j<x;++j)total+=j;return total;}'}
    assert p.leakage_matches(a,[b])
    assert p.leakage_matches(a,[a])[0]['sample_id']=='a'
