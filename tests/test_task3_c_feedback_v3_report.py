"""Artificial regression for reused rubric versus current inference Level contract."""
from scripts import task3_c_feedback_v3 as cli


def test_review_policy_uses_current_frozen_Level_rules(monkeypatch):
    old={'official_levels':[{'level':'old'}],'rubric':{},'schema':{'cases':[{'outputs':[{}]}]},'cases':['OLD-STUDENT-DATA']}
    current=[{'level':'current official rule'}]
    monkeypatch.setattr(cli,'read',lambda p: current if p.name=='level-definitions.json'else old)
    policy=cli.review_policy()
    assert policy['official_levels']==current and 'cases'not in policy
    assert 'addresses_ban'in policy['rubric'] and 'placeholder_only'in policy['rubric']
