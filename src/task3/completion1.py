"""Isolate one required problem while retaining verbatim background context."""
from __future__ import annotations

import copy
import json
import re

from src.task3 import completion16 as c
from src.task3.dataset import write_json
from src.task3.level_blind import digest

VERSION='v16-A-active-problem-projection-v1'
FOCUS_RULE='Only the active required problem is assessed in this call. Background requirements, prototypes and source are context, not additional output scopes. Every finding must use active_problem_id. Do not remap a claim about another problem to that ID. Report only supported diagnoses, without solutions.'


def focus_messages(messages,unit):
    result=copy.deepcopy(messages);body=json.loads(result[1]['content'])
    ids=body['recovery_scope']['problem_ids'];problems=c.old.task_payload(unit)['problems']
    if len(ids)!=1 or ids[0] not in {p['pid'] for p in problems}:raise c.RecoveryFailure('one known active problem required')
    statement=unit['task']['statement']
    headers=list(re.finditer(r'(?m)^\*\*Problem\s+\d+\b',statement))
    if len(headers)!=len(problems):raise c.RecoveryFailure('requirement boundaries unavailable; no guessed section')
    index=next(i for i,p in enumerate(problems) if p['pid']==ids[0])
    start=headers[index].start();end=headers[index+1].start() if index+1<len(headers) else len(statement)
    active=statement[:headers[0].start()]+statement[start:end]
    body.update(statement=active,problems=[problems[index]],problem_ids=ids,
                background_full_statement=statement,background_problems=problems)
    body={'active_problem_id':ids[0],'scope_rule':FOCUS_RULE,**body}
    result[0]['content']=('ACTIVE PROBLEM: '+ids[0]+'. '+FOCUS_RULE+'\n\n'+result[0]['content'].replace(
        'Inspect each required problem;', 'Inspect only the active required problem;'))
    result[1]['content']=json.dumps(body,ensure_ascii=False)
    return result


def complete_merge(baseline,recovered,order,hashes):
    merged=c.merge_outputs(baseline,recovered,order,hashes)
    if [r['sample_id'] for r in merged]!=list(order):raise c.RecoveryFailure('incomplete authoritative ID coverage')
    return merged


class FocusedRecoverer(c.Recoverer):
    def __init__(self,*args,reused=None,**kwargs):
        super().__init__(*args,**kwargs);self.reused=reused or {}

    def generate_scope(self,scope,purpose,prior=None):
        if purpose=='length' and scope['scope_id'] in self.reused:
            entry=copy.deepcopy(self.reused[scope['scope_id']])
            c.old.parse_findings(json.dumps(dict(findings=entry['findings'])),self.u)
            entry['reused_from_prior_run']=True;self.ledger.append(entry)
            return copy.deepcopy(entry['findings'])
        messages=c.v16.messages_findings(self.u,self.labels,'A')
        messages[0]['content']+='\n\n'+c.SCOPE_INSTRUCTION+('\n\n'+c.REASSESS_INSTRUCTION if purpose=='reassessment' else '')
        body=json.loads(messages[1]['content']);body['recovery_scope']=scope
        if prior is not None:body['unresolved_prior_claims']=prior
        messages[1]['content']=json.dumps(body,ensure_ascii=False)
        messages=focus_messages(messages,self.u);last=None
        for attempt in range(1 if purpose=='reassessment' else 2):
            current=copy.deepcopy(messages)
            if attempt:
                current[0]['content']+='\nReturn a complete concise replacement for this same active problem after the actual failure below. No prefix or unrelated problem IDs.'
                current.append(dict(role='user',content=json.dumps(dict(failure=last,previous_response=raw),ensure_ascii=False)))
            current,view=c.dv.prepare_messages(self.u,current,self.j.backend.tokenizer,self.j.config['findings_max_new_tokens'],self.j.config['context_limit'])
            row=self.j.call(self.u['sample_id'],'taxonomy',current,attempt=attempt,resolver_id=[purpose,scope['scope_id']])
            raw=row.get('raw_text') or '';result=c.inventory(row,self.u,view)
            path=self.j.out/'generations'/digest([self.u['sample_id'],purpose,scope['scope_id'],attempt])
            path.parent.mkdir(parents=True,exist_ok=True);path.with_suffix('.raw.txt').write_text(raw,encoding='utf-8')
            write_json(path.with_suffix('.audit.json'),dict(inventory=result,view=view,journal_key=row['key']))
            if result['findings'] is not None:
                if any(v['field']=='other' for v in result['violations']):
                    last=dict(reason='structural finding failure',violations=result['violations']);continue
                if any(f['problem_id'] not in scope['problem_ids'] for f in result['findings']):
                    last=dict(reason='finding outside active problem',allowed=scope['problem_ids']);continue
                fixed,failed=self.fields(result['findings'],purpose+':'+scope['scope_id'],view)
                if not failed:
                    c.old.parse_findings(json.dumps(dict(findings=fixed)),self.u)
                    self.ledger.append(dict(scope=scope,purpose=purpose,status='valid',journal_key=row['key'],findings=fixed))
                    return fixed
                if purpose=='reassessment':raise c.RecoveryFailure('reassessment fields still unresolved')
                self.ledger.append(dict(scope=scope,purpose=purpose,status='field_pending',journal_key=row['key'],failed_indices=sorted(failed)))
                return fixed,failed
            last=result['failure'] or dict(reason='structural failure')
        self.ledger.append(dict(scope=scope,purpose=purpose,status='unresolved',failure=last))
        raise c.RecoveryFailure('active-problem generation exhausted: '+str(last))
