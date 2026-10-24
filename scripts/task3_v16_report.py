#!/usr/bin/env python3
"""Offline final packaging for the frozen v1.6 bounded experiment; no inference."""
from __future__ import annotations
import argparse
from collections import Counter
import html
import json
import re
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.task3.dataset import read_json,write_json
from src.task3.level_blind import digest,sha
from src.task3.v16_experiment import jsonl,metrics
from src.task3 import arm_d_plus_v15 as old
from scripts.task3_arm_d_plus import validate_export


def load(path,default=None):return read_json(path) if Path(path).exists() else default


def risk_selection(out):
    rows=load(out/'public/results.private.json',[]);flags=[]
    selected=set(read_json(out/'public-review-selection.json')['ids'])
    for r in rows:
        if not r.get('terminal'):continue
        reasons=[];feedback=(r.get('output') or {}).get('feedback','')
        findings=(r.get('stage1') or {}).get('findings',[])
        stated=' '.join(f['location']+' '+f['error'] for f in findings)
        if r['status']!='resolved':reasons.append('structural_failure')
        if r['level']==2 and (re.search(r'\b(?:cần|nên|hãy)\b.{0,60}\b(?:thêm|xóa|thay|đổi|khởi tạo|sửa|sử dụng|dùng|tăng|giảm|đặt|gán)\b',feedback,re.I)
            or re.search(r'\b(?:thay)\b.{0,80}\bbằng\b|\bđổi\b.{0,60}\bthành\b',feedback,re.I)):
            reasons.append('suspected_L2_repair')
        if re.search(r'\bmain\b',feedback,re.I) and not re.search(r'\bmain\b',stated,re.I):reasons.append('suspected_main_location_drift')
        for f in findings:
            err=f['error'].lower()
            if 'uninitializ' in err and ('global' in err or 'static' in err):reasons.append('suspected_global_initialization_claim')
            if any(t in err for t in ('timezone','time zone','locale')):reasons.append('suspected_invented_optional_requirement')
        if reasons:flags.append(dict(sample_id=r['sample_id'],reasons=sorted(set(reasons)),result_sha256=digest(r),overlaps_preselected=r['sample_id'] in selected))
    value=dict(policy=read_json(out/'public-risk-policy.json'),processed_terminal=sum(bool(r.get('terminal')) for r in rows),
        final=len(rows)==328 and all(r.get('terminal') for r in rows),cases=flags,
        flag_counts=dict(Counter(reason for f in flags for reason in f['reasons'])))
    write_json(out/'public-risk-selected.private.json',value)
    return value


def measurement_layers(out):
    layers={}
    for phase in ('renderer','paired-A','paired-B','internal-A','internal-B','public'):
        rows=read_json(out/phase/'results.private.json');stages={}
        for stage in ('taxonomy','feedback'):
            checks=[]
            for r in rows:
                sid=r.get('sample_id',r.get('case_id'))
                for attempt in (0,1):
                    p=out/phase/'normalized-responses'/(digest([sid,stage,attempt])+'.audit.json')
                    if p.exists():checks.append(read_json(p))
            stages[stage]=dict(evaluated_responses=len(checks),raw_json_compliance=sum(r['raw_format_compliant'] for r in checks),
                transport_envelope_success=sum(r['transport_normalized_success'] for r in checks),
                schema_reference_success=sum(r['schema_reference_success'] for r in checks),
                failures=dict(Counter(r['failure']['category'] for r in checks if r.get('failure'))))
        layers[phase]=dict(stages=stages,input_count=len(rows),mapped_detector_coverage=sum(r.get('stage1') is not None for r in rows),
            feedback_valid=sum(r['status']=='resolved' for r in rows),
            mapping_methods=dict(Counter(a['mapping_method'] for r in rows for a in r.get('mapping_audit',[]))),
            note='Audited response counts include attempt0 replay and corrections separately; they are not new-call costs. L1 templates have no feedback response.')
    write_json(out/'measurement-layers.json',layers)
    return layers


def explicit_replay_bindings(out):
    """Materialize per-ID replay lineage in every standalone private result view."""
    for phase in ('internal','public'):
        records=read_json(out/'replay'/phase/'per-id.private.json')
        provenance={r['sample_id']:r['baseline'].get('provenance') for r in records}
        path=out/'replay'/phase/'replay-results.private.json';rows=read_json(path)
        for r in rows:
            r['replay_provenance']=provenance[r['sample_id']]
            r['new_parser_identity']='v16-transport-strict-six-fields-v1'
            if r['stage1'] is not None and not r['replay_provenance']:raise ValueError('unbound replay result')
        write_json(path,rows)


def quality_and_examples(out):
    reviews=read_json(out/'reviews/internal-and-probes.private.json');public=read_json(out/'reviews/public.private.json')
    oldpath=ROOT/'outputs/task3/internal-arm-d-plus-v1.5-compiler-refs/renderer-eval/reviews.private.json'
    historical=[r for r in read_json(oldpath) if r['prompt_version']=='v15']
    current=reviews['renderer']
    quality=dict(renderer_fixed=dict(historical_v15_n=len(historical),new_n=len(current),
        historical_disclosure_pass=sum(r['verdicts']['level2_disclosure'] for r in historical),
        new_disclosure_pass=sum(r['level2_disclosure'] for r in current),
        historical_joint_pass=sum(all(r['verdicts'][k] for k in ('factual_fidelity','location_cause','level2_disclosure','empty_findings')) for r in historical),
        new_joint_pass=sum(all(r[k] for k in ('fidelity','location_cause','level2_disclosure','empty_findings')) for r in current),
        caveat='Different prompts/parser histories; fixed findings, no controlled raw-format claim'),internal={},public=public.get('summary',{}))
    for arm in ('A','B'):
        rows=read_json(out/f'internal-{arm}/results.private.json');by={r['sample_id']:r for r in rows}
        rr=reviews['internal'][arm];l2=[r for r in rr if by[r['sample_id']]['level']==2 and by[r['sample_id']]['output'] is not None]
        quality['internal'][arm]=dict(all30_reviewed=len(rr),unsupported_cases=sum(r['unsupported_case'] for r in rr),
            findings_factual=dict(Counter(r['findings_factual'] for r in rr)),
            feedback_fidelity=dict(Counter(r['feedback_fidelity'] for r in rr)),
            feedback_factual=dict(Counter(r['feedback_factual'] for r in rr)),
            level_compliance=dict(Counter(r['level_compliance'] for r in rr)),
            actual_L2=dict(n=len(l2),level_compliance=dict(Counter(r['level_compliance'] for r in l2))))
    write_json(out/'quality-summary.private.json',quality)
    selected=read_json(out/'selection.json')['selected'];rows=read_json(out/f'internal-{selected}/results.private.json')
    by={r['sample_id']:r for r in rows};ub={u['sample_id']:u for u in read_json(out/'inputs/internal.private.json')}
    rb={r['sample_id']:r for r in reviews['internal'][selected]}
    choices=['SYN-COUNT-0002','SYN-COUNT-0011','SYN-SUMPAIR-0017','SYN-COUNTEVEN-0015','SYN-GEN-0021',
             'SYN-POWER-0006','SYN-RANGE-0004','SYN-POWER-0007-L2','SYN-SUMPAIR-0005']
    choices=[sid for sid in choices if sid in by]
    for r in rows:
        rev=rb[r['sample_id']]
        if rev['findings_factual']=='pass' and rev['feedback_factual']=='pass' and rev['level_compliance']=='pass' and r['sample_id'] not in choices:
            choices.append(r['sample_id']);break
    while len(choices)<10:
        choices.append(next(s for s in by if s not in choices))
    text=['# Ví dụ thật Task 3 v1.6','',f'Arm nội bộ được chọn chung: {selected}. Nội dung findings/feedback dưới đây là output thực, không chỉnh bằng tay. Review được ghi riêng, không đưa vào prompt.']
    def example(phase,u,r,review):
        return [f'\n## {u["sample_id"]} — {phase}, requested Level{u["level"]}',
                '\nNguồn nguyên văn:\n```cpp\n'+u['task']['code']+'\n```',
                '\nFindings thực tế:\n```json\n'+json.dumps(r['stage1'],ensure_ascii=False,indent=2)+'\n```',
                '\nFeedback thực tế: '+(r['output']['feedback'] if r.get('output') else 'KHÔNG CÓ OUTPUT HỢP LỆ'),
                '\nFailure thực tế: '+json.dumps(r.get('failure'),ensure_ascii=False),
                '\n**Review riêng của agent:** '+json.dumps(review,ensure_ascii=False)]
    for sid in choices:text+=example('internal-'+selected,ub[sid],by[sid],rb[sid])
    # Print an exhausted case from A even if the globally selected arm is B.
    arows=read_json(out/'internal-A/results.private.json');ar={r['sample_id']:r for r in reviews['internal']['A']}
    failed=next((r for r in arows if r['status']=='unresolved'),None)
    if failed:text+=example('A dev — exhausted recovery, không phải public fallback',ub[failed['sample_id']],failed,ar[failed['sample_id']])
    pubrows=read_json(out/'public/results.private.json');pubby={r['sample_id']:r for r in pubrows}
    pubu={u['sample_id']:u for u in read_json(out/'inputs/public.private.json')};pubr={r['sample_id']:r for r in public['cases']}
    public_choices=[s for s in ('Class03-Final-1-S52','Class01-Test2-S40','Class01-Test1-S45','Class01-Test1-S01') if s in pubr]
    good=next((r['sample_id'] for r in public['cases'] if r['findings_factual']=='pass' and r['feedback_factual']=='pass' and r['level_compliance']=='pass'),None)
    clean=next((r['sample_id'] for r in public['cases'] if r.get('source_assessment',{}).get('no_supported_issue_reason')),None)
    for sid in (good,clean):
        if sid and sid not in public_choices:public_choices.append(sid)
    for sid in public_choices:text+=example('selected public',pubu[sid],pubby[sid],pubr[sid])
    path=out/'EXAMPLES.vi.private.md';path.write_text('\n'.join(text)+'\n',encoding='utf-8');path.chmod(0o600)
    return quality


def casebooks(out):
    reviews=read_json(out/'reviews/internal-and-probes.private.json')
    public_reviews=read_json(out/'reviews/public.private.json')
    indexes={}
    for phase in ('internal-A','internal-B','public'):
        units=read_json(out/'inputs'/('public.private.json' if phase=='public' else 'internal.private.json'))
        rows=read_json(out/phase/'results.private.json');by={r['sample_id']:r for r in rows}
        revs=public_reviews['cases'] if phase=='public' else reviews['internal'][phase[-1]]
        revby={r['sample_id']:r for r in revs}
        records=[];index=[]
        attempts=jsonl(out/phase/'attempts.jsonl')
        replay=load(out/'replay'/('public' if phase=='public' else 'internal')/'per-id.private.json',[])
        replay_by={r['sample_id']:r for r in replay}
        text=['<!doctype html><meta charset="utf-8"><title>Task3 v1.6 casebook</title>',
              '<style>body{font:15px system-ui;max-width:1200px;margin:30px auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f4f6;padding:12px}details{margin:14px 0}article{border-bottom:2px solid #555;margin:32px 0}</style>',
              '<h1>'+phase+'</h1><p>Private student data. Source-grounded agent review; not independent human grading. Unreviewed cases have explicit status.</p>']
        for u in units:
            sid=u['sample_id'];r=by[sid];review=revby.get(sid)
            if review and review['result_sha256']!=digest(r):raise ValueError('casebook review binding mismatch')
            record=dict(sample_id=sid,level=u['level'],family=u['family'],source=u['task']['code'],task=u['task'],
                source_catalog=u['source_catalog'],local_compiler=u['local_compiler'],result=r,review=review,
                review_status='source_reviewed' if review else 'schema_status_provenance_only',
                new_attempts=[a for a in attempts if a['sample_id']==sid],historical_replay=replay_by.get(sid))
            records.append(record)
            index.append(dict(sample_id=sid,level=u['level'],family=u['family'],status=r['status'],
                detector_valid=r['stage1'] is not None,feedback_valid=r['status']=='resolved',failure=r['failure'],
                arm=r['arm'],review_status=record['review_status'],result_sha256=digest(r),
                casebook_anchor=sid,provenance=r.get('replay_provenance'),new_call_keys=[a['key'] for a in record['new_attempts']]))
            def block(title,value):
                body=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)
                return '<details><summary>'+html.escape(title)+'</summary><pre>'+html.escape(body)+'</pre></details>'
            text+=['<article id="'+html.escape(sid,quote=True)+'"><h2>'+html.escape(sid)+f' — Level{u["level"]}</h2>',
                block('Full statement, requirements and metadata',u['task']),block('Original source',u['task']['code']),
                block('Actual findings and exact extracted evidence',r['stage1']),block('Actual feedback / failure',dict(output=r['output'],failure=r['failure'])),
                block('Separately labelled agent review',review if review else record['review_status']),
                block('Original separate logs, source catalog and hashes',u['source_catalog']),
                block('New journal rows',record['new_attempts']),block('Historical attempt0 / attempt1 replay evidence',record['historical_replay']),'</article>']
        write_json(out/phase/'casebook.private.json',records);write_json(out/phase/'complete-index.private.json',index)
        path=out/phase/'CASEBOOK.private.html';path.write_text('\n'.join(text),encoding='utf-8');path.chmod(0o600)
        indexes[phase]=index
    return indexes


def final_checks(out):
    frozen=read_json(out/'method-freeze.json')
    changed=[n for n,h in frozen['code_sha256'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    if changed:raise ValueError('frozen inference code drift: '+str(changed))
    oldroot=ROOT/'outputs/task3/v1.5-observation-20261024'
    manifest=read_json(out/'historical-manifest-before.json')
    historical_changed=[n for n,h in manifest.items() if not (oldroot/n).is_file() or sha(oldroot/n)!=h]
    if historical_changed:raise ValueError('historical artifacts changed')
    selected=read_json(out/'selection.json')
    if sha(out/'reviews/internal-and-probes.private.json')!=selected['reviews_sha256']:raise ValueError('selection review drift')
    public_review=read_json(out/'reviews/public.private.json');risk=risk_selection(out)
    expected_review=set(read_json(out/'public-review-selection.json')['ids'])|{r['sample_id'] for r in risk['cases']}
    actual=[r['sample_id'] for r in public_review['cases']]
    if not risk['final'] or len(actual)!=len(set(actual)) or set(actual)!=expected_review:raise ValueError('public review population incomplete')
    if public_review.get('draft') or public_review.get('independent_human') is not False:raise ValueError('public review status invalid')
    labels=frozen['labels']['taxonomy_error'];summary={}
    for phase in ('internal-A','internal-B','public'):
        source='public' if phase=='public' else 'internal'
        requested=read_json(out/'inputs'/f'{source}-requested-levels.private.json')
        rows=read_json(out/phase/'results.private.json');units=read_json(out/'inputs'/f'{source}.private.json');by={u['sample_id']:u for u in units}
        if len(rows)!=len(requested) or {r['sample_id'] for r in rows}!=set(requested):raise ValueError('final IDs mismatch')
        for r in rows:
            if r['level']!=by[r['sample_id']]['level']:raise ValueError('final Level mismatch')
            if r['stage1'] is not None:old.validate_normalized(r['stage1']['findings'],by[r['sample_id']],labels)
            if phase=='public' and r['arm']!=selected['selected']:raise ValueError('public method mixing')
        try:valid=validate_export(out/phase,requested,labels)
        except ValueError:valid=read_json(out/phase/'validation.json')
        write_json(out/phase/'unresolved.private.json',[r for r in rows if r['status']!='resolved'])
        write_json(out/phase/'detector-results.private.json',[dict(sample_id=r['sample_id'],level=r['level'],stage1=r['stage1'],failure=r['failure'],
            replay_provenance=r.get('replay_provenance'),method_freeze_sha256=sha(out/'method-freeze.json')) for r in rows])
        write_json(out/phase/'normalized-findings.private.json',{r['sample_id']:{**r['stage1'],
            'replay_provenance':r.get('replay_provenance'),'method_freeze_sha256':sha(out/'method-freeze.json')} for r in rows if r['stage1'] is not None})
        summary[phase]=dict(expected=len(requested),detector_valid=sum(r['stage1'] is not None for r in rows),
            feedback_valid=sum(r['status']=='resolved' for r in rows),invalid=len([r for r in rows if r['status']!='resolved']),export=valid)
    write_json(out/'final-validation.json',dict(frozen_code_unchanged=True,historical_artifacts_unchanged=True,historical_files_checked=len(manifest),phases=summary))
    return summary


def report(out,summary,indexes):
    replay=read_json(out/'offline-replay-summary.json');comp=read_json(out/'internal-comparison.private.json')
    selected=read_json(out/'selection.json');reviews=read_json(out/'reviews/internal-and-probes.private.json')
    public_reviews=read_json(out/'reviews/public.private.json');cost=read_json(out/'costs-and-runtime.json')
    rr=reviews.get('renderer',[])
    old_fixture=read_json(ROOT/'outputs/task3/internal-arm-d-plus-v1.5-compiler-refs/renderer-eval/reviews.private.json')
    old_outputs=read_json(ROOT/'outputs/task3/internal-arm-d-plus-v1.5-compiler-refs/renderer-eval/outputs.private.json')
    mlines=['# Task 3 v1.6 — kết quả thử nghiệm có giới hạn','',
        f'Phương pháp được chọn chung: **{selected["selected"]}**. Public đạt **{summary["public"]["feedback_valid"]}/328** output hợp lệ về cấu trúc; complete export: **{summary["public"]["export"]["passed"]}**. Chất lượng chẩn đoán và Level được đo riêng; không có public gold để chứng nhận accuracy.',
        '', 'Model thực tế: Qwen/Qwen2.5-Coder-7B-Instruct, revision c03e6d358207e414f1eca0bb1891e29f1db0e242, toàn bộ tham số BF16 trên CUDA:0; không 4-bit/offload. Giữ greedy seed42, concurrency1, context32768, findings1536, renderer1024 và max_time45s.',
        '', '| Cùng internal30, gold giữ nguyên | Detector-valid | E2E | micro-F1 | macro-F1 | TP/FP/FN | exact |',
        '|---|---:|---:|---:|---:|---|---:|']
    hist=comp['historical']['primary']['detector']
    for name,key in [('D lịch sử','D'),('v1.4 strict','v14'),('v1.5 strict gốc','v15_observation')]:
        m=hist[key];e2e=comp['historical']['baseline_bindings'][key]['end_to_end_available']
        mlines.append(f'| {name} | {m["valid"]} | {e2e} | {m["micro_f1"]:.10f} | {m["macro_f1"]:.10f} | {m["TP"]}/{m["FP"]}/{m["FN"]} | {m["exact_count"]} |')
    m=comp['replay_only_A']
    mlines.append(f'| A chỉ replay attempt0 | {m["valid"]} | chưa render | {m["micro_f1"]:.10f} | {m["macro_f1"]:.10f} | {m["TP"]}/{m["FP"]}/{m["FN"]} | {m["exact_count"]} |')
    for arm in ('A','B'):
        m=comp[arm]['detector'];e2e=comp[arm]['end_to_end']['valid']
        mlines.append(f'| {arm} hoàn tất recovery | {m["valid"]} | {e2e} | {m["micro_f1"]:.10f} | {m["macro_f1"]:.10f} | {m["TP"]}/{m["FP"]}/{m["FN"]} | {m["exact_count"]} |')
    mlines+=['','Invalid vẫn là None, không phải clean đúng. Primary tính đủ30 ID; valid-only và matched secondary có ID/denominator riêng trong artifacts. Internal30, paired probes và tám fixture đều là dữ liệu phát triển đã xem, không phải heldout độc lập.',
        '', 'Chuẩn hóa deterministic khôi phục đầu ra đã lãng phí:','']
    for phase in ('internal','public'):
        c=replay[phase];b=c['baseline'];a=c['historical_correction']
        mlines.append(f'- {phase}: attempt0 raw JSON {b["raw_json_compliance"]}, schema/reference {b["schema_reference_success"]}/{b["population"]}, direct official {b["direct_official_success"]}, pending mapping {b["pending_mapping"]}. Historical attempt1 direct official {a["direct_official_success"]}; chỉ là bằng chứng riêng. {c["historical_avoided_correction_rows"]["count"]} correction lịch sử có thể tránh theo policy transport; đây là accounting lịch sử, không phải speedup đo từ fresh run.')
    mlines+=['','Số replay trùng phân tích trước: internal27/30 và public299 nhãn official trực tiếp ở attempt0,303 ở attempt1. Schema/reference public302/306 gồm thêm3 pending mapping mỗi lượt. Termination được kiểm tra trước parsing: attempt0 có7 length, attempt1 có3; một public chưa từng có generation vì context. Không dùng attempt1 thay attempt0, không chọn theo gold.',
        '', 'Sửa hướng dẫn suy luận và lựa chọn chung:',
        f'B tăng F1 và detector coverage nhưng unsupported cases tăng16→21. Điều kiện unsupported không đạt; mọi điều kiện còn lại đạt. Vì vậy chọn A theo policy đã đóng băng, không chọn theo từng public ID.',
        'B chỉ thay đoạn reasoning; A/B dùng cùng parser, log projection, resolver, recovery, renderer và backend. Paired score là số cặp đáp ứng cả hai vế, gồm invariance không buộc có lỗi. Một response chỉ đúng schema không được tính là hiểu cặp. Khi có verdict tranh luận, policy dùng A.',
        '', '| Arm | Unsupported-finding cases /30 | Clean false alarm / invalid | Paired đúng cả cặp /6 |',
        '|---|---:|---|---:|']
    for arm in ('A','B'):
        m=comp[arm]['detector'];a=selected[arm]
        mlines.append(f'| {arm} | {a["unsupported_cases"]} | {m["clean_false_alarms"]}/{m["clean_invalid"]} | {a["paired_score"]} |')
    q=read_json(out/'quality-summary.private.json')
    mlines+=['','A có3 ca không có stage1: not_evaluable, không tính là factual pass hay clean đúng. Count unsupported ở bảng dùng đủ30 ID theo policy; phép so sánh cùng27 ID hợp lệ được lưu riêng ở internal-matched-secondary.private.json.',
        '', 'Review source-grounded bởi Codex agent, không phải human độc lập. Rubric phân biệt supported, partially supported/mislocated, unsupported, condition omitted, invented optional requirement, genuine omission và gold disagreement. Gold không bị sửa. Review renderer-fidelity tách khỏi detector đúng/sai và khỏi Level.',
        '', f'Renderer L2 trên tám findings cố định: disclosure pass {q["renderer_fixed"]["historical_disclosure_pass"]}/8→{q["renderer_fixed"]["new_disclosure_pass"]}/8; joint fidelity/location/disclosure {q["renderer_fixed"]["historical_joint_pass"]}/8→{q["renderer_fixed"]["new_joint_pass"]}/8. Location/điều kiện vẫn bị mất ở một số câu.',
        'Actual internal A: L2 pass6/9, fail3/9; B pass4/10, fail6/10 (gồm một feedback tiếng Anh). V1.5 gốc chỉ có một L2 hợp lệ và ca đó vẫn lộ cách sửa ở v1.6: SYN-SUMPAIR-0017 nói cần thêm chấm phẩy, đồng thời giữ location prob1 sai từ detector. Coverage khác nhau nên không kết luận cải thiện nhân quả trên actual outputs. Các từ khóa thêm/đổi chỉ làm tín hiệu review, không phải bộ lọc semantic.',
        '', 'Độ phủ public và review: Level115/163/50/0 từ authoritative mapping; không lấy Level theo hậu tố ID. Tất cả328 được audit ID/schema/status/provenance. Slice24+ được chọn bằng hash theo family/Level trước inference; mọi failure/flag được review riêng. Không gọi slice này là public accuracy.',
        f'Review52 ca khác nhau =24 chọn trước +32 risk −4 trùng. Slice24: factual pass4/mixed12/fail7/not-evaluable1; Level pass15/mixed4/fail4/not-evaluable1. Risk32: factual pass1/mixed12/fail3/not-evaluable16; Level pass4/mixed1/fail11/not-evaluable16. Các verdict không phải tỷ lệ accuracy của public.',
        '', 'Context case dùng diagnostic view generic: full source2492 ký tự/100 dòng và toàn bộ yêu cầu được giữ nguyên. Supplied/local logs gốc52303/41653 ký tự giữ riêng. View ưu tiên primary error/warning và source/caret, giữ nguyên số dòng gốc, hash/ranges/omissions/token audit; refs không được trỏ vào dòng chưa trình bày. Source-missing-header giữ status/history gốc và điều tra readiness lịch sử, không cần sửa classifier hoặc source.',
        '', 'Các blocker cuối cùng:6 schema/kind sai,7 reference (thiếu refs, ngoài nguồn hoặc dòng chưa trình bày),3 generation length; không còn lỗi outer JSON transport. Danh sách đủ16 ID và raw history ở public/unresolved.private.json. Class01-Test1-S01 đã fit context nhưng lặp ref supplied-log29 chưa trình bày (một note overload), nên vẫn thất bại sau một correction.',
        'Lỗi chất lượng còn lại có ví dụ cụ thể: Class03-Final-1-S52 cáo buộc i/j chưa khởi tạo dù nguồn đã gán; Class01-Test2-S40 tự đặt yêu cầu locale/timezone rồi trả feedback tiếng Anh; Class01-Test1-S45 nhận ra hàm rỗng nhưng nói Hãy đảm bảo… ở L2. SYN-SUMPAIR-0005 còn đưa biểu thức sửa không đúng. Xem source, actual finding/feedback và review riêng trong EXAMPLES.vi.private.md.',
        '', 'Chi phí mới (mọi failed/recovery/resolver đều tính):','',
        '| Phase | Normal | Correction | Resolver | Input tokens | Output tokens | Call latency(s) |',
        '|---|---:|---:|---:|---:|---:|---:|']
    total_in=total_out=total_calls=0
    for phase,c in cost['phases'].items():
        stages=list(c['by_stage'].values());n=sum(x['normal_calls'] for x in stages);r=sum(x['correction_calls'] for x in stages);v=sum(x['resolver_calls'] for x in stages)
        it=sum(x['input_tokens'] for x in stages);ot=sum(x['output_tokens'] for x in stages);lat=sum(x['latency_s'] for x in stages)
        total_in+=it;total_out+=ot;total_calls+=c['total_calls']
        mlines.append(f'| {phase} | {n} | {r} | {v} | {it} | {ot} | {lat:.3f} |')
    runtime=read_json(out/'runtime-after-load-1.json');accounting=read_json(out/'additional-runtime-accounting.json')
    mlines+=['',f'Tổng {total_calls} call mới (331 text generations +3 resolver forward passes), input/output token {total_in}/{total_out}. Model loads thực tế: {len(cost["model_loads"])}; load {runtime["load_latency_s"]:.3f}s; peak allocated/reserved sau inference {runtime["peak_gpu_memory_allocated_bytes"]/2**30:.3f}/{runtime["peak_gpu_memory_reserved_bytes"]/2**30:.3f}GiB. 715 generations v1.5 và27 fixture calls cũ là lịch sử, không phải chi phí mới. Replay offline không tạo call Qwen mới.',
        f'Elapsed process {cost["process_elapsed_s"]:.3f}s, gồm khoảng {accounting["review_checkpoint_interval_s_from_artifact_mtimes"]:.3f}s tại checkpoint review (ước từ mtime artifact). Compiler preparation12 calls và12 calls preflight bổ sung được tính riêng; không chạy unsafe variants. Bằng chứng compiler của358 input lịch sử được tái dùng, không báo là compile/cache hit mới.',
        '', 'Kiểm thử và tính toàn vẹn: 1713 passed,15 skipped ở relevant Task3 regression. Full repository pytest đã thử nhưng collection bị chặn do thiếu sklearn tại test_clm_zeroshot_task1.py và test_task1_clm_probe.py (5 skipped,2 errors); không cài dependency mới. RED→GREEN cho parser/field errors/provenance/dispute policy; code review hai P2 đã sửa trước freeze. git diff --check và offline token/hash/reference/export verification được chạy và lưu. Mọi2226 artifact lịch sử khớp hash ban đầu.',
        '', 'Bằng chứng và giới hạn: đã xác minh normalization giữ payload, schema/reference checks, bounded/resumable execution, phép so sánh trên dữ liệu phát triển và validator ID chính xác khi xuất. Public bị từ chối complete export vì thiếu16 ID. Chưa đo public accuracy, khả năng tổng quát hóa trên tập độc lập, hay sự hoàn hảo semantic/Level; JSON hợp lệ không chứng minh diagnosis đúng. Không tự sửa feedback bằng tay, không upload/submit, không commit/push.',
        '', 'Artifacts: [public export/status](public/validation.json), [offline replay](offline-replay-summary.json), [internal comparison](internal-comparison.private.json), [selection](selection.json), [frozen method](method-freeze.json), [quality](quality-summary.private.json), [internal A casebook](internal-A/CASEBOOK.private.html), [internal B casebook](internal-B/CASEBOOK.private.html), [public casebook](public/CASEBOOK.private.html), [ví dụ thật](EXAMPLES.vi.private.md), [commands](reproduction-commands.json), [cost/runtime](costs-and-runtime.json), [final verification](final-validation.json).']
    (out/'REPORT.vi.md').write_text('\n'.join(mlines)+'\n',encoding='utf-8')
    write_json(out/'new-cost-totals.json',dict(calls=total_calls,input_tokens=total_in,output_tokens=total_out))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    summary=final_checks(out);explicit_replay_bindings(out);risk_selection(out);measurement_layers(out);quality_and_examples(out);indexes=casebooks(out);report(out,summary,indexes)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
