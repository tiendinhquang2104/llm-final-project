from copy import deepcopy
from src.task3.prompt_crossover import AXES
from scripts.task3_sft_v4_report import joint_outcome, choose_example, comparative_evidence_known


def test_joint_transition_preserves_unresolved_code_and_unevaluable_semantics():
    row = dict(status='valid', level=3, faulty=True,
               parsed={'taxonomy_error': ['Lỗi logic'], 'feedback': 'x'},
               axes={a: 'pass' for a in AXES}, correct_status='pass', code_verdict='absent')
    assert joint_outcome(row) is True
    for axis in AXES:
        changed = deepcopy(row)
        changed['axes'][axis] = 'not_evaluable'
        assert joint_outcome(changed) is None
    for field in ['unsupported_claims', 'taxonomy_feedback_contradiction']:
        changed = deepcopy(row)
        changed[field] = 'uncertain'
        assert joint_outcome(changed) is None
    row['code_verdict'] = 'uncertain'
    assert joint_outcome(row) is None


def test_existing_category_can_reuse_unit_instead_of_being_called_absent():
    unit = dict(split='dev', family_id='f', level=3)
    assert choose_example([unit], {('dev', 'f', 3)}, {'f'}, lambda u: 'fixed') == unit
    assert choose_example([], set(), set(), lambda u: 'fixed') is None


def test_count_improvement_with_unresolved_pairs_cannot_support_recommendation():
    old = {k: {'unknown': 0} for k in ['diagnostic_pairs', 'supported_diagnosis', 'useful_l3_repair']}
    new = deepcopy(old)
    assert comparative_evidence_known(old, new, [], [])
    old['diagnostic_pairs']['unknown'] = 23
    new['diagnostic_pairs']['unknown'] = 22
    assert not comparative_evidence_known(old, new, [], [])
