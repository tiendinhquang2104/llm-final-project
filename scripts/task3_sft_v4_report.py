"""Offline V4 report/casebook/cost accounting; no training or generation."""
import argparse,html,json,hashlib,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.sft_v1 import read_jsonl,sha256
from src.task3.sft_v1_experiment import write_json
from src.task3.sft_v4 import metrics,diagnosis,useful_repair,pair_success,feedback_success
from scripts.task3_sft_v4 import OUT,load,verify,cell_map
from scripts.task3_fresh_eval_report import pre,table,ratio
from src.task3.prompt_crossover import call_state
from src.task3.sft_v4 import EvaluationJournal
from scripts.task3_base_pv3_control import verify_files


def joint_outcome(row):
    if (row['status'] != 'valid' or row['correct_status'] in ['uncertain', 'not_evaluable']
            or row.get('code_verdict') == 'uncertain'
            or any(row.get(k) in ['uncertain', 'not_evaluable'] for k in ['unsupported_claims', 'taxonomy_feedback_contradiction'])
            or any(v in ['uncertain', 'not_evaluable'] for v in row['axes'].values())):
        return None
    return feedback_success(row)


def choose_example(eligible, used, used_families, rank):
    return min(eligible, key=lambda u: ((u['split'], u['family_id'], u['level']) in used,
        u['family_id'] in used_families, rank(u)), default=None)


def comparative_evidence_known(old, new, old_rows, new_rows):
    for r in [old, new]:
        if any(r[k]['unknown'] for k in ['diagnostic_pairs', 'supported_diagnosis', 'useful_l3_repair']):
            return False
    return all(joint_outcome(r) is not None for r in old_rows + new_rows if not r['faulty'])


def comparison(left,right,fn):
    a={r['example_id']:r for r in left};b={r['example_id']:r for r in right}
    if set(a)!=set(b):raise ValueError('paired output population')
    groups=defaultdict(list)
    for eid in sorted(a):
        if any(a[eid][k]!=b[eid][k] for k in ['sample_id','level','family_id','faulty','gold_taxonomy']):raise ValueError('paired binding')
        x,y=fn(a[eid]),fn(b[eid]);kind='unknown' if x is None or y is None else 'both_pass' if x and y else 'left_only' if x else 'right_only' if y else 'both_fail'
        groups[kind].append(eid)
    return {k:dict(count=len(groups[k]),targets=groups[k]) for k in ['left_only','right_only','both_pass','both_fail','unknown']}


def build(out):
    m=verify(out);sel=load(out/'selection.json')
    if sha256(out/'selection.json')!=load(out/'selection.sha256.json')['sha256']:raise ValueError('selection seal')
    verify_files(sel['dev_evidence'])
    cells={'dev':['base','V3','step48','step96'],'test':['base','V3','selected']};allr={};allg={};mm={}
    for split,cc in cells.items():
        allr[split]={};allg[split]={};mm[split]={}
        ex=read_jsonl(out/f'dataset/{split}.examples.private.jsonl');expected={e['example_id'] for e in ex}
        for c in cc:
            rr=read_jsonl(out/split/c/'reviews.private.jsonl');gg=read_jsonl(out/split/c/'generations.jsonl')
            if len(rr)!=72 or {r['example_id'] for r in rr}!=expected:raise ValueError('all72 reviewed')
            gi={r['example_id']:r for r in gg}
            for r in rr:
                if any(r.get(k)!=v for k,v in gi[r['example_id']].items()):raise ValueError('review/generation binding')
            allr[split][c]=rr;allg[split][c]=gg;mm[split][c]=metrics(rr)
    if mm['dev']!=load(out/'dev-metrics.json'):raise ValueError('dev metrics changed after selection')
    write_json(out/'metrics.json',mm)
    paired={}
    for split,cc in cells.items():
        pairs=[('base','V3')]+[('V3',c) for c in cc if c not in ['base','V3']]
        paired[split]={}
        for a,b in pairs:
            ra,rb=allr[split][a],allr[split][b]
            f23=lambda rr:[r for r in rr if r['faulty'] and r['level']>1]
            f3=lambda rr:[r for r in rr if r['faulty'] and r['level']==3]
            pair_a={(p['family_id'],p['level']):p['diagnostic_pair_success'] for p in mm[split][a]['diagnostic_pairs']['details'] if p['level']>1}
            pair_b={(p['family_id'],p['level']):p['diagnostic_pair_success'] for p in mm[split][b]['diagnostic_pairs']['details'] if p['level']>1}
            trans=Counter('unknown' if pair_a[k] is None or pair_b[k] is None else 'both_pass' if pair_a[k] and pair_b[k] else 'left_only' if pair_a[k] else 'right_only' if pair_b[k] else 'both_fail' for k in pair_a)
            paired[split][a+'__'+b]=dict(diagnostic_pairs=dict(trans),diagnosis=comparison(f23(ra),f23(rb),diagnosis),repair=comparison(f3(ra),f3(rb),useful_repair),joint=comparison(ra,rb,joint_outcome))
    write_json(out/'paired-comparisons.json',paired)
    grouped={}
    for split,cc in cells.items():
        grouped[split]={}
        for c in cc:
            grouped[split][c]={}
            for fid in sorted({r['family_id'] for r in allr[split][c]}):
                rr=[r for r in allr[split][c] if r['family_id']==fid]
                grouped[split][c][fid]=dict(targets=6,sources=2,joint=sum(feedback_success(r) for r in rr),diagnosis=sum(diagnosis(r) is True for r in rr if r['faulty'] and r['level']>1),repair=sum(useful_repair(r) is True for r in rr if r['faulty'] and r['level']==3),clean_alarms=sum(r['status']=='valid' and bool(r['parsed']['taxonomy_error']) for r in rr if not r['faulty']))
    write_json(out/'source-family-summaries.json',grouped)
    journal=EvaluationJournal(out/'journal.jsonl',cell_map(out));events=journal.events();reserved=journal.reserved()
    if len(reserved)!=504:raise ValueError('exact504 evaluation reservations')
    train=load(out/'main/training-result.json');evid=load(out/'evidence-summary.json')
    loads=[e for e in events if e.get('type')=='base_model_load_completed']
    starts=[e for e in events if e.get('type')=='base_model_load_started']
    costs=dict(base_model_loads=dict(count=len(loads),completed=len(loads),attempts=len(starts),uncompleted_attempts=len(starts)-len(loads),wall_s=sum(e['wall_s'] for e in loads),events=loads),
        adapter_loads=dict(completed_cell_loads=sum(c!='base' for cc in cells.values() for c in cc),attempts_exact=None,wall_s=None,scope='Five distinct cell adapter loads have durable runtime-before/completion proofs; repeated/interrupted attempts and adapter-only timing were not separately instrumented.'),
        evaluation_load_intervals={s:load(out/s/'load-runtime.json') for s in cells},
        prefreeze_failed_validation=load(out/'prefreeze-failed-validation-costs.json'),training=train,
        training_steps=96,optimizer_smoke_steps=0,train_forward_calls=sum(e.get('type')=='train_forward' for e in events),teacher_forced_evaluation_forwards=0,
        generations=dict(reservations=504,completed=sum(e.get('type')=='generation_completed' for e in events),unknown=sum(bool(r.get('call_count_uncertain')) for split in allg for cc in allg[split].values() for r in cc),
            input_tokens=sum(r['input_tokens'] for split in allg for cc in allg[split].values() for r in cc if not r.get('call_count_uncertain')),output_tokens=sum(r['output_tokens'] for split in allg for cc in allg[split].values() for r in cc if not r.get('call_count_uncertain')),
            wall_s=sum(r['wall_s'] for split in allg for cc in allg[split].values() for r in cc)),
        cells={split:{c:load(out/split/c/'complete.json') for c in cc} for split,cc in cells.items()},evidence=evid,
        additional_claim_tests=load(out/'additional-claim-tests.private.json') if (out/'additional-claim-tests.private.json').exists() else dict(compiler_calls=0,runtime_calls=0,reason='No concrete unresolved executable claim required new tests beyond saved pair evidence.'),
        scope='Measured Qwen loads/main/generations and CppSandbox calls; CPU tokenizer/agent authoring/review tokens and monetary bill not instrumented. No inference-cost zero imputed for unknown calls.')
    write_json(out/'costs-and-runtime.json',costs)
    sources={r['sample_id']:r for r in read_jsonl(out/'dataset/sources.private.jsonl') if r['split'] in cells};gold={r['sample_id']:r for r in read_jsonl(out/'dataset/gold.private.jsonl')};fam={f['family_id']:f for f in load(out/'families.authored.private.json')}
    units=[]
    for split,cc in cells.items():
        chosen='selected' if split=='test' else f"step{sel['step']}"
        for fid in sorted({s['family_id'] for s in sources.values() if s['split']==split}):
            for level in [1,2,3]:
                ss=[s for s in sources.values() if s['split']==split and s['family_id']==fid]
                faulty=next(s for s in ss if gold[s['sample_id']]['faulty']);clean=next(s for s in ss if not gold[s['sample_id']]['faulty'])
                ri={c:{r['faulty']:r for r in allr[split][c] if r['family_id']==fid and r['level']==level} for c in cc}
                old=pair_success(ri['V3'][False],ri['V3'][True]) if level>1 else None;new=pair_success(ri[chosen][False],ri[chosen][True]) if level>1 else None
                alike=any(all(r['status']=='valid' for r in rr.values())
                    and bool(rr[False]['parsed']['taxonomy_error'])==bool(rr[True]['parsed']['taxonomy_error'])
                    and ((rr[False]['correct_status']=='pass' and rr[True]['correct_status']=='fail')
                        or (rr[False]['correct_status']=='fail' and rr[True]['correct_status']=='pass'))
                    for rr in ri.values())
                unit=dict(split=split,family_id=fid,level=level,faulty_source=faulty['sample_id'],clean_source=clean['sample_id'],rows=ri,chosen=chosen,old_pair=old,new_pair=new,alike=alike)
                units.append(unit)
    rank=lambda u:hashlib.sha256(f"{u['split']}/{u['family_id']}/{u['faulty_source']}/L{u['level']}".encode()).hexdigest()
    cats=[('correct_clean_faulty_discrimination',lambda u:u['new_pair'] is True),('both_treated_alike',lambda u:u['alike']),
        ('new_adapter_improvement',lambda u:u['old_pair'] is False and u['new_pair'] is True),('new_adapter_regression',lambda u:u['old_pair'] is True and u['new_pair'] is False),
        ('correct_L3_repair',lambda u:u['level']==3 and any(useful_repair(rr[True]) is True for rr in u['rows'].values())),
        ('incorrect_or_missing_L3_repair',lambda u:u['level']==3 and useful_repair(u['rows'][u['chosen']][True]) is False),
        ('cross_Level_taxonomy',lambda u:True),('compile_interface_behavior',lambda u:fam[u['family_id']]['category']=='compile_interface')]
    selected=[];used=set();usedfam=set()
    for category,predicate in cats:
        eligible=[u for u in units if predicate(u)]
        u=choose_example(eligible,used,usedfam,rank)
        selected.append(dict(category=category,unit=u,absent_reason=None if u else 'Không có ví dụ đạt tiêu chí trong các output đã review.'))
        if u:used.add((u['split'],u['family_id'],u['level']));usedfam.add(u['family_id'])
    while len(used)<8:
        unused=[u for u in units if (u['split'],u['family_id'],u['level']) not in used]
        u=choose_example(unused,used,usedfam,rank)
        if u is None:raise ValueError('insufficient real example units')
        selected.append(dict(category='deterministic_fill',unit=u,absent_reason=None))
        used.add((u['split'],u['family_id'],u['level']));usedfam.add(u['family_id'])
    write_json(out/'example-selection.json',dict(policy=load(out/'example-policy.json'),examples=[dict(category=e['category'],split=e['unit']['split'] if e['unit'] else None,family_id=e['unit']['family_id'] if e['unit'] else None,level=e['unit']['level'] if e['unit'] else None,
        correct_repair_systems=[c for c,rr in e['unit']['rows'].items() if e['unit']['level']==3 and useful_repair(rr[True]) is True] if e['unit'] else [],absent_reason=e['absent_reason']) for e in selected]))
    head='<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Task3 V4 diagnostic pairs</title><style>body{font:15px system-ui;background:#f6f7fa;margin:24px}section,article{background:white;border:1px solid #ccd;padding:16px;margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f2f5;padding:12px}.systems{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}article{min-width:0}[hidden]{display:none}</style>'
    book=[head,'<h1>V4 — toàn bộ dev/test:144 target,504 output</h1><p>Dữ liệu synthetic do agent soạn/review; không human-independent validation. Gold/evidence riêng tư, không thuộc input model. Review dùng opaque response IDs; casebook sau review hiển thị hệ thống để kiểm tra.</p><label>Tìm <input id="q" type="search"></label><label>Split <select id="sp"><option value="">Tất cả</option><option>dev</option><option>test</option></select></label><label>Level <select id="lv"><option value="">Tất cả</option><option>1</option><option>2</option><option>3</option></select></label>']
    for split,cc in cells.items():
        for eid in sorted({r['example_id'] for r in allr[split]['base']}):
            sample=next(r for r in allr[split]['base'] if r['example_id']==eid);s=sources[sample['sample_id']];g=gold[s['sample_id']]
            book+=[f'<section class="case" id="{eid}" data-sp="{split}" data-lv="{sample["level"]}"><h2>{split}/{eid} — {s["family_id"]} — '+('faulty' if g['faulty'] else 'clean')+'</h2>',
                '<details><summary>Đặc tả/source đầy đủ</summary>'+pre(s['statement'])+pre(s['code'])+'</details>',
                '<details><summary>Gold/private evidence tách khỏi modelinput</summary>'+pre(g)+pre(load(out/g['evidence_path']))+'</details><div class="systems">']
            for c in cc:
                r=next(r for r in allr[split][c] if r['example_id']==eid)
                book+=['<article class="system-panel"><h3>'+html.escape(c)+'</h3><h4>Raw</h4>'+pre(r['raw'])+'<h4>Parsed</h4>'+pre(r['parsed'])+'<h4>Verdict/reason</h4>'+pre({k:r.get(k) for k in ['axes','correct_status','unsupported_claims','taxonomy_feedback_contradiction','code_verdict','evidence','review_id']})+'<details><summary>Finish/token/time</summary>'+pre({k:r.get(k) for k in ['finish_reason','status','input_tokens','output_tokens','wall_s','call_count_uncertain']})+'</details></article>']
            book+=['</div></section>']
    book+=['<script>function f(){let q=document.getElementById("q").value.toLowerCase(),s=document.getElementById("sp").value,l=document.getElementById("lv").value;document.querySelectorAll(".case").forEach(x=>x.hidden=!(x.textContent.toLowerCase().includes(q)&&(!s||x.dataset.sp===s)&&(!l||x.dataset.lv===l)));}["q","sp","lv"].forEach(x=>document.getElementById(x).addEventListener("input",f));</script></html>']
    (out/'paired-casebook.html').write_text('\n'.join(book))
    ex=['# Ví dụ V4: cặp thật, chọn theo quy tắc đã freeze','']
    for e in selected:
        ex+=['## '+e['category'],''];u=e['unit']
        if u is None:ex+=[e['absent_reason'],''];continue
        ex += [f"{u['split']}/{u['family_id']}/L{u['level']}",'',fam[u['family_id']]['statement'],'']
        transition=lambda v:'unknown' if v is None else 'pass' if v else 'fail'
        ex += ['Joint V3 → '+u['chosen']+': '+', '.join(('faulty' if faulty else 'clean')+' '+transition(joint_outcome(u['rows']['V3'][faulty]))+' → '+transition(joint_outcome(u['rows'][u['chosen']][faulty])) for faulty in [False,True])+'.','']
        if u['level']==3:
            ex += ['Hệ thống có repair đúng/hữu ích trong ví dụ này: '+(', '.join(c for c,rr in u['rows'].items() if useful_repair(rr[True]) is True) or 'không có')+'.','']
        for faulty,sid in [(False,u['clean_source']),(True,u['faulty_source'])]:
            ex += [('FAULTY' if faulty else 'CLEAN')+' source:','','```cpp',sources[sid]['code'],'```','','Gold/evidence:','','```json',json.dumps(gold[sid],ensure_ascii=False,indent=2),'```','']
            for c,rr in u['rows'].items():
                r=rr[faulty];ex += [c+' raw/parsed/verdict:','','````json',json.dumps({k:r.get(k) for k in ['raw','parsed','axes','correct_status','unsupported_claims','taxonomy_feedback_contradiction','evidence']},ensure_ascii=False,indent=2),'````','']
            ex+=['Taxonomy theo L1/L2/L3:','','```json',json.dumps({c:[dict(level=r['level'],status=r['status'],taxonomy=r['parsed']['taxonomy_error'] if r['status']=='valid' else None) for r in allr[u['split']][c] if r['sample_id']==sid] for c in cells[u['split']]},ensure_ascii=False,indent=2),'```','']
    (out/'EXAMPLES.vi.md').write_text('\n'.join(ex))
    render_report(out,m,sel,mm,paired,costs,selected,allr)
    print(json.dumps(dict(status='reported',selected=sel['step'],fallback=sel['fallback'],metrics={s:{c:r['selection_counts'] for c,r in cc.items()} for s,cc in mm.items()}),ensure_ascii=False))


def render_report(out,m,sel,mm,paired,costs,examples,allr):
    headers=['Split/system','Pair diagnosis /24','Faulty diagnosis /24','Faulty L3 repair /12','Clean FA /36','Invalid /72','Joint /72']
    rows=[]
    for split,cc in mm.items():
        for c,r in cc.items():rows.append([split+'/'+c,ratio(r['diagnostic_pairs']['count'],24),ratio(r['supported_diagnosis']['count'],24),ratio(r['useful_l3_repair']['count'],12),ratio(r['clean_false_alarms'],36),ratio(r['invalid'],72),ratio(r['successful_feedback'],72)])
    primary=table(headers,rows)
    t=mm['test'];v3=t['V3'];new=t['selected']
    improve=new['diagnostic_pairs']['count']>v3['diagnostic_pairs']['count'];safe=new['useful_l3_repair']['count']>=v3['useful_l3_repair']['count'] and new['clean_successful']>=v3['clean_successful'] and new['clean_false_alarms']<=v3['clean_false_alarms']
    test_safeguards=(new['invalid']<=v3['invalid'] and new['disclosure_failures']<=v3['disclosure_failures']
        and new['disclosure_unknown']==0 and v3['disclosure_unknown']==0)
    evidence_known=comparative_evidence_known(v3,new,allr['test']['V3'],allr['test']['selected'])
    recommended=improve and safe and evidence_known and test_safeguards and sel['eligible_for_promotion'] and not sel['fallback']
    conclusion='Số cặp chẩn đoán thành công trên test tăng so với V3, không có giảm repair/clean success theo các phép đếm đã định và không còn uncertainty ở các so sánh chính; đây chỉ là ứng viên nghiên cứu cần đánh giá độc lập tiếp.' if recommended else 'Chưa có bằng chứng đủ để khuyến nghị triển khai: cần xem cả pair diagnosis, repair và clean assessment, không coi đổi thiên hướng khen/báo lỗi là thành công. Chênh lệch số pass là quan sát trên mẫu này.'
    if not evidence_known:conclusion+=' Các unknown trong so sánh chính vẫn chưa được giải quyết.'
    status_table=table(['Split/system','Clean joint /36','Faulty joint /36','Faulty empty /36','Faulty invalid /36','Both status /36 (unknown)','Disclosure pass/fail/unknown','Required content /72','VN /72','Taxonomy consistent /24'],[[s+'/'+c,ratio(r['clean_successful'],36),ratio(r['faulty_successful'],36),ratio(r['faulty_misses'],36),ratio(r['faulty_invalids'],36),str(sum(p['status_both_correct'] is True for p in r['diagnostic_pairs']['details']))+'/36 ('+str(sum(p['status_both_correct'] is None for p in r['diagnostic_pairs']['details']))+')',f"{r['disclosure_compliant']}/{r['disclosure_failures']}/{r['disclosure_unknown']}",ratio(r['required_content_met'],72),ratio(r['axes']['vietnamese_compliance']['pass'],72),ratio(r['taxonomy_cross_level']['consistent'],24)] for s,cc in mm.items() for c,r in cc.items()])
    level_table=table(['Split/system/Level','Joint /24','Clean /12','Faulty /12','Disclosure /24','Content /24'],[[s+'/'+c+'/L'+l,*[ratio(r['by_level'][l][k],den) for k,den in [('successful_feedback',24),('clean_successful',12),('faulty_successful',12),('disclosure_compliant',24),('required_content_met',24)]]] for s,cc in mm.items() for c,r in cc.items() for l in ['1','2','3']])
    pair_level=table(['Split/system','Pair L2 /12','Pair L3 /12','Pair unknown /24','Diagnosis unknown /24','Repair unknown /12'],[[s+'/'+c,ratio(r['diagnostic_pairs']['by_level']['2']['count'],12),ratio(r['diagnostic_pairs']['by_level']['3']['count'],12),str(r['diagnostic_pairs']['unknown']),str(r['supported_diagnosis']['unknown']),str(r['useful_l3_repair']['unknown'])] for s,cc in mm.items() for c,r in cc.items()])
    ex_table=table(['Category','Ví dụ thật','Hệ thống repair đúng nếu L3'],[[e['category'],f"{e['unit']['split']}/{e['unit']['family_id']}/L{e['unit']['level']}" if e['unit'] else e['absent_reason'],', '.join(c for c,rr in e['unit']['rows'].items() if e['unit']['level']==3 and useful_repair(rr[True]) is True) if e['unit'] else ''] for e in examples])
    GiB=1024**3;tr=costs['training'];tot=costs['generations']
    costs_table=table(['Phase','Calls/steps','Time(s)','VRAM allocated/reserved GiB'],[['Main train','96 steps/384 forwards',f"{tr['wall_s']:.3f}",f"{tr['peak_allocated_bytes']/GiB:.3f}/{tr['peak_reserved_bytes']/GiB:.3f}"]]+[[s+'/'+c,str(r['targets']),f"{r['generation_wall_s']:.3f}",f"{r['peak_allocated_bytes']/GiB:.3f}/{r['peak_reserved_bytes']/GiB:.3f}"] for s,cc in costs['cells'].items() for c,r in cc.items()])
    text=f'''# Task3 V4 — diagnostic paired fine-tuning

**Huấn luyện hoàn tất 96/96 bước optimizer, một epoch với 384 target; chọn checkpoint ở bước {sel['step']}, fallback={str(sel['fallback']).lower()}.** Số cặp chẩn đoán thành công trên test của adapter mới **{new['diagnostic_pairs']['count']}/24** so với V3 **{v3['diagnostic_pairs']['count']}/24**. Báo lỗi trên code clean (adapter mới/V3) **{new['clean_false_alarms']}/36 — {v3['clean_false_alarms']}/36**; repair đúng/hữu ích **{new['useful_l3_repair']['count']}/12 — {v3['useful_l3_repair']['count']}/12**. {conclusion}

## Phạm vi và thiết kế

88 family mới, 176 source, 528 target L1–L3: train64/128/384, dev12/24/72, test12/24/72. Quota12 compile/interface,20 condition/boundary/tie,20 state/loop/order,16 formula/integer/array/string,12 interaction/missing behavior,8IO. Phân bổ cố định trước authoring/modelresults. Các family/template gần nhau phát hiện trong cross-review được thay trước freeze; kiểm tra 1.726 source lịch sử không có exact/whitespace match. Giới hạn semantic/pretraining independence được nêu ở DATA_CARD/audit; không dùng code public hoặc old evaluation families làm training. Fresh-eval cũ vẫn là dữ liệu đã quan sát, không chạy lại 120 target.

P_v3 và schema giữ nguyên. Một LoRA mới từ Qwen/Qwen2.5-Coder-7B-Instruct revision c03e6d358207e414f1eca0bb1891e29f1db0e242, không load/merge/stack V3 để train. NF4 double quantization/BF16 compute, FP32 nonquantized sau native preparation, SDPA; r16/alpha32/dropout0.05 trên q/k/v/o/gate/up/down. AdamW hiện có, lr2e-5, cosine/warmup0.03, weight decay0, maxnorm1, microbatch1/accum4, seed42, context8192 không truncation, packingoff. Checkpoint48/96 chứa optimizer/scheduler/RNG;384 target xuất hiện đúng một lần. Hash toàn bộ byte của các tham số ngoài adapter trước/sau train không đổi; chỉ LoRA cập nhật.

Minibatch thật từ Trainer được kiểm tra trước bước optimizer đầu tiên: mask system/user/header/padding, supervise complete assistantJSON+termination, equal mean CE trong từng example rồi mean across examples, weight1. Dataloader train không nhận mẫu dev/test. Không chạy optimizer smoke (0 bước); teacher-forced evaluation có 0 forward, không dùng loss để chọn. So với proposal cũ: learning rate 2e-5 thay 1e-5, thêm V3 để đối chứng, 504 thay 360 lượt sinh, dùng metric cặp chẩn đoán và eligibility so với V3 theo yêu cầu mới.

Tất cả hệ thống dùng cùng P_v3, tokenizer và chat template, allowed syntax-onlycompiler view, greedy seed42 concurrency1, repetition_penalty1.1, max_time45s, max_new_tokens1024, contextguard32768, EOS151645/pad151643, native strict parser/termination. Không modelinput nào có pair/family IDs, gold, witness, counterpart hay reference. Dev có 288 lượt sinh; selection được ghi và hash trước 216 lượt test. Không retry, không chạy lại completed output. Mọi invalid/semantic failure vẫn nằm trong mẫu số.

## So sánh chính

{primary}

Pair success yêu cầu cả hai valid: clean empty taxonomy và truthful clean assessment, faulty tìm actual defect với đúng vị trí/condition và không material accusation sai.24 cơ hội family × L2/L3; disclosure và repair chấm riêng. Không suy ra diagnosis đúng chỉ từ nhãn khác rỗng, hoặc clean đúng chỉ từ nhãn rỗng. Kết luận trong văn bản và các khẳng định không có cơ sở được chấm riêng; uncertainty không được tính là pass.

{pair_level}

## Clean/faulty, schema, Level và consistency

{status_table}

{level_table}

Disclosure unknown chỉ đếm các output valid còn chưa kết luận; invalid được báo riêng và giữ trong mẫu số chính.

Các metric phụ chi tiết gồm textual-status/unsupported-claim counters, taxonomy–feedback contradiction, valid/invalid, taxonomy precision/recall/F1, per-source/family tại metrics.json và source-family-summaries.json. Taxonomy consistency là tính đồng nhất ba Level, có thể đồng nhất nhưng sai; không thay diagnosis. L1 không bị trừ vì không nêu cause bị cấm; L2 precision/multiple sentences được phép; L3 generic check-logic không thành repair hữu ích. Không có L4target và không claim bảo toàn L4.

## Quyết định checkpoint trước test

Chọn bước {sel['step']} chỉ từ dev. Eligibility count: cleanalarm/invalid/disclosurefailure không hơn V3dev; eligible steps {sel['eligible_steps']}. Fallback {sel['fallback']}; eligible_for_promotion preliminary {sel['eligible_for_promotion']}; unresolveddisclosure {sel['unresolved_disclosure']}. Ranking lexicographic: pair-success, usefulL3repair, supporteddiagnosis, lowercleanFA, earlierstep. Uncertaindisclosure được ghi riêng và chặn promotion-ready, không đổi count ranking đã yêu cầu. Passingeligibility không chứng minh cải thiện. selection.json/seal lưu dev evidence hashes và0test reservations khi chọn. Không dùng test để chọn lại checkpoint.

Candidate counts frozen: `{json.dumps(sel['candidates'],ensure_ascii=False)}`.

## Paired transitions và ý nghĩa

Test V3→selected diagnostic pairs: `{json.dumps(paired['test']['V3__selected']['diagnostic_pairs'],ensure_ascii=False)}`. Diagnosis/repair/joint target transitions và dev48/96 nằm đầy đủ trong paired-comparisons.json. Đây là paired family evidence, không coi ba Levels là ba chương trình độc lập.

Trên test, joint success tăng từ {v3['successful_feedback']}/72 lên {new['successful_feedback']}/72 nhờ clean joint tăng {v3['clean_successful']}/36 → {new['clean_successful']}/36. Faulty joint giảm {v3['faulty_successful']}/36 → {new['faulty_successful']}/36; faulty empty taxonomy tăng {v3['faulty_misses']}/36 → {new['faulty_misses']}/36, diagnosis được xác nhận giảm {v3['supported_diagnosis']['count']}/24 → {new['supported_diagnosis']['count']}/24. Xu hướng này phù hợp với việc thiên về đánh giá clean/khen ngợi, chưa phải cải thiện khả năng phân biệt lỗi. Một fixed recipe và mẫu authored nhỏ không cho phép quy nguyên nhân cho riêng data hay optimizer.

{conclusion} Observed pair-pass count increased={improve}; no counted repair/clean-success regression={safe}; comparative evidence fully known={evidence_known}; test schema/disclosure safeguard={test_safeguards}. Cần tách learning diagnosis thật khỏi chuyển sang always-clean/always-faulty bằng cả clean/faulty pair scores, supported cause và correct useful repair. Không suy từ nhiều defect labels, câu ngắn hơn hoặc loss thấp hơn. Không gán nguyên nhân hiệu ứng cho một data/optimizer choice riêng biệt; chỉ một fixed recipe và một authored dataset nhỏ.

## Ít nhất tám ví dụ thật

Quy tắc category+hash đã lưu trước generation; ưu tiên unit chưa dùng/family chưa dùng, giữ cả improvement/regression khi có; nhóm vắng được ghi rõ, rồi bổ sung unit theo hash để có ít nhất 8 ví dụ thật. Mỗi ví dụ có cả clean/faulty source, spec, outputs/verdicts và cross-Level taxonomy tại EXAMPLES.vi.md; toàn bộ 144 target và 504 output ở paired-casebook.html.

{ex_table}

Trong bảng ví dụ, `new_adapter_improvement` chỉ chuyển diagnostic-pair từ fail đã biết sang pass; không có trường hợp như vậy. Cải thiện clean joint được báo riêng: mỗi ví dụ ở EXAMPLES.vi.md ghi chuyển joint V3 → adapter mới cho cả clean và faulty, cùng toàn bộ raw output và lý do. Không gán nhãn cải thiện chẩn đoán cho một cải thiện chỉ ở clean.

## Chi phí và phục hồi

{costs_table}

Qwen base loads hoàn tất **{costs['base_model_loads']['count']}**, tổng load wall **{costs['base_model_loads']['wall_s']:.3f}s** (native loader events; post-load audits scoped riêng). Số lần thử load {costs["base_model_loads"]["attempts"]}, chưa hoàn tất {costs["base_model_loads"]["uncompleted_attempts"]}. Năm adapter cell loads có bằng chứng hoàn tất; thời gian adapter-only và số interrupted attempts không được đo riêng. Huấn luyện 96 bước, smoke 0, train forward 384; teacher-forced eval 0. Generation reservations 504, completions{tot['completed']}, unknown{tot['unknown']}; **{tot['input_tokens']} input tokens, {tot['output_tokens']} output tokens**, measured generationwall **{tot['wall_s']:.3f}s**. Peak train đo main Trainer interval, inference từngcell reset riêng và gồm residentadapter/cache; phasewall có thể gồm weight hash. Không phải tổng GPUmemory mọi process, không impute agentreviewtoken/hóađơn thành0.

Evidence giữ lại của dataset:176 lượt kiểm tra cú pháp + 264 lượt biên dịch đầy đủ; {costs['evidence']['runtime_calls']} runtimecases. Pythonoracle selfchecks riêng, không gọi exhaustiveC++ tests. Novel-model-claim extra compiler/runtimecalls: {costs['additional_claim_tests']['compiler_calls']}/{costs['additional_claim_tests']['runtime_calls']}. Lần IX001 thất bại trước freeze thêm 2 lượt cú pháp + 2 lượt biên dịch đầy đủ (tổng compiler đã biết là 444); runtime thêm ít nhất 2, số chính xác và timing không lưu bền vững, tổng runtime tối thiểu 2.706. Prefreeze witness/overlap fixes lưu log và chronology, không có postfreezegold âmthầm thay đổi. Checkpoint/journal parity chặn optimizer replay; unresolved generation reservation không được gọi lại. Chi tiết mọi failure/recovery trong journals/logs/audits.

## Giới hạn, artifacts và một bước tiếp

Dữ liệu synthetic do agents soạn/kiểm chứng/review, không human-independent validation. Review panels dùng opaque IDs nhưng tác giả đã thấy specification/evidence; không claim blind human study. Finite tests không chứng minh universal correctness, corpus scan không chứng minh pretraining independence; test model outputs chỉ quan sát sau selection. Unknowns/disputes phải giữ ở uncertainty-records.private.json; nếu có golderror thì original giữ nguyên và versionedsensitivity riêng. Không có điểm chính thức mới hoặc khẳng định hoàn hảo.

Checkpoint được chọn: `{sel['checkpoint']}`. Các checkpoint48/96 và checkpoint-identity.json nằm dưới `{out/'main'}`. Thư mục artifact tuyệt đối `{out}` chứa dataset/DATA_CARD.md, split-manifest/verifiedsources/gold/evidence, targetconsistency, manifest/seal/preflight, actualtrainingarguments/PEFTconfig/realGPUminibatch/traininglog/checkpointstates, all dev/test rawparsed/reviews, selection/seal, metrics/pairedcomparisons/sourcefamily, casebook/EXAMPLES, costs, uncertainty, reproduction/resumecommands và finalverification.

**Một bước tiếp theo:** giữ A với điểm đã báo cáo **0.3834** làm baseline nộp bài; nhờ người đánh giá độc lập thẩm định 12 family test và các repair/dispute trước bất kỳ thử nghiệm triển khai công khai. Không trainthêm, publicinference, submit, commit, push hay upload trong task này.
'''
    text=text.replace('dev בלבד','dev only')
    (out/'REPORT.vi.md').write_text(text)
    write_json(out/'decision.json',dict(training_completed=True,selected_step=sel['step'],fallback=sel['fallback'],test_pair_pass_count_increased_vs_V3=improve,comparative_evidence_known=evidence_known,test_schema_disclosure_safeguards=test_safeguards,no_counted_repair_clean_regression=safe,research_candidate_for_further_independent_testing=recommended,submission_baseline='A, reported0.3834 unchanged',new_official_score=None,next_action='Independent human review of12testfamilies/repairs/disputes; no public inference or submission.'))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,default=OUT);args=a.parse_args();build(args.out.resolve())
