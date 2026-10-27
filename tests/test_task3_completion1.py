import copy
import json
from pathlib import Path

import pytest

from src.task3 import completion16 as c
from src.task3 import completion1 as focused
from src.task3 import arm_d_plus_v16 as v16
from tests.test_task3_completion16 import unit, finding


def multi_unit():
    u=unit()
    u['task']['statement']='Shared declarations.\n**Problem 1 (1 point).** Read records.\n**Problem 2 (4 points).** Build a list in array order.\n'
    u['task']['problems']=[dict(pid='P1',prototype='void prob1();'),dict(pid='P2',prototype='void prob2();')]
    return u


def test_focus_has_one_active_problem_without_losing_original_context():
    u=multi_unit();messages=v16.messages_findings(u,list(c.old.DEFINITIONS),'A')
    body=json.loads(messages[1]['content']);body['recovery_scope']=dict(scope_id='problem:P2',problem_ids=['P2'])
    messages[1]['content']=json.dumps(body);before=copy.deepcopy(messages)
    fixed=focused.focus_messages(messages,u)
    new=json.loads(fixed[1]['content'])
    assert [p['pid'] for p in new['problems']]==new['problem_ids']==['P2']
    assert 'Build a list' in new['statement'] and 'Read records' not in new['statement']
    assert new['background_full_statement']==u['task']['statement']
    assert new['background_problems']==body['problems'] and new['sources']==body['sources']
    assert 'Inspect each required problem' not in fixed[0]['content']
    assert messages==before


def test_unknown_or_multiple_active_problem_is_rejected():
    u=multi_unit();m=v16.messages_findings(u,list(c.old.DEFINITIONS),'A')
    for ids in (['P9'],['P1','P2']):
        body=json.loads(m[1]['content']);body['recovery_scope']=dict(problem_ids=ids)
        with pytest.raises(ValueError):focused.focus_messages([m[0],dict(role='user',content=json.dumps(body))],u)


def test_reused_valid_scope_does_not_access_journal():
    u=unit();entry=dict(scope=dict(scope_id='problem:P1',problem_ids=['P1']),purpose='length',status='valid',journal_key='old-key',findings=[finding()])
    r=focused.FocusedRecoverer(u,None,[],list(c.old.DEFINITIONS),{},reused={'problem:P1':entry})
    assert r.generate_scope(entry['scope'],'length')==[finding()]
    assert r.ledger[0]['reused_from_prior_run'] and r.ledger[0]['journal_key']=='old-key'
    assert 'reused_from_prior_run' not in entry


def test_archived_p2_raw_stays_out_of_scope_and_is_not_filtered():
    p=Path('outputs/task3/v1.6-completion16-20261024')
    if not p.exists():pytest.skip('local archived run not distributed')
    u=next(u for u in json.loads((p/'inputs.private.json').read_text()) if u['sample_id']=='Class01-Test1-S09')
    rows=map(json.loads,(p/'attempts.jsonl').read_text().splitlines())
    row=next(r for r in rows if r['sample_id']==u['sample_id'] and r['resolver_id']==['length','problem:P2'] and r['attempt']==0)
    raw=c.inventory(row,u)['findings'];assert {f['problem_id'] for f in raw}=={'P1','P2','P3','P4'}
    fixed=focused.focus_messages(row['messages'],u)
    assert json.loads(fixed[1]['content'])['problem_ids']==['P2']
    assert len(raw)==10  # Historical rejected content remains intact, never salvaged by filtering.


def test_complete_merge_requires_missing_id_and_preserves_every_baseline_output():
    a=dict(sample_id='a',output=dict(taxonomy_error=[],feedback='Gốc'))
    b=dict(sample_id='b',output=dict(taxonomy_error=[],feedback='Mới'))
    hashes={'a':c.object_hash(a['output'])}
    with pytest.raises(ValueError):focused.complete_merge([a],[],['a','b'],hashes)
    assert focused.complete_merge([a],[b],['b','a'],hashes)==[b,a]
    with pytest.raises(ValueError):focused.complete_merge([{**a,'output':{**a['output'],'feedback':'Changed'}}],[b],['a','b'],hashes)
