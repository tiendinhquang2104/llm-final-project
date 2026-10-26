"""V2 policy and data bindings; training/encoding remain the native v1 infrastructure."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from src.task3.sft_v1_experiment import Journal

SELECTION_POLICY = {
    'version':'sft-v2-dev-joint-v1',
    'eligibility':'clean false-alarm targets <= native base and invalid targets <= native base',
    'eligible_order':['joint_successful desc','clean_false_alarms asc','faulty_l3_correct desc','mean_loss asc','step asc'],
    'fallback_order':['clean_false_alarms asc','joint_successful desc','faulty_l3_correct desc','mean_loss asc','step asc'],
    'joint':'valid + supported diagnosis + applicable essential location/condition + Level + Vietnamese; faulty L3 correct repair; L4 accurate explanation AND bounded verified solution',
    'uncertain_not_evaluable':'non-pass',
    'applicability':'location N/A for L1 or clean truthful status; L3 repair N/A only for clean; L4 requires explanation and code',
    'review':'source-grounded agent review, identity blinded where practical; not independent gold or an official score',
}
CALL_BUDGET = dict(logical_total=1120, verified_reuse=160, fresh_logical=960,
                   native_primary=720, ar15_logical=240, ar15_attempts_per_request=3,
                   ar15_physical=720, primary_physical=1440, smoke=2, physical_total=1442)


class BudgetJournal(Journal):
    def reserve(self,key,budget=None):
        reserved=self.reserved()
        if key in reserved: raise ValueError('generation already reserved: '+key)
        smoke=[k for k in reserved if k.startswith('smoke-')]
        ar15=[k for k in reserved if k.startswith('ar15-')]
        native=[k for k in reserved if not k.startswith(('smoke-','ar15-'))]
        if len(reserved)>=CALL_BUDGET['physical_total']: raise ValueError('physical ceiling exhausted')
        if key.startswith('smoke-'):
            if len(smoke)>=2: raise ValueError('smoke ceiling exhausted')
        elif key.startswith('ar15-'):
            request=key.rsplit('/',1)[0]+'/'
            if len(ar15)>=720 or sum(k.startswith(request) for k in ar15)>=3:
                raise ValueError('A/R15 physical/request ceiling exhausted')
        elif len(native)>=720: raise ValueError('native primary ceiling exhausted')
        self.append(dict(type='generation_reserved',key=key))


def select_checkpoint(candidates,base_false_alarms,base_invalid):
    if sorted(c['step'] for c in candidates)!=[120,240]: raise ValueError('two fixed checkpoints required')
    for c in candidates:
        if not math.isfinite(c['mean_loss']) or any(type(c[k]) is not int or c[k]<0 for k in
             ('clean_false_alarms','invalid','joint_successful','faulty_l3_correct')):
            raise ValueError('invalid candidate statistics')
    eligible=[c for c in candidates if c['clean_false_alarms']<=base_false_alarms and c['invalid']<=base_invalid]
    def order(c):
        tail=(-c['faulty_l3_correct'],c['mean_loss'],c['step'])
        return ((-c['joint_successful'],c['clean_false_alarms']) if eligible else
                (c['clean_false_alarms'],-c['joint_successful']))+tail
    chosen=min(eligible or candidates,key=order)
    return dict(step=chosen['step'],passes_preliminary_conditions=bool(eligible),candidates=candidates,
                eligible_steps=[c['step'] for c in eligible],native_base_limits=dict(
                    clean_false_alarms=base_false_alarms,invalid=base_invalid),policy=SELECTION_POLICY)


def joint_success(status,level,faulty,axes,l4_code):
    if status!='valid': return False
    if any(axes.get(k)!='pass' for k in ('diagnosis_supported','level_compliance','vietnamese_compliance')):
        return False
    location=axes.get('location_and_condition')
    if location!='pass' and not (location=='not_applicable' and (level==1 or not faulty)): return False
    if level==3 and faulty and axes.get('l3_repair_direction')!='pass': return False
    if level==4 and (axes.get('l4_explanation_quality')!='pass' or l4_code!='pass'): return False
    return True


def cross_level_consistency(rows):
    groups=defaultdict(list)
    for r in rows: groups[r['sample_id']].append(r)
    records=[]
    for sid,items in groups.items():
        levels=[r['level'] for r in items]
        if len(levels)!=len(set(levels)): raise ValueError('duplicate Level')
        complete=sorted(levels)==[1,2,3,4]
        invalid=any(r['status']!='valid' for r in items)
        signatures={tuple(sorted(r['parsed']['taxonomy_error'])) for r in items if r['status']=='valid'}
        records.append(dict(sample_id=sid,complete=complete,contains_invalid=invalid,
            consistent=complete and not invalid and len(signatures)==1,
            taxonomy_by_level={str(r['level']):r['parsed']['taxonomy_error'] if r['status']=='valid' else None for r in items}))
    return dict(sources=len(records),complete_sources=sum(r['complete'] for r in records),
        incomplete_sources=sum(not r['complete'] for r in records),sources_with_invalid=sum(r['contains_invalid'] for r in records),
        consistent_complete_valid_sources=sum(r['consistent'] for r in records),
        inconsistent_complete_valid_sources=sum(r['complete'] and not r['contains_invalid'] and not r['consistent'] for r in records),
        records=records)


def load_split(root,split='train'):
    """Validate all split bindings; render through the unchanged native v1 function."""
    from src.task3.sft_v1 import read_jsonl,sha256,native_prompt,INPUT_KEYS
    from src.task3.sft_v1_evaluation import _schema_error
    root=Path(root)
    parts=json.loads((root/'split-manifest.json').read_text())['partitions']
    if set(parts)!={'train','dev','test','final'} or split not in parts: raise ValueError('split policy')
    owners={};manifest={}
    for name,items in parts.items():
        for item in items:
            sid=item['source_id'];code=(root/'sources'/f'{sid}.cpp').read_text()
            if sha256(root/'sources'/f'{sid}.cpp')!=item['source_sha256']: raise ValueError('source hash')
            for kind,value in [('id',sid),('family',item['family_id']),('cluster',item['cluster']),('normalized',''.join(code.split()))]:
                key=kind,value
                if key in owners and owners[key]!=name: raise ValueError('cross-split binding: '+kind)
                owners[key]=name
            if name==split:
                if sid in manifest: raise ValueError('duplicate source')
                manifest[sid]=item
    labels=json.loads((root/'label_space.json').read_text())['taxonomy_error']
    records=read_jsonl(root/f'{split}.records.jsonl');data=read_jsonl(root/f'{split}.sft.jsonl')
    if len(records)!=4*len(manifest) or len(records)!=len(data): raise ValueError('target count')
    examples=[];coverage=defaultdict(list);seen=set()
    for record,row in zip(records,data):
        x=record['input'];sid=record['source_id'];eid=record['sample_id'];level=x['target_feedback_level']
        if eid in seen or sid not in manifest or record['split']!=split: raise ValueError('record binding')
        seen.add(eid);coverage[sid].append(level)
        if (set(x)!=INPUT_KEYS or type(level)is not int or level not in (1,2,3,4)
            or x['code']!=(root/'sources'/f'{sid}.cpp').read_text() or x['language']!='cpp11'
            or record['family_id']!=manifest[sid]['family_id'] or record['group_id']!=manifest[sid]['cluster']):
            raise ValueError('input/source whitelist')
        if (set(row)!={'prompt','completion'} or row['prompt']!=native_prompt(root,x,labels)
            or len(row['completion'])!=1 or set(row['completion'][0])!={'role','content'}
            or row['completion'][0]['role']!='assistant'): raise ValueError('native prompt mapping')
        completion=row['completion'][0]['content'];output=json.loads(completion)
        if output!=record['output'] or _schema_error(output,labels): raise ValueError('target schema')
        examples.append(dict(example_id=eid,sample_id=sid,level=level,prompt=row['prompt'],completion=completion,loss_weight=1.))
    if set(coverage)!=set(manifest) or any(sorted(v)!=[1,2,3,4] for v in coverage.values()): raise ValueError('Level coverage')
    return examples
