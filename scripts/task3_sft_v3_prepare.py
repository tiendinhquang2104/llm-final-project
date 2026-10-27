"""Freeze a train-only target revision and reviewed oracle; never invoke Qwen."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.sft_v1 import sha256,read_jsonl,native_prompt,INPUT_KEYS
from src.task3.sft_v1_experiment import write_json
from src.task3.sft_v3 import REVIEW_POLICY,SELECTION_POLICY,ORACLE_WRAPPER

SYSTEM_PROMPT='''Bạn đánh giá bài lập trình C++ theo đầy đủ yêu cầu đề, mã nguồn và chẩn đoán cú pháp được cung cấp. Tự xác định lỗi có bằng chứng; không bịa lỗi cho bài đúng. Nhãn taxonomy và phản hồi phải nhất quán, không thay nhãn chỉ vì đổi Level. Viết tiếng Việt, chỉ trả đúng một đối tượng JSON {"taxonomy_error": [...], "feedback": "..."}, không có trường khác hay văn bản ngoài JSON.
Tuân thủ mức phản hồi yêu cầu:
Level 1: Chỉ báo có vấn đề / khen ngợi, không chỉ ra vị trí lỗi; không nêu nguyên nhân cụ thể, không đưa code sửa.
Level 2: Chỉ ra lỗi ở đâu và nguyên nhân là gì; không đưa cách sửa cụ thể, không đưa code. Chẩn đoán cần chính xác, không giới hạn số câu.
Level 3: Chẩn đoán và gợi ý hướng sửa hữu ích, đúng với nguyên nhân; không đưa lời giải hoàn chỉnh.
Level 4: Được phép đưa code sửa / lời giải mẫu; nội dung giải thích và code nếu có phải đúng, hữu ích.
Giữ các điều kiện gây lỗi thiết yếu; không nhầm một lựa chọn triển khai hợp lệ với lỗi. Với bài đúng, nhận xét đúng thực tế, không đòi sửa lỗi không tồn tại.'''+'\n'


def jsonl(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows))


def records(path):
    obj=json.loads(path.read_text())
    return obj if isinstance(obj,list) else obj.get('records',obj.get('reviews'))


def load_examples(root,split):
    """Render only the requested partition; IDs/findings never enter E2E input."""
    labels=json.loads((root/'label_space.json').read_text())['taxonomy_error']
    parts=json.loads((root/'split-manifest.json').read_text())['partitions']
    owners={}
    for partition,items in parts.items():
        for item in items:
            for kind in ('source_id','family_id','cluster'):
                key=(kind,item[kind])
                if key in owners and owners[key]!=partition:raise ValueError('cross-split ownership')
                owners[key]=partition
    manifest={r['source_id']:r for r in parts[split]}
    rows=read_jsonl(root/f'{split}.records.jsonl');result=[];coverage={}
    for row in rows:
        sid=row['source_id'];x=row['input'];level=x['target_feedback_level']
        if set(x)!=INPUT_KEYS or sid not in manifest or row['split']!=split:raise ValueError('input boundary')
        source=root/'sources'/f'{sid}.cpp'
        if sha256(source)!=manifest[sid]['source_sha256'] or source.read_text()!=x['code']:raise ValueError('source binding')
        if x['language']!='cpp11' or type(level)is not int or level not in (1,2,3,4):raise ValueError('Level/language')
        result.append(dict(example_id=row['sample_id'],sample_id=sid,level=level,
            prompt=native_prompt(root,x,labels),completion=json.dumps(row['output'],ensure_ascii=False),loss_weight=1.))
        coverage.setdefault(sid,[]).append(level)
    if set(coverage)!=set(manifest) or any(sorted(v)!=[1,2,3,4] for v in coverage.values()):raise ValueError('four-Level coverage')
    if len({r['example_id'] for r in result})!=len(result):raise ValueError('duplicate target')
    return result


def prepare(repo,out):
    root=repo/'data/raw/task3-sft-v3';old=repo/'data/raw/task3-sft-v2'
    if root.exists():raise FileExistsError('v3 dataset already exists')
    audits=[]
    for name in ['train-a.private.json','train-b.private.json','train-c.private.json']:
        audits+=records(out/'audit'/name)
    original=read_jsonl(old/'train.records.jsonl');by_source={}
    for row in original:by_source.setdefault(row['source_id'],{})[str(row['input']['target_feedback_level'])]=row['output']
    if len(audits)!=240 or {r['source_id'] for r in audits}!=set(by_source):raise ValueError('audit does not cover all 240 train sources')
    reviewed={r['source_id']:r for r in audits};quarantined=[];changes=[]
    for sid,r in reviewed.items():
        if r.get('quarantine') or r.get('quarantined'):
            if not r.get('quarantine_reason'):raise ValueError('quarantine needs explicit reason')
            quarantined.append(sid);continue
        if sha256(old/'sources'/f'{sid}.cpp')!=r['source_sha256']:raise ValueError('audit source hash')
        if sorted(r['reviewed_levels'])!=[1,2,3,4]:raise ValueError('all four targets must be reviewed')
        targets=r['revised_targets'];taxa=[]
        for level in ('1','2','3','4'):
            target=targets[level]
            if set(target)!={'taxonomy_error','feedback'}:raise ValueError('target schema')
            taxa.append(target['taxonomy_error'])
            if target!=by_source[sid][level]:
                reason=next((c['reason'] for c in r['changes'] if str(c['level'])==level),None)
                if not reason:raise ValueError('exact change reason missing')
                changes.append(dict(source_id=sid,level=int(level),original=by_source[sid][level],revised=target,reason=reason))
        if any(t!=taxa[0] for t in taxa) or bool(taxa[0])!=r['faulty']:raise ValueError('clean/faulty/Level consistency')
    root.mkdir();shutil.copytree(old/'sources',root/'sources')
    for name in ('label_space.json','split-manifest.json','cases.private.json','dev.records.jsonl','test.records.jsonl','final.records.jsonl'):
        shutil.copyfile(old/name,root/name)
    # Evaluation targets are copied byte-for-byte. Final content is not read before selection.
    for split in ('test','final'):shutil.copyfile(old/f'{split}.sft.jsonl',root/f'{split}.historical.sft.jsonl')
    (root/'SYSTEM_PROMPT.txt').write_text(SYSTEM_PROMPT)
    parts=json.loads((root/'split-manifest.json').read_text())
    if quarantined:
        parts['partitions']['train']=[r for r in parts['partitions']['train'] if r['source_id'] not in quarantined]
        write_json(root/'split-manifest.json',parts)
    updated=[]
    for row in original:
        sid=row['source_id']
        if sid in quarantined:continue
        level=str(row['input']['target_feedback_level']);row['output']=reviewed[sid]['revised_targets'][level];updated.append(row)
    jsonl(root/'train.records.jsonl',updated)
    for split in ('train','dev'):
        examples=load_examples(root,split)
        jsonl(root/f'{split}.sft.jsonl',[dict(prompt=e['prompt'],completion=[dict(role='assistant',content=e['completion'])]) for e in examples])
    oracle=records(out/'audit/dev-oracle.private.json')
    dev_ids={r['source_id'] for r in read_jsonl(old/'dev.records.jsonl')}
    if len(oracle)!=20 or {r['source_id'] for r in oracle}!=dev_ids:raise ValueError('reviewed oracle requires exactly 20 dev sources')
    for r in oracle:
        if sha256(old/'sources'/f"{r['source_id']}.cpp")!=r['source_sha256']:raise ValueError('oracle source binding')
        if any(k in r for k in ('targets','revised_targets','solution_code')):raise ValueError('oracle answer leakage')
    write_json(root/'canonical-train.private.json',dict(review_type='source-grounded agent review; not independent human gold',records=audits))
    write_json(root/'oracle-dev.private.json',dict(review_type='source-grounded agent review; frozen before predictions; no independent human gold',records=oracle))
    write_json(root/'target-changes.private.json',dict(version='v3.0',changes=changes,quarantined=quarantined,original_train_records_sha256=sha256(old/'train.records.jsonl')))
    write_json(root/'dataset-manifest.json',dict(version='task3-sft-v3.0',train_sources=len(updated)//4,train_targets=len(updated),
        train_clean_sources=sum(not r['faulty'] for r in audits if r['source_id'] not in quarantined),
        train_faulty_sources=sum(r['faulty'] for r in audits if r['source_id'] not in quarantined),target_changes=len(changes),quarantined_sources=quarantined,
        dev_targets=80,oracle_dev_targets=80,observed_final_targets=160,evaluation_independence='previously observed synthetic evaluation; not unseen or independent',
        source_spec_split_bytes='preserved; only quarantined train membership may be removed',train_optimizer_steps_per_epoch=len(updated)//4,main_optimizer_steps=len(updated)//2))
    files={str(p.relative_to(root)):sha256(p) for p in root.rglob('*') if p.is_file()}
    (root/'SHA256SUMS').write_text(''.join(f'{h}  {name}\n' for name,h in sorted(files.items())))
    official=Path('/workspace/llm-final-project/data/raw/public_test_release/label_space.json')
    labels=json.loads(official.read_text(encoding='utf-8-sig'))
    if labels!=json.loads((root/'label_space.json').read_text()):raise ValueError('official contract discrepancy')
    contract=dict(requirements_file='DoAn-LLM-Challenge.docx.md',requirements_sha256=sha256(repo/'DoAn-LLM-Challenge.docx.md'),
        authoritative_label_space=str(official),label_space_sha256=sha256(official),definitions=labels['feedback_level'],
        original_vs_release='Original Task3 input includes supplied taxonomy; public release requires taxonomy+feedback. This experiment production remains end-to-end, oracle evaluation only.',
        system_prompt_sha256=sha256(root/'SYSTEM_PROMPT.txt'),oracle_wrapper=ORACLE_WRAPPER,review_policy=REVIEW_POLICY,selection_policy=SELECTION_POLICY)
    write_json(out/'official-contract.json',contract);write_json(out/'review-policy.json',REVIEW_POLICY);write_json(out/'selection-policy.json',SELECTION_POLICY)
    (out/'ORACLE_WRAPPER.txt').write_text(ORACLE_WRAPPER);shutil.copyfile(root/'SYSTEM_PROMPT.txt',out/'SYSTEM_PROMPT.txt')
    definitions='\n'.join(f"- **{d['level']}**: “{d['định nghĩa']}” Cấm: “{d['cấm']}”" for d in labels['feedback_level'])
    spec=f'''# Task 3 SFT v3 — đặc tả đóng băng\n\nYêu cầu gốc: `DoAn-LLM-Challenge.docx.md`, SHA256 `{contract['requirements_sha256']}`.\nLabel chính thức: `{official}`, SHA256 `{contract['label_space_sha256']}`.\n\n{definitions}\n\nĐề gốc nhận nhãn cho sẵn; schema public yêu cầu taxonomy + feedback. Candidate ở đây tự chẩn đoán end-to-end; oracle là probe riêng chỉ trên dev.\nKhông giới hạn L2 một câu. L4 không bắt buộc code. Độ dài tăng theo Level là phong cách tùy chọn. Chẩn đoán L2 chính xác được phép dù người học suy ra cách sửa. Hướng sửa cục bộ có thể cụ thể ở L3; không đưa chương trình/lời giải hoàn chỉnh.\n\nDữ liệu train được audit toàn bộ bằng agent, không phải human gold độc lập. Giữ nguồn/spec/split và gold lịch sử; canonical private không vào dataloader. Dev20/80 để chọn; final40/160 đã quan sát chỉ mở nội dung sau selection.\n\nMột adapter mới, pinned Qwen revision c03e6d358207e414f1eca0bb1891e29f1db0e242, NF4 double quant/BF16, LoRA16/32/0.05, LR2e-5, AdamW weight_decay0, cosine, warmup0.03, clip1, batch1/accum4/seed42, context train8192, 2 epoch. Không packing/truncation, assistant-only termination loss và equal-example mean. Smoke16 targets/4 steps/2 generation tối đa, bỏ toàn bộ cập nhật smoke. Lưu ở cuối mỗi epoch. Evaluation context32768, greedy một lần, L1–3 tối đa1024 token, L4 tối đa1536, max_time45s.\n\n640 dev generation = 4 states × (80 end-to-end + 80 oracle). Sau selection khóa, 480 observed-final end-to-end = 3 states ×160. Không semantic retry/verifier/public inference.\n\nCác trục: disclosure chính thức; chẩn đoán/coverage; fidelity/điều kiện; hướng sửa L3; hữu ích L4; code đúng; tiếng Việt/schema. Hướng sửa sai không tự động tính thành disclosure sai. Clean không cần lỗi/hướng sửa hư cấu. Faulty khen chung không hoàn thành nhiệm vụ. Code có cung cấp mà sai làm joint fail.\n\nEligibility so với v2 cùng prompt: invalid, clean false alarm, faulty miss cộng faulty invalid không tăng; supported faulty diagnosis và L3 correct không giảm. Trong ứng viên đạt: Level, balanced joint, oracle fidelity+Level joint, dev loss, checkpoint sớm. Không ai đạt: balanced joint, supported faulty diagnosis, Level, sớm; ghi fail promotion rồi vẫn đánh giá final. Mục tiêu95% chỉ mô tả.\n\nCùng thay target và prompt nên không tách được tác động nhân quả. Oracle đổi nhiệm vụ nên chênh lệch oracle/end-to-end không phải phân rã nhân quả thuần túy. Điểm lịch sử user báo A0.3834, v2 0.3567, B0.3247 không phải số đo mới. Không suy điểm public từ synthetic.\n'''
    (repo/'docs/task3_sft_v3_experiment.md').write_text(spec)
    print(json.dumps(json.loads((root/'dataset-manifest.json').read_text()),ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();prepare(REPO,a.out.resolve())
