"""Validate completed local artifacts and produce the Vietnamese experiment report."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.task3.sft_v1 import load_split,read_jsonl,sha256,verify_checksums
from src.task3.sft_v1_experiment import Journal,write_json
from src.task3.sft_v1_runtime import verify_frozen

STATES=['base-dev','step-80-dev','step-160-dev','base-test','selected-test']
DIMS=['diagnosis_supported','location_and_condition','unsupported_defects','level_compliance',
      'vietnamese_compliance','l3_repair_direction','l4_solution_quality']


def fmt(v):
    return 'N/A' if v is None else f'{v:.4f}'


def report(run):
    frozen=json.loads((run/'manifest.json').read_text());verify_frozen(REPO,run,frozen)
    execution=json.loads((run/'execution-result.json').read_text())
    root=REPO/frozen['config']['dataset_root'];verify_checksums(root)
    examples={s:load_split(root,s) for s in ('dev','test')}
    reviews={}
    for path in sorted((run/'quality').glob('*.json')):
        data=json.loads(path.read_text())
        if not isinstance(data,list):continue
        for row in data:
            key=(row['state'],row['example_id'])
            if key in reviews:raise ValueError('duplicate quality review '+str(key))
            if set(row['dimensions'])!=set(DIMS):raise ValueError('incomplete rubric '+str(key))
            if not set(row['dimensions'].values())<={'pass','fail','uncertain','not_applicable','not_evaluable'}:
                raise ValueError('unknown review verdict '+str(key))
            reviews[key]=row
    if len(reviews)!=400:
        raise ValueError('expected exactly 400 reviewed target responses')
    semantic={};counts={};comparison=[];invalid=[]
    for state in STATES:
        generations=read_jsonl(run/state/'generations.jsonl')
        invalid.extend(dict(state=state,**row) for row in generations if row['status']!='valid')
        summary=json.loads((run/state/'complete.json').read_text())
        if len(generations)!=80 or len({g['example_id'] for g in generations})!=80:
            raise ValueError('incomplete or duplicate generation state')
        selected=[reviews[(state,g['example_id'])] for g in generations]
        if len({r['sample_id'] for r in selected})!=20:raise ValueError('wrong source denominator')
        for g,r in zip(generations,selected):
            if r['status']!=g['status'] or r['level']!=g['level'] or r['sample_id']!=g['sample_id']:
                raise ValueError('quality/source mismatch')
            if g['status']!='valid' and set(r['dimensions'].values())!={'not_evaluable'}:
                raise ValueError('invalid output has evaluable semantic verdict')
            if not r.get('evidence'):raise ValueError('quality row lacks grounded rationale')
        semantic[state]=dict(targets=80,sources=20,review_type='agent_review_not_independent_or_official',
            dimensions={d:dict(Counter(r['dimensions'][d] for r in selected)) for d in DIMS},
            by_level={str(level):{d:dict(Counter(r['dimensions'][d] for r in selected if r['level']==level))
                                  for d in DIMS} for level in range(1,5)})
        m=summary['metrics'];counts[state]=dict(loss=summary['mean_loss'],valid=m['valid_outputs'],
            invalid=m['invalid_outputs'],taxonomy=m['taxonomy']['all_targets_conservative'],
            clean_false_alarms=m['clean_false_alarms'],costs=m['costs'],per_level=m['by_level'])
    for split,before,after in [('dev','base-dev',f"step-{execution['selection']['step']}-dev"),
                                ('test','base-test','selected-test')]:
        bg={r['example_id']:r for r in read_jsonl(run/before/'generations.jsonl')}
        ag={r['example_id']:r for r in read_jsonl(run/after/'generations.jsonl')}
        for e in examples[split]:
            a=reviews[(before,e['example_id'])];b=reviews[(after,e['example_id'])]
            gains=[d for d in DIMS if a['dimensions'][d]=='fail' and b['dimensions'][d]=='pass']
            regressions=[d for d in DIMS if a['dimensions'][d]=='pass' and b['dimensions'][d]=='fail']
            if gains or regressions:
                comparison.append(dict(split=split,example_id=e['example_id'],source_id=e['sample_id'],
                    level=e['level'],gains=gains,regressions=regressions,
                    before=bg[e['example_id']],after=ag[e['example_id']],
                    before_review=a,after_review=b))
    events=Journal(run/'journal.jsonl').events()
    actual=dict(execution['counts'])
    actual['teacher_forced_evaluation_forwards']=sum(len(read_jsonl(run/s/'losses.jsonl')) for s in STATES)
    actual['training_forwards']=sum(e.get('type')=='train_forward' for e in events)
    actual['smoke_reload_logit_forwards']=2 if (run/'smoke/reload-audit.json').exists() else 0
    actual['adapter_reloads']=sum(e.get('type')=='adapter_loaded' for e in events)+int((run/'smoke/reload-audit.json').exists())
    for step in (80,160):
        checkpoint=run/'main'/f'checkpoint-{step}'
        for name,expected in json.loads((checkpoint/'checkpoint-identity.json').read_text()).items():
            if sha256(checkpoint/name)!=expected:raise ValueError('checkpoint identity changed')
    original=json.loads((run/'initial-workspace-state.json').read_text())
    preserved=[p for p,h in original['files'].items() if not (REPO/p).exists() or sha256(REPO/p)!=h]
    if preserved:raise ValueError('prior files changed: '+str(preserved))
    main=json.loads((run/'main/training-result.json').read_text())
    smoke=json.loads((run/'smoke/training-result.json').read_text())
    costs=dict(smoke=smoke,main=main,evaluation={s:json.loads((run/s/'complete.json').read_text()) for s in STATES})
    reload=json.loads((run/'smoke/reload-audit.json').read_text())
    costs['smoke_generation']=dict(calls=2,output_tokens=sum(reload[k]['output_tokens'] for k in ['generation_before','generation_after']),
                                  wall_s=sum(reload[k]['wall_s'] for k in ['generation_before','generation_after']))
    costs['total_gpu_experiment_process_wall_s']=execution['process_wall_s']
    costs['main_peak_memory_scope']='End-of-main CUDA counters cover the final checkpoint evaluation window, since evaluations reset peak counters; whole-training allocated/reserved peak was not independently retained.'
    current_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    current_branch=subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip()
    if current_head!=frozen['head'] or current_branch!=frozen['config']['required_branch']:
        raise ValueError('HEAD or branch changed during experiment')
    validation=dict(passed=True,manifest_sha256=sha256(run/'manifest.json'),actual_counts=actual,
        all_400_responses_reviewed=True,reviewed_targets=len(reviews),
        primary_targets_per_state=80,sources_per_state=20,
        prior_uncommitted_files_preserved=len(original['files']),head_unchanged=current_head==original['head'],
        selection_before_test=next(i for i,e in enumerate(events) if e.get('type')=='selection_persisted') <
                              next(i for i,e in enumerate(events) if e.get('type')=='generation_reserved' and e['key'].startswith('base-test/')),
        no_public_inference=True,no_commit_or_push=True,
        quality_review='Codex agent review, not independent human or official grader')
    if actual['main_optimizer_steps']!=160 or actual['teacher_forced_evaluation_forwards']!=400 or actual['training_forwards']!=656:
        raise ValueError('actual forward/step counts mismatch')
    write_json(run/'quality-summary.json',semantic);write_json(run/'metrics-summary.json',counts)
    write_json(run/'paired-examples.json',comparison);write_json(run/'cost-summary.json',costs)
    (run/'invalid-responses.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in invalid),encoding='utf-8')
    write_json(run/'final-validation.json',validation)
    lines=['# Thí nghiệm Task 3 SFT v1 QLoRA — 26/10/2026','',
        'Đã thực thi baseline-dev, smoke GPU và một epoch QLoRA. Main hoàn tất **160/160 bước optimizer** trên 640 target/160 source. Không commit, push hoặc nộp predictions.',
        '',f"Checkpoint chọn: **step {execution['selection']['step']}**, theo minimum fixed-dev equal-example completion loss; hòa tuyệt đối chọn bước sớm hơn. Quyết định lưu trước test. Đây không phải quyết định thay A/R15.",
        '', '| State | Loss | JSON hợp lệ | Taxonomy micro P/R/F1 | False alarms clean target; source |',
        '|---|---:|---:|---|---|']
    for s in STATES:
        a=counts[s];t=a['taxonomy'];f=a['clean_false_alarms']['targets']
        fs=a['clean_false_alarms']['sources']
        lines.append(f"| {s} | {fmt(a['loss'])} | {a['valid']}/80 | {fmt(t['precision'])}/{fmt(t['recall'])}/{fmt(t['f1'])} | {f['false_alarms']}/{f['denominator']}; {fs['false_alarms']}/{fs['denominator']} |")
    lines += ['', 'Mỗi state gồm **80 target / 20 source**, mỗi Level20 target. Taxonomy F1 là metric chẩn đoán, không phải điểm Task3 chính thức. Invalid giữ trong mẫu số; faulty invalid tính FN của nhãn gold, clean invalid vẫn là failure riêng, không thành clean prediction. Bảng per-Level đầy đủ trong metrics-summary.json.',
        '', '## Review chất lượng', '',
        'Review do Codex agents đối chiếu source/spec và từng phản hồi, không phải người chấm độc lập hay grader chính thức. Không dùng keyword hoặc exact wording để chấm semantic.', '',
        '| State | Chẩn đoán pass/fail/?/NE | Level pass/fail/?/NE | Tiếng Việt pass | L3 repair pass/fail/N/A/NE | L4 solution pass/fail/?/NE |',
        '|---|---|---|---:|---|---|']
    def tally(state,dim,keys,level=None):
        source=semantic[state]['dimensions'] if level is None else semantic[state]['by_level'][str(level)]
        return '/'.join(str(source[dim].get(k,0)) for k in keys)
    for s in STATES:
        lines.append(f"| {s} | {tally(s,'diagnosis_supported',['pass','fail','uncertain','not_evaluable'])} | {tally(s,'level_compliance',['pass','fail','uncertain','not_evaluable'])} | {semantic[s]['dimensions']['vietnamese_compliance'].get('pass',0)}/80 | {tally(s,'l3_repair_direction',['pass','fail','not_applicable','not_evaluable'],3)} | {tally(s,'l4_solution_quality',['pass','fail','uncertain','not_evaluable'],4)} |")
    lines += ['', 'Tổng hợp mọi verdict, kể cả not_applicable/not_evaluable, theo Level và state ở quality-summary.json. L3/L4 chỉ có20 target mỗi state; các verdict ở Level khác không thuộc mẫu số chuyên biệt.',
        '', '## Chi phí thực đo', '',f"Toàn tiến trình GPU: {execution['process_wall_s']:.2f} giây (bao gồm load, train, eval, save/reload và I/O). Counts: `{json.dumps(actual,ensure_ascii=False)}`.", '',
        '| Phần | Thời gian giây | Peak allocated / reserved GiB |','|---|---:|---|']
    for label,a in [('smoke training',smoke),('main training time; memory = last checkpoint eval window',main)]:
        wall=a.get('training_wall_excluding_checkpoint_evaluation_s',a['wall_s'])
        lines.append(f"| {label} | {wall:.2f} | {a['peak_allocated_bytes']/2**30:.2f} / {a['peak_reserved_bytes']/2**30:.2f} |")
    for s in STATES:
        a=costs['evaluation'][s]
        lines.append(f"| {s}: teacher-forced / generation | {a['teacher_forced']['wall_s']:.2f} / {a['generation']['wall_s']:.2f} | {a['peak_allocated_bytes']/2**30:.2f} / {a['peak_reserved_bytes']/2**30:.2f} |")
    lines += ['',f"Smoke generation riêng: {costs['smoke_generation']['calls']} calls, {costs['smoke_generation']['output_tokens']} output token, {costs['smoke_generation']['wall_s']:.3f} giây. Chi phí token/thời gian từng state và từng Level nằm trong metrics-summary.json/cost-summary.json; thời gian reload-logit riêng chưa tách khỏi toàn tiến trình."]
    lines += ['', 'Đây là NF4 base double quantization, BF16 compute; không phải mọi weights lưu BF16. Loss trung bình assistant CE trong từng hàng rồi trung bình đều giữa hàng, weight1; L4 có68,42% token completion train, không suy ra68,42% loss share.',
        '', '**Giới hạn đo VRAM:** eval reset bộ đếm peak CUDA, nên peak ghi trong main/training-result.json chỉ phản ánh cửa sổ checkpoint eval cuối; chưa giữ riêng peak allocated/reserved bao trùm toàn bộ main training. Các peak smoke và từng eval có phạm vi đo rõ. Không dùng giá trị main đó như peak toàn trajectory.',
        '', '## Tái lập và resume', '', 'Chạy từ worktree, giữ nguyên dependency/snapshot/cache đã pin:', '', '```bash',
        '/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_experiment.py \\',
        '  --out outputs/task3/sft-v1-qlora-REPRO-NEW', '```','',
        'Mỗi thí nghiệm mới tạo thư mục mới. Lệnh sau chỉ dành cho tiếp tục run bị ngắt, không dùng để chạy lại run đã xong:', '', '```bash',
        '/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_experiment.py \\',
        '  --out '+str(run.relative_to(REPO))+' --resume', '```','',
        'Resume bỏ qua generation đã lưu, không retry semantic; reservation mất output thành missing/uncertain. Chỉ tiếp tục native checkpoint có optimizer/scheduler/RNG khi journal không có optimizer progress vượt checkpoint; ngắt giữa step bị từ chối để tránh replay ngầm. Smoke bị ngắt cần chẩn đoán riêng, không tự mở lại trajectory.',
        '', '## Artifacts và giới hạn', '',
        'manifest.json giữ code/data/tokenizer hashes, HEAD/status, versions, recipe, generation/parser/rubric/budgets/smoke IDs. actual-training-arguments.json, peft-config.json và model-audit.json ghi cấu hình thực. Checkpoint80/160 có adapter/optimizer/scheduler/RNG/trainer state và hash; journal/training-log lưu bước/loss/LR/gradient. Smoke có real minibatch và save/reload logits audit. dev-paired.html/test-paired.html chứa đầy đủ source, gold, raw/parsed và trạng thái trước/sau.',
        '', '200 source thuộc50 đặc tả synthetic; dev/test cùng trợ lý biên soạn, không phải gold độc lập của BTC. Loss thấp hơn không chứng minh public accuracy hoặc đủ cơ sở thay A/R15. Không public inference/leaderboard mới; 0.3834 chỉ là số lịch sử người dùng báo.',
        '', '## Ví dụ trước/sau và quyết định sử dụng', '',
        '- Cải thiện dev F23-D2-L4: base bỏ sót lỗi palindrome; step160 nhận ra trạng thái ok bị đặt lại true sau một cặp ký tự khớp và đưa chương trình đầy đủ giữ trạng thái lỗi. Code vượt bộ test authored hữu hạn.',
        '- Cải thiện test F45-D1-L2: adapter nêu đúng thiếu cạnh ngược của đồ thị vô hướng. F45-D3-L4 có code BFS đúng với d[v]=d[u]+1, dù phần giải thích vẫn quy sai nguyên nhân xử lý đỉnh không tới được.',
        '- Hồi quy test F41-D3-L3: base chỉ đúng lỗi giây và hướng t%60; adapter chuyển sang đổ lỗi công thức phút vốn đúng, hướng sửa sai.',
        '- False alarm clean F45-C-L1/L2/L3: base chấp nhận chương trình BFS đúng; adapter gắn lỗi và ở L3 đòi cập nhật lại đỉnh đã thăm, không phù hợp BFS đồ thị không trọng số.',
        '- Level leakage base-dev F23-D3-L2: đưa replacement bound/cách sửa ở Level2. Việc mất thông tin ở adapter không được tính là cải thiện chẩn đoán chỉ vì hết lộ cách sửa.',
        '- Invalid selected-test F46-D2-L4: JSON lỗi escape dấu nháy trong cout; giữ nguyên raw và tất cả axes not_evaluable, không repair.',
        '', 'Giữ baseline A/R15 hiện dùng. Loss giảm và taxonomy F1 tăng không đủ để thay baseline: false alarms clean và chất lượng L2/L3 còn yếu; code L4 đúng có thể đi kèm giải thích sai. Nếu làm thí nghiệm tiếp theo, cần mục tiêu cụ thể giảm false alarms và giữ chẩn đoán/hướng sửa đúng; không tự mở thêm grid search trong lượt này.',
        '', 'Tất cả ví dụ có raw text và evidence trong paired-examples.json; mọi output kể cả invalid nằm trong casebooks và invalid-responses.jsonl. Đây là review agent có thể sai; bộ authored test hữu hạn, dev/test synthetic cùng tác giả, không phải chứng nhận tổng quát hóa hay điểm chính thức.']
    combined={};compile_calls=runtime_calls=0
    for state in STATES:
        counter=Counter()
        for path in sorted((run/'l4-audit'/state).glob('*/result.json')):
            row=json.loads(path.read_text())
            bare=run/'l4-unfenced-audit'/state/path.parent.name/'result.json'
            if row['status']=='not_extractable' and bare.exists():row=json.loads(bare.read_text())
            counter[row['status']]+=1
            if row.get('compile'):
                compile_calls+=1
                runtime_calls+=sum(t.get('executed',False) for t in row.get('tests',[]))
        if sum(counter.values())!=20:raise ValueError('incomplete L4 audit')
        combined[state]=dict(counter)
    write_json(run/'l4-combined-summary.json',dict(states=combined,compile_calls=compile_calls,runtime_calls=runtime_calls,
        claim='Finite authored C++11 tests; separate frozen fenced/unfenced policies, not primary metric or correctness proof'))
    lines+=['','## Kiểm C++ bổ sung cho L4','','| State | Qua bộ test | Sai test | Compile lỗi | Chưa trích được code | Invalid |',
            '|---|---:|---:|---:|---:|---:|']
    for state,c in combined.items():
        lines.append(f"| {state} | {c.get('all_authored_tests_passed',0)} | {c.get('authored_test_failure',0)} | {c.get('compile_error',0)} | {c.get('not_extractable',0)} | {c.get('not_evaluable',0)} |")
    lines+=['',f'Thực chạy {compile_calls} compiler calls và {runtime_calls} authored runtime tests. Mỗi hàng20 target L4. Phần unfenced bổ sung sau khi quan sát format code trần; policy/hash riêng, không thay metric primary. Không sửa code/retry. Qua test hữu hạn không chứng minh lời giải tổng quát hoặc giải thích đúng.',
        '', '132 test liên quan passed;3 optional jail probes skipped. Audit thực đã chạy sandbox C++. Giữ nguyên22 file chưa commit trước thí nghiệm, HEAD/branch và dataset.',
        '', 'Tái tạo audit và báo cáo từ các outputs đã có, không gọi Qwen:', '', '```bash',
        '/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_l4_audit.py --run '+str(run.relative_to(REPO)),
        '/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_l4_unfenced_audit.py --run '+str(run.relative_to(REPO)),
        '/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_report.py --run '+str(run.relative_to(REPO)),
        '```', '', 'Hai audit giữ nguyên kết quả đã lưu, chỉ bổ sung target chưa xử lý. Review semantic là artifact agent đã lưu, không tự tái sinh bằng keyword.']
    (run/'REPORT.vi.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(validation,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    report(p.parse_args().run.resolve())
