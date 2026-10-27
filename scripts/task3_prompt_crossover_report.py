"""Offline Vietnamese crossover report; no model calls or student-code execution."""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.task3.prompt_crossover_analysis import AXES, VERDICTS, summarize, paired_analysis, semantic_value, successful_feedback
from src.task3.sft_v1_runtime import digest

CELLS = ('v2-old','v2-v3','v3-old','v3-v3')
PAIRS = {'v2_prompt':('v2-old','v2-v3'),'v3_prompt':('v3-old','v3-v3'),
         'old_adapter':('v2-old','v3-old'),'v3_adapter':('v2-v3','v3-v3')}
DEFAULT_OUT = REPO/'outputs/task3/prompt-crossover-20261027-run1'
DEFAULT_REPORT = REPO/'reports/task3/TASK3_PROMPT_CROSSOVER_20261027.md'
DEFAULT_EXAMPLES = REPO/'reports/task3/TASK3_PROMPT_CROSSOVER_EXAMPLES_20261027.md'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def jsonl(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]


def dump(value):
    return json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)


def _index(rows, key, label):
    result={}
    for row in rows:
        value=row[key]
        if value in result:
            raise ValueError('duplicate '+label+': '+value)
        result[value]=row
    return result


def validate_populations(out, rows):
    """Reject incomplete/foreign reviews and input/output/evidence joins before writes."""
    out=Path(out).resolve()
    for row in rows:
        if set(row.get('axes',{}))!=set(AXES) or any(v not in VERDICTS for v in row['axes'].values()):
            raise ValueError('pending or invalid review verdict')
        if not row.get('completed_review_record') or not row.get('evidence') or not row.get('review_id'):
            raise ValueError('missing completed review/evidence')
        if row['status']!='valid' and any(v!='not_evaluable' for v in row['axes'].values()):
            raise ValueError('invalid output needs not_evaluable semantic review')
    records=_index(jsonl(out/'evaluation/dev.records.private.jsonl'),'sample_id','source record')
    if len(records)!=80 or len({r['source_id'] for r in records.values()})!=20:
        raise ValueError('expected exact dev80 /20 sources')
    bindings={(r['source_id'],r['input']['target_feedback_level']) for r in records.values()}
    if len(bindings)!=80 or {l for s,l in bindings}!={1,2,3,4}:
        raise ValueError('source/Level population mismatch')
    examples={}
    for arm in ('old','v3'):
        examples[arm]=_index(load(out/f'inputs/{arm}.examples.private.json'),'example_id','input')
        if set(examples[arm])!=set(records):
            raise ValueError('missing or foreign input IDs')
        for eid,e in examples[arm].items():
            r=records[eid]
            if (e['sample_id'],e['level'])!=(r['source_id'],r['input']['target_feedback_level']):
                raise ValueError('input source/Level mismatch')
    if len(rows)!=320 or {r['cell'] for r in rows}!=set(CELLS):
        raise ValueError('require complete320 four-cell review')
    generations={}; evidence={}; complete={}
    for cell in CELLS:
        reviewed=_index([r for r in rows if r['cell']==cell],'example_id','review')
        gens=_index(jsonl(out/f'cells/{cell}/generations.jsonl'),'example_id','generation')
        if set(reviewed)!=set(records) or set(gens)!=set(records):
            raise ValueError('missing or foreign generation/review IDs: '+cell)
        complete[cell]=load(out/f'cells/{cell}/complete.json')
        completion=complete[cell]
        if completion.get('mode')=='reused':
            if (completion.get('targets')!=80 or completion.get('new_generation_calls')!=0 or
                    completion.get('historical_generation_calls')!=80):
                raise ValueError('incomplete reused cell: '+cell)
        else:
            unknown=sum(bool(g.get('call_count_uncertain')) for g in gens.values())
            if (completion.get('generation',{}).get('calls')!=80-unknown or
                    completion.get('unknown',0)!=unknown):
                raise ValueError('incomplete cell calls: '+cell)
        for eid,row in reviewed.items():
            r=records[eid];g=gens[eid]
            if (row['sample_id'],row['level'])!=(r['source_id'],r['input']['target_feedback_level']):
                raise ValueError('review source/Level mismatch')
            if set(row['gold_taxonomy'])!=set(r['output']['taxonomy_error']) or row['faulty']!=bool(r['output']['taxonomy_error']):
                raise ValueError('review gold mismatch')
            for key in ('sample_id','level','status','finish_reason','raw','parsed'):
                if row.get(key)!=g.get(key):
                    raise ValueError('review generation mismatch: '+cell+'/'+eid+'/'+key)
            detail=load(out/f'code-evidence/{cell}/{eid}.json')
            if detail.get('generation_sha256') and detail['generation_sha256']!=digest(g):
                raise ValueError('code evidence generation hash mismatch')
            if detail.get('detail_path'):
                path=(out/detail['detail_path']).resolve()
                if not path.is_relative_to(out):
                    raise ValueError('code evidence detail path outside run')
                detail['bounded_execution_detail']=load(path)
            evidence[(cell,eid)]=detail
        generations[cell]=list(gens.values())
    return records,examples,generations,evidence,complete


def costs(manifest,generations,complete):
    def group(cells):
        rows=[g for c in cells for g in generations[c]]
        result=dict(generation_calls=len(rows),confirmed_generation_calls=sum(not r.get('call_count_uncertain') for r in rows),invalid_outputs=sum(g['status']!='valid' for g in rows),
                    uncertain_call_rows=sum(bool(g.get('call_count_uncertain')) for g in rows))
        for key,name in [('wall_s','generation_wall_s'),('input_tokens','input_tokens'),('output_tokens','output_tokens')]:
            values=[r.get(key) for r in rows if not r.get('call_count_uncertain') and r.get(key) is not None]
            result[name]=sum(values) if values else None
            result[name+'_measured_rows']=len(values)
            result[name+'_unmeasured_rows']=len(rows)-len(values)
        for key in ('peak_allocated_bytes','peak_reserved_bytes'):
            measured=[complete[c][key] for c in cells if complete.get(c,{}).get(key) is not None]
            result[key]=max(measured) if measured else None
        return result
    fresh=[c for c in CELLS if manifest['cells'][c]['mode']=='fresh']
    reused=[c for c in CELLS if manifest['cells'][c]['mode']=='reused']
    return dict(new_calls=sum(len(generations[c]) for c in fresh),reused_outputs=sum(len(generations[c]) for c in reused),
        planned_new_calls=manifest['planned_new_calls'],fresh=group(fresh),reused=group(reused),
        per_cell={c:dict(mode=manifest['cells'][c]['mode'],**group([c]),phase_wall_s=complete.get(c,{}).get('wall_s'),
            memory_scope=complete.get(c,{}).get('memory_scope')) for c in CELLS},monetary_total=None,
        note='Reused là chi phí generation lịch sử trong phạm vi80 output/cell, không tính vào chi phí mới. Không cộng wall của pha với wall con; VRAM lấy max. Không có đơn giá nên không suy ra tiền. Review agent không được telemetry GPU đo. Unknown reservation vẫn tính trong call totals; placeholder token/wall của unknown không được tính là measurement0. Tổng token/wall chỉ gồm confirmed calls có measurement; thiếu measurement ghi không đo, kèm số measured/unmeasured rows.')


def choose_examples(rows,before,after,limit=2):
    left={r['example_id']:r for r in rows if r['cell']==before}
    right={r['example_id']:r for r in rows if r['cell']==after}
    candidates={k:[] for k in ('correct_to_incorrect','incorrect_to_correct','l3_repair_change','contradiction','no_change')}
    for eid in sorted(set(left)&set(right)):
        a,b=left[eid],right[eid]
        av,bv=semantic_value(a,'assessment'),semantic_value(b,'assessment')
        if av is True and bv is False:candidates['correct_to_incorrect'].append(eid)
        if av is False and bv is True:candidates['incorrect_to_correct'].append(eid)
        if a['faulty'] and a['level']==3 and {semantic_value(a,'l3_repair_direction'),semantic_value(b,'l3_repair_direction')}=={True,False}:
            candidates['l3_repair_change'].append(eid)
        if any(r['status']=='valid' and (r.get('taxonomy_feedback_contradiction') is True or
            r.get('completed_review_record',{}).get('taxonomy_feedback_contradiction') is True or
            r.get('completed_review_record',{}).get('verdict',{}).get('taxonomy_feedback_contradiction') is True) for r in (a,b)):
            candidates['contradiction'].append(eid)
        if av is not None and av==bv and a['parsed']==b['parsed']:
            candidates['no_change'].append(eid)
    result={}
    for name,ids in candidates.items():
        seen=set();chosen=[]
        for eid in ids:
            family=left[eid]['family_id']
            if family not in seen:
                chosen.append(eid);seen.add(family)
            if len(chosen)==limit:break
        result[name]=chosen
    clean_reductions=[];faulty_increases=[]
    for eid in sorted(set(left)&set(right)):
        a,b=left[eid],right[eid]
        if a['status']!='valid' or not a['parsed']['taxonomy_error']:
            continue
        if not a['faulty'] and b['status']=='valid' and not b['parsed']['taxonomy_error']:
            clean_reductions.append(eid)
        elif a['faulty'] and (b['status']!='valid' or not b['parsed']['taxonomy_error']):
            faulty_increases.append(eid)
    # Match two different sources; prefer distinct families and equal Levels,
    # then stable IDs. Across examples, each family/source appears at most once.
    pairs=sorted(((c,f) for c in clean_reductions for f in faulty_increases
        if left[c]['sample_id']!=left[f]['sample_id']),key=lambda pair:(
            left[pair[0]]['family_id']==left[pair[1]]['family_id'],
            left[pair[0]]['level']!=left[pair[1]]['level'],pair))
    used_families=set();used_sources=set();tendencies=[]
    for c,f in pairs:
        families={left[c]['family_id'],left[f]['family_id']}
        sources={left[c]['sample_id'],left[f]['sample_id']}
        if families & used_families or sources & used_sources:
            continue
        tendencies.append(dict(clean_example_id=c,faulty_example_id=f))
        used_families.update(families);used_sources.update(sources)
        if len(tendencies)==limit:break
    result['cross_input_tendency']=tendencies
    return result


def render_casebook(rows,records,examples,evidence):
    def pre(value):
        return '<pre>'+html.escape(value if isinstance(value,str) else dump(value))+'</pre>'
    by_cell={c:{r['example_id']:r for r in rows if r['cell']==c} for c in CELLS}
    parts=['<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Task3 prompt crossover — toàn bộ cặp</title><style>body{font:15px system-ui;margin:24px;background:#f6f7fa}section,article{background:white;border:1px solid #ccd;padding:16px;margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f2f5;padding:12px}.cells{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}article{min-width:0}[hidden]{display:none}</style>',
        '<h1>Toàn bộ80 targets ×4 cells</h1><p>Source-grounded agent review; không phải gold độc lập. Dev đã được quan sát nhiều lần. Gold chỉ dùng đánh giá, không nằm trong input model.</p>',
        '<label>Tìm ID, source, output <input id="find" type="search"></label>']
    for eid in sorted(records):
        rec=records[eid]
        parts += ['<section class="case"><h2>'+html.escape(eid)+'</h2><details><summary>Đề, source, syntax log và tham chiếu riêng tư đầy đủ</summary>'+pre(rec)+'</details><div class="cells">']
        for cell in CELLS:
            row=by_cell[cell][eid];arm='old' if cell.endswith('-old') else 'v3'
            parts += ['<article><h3>'+html.escape(cell)+'</h3><details><summary>Prompt thực tế đầy đủ</summary>'+pre(examples[arm][eid]['prompt'])+'</details>',
                '<h4>Raw output</h4>'+pre(row['raw']),'<h4>Parsed output</h4>'+pre(row['parsed']),
                '<h4>Verdict và bằng chứng source</h4>'+pre({k:row.get(k) for k in ('status','finish_reason','axes','code_verdict','evidence','review_id','completed_review_record','code_resolution_evidence')}),
                '<details><summary>Bằng chứng code và bounded execution</summary>'+pre(evidence[(cell,eid)])+'</details></article>']
        parts += ['</div></section>']
    parts += ['<script>document.getElementById("find").addEventListener("input",function(){const q=this.value.toLowerCase();document.querySelectorAll(".case").forEach(s=>s.hidden=!s.textContent.toLowerCase().includes(q));});</script></html>']
    return '\n'.join(parts)


def table(headers,rows):
    def cell(v):return ('không đo' if v is None else str(v)).replace('|','\\|').replace('\n','<br>')
    return '\n'.join(['| '+' | '.join(map(cell,headers))+' |','| '+' | '.join('---' for _ in headers)+' |']+
                     ['| '+' | '.join(map(cell,r))+' |' for r in rows])


def ratio(n,d):
    return f'{n}/{d} ({100*n/d:.1f}%)' if d else f'{n}/0 (không áp dụng)'


def summarize_cells(rows):
    result={}
    for cell in CELLS:
        chosen=[r for r in rows if r['cell']==cell]
        def select(level=None,faulty=None):
            return summarize([r for r in chosen if (level is None or r['level']==level) and (faulty is None or r['faulty']==faulty)])
        result[cell]=dict(overall=select(),by_level={str(l):select(level=l) for l in (1,2,3,4)},
            by_status={n:select(faulty=f) for n,f in [('clean',False),('faulty',True)]},
            by_level_status={str(l):{n:select(level=l,faulty=f) for n,f in [('clean',False),('faulty',True)]} for l in (1,2,3,4)})
    return result


def _metric_table(metrics):
    return table(['Cell','Targets/nguồn','Valid','Clean alarm','Faulty miss+invalid','Faulty diagnosis','Faulty L3 sửa đúng','Disclosure','Required','Thành công','Taxonomy P/R/F1 (aux)'],[
        [c,f"{s['targets']}/{s['sources']}",ratio(s['valid'],s['targets']),ratio(s['clean_false_alarms'],s['clean_targets']),
         ratio(s['faulty_misses_with_invalid'],s['faulty_targets']),ratio(s['supported_faulty_diagnosis'],s['faulty_targets']),
         ratio(s['faulty_l3_correct'],s['faulty_l3_targets']),ratio(s['disclosure_compliant'],s['targets']),ratio(s['required_content_met'],s['targets']),
         ratio(s['successful_feedback'],s['targets']),'/'.join('NA' if v is None else f'{v:.3f}' for v in
          [s['taxonomy_auxiliary']['taxonomy']['all_targets_conservative'][k] for k in ('precision','recall','f1')])]
        for c,s in metrics.items()])


def render_reports(out,manifest,analysis,rows,records):
    metrics=analysis['metrics'];paired=analysis['paired'];cost=analysis['costs']
    matching = manifest.get('technical_matching') is True
    matching_text = ('Đã đối sánh theo hợp đồng runtime/input/parser/adapter trong frozen manifest và reuse audit' if matching else
        'Chưa xác lập đối sánh kỹ thuật; mọi so sánh phải giữ các confounder trong reuse audit')
    def change(name):
        s=paired[name]['overall']['semantic']['assessment'];return f"{name}: {s['win']} cải thiện, {s['loss']} giảm, {s['tie']} hòa, {s['uncertain']} chưa rõ /80"
    # A recommendation is conditioned on diagnosis and harms, never on disclosure/joint alone.
    safe=[]
    for name in ('old_adapter','v3_adapter'):
        a,b=PAIRS[name];x,y=metrics[a]['overall'],metrics[b]['overall']
        if y['supported_faulty_diagnosis']>x['supported_faulty_diagnosis'] and all(y[k]<=x[k] for k in ('invalid','clean_false_alarms','faulty_misses_with_invalid')) and y['faulty_l3_correct']>=x['faulty_l3_correct']:
            safe.append(name)
    next_action=('Kiểm tra độc lập trên dev mới chưa quan sát trước khi cân nhắc thay đổi pipeline; '+', '.join(safe)+' có cải thiện chẩn đoán trong dev hiện tại, cần xác nhận ngoài tập này.' if safe else
        'Giữ nguyên quyết định triển khai; thu thập một tập chẩn đoán mới chưa quan sát để xác nhận tradeoff clean/faulty trước khi chọn adapter/prompt.')
    lines=['# Task3 — prompt crossover dev80','',
        f"1. **{cost['new_calls']} generation mới; {cost['reused_outputs']} output tái sử dụng** (kế hoạch {cost['planned_new_calls']} calls).",
        '2. **Trạng thái đối sánh kỹ thuật:** '+matching_text+'. Manifest và bảo toàn đã được kiểm tra. Khác biệt guard và lý do fresh/reuse đọc cùng `reuse-audit.json`; kết quả là liên hệ có điều kiện theo audit, không bảo đảm bitwise device microstate.',
        '3. **Đổi prompt và chẩn đoán:** '+change('v2_prompt')+'; '+change('v3_prompt')+'.',
        '4. **V3 so V2 cùng prompt:** '+change('old_adapter')+'; '+change('v3_adapter')+'.',
        '5. **Bước tiếp theo:** '+next_action,'',
        'Đây là source-grounded agent review, không phải gold người đánh giá độc lập hoặc điểm chấm chính thức. Dev đã được quan sát nhiều lần;80 targets là20 source ×4 Level, không phải80 chương trình độc lập.','',
        '## Runtime và phương pháp đã đóng băng','',
        table(['Cell','Adapter','Prompt','Mode','Method identity'],[[c,manifest['cells'][c].get('adapter_path'),manifest['cells'][c].get('prompt_arm'),manifest['cells'][c]['mode'],manifest['cells'][c].get('method_identity')] for c in CELLS]),'',
        '```json',dump(manifest.get('runtime',{})),'```','',
        '## Ma trận2×2 đầy đủ','',_metric_table({c:metrics[c]['overall'] for c in CELLS}),'',
        'Taxonomy P/R/F1 là phụ trợ, dùng all-target conservative; invalid faulty góp nhãn gold vào FN. Invalid clean luôn giữ trong mẫu số và thất bại cấu trúc. Nonempty taxonomy không tự chứng minh chẩn đoán đúng.','',
        'Disclosure chỉ kiểm tra giới hạn tiết lộ. Required content riêng: faulty L2 có nội dung chẩn đoán/cause; faulty L3 có chẩn đoán và hint. Hint sai chấm riêng. Praise đúng trên clean được phép. L4 không bắt buộc code; code đã cung cấp sai/chưa rõ làm task success thất bại. Không chọn winner bằng disclosure hoặc joint tổng.','',
        '## Clean/faulty và từng Level','']
    for status in ('clean','faulty'):
        lines += ['### '+status,'',_metric_table({c:metrics[c]['by_status'][status] for c in CELLS}),'']
    lines += [table(['Cell','L','Status','n/nguồn','Invalid','Alarm','Miss+invalid','Diagnosis','L3repair','Disclosure','Required','Success'],[
        [c,l,status,f"{s['targets']}/{s['sources']}",s['invalid'],s['clean_false_alarms'],s['faulty_misses_with_invalid'],s['supported_faulty_diagnosis'],
         s['faulty_l3_correct'],s['disclosure_compliant'],s['required_content_met'],s['successful_feedback']]
        for c in CELLS for l in ('1','2','3','4') for status in ('clean','faulty') for s in [metrics[c]['by_level_status'][l][status]]]),'',
        '## Bốn so sánh ghép cặp','',
        'Win/loss có hướng từ cell trước sang cell sau. Invalid hoặc semantic chưa rõ ở một vế → uncertain, kể cả khi một cổng cần thiết khác đã fail; không biến unknown thành loss chắc chắn. not-applicable ở cả hai → tie; riêng L3 repair, bảng chung chứa các tie không áp dụng, phải đọc bảng faulty-L3 bên dưới. Full taxonomy-set, error-presence và status transitions lưu trong `paired-differences.json`, gồm từng target, từng Level, clean/faulty và giao Level×status.','']
    for name,p in paired.items():
        lines += ['### '+name+': '+' → '.join(PAIRS[name]),'',table(['Trục','Win','Loss','Tie','Uncertain'],[[k,*[v[o] for o in ('win','loss','tie','uncertain')]] for k,v in p['overall']['semantic'].items()]),'']
        repair = p['by_level_status']['3']['faulty']
        lines += ['Faulty-L3 riêng (loại mọi target không áp dụng):','',table(['n','Nguồn','Win','Loss','Tie','Uncertain'],[[repair['targets'],repair['sources'],*[repair['semantic']['l3_repair_direction'][o] for o in ('win','loss','tie','uncertain')]]]),'']
        for kind in ('taxonomy_transitions','error_presence_transitions','validity_transitions'):
            lines += [kind,'',table(['Trước','Sau','Số'],[[json.dumps(r['before'],ensure_ascii=False),json.dumps(r['after'],ensure_ascii=False),r['count']] for r in p['overall'][kind]]),'']
    lines += ['## Chi phí thực đo','',table(['Cell','Mode','Calls/confirmed/unknown','Input tokens (đo/n)','Output tokens (đo/n)','Generation wall s (đo/n)','Phase wall s','Peak allocated bytes'],[
        [c,s['mode'],f"{s['generation_calls']}/{s['confirmed_generation_calls']}/{s['uncertain_call_rows']}",
         f"{s['input_tokens'] if s['input_tokens'] is not None else 'không đo'} ({s['input_tokens_measured_rows']}/{s['generation_calls']})",
         f"{s['output_tokens'] if s['output_tokens'] is not None else 'không đo'} ({s['output_tokens_measured_rows']}/{s['generation_calls']})",
         f"{s['generation_wall_s'] if s['generation_wall_s'] is not None else 'không đo'} ({s['generation_wall_s_measured_rows']}/{s['generation_calls']})",s['phase_wall_s'],s['peak_allocated_bytes']] for c,s in cost['per_cell'].items()]),'',
        cost['note'],'',f"Calls invalid mới/tái sử dụng: {cost['fresh']['invalid_outputs']}/{cost['reused']['invalid_outputs']}; uncertain rows mới/tái sử dụng: {cost['fresh']['uncertain_call_rows']}/{cost['reused']['uncertain_call_rows']}.",'',
        '## Kiểm thử hồi quy','',
        'Kết quả task3 trong `audit/analysis-task3-suite.txt`: 2022 passed,15 skipped (12.58s) tại thời điểm triển khai. Full repository suite đã thử và dừng collection ở `tests/test_clm_zeroshot_task1.py` và `tests/test_task1_clm_probe.py`: interpreter thiếu sklearn; xem `audit/analysis-full-suite.txt`. Không coi run bị dừng là suite xanh. TDD RED/GREEN cho analysis/report giữ riêng tại audit/analysis-*.txt. Kiểm tra mới sau triển khai có thể bổ sung log cùng run.','',
        '## Bằng chứng và tái lập offline','',
        f"Run: `{out}`. Toàn bộ raw, prompts, frozen manifest, code evidence và completed verdicts giữ tại run. `analysis.json` lưu mẫu số, chi phí và verification; `paired-casebook.html` chứa mọi target và cả bốn cell. Báo cáo ví dụ riêng dùng quy tắc tất định theo ID, ưu tiên family khác nhau; không chọn theo văn phong/độ dài.",'',
        '```bash',f'PY=/workspace/llm-final-project/.venv-task3/bin/python',f'cd {REPO}',
        '"$PY" -m pytest -q tests/test_task3_prompt_crossover.py tests/test_task3_prompt_crossover_analysis.py',
        f'"$PY" scripts/task3_prompt_crossover.py verify --out {out}',
        f'"$PY" scripts/task3_prompt_crossover.py metrics --out {out}',
        f'"$PY" scripts/task3_prompt_crossover_report.py --out {out}', '```','',
        'Không tự chạy lại inference bằng các lệnh offline này. Tái lập generation cần cùng frozen manifest và journal; completed/reserved IDs không được gọi lại. Không huấn luyện hoặc đổi checkpoint selection.']
    ex=['# Task3 — ví dụ prompt crossover','',
        'Quy tắc tất định: sort example_id, lấy tối đa2 family khác nhau mỗi loại trong từng comparison; công bố toàn bộ80×4 tại casebook. Mâu thuẫn taxonomy–feedback chỉ chọn khi completed review có annotation tường minh; false praise riêng lẻ không tự chứng minh mâu thuẫn giữa nhãn và văn bản. Nếu không có trường hợp đủ bằng chứng, ghi rõ thay vì thay bằng case chưa rõ. Agent review không phải gold độc lập.','']
    lookup={(r['cell'],r['example_id']):r for r in rows}
    names={'correct_to_incorrect':'Đúng → sai','incorrect_to_correct':'Sai → đúng','l3_repair_change':'Thay đổi hướng sửa L3','contradiction':'Taxonomy và đánh giá có mâu thuẫn','no_change':'Không đổi output có ý nghĩa'}
    for comparison,(a,b) in PAIRS.items():
        ex += ['## '+comparison+': '+a+' → '+b,'']
        for category,ids in analysis['examples'][comparison].items():
            if category=='cross_input_tendency':continue
            ex += ['### '+names[category],'']
            if not ids:ex += ['Không có case đáp ứng điều kiện tất định trong dữ liệu đã review.','']
            for eid in ids:
                rec=records[eid]
                ex += ['#### '+eid,'', '**Đề/source:**','', '```json',dump(rec['input']),'```','']
                for c in (a,b):
                    r=lookup[(c,eid)]
                    ex += ['**'+c+'**','', '```json',dump(dict(parsed=r['parsed'],status=r['status'],axes=r['axes'],code_verdict=r['code_verdict'],evidence=r['evidence'])),'```','']
        tendencies=analysis['examples'][comparison]['cross_input_tendency']
        ex += ['### Tendency false alarm/miss trên các input khác nhau','',
            'Chọn cặp gồm một clean source chuyển từ false alarm sang valid empty taxonomy và một faulty source khác chuyển từ nonempty taxonomy sang miss (empty hoặc invalid), cùng hướng đổi cell. Đây là tendency trên các input khác nhau, không phải transition một source sạch thành source lỗi. Nonempty taxonomy ban đầu không tự chứng minh chẩn đoán đúng. Ưu tiên family khác nhau, cùng Level rồi sort ID; không lặp family/source giữa các cặp.','']
        if not tendencies:
            ex += ['Không có cặp đáp ứng đồng thời clean false-alarm reduction và faulty missed-defect increase trong dữ liệu đã review.','']
        for item in tendencies:
            clean_id,faulty_id=item['clean_example_id'],item['faulty_example_id']
            ex += [f'#### Cross-input: {clean_id} / {faulty_id}','']
            for label,eid in [('Clean false alarm giảm',clean_id),('Faulty miss tăng',faulty_id)]:
                ex += ['**'+label+': '+eid+'**','','```json',dump(records[eid]['input']),'```','']
                for cell in (a,b):
                    r=lookup[(cell,eid)]
                    ex += ['**'+cell+'**','','```json',dump(dict(status=r['status'],parsed=r['parsed'],evidence=r['evidence'])),'```','']
    return '\n'.join(lines)+'\n','\n'.join(ex)+'\n'


def build_report(out,report_path=DEFAULT_REPORT,examples_path=DEFAULT_EXAMPLES):
    # Lazy imports keep every rendering/metric test wholly offline.
    from src.task3.prompt_crossover import verify_run
    from scripts.task3_prompt_crossover import reviewed_rows
    out=Path(out).resolve()
    verification=verify_run(out,preserve=True)
    if not verification.get('passed'):
        raise ValueError('manifest/preservation verification failed')
    manifest=load(out/'manifest.json');rows=reviewed_rows(out)
    records,examples,generations,evidence,complete=validate_populations(out,rows)
    metrics=summarize_cells(rows)
    paired={k:paired_analysis([r for r in rows if r['cell']==a],[r for r in rows if r['cell']==b]) for k,(a,b) in PAIRS.items()}
    if load(out/'metrics.json')!=metrics or load(out/'paired-differences.json')!=paired:
        raise ValueError('saved metrics/paired differences differ from completed reviewed rows')
    accounting=costs(manifest,generations,complete)
    if accounting['new_calls']!=manifest['planned_new_calls']:
        raise ValueError('actual fresh calls differ from frozen plan')
    analysis=dict(metrics=metrics,paired=paired,costs=accounting,verification=verification,
        reuse_audit=load(out/'reuse-audit.json'),
        examples={k:choose_examples(rows,a,b) for k,(a,b) in PAIRS.items()},
        policy='agent_review_not_independent_gold; repeatedly observed dev; invalids in primary denominators',
        manifest_sha256=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest())
    report,short=render_reports(out,manifest,analysis,rows,records)
    outputs={Path(report_path):report,Path(examples_path):short,out/'paired-casebook.html':render_casebook(rows,records,examples,evidence),out/'analysis.json':dump(analysis)+'\n'}
    # All joins, seals, metrics and rendering have completed before the first write.
    for path,text in outputs.items():
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
    return dict(passed=True,outputs=[str(p) for p in outputs],new_calls=accounting['new_calls'],reused_outputs=accounting['reused_outputs'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=DEFAULT_OUT)
    p.add_argument('--report',type=Path,default=DEFAULT_REPORT);p.add_argument('--examples-report',type=Path,default=DEFAULT_EXAMPLES)
    args=p.parse_args();print(dump(build_report(args.out,args.report,args.examples_report)))


if __name__=='__main__':main()
