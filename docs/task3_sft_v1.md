# Tích hợp Task 3 SFT v1 — 26/10/2026

Đây là bàn giao dataset và preflight trong worktree
`/workspace/llm-final-project-arm-d-plus`, branch `fix/task3-strict-feedback`.
Chưa train, chưa gọi Qwen, chưa sinh predictions và chưa có điểm cải thiện mới.
Contract gốc: [task3_sft_v1_handoff.txt](task3_sft_v1_handoff.txt).

## Dữ liệu và tính toàn vẹn

Gói `/workspace/task3-sft-v1.zip` đã được giải nén nguyên trạng vào
`data/raw/task3-sft-v1/`, thuộc vùng dữ liệu được git ignore.

- ZIP SHA256: `7aa004a8f260d5510e20192cba757e17cc5523e756d984822a2deb15c84ad180`.
- SHA256SUMS SHA256: `8374da28569cd235112b928ff48a70ad5c69df2af6a30b9978c48825458be846`.
- Cả 255 tệp trong SHA256SUMS khớp. Đã đọc README, DATA_CARD, label_space, split manifest và final audit.
- `audit_exports.py` và `verify_dataset.py --offline` đạt. Hai script này ghi lại report trong gói, vì vậy được chạy trên bản sao tạm; kết quả mới lưu riêng, gói gốc không bị sửa.
- Offline xác nhận liên kết với bằng chứng đã có: 65 clean pass, 135 faults witnessed, 1.465 runtime tests. Lượt tích hợp thực hiện **0 syntax compile, 0 link, 0 runtime test mới**.

| Split | Họ bài | Source | Target | Vai trò |
|---|---:|---:|---:|---|
| train | 40 | 160 | 640 | Học mặc định từ train.sft.jsonl |
| dev | 5 | 20 | 80 | Chọn checkpoint |
| test | 5 | 20 | 80 | Đánh giá sau khi đã chọn checkpoint |

Mỗi source có đủ L1–L4. Family, cluster, source và source bỏ whitespace
không đi qua nhiều split. Các file messages là biểu diễn thay thế, không phải
dữ liệu thêm. File `train.l123.sft.jsonl` gồm 480 target của cùng source train,
chỉ dùng thay thế cho ablation riêng. 60 source pilot đã nằm trong train;
không nối mini/pilot cũ vào lần nữa.

## Điểm tích hợp vào repo

- [sft_v1.yaml](../configs/task3/sft_v1.yaml): checksum, model/revision, đường dẫn và recipe dự kiến một epoch, không grid search.
- [sft_v1.py](../src/task3/sft_v1.py): loader mặc định chỉ train, đối chiếu renderer whitelist nguyên bản, kiểm grouping, encode bằng `encode_completion` hiện có, factory Trainer dùng `WeightedCompletionCollator` và `weighted_completion_loss` của repo.
- [task3_sft_v1_prepare.py](../scripts/task3_sft_v1_prepare.py): chạy audit offline, tokenizer, encode từng split và kiểm tensor qua Trainer dataloader; không có lệnh train hay load weights.
- [test_task3_sft_v1.py](../tests/test_task3_sft_v1.py): test chống trộn dữ liệu, lộ metadata, sai schema, tràn context, mất JSON/kết thúc assistant, sai padding/loss và loại bỏ cột collator.

Loader chỉ đưa prompt system/user đã đối chiếu nguyên văn vào model input.
ID, split, family/group và trường Level phụ dùng thống kê nằm ngoài input tensor;
requested Level vẫn có trong user prompt theo thiết kế. Collator giữ example ID
riêng để audit, không serialize thành prompt. Không đưa cases
private, seed, findings, test input/expected, reviewer verdict hay solution ID
vào prompt. Compiler view trong prompt giữ syntax-only; không thêm link log,
runtime hay witness. Dev/test không tham gia train dataloader.

Output giữ đúng hai khóa `taxonomy_error`, `feedback`; feedback tiếng Việt.
L1 chỉ trạng thái; L2 một câu ngắn nêu vị trí và nguyên nhân, không code/cách sửa;
L3 có hướng sửa, chưa có lời giải đầy đủ; L4 có code đã được kiểm trong gói.
Câu L2 **“Hàm add_match đếm phần tử không chia hết, trái yêu cầu đề.”** được giữ
nguyên, không dùng bộ lọc từ khóa để làm mơ hồ chẩn đoán. Độ dài tăng
L1 < L2 < L3 < L4 là quy tắc dữ liệu của người dùng, không phải metric chính thức.

## Chạy lại preflight

Từ worktree hiện tại, dùng môi trường đã có:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v1_prepare.py \
  --config configs/task3/sft_v1.yaml \
  --out outputs/task3/task3-sft-v1-preflight-NEW
```

Chọn tên thư mục mới mỗi lần; lệnh từ chối ghi đè output hiện có. Có thể chỉ
định `--tokenizer` là thư mục snapshot local mang đúng revision đã pin.
Lệnh gọi nguyên script `scripts/preflight_tokenizer.py` của gói với
`--revision`, `--max-length 8192`, `--out <run>/tokenizer-audit.json`.
Không tải tokenizer hoặc weights qua mạng.

Revision `c03e6d358207e414f1eca0bb1891e29f1db0e242` và context train 8192 đã đối
chiếu với `configs/task3/r15_abc_20261025.yaml`. Context inference 16384 của
config lịch sử không được dùng thay cho context train. Output lưu actual config,
hash code/tokenizer/chat template, phiên bản Python/dependency, số token,
ba file encoded riêng biệt, tensor minibatch và checksum artifact.

Khi được giao chạy train, caller dùng `load_split(root)` cho train,
`load_split(root, 'dev')` cho dev, rồi `encode_examples` với tokenizer đã pin.
Gọi `make_trainer(model, args, train_rows, dev_rows, tokenizer.pad_token_id)`
với `remove_unused_columns=False`. Factory không nhận test_rows.
Các trường recipe trong YAML là cấu hình dự kiến, **chưa phải cấu hình của
một lượt train đã thực hiện**; cần chuyển và kiểm toàn bộ sang trainer thực tế.

## Kết quả preflight đã đo

Kết quả nằm ở
`outputs/task3/task3-sft-v1-integration-20261026/preflight-final/`:
`actual-config.json`, `tokenizer-audit.json`, `trainer-minibatch.private.json`,
`artifact-sha256.json` và logs. Audit ban đầu ở thư mục cha.

Tokenizer thật đọc đủ 800 target, prefix ổn định, không overflow và không
truncation. Mẫu dài nhất train/dev/test lần lượt 1.231 / 918 / 905 token,
đều trong context 8192. Không thêm BOS/EOS lần nữa sau chat template.

| Level | Hàng train | Token completion train | Tỷ lệ token completion train |
|---|---:|---:|---:|
| L1 | 160 | 3.623 | 6,28% |
| L2 | 160 | 4.983 | 8,63% |
| L3 | 160 | 9.620 | 16,67% |
| L4 | 160 | 39.482 | 68,42% |

Tổng completion train 57.708 token; dev 6.729; test 7.344. Số đo bao gồm phần
kết thúc assistant do chat template tạo ra. Cân bằng hàng không đồng nghĩa
cân bằng token hoặc đóng góp loss. Chính sách tích hợp: tính CE trung bình
trên token assistant trong từng hàng, sau đó trung bình đều giữa các hàng;
`loss_weight=1`. Không dùng token mean chung cho cả batch. Đây là lựa chọn
normalization cần giữ nguyên hoặc báo rõ nếu đổi khi train.

Đã kiểm cả 640 hàng qua dataloader của factory Trainer với batch size 1;
system/user và assistant header có label -100, toàn bộ JSON cùng kết thúc
assistant còn supervised. Kiểm bổ sung cùng collator với hai hàng dài/ngắn
tạo 744 token padding, tất cả padding có label -100.

**Phạm vi:** đây là Trainer CPU dùng placeholder cấm forward, chưa load Qwen
và chưa có optimizer. `actual_qwen_training_minibatch_checked=false` được ghi
rõ trong report. Script tokenizer gốc vẫn giữ
`actual_trainer_collator_checked=false` vì nó chỉ kiểm boundary; bằng chứng
collator bổ sung nằm trong `actual-config.json` và tensor sidecar. Khi train
thật, phải mở lại minibatch từ chính trainer/model đó trước optimizer.

Các test mới cùng test hồi quy encoder/loss/pilot/R15: **48 passed**.
Review không tìm thấy lỗi Critical/Important. Điểm Minor về config khai báo
file/policy khác hành vi thực tế đã được sửa bằng validation và năm test hồi quy.

## Protocol khi được giao train và đánh giá

Giữ prompt tiếng Anh của gói để train/inference. Đây là prompt mới, không
byte-identical A/R15. Base và adapter phải dùng cùng native renderer, prompt,
requested Level, parser, syntax-only compiler view và generation settings.
Nếu sau này chọn prompt A/R15, phải tái render toàn bộ dataset qua đúng renderer
đó và báo thay đổi. Giữ nguyên A/R15 lịch sử để đối chiếu riêng. Các số
A=0.3834, B=0.3247, strict=0.1547 là người dùng đã báo, không phải phép đo mới.

Trước train, freeze actual model/tokenizer revision, checksum/split/prompt,
dependency versions, adapter config, seed, optimizer, max sequence length,
precision, loss mask và sampling policy. Chạy một recipe có giới hạn, chọn
checkpoint theo dev cố định, giữ bản trước train. Không chọn theo leaderboard,
không sửa gold theo prediction, không thêm public source/teacher feedback làm target.

Đánh giá đủ mọi mẫu kể cả invalid; báo riêng chẩn đoán, false alarms trên clean,
Level leakage, tiếng Việt, schema/coverage và chi phí. Không thay metric Task 3
chính thức bằng taxonomy F1. Lưu before/after cùng ID, invalid đầy đủ, token,
time, VRAM, actual config và đường dẫn checkpoint. Nếu dev không tăng, báo đúng
và giữ baseline dùng được. Không gọi mô hình hoàn hảo hoặc hứa tăng điểm.

## Giới hạn dữ liệu

200 source thuộc 50 đặc tả, không phải 800 chương trình độc lập. Có 65 clean /
135 faulty; 60 source pilot dùng lại và 140 source mới thuộc 35 họ; chỉ 8 source
nhiều hàm. Bao phủ 9/10 nhãn, không tự thêm lỗi style để đủ quota. Source khá
ngắn, mutation/template còn lặp. Có 17 cặp tương đồng bề mặt cross-split được
gói công bố; kiểm grouping/hash không chứng minh độc lập ngữ nghĩa.

Dev/test cùng trợ lý biên soạn, không phải gold độc lập của BTC và không chứng
nhận tổng quát hóa lên public. Kiểm C++ là bằng chứng hữu hạn của dataset;
chưa có Qwen generations, checkpoint mới hoặc điểm leaderboard mới.
