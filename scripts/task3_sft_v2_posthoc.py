#!/usr/bin/env python3
"""Post-hoc, offline descriptive evaluation; never grades, selects, or generates.

Read saved generation records, unchanged references and semantic reviews. Missing
or duplicate target IDs cannot count as valid empty taxonomy or joint success.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from scripts.task3_sft_v2_report import assemble_split
from scripts.task3_sft_v2_review import AXES, STATES, reviews
from src.task3.sft_v1 import read_jsonl
from src.task3.sft_v2 import load_split


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rate(n,d):
    return n/d if d else None


def balanced_joint(clean_joint,clean_targets,faulty_joint,faulty_targets):
    if not clean_targets or not faulty_targets:return None
    return .5*clean_joint/clean_targets+.5*faulty_joint/faulty_targets


def semantic_joint(status,level,faulty,dimensions,code_pass):
    """Recompute historical joint definition without rewriting any axis verdict."""
    if status!='valid':return False
    if any(dimensions.get(a)!='pass' for a in ('diagnosis_supported','level_compliance','vietnamese_compliance')):return False
    location=dimensions.get('location_and_condition')
    if location!='pass' and not(location=='not_applicable' and (level==1 or not faulty)):return False
    if faulty and level==3 and dimensions.get('l3_repair_direction')!='pass':return False
    return level!=4 or (dimensions.get('l4_explanation_quality')=='pass' and code_pass)


def taxonomy_scores(rows,valid_only=False):
    tp=fp=fn=invalid=exact=0;used=[]
    for x in rows:
        valid=x['status']=='valid'
        if valid_only and not valid:continue
        used.append(x);gold=set(x['gold_labels'])
        pred=set(x['labels']) if valid else set()
        tp+=len(gold&pred);fp+=len(pred-gold);fn+=len(gold-pred)
        invalid+=not valid;exact+=valid and gold==pred
    precision=tp/(tp+fp) if tp+fp else 0.0
    recall=tp/(tp+fn) if tp+fn else 0.0
    return dict(tp=tp,fp=fp,fn=fn,precision=precision,recall=recall,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0,
                targets=len(used),invalid_targets=invalid,exact_correct=exact)


def summarize_rows(rows):
    result={}
    for name,faulty in [('clean',False),('faulty',True)]:
        group=[x for x in rows if x['faulty']==faulty]
        counts=Counter(x['status'] for x in group)
        ids=lambda predicate:[x['example_id'] for x in group if predicate(x)]
        joint=ids(lambda x:x['joint_success'])
        result[name]=dict(targets=len(group),sources=len({x['source_id'] for x in group}),
            valid=counts['valid'],invalid=sum(n for s,n in counts.items() if s not in ('valid','missing_id','duplicate_id')),
            missing=counts['missing_id'],duplicate=counts['duplicate_id'],
            nonempty_taxonomy=sum(x['status']=='valid' and bool(x['labels']) for x in group),
            empty_taxonomy=sum(x['status']=='valid' and not x['labels'] for x in group),
            joint_success=len(joint),joint_rate=rate(len(joint),len(group)),joint_ids=joint,
            semantic_axes={a:dict(Counter(x['dimensions'][a] for x in group)) for a in AXES})
    result['targets']=len(rows);result['sources']=len({x['source_id'] for x in rows})
    result['valid']=sum(x['status']=='valid' for x in rows)
    result['invalid']=sum(x['status'] not in ('valid','missing_id','duplicate_id') for x in rows)
    result['status_counts']=dict(Counter(x['status'] for x in rows))
    result['semantic_axes']={a:dict(Counter(x['dimensions'][a] for x in rows)) for a in AXES}
    result['taxonomy']=dict(all_targets_conservative=taxonomy_scores(rows),valid_only=taxonomy_scores(rows,True),
        exact_match_all=dict(correct=sum(x['status']=='valid' and set(x['labels'])==set(x['gold_labels']) for x in rows),denominator=len(rows)))
    result['joint']=dict(successful=sum(x['joint_success'] for x in rows),targets=len(rows),
        rate=rate(sum(x['joint_success'] for x in rows),len(rows)))
    result['balanced_joint_success']=balanced_joint(result['clean']['joint_success'],result['clean']['targets'],result['faulty']['joint_success'],result['faulty']['targets'])
    l3=[x for x in rows if x['faulty'] and x['level']==3]
    repair=[x['example_id'] for x in l3 if x['status']=='valid' and x['dimensions']['l3_repair_direction']=='pass']
    supported=[x['example_id'] for x in l3 if x['status']=='valid' and x['dimensions']['l3_repair_direction']=='pass' and x['dimensions']['diagnosis_supported']=='pass']
    result['faulty_l3']=dict(targets=len(l3),sources=len({x['source_id'] for x in l3}),correct_repair_direction=len(repair),correct_repair_ids=repair,
        supported_correct_repair_direction=len(supported),supported_correct_repair_ids=supported,rate=rate(len(repair),len(l3)))
    l4=[x for x in rows if x['level']==4]
    result['l4']=dict(targets=len(l4),status_counts=dict(Counter(x['l4_status'] for x in l4)),
        code_pass=sum(x['code_pass'] for x in l4),explanation_pass=sum(x['dimensions']['l4_explanation_quality']=='pass' for x in l4),
        code_and_explanation_pass=sum(x['code_pass'] and x['dimensions']['l4_explanation_quality']=='pass' for x in l4),
        code_pass_explanation_nonpass=sum(x['code_pass'] and x['dimensions']['l4_explanation_quality']!='pass' for x in l4),
        explanation_verdicts=dict(Counter(x['dimensions']['l4_explanation_quality'] for x in l4)))
    return result


def aggregate_state(references,generations,quality,audits,state):
    refs={}
    for r in references:
        if r['sample_id'] in refs:raise ValueError('duplicate reference ID')
        refs[r['sample_id']]=r
    grouped=defaultdict(list)
    for g in generations:grouped[g['example_id']].append(g)
    rows=[]
    for eid,r in refs.items():
        records=grouped.get(eid,[]);level=r['input']['target_feedback_level'];sid=r['source_id']
        row=records[0] if len(records)==1 else None
        status=row['status'] if row else 'missing_id' if not records else 'duplicate_id'
        if row and (row['sample_id']!=sid or row['level']!=level):raise ValueError('source/Level binding '+eid)
        # Structural valid status must carry an actual schema-shaped payload.
        if status=='valid':
            payload=row.get('parsed')
            if not isinstance(payload,dict) or not isinstance(payload.get('taxonomy_error'),list) or not all(isinstance(v,str) for v in payload['taxonomy_error']) or not isinstance(payload.get('feedback'),str) or not payload['feedback'].strip():
                status='invalid_payload'
        labels=row['parsed']['taxonomy_error'] if status=='valid' else None
        q=quality.get((state,eid));dims={a:q['dimensions'].get(a,'not_evaluable') if q and status=='valid' else 'not_evaluable' for a in AXES}
        audit=audits.get((state,eid));l4_status=audit['status'] if audit else 'missing_audit' if level==4 else None
        code_pass=level==4 and l4_status=='all_authored_tests_passed' and status=='valid'
        faulty=bool(r['output']['taxonomy_error'])
        rows.append(dict(example_id=eid,source_id=sid,level=level,faulty=faulty,status=status,
            original_status=row['status'] if row else None,finish_reason=row.get('finish_reason') if row else None,
            labels=labels,gold_labels=r['output']['taxonomy_error'],dimensions=dims,
            review_present=q is not None,l4_status=l4_status,code_pass=code_pass,
            joint_success=semantic_joint(status,level,faulty,dims,code_pass)))
    result=summarize_rows(rows)
    duplicate_ids=sorted(eid for eid,items in grouped.items() if len(items)>1)
    extras=sorted(set(grouped)-set(refs));missing=sorted(set(refs)-set(grouped))
    invalid_rows=[x for x in rows if x['status'] not in ('valid','missing_id','duplicate_id')]
    result['coverage']=dict(targets=len(refs),generation_rows=len(generations),unique_generation_ids=len(grouped),
        valid=result['valid'],invalid=len(invalid_rows),invalid_ids=[x['example_id'] for x in invalid_rows],
        missing=len(missing),missing_ids=missing,duplicate=len(duplicate_ids),duplicate_ids=duplicate_ids,
        duplicate_extra_rows=sum(len(items)-1 for items in grouped.values()),extra=len(extras),extra_ids=extras,
        duplicate_expected_ids=sorted(set(duplicate_ids)&set(refs)),
        invalid_cause_and_finish_counts=dict(Counter(x['status']+'|'+str(x['finish_reason']) for x in invalid_rows)))
    result['by_level']={str(level):summarize_rows([x for x in rows if x['level']==level]) for level in range(1,5)}
    sources=defaultdict(list)
    for x in rows:sources[x['source_id']].append(x)
    consistent=[]
    for sid,items in sources.items():
        complete=sorted(x['level'] for x in items)==[1,2,3,4]
        invalid=any(x['status']!='valid' for x in items)
        signatures={tuple(sorted(x['labels'])) for x in items if x['status']=='valid'}
        consistent.append(dict(sample_id=sid,complete=complete,contains_invalid=invalid,
            consistent=complete and not invalid and len(signatures)==1,
            taxonomy_by_level={str(x['level']):x['labels'] for x in items}))
    result['cross_level_consistency']=dict(sources=len(consistent),
        complete_sources=sum(x['complete'] for x in consistent),incomplete_sources=sum(not x['complete'] for x in consistent),
        sources_with_invalid=sum(x['contains_invalid'] for x in consistent),
        consistent_complete_valid_sources=sum(x['consistent'] for x in consistent),
        inconsistent_complete_valid_sources=sum(x['complete'] and not x['contains_invalid'] and not x['consistent'] for x in consistent),records=consistent)
    result['source_denominators']=dict(sources=len(sources),all_targets_valid=sum(all(x['status']=='valid' for x in xs) for xs in sources.values()),
        any_target_invalid_or_unavailable=sum(any(x['status']!='valid' for x in xs) for xs in sources.values()),
        all_targets_joint_success=sum(all(x['joint_success'] for x in xs) for xs in sources.values()))
    result['rows']=rows
    return result


def write_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def report(oldrun,out,dataset):
    oldrun=oldrun.resolve();out=out.resolve();dataset=dataset.resolve()
    if out==oldrun or oldrun in out.parents:raise ValueError('cannot write into historical run')
    if out.exists():raise ValueError('output already exists; preserve previous post-hoc outputs')
    historical=read(oldrun/'analysis.json');selection=read(oldrun/'selection.json');manifest=read(oldrun/'manifest.json')
    results={};checks=[];inputs={}
    def check(name,actual,expected):
        checks.append(dict(check=name,actual=actual,expected=expected,agrees=actual==expected))
    for path in [oldrun/'analysis.json',oldrun/'selection.json',oldrun/'manifest.json']:
        inputs[str(path)]=digest(path)
    for split,states in STATES.items():
        references=read_jsonl(dataset/f'{split}.records.jsonl');examples=load_split(dataset,split)
        generated={s:read_jsonl(oldrun/s/'generations.jsonl') for s in states};quality=reviews(oldrun,split);audits={}
        for path in [dataset/f'{split}.records.jsonl',dataset/f'{split}.sft.jsonl',oldrun/'review-packets'/f'{split}-binding.private.json',*sorted((oldrun/'quality').glob(split+'-*.json'))]:inputs[str(path)]=digest(path)
        for state,gens in generated.items():
            inputs[str(oldrun/state/'generations.jsonl')]=digest(oldrun/state/'generations.jsonl')
            for row in gens:
                if row['level']==4:
                    path=oldrun/'l4'/state/row['example_id']/'result.json';audits[state,row['example_id']]=read(path);inputs[str(path)]=digest(path)
                    actual_digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
                    check(state+'/'+row['example_id']+'/L4-generation-binding',actual_digest,audits[state,row['example_id']].get('generation_sha256'))
        # Reuse the strict assembler solely to validate original joins and
        # cross-check independent recomputations below. Counts come from refs/gens.
        assembled=assemble_split(examples,references,generated,quality,audits)
        results[split]={}
        for state in states:
            result=aggregate_state(references,generated[state],quality,audits,state);results[split][state]=result
            baseline=assembled['states'][state];saved=historical['splits'][split]['states'][state]
            for label,expected in [('joined',baseline),('saved',saved)]:
                check(state+'/'+label+'/targets',result['targets'],expected['targets'])
                check(state+'/'+label+'/joint',result['joint']['successful'],expected['joint_successful'])
                check(state+'/'+label+'/valid',result['valid'],expected['metrics']['valid_outputs'])
                check(state+'/'+label+'/invalid',result['invalid'],expected['metrics']['invalid_outputs'])
                for level in ('1','2','3','4'):
                    check(state+'/'+label+'/L'+level+'/valid',result['by_level'][level]['valid'],expected['metrics']['by_level'][level]['valid_outputs'])
                    check(state+'/'+label+'/L'+level+'/invalid',result['by_level'][level]['invalid'],expected['metrics']['by_level'][level]['invalid_outputs'])
                check(state+'/'+label+'/faulty-l3',result['faulty_l3']['correct_repair_direction'],expected['faulty_l3_correct'])
                check(state+'/'+label+'/axes',result['semantic_axes'],expected['dimensions'])
                check(state+'/'+label+'/clean-false-alarms',result['clean']['nonempty_taxonomy'],expected['metrics']['clean_false_alarms']['targets']['false_alarms'])
                for key in ('tp','fp','fn','precision','recall','f1','targets','invalid_targets'):
                    check(state+'/'+label+'/taxonomy/'+key,result['taxonomy']['all_targets_conservative'][key],expected['metrics']['taxonomy']['all_targets_conservative'][key])
                check(state+'/'+label+'/cross-level',result['cross_level_consistency'],expected['consistency'])
    for split,state,group,field,expected in [
        ('final','v1-final','clean','nonempty_taxonomy',56),('final','v2-final','clean','nonempty_taxonomy',6),
        ('final','v1-final','clean','joint_success',10),('final','v2-final','clean','joint_success',53),
        ('final','v1-final','faulty','joint_success',17),('final','v2-final','faulty','joint_success',8),
        ('final','v1-final','faulty','empty_taxonomy',17),('final','v2-final','faulty','empty_taxonomy',54),
        ('final','v1-final','faulty','invalid',1),('final','v2-final','faulty','invalid',4),
        ('test','v1-regression','clean','joint_success',6),('test','v2-regression','clean','joint_success',15),
        ('test','v1-regression','faulty','joint_success',18),('test','v2-regression','faulty','joint_success',8),
        ('test','v1-regression','faulty','empty_taxonomy',11),('test','v2-regression','faulty','empty_taxonomy',38)]:
        check('requested/'+state+'/'+group+'/'+field,results[split][state][group][field],expected)
    final=results['final']['v2-final']
    check('requested/final-v2/L1-L3-valid',sum(final['by_level'][str(l)]['valid'] for l in (1,2,3)),120)
    check('requested/final-v2/L4-valid',final['by_level']['4']['valid'],32)
    check('requested/final-v2/invalid-cause-finish',final['coverage']['invalid_cause_and_finish_counts'],{'malformed_json|eos':8})
    discrepancies=[x for x in checks if not x['agrees']]
    # Verify the historical evidence stayed byte-for-byte unchanged while read.
    changed=[p for p,h in inputs.items() if digest(p)!=h]
    if changed:raise ValueError('historical input changed during offline analysis: '+str(changed))
    out.mkdir(parents=True)
    data=dict(version='task3-sft-v2-posthoc-v1',post_hoc=True,official_score=False,checkpoint_selection_unchanged=True,
        selected_step=selection['step'],historical_manifest_head=manifest['head'],
        balanced_joint_definition='0.5 * clean_joint/clean_targets + 0.5 * faulty_joint/faulty_targets; None when either class is absent',
        denominator_policy='Targets are requested Levels; sources are unique original programs. Invalid/missing/duplicate are separate; none become valid clean. Conservative taxonomy FN includes all gold labels for unavailable/invalid targets.',
        taxonomy_presence_caveat='Nonempty faulty taxonomy predicts error presence only, not correct label or supported diagnosis. Joint reuses existing semantic dimensions and is not taxonomy exact-match.',
        semantic_limit='Existing source-grounded agent judgments; not independent human gold; finite authored L4 checks do not prove full correctness. No new grading.',
        historical_run=str(oldrun),input_hashes=inputs,script_sha256=digest(__file__),splits=results)
    write_json(out/'tables.json',data)
    reconciliation=dict(post_hoc=True,all_agree=not discrepancies,checks=len(checks),discrepancies=discrepancies,details=checks,historical_inputs_unchanged=True)
    write_json(out/'reconciliation.json',reconciliation)
    columns=['split','state','level','targets','sources','valid','invalid','clean_targets','clean_nonempty','clean_empty','clean_invalid','clean_joint','faulty_targets','faulty_nonempty','faulty_empty','faulty_invalid','faulty_joint','balanced_joint','taxonomy_tp','taxonomy_fp','taxonomy_fn','taxonomy_precision','taxonomy_recall','taxonomy_f1','faulty_l3_correct','faulty_l3_targets','l4_code_pass','l4_explanation_pass','l4_code_pass_explanation_nonpass']
    with (out/'tables.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for split,states in results.items():
            for state,s in states.items():
                for level,x in [('all',s),*s['by_level'].items()]:
                    c=x['clean'];d=x['faulty'];t=x['taxonomy']['all_targets_conservative']
                    writer.writerow(dict(split=split,state=state,level=level,targets=x['targets'],sources=x['sources'],valid=x['valid'],invalid=x['invalid'],clean_targets=c['targets'],clean_nonempty=c['nonempty_taxonomy'],clean_empty=c['empty_taxonomy'],clean_invalid=c['invalid'],clean_joint=c['joint_success'],faulty_targets=d['targets'],faulty_nonempty=d['nonempty_taxonomy'],faulty_empty=d['empty_taxonomy'],faulty_invalid=d['invalid'],faulty_joint=d['joint_success'],balanced_joint=x['balanced_joint_success'],**{'taxonomy_'+k:t[k] for k in ('tp','fp','fn','precision','recall','f1')},faulty_l3_correct=x['faulty_l3']['correct_repair_direction'],faulty_l3_targets=x['faulty_l3']['targets'],l4_code_pass=x['l4']['code_pass'],l4_explanation_pass=x['l4']['explanation_pass'],l4_code_pass_explanation_nonpass=x['l4']['code_pass_explanation_nonpass']))
    lines=['# Phân tích hậu nghiệm Task 3 SFT v2','',
        'Phân tích **post hoc** từ generation, reference và review đã lưu; không gọi model, không tạo điểm ngữ nghĩa mới và không thay đổi checkpoint step '+str(selection['step'])+'. Dữ liệu synthetic và review agent không phải gold độc lập. Đây không phải điểm Task 3 chính thức.',
        '', 'Balanced joint = 0,5 × clean joint / clean target + 0,5 × faulty joint / faulty target. Chỉ số mô tả hậu nghiệm, không phải luật chọn checkpoint hồi tố. Target là một Level; bốn Level cùng source phụ thuộc nhau.',
        '', 'Nonempty taxonomy trên faulty chỉ dự đoán có lỗi; không bảo đảm đúng nhãn hoặc chẩn đoán có căn cứ. Joint giữ nguyên các verdict đã có và không đồng nghĩa với taxonomy exact-match. Invalid không được chuyển thành empty/clean. TP/FP/FN bảo thủ: invalid faulty đóng góp nhãn gold vào FN; invalid clean vẫn là thất bại.',
        '', '| Split/state | Target/source | Valid/invalid | Clean nonempty/empty/invalid | Clean joint | Faulty nonempty/empty/invalid | Faulty joint | Balanced joint | Taxonomy TP/FP/FN | P/R/F1 | Faulty L3 đúng | L4 code/explanation pass |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for split,states in results.items():
        for state,x in states.items():
            c=x['clean'];d=x['faulty'];t=x['taxonomy']['all_targets_conservative'];l3=x['faulty_l3'];l4=x['l4']
            lines.append(f'| {split}/{state} | {x["targets"]}/{x["sources"]} | {x["valid"]}/{x["invalid"]} | {c["nonempty_taxonomy"]}/{c["empty_taxonomy"]}/{c["invalid"]} | {c["joint_success"]}/{c["targets"]} | {d["nonempty_taxonomy"]}/{d["empty_taxonomy"]}/{d["invalid"]} | {d["joint_success"]}/{d["targets"]} | {x["balanced_joint_success"]:.4f} | {t["tp"]}/{t["fp"]}/{t["fn"]} | {t["precision"]:.4f}/{t["recall"]:.4f}/{t["f1"]:.4f} | {l3["correct_repair_direction"]}/{l3["targets"]} | {l4["code_pass"]}/{l4["explanation_pass"]} trên {l4["targets"]} |')
    lines+=['','A/R15-dev có 9 record đã lưu mang status=missing: controller không xuất payload cuối sau các attempt. Đây là 9 output invalid (4 clean, 5 faulty), không phải 9 ID vắng trong generation journal. Missing ID được đếm riêng bằng đối chiếu tập ID.',
        '', 'FINAL V1→V2: clean false alarm 56→6/80, clean joint 10→53/80; faulty joint 17→8/80, faulty empty 17→54/80, faulty invalid 1→4/80. Lợi ích joint chủ yếu ở clean; faulty bị bỏ sót nhiều hơn.',
        '', 'Observed regression V1→V2: clean joint 6→15/20, faulty joint 18→8/60, faulty empty 11→38/60. Balanced joint phản ánh hai mẫu số khác nhau.',
        '', 'FINAL V2: L1–L3 valid 120/120, L4 valid 32/40; tám invalid đều malformed_json với finish_reason=eos. L4 code và giải thích được đếm riêng; code đúng không cứu giải thích sai. Kiểm thử code hữu hạn không chứng minh đúng tuyệt đối.',
        '', f'Đối chiếu: {len(checks)} kiểm tra; {len(discrepancies)} sai khác. Mọi input lịch sử giữ nguyên hash. Chi tiết IDs, 7 trục semantic, per-Level, source denominator và cross-Level taxonomy nằm trong tables.json; bảng phẳng trong tables.csv; so sánh máy đọc trong reconciliation.json.',
        '', 'Tái lập (đích phải chưa tồn tại):', '', '```bash',f'/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_posthoc.py --historical-run {oldrun} --dataset {dataset} --out <fresh-directory>', '/workspace/llm-final-project/.venv-task3/bin/python -m unittest tests.test_task3_sft_v2_posthoc -v','```']
    if discrepancies:
        # Never write the requested example counts as established facts on disagreement.
        lines=[line for line in lines if not line.startswith(('FINAL V1→V2:','Observed regression V1→V2:','FINAL V2:'))]
        lines+=['','Có sai khác với số đã báo cáo; xem actual/expected trong reconciliation.json. Không ép số khớp.']
    (out/'posthoc.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return dict(output=str(out),all_agree=not discrepancies,states=sum(len(x) for x in results.values()),checks=len(checks),discrepancies=len(discrepancies))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--historical-run',type=Path,required=True);p.add_argument('--dataset',type=Path,default=REPO/'data/raw/task3-sft-v2');p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(report(a.historical_run,a.out,a.dataset),ensure_ascii=False))

if __name__=='__main__':main()
