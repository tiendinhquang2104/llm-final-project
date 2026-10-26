"""Pure helpers for the frozen, single-attempt SFT v2 public run.

No model loading, compiler execution, inference or semantic grading occurs here.
Original statement/source and supplied diagnostics remain intact. Submission
payloads are always re-parsed from original responses and actual termination.
"""
from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path

from src.synth.feedback import FEEDBACK_LEVELS
from src.task3.input_fields import METADATA_FIELDS, PROBLEM_FIELDS, input_value, policy_value, project
from src.task3.sft_v1_evaluation import parse_response
from src.task3.sft_v1_experiment import Journal, write_json
from src.task3.submission import validate_submission


def _digest(value):
    """Exactly the persisted native runtime's object digest convention."""
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def _get(record,name,default=None):
    return record.get(name,default) if isinstance(record,dict) else getattr(record,name,default)


def _level(value):
    if type(value) is int and 1<=value<=4:return value
    if isinstance(value,str) and value in FEEDBACK_LEVELS:return FEEDBACK_LEVELS.index(value)+1
    raise ValueError('authoritative requested Level must be an official Level or integer 1..4')


def _json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)


def map_input(record,syntax):
    """Map official task-only fields into the six-field frozen native contract.

    Append deterministic attributed requirements to the original statement.
    IDs, teacher feedback, taxonomy and other annotation fields are never copied.
    """
    statement=_get(record,'statement');code=_get(record,'code');exam_type=_get(record,'exam_type')
    if not isinstance(statement,str) or not isinstance(code,str):raise ValueError('statement and original source must be text')
    if exam_type not in ('single_problem','multi_problem'):raise ValueError('unsupported submission mode')
    requested=_get(record,'requested_level',_get(record,'target_feedback_level'))
    level=_level(requested)
    problems=_get(record,'problems',[]) or []
    if not isinstance(problems,list):raise ValueError('structured problems must be a list')
    additions={}
    if problems:additions['official_subproblems']=[project(p,PROBLEM_FIELDS) for p in problems]
    policy=policy_value(_get(record,'grading_policy'))
    if policy not in ('',None,{}):additions['official_grading_policy']=policy
    for name in ('exam_metadata','input_metadata'):
        metadata=_get(record,name,{}) or {}
        selected=project(metadata,METADATA_FIELDS)
        if selected:additions['official_'+name]=selected
    if additions:
        statement+='\n\n[Official structured requirements; preserved public input metadata]\n'+_json(additions)
    supplied=_get(record,'compile_log')
    if supplied is not None and not isinstance(supplied,str):raise ValueError('supplied compile_log must be text or null')
    if not isinstance(syntax,dict):raise ValueError('local syntax evidence must be an object')
    stdout=syntax.get('stdout','') or '';stderr=syntax.get('stderr','') or ''
    if not isinstance(stdout,str) or not isinstance(stderr,str):raise ValueError('local syntax stdout/stderr must be text')
    status=syntax.get('status','unavailable')
    if not isinstance(status,str):raise ValueError('local syntax status must be text')
    # Successful syntax-only evidence with no diagnostics adds no misleading
    # semantic assertion to the familiar empty-log native contract.
    local_empty_pass=status in ('passed','pass','ok','success','compiled','syntax_ok','syntax_passed') and not stdout and not stderr
    logparts=[]
    if supplied:logparts.append('[Dataset supplied compile_log; verbatim]\n'+supplied)
    if not local_empty_pass:
        logparts.append('[Local syntax-only compiler; unchanged source, not executed]\n'+
                        'status: '+status+'\nstdout:\n'+stdout+'\nstderr:\n'+stderr)
    return dict(statement=statement,exam_type=exam_type,language='cpp11',code=code,
                compile_log='\n\n'.join(logparts),target_feedback_level=level)


def fixed_review_slice(rows,seed='task3-v2-public-review-20261026',per_level=12):
    """Select by input metadata only, hash-ordering within exam-family strata.

    Return original rows; selection never inspects responses. Families themselves
    are hash-ordered, then sampled round-robin within each authoritative Level.
    """
    if type(per_level) is not int or per_level<1:raise ValueError('positive per-Level review count required')
    ids=set();groups=defaultdict(lambda:defaultdict(list))
    for row in rows:
        sid=row.get('sample_id');level=_level(row.get('level'));family=row.get('exam_id')
        if not isinstance(sid,str) or not sid or sid in ids:raise ValueError('duplicate or invalid review input ID')
        if not isinstance(family,str) or not family:raise ValueError('review input requires an exam family')
        ids.add(sid);groups[level][family].append(row)
    chosen=[]
    hash_key=lambda value:hashlib.sha256((seed+'|'+value).encode()).hexdigest()
    for level in sorted(groups):
        families=groups[level]
        order=sorted(families,key=lambda f:(hash_key(f),f))
        queues={f:deque(sorted(families[f],key=lambda r:(hash_key(r['sample_id']),r['sample_id']))) for f in order}
        count=0
        while count<per_level and any(queues.values()):
            for family in order:
                if queues[family] and count<per_level:
                    chosen.append(queues[family].popleft());count+=1
    return chosen


def context_preflight(tokenizer,examples,settings,context=8192):
    """Tokenize actual full chat prompts, reserving frozen Level allowances."""
    if type(context) is not int or context<1:raise ValueError('positive context limit required')
    result=[];seen=set()
    for example in examples:
        sid=example['sample_id'];level=_level(example['level'])
        if sid in seen:raise ValueError('duplicate context-preflight ID')
        seen.add(sid)
        allowance=settings['max_new_tokens'][str(level)]
        if type(allowance) is not int or allowance<1:raise ValueError('positive frozen generation allowance required')
        ids=tokenizer.apply_chat_template(example['prompt'],tokenize=True,add_generation_prompt=True)
        if isinstance(ids,dict):ids=ids['input_ids']
        if hasattr(ids,'shape'):
            shape=ids.shape
            prompt_tokens=int(shape[-1])
        elif isinstance(ids,list) and ids and isinstance(ids[0],list):
            if len(ids)!=1:raise ValueError('expected one actual prompt')
            prompt_tokens=len(ids[0])
        else:prompt_tokens=len(ids)
        total=prompt_tokens+allowance
        result.append(dict(sample_id=sid,level=level,prompt_tokens=prompt_tokens,allowance=allowance,total_tokens=total,
            status='evaluable' if total<=context else 'context_preflight_failure',context_limit=context,
            prompt_sha256=_digest(example['prompt'])))
    return result


class PublicJournal(Journal):
    """Durable allowed-ID reservation journal; every reservation is one attempt.

    An interrupted reservation remains reserved on resume. Budget arguments from
    the native historical runtime cannot expand the frozen public ID budget.
    """
    def __init__(self,path,allowed):
        super().__init__(path)
        if not isinstance(allowed,dict) or any(not isinstance(k,str) or not k or not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v) for k,v in allowed.items()):
            raise ValueError('allowed journal keys must bind prompt SHA256 values')
        self.allowed=dict(allowed)
        self._validate(self.events())

    def _validate(self,events):
        reserved=set();completed=set()
        for event in events:
            if not isinstance(event,dict):raise ValueError('journal event must be an object')
            kind=event.get('type')
            if kind not in ('generation_reserved','generation_completed','generation_interrupted_unknown'):continue
            key=event.get('key')
            if key not in self.allowed:raise ValueError('unknown public journal key: '+str(key))
            if kind=='generation_reserved':
                if key in reserved:raise ValueError('duplicate generation reservation: '+key)
                if event.get('prompt_sha256')!=self.allowed[key]:raise ValueError('reservation prompt hash differs: '+key)
                reserved.add(key)
                if len(reserved)>len(self.allowed):raise ValueError('physical call ceiling exceeded')
            elif kind=='generation_completed':
                if key not in reserved:raise ValueError('completion without reservation: '+key)
                if key in completed:raise ValueError('duplicate generation completion: '+key)
                response=event.get('result')
                if not isinstance(response,dict):raise ValueError('completion missing result: '+key)
                if response.get('sample_id',key)!=key:raise ValueError('completion ID binding mismatch: '+key)
                if response.get('prompt_sha256',self.allowed[key])!=self.allowed[key]:raise ValueError('completion prompt hash differs: '+key)
                completed.add(key)
            elif key not in reserved or key in completed:
                raise ValueError('interruption without outstanding reservation: '+key)
        return reserved,completed

    def append(self,event):
        self._validate([*self.events(),event]);super().append(event)

    def reserve(self,key,ignored_native_budget=None):
        reserved,_=self._validate(self.events())
        if key not in self.allowed:raise ValueError('unknown public generation key: '+str(key))
        if key in reserved:raise ValueError('generation already reserved; never replay: '+key)
        if len(reserved)>=len(self.allowed):raise ValueError('public physical call ceiling exhausted')
        self.append(dict(type='generation_reserved',key=key,prompt_sha256=self.allowed[key]))


def export_submission(outdir,requested,results,labels):
    """Export a complete or explicitly partial official wrapper from raw bytes.

    Reject ambiguous identity coverage. Structural validity alone determines
    export eligibility; semantic quality never gates an otherwise valid payload.
    """
    outdir=Path(outdir)
    if not isinstance(requested,dict) or not requested:raise ValueError('nonempty ordered requested map required')
    for sid,level in requested.items():
        if not isinstance(sid,str) or not sid or level not in FEEDBACK_LEVELS:raise ValueError('invalid requested ID or official Level')
    rows={}
    for row in results:
        if not isinstance(row,dict):raise ValueError('generation result must be an object')
        sid=row.get('sample_id',row.get('example_id'))
        if sid not in requested:raise ValueError('extra generation ID: '+str(sid))
        if sid in rows:raise ValueError('duplicate generation ID: '+sid)
        if 'level' in row and _level(row['level'])!=FEEDBACK_LEVELS.index(requested[sid])+1:raise ValueError('requested Level binding mismatch: '+sid)
        rows[sid]=row
    predictions=[];unresolved=[]
    for sid,level in requested.items():
        row=rows.get(sid)
        parsed=parse_response(row.get('raw') if row else None,labels,row.get('finish_reason','missing') if row else 'missing')
        if parsed['status']=='valid':predictions.append(dict(sample_id=sid,output=parsed['parsed']))
        else:
            unresolved.append(dict(sample_id=sid,requested_level=level,status=parsed['status'],error=parsed['error'],
                finish_reason=row.get('finish_reason') if row else 'missing',raw_history=[row] if row else []))
    complete=not unresolved
    filename='predictions.json' if complete else 'partial.predictions.json'
    # Refuse mixing an earlier export with this frozen result set.
    protected=('predictions.json','partial.predictions.json','unresolved.json','validation.json','predictions.json.sha256','partial.predictions.json.sha256')
    if any((outdir/name).exists() for name in protected):raise ValueError('export artifacts already exist; choose a fresh export directory')
    outdir.mkdir(parents=True,exist_ok=True)
    path=outdir/filename;write_json(path,predictions)
    actual=json.loads(path.read_text(encoding='utf-8'))
    if actual!=predictions:raise ValueError('saved prediction bytes differ from planned export')
    subset={row['sample_id']:requested[row['sample_id']] for row in predictions}
    official=validate_submission(path,requested if complete else subset) if subset else None
    if not subset and actual!=[]:raise ValueError('empty partial export must contain exactly []')
    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    (outdir/(filename+'.sha256')).write_text(checksum+'  '+filename+'\n',encoding='ascii')
    if unresolved:write_json(outdir/'unresolved.json',unresolved)
    validation=dict(complete_export=complete,expected=len(requested),valid=len(predictions),unresolved=len(unresolved),
        path=str(path),prediction_path=str(path),sha256=checksum,saved_bytes_validated=True,
        official_validation=official,empty_partial_validation='Saved JSON array is empty; official validator requires a nonempty requested map.' if not subset else None,
        semantic_quality_required_for_export=False,exported_locally=True,submitted=False)
    write_json(outdir/'validation.json',validation)
    return validation
