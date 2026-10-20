# Task 3 — bàn giao submission R15 zero-shot, 20/10/2026

**File để tự upload:** `/workspace/llm-final-project/outputs/task3/submission-r15-20261020/predictions.json`.

SHA-256: `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`.

**328/328 records; validator CLI chạy lại trả `VALID`, exit 0.** Đây là bản sao nguyên byte của `outputs/task3/round15/public-candidate-zero/predictions.json` đã sinh trước đây, không phải một lượt inference mới. Dùng đúng R15 zero-shot, không dùng R14 dự phòng vì R15 hợp lệ. Không fine-tune, đổi prompt, sửa feedback theo từng bài, push hoặc nộp leaderboard. Predictions và toàn bộ raw public vẫn ignored; chỉ báo cáo/metadata được commit.

## Phương pháp và provenance

Generation code commit: `f6a17b13a3954755dd55809d9082784e36391546`; run manifest ghi worktree sạch khi sinh. Model `Qwen/Qwen2.5-Coder-7B-Instruct`, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`. Runtime đã lưu xác nhận NF4 trên CUDA, quantized compute BF16; tokenizer `Qwen2TokenizerFast`, không mock, cùng revision. Không tải model trong lần bàn giao này.

Config cố định `configs/task3/r15_zero_shot.yaml` kế thừa `r15_common.yaml`: seed42, greedy, context16384, max_new_tokens1024 (L4 cap1536), tối đa3 attempts, soft max_time45s, few_shot_k0. Prompt policy `round15-short-direct-v1`; completion policy `preserve_qwen_content_with_schema_and_explicit_l1_l2_only`. Giữ nguyên cả cơ chế retry và fallback R15 đã có, không thêm guard.

Đối chiếu config, toàn bộ17 implementation hashes và bank hash với run manifest và freeze trước public đều khớp. Freeze `outputs/task3/round15/selected-prompt-freeze.json`, SHA-256 `031c546bb5a83236725a158176585183c78799f7a8c4adc502d197cb3c858795`, ghi `public_used_for_prompt_selection=false`. Zero-shot không chèn ví dụ vào query: cả361 attempts ghi `examples_used=0`.

Cả328 first prompts khớp public release hiện có và diagnostic gốc đã lưu; tái tính full runner input identity cũng khớp checkpoint, không gọi compiler/model. Đối chiếu17 implementation blobs tại generation commit cũng khớp hash. Audit offline đã kiểm tra prompt/attempt identity, thứ tự và giới hạn attempts, phát lại quyết định schema/disclosure trên raw đã lưu, đối chiếu tất cả328 final với checkpoint và traces. Có304 final từ first model attempt,15 từ model retry,9 từ fallback có sẵn. Final fallback được tái dựng đúng bằng taxonomy của latest schema-valid attempt và câu fallback cố định của runner. Không có unresolved ID. Raw và mọi retry/reason vẫn ở `outputs/task3/round15/public-candidate-zero/{attempts.jsonl,decisions.jsonl,progress.json,traces.json}`.

## ZIP mới: xác nhận bằng bytes, không dùng cho submission này

Tìm thấy ZIP người dùng gọi `generate-dataset_v2(1).zip` trên Docker dưới tên `/workspace/llm-final-project/generate-dataset_v2.zip`.

| Artifact | SHA-256 |
|---|---|
| ZIP mới | `6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b` |
| Member `generate-dataset/task3_feedback.json` | `38da5e36636ba74315b3e0d6e8e25e7240595b7cb2dcf33ef00dcc21542f9a32` |
| Member `generate-dataset/label_space.json` | `056a4d1a0ccfd60688b43efdf5df64a4c1310e3c6f1d99ab813691a2da27a9dc` |

Root metadata có627 records/627 ID duy nhất, so với612 được ghi trong audit phiên bản trước;27 records có positive “Lỗi thuật toán”. Label space vẫn đúng10 nhóm chính thức. Chỉ đọc metadata trực tiếp trong ZIP, không giải nén đè, preprocess, huấn luyện hoặc chỉnh prompt. Không tuyên bố candidate R15 đã dùng annotation mới.

Cùng đường dẫn ZIP từng trỏ tới bytes khác trong R16/R17 (hash `3581498f3db9b55e8bef911609b7829d1928805e66d2956d36a2084b3ca190d0`). Giữ nguyên provenance lịch sử đó; tên file không xác định phiên bản.

## Hợp đồng submission và kết quả validator

Đã đọc trực tiếp `data/raw/public_test_release/task3_feedback.json` và `label_space.json`: đủ328 unique ID, requested Levels115/163/50/0. Mỗi prediction có đúng `sample_id` và `output`; output có đúng `taxonomy_error` và `feedback`, nhãn chỉ trong10 nhóm chính thức, không lặp nhãn. Thứ tự và tập ID khớp public release.

Public release không có `task3_requested_levels.json` tại thư mục raw. Bản bàn giao có map ignored cùng tên, tạo **chỉ từ `sample_id` và `input.target_feedback_level`**, không đưa source vào map, ví dụ hay training. Map khớp cả official map đã lưu và run manifest. Schema không có trường Level trong prediction; Level được xác định bằng ID và map chính thức.

Lệnh đã chạy từ `/workspace/llm-final-project`:

```bash
.venv-task3/bin/python scripts/validate_task3_submission.py \
  --predictions outputs/task3/submission-r15-20261020/predictions.json \
  --requested-levels outputs/task3/submission-r15-20261020/task3_requested_levels.json
```

```json
{"status":"VALID","records":328,"levels":{"Level 1 - Gợi ý nhẹ":115,"Level 2 - Chẩn đoán":163,"Level 3 - Gợi ý sửa":50,"Level 4 - Lời giải mẫu":0}}
```

Log thật: `outputs/task3/submission-r15-20261020/validator-cli.log`. Validator kiểm tra ID/schema/nhãn/nonempty feedback và hợp đồng map Level. **Validator không chứng minh nhận định đúng source, tiếng Việt thuần hoặc tuân thủ Level về ngữ nghĩa.** Không có gold public để tính F1.

## Thống kê offline, không dùng để sửa prompt

| Chỉ số | Giá trị |
|---|---:|
| Feedback rỗng / ID unresolved | 0 / 0 |
| Placeholder nguyên câu / TEST-ONLY / ARTIFACT-FIXTURE marker | 0 |
| Tổng label assignments / taxonomy `[]` | 208 / 120 |
| Độ dài feedback, ký tự min / median / mean / max | 28 / 134 / 145,027 / 662 |
| Raw attempts đã có / schema-failed attempts | 361 / 1 |
| Fallback R15 có sẵn | 9 (L1:3, L2:6) |
| First raw bị screen disclosure L1 / L2 | 4/115 / 19/163 |
| Final bị cùng screen L1 / L2 | 0/115 / 0/163 |
| Feedback chứa ký tự CJK | 5 (đều L3) |

| Nhãn chính thức | Số prediction có nhãn |
|---|---:|
| Lỗi biên dịch | 86 |
| Lỗi nhập/xuất | 32 |
| Lỗi logic | 86 |
| Lỗi vòng lặp | 0 |
| Lỗi mảng/chuỗi | 0 |
| Lỗi hàm | 4 |
| Lỗi edge case | 0 |
| Lỗi thuật toán | 0 |
| Lỗi hard-code | 0 |
| Lỗi style | 0 |

Không gọi9 fallback là feedback chẩn đoán hữu ích hoặc toàn bộ328 final là model output nguyên văn. Chúng là hành vi cố định của R15, không phải placeholder mới được tạo để lấp ID. Không thấy feedback nguyên câu dạng `...`, TODO/TBD/placeholder/dummy/mock/test/fixture hoặc marker TEST-ONLY/ARTIFACT-FIXTURE trong audit; điều này không chứng minh chất lượng nội dung.

Năm feedback có ký tự CJK là hạn chế ngôn ngữ còn tồn tại; không cam kết toàn bộ feedback thuần tiếng Việt. Screen disclosure cũ chỉ áp dụng L1/L2 và dựa pattern, không đánh giá L3/L4, cũng không chứng minh đủ chẩn đoán/hướng sửa. Giữ nguyên output theo phương pháp R15 cố định; không dùng quan sát public này để chọn prompt, sửa từng response hoặc chạy thêm inference. R14 không được chọn thay thế dựa trên các thống kê public.

## Tái hiện bàn giao offline

Đoạn sau tạo lại bản sao và map từ hai trường được phép; không gọi model. Nếu đã có file bàn giao, yêu cầu hash khớp trước khi tiếp tục.

```bash
.venv-task3/bin/python - <<'PY'
import hashlib, json, shutil
from pathlib import Path
src = Path('outputs/task3/round15/public-candidate-zero/predictions.json')
out = Path('outputs/task3/submission-r15-20261020')
out.mkdir(mode=0o700, parents=True, exist_ok=True)
expected = '9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45'
assert hashlib.sha256(src.read_bytes()).hexdigest() == expected
release = json.loads(Path('data/raw/public_test_release/task3_feedback.json').read_text())
levels = {r['sample_id']: r['input']['target_feedback_level'] for r in release['samples']}
assert len(levels) == len(release['samples']) == 328
assert list(levels) == [r['sample_id'] for r in json.loads(src.read_text())]
dst = out/'predictions.json'
if dst.exists():
    assert hashlib.sha256(dst.read_bytes()).hexdigest() == expected
else:
    shutil.copyfile(src, dst)
dst.chmod(0o600)
p = out/'task3_requested_levels.json'
p.write_text(json.dumps(levels, ensure_ascii=False, indent=2)+'\n')
p.chmod(0o600)
print(dst.resolve(), hashlib.sha256(dst.read_bytes()).hexdigest())
PY
.venv-task3/bin/python scripts/validate_task3_submission.py \
  --predictions outputs/task3/submission-r15-20261020/predictions.json \
  --requested-levels outputs/task3/submission-r15-20261020/task3_requested_levels.json
```

Lệnh inference R15 tương ứng dưới đây chỉ để tham chiếu provenance, **không chạy trong lần bàn giao**. Nó có thể load model/compile lại kể cả khi resume; dùng các lệnh offline phía trên để kiểm chứng file hiện có.

```bash
.venv-task3/bin/python scripts/task3_round15.py \
  --config configs/task3/r15_zero_shot.yaml --phase public \
  --output-dir outputs/task3/round15/public-candidate-zero \
  --freeze outputs/task3/round15/selected-prompt-freeze.json
```

[Metadata kiểm chứng](TASK3_R15_SUBMISSION_HANDOFF_20261020.json) ghi hash release, map, config/model, kết quả CLI và36 protected artifact hashes đối chiếu không đổi. Metadata không chứa source, rendered prompts hoặc raw/final feedback public. Không thay production code, nên kiểm chứng tập trung vào file nộp thật và provenance, không chạy lại inference hay toàn bộ test suite.
