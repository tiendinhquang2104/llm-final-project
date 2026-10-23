"""Freeze/report integrity on non-sensitive artificial fixtures."""
import importlib
import json
import pytest

@pytest.fixture
def cli():
    class Lazy:
        def __getattr__(self,name):
            try:return getattr(importlib.import_module('scripts.task3_two_pass_findings'),name)
            except ModuleNotFoundError:pytest.fail('findings experiment CLI missing')
    return Lazy()


def test_no_credit_unresolved_even_gold_clean(cli):
    values=cli.taxonomy_summary([[],['Lỗi logic']],[None,['Lỗi logic']])
    assert values['samples']==2 and values['exact_count']==1 and values['invalid']==1


def test_status_denominator_rejects_missing_and_duplicate_ids(cli):
    units=[{'sample_id':'A'},{'sample_id':'B'}]
    for rows in [[{'sample_id':'A'}],[{'sample_id':'A'},{'sample_id':'A'}]]:
        with pytest.raises(ValueError):cli.index_results(units,rows)


def test_verify_seal_rejects_mutation(cli,tmp_path):
    p=tmp_path/'x.json';p.write_text('{"v":1}')
    cli.seal_files(tmp_path,'seal.json',['x.json'])
    cli.verify_seal(tmp_path,'seal.json')
    p.write_text('{"v":2}')
    with pytest.raises(ValueError):cli.verify_seal(tmp_path,'seal.json')


def test_stage1_adapter_preserves_text_and_labels(cli):
    stage1={'taxonomy_error':['Lỗi logic'],'findings':[{'label':'Lỗi logic','error':'Exact assertion  \nwith whitespace.','problem_id':'P1','location':'f','evidence':'x'}]}
    assert cli.renderer_adapter(stage1)=={'taxonomy_error':['Lỗi logic'],'issues':[{'label':'Lỗi logic','note':'Exact assertion  \nwith whitespace.'}]}

@pytest.mark.parametrize('field',['statement','problems','grading_policy','exam_type','exam_id','source','split'])
def test_archive_binding_rejects_stale_prepared_metadata(cli,field):
    from types import SimpleNamespace
    attrs={'code':'int x;','gold_taxonomy':[],'target_feedback_level':'Level 1','statement':'Statement',
           'problems':[],'grading_policy':'Policy','exam_type':'single_problem','exam_id':'X','source':'synthetic','sample_id':'A'}
    raw=SimpleNamespace(**attrs);prepared=SimpleNamespace(**attrs,split='synthetic-train')
    setattr(prepared,field,'STALE')
    with pytest.raises(ValueError):cli.validate_prepared(prepared,raw)

@pytest.mark.parametrize('row',[{'sample_id':'A','status':'unresolved','output':{'taxonomy_error':[],'feedback':'Fake'}},
    {'sample_id':'A','status':'resolved','output':None}])
def test_status_output_contradiction_cannot_receive_credit(cli,row):
    with pytest.raises(ValueError):cli.index_results([{'sample_id':'A'}],[row])
