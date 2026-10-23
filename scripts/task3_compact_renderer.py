#!/usr/bin/env python3
"""Offline oracle renderer isolation and artificial guard probes; never production."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from src.task3 import compact as c,compact_runner as runner,grounded as g
from src.task3.dataset import write_json
from src.task3.grounded_runner import Journal
from src.task3.level_blind import read,sha,digest
from task3_compact import OUT,CONFIG,FILES,backend


def oracle_cases():
    seal=read(OUT/'review/source-seal.json')
    for name,h in seal['reviewers'].items():g.require(sha(OUT/'review'/name)==h,'source review changed')
    source={x['sample_id']:x for x in read(OUT/'review/source-a.private.json')['cases']}
    units=read(OUT/'p1-selection.private.json');cases=[]
    for index,u in enumerate(units):
        ref=source[u['sample_id']];findings=ref['findings']
        # This is deliberately source-reviewed oracle data, not generated evidence.
        base=[{k:f[k]for k in ['scope','quote','observed','conflict','when','labels']}
              |({'overlap_reason':f['overlap_reason']}if 'overlap_reason'in f else {})for f in findings]
        d=c.parse(json.dumps(dict(verdict='error'if findings else 'clean',reason=ref['reason'],findings=base),ensure_ascii=False),u['task'],'whole')
        g.require(d['publishable'] and not d['rejected'],'oracle source binding failed')
        for f,original in zip(d['selected_findings'],findings):f['repair']=original['repair']
        d['provenance']='offline_oracle';d['source_review_sha256']=seal['reviewers']['source-a.private.json']
        cases.append(dict(unit=u,diagnosis=d))
        if index in [0,3]:
            modified={**u,'level':4,'request_id':u['request_id']+'@oracle-L4'}
            cases.append(dict(unit=modified,diagnosis=copy.deepcopy(d)))
    return cases


def guard_fixtures():
    f=dict(id='F1',subproblem='whole',source_span={'start_line':2,'end_line':2},observed='Phép tính hiện tại làm giảm tổng mỗi lượt.',
        conflict='Tổng chữ số bị lệch khi có chữ số dương.',repair='Điều chỉnh phép toán tích lũy.',quote='sum -= digit;',condition='Chữ số dương.',requirement_ref='statement')
    d=dict(status='confirmed_findings',selected_findings=[f],publishable=True)
    pairs=[(1,'Em nên thử đối chiếu kết quả bài tính tổng chữ số với thêm vài đầu vào nhé.',True),
        (1,'Ở dòng 2, phép trừ khiến tổng bị giảm.',False),
        (2,'Ở phần xử lý chữ số, tổng bị lệch vì phép tính hiện tại làm giảm giá trị mỗi lượt.',True),
        (2,'Em hãy đổi phép trừ sang phép cộng.',False),
        (2,'Thay phép trừ bằng phép cộng sẽ cho tổng đúng.',False),
        (2,'Bài này cần được kiểm tra lại.',False),
        (3,'Phần tính tổng làm giảm giá trị. Em cần điều chỉnh phép toán tích lũy để phản ánh tổng các chữ số.',True),
        (3,'Phần tính tổng làm giảm giá trị mỗi lượt.',False)]
    return [dict(id='policy-'+str(i+1),level=l,view=c.view(d,l,'tính tổng chữ số'),feedback=t,expected_accept=e)
            for i,(l,t,e)in enumerate(pairs)]


def freeze():
    d=OUT/'renderer';g.require(not d.exists(),'oracle experiment already frozen');d.mkdir()
    cases=oracle_cases();write_json(d/'cases.private.json',cases);write_json(d/'guard-fixtures.private.json',guard_fixtures())
    files=FILES+['scripts/task3_compact_renderer.py']
    manifest=dict(authority='OFFLINE ORACLE; no production score',source_seal_sha256=sha(OUT/'review/source-seal.json'),
        config=read(CONFIG),cases_sha256=sha(d/'cases.private.json'),fixtures_sha256=sha(d/'guard-fixtures.private.json'),
        code_sha256={n:sha(ROOT/n)for n in files},prompt_sha256=digest([runner.FEEDBACK_SYSTEM,runner.GUARD_SYSTEM]),
        fixed_counterfactuals='original8 Levels plus L4 on predetermined indices0,3; ten paired cases')
    write_json(d/'freeze.json',manifest);(d/'freeze.sha256').write_text(sha(d/'freeze.json')+'\n')
    print(json.dumps({'oracle_cases':len(cases),'guard_fixtures':8,'freeze_sha256':sha(d/'freeze.json')}))


def verify():
    d=OUT/'renderer';m=read(d/'freeze.json');g.require(sha(d/'freeze.json')==(d/'freeze.sha256').read_text().strip(),'oracle freeze changed')
    for name,field in [('cases.private.json','cases_sha256'),('guard-fixtures.private.json','fixtures_sha256')]:g.require(sha(d/name)==m[field],'oracle data changed')
    for n,h in m['code_sha256'].items():g.require(sha(ROOT/n)==h,'oracle code drift:'+n)
    return d,m


def run():
    d,m=verify();g.require(not (d/'run.private.json').exists(),'completed oracle run; no resampling')
    b=backend(m['config']);write_json(d/'runtime-before.private.json',b.runtime_metadata());j=Journal(d/'candidate',b,m['config'],sha(d/'freeze.json'));results=[]
    for case in read(d/'cases.private.json'):
        u=case['unit'];diagnosis=case['diagnosis'];arms={a:runner.render(u,diagnosis,j,a,oracle=True)for a in ['C1','C2']}
        results.append(dict(request_id=u['request_id'],sample_id=u['sample_id'],level=u['level'],arms=arms))
        write_json(d/'results.private.json',results);print(json.dumps({'oracle_processed':len(results),'C1':arms['C1']['status'],'C2':arms['C2']['status']}),flush=True)
    probes=[]
    for f in read(d/'guard-fixtures.private.json'):
        messages=[dict(role='system',content=runner.GUARD_SYSTEM),dict(role='user',content=json.dumps({'view':f['view'],'response':{'feedback':f['feedback']}},ensure_ascii=False))]
        try:
            verdict=g.parse_guard(runner.call(j,'fixture/'+f['id'],messages));actual=verdict['accepted'];error=None
        except (ValueError,RuntimeError,KeyError,TypeError)as exc:verdict=None;actual=None;error=str(exc)
        probes.append(dict(**f,actual_accept=actual,guard=verdict,error=error))
    write_json(d/'guard-probes.private.json',probes);verify()
    write_json(d/'run.private.json',dict(oracle_only=True,cases=len(results),
        completed={a:sum(r['arms'][a]['status']=='resolved'for r in results)for a in ['C1','C2']},
        guard_false_accept=sum(p['actual_accept']is True and not p['expected_accept']for p in probes),
        guard_false_reject=sum(p['actual_accept']is False and p['expected_accept']for p in probes),
        guard_parse_failure=sum(p['actual_accept']is None for p in probes),runtime=b.runtime_metadata(),replay=False))
    print(json.dumps(read(d/'run.private.json')),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['freeze','verify','run']);a=p.parse_args()
    {'freeze':freeze,'verify':verify,'run':run}[a.action]()
