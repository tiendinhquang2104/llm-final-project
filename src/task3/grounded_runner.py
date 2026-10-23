"""Raw-before-parser journal, bounded retries, no semantic-clean fallback."""
from __future__ import annotations
import json
import os
from pathlib import Path
import time
from src.task3 import grounded as g
from src.task3.level_blind import digest, sha
from src.task3.dataset import write_json
from src.task3.round15_disclosure import disclosure_violations


class Journal:
    def __init__(self,out,backend,config,binding):
        self.out=Path(out);self.out.mkdir(parents=True,exist_ok=True)
        self.backend=backend;self.config=config
        self.identity=digest([binding,config])
        p=self.out/'identity.json'
        if p.exists():g.require(json.loads(p.read_text())=={'identity':self.identity},'journal identity changed')
        else:
            g.require(not (self.out/'attempts.jsonl').exists(),'unbound journal')
            write_json(p,{'identity':self.identity})
        self.path=self.out/'attempts.jsonl';self.rows={}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                row=json.loads(line);key=row['key']
                g.require(key not in self.rows,'duplicate journal key')
                g.require(row['identity']==self.identity and row['prompt_sha256']==digest(row['messages']),'journal binding corrupted')
                self.rows[key]=row

    def call(self,key,messages):
        h=digest(messages)
        if key in self.rows:
            row=self.rows[key];g.require(row['prompt_sha256']==h,'resume prompt changed');return row
        tokens=len(self.backend.tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True))
        g.require(tokens+self.config['max_new_tokens']<=self.config['context_limit'],'context overflow; never truncate source')
        row=dict(key=key,identity=self.identity,messages=messages,prompt_sha256=h,input_tokens=tokens)
        start=time.perf_counter()
        try:
            gen=self.backend.generate(messages,self.config)
            row.update(raw_text=gen.text,output_tokens=gen.output_tokens,latency_s=gen.latency_s,finish_reason=gen.finish_reason,error=None)
        except RuntimeError as exc:
            row.update(raw_text=None,output_tokens=None,latency_s=time.perf_counter()-start,finish_reason='runtime_error',error=str(exc))
        with self.path.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
        self.path.chmod(0o600);self.rows[key]=row
        return row


def diagnose(unit,journal,max_attempts=2):
    error=None;rejections=[]
    for attempt in range(1,max_attempts+1):
        row=journal.call(unit['request_id']+'/diagnosis/'+str(attempt),g.diagnosis_messages(unit['task'],error))
        if row['error']:return {'status':'unresolved','reason':row['error'],'rejections':rejections}
        try:
            d=g.parse_diagnosis(row['raw_text'],unit['task'])
            return dict(status='resolved' if d['publishable'] else 'unresolved',diagnosis=d,rejections=rejections,
                        reason=None if d['publishable'] else 'plausible_but_unverified')
        except (ValueError,TypeError,KeyError) as exc:
            error=str(exc);rejections.append(dict(attempt=attempt,reason=error))
    return dict(status='unresolved',reason=error,rejections=rejections)


def render(unit,d,journal,arm,max_attempts=2):
    codes=[];rejections=[];level=unit['level']
    for attempt in range(1,max_attempts+1):
        key=unit['request_id']+'/'+arm+'/'+str(attempt)
        row=journal.call(key,g.feedback_messages(d,level,unit['task'],arm,codes))
        if row['error']:return dict(status='unresolved',reason=row['error'],rejections=rejections)
        try:
            f=g.parse_feedback(row['raw_text'],d,level)
            violations=disclosure_violations(f['feedback'],level)
            if violations:
                codes=['L1_DETAIL_LEAK' if level==1 else 'L2_EXPLICIT_REPAIR' if level==2 else 'FULL_SOLUTION']
                rejections.append(dict(attempt=attempt,reason='lexical disclosure',details=violations));continue
            guard=None
            if arm=='C2':
                checked=journal.call(key+'/guard',g.guard_messages(d,level,f))
                if checked['error']:return dict(status='unresolved',reason=checked['error'],rejections=rejections)
                guard=g.parse_guard(checked['raw_text'])
                if not guard['accepted']:
                    codes=guard['reason_codes'] or ['UNSUPPORTED_CLAIM']
                    rejections.append(dict(attempt=attempt,reason='semantic_screen_rejected',guard=guard));continue
            return dict(status='resolved',output={'taxonomy_error':d['taxonomy_error'],'feedback':f['feedback']},
                        sentence_support=f['sentence_support'],taxonomy_support=d['taxonomy_support'],
                        guard=guard,rejections=rejections,semantic_correctness='not_independently_verified')
        except (ValueError,TypeError,KeyError) as exc:
            codes=['SCHEMA'];rejections.append(dict(attempt=attempt,reason=str(exc)))
    return dict(status='unresolved',reason='bounded_feedback_exhaustion',rejections=rejections)


def run_candidates(units,journal,out):
    results=[]
    for unit in units:
        diagnosis=diagnose(unit,journal,max_attempts=journal.config.get('diagnosis_max_attempts',2))
        arms={}
        for arm in ['C1','C2']:
            arms[arm]=render(unit,diagnosis['diagnosis'],journal,arm,max_attempts=journal.config.get('feedback_max_attempts',2)) if diagnosis['status']=='resolved' else dict(status='unresolved',reason=diagnosis['reason'])
        row=dict(request_id=unit['request_id'],sample_id=unit['sample_id'],level=unit['level'],diagnosis=diagnosis,arms=arms)
        results.append(row);write_json(Path(out)/'results.private.json',results)
        print(json.dumps(dict(completed=len(results),total=len(units),C1=arms['C1']['status'],C2=arms['C2']['status'])),flush=True)
    return results
