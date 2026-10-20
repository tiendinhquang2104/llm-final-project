from tests.task3_discovery_cases import development_cases,independent_cases
from src.task3.schema import code_hash
import pytest


def test_train_check_fixtures_are_disjoint_by_problem_group_and_code():
    from src.task3.discovery_eval import assert_isolated
    assert_isolated(development_cases(),independent_cases())
    with pytest.raises(ValueError):assert_isolated(development_cases(),development_cases())
    # Renaming or whitespace is not an independent check case.
    from dataclasses import replace
    c=development_cases()[0]
    with pytest.raises(ValueError):assert_isolated([c],[replace(c,name='other',exam='other',group='other',code='int main( ){ return 2; }')])


def test_metrics_separate_finding_accuracy_from_label_agreement():
    from src.task3.discovery_eval import score_findings
    expected=[{'taxonomy_group':'Lỗi logic','source_span':{'start':10,'end':15}}]
    predicted=[{'taxonomy_group':'Lỗi logic','source_span':{'start':50,'end':55}}]
    score=score_findings(expected,predicted)
    assert score['tp']==0 and score['fp']==1 and score['fn']==1
    assert score['label_exact'] is True


def test_runner_rejects_evaluation_splits_before_reading():
    from src.task3.discovery_eval import load_train_rows
    for split in ('real-val','public','synthetic-heldout','quarantine'):
        with pytest.raises(ValueError):load_train_rows('/ABSENT',split)


def test_gold_and_teacher_mutation_cannot_change_inference_input_or_findings():
    from src.task3.discovery_eval import inference_input
    from src.task3.discovery import discover
    row={'code':'int main(){return 0;}','statement':'Return zero.','problems':[],
         'gold_taxonomy':['Lỗi thuật toán'],'gold_feedback':'Invent a claim.','provenance':{'oracle':'bad'}}
    evidence={'status':'compiled','diagnostic':''}
    original=inference_input(row,evidence)
    row.update(gold_taxonomy=[],gold_feedback='Everything is correct.',provenance={'oracle':'different'})
    assert inference_input(row,evidence)==original
    assert discover(inference_input(row,evidence))==discover(original)


def test_span_agreement_is_explicitly_not_a_factual_metric():
    from src.task3.discovery_eval import score_findings
    finding={'taxonomy_group':'Lỗi logic','source_span':{'start':1,'end':3}}
    fabricated=dict(finding,observed_fact='unsupported',cause='wrong',evidence={})
    result=score_findings([finding],[fabricated])
    assert result['tp']==1
    assert result['metric_kind']=='taxonomy_and_span_agreement_not_semantic_correctness'
