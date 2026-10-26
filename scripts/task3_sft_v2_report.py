#!/usr/bin/env python3
"""Offline v2 analysis and paired casebooks from completed, reviewed artifacts.

This command never imports a model, starts a compiler, creates a review, modifies
frozen scientific inputs, or retries generation. Missing evidence is an error.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime
from html import escape
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.sft_v1 import read_jsonl,sha256
from src.task3.sft_v1_evaluation import aggregate_metrics
from src.task3.sft_v1_experiment import write_json
from src.task3.sft_v2 import load_split,cross_level_consistency,joint_success,SELECTION_POLICY
from scripts.task3_sft_v2_review import AXES,STATES,reviews,summarize

VERDICTS={'pass','fail','uncertain','not_applicable','not_evaluable'}
COUNTS={'dev':80,'final':160,'test':80}
BOOKS={'dev':'dev-paired.html','final':'final-paired.html','test':'regression-paired.html'}
HISTORICAL={'A/R15':0.3834,'B':0.3247,'older_strict_pipeline':0.1547}


def json_read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def indexed(items,key='example_id'):
    result={}
    for item in items:
        if item[key] in result:raise ValueError('duplicate '+key+': '+item[key])
        result[item[key]]=item
    return result


def assemble_split(examples,source_records,generations,quality,audits):
    """Join actual evidence, then recompute every denominator from joined rows."""
    by_id=indexed(examples)
    source=indexed(source_records,'sample_id')
    if set(source)!=set(by_id):raise ValueError('source/gold target coverage')
    states=list(generations);joined={s:[] for s in states};targets=[]
    if not states:raise ValueError('no comparison states')
    by_state={s:indexed(rows) for s,rows in generations.items()}
    for state in states:
        if set(by_state[state])!=set(by_id):raise ValueError('generation target coverage: '+state)
    if set(quality)!={(s,eid) for s in states for eid in by_id}:raise ValueError('review coverage')
    expected_audits={(s,eid) for s in states for eid,e in by_id.items() if e['level']==4}
    if set(audits)!=expected_audits:raise ValueError('L4 audit coverage')
    for e in examples:
        eid=e['example_id'];gold=json.loads(e['completion']);r=source[eid]
        if r['source_id']!=e['sample_id'] or r['output']!=gold:raise ValueError('reference binding')
        target=dict(example_id=eid,sample_id=e['sample_id'],level=e['level'],faulty=bool(gold['taxonomy_error']),
                    specification=r['input']['statement'],source=r['input']['code'],syntax_only=r['input']['compile_log'],
                    submission_mode=r['input'].get('exam_type'),native_prompt=e['prompt'],gold=gold,states={})
        for state in states:
            row=by_state[state][eid];q=quality[state,eid]
            if (row['sample_id']!=e['sample_id'] or row['level']!=e['level'] or
                any(q.get(k)!=v for k,v in {'state':state,'example_id':eid,'sample_id':e['sample_id'],'level':e['level'],'status':row['status']}.items())):
                raise ValueError('source/Level/review binding: '+state+'/'+eid)
            dimensions=q['dimensions']
            if set(dimensions)!=set(AXES) or not set(dimensions.values())<=VERDICTS or not isinstance(q.get('evidence'),str) or not q['evidence'].strip():
                raise ValueError('incomplete semantic evidence: '+state+'/'+eid)
            if row['status']!='valid' and set(dimensions.values())!={'not_evaluable'}:raise ValueError('invalid output has evaluable review')
            l4=audits[state,eid] if e['level']==4 else None
            if l4 is not None and (not isinstance(l4.get('status'),str) or not l4['status']):raise ValueError('missing L4 status')
            code='pass' if l4 is not None and l4['status']=='all_authored_tests_passed' else 'fail' if l4 is not None else None
            entry=dict(example_id=eid,sample_id=e['sample_id'],level=e['level'],gold=gold,generation=row,
                       semantic_review=q,l4=l4,joint_success=joint_success(row['status'],e['level'],target['faulty'],dimensions,code),
                       clean_false_alarm=not target['faulty'] and row['status']=='valid' and bool(row['parsed']['taxonomy_error']))
            target['states'][state]=entry;joined[state].append(entry)
        targets.append(target)
    summaries={}
    for state,items in joined.items():
        metrics=aggregate_metrics(examples,generations[state])
        # The generic metric deliberately leaves semantic review pending. Replace
        # that metadata only after complete, concrete reviews were joined above.
        for level,subset in [(None,items)]+[(n,[x for x in items if x['level']==n]) for n in range(1,5)]:
            m=metrics if level is None else metrics['by_level'][str(level)]
            m['feedback_quality']={'review_type':'agent_review_not_independent_gold','reviewed':len(subset),'not_evaluable':sum(x['generation']['status']!='valid' for x in subset),'pending':0}
        dims={axis:dict(Counter(x['semantic_review']['dimensions'][axis] for x in items)) for axis in AXES}
        by_level={str(level):{axis:dict(Counter(x['semantic_review']['dimensions'][axis] for x in items if x['level']==level)) for axis in AXES} for level in range(1,5)}
        joint=[x['example_id'] for x in items if x['joint_success']]
        repairs=[x['example_id'] for x in items if x['level']==3 and x['gold']['taxonomy_error'] and x['generation']['status']=='valid' and x['semantic_review']['dimensions']['l3_repair_direction']=='pass']
        code_rows=[x for x in items if x['level']==4]
        summaries[state]=dict(targets=len(items),sources=len({x['sample_id'] for x in items}),metrics=metrics,dimensions=dims,by_level=by_level,
            joint_successful=len(joint),joint_ids=joint,faulty_l3_correct=len(repairs),faulty_l3_ids=repairs,
            l4=dict(targets=len(code_rows),status_counts=dict(Counter(x['l4']['status'] for x in code_rows)),
                    code_pass_explanation_nonpass=sum(x['l4']['status']=='all_authored_tests_passed' and x['semantic_review']['dimensions']['l4_explanation_quality']!='pass' for x in code_rows),
                    compile_calls=sum(x['l4'].get('compile') is not None for x in code_rows),runtime_calls=sum(t.get('executed',False) for x in code_rows for t in x['l4'].get('tests',[]))),
            consistency=cross_level_consistency(generations[state]),reviewed_targets=len(items),pending_reviews=0)
        for axis in AXES:
            if sum(dims[axis].values())!=len(items):raise ValueError('semantic denominator mismatch')
        if sum(summaries[state]['l4']['status_counts'].values())!=len(code_rows):raise ValueError('L4 denominator mismatch')
    return dict(targets=targets,states=summaries,review_type='source-grounded agent review; synthetic, not independent human or official gold')


def reconcile_saved(actual,saved):
    """Refuse summaries inconsistent with actual per-target reviews and results."""
    expected=dict(targets=actual['targets'],joint_successful=actual['joint_successful'],joint_ids=actual['joint_ids'],
                  faulty_l3_correct=actual['faulty_l3_correct'],faulty_l3_ids=actual['faulty_l3_ids'],dimensions=actual['dimensions'],
                  clean_false_alarms=actual['metrics']['clean_false_alarms']['targets']['false_alarms'],invalid=actual['metrics']['invalid_outputs'])
    for key,value in expected.items():
        if saved.get(key)!=value:raise ValueError('semantic summary disagreement: '+key)


def journal_costs(events,reuse,ceiling):
    reservations=[e['key'] for e in events if e.get('type')=='generation_reserved']
    if len(set(reservations))!=len(reservations):raise ValueError('duplicate physical reservation')
    if len(reservations)>ceiling:raise ValueError('physical call ceiling exceeded')
    smoke=[k for k in reservations if k.startswith('smoke-')]
    ar15=[k for k in reservations if k.startswith('ar15-')]
    native=[k for k in reservations if not k.startswith(('smoke-','ar15-'))]
    requests={k.rsplit('/',1)[0] for k in ar15}
    completed=[e for e in events if e.get('type') in ('generation_completed','ar15_generation_completed')]
    completed_keys=[e['key'] for e in completed]
    if len(set(completed_keys))!=len(completed_keys) or not set(completed_keys)<=set(reservations):raise ValueError('physical completion journal disagreement')
    payloads=[e['result'] if e['type']=='generation_completed' else e for e in completed]
    return dict(physical_reservations=len(reservations),physical_ceiling=ceiling,
        fresh_native_primary_reservations=len(native),ar15_physical_reservations=len(ar15),ar15_logical_requests_with_attempts=len(requests),
        ar15_internal_retries_reserved=len(ar15)-len(requests),smoke_reservations=len(smoke),completed_physical_calls=len(completed),
        reserved_without_completion=sorted(set(reservations)-set(completed_keys)),
        completed_generation_wall_s=sum(r.get('wall_s',0) or 0 for r in payloads),
        completed_generation_output_tokens=sum(r.get('output_tokens',0) or 0 for r in payloads),
        known_completed_generation_input_token_sum=sum(r.get('input_tokens',0) or 0 for r in payloads),
        completion_events_missing_input_token_count=sum('input_tokens' not in r for r in payloads),
        ar15_input_token_journal_limit='A/R15 input tokens are retained in request reservations/generation rows; completion events alone may omit them.',
        reused_states=sorted(s for s,r in reuse.items() if r.get('generated_in_this_experiment') is False),
        whole_experiment_wall_s_available=False,wall_scope='Sum of completed physical generation latencies only; excludes loading, training, authoring, idle time and reused generation cost.')


def pre(value):
    if not isinstance(value,str):value=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)
    return '<pre>'+escape(value)+'</pre>'


def render_casebook(title,bundle):
    states=list(bundle['states']);targets=bundle['targets']
    statuses=sorted({x['generation']['status'] for t in targets for x in t['states'].values()})
    options=lambda vals:''.join('<option value="'+escape(x,quote=True)+'">'+escape(x)+'</option>' for x in vals)
    parts=['<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>'+escape(title)+'</title><style>body{font:15px system-ui;margin:24px;background:#f5f6f8;color:#172033}header{position:sticky;top:0;background:#f5f6f8;padding:12px;z-index:1}section{padding:18px;background:white;border:1px solid #cbd2db;border-radius:8px;margin:18px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f2f5;padding:12px}.paired{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:12px}article{border:1px solid #ccd2dc;padding:12px;min-width:0}input,select{padding:7px;margin:4px}[hidden]{display:none!important}</style>',
        '<header><h1>'+escape(title)+'</h1>',f'<p>{len(targets)} target / {len({t["sample_id"] for t in targets})} source mỗi state. Review đã hoàn tất: đối chiếu source/spec và phản hồi thực; review agent, không phải gold độc lập. Code L4 và giải thích được chấm riêng.</p>',
        '<input id="search-filter" type="search" aria-label="Tìm nội dung" placeholder="ID, source, phản hồi, evidence">',
        '<select id="state-filter" aria-label="State"><option value="">Mọi state</option>'+options(states)+'</select>',
        '<select id="level-filter" aria-label="Level"><option value="">Mọi Level</option>'+options(['1','2','3','4'])+'</select>',
        '<select id="clean-filter" aria-label="Gold"><option value="">Mọi gold</option><option value="clean">Clean</option><option value="faulty">Faulty</option></select>',
        '<select id="status-filter" aria-label="Status"><option value="">Mọi trạng thái</option>'+options(statuses)+'</select>',
        '<select id="axis-filter" aria-label="Trục review"><option value="">Mọi trục</option>'+options(AXES)+'</select>',
        '<select id="verdict-filter" aria-label="Verdict"><option value="">Mọi verdict</option>'+options(sorted(VERDICTS))+'</select><span id="visible-count"></span></header>',
        '<details><summary>Tổng hợp đã đối chiếu từng record; taxonomy F1 cục bộ, không phải điểm Task 3 chính thức</summary>'+pre(bundle['states'])+'</details>']
    for t in targets:
        parts += [f'<section class="case" id="{escape(t["example_id"],quote=True)}" data-level="{t["level"]}" data-gold="'+('faulty' if t['faulty'] else 'clean')+'">',
                  '<h2>'+escape(t['example_id'])+' · '+escape(t['sample_id'])+'</h2>',
                  '<details><summary>Đặc tả</summary>'+pre(t['specification'])+'</details>',
                  '<details><summary>Source của sinh viên và syntax-only input</summary>'+pre(t['source'])+pre(t['syntax_only'])+'</details>',
                  '<details><summary>Prompt native đầy đủ; gold không nằm trong prompt</summary>'+pre(t['native_prompt'])+'</details>',
                  '<details><summary>Gold reference riêng</summary>'+pre(t['gold'])+'</details><div class="paired">']
        for state,entry in t['states'].items():
            row=entry['generation'];q=entry['semantic_review']
            verdicts=json.dumps(q['dimensions'],ensure_ascii=False,separators=(',',':'))
            parts += ['<article class="response" data-state="'+escape(state,quote=True)+'" data-status="'+escape(row['status'],quote=True)+'" data-verdicts="'+escape(verdicts,quote=True)+'">',
                '<h3>'+escape(state)+'</h3><p>'+escape(row['status'])+' · joint: '+str(entry['joint_success']).lower()+'</p>',
                '<p>'+('A/R15: raw dưới đây là controller export; finish_reason eos mô tả export. Raw model attempts và kết thúc thật được lưu riêng bên dưới.' if row.get('raw_kind') else 'Native: raw dưới đây là phản hồi model, giữ nguyên trạng thái kết thúc.')+'</p>',
                '<h4>Raw response giữ nguyên, kể cả invalid</h4>'+pre(row.get('raw')),
                *(['<h4>Raw model attempts và kết thúc thật của A/R15</h4>'+pre({'raw_attempts':row.get('raw_attempts'),'actual_attempt_finish_reasons':row.get('actual_attempt_finish_reasons'),'raw_kind':row.get('raw_kind'),'structural_validity_basis':row.get('structural_validity_basis'),'historical_final_origin':row.get('historical_final_origin')})] if row.get('raw_kind') else []),
                '<h4>Parsed payload</h4>'+pre(row.get('parsed')),
                '<h4>Semantic dimensions đã hoàn tất</h4>'+pre(q['dimensions']),
                '<h4>Evidence từ review source/spec/phản hồi</h4>'+pre(q['evidence']),
                '<details><summary>Toàn bộ review và provenance</summary>'+pre(q)+'</details>',
                '<h4>Kiểm code L4 hữu hạn, tách khỏi giải thích</h4>'+pre(entry['l4'] if entry['l4'] is not None else {'status':'not_applicable','reason':'Level khác 4'}),
                '<details><summary>Toàn bộ generation record, raw attempts A/R15 và chi phí</summary>'+pre(row)+'</details></article>']
        parts+=['</div></section>']
    parts.append('''<script>
const fields = Object.fromEntries(['search','state','level','clean','status','axis','verdict'].map(x=>[x,document.getElementById(x+'-filter')]));
function filterCases(){let count=0;for(const section of document.querySelectorAll('section.case')){
 const query=fields.search.value.toLocaleLowerCase();const shared=(!fields.level.value||section.dataset.level===fields.level.value)&&(!fields.clean.value||section.dataset.gold===fields.clean.value)&&(!query||section.textContent.toLocaleLowerCase().includes(query));let visible=false;
 for(const article of section.querySelectorAll('article.response')){const dims=JSON.parse(article.dataset.verdicts);const verdict=fields.verdict.value;const axis=fields.axis.value;
 const match=(!fields.state.value||article.dataset.state===fields.state.value)&&(!fields.status.value||article.dataset.status===fields.status.value)&&(!verdict||(axis?dims[axis]===verdict:Object.values(dims).includes(verdict)));article.hidden=!match;visible=visible||match;}
 section.hidden=!(shared&&visible);if(!section.hidden)count++;}document.getElementById('visible-count').textContent=count+' target hiển thị';}
for(const field of Object.values(fields))field.addEventListener('input',filterCases);filterCases();
</script></html>''')
    return '\n'.join(parts)


def choose_examples(bundles,selected_step):
    """Choose reproducible comparative categories without hiding absent categories."""
    categories={key:None for key in ['clean_false_alarm_fixed','clean_false_alarm_introduced','correct_l3_direction','incorrect_l3_direction','cross_level_diagnosis_change','l4_code_pass_explanation_fail','invalid_output','ar15_better']}
    def save(category,split,target,states,related=None):
        if categories[category] is None:
            categories[category]=dict(split=split,example_id=target['example_id'],sample_id=target['sample_id'],level=target['level'],
                specification=target['specification'],source=target['source'],gold=target['gold'],
                states={s:target['states'][s] for s in states},related_levels=related or [])
    for split in ('final','dev','test'):
        b=bundles[split];after='v2-final' if split=='final' else f'step-{selected_step}-dev' if split=='dev' else 'v2-regression'
        before=['base-final','v1-final'] if split=='final' else ['base-dev','v1-dev'] if split=='dev' else ['base-regression','v1-regression']
        ar15='ar15-'+split
        for target in b['targets']:
            a=target['states'][after];ga=a['generation'];dims=a['semantic_review']['dimensions']
            if not target['faulty'] and ga['status']=='valid':
                for state in before:
                    old=target['states'][state]
                    if old['generation']['status']!='valid':continue
                    if old['clean_false_alarm'] and not a['clean_false_alarm']:save('clean_false_alarm_fixed',split,target,[state,after])
                    if not old['clean_false_alarm'] and a['clean_false_alarm']:save('clean_false_alarm_introduced',split,target,[state,after])
            if target['faulty'] and target['level']==3 and ga['status']=='valid':
                if dims['l3_repair_direction']=='pass' and dims['diagnosis_supported']=='pass':save('correct_l3_direction',split,target,[after])
                if dims['l3_repair_direction'] in ('fail','uncertain'):save('incorrect_l3_direction',split,target,[after])
            for state,item in target['states'].items():
                if item['generation']['status']!='valid':save('invalid_output',split,target,[state])
                if target['level']==4 and item['l4']['status']=='all_authored_tests_passed' and item['semantic_review']['dimensions']['l4_explanation_quality']=='fail':save('l4_code_pass_explanation_fail',split,target,[state])
            if ar15 in target['states'] and target['states'][ar15]['joint_success'] and not a['joint_success']:save('ar15_better',split,target,[ar15,after])
        inconsistent={r['sample_id'] for r in b['states'][after]['consistency']['records'] if r['complete'] and not r['contains_invalid'] and not r['consistent']}
        for target in b['targets']:
            if target['sample_id'] in inconsistent:
                related=[dict(example_id=t['example_id'],level=t['level'],response=t['states'][after]) for t in b['targets'] if t['sample_id']==target['sample_id']]
                save('cross_level_diagnosis_change',split,target,[after],related)
                break
    return categories


def fmt(value):
    return 'N/A' if value is None else f'{value:.4f}'


def markdown_report(analysis,run):
    selected=analysis['selection'];manifest=analysis['manifest'];config=manifest['config'];data=analysis['dataset'];steps=analysis['training']['main']['actual_optimizer_steps']
    lines=['# Thí nghiệm Task 3 SFT v2 QLoRA — 26/10/2026','',
        f'Đã hoàn tất {steps}/240 bước optimizer, một epoch từ cùng base đã pin, sau smoke bốn bước được loại bỏ. Checkpoint được chọn bằng dev: **step {selected["step"]}**. Không có kết quả leaderboard mới trong thí nghiệm này.',
        '',f'Dữ liệu train giữ 160 source gốc và thêm đúng 40 cặp clean/faulty: **{data["sources"]["train"]} source / {data["targets"]["train"]} target**, gồm {data["train_clean"]} clean và {data["train_faulty"]} faulty. Ledger ghi **{analysis["target_changes"]["count"]} thay đổi target gốc** có bản trước/sau, lý do, bằng chứng và phiên bản; không đổi source hoặc đặc tả để giả làm sửa annotation.',
        '',f'Dev giữ nguyên 20 source/80 target; old test giữ nguyên 20/80 và chỉ là regression đã quan sát. Final mới gồm 10 family, 40 source/160 target; đóng băng trước generation, không dùng chọn checkpoint. Đây là dữ liệu synthetic được agent soạn, kiểm và review, không phải gold độc lập.',
        '', '## So sánh trên cùng dữ liệu','',
        'Taxonomy micro F1 bên dưới là metric chẩn đoán **cục bộ**, không phải điểm Task 3 chính thức. Mẫu số gồm mọi target; invalid luôn là invalid, không được đổi thành dự đoán clean. Mỗi source có bốn Level phụ thuộc nhau.',
        '', '| Split / state | Target / source | F1 cục bộ | Invalid | FA clean target | FA clean source | Joint thành công | L3 faulty sửa đúng | Code L4 qua test |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for split,bundle in analysis['splits'].items():
        for state,s in bundle['states'].items():
            m=s['metrics'];fa=m['clean_false_alarms'];faulty_l3=sum(t['faulty'] and t['level']==3 for t in bundle['targets'])
            lines.append(f'| {"observed regression" if split=="test" else split} / {state} | {s["targets"]} / {s["sources"]} | {fmt(m["taxonomy"]["all_targets_conservative"]["f1"])} | {m["invalid_outputs"]}/{s["targets"]} | {fa["targets"]["false_alarms"]}/{fa["targets"]["denominator"]} | {fa["sources"]["false_alarms"]}/{fa["sources"]["denominator"]} | {s["joint_successful"]}/{s["targets"]} | {s["faulty_l3_correct"]}/{faulty_l3} | {s["l4"]["status_counts"].get("all_authored_tests_passed",0)}/{s["l4"]["targets"]} |')
    lines+=['','Joint yêu cầu cấu trúc hợp lệ, chẩn đoán có bằng chứng, vị trí/điều kiện thiết yếu khi áp dụng, đúng Level và tiếng Việt; faulty L3 thêm hướng sửa đúng, L4 thêm giải thích đúng và code qua kiểm hữu hạn. uncertain/not_evaluable không được tính pass. N/A được giữ riêng theo policy.','',
        '## Review từng trục và tính nhất quán','',
        'Review do agent đọc đặc tả, source và phản hồi thực; danh tính được che trong packet khi có thể. Không dùng keyword hoặc exact wording để chấm semantic. Casebook nhúng toàn bộ verdict và evidence đã hoàn tất, raw/parsed kể cả invalid, code L4 đã trích và kết quả compiler/runtime.','',
        'Đây là re-review theo protocol v2, kể cả các generations base/v1 được reuse nguyên trạng. Số review v1 lịch sử do người dùng nêu (diagnosis 29/80, Level 51/80, L3 1/20, code L4 5/20 trên old test) vẫn thuộc lượt review trước; chênh lệch verdict mới không phải thay đổi model hoặc raw output. Protocol hiện tại cho hướng L3 sai fail cả repair và Level, nên hai trục này không độc lập.','',
        'Review chỉ mù một phần: tên phương pháp được ẩn và panel đảo theo source, nhưng agent vẫn giữ lịch sử task và có vai trò author/reviewer. Không có human gold hay review độc lập; bất định và adjudication được giữ trong artifact.','',
        '| State | Diagnosis pass | Location pass / N/A | Không có defect vô căn cứ pass | Level pass | Tiếng Việt pass | Giải thích L4 pass | Code L4 đúng nhưng giải thích non-pass |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for b in analysis['splits'].values():
        for state,s in b['states'].items():
            d=s['dimensions'];count=lambda a,v='pass':d[a].get(v,0)
            lines.append(f'| {state} | {count("diagnosis_supported")}/{s["targets"]} | {count("location_and_condition")} / {count("location_and_condition","not_applicable")} | {count("unsupported_defects")}/{s["targets"]} | {count("level_compliance")}/{s["targets"]} | {count("vietnamese_compliance")}/{s["targets"]} | {s["by_level"]["4"]["l4_explanation_quality"].get("pass",0)}/{s["l4"]["targets"]} | {s["l4"]["code_pass_explanation_nonpass"]} |')
    lines+=['','Mọi pass/fail/uncertain/not_applicable/not_evaluable theo từng Level nằm trong analysis.json; các cột pass giữ toàn bộ target làm mẫu số khi nêu tỷ lệ. L3 đúng và code L4 được tách riêng ở bảng trên. Bảng sau chỉ đo nhất quán taxonomy giữa bốn Level; nhất quán không đồng nghĩa chính xác.','',
            '| State | Source đủ bốn Level | Có invalid | Nhất quán và đủ/hợp lệ | Không nhất quán đủ/hợp lệ | Thiếu Level |','|---|---:|---:|---:|---:|---:|']
    for b in analysis['splits'].values():
        for state,s in b['states'].items():
            c=s['consistency'];lines.append(f'| {state} | {c["complete_sources"]}/{c["sources"]} | {c["sources_with_invalid"]} | {c["consistent_complete_valid_sources"]} | {c["inconsistent_complete_valid_sources"]} | {c["incomplete_sources"]} |')
    lines+=['','## Chọn checkpoint và phạm vi so sánh','',
        f'Điều kiện sơ bộ: FA clean target và invalid không vượt native base dev. Các bước đủ điều kiện: `{selected["eligible_steps"]}`. Checkpoint step {selected["step"]} '+('đạt điều kiện sơ bộ.' if selected['passes_preliminary_conditions'] else '**được chọn theo fallback và không đạt điều kiện sơ bộ để đề nghị nâng cấp**.'),
        '', 'Trong nhóm đủ điều kiện, tối đa joint; hòa thì ít FA hơn, nhiều faulty-L3 đúng hơn, loss dev thấp hơn, rồi bước sớm hơn. Nếu không có bước đủ điều kiện, ít FA được ưu tiên trước joint, sau đó giữ các tiêu chí hòa còn lại. Quyết định được lưu và kiểm hash trước khi mở final outputs; final và old regression không đổi quyết định.',
        '', 'Native base, v1 và v2 dùng byte-identical prompt native cho mỗi case dùng chung, cùng parser và greedy/Level token/max_time policy. A/R15 là **system comparator lịch sử chính xác theo snapshot**: prompt/controller/parser/guard/fallback và tối đa ba lần gọi được giữ riêng; không gọi đây là so sánh chỉ thay adapter. Các khác biệt backend, EOS/context và mapping input được ghi nguyên trong manifest:',
        '', '```json',json.dumps(manifest['ar15_identity'],ensure_ascii=False,indent=2),'```',
        '', '## Recipe, hash và kiểm dữ liệu','',
        f'Model `{config["model_id"]}`, revision `{config["revision"]}`, seed `{config["seed"]}`. NF4 double quantization, BF16 compute; LoRA r16/alpha32/dropout0.05, q/k/v/o/gate/up/down; LR 2e-5, một epoch, batch1/accumulation4, max length8192, không packing/truncation, assistant-only equal-example mean loss weight1. V2 khởi tạo từ base, không tiếp tục adapter v1.',
        '', 'Cấu hình thực của Trainer, config frozen, model/tokenizer/code/data/checkpoint hashes và versions được giữ trong analysis.json và manifest.json. Cấu hình optimizer/scheduler/warmup/clipping thực:',
        '', '```json',json.dumps({k:v for k,v in analysis['training']['actual_arguments'].items() if k in ['optim','learning_rate','lr_scheduler_type','warmup_ratio','max_grad_norm','gradient_accumulation_steps','num_train_epochs','per_device_train_batch_size','seed','remove_unused_columns','skip_memory_metrics']},ensure_ascii=False,indent=2),'```',
        '', 'Bằng chứng kiểm dữ liệu mới (private; không được đưa vào prompt):','', '```json',json.dumps(analysis['authoring_evidence'],ensure_ascii=False,indent=2),'```',
        '', 'Kiểm overlap gồm exact/normalized/structural và review family. Không phát hiện exact duplicate mới theo screen; báo cáo lưu mọi near match và giới hạn. Cấu trúc/idiom thông dụng và sự tương đồng trong family train còn lại; kiểm hữu hạn và similarity heuristic không chứng minh độc lập ngữ nghĩa hoặc đúng tuyệt đối.',
        '', '## Chi phí và bộ nhớ','',
        '```json',json.dumps(analysis['costs']['journal'],ensure_ascii=False,indent=2),'```',
        '',f'{analysis["costs"]["displayed_targets"]} record được trình bày trong casebook; trong đó các state dev và regression có reuse được ghi riêng. Budget logic gốc tối đa1120 gồm dev400, final640 và80 output v2 regression mới;160 output base/v1 regression lịch sử chỉ được trình bày thêm, không tính thành generation mới. Call budget frozen:',
        '', '```json',json.dumps(manifest['call_budget'],ensure_ascii=False,indent=2),'```',
        '', '| State | Chi phí generation lịch sử được reuse? | Input / output token | Tổng / median giây generation | Mean loss |','|---|---|---:|---:|---:|']
    for b in analysis['splits'].values():
        for state,s in b['states'].items():
            c=s['metrics']['costs'];lines.append(f'| {state} | {"có" if state in analysis["costs"]["journal"]["reused_states"] else "không"} | {c["input_tokens"]["sum"]} / {c["output_tokens"]["sum"]} | {fmt(c["wall_s"]["sum"])} / {fmt(c["wall_s"]["median"])} | {fmt(s["mean_loss"])} |')
    lines+=['','Các chi phí generation trong state có reuse là chi phí lịch sử; không cộng vào chi phí mới. Tổng journal là latency các physical calls hoàn tất, không phải wall toàn thí nghiệm; không cộng thêm checkpoint eval đã nằm trong thời gian main. Reservation thiếu completion được giữ để thể hiện bất định, không âm thầm gọi lại.','',
        'Phạm vi thời gian/bộ nhớ main được ghi đúng như runtime đo:','', '```json',json.dumps(analysis['training']['memory_and_time_scope'],ensure_ascii=False,indent=2),'```',
        '', 'Các peak từng eval và smoke nằm trong analysis.json và artifact gốc. Nếu có resume, peak quan sát từ interval trước lấy ở ranh giới journal; phần interval bị ngắt sau entry cuối không thể khôi phục. Không suy diễn chi phí tiền tệ khi không có đơn giá.',
        '', '## Ví dụ có bằng chứng','']
    lines+=['','Nhãn ví dụ FA đã sửa/mới xuất hiện chỉ xét taxonomy false alarm. Văn xuôi vẫn có thể chứa chẩn đoán vô căn cứ; đọc verdict và evidence đi kèm để đánh giá nội dung.']
    labels={'clean_false_alarm_fixed':'Taxonomy false alarm clean đã sửa','clean_false_alarm_introduced':'Taxonomy false alarm clean mới xuất hiện','correct_l3_direction':'Hướng L3 đúng','incorrect_l3_direction':'Hướng L3 sai hoặc chưa chắc','cross_level_diagnosis_change':'Chẩn đoán thay đổi giữa Level','l4_code_pass_explanation_fail':'Code L4 qua test nhưng giải thích sai','invalid_output':'Output invalid được giữ nguyên','ar15_better':'A/R15 tốt hơn trên case'}
    for category,title in labels.items():
        chosen=analysis['examples'][category];lines+=['',f'### {title}','']
        if chosen is None:
            lines.append('Không có trường hợp thỏa điều kiện này trong các output đã review.');continue
        link=run/BOOKS[chosen['split']]
        lines += [f'`{chosen["example_id"]}` ({chosen["split"]}), [casebook]({link}#{chosen["example_id"]}).',
                  '', 'Đặc tả: '+chosen['specification'],'','Source được đối chiếu:','','```cpp',chosen['source'].rstrip(),'```']
        for state,item in chosen['states'].items():
            d=item['semantic_review']['dimensions'];lines+=['',f'**{state}** — status `{item["generation"]["status"]}`, joint `{item["joint_success"]}`, L3 `{d["l3_repair_direction"]}`, giải thích L4 `{d["l4_explanation_quality"]}`; code `{item["l4"]["status"] if item["l4"] else "N/A"}`.',
                '', 'Evidence: '+item['semantic_review']['evidence'],'','Trích phản hồi thực (tối đa1200 ký tự; bản đầy đủ trong casebook):','','~~~~',str(item['generation']['parsed']['feedback'] if item['generation']['status']=='valid' else item['generation'].get('raw'))[:1200],'~~~~']
        if chosen['related_levels']:
            lines+=['','Taxonomy từng Level: '+json.dumps({str(t['level']):t['response']['generation']['parsed']['taxonomy_error'] for t in chosen['related_levels']},ensure_ascii=False)]
    final=analysis['splits']['final']['states'];v2=final['v2-final'];ar15=final['ar15-final']
    competitive=(v2['joint_successful']>ar15['joint_successful'] and v2['metrics']['clean_false_alarms']['targets']['false_alarms']<=ar15['metrics']['clean_false_alarms']['targets']['false_alarms'] and v2['metrics']['invalid_outputs']<=ar15['metrics']['invalid_outputs'] and v2['faulty_l3_correct']>=ar15['faulty_l3_correct'])
    recommendation=('Có thể cân nhắc một thí nghiệm public riêng, được phê duyệt riêng, vì v2 có nhiều joint thành công hơn A/R15 trên final synthetic mà không tăng FA/invalid trong so sánh này. Hiện vẫn giữ A/R15; bằng chứng local cùng review agent chưa đủ để thay hệ thống.' if competitive else 'Giữ A/R15 hiện dùng. Các số đo final này chưa tạo bằng chứng đủ mạnh để thay hệ thống bằng v2; không mở thêm epoch, v3 hay tìm hyperparameter trong lượt này.')
    lines+=['','## Nhận định và giới hạn','',recommendation,'',
        f'Final joint: A/R15 {ar15["joint_successful"]}/{ar15["targets"]}, v2 {v2["joint_successful"]}/{v2["targets"]}. H1/H2/H3 là giả thuyết của thay đổi gộp dữ liệu và cách viết target; thí nghiệm không cô lập nguyên nhân từng thay đổi. Không quy kết NF4, kích thước model hay thời lượng train nếu thiếu đối chứng phù hợp.',
        '', 'Điểm leaderboard lịch sử do người dùng báo, tách khỏi mọi số đo local bên trên: A/R15 0.3834; B 0.3247; strict cũ 0.1547. Không có phép đo public mới hoặc cam kết tăng leaderboard. Test hữu hạn không chứng minh lời giải tổng quát; source/Level không độc lập, final synthetic nhỏ và reviewer có thể sai.',
        '', '## Tái tạo báo cáo offline','', '```bash',f'/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_report.py --run {run}','```','',
        'Lệnh chỉ đọc generation/review/L4 đã hoàn tất và ghi analysis.json, ba paired casebook cùng báo cáo này. Không gọi model, GPU, compiler hoặc tự sinh verdict. Thiếu review/evidence, thiếu state hoặc summary không khớp record sẽ dừng thay vì tuyên bố hoàn tất.']
    return '\n'.join(lines)+'\n'


def report(run,report_path=None):
    run=Path(run).resolve(strict=True)
    # Gate on completion before opening any raw model output.
    for states in STATES.values():
        for state in states:
            for name in ('complete.json','generations.jsonl'):
                if not (run/state/name).is_file():raise ValueError('report requires every completed state: '+state+'/'+name)
    from src.task3.sft_v1 import verify_checksums
    from src.task3.sft_v1_runtime import verify_frozen
    from src.task3.sft_v2_runtime import validated_selection
    manifest=json_read(run/'manifest.json');verify_frozen(REPO,run,manifest)
    selection=validated_selection(REPO,run,manifest)
    root=REPO/manifest['config']['dataset_root'];verify_checksums(root,manifest['config']['checksum_manifest_sha256'])
    dataset=json_read(root/'dataset-manifest.json')
    if dataset['sources']!={'train':240,'dev':20,'test':20,'final':40} or dataset['targets']!={'train':960,'dev':80,'test':80,'final':160}:raise ValueError('dataset denominator mismatch')
    oldroot=REPO/'data/raw/task3-sft-v1';immutable={}
    for split in ('dev','test'):
        immutable[split]={suffix:sha256(root/f'{split}.{suffix}')==sha256(oldroot/f'{split}.{suffix}') for suffix in ('records.jsonl','sft.jsonl')}
        if not all(immutable[split].values()):raise ValueError('original evaluation gold changed')
    main=json_read(run/'main/training-result.json');smoke=json_read(run/'smoke/training-result.json')
    if main.get('actual_optimizer_steps')!=240 or main.get('actual_train_forward_calls')!=960:raise ValueError('bounded main run not complete')
    if smoke.get('actual_optimizer_steps')!=4:raise ValueError('smoke step count mismatch')
    checkpoints={}
    for step in (120,240):
        directory=run/'main'/f'checkpoint-{step}';identity=json_read(directory/'checkpoint-identity.json')
        if any(sha256(directory/name)!=h for name,h in identity.items()):raise ValueError('checkpoint changed')
        checkpoints[str(step)]=identity
    parity=json_read(run/'native-prompt-parity.private.json')
    final_parity_path=run/'native-final-prompt-parity.private.json'
    final_parity=json_read(final_parity_path)
    if final_parity.get('targets')!=160 or final_parity.get('byte_identical') is not True or len(final_parity.get('per_target',{}))!=160:
        raise ValueError('final native prompt parity coverage')
    for identity in final_parity['per_target'].values():
        if set(identity)!={'base-final','v1-final','v2-final'} or len(set(identity.values()))!=1 or any(not isinstance(h,str) or len(h)!=64 for h in identity.values()):
            raise ValueError('final native prompt digest mismatch')
    bundles={};state_artifacts={};reviewed=0
    for split,states in STATES.items():
        examples=load_split(root,split)
        if len(examples)!=COUNTS[split] or len({x['sample_id'] for x in examples})*4!=COUNTS[split]:raise ValueError('evaluation denominator')
        if split=='final' and set(final_parity['per_target'])!={e['example_id'] for e in examples}:raise ValueError('final prompt target binding')
        if split in parity:
            observed={e['example_id']:hashlib.sha256(json.dumps(e['prompt'],ensure_ascii=False).encode()).hexdigest() for e in examples}
            if observed!=parity[split]['prompt_sha256'] or not parity[split]['example_objects_equal'] or not parity[split]['sft_bytes_equal']:raise ValueError('native prompt parity changed')
        generated={s:read_jsonl(run/s/'generations.jsonl') for s in states}
        quality=reviews(run,split);audits={}
        for state in states:
            for row in generated[state]:
                if row['level']!=4:continue
                path=run/'l4'/state/row['example_id']/'result.json'
                if not path.is_file():raise ValueError('missing bounded L4 result: '+str(path))
                audit=json_read(path)
                digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
                if audit.get('generation_sha256')!=digest:raise ValueError('L4 result/generation hash mismatch')
                audits[state,row['example_id']]=audit
        bundle=assemble_split(examples,read_jsonl(root/f'{split}.records.jsonl'),generated,quality,audits)
        semantic=summarize(run,split)
        for state,s in bundle['states'].items():
            reconcile_saved(s,semantic[state]);complete=json_read(run/state/'complete.json')
            for key in ('targets','sources','valid_outputs','invalid_outputs','status_counts','source_coverage','taxonomy','clean_false_alarms'):
                if s['metrics'][key]!=complete['metrics'][key]:raise ValueError('saved metric/per-case disagreement: '+state+'/'+key)
            for level in ('1','2','3','4'):
                for key in ('targets','sources','valid_outputs','invalid_outputs','taxonomy','clean_false_alarms'):
                    if s['metrics']['by_level'][level][key]!=complete['metrics']['by_level'][level][key]:raise ValueError('per-Level metric disagreement')
            if 'cross_level_consistency' in complete:
                recorded=complete['cross_level_consistency'];actual=s['consistency']
                if any(recorded[k]!=v for k,v in actual.items() if k!='records'):raise ValueError('cross-Level metric disagreement')
                if sorted(recorded['records'],key=lambda x:x['sample_id'])!=sorted(actual['records'],key=lambda x:x['sample_id']):raise ValueError('cross-Level record disagreement')
            s['mean_loss']=complete.get('mean_loss')
            s['recorded_phase_cost']={k:v for k,v in complete.items() if k not in ('metrics','cross_level_consistency')}
            state_artifacts[state]={name:sha256(run/state/name) for name in ('complete.json','generations.jsonl')}
            reviewed+=s['reviewed_targets']
        bundles[split]=bundle
    if reviewed!=1280:raise ValueError('expected 400 dev +640 final +240 observed regression reviews')
    events=read_jsonl(run/'journal.jsonl');reuse=json_read(run/'reuse-provenance.json')
    costs=journal_costs(events,reuse,manifest['call_budget']['physical_total'])
    chosen=[i for i,e in enumerate(events) if e.get('type')=='selection_persisted']
    finals=[i for i,e in enumerate(events) if e.get('type')=='generation_reserved' and (e['key'].startswith(('ar15-final/','base-final/','v1-final/','v2-final/','v2-regression/')))]
    if len(chosen)!=1 or not finals or chosen[0]>=min(finals):raise ValueError('selection/final journal order')
    if [e['step'] for e in events if e.get('type')=='optimizer_completed' and e.get('kind')=='main']!=list(range(1,241)):raise ValueError('main optimizer journal mismatch')
    # Independently compare selected candidate data to the actual joined dev rows.
    for candidate in selection['candidates']:
        s=bundles['dev']['states'][f'step-{candidate["step"]}-dev']
        reconcile_saved(s,candidate)
        if candidate['mean_loss']!=s['mean_loss']:raise ValueError('selection loss mismatch')
    ledger=json_read(root/'target-changes.private.json')
    if len(ledger['changes'])!=dataset['target_changes']:raise ValueError('target correction ledger count')
    evidence={}
    for split in ('train','final'):
        evidence[split]=json_read(root/f'authoring/{split}-verification/summary.json')
        evidence[split].pop('repair_verification',None)
        if evidence[split].get('passed') is not True:raise ValueError('authoring verification not complete')
    overlap=json_read(root/'overlap.private.json')
    if any(x['exact_or_whitespace_matches'] for x in overlap['results']):raise ValueError('new exact/normalized duplicate')
    initial=json_read(run/'initial-workspace-state.json')
    changed=[p for p,h in initial['files'].items() if not (REPO/p).is_file() or sha256(REPO/p)!=h]
    if changed:raise ValueError('preexisting file changed: '+str(changed))
    git=lambda *args:subprocess.check_output(['git',*args],cwd=REPO,text=True).strip()
    head=git('rev-parse','HEAD');branch=git('branch','--show-current')
    if head!=manifest['head'] or head!=initial['head'] or branch!=manifest['config']['required_branch']:raise ValueError('workspace branch/HEAD changed')
    scope_keys=['wall_s','training_wall_excluding_checkpoint_evaluation_s','checkpoint_evaluation_wall_s','wall_measurement_scope','peak_allocated_bytes','peak_reserved_bytes','peak_memory_scope','peak_counter_resets_this_invocation','trajectory_observed_peak_allocated_bytes','trajectory_observed_peak_reserved_bytes','trajectory_peak_scope','resumed_from_step']
    if not main.get('peak_memory_scope') or main.get('peak_counter_resets_this_invocation')!=1:raise ValueError('missing whole-main memory scope')
    analysis=dict(version='sft-v2-offline-report-v1',run=str(run),manifest=manifest,manifest_sha256=sha256(run/'manifest.json'),
        reporter_sha256=sha256(Path(__file__)),dataset=dataset,split_manifest_sha256=sha256(root/'split-manifest.json'),
        target_changes=dict(count=len(ledger['changes']),ledger_path=str(root/'target-changes.private.json'),ledger_sha256=sha256(root/'target-changes.private.json'),ledger=ledger),
        authoring_evidence=evidence,overlap=dict(method=overlap['method'],unique_existing_sources=overlap['unique_existing_sources'],threshold_for_review=overlap['threshold_for_review'],results=overlap['results'],limitations=overlap['limitations'],skipped=overlap['skipped']),
        immutable_dev_and_observed_test=immutable,native_prompt_parity=parity,native_final_prompt_parity=dict(final_parity,artifact_sha256=sha256(final_parity_path),source_count=40),reuse_provenance=reuse,selection=selection,
        selection_sha256=sha256(run/'selection.json'),splits=bundles,state_artifact_hashes=state_artifacts,
        historical_user_reported_leaderboard=HISTORICAL,historical_scores_are_current_measurements=False,
        training=dict(main=main,smoke=smoke,actual_arguments=json_read(run/'main/actual-training-arguments.json'),memory_and_time_scope={k:main[k] for k in scope_keys if k in main},checkpoint_hashes=checkpoints,
            freshness=json_read(run/'main-freshness.json'),smoke_complete=json_read(run/'smoke/complete.json'),reload_audit=json_read(run/'smoke/reload-audit.json')),
        costs=dict(journal=costs,displayed_targets=reviewed,reuse_artifact_targets=sum(bundles[split]['states'][state]['targets'] for split in bundles for state in bundles[split]['states'] if state in reuse),formal_logical_budget=manifest['call_budget'],
            teacher_forced_forward_rows=sum(len(read_jsonl(run/state/'losses.jsonl')) for states in STATES.values() for state in states if (run/state/'losses.jsonl').exists()),
            teacher_forced_scope='Includes historical reused loss rows; state provenance identifies fresh versus reused. A/R15 has no native teacher-forced loss.'),
        validation=dict(passed=True,reviewed_target_responses=reviewed,pending_reviews=0,summary_counts_reconciled=True,all_raw_including_invalid_retained=True,source_gold_prompt_separate=True,
            selection_before_any_fresh_final_generation=True,all_original_files_preserved=True,initial_head=initial['head'],final_head=head,branch=branch,initial_git_status=initial.get('status',initial.get('git_status')),
            checks='frozen code/data/tokenizer/dependency hashes, source/split loading, dev/test bytes, selection seal and candidate counts, checkpoint identities, per-state/all-Level denominators, per-target semantic evidence and L4 generation hash'),
        semantic_review_limit='Source-grounded agent re-review under v2 calibration, partially blinded because agents retain task/author history; not independent human gold or official Task 3 scoring. Wrong L3 repair fails both repair and Level, so those axes overlap. Historical v1 review counts are separate. Finite authored L4 tests do not prove correctness.')
    analysis['examples']=choose_examples(bundles,selection['step'])
    for split,bundle in bundles.items():(run/BOOKS[split]).write_text(render_casebook('Task 3 SFT v2 · '+('observed regression' if split=='test' else split),bundle),encoding='utf-8')
    report_path=Path(report_path) if report_path else REPO/'reports/task3/TASK3_SFT_V2_QLORA_20261026.md'
    report_path.parent.mkdir(parents=True,exist_ok=True)
    text=markdown_report(analysis,run);report_path.write_text(text,encoding='utf-8');(run/'REPORT.vi.md').write_text(text,encoding='utf-8')
    analysis['validation']['final_git_status']=git('status','--short')
    analysis['quality_artifact_hashes']={str(p.relative_to(run)):sha256(p) for p in sorted((run/'quality').glob('*.json'))}
    analysis['report_paths']={'vietnamese_markdown':str(report_path),'casebooks':{split:str(run/name) for split,name in BOOKS.items()}}
    write_json(run/'analysis.json',analysis)
    print(json.dumps(dict(passed=True,reviewed_targets=reviewed,selected_step=selection['step'],physical_calls_reserved=costs['physical_reservations'],analysis=str(run/'analysis.json'),report=str(report_path)),ensure_ascii=False))
    return analysis


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args();report(args.run,args.report)

if __name__=='__main__':main()
