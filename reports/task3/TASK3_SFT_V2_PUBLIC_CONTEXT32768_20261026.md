# Task3 SFT v2 public — context32768, 26/10/2026

**328/328 output hợp lệ; `complete_export=true`.**

Candidate chính xác: `/workspace/llm-final-project-arm-d-plus/outputs/task3/sft-v2-public-context32768-20261026-run1/submission/predictions.json`.

SHA256: `fc4b7ac7d7e737f7b36f464dff2df7240d7833dbb8d78332745099f2a80974bf`.

Kích thước: **82.623 byte**. **Đã xuất cục bộ, chưa submit.** File đủ cấu trúc để thử submission; tính đúng của chẩn đoán chưa được chứng nhận bởi validation.

Bản tiện dùng đã tạo tại [submission-candidates/sft-v2-context32768/predictions.json](../../submission-candidates/sft-v2-context32768/predictions.json), byte-identical với [candidate trong run](../../outputs/task3/sft-v2-public-context32768-20261026-run1/submission/predictions.json). Đích copy trước đó chưa tồn tại. Root `predictions.json`, bản partial320 và toàn bộ lượt cũ giữ nguyên.

## Context được xác minh, thay đổi được giới hạn

Model/tokenizer local pinned là `Qwen/Qwen2.5-Coder-7B-Instruct`, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`. `config.json` gốc đã có `max_position_embeddings=32768`, `rope_theta=1000000`, không có RoPE scaling, `use_sliding_window=false`; tokenizer `model_max_length=32768`. Đã kiểm hash bảy file model, bảy file tokenizer và sáu file identity checkpoint, cùng persisted selection step240. Bằng chứng source/config/backend tại [context-support-audit.json](../../outputs/task3/sft-v2-public-context32768-20261026-run1/context-support-audit.json).

Training max sequence8192, guard ứng dụng8192 và context model32768 là ba trường khác nhau. Training ở8192 không tự áp đặt trần inference8192. Lượt cũ bị chặn tại guard ứng dụng. Lượt mới giữ nguyên model config/RoPE/tokenizer, SDPA, NF4 double quant/BF16 compute và native V2 preparation. Model đã load xác nhận max position32768, SDPA, RoPE gốc. Preparation đặt `model.config.use_cache=false`, còn lời gọi sinh native truyền rõ `use_cache=true`; cache inference được dùng theo đối số này. Source Transformers Qwen2/DynamicCache đã được đối chiếu, không thay backend để tạo hỗ trợ giả.

Chỉ thay đổi khoa học dự kiến: guard context **8192→32768**, cùng giá trị đi qua preflight/config/guard lúc sinh. Module lịch sử được giữ nguyên; wrapper context mới giữ body native, có bằng chứng AST tương đương sau khi bỏ tham số/check context mới và khôi phục hằng8192. Các thay đổi quản trị được ghi riêng: identity/journal mới, kiểm provenance khi resume, lịch longest-first và báo cáo.

Method: `task3-sft-v2-step240-native-public-context32768-v1`. Freeze SHA256 `3427bee73d45210e349dccae28f7e9674b29e1fc61a32af16dcdfdf6e2bf8b71`, tại [freeze.json](../../outputs/task3/sft-v2-public-context32768-20261026-run1/freeze.json). Đã giữ freeze sơ bộ riêng, sửa binding method/freeze của journal và khóa lại trước mọi generation. Journal từ method8192 hoặc freeze khác bị từ chối dù cùng ID/prompt.

Giữ step240/r16/alpha32, native system/renderer/parser/outer-fence policy, source đầy đủ, P1–P4/prototype/prerequisite và supplied/local logs nguyên bản. Không train, đổi selection, thay prompt, nén log, truncate source, điều chỉnh RoPE, tuning, verifier Qwen, retry hoặc sửa JSON/feedback. Seed42; greedy/concurrency1; allowance L1–L3=1024, L4=1536; max_time45s; EOS151645; pad151643 như frozen8192. Public không có L4.

## Input, thứ tự và kết quả sinh mới

Official mapping xác nhận328 ID: L1=115, L2=163, L3=50, L4=0. Không suy Level từ hậu tố ID. Đã kiểm lại source/hash/mapping và cache compiler theo source, decoded source, binary/template/policy/flags. Tái dùng bằng chứng328 input/326 cache record; **0 compile mới,0 link,0 runtime chương trình sinh viên**.

Retokenize cả328 actual prompt bằng tokenizer thật; byte chat-rendered và token IDs khớp với prompt cũ được retokenize bằng snapshot pinned, và token count khớp preflight cũ. Lượt cũ không lưu vector token IDs; [prompt-equivalence.json](../../outputs/task3/sft-v2-public-context32768-20261026-run1/prompt-equivalence.json) ghi rõ phép đối chiếu này, hash token IDs mới và hash prompt. Không có discrepancy về input. Mọi prompt+allowance vừa32768; lớn nhất18.824+1.024=19.848.

Đã freeze thứ tự longest-first: **Class01-Test1-S01** là primary đầu tiên, sau đó phần còn lại theo thứ tự official. Kết quả đầu không bị bỏ làm warm-up hoặc sinh lại: input18.824 token, output42 token, EOS, valid,3,356s. Đây là kiểm tra bộ nhớ thực tế trên prompt dài nhất của bộ này; không phải phép đo synthetic ở đúng32768 token.

**Cả328 output được gọi mới**, mỗi ID một reservation/completion, không nhập320 câu trả lời cũ vào candidate.328 đều EOS/valid,0 timeout/length/OOM/parse failure/uncertain. Export trở về authoritative order, đúng wrapper `[{sample_id, output:{taxonomy_error, feedback}}]`, taxonomy thuộc label space và feedback không rỗng. Đã mở lại byte saved file bằng validator chính thức; không có private metadata trong payload. [validation.json](../../outputs/task3/sft-v2-public-context32768-20261026-run1/submission/validation.json) và `predictions.json.sha256` giữ bằng chứng.

## So với320 output trước

Trên320 ID trước đây có payload hợp lệ: **320 raw response trùng byte,320 payload trùng byte**, taxonomy đổi0, feedback đổi0, lỗi cấu trúc mới0. Input/source/spec binding đổi0 trên328. Payload bytes dùng canonical UTF8 JSON với `ensure_ascii=False`, `sort_keys=True`, separator `,`/`:`; giữ nguyên thứ tự mảng nhãn, Unicode và whitespace trong feedback. Raw equality so riêng byte UTF8 phản hồi gốc. Không giả định reproducibility trước khi đo.

Transitions trên320 cặp: nonempty→nonempty224, empty→empty96; không có chuyển empty↔nonempty. Chi tiết tại [comparison.json](../../outputs/task3/sft-v2-public-context32768-20261026-run1/analysis/comparison.json), `comparison.rows.jsonl`.

Được tái dùng đúng59 review V2 trước vì payload và full input/source binding đồng nhất. Một review cũ có payload null không đủ điều kiện;268 ID chưa có verdict được chuyển tại bước reuse. Review mới riêng tám mẫu bị chặn cũ bổ sung tám verdict, gồm trường hợp null trước đây: tổng67 ID có review nguồn, còn261 chưa review nguồn. Không chuyển verdict cho output đổi hoặc source/spec đổi; lượt này output đổi0. Các review là agent review có bằng chứng, không phải public gold độc lập. [semantic-review-reuse.json](../../outputs/task3/sft-v2-public-context32768-20261026-run1/analysis/semantic-review-reuse.json) giữ điều kiện và binding.

## Tám mẫu trước đây bị chặn

Tất cả Level2 chính thức; allowance1024, context32768, status valid/EOS. Không lấy invalid/rỗng làm clean. Source/spec review trực tiếp cho thấy cả tám có lỗi biên dịch thật trong bằng chứng có sẵn; điều đó không làm mọi lời chẩn đoán được sinh tự động đúng.

| ID | Input token thực | Chẩn đoán | L2 | Tiếng Việt |
|---|---:|---|---|---|
| Class01-Test1-S01 | 18.824 | fail | pass | pass |
| Class01-Test1-S08 | 8.548 | pass | pass | pass |
| Class01-Test1-S09 | 12.254 | pass | pass | pass |
| Class01-Test1-S10 | 9.984 | uncertain | pass | pass |
| Class01-Test2-S08 | 9.259 | pass | pass | pass |
| Class01-Test2-S13 | 11.354 | pass | fail | pass |
| Class02-Test1-S19 | 12.809 | fail | pass | pass |
| Class02-Test1-S34 | 8.602 | pass | pass | pass |

Năm chẩn đoán supported, hai fail, một uncertain; L2 form7pass/1fail; tiếng Việt8pass. Taxonomy–feedback7pass/1fail. Đây là thống kê của tám review, không phải accuracy/F1 public. S01 nói trả null nhưng source là bare `return;` trong hàm trả `General*`; null pointer và thiếu giá trị trả là hai hành vi khác nhau. S10 khẳng định bỏ mất dữ liệu dòng đầu nhưng chưa có CSV/header để chứng minh. S19 nói về bỏ dòng khi đếm trong khi gắn nhãn compilation và không chẩn đoán lỗi compile/type thực tế. S13 có chẩn đoán vector→General có căn cứ nhưng dùng hai câu, trái hợp đồng L2 một câu ngắn. Không sửa câu nào để qua review.

[Casebook tám mẫu](../../outputs/task3/sft-v2-public-context32768-20261026-run1/eight-review/casebook.html) chứa full source/yêu cầu/log, nguyên raw output, verdict/evidence; dữ liệu máy tại [eight-formerly-blocked.json](../../outputs/task3/sft-v2-public-context32768-20261026-run1/analysis/eight-formerly-blocked.json) và [review.jsonl](../../outputs/task3/sft-v2-public-context32768-20261026-run1/eight-review/review.jsonl). Phần cuối báo cáo chép nguyên cả tám phản hồi.

## Chi phí, kiểm chứng và giới hạn

328 attempted/reserved/completed, không retry hoặc reservation uncertain. Input **607.419 token**, output **12.475 token**. Load model+adapter **14,967s**, trong đó base6,132s đã nằm trong tổng, không cộng đôi. Generation phase **339,983s** gồm toàn bộ lời gọi và persistence; tổng per-call **334,503s**. Peak CUDA toàn pha sau load: allocated **16.162.931.712 byte (15,053GiB)**, reserved **18.763.218.944 byte (17,475GiB)**. Reset đúng một lần trước pha, không reset từng case; đo CUDA allocator, không phải NVML toàn hệ thống. GPU RTX5090. [costs.json](../../outputs/task3/sft-v2-public-context32768-20261026-run1/analysis/costs.json) giữ scope, thời gian từng call và hash dữ liệu nguồn.

**102 test liên quan pass**, gồm admission của input>8192 ở32768, boundary31744+1024, reject31745+1024, full prompt/allowance/không truncate, one-attempt, không nhận journal khác method/freeze, export/denominator/parser và review reuse khi byte/source đổi. [final-integrity.json](../../outputs/task3/sft-v2-public-context32768-20261026-run1/final-integrity.json):30 named checks đều pass, xác minh lại weights thật, model/adapter/freeze, fresh journal, token/order, candidate/copy và toàn bộ lịch sử.899 file repo có trước cùng run8192/experiment V1/V2/root predictions giữ nguyên hash. Không commit, push, upload hoặc submit.

Context cao hơn giải quyết coverage, chưa chứng minh chất lượng chẩn đoán tăng.320 output giống hệt giữ nguyên cả ưu/nhược điểm đã review ở lượt cũ, gồm bỏ sót lỗi và báo oan; tám output mới vẫn có chẩn đoán sai/uncertain và một lỗi Level. Adapter train8192 chưa được chứng nhận tổng quát hóa tốt lên input dài. Không có public gold, accuracy/F1 hoặc leaderboard mới; không khẳng định tốt hơn A/R15 hay hứa tăng điểm.

## Lệnh kiểm chứng offline và resume

Từ `/workspace/llm-final-project-arm-d-plus`, không cần tải gì:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_context32768.py verify
PYTHONDONTWRITEBYTECODE=1 /workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_context32768_verify.py
```

Hai lệnh chỉ đọc/hash/validate, không load Qwen, gọi CUDA hoặc compiler. Để resume đúng run nếu bị ngắt:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_context32768.py infer
```

Completed được phục hồi từ journal; reservation uncertain không gọi lại. Trên run hoàn tất hiện tại lệnh không load model/gọi mới. Không chạy `prepare`/`export` đè run đã có. Metadata/sidecar và checksum độc lập với official payload; xem [hướng dẫn](../../docs/task3_sft_v2_context32768.md).

## Nguyên tám phản hồi mới

### Class01-Test1-S01

Requested: Level 2 - Chẩn đoán; input=18824; status=valid; finish=eos.

```json
{"taxonomy_error": ["Lỗi biên dịch"], "feedback": "Hàm đọc dữ liệu từ tệp trả về một con trỏ null khi gặp lỗi và thiếu giá trị trả về."}
```

### Class01-Test1-S08

Requested: Level 2 - Chẩn đoán; input=8548; status=valid; finish=eos.

```json
{"taxonomy_error": ["Lỗi biên dịch"], "feedback": "Hàm đọc dữ liệu trong prob1 thiếu đối tượng đầu vào và sử dụng toán tử xuất không hợp lệ."}
```

### Class01-Test1-S09

Requested: Level 2 - Chẩn đoán; input=12254; status=valid; finish=eos.

```json
{"taxonomy_error": ["Lỗi biên dịch"], "feedback": "Hàm đọc file trả về rỗng khi gặp lỗi và thiếu giá trị trả."}
```

### Class01-Test1-S10

Requested: Level 2 - Chẩn đoán; input=9984; status=valid; finish=eos.

```json
{"taxonomy_error": ["Lỗi nhập/xuất"], "feedback": "Hàm prob1 đọc dòng đầu tiên của file làm tiêu đề nên bỏ qua dữ liệu cần thiết."}
```

### Class01-Test2-S08

Requested: Level 2 - Chẩn đoán; input=9259; status=valid; finish=eos.

```json
{"taxonomy_error": ["Lỗi biên dịch"], "feedback": "Hàm insertBST nhận tham số g kiểu vector nhưng chỉ xử lý một phần tử."}
```

### Class01-Test2-S13

Requested: Level 2 - Chẩn đoán; input=11354; status=valid; finish=eos.

```json
{"taxonomy_error": ["Lỗi biên dịch"], "feedback": "Trong hàm prob2(), bạn cố gắng gán một vector vào một biến thuộc kiểu General. Điều này gây lỗi biên dịch vì phép gán giữa hai loại dữ liệu khác nhau."}
```

### Class02-Test1-S19

Requested: Level 2 - Chẩn đoán; input=12809; status=valid; finish=eos.

```json
{"taxonomy_error": ["Lỗi biên dịch"], "feedback": "Hàm countLine đọc dòng đầu tiên làm trống và bỏ qua nó trong đếm."}
```

### Class02-Test1-S34

Requested: Level 2 - Chẩn đoán; input=8602; status=valid; finish=eos.

```json
{"taxonomy_error": ["Lỗi biên dịch"], "feedback": "Khai báo cấu trúc Battle thiếu dấu chấm phẩy ở cuối."}
```
