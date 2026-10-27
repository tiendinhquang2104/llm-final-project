"""Offline Vietnamese v3 report and complete, source-grounded paired casebooks.

Reads the sealed run and completed adjudications only. Never calls a model,
executes student C++, changes selection, or rewrites metrics/generations/targets.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import statistics
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.task3_sft_v3_review import STATES, reviewed_rows, oracle_fidelity_level
from src.task3.sft_v3 import AXES, joint_success, summarize
from src.task3.sft_v3_runtime import validate_selection, verify, preservation
from src.task3.sft_v1_runtime import digest

DEFAULT_OUT = REPO / 'outputs/task3/sft-v3-qlora-20261026-run1'
DEFAULT_REPORT = REPO / 'reports/task3/TASK3_SFT_V3_QLORA_20261026.md'
AXIS_VI = {
    'diagnosis_supported': 'Chẩn đoán có căn cứ', 'coverage': 'Bao phủ lỗi',
    'factual_fidelity': 'Trung thực dữ kiện', 'location_and_condition': 'Vị trí/điều kiện',
    'level_compliance': 'Tuân thủ Level', 'l3_repair_direction': 'Hướng sửa L3',
    'l4_usefulness': 'Hữu ích L4', 'vietnamese_compliance': 'Tiếng Việt',
}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def ratio(n, d):
    return f'{n}/{d} ({100*n/d:.1f}%)' if d else f'{n}/0 (không áp dụng)'


def percent(value):
    return 'không áp dụng' if value is None else f'{100*value:.1f}%'


def table(headers, rows):
    def cell(v):
        return str(v).replace('|', '\\|').replace('\n', '<br>')
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows])


def joint(row):
    return joint_success(row['status'], row['level'], row['faulty'], row['axes'], row['code_verdict'])


def assessment(row):
    return row['status'] == 'valid' and all(row['axes'][axis] == 'pass' for axis in
                                          ('diagnosis_supported', 'coverage', 'factual_fidelity'))


def enhanced_summary(rows):
    result = summarize(rows)
    # The historical summary omits not_evaluable from its axis counters. Keep it
    # explicitly here so invalid targets cannot disappear from the denominator.
    result['axes_all_targets'] = {axis: dict(Counter(row['axes'][axis] for row in rows)) for axis in AXES}
    result['invalid_statuses'] = dict(Counter(row['status'] for row in rows if row['status'] != 'valid'))
    result['unique_clean_sources'] = len({r['sample_id'] for r in rows if not r['faulty']})
    result['unique_faulty_sources'] = len({r['sample_id'] for r in rows if r['faulty']})
    result['level_goal_95_reached'] = result['level_compliant'] >= .95 * result['targets']
    result['oracle_fidelity_level_successful'] = sum(oracle_fidelity_level(r) for r in rows)
    result['code_verdicts'] = dict(Counter(r['code_verdict'] for r in rows))
    return result


def summarize_states(rows, states):
    result = {}
    for state in states:
        chosen = [r for r in rows if r['state'] == state]
        result[state] = {
            'overall': enhanced_summary(chosen),
            'by_level': {str(level): enhanced_summary([r for r in chosen if r['level'] == level])
                         for level in (1, 2, 3, 4)},
            'by_status': {name: enhanced_summary([r for r in chosen if r['faulty'] == faulty])
                          for name, faulty in [('clean', False), ('faulty', True)]},
            'by_level_and_status': {
                str(level): {name: enhanced_summary([r for r in chosen if r['level'] == level and r['faulty'] == faulty])
                             for name, faulty in [('clean', False), ('faulty', True)]}
                for level in (1, 2, 3, 4)},
        }
    return result


def style_summary(rows):
    result = {}
    for state in sorted({r['state'] for r in rows}):
        selected = [r for r in rows if r['state'] == state and r['status'] == 'valid']
        levels = {}
        for level in (1, 2, 3, 4):
            texts = [r['parsed']['feedback'] for r in selected if r['level'] == level]
            levels[str(level)] = dict(valid=len(texts),
                median_characters=statistics.median(map(len, texts)) if texts else None,
                approximate_mean_sentences=statistics.mean(
                    len(re.findall(r'[.!?]+(?:\s|$)', text)) for text in texts) if texts else None)
        by_source = defaultdict(dict)
        for row in selected:
            by_source[row['sample_id']][row['level']] = len(row['parsed']['feedback'])
        complete = [v for v in by_source.values() if len(v) == 4]
        result[state] = dict(by_level=levels, all_four_valid_sources=len(complete),
            strictly_increasing_character_lengths=sum(v[1] < v[2] < v[3] < v[4] for v in complete),
            policy='Mô tả phong cách tùy chọn; đếm câu xấp xỉ, không phải tiêu chí Level/chọn checkpoint.')
    return result


def validate_populations(out, manifest):
    all_rows, generations, records, evidence = {}, {}, {}, {}
    for split in ('dev', 'final'):
        expected_per_state = manifest['config']['expected_rows'][split]
        rows = reviewed_rows(out, split)  # Raises on any pending, missing, duplicate or foreign review.
        expected = len(STATES[split]) * expected_per_state
        if len(rows) != expected or expected != manifest['call_budget']['dev' if split == 'dev' else 'observed_final']:
            raise ValueError(f'{split}: require complete {expected} verdicts; found {len(rows)}')
        original_verdicts = {}
        for path in sorted((out / 'quality').glob(f'{split}-*.json')):
            payload = load(path)
            verdicts = payload if isinstance(payload, list) else payload.get('records', payload.get('reviews'))
            for verdict in verdicts:
                for rid in verdict.get('review_ids', [verdict.get('review_id')]):
                    original_verdicts[rid] = dict(file=str(path.relative_to(out)), verdict=verdict)
        for row in rows:
            row['completed_review_record'] = original_verdicts[row['review_id']]
        source_records = jsonl(REPO / manifest['config']['dataset_root'] / f'{split}.records.jsonl')
        by_eid = {r['sample_id']: r for r in source_records}
        if len(by_eid) != expected_per_state:
            raise ValueError('duplicate or missing source record')
        # source record sample_id is source-Ln; source_id is the unique student source.
        records[split] = {r['source_id']: r for r in source_records}
        for state in STATES[split]:
            complete = load(out / state / 'complete.json')
            gen = jsonl(out / state / 'generations.jsonl')
            by_generation = {r['example_id']: r for r in gen}
            reviewed = [r for r in rows if r['state'] == state]
            if (len(gen) != expected_per_state or set(by_generation) != set(by_eid)
                    or len(reviewed) != expected_per_state
                    or complete['generation']['calls'] != expected_per_state):
                raise ValueError('incomplete generation/review state ' + state)
            population = Counter((r['sample_id'], r['level']) for r in reviewed)
            if any(v != 1 for v in population.values()) or len({r['sample_id'] for r in reviewed}) != expected_per_state // 4:
                raise ValueError('source/Level population mismatch ' + state)
            generations[state] = by_generation
            for row in reviewed:
                detail = load(out / 'code-evidence' / state / (row['example_id'] + '.json'))
                if detail['generation_sha256'] != digest(by_generation[row['example_id']]):
                    raise ValueError('code evidence generation binding mismatch')
                if detail.get('detail_path'):
                    detail_path = (out / detail['detail_path']).resolve()
                    if not detail_path.is_relative_to(out):
                        raise ValueError('code evidence outside run')
                    detail['bounded_execution_detail'] = load(detail_path)
                evidence[(state, row['example_id'])] = detail
        all_rows[split] = rows
    return all_rows, generations, records, evidence


def costs(out, manifest, rows_by_split, generations):
    events = jsonl(out / 'journal.jsonl')
    reserved = [e['key'] for e in events if e.get('type') == 'generation_reserved']
    if len(reserved) != len(set(reserved)):
        raise ValueError('duplicate generation reservation')
    completed = {e['key']: e['result'] for e in events if e.get('type') == 'generation_completed'}
    primary = [key for key in reserved if not key.startswith('smoke-')]
    smoke_keys = [key for key in reserved if key.startswith('smoke-')]
    if len(primary) > 1120 or len(smoke_keys) > 2:
        raise ValueError('frozen generation budget exceeded')
    train = load(out / 'main/training-result.json')
    if (train['status'] != 'complete' or train['actual_epochs'] != manifest['steps']['epochs']
            or train['actual_optimizer_steps'] != manifest['steps']['main']):
        raise ValueError('main training incomplete')
    encoded = {r['example_id']: r for r in jsonl(out / 'preflight/train.encoded.private.jsonl')}
    token_exposures = {}
    for kind in ('main', 'smoke'):
        forwards = [e['example_id'] for e in events if e.get('type') == 'train_forward' and e.get('kind') == kind]
        token_exposures[kind] = dict(forwards=len(forwards),
            full_tokens=sum(len(encoded[eid]['input_ids']) for eid in forwards),
            completion_tokens=sum(sum(t != -100 for t in encoded[eid]['labels']) for eid in forwards))
    if token_exposures['main']['forwards'] != train['actual_train_forward_calls']:
        raise ValueError('train forward evidence mismatch')
    phases = {}
    for state, by_eid in generations.items():
        complete = load(out / state / 'complete.json')
        gens = list(by_eid.values())
        losses = jsonl(out / state / 'losses.jsonl')
        phases[state] = dict(
            phase_wall_s=complete['wall_s'], generation_wall_s=sum(r['wall_s'] for r in gens),
            teacher_forced_wall_s=sum(r['wall_s'] for r in losses),
            generation_calls=len(gens), teacher_forced_forwards=len(losses),
            input_tokens=sum(r['input_tokens'] for r in gens), output_tokens=sum(r['output_tokens'] for r in gens),
            teacher_forced_completion_tokens=sum(r['completion_tokens'] for r in losses),
            peak_allocated_bytes=complete['peak_allocated_bytes'], peak_reserved_bytes=complete['peak_reserved_bytes'],
            memory_scope=complete['memory_scope'],
            uncertain_call_rows=sum(bool(r.get('call_count_uncertain')) for r in gens))
    loading = [e for e in events if e.get('type') == 'base_model_load_completed']
    smoke_generations = [completed[key] for key in smoke_keys if key in completed]
    totals = {split: {field: sum(phases[state][field] for state in STATES[split]) for field in
              ('phase_wall_s', 'generation_wall_s', 'teacher_forced_wall_s', 'generation_calls',
               'teacher_forced_forwards', 'input_tokens', 'output_tokens', 'teacher_forced_completion_tokens')}
              for split in ('dev', 'final')}
    active, spans = {}, []
    for event in events:
        if event.get('type') == 'stage_started':
            active[event['stage']] = event['utc']
        elif event.get('type') in ('stage_completed', 'technical_failure') and event.get('stage') in active:
            start = active.pop(event['stage'])
            spans.append(dict(stage=event['stage'], start_utc=start, end_utc=event['utc'],
                status=event['type'], elapsed_s=(datetime.fromisoformat(event['utc']) - datetime.fromisoformat(start)).total_seconds()))
    return dict(main_training=train, training_token_exposures=token_exposures,
        smoke_training=load(out / 'smoke/training-result.json'), smoke_reload=load(out / 'smoke/reload-audit.json'),
        smoke_complete=load(out / 'smoke/complete.json'),
        smoke_generations=dict(reservations=len(smoke_keys), completed=len(smoke_generations),
            wall_s=sum(r['wall_s'] for r in smoke_generations),
            input_tokens=sum(r['input_tokens'] for r in smoke_generations),
            output_tokens=sum(r['output_tokens'] for r in smoke_generations)),
        model_loading=dict(completed_loads=len(loading), wall_s=sum(e['wall_s'] for e in loading),
            events=loading, memory_scope='Không có đỉnh VRAM đo riêng cho nạp model; không gán đỉnh train/eval cho nạp.'),
        generation_accounting=dict(primary_reservations=len(primary), primary_completed_journal_keys=sum(k in completed for k in primary),
            smoke_reservations=len(smoke_keys), smoke_completed_journal_keys=sum(k in completed for k in smoke_keys),
            unresolved_reservations=[k for k in reserved if k not in completed],
            interrupted_unknown_events=[e for e in events if e.get('type') == 'generation_interrupted_unknown']),
        evaluation_phases=phases, evaluation_totals=totals, stage_elapsed=spans,
        technical_failures=[e for e in events if e.get('type') == 'technical_failure'],
        note='Không cộng thời gian stage với các pha con. Tổng pha là các phạm vi đã đo, không phải tổng GPU billing; đỉnh VRAM lấy max, không cộng. Chi phí review bằng agent không được telemetry GPU này đo.')


def choose_examples(rows, before_state, after_state, limit=3):
    a = {r['example_id']: r for r in rows if r['state'] == before_state}
    b = {r['example_id']: r for r in rows if r['state'] == after_state}
    result = {}
    for name, predicate in [
        ('joint_improvements', lambda x, y: not joint(x) and joint(y)),
        ('joint_regressions', lambda x, y: joint(x) and not joint(y)),
        ('level_improvements', lambda x, y: x['axes']['level_compliance'] != 'pass' and y['axes']['level_compliance'] == 'pass'),
        ('level_regressions', lambda x, y: x['axes']['level_compliance'] == 'pass' and y['axes']['level_compliance'] != 'pass'),
        ('diagnosis_improvements', lambda x, y: not assessment(x) and assessment(y)),
        ('diagnosis_regressions', lambda x, y: assessment(x) and not assessment(y)),
    ]:
        matches = [eid for eid in sorted(a) if predicate(a[eid], b[eid])]
        seen, selected = set(), []
        for eid in matches:
            sid = a[eid]['sample_id']
            if sid not in seen:
                seen.add(sid)
                selected.append(dict(example_id=eid, source_id=sid, level=a[eid]['level'], faulty=a[eid]['faulty'],
                    before=a[eid], after=b[eid]))
            if len(selected) == limit:
                break
        result[name] = dict(total_pairs=len(matches), representative_pairs=selected,
            selection='Xếp example_id tăng dần, tối đa ba nguồn khác nhau; ví dụ mô tả, không phải mẫu đại diện thống kê.')
    return result


def interpretation(dev_metrics, selected_state):
    v2e, v3e = [dev_metrics[s + '-dev']['overall'] for s in ('v2', selected_state)]
    v2o, v3o = [dev_metrics[s + '-oracle-dev']['overall'] for s in ('v2', selected_state)]
    e2e_delta = v3e['official_level_compliance_rate'] - v2e['official_level_compliance_rate']
    oracle_delta = v3o['oracle_fidelity_level_successful'] / v3o['targets'] - v2o['oracle_fidelity_level_successful'] / v2o['targets']
    diag_delta = v3e['supported_faulty_diagnosis'] - v2e['supported_faulty_diagnosis']
    if e2e_delta > 0 and v3e['faulty_misses_with_invalid'] > v2e['faulty_misses_with_invalid']:
        text = 'Level end-to-end tăng nhưng số bỏ sót lỗi cộng invalid tăng: có đánh đổi tính đúng nhiệm vụ lấy tuân thủ bề mặt; ưu tiên chẩn đoán và khả năng phát hiện lỗi.'
    elif oracle_delta > 0 and diag_delta <= 0:
        text = 'Oracle fidelity+Level cải thiện nhưng chẩn đoán end-to-end không tăng: bằng chứng phù hợp với chẩn đoán còn là khâu giới hạn. Ưu tiên cải thiện chẩn đoán trong một thí nghiệm riêng.'
    elif v3o['level_compliant'] < .95*v3o['targets'] and v3e['level_compliant'] < .95*v3e['targets']:
        text = 'Cả oracle và end-to-end còn không đạt mục tiêu Level: học biểu đạt đúng Level vẫn chưa được giải quyết; cần theo dõi chẩn đoán đồng thời.'
    elif oracle_delta > 0 and diag_delta > 0:
        text = 'Cả oracle fidelity+Level và số chẩn đoán có căn cứ đều tăng trong mẫu đã quan sát. Mức tăng dưới đây chỉ mô tả bộ synthetic này; chưa suy ra hiệu quả public hay chọn kiến trúc hai bước.'
    else:
        text = 'Các trục thay đổi không đồng nhất; chưa đủ bằng chứng quy kết một khâu duy nhất. Xem riêng lỗi chẩn đoán, fidelity và disclosure trong casebook trước một thí nghiệm tiếp theo.'
    additional=[]
    if oracle_delta>0 and diag_delta<=0:
        additional.append('Oracle fidelity+Level tăng trong khi số chẩn đoán end-to-end có căn cứ không tăng: chẩn đoán vẫn là điểm cần ưu tiên, dù oracle không tạo ra phân rã nhân quả thuần túy.')
    if v3o['level_compliant']<.95*v3o['targets'] and v3e['level_compliant']<.95*v3e['targets']:
        additional.append('Trên dev, cả hai probe vẫn dưới mục tiêu Level 95%; học diễn đạt theo Level cũng chưa được giải quyết. Cần đọc riêng các Level còn yếu, đồng thời giữ các điều kiện bảo toàn chẩn đoán.')
    return dict(additional_findings_vi=additional,e2e_level_delta_percentage_points=100*e2e_delta,
        oracle_fidelity_plus_level_delta_percentage_points=100*oracle_delta,
        supported_faulty_diagnosis_count_delta=diag_delta,
        faulty_misses_with_invalid_count_delta=v3e['faulty_misses_with_invalid']-v2e['faulty_misses_with_invalid'],
        conclusion_vi='Trên dev, ' + text[0].lower() + text[1:],
        causal_limit='Target và prompt cùng đổi; oracle cung cấp dữ kiện và đổi nhiệm vụ. Không coi chênh lệch hai probe là phân rã nhân quả hoặc dự báo điểm public.')


def casebook(split, rows, generations, records, evidence, manifest, oracle_findings=None):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['sample_id']].append(row)
    def esc(value):
        return html.escape(str(value), quote=True)
    def pre(value):
        return '<pre>' + esc(value if isinstance(value, str) else dump(value)) + '</pre>'
    parts = ['<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Task3 v3 — paired ' + split + '</title><style>body{font:15px system-ui;margin:24px;background:#f4f6f8;color:#18212b}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px ui-monospace,monospace;background:#edf1f5;padding:12px}section{background:white;padding:18px;margin:20px 0;border-radius:10px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}.card{border:1px solid #cbd5e1;padding:12px;border-radius:8px;min-width:0}.ok{border-top:5px solid #23855b}.bad{border-top:5px solid #bb4444}summary{cursor:pointer;font-weight:600;padding:8px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #cbd5e1;padding:5px;text-align:left}input{padding:10px;width:min(700px,90%)}</style>',
        '<h1>Task3 SFT v3 — paired casebook ' + split + '</h1>',
        '<p>Đã nhúng toàn bộ phán quyết hoàn tất, raw/parsed kể cả invalid, đề, mã nguồn và bằng chứng code. Review bằng agent có căn cứ nguồn; không phải human gold độc lập. Các trạng thái dùng cùng prompt v3. Final đã từng được quan sát, không phải unseen độc lập.</p>',
        '<p>' + esc(f'{len(rows)} targets; {len(grouped)} nguồn duy nhất. Invalid vẫn ở mẫu số. Joint theo policy đã đóng băng; không chấm qua độ dài hay từ khóa.') + '</p>',
        '<label>Lọc nguồn/nội dung: <input id="filter" type="search" placeholder="source_id, Level, trạng thái, nội dung"></label>']
    order = {state: i for i, state in enumerate(STATES[split])}
    for sid in sorted(grouped):
        record = records[sid]
        x = record['input']
        parts += ['<section class="source" id="' + esc(sid) + '"><h2>' + esc(sid) + '</h2>',
                  '<p>Nguồn SHA256: <code>' + hashlib.sha256(x['code'].encode()).hexdigest() + '</code>; ' +
                  ('faulty' if grouped[sid][0]['faulty'] else 'clean') + '</p>',
                  '<details open><summary>Đề bài đầy đủ và chế độ nộp</summary>' + pre(x['statement']) + pre({'exam_type': x['exam_type'], 'language': x.get('language')}) + '</details>',
                  '<details><summary>Mã nguồn đầy đủ, số dòng chỉ để đối chiếu</summary>' + pre('\n'.join(f'{i:3}: {line}' for i, line in enumerate(x['code'].splitlines(), 1))) + '</details>',
                  '<details><summary>Syntax-only diagnostic đầu vào</summary>' + pre(x['compile_log']) + '</details>']
        if split == 'dev' and oracle_findings and sid in oracle_findings:
            parts.append('<details><summary>Oracle findings đã review và đóng băng trước generation</summary>' + pre(oracle_findings[sid]) + '</details>')
        for level in (1, 2, 3, 4):
            parts += ['<h3 id="' + esc(f'{sid}-L{level}') + '">Level ' + str(level) + '</h3><div class="grid">']
            for row in sorted([r for r in grouped[sid] if r['level'] == level], key=lambda r: order[r['state']]):
                raw = generations[row['state']][row['example_id']]
                parts += ['<article class="card ' + ('ok' if joint(row) else 'bad') + '"><h4>' + esc(row['state']) + '</h4>',
                    '<p>' + esc(f"status={row['status']}; joint={'pass' if joint(row) else 'fail'}; code={row['code_verdict']}; review_id={row['review_id']}") + '</p>',
                    '<table><tr><th>Trục review</th><th>Phán quyết</th></tr>' + ''.join('<tr><td>' + esc(AXIS_VI[a]) + '</td><td>' + esc(row['axes'][a]) + '</td></tr>' for a in AXES) + '</table>',
                    '<h5>Bằng chứng và lý do review đã hoàn tất</h5>' + pre(row['evidence']),
                    '<details><summary>Phán quyết review gốc, gồm code resolution nếu có</summary>' + pre(row.get('completed_review_record', row)) + '</details>',
                    '<details open><summary>Parsed (null nếu invalid)</summary>' + pre(row['parsed']) + '</details>',
                    '<details><summary>Raw nguyên vẹn</summary>' + pre(row['raw']) + '</details>',
                    '<details><summary>Metadata generation, parser, token, thời gian</summary>' + pre({k: v for k, v in raw.items() if k not in ('raw', 'parsed')}) + '</details>',
                    '<details><summary>Bằng chứng code đầy đủ và bounded compile/runtime</summary>' + pre(evidence[(row['state'], row['example_id'])]) + '</details></article>']
            parts.append('</div>')
        parts.append('</section>')
    parts += ['<script>document.getElementById("filter").addEventListener("input",function(){const q=this.value.toLowerCase();document.querySelectorAll(".source").forEach(s=>s.hidden=!s.textContent.toLowerCase().includes(q));});</script></html>']
    return '\n'.join(parts)


def report_text(out, analysis, records):
    m, selection, cost = analysis['manifest'], analysis['selection'], analysis['costs']
    ds, train = analysis['dataset_manifest'], cost['main_training']
    selected = analysis['selected_dev_state']
    final_v2 = analysis['metrics']['final']['v2-final']['overall']
    final_v3 = analysis['metrics']['final']['v3-selected-final']['overall']
    lines = ['# Task 3 SFT v3 — QLoRA, 26/10/2026', '',
        f"Đã hoàn thành **{train['actual_epochs']} epoch, {train['actual_optimizer_steps']} optimizer steps**, scheduler {train['actual_scheduler_steps']} steps, {train['actual_train_forward_calls']} train forwards. Checkpoint được khóa từ dev: **step {selection['step']}** (`{selection['checkpoint']}`). " +
        ('Đạt các điều kiện eligibility so với v2 cùng prompt.' if selection['passes_preliminary_conditions'] else '**Không đạt điều kiện promotion**; đây là candidate chẩn đoán theo fallback đã đóng băng, vẫn đánh giá observed-final.'), '',
        analysis['interpretation']['conclusion_vi']+' '+' '.join(analysis['interpretation'].get('additional_findings_vi',[])), '',
        f"Observed-final, v2 → selected v3: báo lỗi giả clean **{final_v2['clean_false_alarms']} → {final_v3['clean_false_alarms']}/{final_v3['clean_targets']}**; faulty miss cộng invalid **{final_v2['faulty_misses_with_invalid']} → {final_v3['faulty_misses_with_invalid']}/{final_v3['faulty_targets']}**; chẩn đoán faulty có căn cứ **{final_v2['supported_faulty_diagnosis']} → {final_v3['supported_faulty_diagnosis']}/{final_v3['faulty_targets']}**; faulty L3 repair **{final_v2['faulty_l3_correct']} → {final_v3['faulty_l3_correct']}/{final_v3['faulty_l3_targets']}**. Đây là hậu kiểm, không thay selection.", '',
        f"Official-Level của selected v3 trên final: **{ratio(final_v3['level_compliant'], final_v3['targets'])}**; L1/L2/L3/L4 lần lượt " + ' / '.join(ratio(analysis['metrics']['final']['v3-selected-final']['by_level'][str(l)]['level_compliant'], analysis['metrics']['final']['v3-selected-final']['by_level'][str(l)]['targets']) for l in (1, 2, 3, 4)) + '. ' + ('Đạt 95% tổng. ' if final_v3['level_goal_95_reached'] else 'Chưa đạt 95% tổng. ') + ('Đạt 95% ở mọi Level.' if all(v['level_goal_95_reached'] for v in analysis['metrics']['final']['v3-selected-final']['by_level'].values()) else 'Chưa đạt 95% ở mọi Level.'), '',
        f"Joint final tăng {final_v2['joint_successful']} → {final_v3['joint_successful']}/{final_v3['targets']}, trong đó clean tăng {analysis['metrics']['final']['v2-final']['by_status']['clean']['joint_successful']} → {analysis['metrics']['final']['v3-selected-final']['by_status']['clean']['joint_successful']}/{final_v3['clean_targets']} nhưng faulty giảm {analysis['metrics']['final']['v2-final']['by_status']['faulty']['joint_successful']} → {analysis['metrics']['final']['v3-selected-final']['by_status']['faulty']['joint_successful']}/{final_v3['faulty_targets']}. Mức tăng joint tổng không đồng nghĩa chẩn đoán lỗi tốt hơn.", '',
        'Điểm A **0.3834**, SFT v2 **0.3567**, B **0.3247** là số lịch sử do người dùng báo, không phải phép đo mới. Không chạy public inference/submission và không suy điểm public từ báo cáo này.', '',
        '## Dữ liệu, hợp đồng và giới hạn diễn giải', '',
        f"Train: {ds['train_sources']} nguồn / {ds['train_targets']} targets ({ds['train_clean_sources']} clean, {ds['train_faulty_sources']} faulty); thay {ds['target_changes']} targets, quarantine {len(ds['quarantined_sources'])} nguồn. Giữ nguyên source/spec/split và gold lịch sử. Dev: 20 nguồn × 4 Levels = 80 targets/probe/state; final: 40 nguồn × 4 Levels = 160 targets/state. 640 dev + 480 final = 1120 primary outputs.", '',
        'Dev dùng chọn checkpoint; observed-final là bộ synthetic đã từng được xem, chỉ mở nội dung sau khi khóa selection trong lần chạy này. Hai bộ không độc lập hoặc thật sự unseen. Review nguồn/đề bằng agent, ẩn danh trạng thái nơi khả thi; không phải human gold độc lập. Nhiều Levels và trạng thái dùng lại cùng nguồn nên các targets phụ thuộc; không coi 1120 outputs là 1120 chương trình độc lập.', '',
        'Hợp đồng chính thức (trích nguyên định nghĩa đã đóng băng):', '']
    for item in analysis['official_contract']['definitions']:
        lines += [f"- **{item['level']}**: “{item['định nghĩa']}” Cấm: “{item['cấm']}”"]
    lines += ['', 'L2 được nhiều câu và chẩn đoán chính xác; không yêu cầu nói mơ hồ. L3 được hướng sửa cục bộ cụ thể, không đưa lời giải hoàn chỉnh. L4 được cung cấp code nhưng vắng code không tự động fail. Clean không cần phát minh lỗi/hướng sửa. Wrong hint được chấm riêng khỏi disclosure. Code đã cung cấp mà sai hoặc chưa được giải quyết làm joint fail.', '',
        'Joint = valid + chẩn đoán/bao phủ/fidelity có căn cứ + đúng Level + tiếng Việt; faulty L2–L4 cần vị trí/điều kiện; faulty L3 cần hướng sửa đúng hữu ích; L4 cần hữu ích; code được cung cấp cần đúng. Supported faulty diagnosis đòi valid, nhãn lỗi không rỗng, diagnosis+coverage+fidelity đều pass. Repair L3 chỉ tính faulty L3 có assessment và hướng sửa pass. Invalid ở mọi mẫu số và các trục invalid là not_evaluable.', '',
        '## Dev: end-to-end và oracle', '']
    for probe, states in [('End-to-end', [s for s in STATES['dev'] if '-oracle-' not in s]), ('Oracle-assisted (chỉ evaluation)', [s for s in STATES['dev'] if '-oracle-' in s])]:
        lines += ['### ' + probe, '', table(['Trạng thái', 'Targets/nguồn', 'Invalid', 'Level đúng', 'Joint', 'Balanced joint', 'Fidelity+Level'], [
            [s, f"{(v:=analysis['metrics']['dev'][s]['overall'])['targets']}/{v['sources']}", v['invalid'], ratio(v['level_compliant'], v['targets']), ratio(v['joint_successful'], v['targets']), percent(v['balanced_joint']), ratio(v['oracle_fidelity_level_successful'], v['targets'])] for s in states]), '',
            table(['Trạng thái', 'Clean báo lỗi giả', 'Clean invalid', 'Faulty miss valid', 'Faulty invalid', 'Miss + invalid', 'Chẩn đoán có căn cứ', 'Faulty L3 repair'], [
            [s, ratio((v:=analysis['metrics']['dev'][s]['overall'])['clean_false_alarms'], v['clean_targets']), ratio(v['clean_invalids'], v['clean_targets']), ratio(v['faulty_misses'], v['faulty_targets']), ratio(v['faulty_invalids'], v['faulty_targets']), ratio(v['faulty_misses_with_invalid'], v['faulty_targets']), ratio(v['supported_faulty_diagnosis'], v['faulty_targets']), ratio(v['faulty_l3_correct'], v['faulty_l3_targets'])] for s in states]), '']
    lines += ['### Level và mục tiêu 95% (mô tả)', '', table(['Trạng thái', 'Tổng', 'L1', 'L2', 'L3', 'L4', 'Đạt ≥95% tổng + mọi Level'], [
        [s, ratio((v:=analysis['metrics']['dev'][s]['overall'])['level_compliant'], v['targets'])] + [ratio(analysis['metrics']['dev'][s]['by_level'][str(l)]['level_compliant'], analysis['metrics']['dev'][s]['by_level'][str(l)]['targets']) for l in (1, 2, 3, 4)] +
        ['Có' if all(analysis['metrics']['dev'][s][key].get('level_goal_95_reached', False) for key in ['overall']) and all(x['level_goal_95_reached'] for x in analysis['metrics']['dev'][s]['by_level'].values()) else 'Không'] for s in STATES['dev']]), '',
        'Mỗi Level dev có 20 targets, chung 20 nguồn; 95% tương ứng ít nhất 19/20 mỗi Level và 76/80 tổng. Đây là đích mô tả, không phải khoảng tin cậy thống kê hay điều kiện promotion duy nhất.', '',
        '## Selection đã khóa trước observed-final', '',
        table(['Step', 'Eligible', 'Điều kiện không đạt', 'E2E Level', 'Balanced joint', 'Oracle fidelity+Level tie-break', 'Dev loss'], [
            [c['step'], 'Có' if c['step'] in selection['eligible_steps'] else 'Không', ', '.join(selection['eligibility_failures'][str(c['step'])]) or 'Không', ratio(c['level_compliant'], c['targets']), percent(c['balanced_joint']), c['oracle_joint'], f"{c['mean_loss']:.6f}"] for c in selection['candidates']]), '',
        'So v2 cùng prompt, invalid/clean false alarm/faulty miss cộng invalid không được tăng; supported faulty diagnosis và correct faulty-L3 repair không được giảm. Eligible: ưu tiên Level, balanced joint, oracle joint, loss thấp, checkpoint sớm. Không eligible: ưu tiên balanced joint, diagnosis, Level, checkpoint sớm. Không chọn lại bằng kết quả final. `selection.json` và seal/evidence đã kiểm tra.', '',
        '## Observed-final end-to-end', '', table(['Trạng thái', 'Targets/nguồn', 'Invalid', 'Level đúng', 'Joint', 'Balanced joint'], [
        [s, f"{(v:=analysis['metrics']['final'][s]['overall'])['targets']}/{v['sources']}", v['invalid'], ratio(v['level_compliant'], v['targets']), ratio(v['joint_successful'], v['targets']), percent(v['balanced_joint'])] for s in STATES['final']]), '',
        table(['Trạng thái', 'Clean báo lỗi giả', 'Clean invalid', 'Faulty miss valid', 'Faulty invalid', 'Miss + invalid', 'Chẩn đoán có căn cứ', 'Faulty L3 repair'], [
        [s, ratio((v:=analysis['metrics']['final'][s]['overall'])['clean_false_alarms'], v['clean_targets']), ratio(v['clean_invalids'], v['clean_targets']), ratio(v['faulty_misses'], v['faulty_targets']), ratio(v['faulty_invalids'], v['faulty_targets']), ratio(v['faulty_misses_with_invalid'], v['faulty_targets']), ratio(v['supported_faulty_diagnosis'], v['faulty_targets']), ratio(v['faulty_l3_correct'], v['faulty_l3_targets'])] for s in STATES['final']]), '',
        table(['Trạng thái', 'L1', 'L2', 'L3', 'L4', 'Đạt ≥95% tổng + mọi Level'], [
        [s] + [ratio(analysis['metrics']['final'][s]['by_level'][str(l)]['level_compliant'], analysis['metrics']['final'][s]['by_level'][str(l)]['targets']) for l in (1, 2, 3, 4)] +
        ['Có' if analysis['metrics']['final'][s]['overall']['level_goal_95_reached'] and all(x['level_goal_95_reached'] for x in analysis['metrics']['final'][s]['by_level'].values()) else 'Không'] for s in STATES['final']]), '',
        'Mỗi Level final có 40 targets/40 nguồn, nên 95% là 38/40; tổng 152/160. Tất cả kết quả final ở trên là mô tả regression sau selection, không phải một lần chọn mô hình mới.', '',
        '## Biểu đạt và chẩn đoán: độ lớn thay đổi', '',
        f"Selected v3 so v2 trên dev: E2E Level **{analysis['interpretation']['e2e_level_delta_percentage_points']:+.1f} điểm phần trăm**; oracle fidelity+Level **{analysis['interpretation']['oracle_fidelity_plus_level_delta_percentage_points']:+.1f} điểm phần trăm**; supported faulty diagnosis **{analysis['interpretation']['supported_faulty_diagnosis_count_delta']:+d} targets**; faulty misses cộng invalid **{analysis['interpretation']['faulty_misses_with_invalid_count_delta']:+d} targets**.", '',
        analysis['interpretation']['conclusion_vi']+' '+' '.join(analysis['interpretation'].get('additional_findings_vi',[])), '', analysis['interpretation']['causal_limit'], '',
        'Oracle fidelity+Level (tie-break `oracle_joint`) đòi valid, supported diagnosis/coverage/fidelity, Level, tiếng Việt, vị trí/điều kiện khi cần và code đã cung cấp đúng; không gồm cổng L3 repair/L4 usefulness. Full oracle task joint trong bảng đòi thêm hai cổng đó. Định nghĩa vận hành này được đóng băng trước primary dev output trong `oracle-metric-definition.json`. Oracle được cho findings đúng đã review, end-to-end chỉ nhận đề/source/mode/syntax log/Level. Thành công oracle không được gọi là thành công production. Thí nghiệm này không tự động đổi pipeline production thành hai bước, không tự động v4 hoặc huấn luyện thêm.', '',
        '## Ví dụ cải thiện và regression có bằng chứng', '']
    labels = {'joint_improvements': 'Joint cải thiện', 'joint_regressions': 'Joint regression', 'level_improvements': 'Level cải thiện', 'level_regressions': 'Level regression', 'diagnosis_improvements': 'Assessment cải thiện', 'diagnosis_regressions': 'Assessment regression'}
    for split in ('dev', 'final'):
        lines += [f'### {split}: v2 → selected v3', '']
        for kind, group in analysis['paired_changes'][split].items():
            lines += [f"**{labels[kind]}**: {group['total_pairs']} cặp target. {group['selection']}", '']
            if not group['representative_pairs']:
                lines += ['Không có cặp thuộc loại này.', '']
            for pair in group['representative_pairs']:
                sid, eid = pair['source_id'], pair['example_id']
                code = records[split][sid]['input']['code']
                lines += [f"- `{eid}` ({'faulty' if pair['faulty'] else 'clean'}); xem [{split} casebook](../../{out.relative_to(REPO)}/{split}-paired-casebook.html#{eid}).", '',
                    '  Nguồn (toàn bộ snippet ngắn; casebook giữ đầy đủ đề và mã):', '',
                    '```cpp\n' + '\n'.join(f'{i}: {line}' for i, line in enumerate(code.splitlines(), 1)) + '\n```', '']
                for side, name in [('before', 'v2'), ('after', 'v3')]:
                    row = pair[side]
                    feedback = row['parsed']['feedback'] if row['parsed'] else row['raw']
                    lines += [f"**{name}**: status `{row['status']}`, joint `{'pass' if joint(row) else 'fail'}`; review: {row['evidence']}", '',
                        '> ' + feedback[:1600].replace('\n', '\n> ') + ('\n> [Phần còn lại có trong casebook.]' if len(feedback) > 1600 else ''), '']
    lines += ['## Chi phí thực tế và phạm vi đo', '']
    accounting = cost['generation_accounting']
    lines += [f"Journal: {accounting['primary_reservations']} primary reservations, {accounting['primary_completed_journal_keys']} completion keys; {accounting['smoke_reservations']} smoke reservations, {accounting['smoke_completed_journal_keys']} smoke completion keys; {len(accounting['unresolved_reservations'])} reservations chưa có completion. Reservations không đồng nghĩa chắc chắn đã chạy nếu bị ngắt; raw missing/invalid vẫn giữ nguyên.", '']
    def gib(value):
        return f'{value / 2**30:.3f}'
    cost_rows = [['Main training', f"{train['wall_s']:.3f}", train['actual_optimizer_steps'], cost['training_token_exposures']['main']['full_tokens'], cost['training_token_exposures']['main']['completion_tokens'], gib(train['peak_allocated_bytes']), gib(train['peak_reserved_bytes']), train['peak_memory_scope']],
                 ['Smoke training', f"{cost['smoke_training']['wall_s']:.3f}", cost['smoke_training']['actual_optimizer_steps'], cost['training_token_exposures']['smoke']['full_tokens'], cost['training_token_exposures']['smoke']['completion_tokens'], gib(cost['smoke_training']['peak_allocated_bytes']), gib(cost['smoke_training']['peak_reserved_bytes']), 'Chỉ khoảng Trainer smoke; không bao gồm reload/generation'],
                 ['Smoke generations', f"{cost['smoke_generations']['wall_s']:.3f}", cost['smoke_generations']['completed'], cost['smoke_generations']['input_tokens'], cost['smoke_generations']['output_tokens'], 'không đo riêng', 'không đo riêng', 'Hai lần kiểm tra save/reload; không dùng cập nhật smoke cho main'],
                 ['Model loading', f"{cost['model_loading']['wall_s']:.3f}", cost['model_loading']['completed_loads'], '—', '—', 'không đo riêng', 'không đo riêng', cost['model_loading']['memory_scope']]]
    for state, value in cost['evaluation_phases'].items():
        cost_rows.append([state, f"{value['phase_wall_s']:.3f}", value['generation_calls'], value['input_tokens'], value['output_tokens'], gib(value['peak_allocated_bytes']), gib(value['peak_reserved_bytes']), value['memory_scope']])
    lines += [table(['Pha', 'Wall s', 'Steps/calls', 'Input/full tokens', 'Output/completion tokens', 'Peak allocated GiB', 'Peak reserved GiB', 'Phạm vi'], cost_rows), '',
        table(['Evaluation', 'Generation calls', 'Generation s', 'Teacher-forced forwards', 'Teacher-forced s', 'Input tokens', 'Output tokens', 'TF completion tokens'], [
            [split, v['generation_calls'], f"{v['generation_wall_s']:.3f}", v['teacher_forced_forwards'], f"{v['teacher_forced_wall_s']:.3f}", v['input_tokens'], v['output_tokens'], v['teacher_forced_completion_tokens']] for split, v in cost['evaluation_totals'].items()]), '',
        cost['note'], '',
        'Qwen được huấn luyện/sinh cục bộ, không gọi API thương mại cho các lượt Qwen. Không có đơn giá điện/thuê GPU hoặc telemetry chi phí/token của các agent Codex, nên không suy ra tổng chi phí tiền tệ.', '',
        f"Smoke: {cost['smoke_complete']['optimizer_steps']} optimizer steps, {cost['smoke_complete']['generations']} generations; reload passed={cost['smoke_reload']['passed']}, max |logit difference|={cost['smoke_reload']['max_abs_difference']}. Main dùng adapter mới; smoke updates bị bỏ, optimizer/scheduler/RNG khởi tạo lại theo bằng chứng `main-freshness.json`. Không yêu cầu mọi LoRA tensor có gradient khác không ở bước đầu.", '',
        'Chi phí code audit (không Qwen, không semantic retry): ' + dump(analysis['code_audit_counts']).replace('\n', ' '), '',
        '## Cấu hình, checkpoint và bảo toàn', '',
        'Phần cứng thực tế: ' + dump(analysis['hardware']).replace('\n', ' ') + '.', '',
        f"Pinned `{m['config']['model_id']}` revision `{m['config']['revision']}`. NF4 double quant/BF16; LoRA r16/alpha32/dropout0.05; q/k/v/o/gate/up/down. LR2e-5, AdamW weight_decay0, cosine/warmup0.03/clip1, batch1/accum4/seed42. Train8192 không packing/truncation, assistant-only loss gồm termination, equal-example mean/loss_weight1, remove_unused_columns=False. Evaluation32768, không đổi RoPE/tokenizer, greedy một lần; L1–3 tối đa1024, L4 tối đa1536, max_time45s. Actual arguments: `main/actual-training-arguments.json`; manifest lưu đủ giá trị và phiên bản thư viện.", '',
        table(['Checkpoint', 'Files trong identity', 'Identity SHA256', 'Được chọn'], [[step, len(data['files']), data['identity_sha256'], 'Có' if step == str(selection['step']) else 'Không'] for step, data in analysis['checkpoint_identities'].items()]), '',
        f"Manifest SHA256 `{analysis['artifact_hashes']['manifest.json']}`; selection SHA256 `{analysis['artifact_hashes']['selection.json']}`. HEAD `{m['head']}`, branch `{m['branch']}`. Preservation-after passed={analysis['preservation_after']['passed']}; root predictions SHA256 `{analysis['preservation_after']['root_predictions_sha256']}`. Initial file hashes và historical indices được giữ; báo cáo không sửa chúng.", '',
        'Tất cả data/model/tokenizer/chat-template/code/adapter/checkpoint hashes, generation/state/review/code-evidence hashes và actual arguments được nhúng trong `analysis.json` hoặc identity/manifest được liên kết bằng SHA256. `analysis.json` giữ nguyên đầy đủ manifest và initial-workspace-state; các đối tượng này không được chỉnh sửa.', '',
        '## Kiểm tra và lệnh tái lập', '', analysis['validation']['task3_tests'], '',
        'Full pytest đã thử nhưng collection có 2 lỗi thiếu `sklearn` ở hai file Task1 (và 5 skipped); đây không phải bằng chứng toàn bộ repository pass. Log gốc: `pytest-full.log`. Script báo cáo kiểm tra đủ verdicts, population, manifest/selection seal, generation bindings và bảo toàn trước khi ghi; không chạy model/C++.', '',
        'Các lệnh đã dùng theo thứ tự. Không chạy lại trên workspace đã hoàn tất: prepare cố ý từ chối dataset v3 đã tồn tại. Tái lập trong môi trường riêng cần source/spec/split, ba audit train, oracle audit đã đóng băng và initial-workspace-state mới hợp lệ trước prepare/freeze. Review thủ công bằng agent phải hoàn tất giữa packets và metrics/select; không có lệnh tự động tạo human gold:', '',
        '```bash\n' + '\n'.join(analysis['reproduction_commands']) + '\n```', '',
        '## Phụ lục: mọi mẫu số theo Level và clean/faulty', '']
    for split in ('dev', 'final'):
        lines += ['### ' + split, '', table(['Trạng thái', 'L', 'Clean n/nguồn', 'Faulty n/nguồn', 'Clean Level', 'Faulty Level', 'Clean false alarm / invalid', 'Faulty miss / invalid', 'Faulty diagnosis', 'Faulty L3 repair', 'Clean joint', 'Faulty joint'], [
            [state, level, f"{(c:=analysis['metrics'][split][state]['by_level_and_status'][str(level)]['clean'])['targets']}/{c['sources']}", f"{(f:=analysis['metrics'][split][state]['by_level_and_status'][str(level)]['faulty'])['targets']}/{f['sources']}", ratio(c['level_compliant'], c['targets']), ratio(f['level_compliant'], f['targets']), f"{c['clean_false_alarms']} / {c['clean_invalids']} (n={c['targets']})", f"{f['faulty_misses']} / {f['faulty_invalids']} (n={f['targets']})", ratio(f['supported_faulty_diagnosis'], f['targets']), ratio(f['faulty_l3_correct'], f['faulty_l3_targets']), ratio(c['joint_successful'], c['targets']), ratio(f['joint_successful'], f['targets'])]
            for state in STATES[split] for level in (1, 2, 3, 4)]), '']
    lines += ['### Phong cách tùy chọn, tách khỏi official Level', '',
        table(['Trạng thái', 'Median ký tự L1/L2/L3/L4', 'Nguồn đủ 4 valid', 'Độ dài tăng nghiêm ngặt'], [[state, '/'.join(str(v['by_level'][str(l)]['median_characters']) for l in (1, 2, 3, 4)), v['all_four_valid_sources'], v['strictly_increasing_character_lengths']] for state, v in analysis['style_only'].items()]), '',
        'Đếm câu trong analysis là xấp xỉ (có thể gặp dấu câu trong code); độ dài và thứ tự độ dài không làm pass/fail Level, không chọn checkpoint. Báo cáo/casebook giữ mọi invalid và phán quyết uncertain; hữu hạn test code không chứng minh mọi input đúng. Dữ liệu synthetic có thể không đại diện phân bố public; agent review và việc gold từng được xem hạn chế khả năng khái quát.', '',
        'Công cụ hỗ trợ: Codex/GPT-6 viết mã, audit target và thực hiện source-grounded agent review; Qwen/Qwen2.5-Coder-7B-Instruct là mô hình được huấn luyện/đánh giá. Review là hậu kiểm thí nghiệm, không can thiệp hoặc sửa output suy luận.', '',
        'Artifact: `analysis.json`, `dev-paired-casebook.html`, `final-paired-casebook.html` trong thư mục run; các casebooks hoạt động offline, không tải tài nguyên mạng.', '']
    return '\n'.join(lines)


def build(out, report, validation_note):
    manifest = load(out / 'manifest.json')
    if sha(out / 'manifest.json') != load(out / 'manifest.sha256.json')['sha256']:
        raise ValueError('manifest seal changed')
    verify(REPO, out, manifest)
    current_preservation = preservation(REPO, out)
    selection = validate_selection(REPO, out, manifest)
    review_identity = load(out / 'review-code-identity.json')
    for name, expected in review_identity['code'].items():
        if sha(REPO / name) != expected:
            raise ValueError('review code changed: ' + name)
    if sha(out / 'oracle-metric-definition.json') != review_identity['oracle_metric_definition_sha256']:
        raise ValueError('oracle metric definition changed')
    initial = load(out / 'initial-workspace-state.json')
    # Require a completed external preservation check, and never replace an
    # artifact that existed before this experiment.
    preserved = load(out / 'preservation-after.json')
    if preserved.get('passed') is not True or preserved['root_predictions_sha256'] != initial['root_predictions_sha256']:
        raise ValueError('completed preservation check is required')
    if preserved != current_preservation:
        raise ValueError('current preservation differs from the completed external check')
    outputs = [report, out / 'analysis.json', out / 'dev-paired-casebook.html', out / 'final-paired-casebook.html']
    for path in outputs:
        if not path.is_relative_to(REPO) or str(path.relative_to(REPO)) in initial['files']:
            raise ValueError('report destination would replace a preexisting/protected file')
    rows, generations, records, evidence = validate_populations(out, manifest)
    metrics = {split: summarize_states(rows[split], STATES[split]) for split in ('dev', 'final')}
    selected_state = 'v3-epoch' + str(manifest['steps']['checkpoints'].index(selection['step']) + 1)
    for split in ('dev', 'final'):
        existing = out / 'reviewed' / (split + '-metrics.json')
        if existing.exists():
            original = load(existing)
            # Check common frozen summary fields only; enhanced descriptive
            # counters belong to this report and do not modify metric files.
            for state in STATES[split]:
                for key, value in original[state]['overall'].items():
                    if metrics[split][state]['overall'][key] != value:
                        raise ValueError('review metrics differ from completed metrics artifact')
    artifact_hashes = {str(p.relative_to(out)): sha(p) for p in [out / 'manifest.json', out / 'selection.json', out / 'journal.jsonl', out / 'initial-workspace-state.json', out / 'preservation-after.json', out / 'oracle-metric-definition.json', out / 'review-code-identity.json']}
    for directory, pattern in [('quality', '*.json'), ('review-packets', '*binding.private.json'), ('reviewed', '*.json'), ('code-evidence', '**/*')]:
        for path in sorted((out / directory).glob(pattern)):
            if not path.is_file():
                continue
            artifact_hashes[str(path.relative_to(out))] = sha(path)
    for state in STATES['dev'] + STATES['final']:
        for name in ('complete.json', 'generations.jsonl', 'losses.jsonl', 'state-binding.json'):
            artifact_hashes[f'{state}/{name}'] = sha(out / state / name)
    checkpoints = {}
    for step in manifest['steps']['checkpoints']:
        path = out / 'main' / f'checkpoint-{step}' / 'checkpoint-identity.json'
        checkpoints[str(step)] = dict(path=str(path.parent), identity_sha256=sha(path), files=load(path))
    code_counts = dict(targets=len(evidence), statuses=dict(Counter(v['status'] for v in evidence.values())),
        compile_calls=sum(v.get('compile_calls', 0) for v in evidence.values()),
        runtime_calls=sum(v.get('runtime_calls', 0) for v in evidence.values()))
    cmd = '/workspace/llm-final-project/.venv-task3/bin/python'
    run = str(out.relative_to(REPO))
    reproduction = [f'cd {REPO}', 'export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false',
        f'{cmd} scripts/task3_sft_v3_prepare.py --out {run}',
        f'{cmd} scripts/task3_sft_v3_experiment.py freeze --out {run}',
        f'{cmd} scripts/task3_sft_v3_experiment.py train-dev --out {run}',
        f'{cmd} scripts/task3_sft_v3_review.py code --split dev --out {run}',
        f'{cmd} scripts/task3_sft_v3_review.py packets --split dev --out {run}',
        '# Hoàn tất source-grounded agent review 640 dev targets vào quality/dev-*.json.',
        f'{cmd} scripts/task3_sft_v3_review.py metrics --split dev --out {run}',
        f'{cmd} scripts/task3_sft_v3_review.py select --out {run}',
        f'{cmd} scripts/task3_sft_v3_experiment.py final --out {run}',
        f'{cmd} scripts/task3_sft_v3_review.py code --split final --out {run}',
        f'{cmd} scripts/task3_sft_v3_review.py packets --split final --out {run}',
        '# Hoàn tất source-grounded agent review 480 final targets vào quality/final-*.json.',
        f'{cmd} scripts/task3_sft_v3_review.py metrics --split final --out {run}',
        f'{cmd} scripts/task3_sft_v3_experiment.py verify --out {run}',
        f'{cmd} scripts/task3_sft_v3_report.py --out {run}']
    analysis = dict(version='task3-sft-v3-report-v1', created_utc=datetime.now(timezone.utc).isoformat(),
        report_script_sha256=sha(Path(__file__)), manifest=manifest, selection=selection,
        selected_dev_state=selected_state, dataset_manifest=load(REPO / manifest['config']['dataset_root'] / 'dataset-manifest.json'),
        hardware=load(out / 'hardware.json'),official_contract=load(out / 'official-contract.json'), oracle_metric_definition=load(out / 'oracle-metric-definition.json'), initial_workspace_state=initial,
        preservation_after=preserved, checkpoint_identities=checkpoints, artifact_hashes=artifact_hashes,
        actual_training_arguments=load(out / 'main/actual-training-arguments.json'), main_freshness=load(out / 'main-freshness.json'),
        metrics=metrics, costs=costs(out, manifest, rows, generations), code_audit_counts=code_counts,
        style_only=style_summary(rows['dev'] + rows['final']),
        interpretation=interpretation(metrics['dev'], selected_state),
        paired_changes=dict(dev=choose_examples(rows['dev'], 'v2-dev', selected_state + '-dev'),
                            final=choose_examples(rows['final'], 'v2-final', 'v3-selected-final')),
        validation=dict(task3_tests=validation_note, full_collection_log='pytest-full.log',
            review_coverage=dict(dev=len(rows['dev']), final=len(rows['final'])),
            selection_seal_verified=True, generation_review_bindings_verified=True,
            current_frozen_inputs_verified=True, current_preservation_verified=True,
            current_review_code_identity_verified=True),
        historical_user_reported_scores=dict(A=.3834, sft_v2=.3567, B=.3247),
        independence='Synthetic, previously observed; source-grounded agent review, not independent human gold.',
        reproduction_commands=reproduction)
    text = report_text(out, analysis, records)
    oracle_packet = load(REPO / manifest['config']['dataset_root'] / 'oracle-dev.private.json')
    oracle_rows = oracle_packet if isinstance(oracle_packet, list) else oracle_packet['records']
    oracle_findings = {row['source_id']: row for row in oracle_rows}
    books = {split: casebook(split, rows[split], generations, records[split], evidence, manifest, oracle_findings) for split in ('dev', 'final')}
    return analysis, text, books


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--report', type=Path, default=DEFAULT_REPORT)
    parser.add_argument('--check-only', action='store_true', help='Validate/build in memory; write nothing.')
    parser.add_argument('--task3-test-result', default='Bộ Task3 cuối: 1992 passed, 15 skipped trong 12.43s; safeguards liên quan: 37 passed trong 3.43s. Log: pytest-task3-final.log và pytest-final-relevant.log.')
    args = parser.parse_args()
    out, report = args.out.resolve(), args.report.resolve()
    if not out.is_relative_to(REPO / 'outputs/task3') or not report.is_relative_to(REPO / 'reports/task3'):
        raise ValueError('output paths must remain under this repository task3 output/report directories')
    analysis, text, books = build(out, report, args.task3_test_result)
    if args.check_only:
        print(dump(dict(status='validated_no_writes', reviews=analysis['validation']['review_coverage'])))
        return
    # All prerequisites are validated before any report artifact is written.
    report.parent.mkdir(parents=True, exist_ok=True)
    (out / 'analysis.json').write_text(dump(analysis) + '\n', encoding='utf-8')
    for split, book in books.items():
        (out / (split + '-paired-casebook.html')).write_text(book, encoding='utf-8')
    report.write_text(text, encoding='utf-8')
    print(dump(dict(report=str(report), analysis=str(out / 'analysis.json'),
                    casebooks=[str(out / (s + '-paired-casebook.html')) for s in ('dev', 'final')],
                    review_coverage=analysis['validation']['review_coverage'])))


if __name__ == '__main__':
    main()
