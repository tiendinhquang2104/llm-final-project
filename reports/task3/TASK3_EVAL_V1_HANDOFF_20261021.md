# Task 3 — Evaluation v1 đã freeze (2026-10-21, Asia/Saigon)

**Đã khóa 86 source / 28 family và 122 requests; không train, load model, inference, chọn checkpoint, push hay nộp leaderboard.** Model scope giữ Qwen2.5-Coder-7B-Instruct (<10B); adapter R18 không đủ điều kiện. Bộ này là development evaluation có kiểm soát phơi nhiễm, **không phải benchmark mù**.

HEAD trước sửa: `da41adb69b3091e5c9c859be13b94d40892fb80a`, branch `feat/task3-quality-round5`; working tree ban đầu sạch. Chỉ thêm file mới, không sửa file có sẵn. SHA-256 của ZIP được kiểm đúng bytes, không suy version từ tên và không giải nén đè split. Manifest lưu hash từng member được đọc.

[Freeze manifest](TASK3_EVAL_V1_FREEZE_20261021.json) khóa selection policy, thứ tự ID, source/statement/problem-context hashes, Level, source-reference hash, requests, rubric, definitions và implementation. [Train-exclusion manifest](TASK3_EVAL_V1_TRAIN_EXCLUSION_20261021.json) lưu các identity/family phải chặn.

Phân bố: **74 defective, 11 scoped-clean (12.79%), 1 unresolved; 56 single_problem, 30 multi_problem**. 80 primary L1–3 có tỷ lệ **28:40:12**, gần 115:163:50; thêm 6 L4. Counterfactual cố định **12 source lấy từ evaluation × L1/2/3 = 36 requests**, 12 family, gồm 2 scoped-clean. Scoring primary/counterfactual tách biệt; không nhân ba trọng số taxonomy primary.

| Nhóm chính thức | Annotation v2 | Source-reference | Family source-reference |
|---|---:|---:|---:|
|Lỗi biên dịch|6|6|6|
|Lỗi edge case|4|4|4|
|Lỗi hard-code|8|7|7|
|Lỗi hàm|10|12|11|
|Lỗi logic|17|13|11|
|Lỗi mảng/chuỗi|18|18|15|
|Lỗi nhập/xuất|3|7|7|
|Lỗi style|4|0|0|
|Lỗi thuật toán|9|6|6|
|Lỗi vòng lặp|18|19|15|

**Thiếu coverage:** source-reference style có support 0 vì không có quy tắc style rõ trong các đề đã chọn; TODO/comment/biến không dùng không tự thành lỗi. Giữ đủ 10 nhãn trong macro-F1, không bịa lỗi để lấp nhóm. Annotation v2 vẫn có 4 style. Source-reference có 85 source xác định và 19 bất đồng tập nhãn với v2; không sửa ZIP/gold. AL-vs-LG/FN, whitespace, domain/time limit nằm trong review packet.

| Level | Source | Clean | Defective | Unresolved |
|---|---:|---:|---:|---:|
|1|28|4|23|1|
|2|40|5|35|0|
|3|12|2|10|0|
|4|6|0|6|0|

Level assignment được định trước bằng largest-remainder và shuffle seed42, không suy taxonomy từ Level. Các strata primary thưa: L1 thiếu AL/ST; L3 thiếu BC/FN/AL/ST; L4 thiếu BC/IO/LG/EC/ST. Counterfactual có AL ở cả L1/2/3 nhưng báo riêng, không gộp để che thiếu support. Manifest có support từng nhãn theo Level và single/multi, cùng ID/family đầy đủ.

Kiểm kê lịch sử đã đọc metadata R13–R18: 495 synthetic-train, 26 real-train, 47 heldout cũ, sáu real-val; R14 kể cả selection superseded; development R15/R16/R17; few-shot bank/draft và parent source; 20 R18 train code, 20 counterfactual và 16 paired evaluation; 22 artificial R13 development/check cases. Giữ cả source variants/hash cũ và mới. Registry lịch sử có 638 identity variants; registry train sau thêm evaluation có 724 entries (entries là event/variant, không phải 724 source độc lập). Hai ID từng lọt R18 nằm trong gate cùng toàn bộ peer, không có special-case chỉ hai ID.

Trong 15 source mới của ZIP: 8 đã dùng R18 nên không chọn; 7 chưa dùng theo ID/source trong các thí nghiệm được chọn. Cả 28 family/template đã có phơi nhiễm. Source-only corpus/source-pool exposure khác với ID đã xem model output hoặc làm bank/target; registry giữ hai mức riêng. Không có selected ID/group/exact/token/identifier-renamed identity khớp direct experimental history. Không đọc public inputs/predictions, raw outputs R15/R18 hoặc điểm leaderboard để chọn source/reference/method. Chỉ hash public predictions trong bước kiểm bảo toàn bytes độc lập.

Có **442 cặp** evaluation–history đạt ngưỡng shingle Jaccard ≥0.85, lưu riêng như tín hiệu lexical review, gồm source từng quét trong corpus và các template gần nhau. Không gọi ngưỡng này là chứng minh semantic độc lập. **Train eligibility hiện tại = 0** vì family của evaluation/development lịch sử đều bị cấm. Không có source dự kiến train nào được admit để trùng eval; không nới family gate để tạo train set. Fine-tuning sau này cần family/source mới vượt cả registry và review semantic near-duplicate.

Guard chạy được ở hai boundary `before_targets` và `before_optimizer`, từ chối thiếu identity/source hoặc match ID/group/family/exact/token/rename/near-duplicate. Các script train cũ giữ nguyên; chưa có target writer/optimizer mới chạy trong lượt này. Bước fine-tuning sau phải tích hợp guard vào cả hai boundary, không chỉ gọi thủ công một lần.

**Evidence:** 93 primary findings: 75 symbolic counterexamples và 18 static reasoning; tất cả `agent-reviewed static reasoning`, không human-verified, không thực thi/biên dịch source evaluation. Một finding overflow chỉ đúng sau khi sửa shadowing được chuyển sang `conditional_findings`, không làm yêu cầu chẩn đoán primary. 11 clean có invariant/lập luận và domain cụ thể (ASCII, count/capacity, nonempty, intermediate arithmetic…). Compile pass không được dùng làm bằng chứng đúng.

Sandbox host không tạo được namespace (`bwrap`); không chạy mã sinh viên để thử phản ví dụ và không gọi compiler trên source evaluation. Các test C++ có sẵn chỉ dùng artificial fixtures của repository; không dùng chúng làm bằng chứng đã chạy 86 source. Các chẩn đoán syntax ở đây là agent static reasoning, không gắn nhãn compiler-confirmed.

Unresolved duy nhất là ID trong freeze có token viết hoa đúng kèm leading space: đề không chỉ rõ checker whitespace. Annotation v2 được giữ; source-reference = null, không tự biến thành clean. Chi tiết quote/cause/input/expected/derived nằm riêng tư. Những tình huống EOF probe, allocated-but-uninitialized, string terminator, shadowing và prerequisite P1 đã được review chéo. Không khẳng định output xác định sau undefined behavior.

Evaluator cố định báo completion/schema/unresolved/abstained/runtime error riêng; `[]` chỉ đúng khi có output hợp schema thật. TP/FP/FN, micro/macro đủ 10 nhãn và exact set xuất thành **hai bảng annotation v2/source-reference**. Missing/error vẫn có FN và không được thưởng exact-clean. Invariance chỉ trên completed triples, kèm mẫu số incomplete. Feedback dùng ledger gắn prediction SHA-256, reviewer, evidence và rationale; thiếu review/null là pending, không thành điểm 0 hay pass. L1 disclosure/L2 repair leak áp dụng cả clean; L2 hữu ích/L3 sửa khả thi và false-clean/missing-core có domain/mẫu số defect rõ. Diagnostic Unicode tự động hiện dò Han; đánh giá CJK (kể cả kana/Hangul) và tiếng Việt vẫn cần ledger ngữ nghĩa, không suy truth từ detector. Không keyword gate hay LLM judge nào được coi là ground truth.

Private snapshot nằm dưới ignored storage; Git chỉ chứa code/test/metadata/report, không source, statement, quote hoặc finding chi tiết:

| Artifact riêng tư — thư mục gốc bên dưới | SHA-256 |
|---|---|
|`historical-inventory.private.json`|`1ada3d6ce24e510773073c0d60a09c84a36c8bfb93c9a9cd0811fe30fc1e9fc4`|
|`level-contracts.json`|`c525cb2251444e8488caf87b220d3b2120aba7b5c83065a8cf247682c8b9abb0`|
|`metric-definitions.json`|`c2190e8b475fccd38fc0d45a0355fe969febb1f8238de4ae186dc28652a4d39d`|
|`model-inputs.private.json`|`cf6b2f2f3b54b074038c58766b6817c23d53e0ffd0b1a8a38499da72565608dc`|
|`near-duplicate-registry.private.json`|`1b099ad0b951ee367436c0e33a82f7bd239457c9901daeaa3b05296c1ea226bf`|
|`policy.json`|`cbceb9b27c515efa2d9771c02dad0483e90aaae87fba286aecf46b61d99b985d`|
|`reference.private.json`|`6ac5403e4e4704697bf920c5e63c2341141542bcc07fee67b06156f39018041b`|
|`review-packet.private.json`|`2aef0a3f05dbe551b6f87c9c9848a504908228070d577d34a0918cf86bbef366`|
|`train-registry.private.json`|`753ccad7338ee62d5e8f6cb6782bdcbe72482208eb67ea0e2981f46a501f13c6`|

Đường dẫn tuyệt đối: `/workspace/llm-final-project/outputs/task3/eval-freeze-v1-20261021/frozen`.

Freeze manifest SHA-256: `f7693da146b174faefd12fae96f9a7a3fbca118c1f8fd01d164d16b30d619e83`.
Seal SHA-256: `3276cb4fa2990330fcd6d9f92e0b691db352090452146db02abb0e3cda94f2f1`.

`reference.private.json` có source/statement, provenance/ID/problem/prototype/prerequisite, exact quote spans, domain, finding và rubric từng Level. `model-inputs.private.json` chỉ có input được phép, không gold/reference/teacher feedback; payload `task` của từng CF code bằng nhau giữa 3 Level. `review-packet.private.json` chứa disputed/conditional/unresolved cùng source audits và code audit; các lỗi integrity phát hiện trước freeze đã có regression test và review xác nhận sửa.

Kiểm thử và bàn giao: **724 passed, 4 skipped** cho toàn bộ `tests/test_task3*.py`, gồm **65 test mới**. Full `pytest -q` không collect được hai module Task 1 (`test_clm_zeroshot_task1.py`, `test_task1_clm_probe.py`) vì môi trường thiếu `sklearn`; không sửa dependency ngoài phạm vi. Lượt bổ sung Task3+synthetic bị ngắt sau hơn 10 phút tại test build generated fixture có sẵn, không tuyên bố lượt này pass. [Verification JSON](TASK3_EVAL_V1_VERIFICATION_20261021.json) ghi commands và trạng thái riêng.

Review artifact độc lập qua **520 kiểm tra**, không còn finding quan trọng. Smoke evaluator dùng list predictions rỗng (fixture, không inference): 86 unresolved, 0 exact-clean reward, 12 incomplete CF triples, semantic pending. Cả 20 R18 train ID bị chặn tại cả hai boundary; prepare lặp bị từ chối. Sau test, **517 tracked file ban đầu và 154 artifact được bảo vệ** giữ nguyên bytes; public predictions chỉ hash, SHA-256 vẫn `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`.

Tái hiện từ `/workspace/llm-final-project` (chỉ dùng archive đúng hash và private review artifacts đã có):

```bash
.venv-task3/bin/python scripts/task3_freeze_eval.py prepare
.venv-task3/bin/python scripts/task3_freeze_eval.py verify
```

`prepare` đã chạy; chạy lại sẽ từ chối ghi đè. Dùng `verify` cho snapshot hiện tại. Không xóa seal để chọn lại sau khi thấy output. Mọi sửa reference sau này cần phiên bản mới và changelog, không viết đè snapshot này.

Evaluator cho prediction của bước sau; predictions là list `{request_id,status,output}` hoặc `{request_id,status,raw_text}`; output đúng hai trường `taxonomy_error` và `feedback`. Status: `completed`, `unresolved`, `abstained`, `runtime_error`, `schema_error`. Request IDs lấy nguyên từ manifest, giữ primary/cf riêng:

```bash
.venv-task3/bin/python scripts/task3_freeze_eval.py review-template \
  --predictions outputs/task3/eval-v1-step2/METHOD.predictions.json \
  --output outputs/task3/eval-v1-step2/METHOD.review-template.json
.venv-task3/bin/python scripts/task3_freeze_eval.py evaluate \
  --predictions outputs/task3/eval-v1-step2/METHOD.predictions.json \
  --ledger outputs/task3/eval-v1-step2/METHOD.reviewed-ledger.json \
  --output outputs/task3/eval-v1-step2/METHOD.evaluation.json
```

Bỏ `--ledger` để tái tính taxonomy/completion trước, phần semantic vẫn pending. Template phải được điền reviewer/rationale/evidence và bool/null; không dùng exact string match. `write_new` từ chối ghi đè output metric/ledger, nên dùng tên output mới khi thêm review.

```bash
.venv-task3/bin/python scripts/task3_freeze_eval.py train-gate \
  --candidates outputs/task3/FUTURE/candidate-identities.json --stage before_targets
.venv-task3/bin/python scripts/task3_freeze_eval.py train-gate \
  --candidates outputs/task3/FUTURE/candidate-identities.json --stage before_optimizer
```

Candidate là list có `sample_id`, `family`/`exam_id`, `group`, `code` và provenance/hash. New-family candidate bắt buộc có source để screen near-duplicate; guard vẫn phải được gọi trong code target writer/optimizer với đúng candidate bytes.

BƯỚC 2 (chưa chạy): verify seal rồi paired R15 7B vs hai bước base 7B vs adapter 7B **hợp lệ** trên đúng 86 primary và 36 counterfactual requests. Khóa decoder/precision/revision/compiler evidence chung, lưu raw/final/unresolved và SHA; không tune prompt/checkpoint trên output này. Hai bước phải diagnostic không Level, final taxonomy copy từ diagnostic. Chỉ arm adapter được dùng adapter đã qua cách ly train; không tái dùng adapter R18 bị loại. Nếu chưa có adapter hợp lệ thì arm đó còn pending, không train trong bước chuẩn bị này để lấp điều kiện. Model inference inputs lấy từ `model-inputs.private.json`, không đưa `reference.private.json` hoặc ledger vào model.
