# Taxonomy trước Feedback Level: thí nghiệm offline khóa trên Round 24

Ngày bàn giao: 22/10/2026 (Asia/Saigon).

**Verdict: CHƯA ĐỦ BẰNG CHỨNG cho giả thuyết đầy đủ “bỏ Level giúp taxonomy ổn định và đúng hơn”; giữ R15.** Nhánh tách bước giảm bỏ nhãn so với L1 và tăng micro-F1 so với baseline chính L2, nhưng precision giảm, FP tăng và review phát hiện lặp lại nhãn chức năng mới không có căn cứ trên hai source. Gate nội dung không đạt; dừng sau taxonomy, không sinh feedback, không mở prompt vòng hai.

## Thiết kế và khóa trước inference

- Branch: `feat/task3-quality-round5`. HEAD đầu: `acc4961b6354785a04e4d1b7662135cf7fdfe593`. `git status --short` ban đầu: rỗng (sạch). HEAD cuối là commit bàn giao chứa báo cáo này; hash đầy đủ được ghi sau commit tại `outputs/task3/level-blind-20261022/handoff.private.json` và trong lời bàn giao. Không chèn hash tự tham chiếu vào chính commit. Trường initial_status trong manifest là status ở thời điểm freeze (đã có code/test mới), khác status sạch trước khi bắt đầu.

- Freeze: `2026-10-22T08:29:04.694534+00:00` = 15:29:04 ngày 22/10/2026 giờ Việt Nam; SHA-256 manifest: `3e567d73948bc2a4b341ec0f68ada0caab9248133ae4fb846b963aab550d3a5c`. Manifest: `outputs/task3/level-blind-20261022/manifest.private.json`; seal: `manifest.sha256`.

- Prompt template hash: `d9ad48d56553d68f927afe1aea481e828664ef225b0a6e6db1994a3d86d323b8`. 20 rendered prompt/hash đầy đủ đã lưu trước inference trong `rendered-prompts.private.json`; template và payload đều được audit, không chỉ tìm tên biến.

- Model `Qwen/Qwen2.5-Coder-7B-Instruct`, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`; base model <10B, không adapter/fine-tuning/API LLM ngoài. Runtime kiểm tra NF4, double quantization, compute BF16; toàn bộ model trên CUDA.

- Payload taxonomy đúng 5 trường từ first rendered user payload R15, giữ nguyên statement/problems/grading_policy/code/compiler, bỏ requested_level. Mọi source có compiler status unknown, diagnostic rỗng. Không biên dịch hoặc chạy chương trình mới. Không thêm target Level, gold, teacher feedback, prior prediction, review, split hoặc metadata code_path/sample_id vào payload. Tên file và problem ID tự nhiên vốn có trong đề/code/problems được giữ nguyên từ R15; không thêm tên file tiết lộ nhãn/split. Problems chỉ có pid/statement/prototype. Không dùng ví dụ, CoT, witness, voting, rulebook hoặc semantic retry.

- Parser: một JSON object đúng một khóa taxonomy_error; hoặc một object duy nhất trong fence json/không ngôn ngữ. Từ chối prose/thinking, khóa trùng/thừa, nhãn lạ/trùng. JSON/schema failure được tối đa **một** retry kèm lỗi định dạng, không nạp lại câu trả lời trước hoặc chọn câu điểm cao. Runtime error không retry. Hết retry giữ invalid/None; không đổi thành ∅.

- Mỗi source nhận một prediction taxonomy; cùng một giá trị được project đúng ba ID có sẵn. Retry chỉ là ngoại lệ schema được khóa. Baseline chính R15 L2 cố định trước inference; L1/L3 báo đầy đủ. R15 sinh taxonomy + feedback, nhánh mới taxonomy only: khác tác vụ và chi phí, không phải phép so sánh một biến thuần túy.

- Chỉ có một prompt mới và một lượt chính thức. Gate đã khóa: 20/20 valid; F1 > L2; EM ≥ L2; không có cơ chế FP hàng loạt mới theo review nguồn; báo TP/FP mới và xác nhận lợi ích có căn cứ. Protocol feedback có điều kiện đã ghi vào manifest, nhưng **không được thực thi** vì gate review thất bại.

### Generation config thực tế

```json

{
  "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
  "revision": "c03e6d358207e414f1eca0bb1891e29f1db0e242",
  "seed": 42,
  "data_dir": "data/processed/task3",
  "context_limit": 16384,
  "max_new_tokens": 1024,
  "level4_max_tokens": 1536,
  "max_attempts": 3,
  "generation_max_time_s": 45,
  "do_sample": false,
  "few_shot_k": 0,
  "load_in_4bit": true,
  "cpp_compiler": "/usr/bin/g++",
  "compiler_timeout_s": 3,
  "prompt_policy": "round15-short-direct-v1",
  "example_bank": "outputs/task3/round15/train-examples.json",
  "completion_policy": "preserve_qwen_content_with_schema_and_explicit_l1_l2_only",
  "prompt_variant": "zero_shot"
}

```

`max_attempts: 3` trong config kế thừa chỉ dành cho protocol feedback/R15; runner taxonomy áp dụng cứng tối đa 2 calls/source (1 + 1 schema retry). `cpp_compiler` và example_bank là config kế thừa, không được gọi/đọc để bổ sung bằng chứng hay few-shot trong thí nghiệm này.

### System template nguyên văn

Bạn đọc yêu cầu bài toán và mã C++ của sinh viên. Xác định những nhóm lỗi có bằng chứng từ mã nguồn so với yêu cầu bài toán. Chỉ trả về JSON có đúng một khóa `taxonomy_error`, là mảng không lặp các tên nhóm trong danh sách cho phép: `Lỗi biên dịch`, `Lỗi nhập/xuất`, `Lỗi logic`, `Lỗi vòng lặp`, `Lỗi mảng/chuỗi`, `Lỗi hàm`, `Lỗi edge case`, `Lỗi thuật toán`, `Lỗi hard-code`, `Lỗi style`. Có thể trả `[]` nếu không đủ căn cứ xác định lỗi. Không sinh feedback, giải thích, hướng sửa hoặc văn bản ngoài JSON. Không suy ra chương trình đúng chỉ từ việc biên dịch thành công.

### User template nguyên văn

```python

json.dumps(payload, ensure_ascii=False)

```

`payload` có đúng các khóa theo thứ tự `statement`, `problems`, `grading_policy`, `code`, `compiler`; giá trị giống R15 đối ứng. Chat framing dùng tokenizer Qwen đã pin, hash template `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`. Từ “Level” tự nhiên trong statement/code không được dùng như phép dò leak thô.

Format-only retry template nguyên văn: JSON/schema không hợp lệ: {error}. Chỉ trả lại JSON đúng schema đã yêu cầu.

## Xác minh tập và baseline

- Dùng nguyên sources.private.json, model-inputs.private.json và selection-freeze.json Round 24; không chọn lại source hoặc tạo tập tương đương. 20 source train-only: 12 real + 8 synthetic; 10 development + 10 confirmation. 20 hash code, 20 token hash, 20 renamed-code hash khác nhau. Origin record, bytes source, code text, ID/projection, gold và feedback gốc đều đối chiếu khớp. Archive provenance synthetic được giữ nguyên trong manifest nguồn và đối chiếu bổ sung sau run (8/8 khớp); trước inference đã xác minh origin record/hash và raw-source hash. Không tái tạo dữ liệu.

- **60 ID chỉ là ba projection của 20 source**, không phải 60 mẫu độc lập. “Confirmation” là tên ranh giới được giữ từ manifest cũ, không blind/independent: cả hai nửa đã lộ qua nhiều vòng. Các family/đề chung còn có thể tương quan, nên 20 đơn vị source cũng không bảo đảm độc lập thống kê tuyệt đối.

- Baseline có đủ 60/60 prediction, 60 trace, 68 raw attempts và decisions đối ứng. Có 8 calls retry, 3 disclosure fallback (EX01-S103 L1, EX01-S113 L1, EX02-S209 L1). First raw attempt đều parse được schema R15. Tính lại trực tiếp: 17/20 source đổi taxonomy giữa L1/L2/L3 ở first raw, 15/20 ở final. Hai fallback L1 đổi taxonomy làm giảm số source có biến thiên; không nhập nhằng raw với final.

- Các bản reference agent không phải gold gốc: reference.private.json ban đầu 3 confirmed/17 disputed; overlay reference-rulebook-v2.private.json cuối cùng 7 confirmed theo provisional agent mapping/13 disputed. Cả 20 human_verified=false; human-decisions.private.json rỗng. Gold chính luôn lấy nguyên annotation train, không lấy overlay.

## Metrics theo gold gốc (20 source)

| Phương pháp | Valid/invalid | EM | TP/FP/FN | P micro | R micro | F1 micro | F1 macro | ∅ khi gold≠∅ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R15_L1 | 20/0 | 2/20 | 1/1/24 | 0.500000 | 0.040000 | 0.074074 | 0.055556 | 16 |
| R15_L2 | 20/0 | 3/20 | 6/9/19 | 0.400000 | 0.240000 | 0.300000 | 0.097222 | 4 |
| R15_L3 | 20/0 | 3/20 | 6/11/19 | 0.352941 | 0.240000 | 0.285714 | 0.086257 | 2 |
| level_blind | 20/0 | 3/20 | 9/17/16 | 0.346154 | 0.360000 | 0.352941 | 0.191270 | 1 |


Macro-F1 theo convention Round 24: trung bình chỉ trên nhóm có gold support >0; nhóm không có support không vào macro. Trong tập này có 9 nhóm support; edge case không support. Per-label F1 không xác định ghi NA; precision/recall mẫu số 0 cũng NA. Invalid bị đếm riêng, không exact kể cả gold rỗng, và mọi nhãn gold của source invalid vẫn là FN. Không có invalid ở kết quả cuối.

### Từng nhóm nhãn (TP/FP/FN; F1)

| Nhóm chính thức | R15 L1 | R15 L2 (chính) | R15 L3 | Level-blind |
| --- | --- | --- | --- | --- |
| Lỗi biên dịch | 1/1/1; 0.500000 | 1/5/1; 0.250000 | 1/5/1; 0.250000 | 1/5/1; 0.250000 |
| Lỗi nhập/xuất | 0/0/1; 0.000000 | 0/1/1; 0.000000 | 0/0/1; 0.000000 | 1/2/0; 0.500000 |
| Lỗi logic | 0/0/9; 0.000000 | 5/2/4; 0.625000 | 5/5/4; 0.526316 | 6/6/3; 0.571429 |
| Lỗi vòng lặp | 0/0/4; 0.000000 | 0/0/4; 0.000000 | 0/0/4; 0.000000 | 1/0/3; 0.400000 |
| Lỗi mảng/chuỗi | 0/0/1; 0.000000 | 0/0/1; 0.000000 | 0/0/1; 0.000000 | 0/1/1; 0.000000 |
| Lỗi hàm | 0/0/1; 0.000000 | 0/1/1; 0.000000 | 0/1/1; 0.000000 | 0/2/1; 0.000000 |
| Lỗi edge case | 0/0/0; NA | 0/0/0; NA | 0/0/0; NA | 0/0/0; NA |
| Lỗi thuật toán | 0/0/2; 0.000000 | 0/0/2; 0.000000 | 0/0/2; 0.000000 | 0/0/2; 0.000000 |
| Lỗi hard-code | 0/0/1; 0.000000 | 0/0/1; 0.000000 | 0/0/1; 0.000000 | 0/1/1; 0.000000 |
| Lỗi style | 0/0/4; 0.000000 | 0/0/4; 0.000000 | 0/0/4; 0.000000 | 0/0/4; 0.000000 |


### Breakdown đã khóa

| Nhóm | Phương pháp | n | EM | TP/FP/FN | micro-F1 |
| --- | --- | --- | --- | --- | --- |
| development | R15_L1 | 10 | 1 | 1/1/12 | 0.133333 |
| development | R15_L2 | 10 | 1 | 3/5/10 | 0.285714 |
| development | R15_L3 | 10 | 1 | 3/7/10 | 0.260870 |
| development | level_blind | 10 | 2 | 5/8/8 | 0.384615 |
| confirmation | R15_L1 | 10 | 1 | 0/0/12 | 0.000000 |
| confirmation | R15_L2 | 10 | 2 | 3/4/9 | 0.315789 |
| confirmation | R15_L3 | 10 | 2 | 3/4/9 | 0.315789 |
| confirmation | level_blind | 10 | 1 | 4/9/8 | 0.320000 |
| real | R15_L1 | 12 | 2 | 1/1/15 | 0.111111 |
| real | R15_L2 | 12 | 1 | 3/8/13 | 0.222222 |
| real | R15_L3 | 12 | 1 | 3/8/13 | 0.222222 |
| real | level_blind | 12 | 2 | 7/12/9 | 0.400000 |
| synthetic | R15_L1 | 8 | 0 | 0/0/9 | 0.000000 |
| synthetic | R15_L2 | 8 | 2 | 3/1/6 | 0.461538 |
| synthetic | R15_L3 | 8 | 2 | 3/3/6 | 0.400000 |
| synthetic | level_blind | 8 | 1 | 2/5/7 | 0.250000 |


Confirmation tăng F1 rất ít (0,315789 → 0,320000), EM giảm 2 → 1 và FP tăng 4 → 9. Synthetic giảm F1 0,461538 → 0,250000. Vì vậy lợi ích tổng không nhất quán giữa các nhóm; không viện dẫn 60 ID để phóng đại độ tin cậy.

### Sensitivity: chỉ 7 source provisional của agent, không thay gold

| Phương pháp | n | EM | TP/FP/FN | micro-F1 |
| --- | --- | --- | --- | --- |
| R15_L1 | 7 | 0 | 0/0/10 | 0.000000 |
| R15_L2 | 7 | 2 | 3/3/7 | 0.375000 |
| R15_L3 | 7 | 1 | 2/5/8 | 0.235294 |
| level_blind | 7 | 2 | 4/3/6 | 0.470588 |


13 source disputed giữ trong mọi metrics gold gốc; không có canonical agent reference để tính exact/F1 thay thế cho chúng. Casebook ghi điều kiện/domain/category tranh chấp và gold-disagreement từng nhãn. Không chọn một disputed option có lợi để chấm lại. Không có human verified subset (n=0, không báo điểm).

## Bảng 20 source

Ký hiệu rút gọn chỉ dùng trong báo cáo: Lỗi biên dịch=BD, Lỗi nhập/xuất=NX, Lỗi logic=LG, Lỗi vòng lặp=VL, Lỗi mảng/chuỗi=MC, Lỗi hàm=HM, Lỗi edge case=EC, Lỗi thuật toán=TT, Lỗi hard-code=HC, Lỗi style=ST. ∅ là prediction rỗng hợp lệ. D/C=development/confirmation; P=provisional agent, X=disputed. `R24-...` là stem của ba ID đúng manifest, thêm `-L1`, `-L2`, `-L3`. Hash ngắn là prefix SHA-256 của code text.

| Source / query stem | Hash / split | Gold | R15 L1 | R15 L2 | R15 L3 | Mới | Valid/retry | TP / FP / FN | Review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EX01-S101 / R24-de1599afc3 | e66ff20525bb / D | LG | ∅ | BD | BD | BD | valid / 1 | ∅ / BD / LG | X |
| EX01-S103 / R24-f9467ace63 | 2773a782ad88 / D | HC,BD | BD | BD | BD | BD,NX,LG | valid / 0 | BD / LG,NX / HC | X |
| EX01-S105 / R24-7d4eae3552 | 24585a3812d3 / D | MC,LG | ∅ | BD | BD | BD,LG | valid / 0 | LG / BD / MC | X |
| EX01-S107 / R24-399047b69b | bbbc50feb702 / D | LG,VL | ∅ | BD | BD | BD,LG | valid / 0 | LG / BD / VL | X |
| EX01-S113 / R24-1b0e067d74 | 4893932d2266 / D | HM | BD | BD | BD | BD,LG | valid / 1 | ∅ / BD,LG / HM | X |
| EX01-S115 / R24-9d3f72a8d5 | cd348457aa46 / D | ∅ | ∅ | BD | BD | ∅ | valid / 0 | ∅ / ∅ / ∅ | X |
| EX02-S202 / R24-0ea31a81ff | 504cf40dead5 / C | ∅ | ∅ | ∅ | ∅ | ∅ | valid / 1 | ∅ / ∅ / ∅ | X |
| EX02-S203 / R24-669ed70557 | 2ec0c125df37 / C | BD | ∅ | HM | LG | LG,HM | valid / 1 | ∅ / HM,LG / BD | X |
| EX02-S205 / R24-2873cb0406 | b4c902c4f28d / C | NX | ∅ | LG | LG | LG,NX | valid / 1 | NX / LG / ∅ | X |
| EX02-S207 / R24-10cc34e4d7 | 8e158849bc4a / C | TT | ∅ | LG | LG | LG | valid / 1 | ∅ / LG / TT | P |
| EX02-S209 / R24-b423346d0b | 34daa7a893b5 / C | LG,TT,VL | ∅ | LG | LG | LG,VL | valid / 1 | LG,VL / ∅ / TT | X |
| EX02-S216 / R24-5a029c4663 | 1cd8312126d1 / C | LG,VL | ∅ | LG | LG | LG,MC | valid / 1 | LG / MC / VL | P |
| SYN-DIGITSUM-0005 / R24-b923e2bf03 | f1b77f2f9b01 / C | ST | ∅ | ∅ | ∅ | HC | valid / 1 | ∅ / HC / ST | X |
| SYN-BASE2-0004 / R24-5a306bfa2c | b37a5e03fbeb / C | ST | ∅ | ∅ | ∅ | BD | valid / 1 | ∅ / BD / ST | X |
| SYN-SUMEVEN-0007 / R24-607443dcd5 | e167d1d3ec14 / D | ST | ∅ | ∅ | LG | LG | valid / 1 | ∅ / LG / ST | X |
| SYN-FACT-0003 / R24-5026bf6100 | dfd69e4a39c4 / D | ST | ∅ | ∅ | LG | ∅ | valid / 1 | ∅ / ∅ / ST | P |
| SYN-DIGITSUM-0011 / R24-bc45f55f2b | 79cb238393ef / C | LG | ∅ | LG | LG | HM | valid / 1 | ∅ / HM / LG | P |
| SYN-SUMEVEN-0016 / R24-51e82fa8cf | bb744689e3ba / D | LG,VL | ∅ | LG | LG | LG | valid / 1 | LG / ∅ / VL | P |
| SYN-FACT-0007 / R24-1b1380ba32 | 27290fbbe31a / D | LG | ∅ | LG | LG | LG | valid / 1 | LG / ∅ / ∅ | P |
| SYN-BASE2-0010 / R24-df97396caa | 7b1090cc74f6 / C | LG | ∅ | NX | HM | NX | valid / 1 | ∅ / NX / LG | P |


### First raw taxonomy R15 và retry/fallback

| Source | First raw L1 / L2 / L3 | Calls L1/L2/L3 | Fallback L1/L2/L3 |
| --- | --- | --- | --- |
| EX01-S101 | ∅ / BD / BD | 1/2/1 | 0/0/0 |
| EX01-S103 | ∅ / BD / BD | 3/1/1 | 1/0/0 |
| EX01-S105 | ∅ / BD / BD | 1/2/1 | 0/0/0 |
| EX01-S107 | ∅ / BD / BD | 1/1/1 | 0/0/0 |
| EX01-S113 | ∅ / BD / BD | 3/1/1 | 1/0/0 |
| EX01-S115 | ∅ / BD / BD | 1/1/1 | 0/0/0 |
| EX02-S202 | ∅ / ∅ / ∅ | 1/1/1 | 0/0/0 |
| EX02-S203 | ∅ / HM / LG | 1/1/1 | 0/0/0 |
| EX02-S205 | ∅ / LG / LG | 1/1/1 | 0/0/0 |
| EX02-S207 | ∅ / LG / LG | 1/1/1 | 0/0/0 |
| EX02-S209 | ∅ / LG / LG | 3/1/1 | 1/0/0 |
| EX02-S216 | ∅ / LG / LG | 1/1/1 | 0/0/0 |
| SYN-DIGITSUM-0005 | ∅ / ∅ / ∅ | 1/1/1 | 0/0/0 |
| SYN-BASE2-0004 | ∅ / ∅ / ∅ | 1/1/1 | 0/0/0 |
| SYN-SUMEVEN-0007 | ∅ / ∅ / LG | 1/1/1 | 0/0/0 |
| SYN-FACT-0003 | ∅ / ∅ / LG | 1/1/1 | 0/0/0 |
| SYN-DIGITSUM-0011 | ∅ / LG / LG | 1/1/1 | 0/0/0 |
| SYN-SUMEVEN-0016 | ∅ / LG / LG | 1/1/1 | 0/0/0 |
| SYN-FACT-0007 | ∅ / LG / LG | 1/1/1 | 0/0/0 |
| SYN-BASE2-0010 | ∅ / NX / HM | 1/1/1 | 0/0/0 |


## Review bằng chứng và quyết định gate

Đã review toàn bộ **26 emitted labels: 9 TP + 17 FP theo gold gốc**. Casebook riêng `casebook.private.json` giữ exact source/statement excerpts, line spans, source hash, đánh giá và rationale; excerpts nằm trong ignored outputs. Bảng dưới chỉ tóm tắt vị trí và nhận định; không sửa prediction model hoặc gold. TP theo gold có thể vẫn có taxonomy-boundary disagreement với provisional agent mapping.

| Source | Nhãn | Gold | Dòng code | Agent assessment / căn cứ |
| --- | --- | --- | --- | --- |
| EX01-S101 | Lỗi biên dịch | FP | [80, 104] | unsupported_context: Allocation/count and deletion defects are runtime/logic issues; omitted prob3 may depend on harness linkage. Compiler evidence is unknown; no specific language error establishes this label. |
| EX01-S103 | Lỗi biên dịch | TP | [19, 29] | supported_static: Missing struct terminator plus incompatible pointer/object assignment and undeclared identifier establish language errors statically; no compiler execution claimed. |
| EX01-S103 | Lỗi nhập/xuất | FP | [31, 42] | gold-disagreement: P1 inserts into the file stream instead of reading required General records and returns null. Original gold omits input/output; agent mapping also supports it. |
| EX01-S103 | Lỗi logic | FP | [31, 42] | gold-disagreement_boundary: Required record construction is absent and P1 returns null; a functional defect is real, but logic vs input/output/function naming remains disputed. |
| EX01-S105 | Lỗi biên dịch | FP | [29, 34] | disputed_context: Variable-length automatic arrays are outside standard C++11 but g++ can accept extensions; functions-only submission omits main by requirement. No compiler evidence or specific guaranteed rejection is available. |
| EX01-S105 | Lỗi logic | TP | [79, 102] | supported_static: Uninitialized node pointer is dereferenced; temp remains null on first list iteration and is dereferenced. Original logic label has source support. |
| EX01-S107 | Lỗi biên dịch | FP | [122, 164] | unsupported_context: Nonadvancing pointer loop, era arithmetic and null-tail access are functional/runtime defects. No visible syntax error or compiler result establishes compilation failure. |
| EX01-S107 | Lỗi logic | TP | [122, 133] | supported_static: Age uses absolute year difference without BC/AD adjustment, and the list cursor never advances; compare explicit oldest-general/era requirement. |
| EX01-S113 | Lỗi biên dịch | FP | [133, 164] | unsupported_context: Missing required problem implementations and incomplete field parsing are source defects; this file retains main and no specific syntax/type failure is established. |
| EX01-S113 | Lỗi logic | FP | [45, 79] | gold-disagreement_boundary: The row helper declares j but tests/increments i and only counts when i equals fixed j; behavior fails row selection. Logic vs loop naming is disputed; original gold only function. |
| EX02-S203 | Lỗi hàm | FP | [11, 32] | gold-disagreement_boundary: sum has only a block-scope declaration in ts and is called from main; ts also recurses on consumed input. Defects are real, but function vs compilation label is disputed. Candidate misses original compilation label. |
| EX02-S203 | Lỗi logic | FP | [14, 26] | gold-disagreement: The digit-power expression multiplies digit by count rather than exponentiation required by Armstrong statement. Syntax errors coexist; original gold only compilation. |
| EX02-S205 | Lỗi nhập/xuất | TP | [30, 38] | supported_static: Both answer branches print a leading space instead of the required exact True/False token. |
| EX02-S205 | Lỗi logic | FP | [3, 28] | gold-disagreement_conditional: For ordinary 32-bit int, valid 999999999 gives digit-power sum 3486784401 > 2147483647. Exact target width is not provided; retain conditional/domain dispute instead of assuming a new compiler finding. |
| EX02-S207 | Lỗi logic | FP | [3, 11] | gold-disagreement: Inner y shadows the accumulator and initializes from itself; returned outer y is not updated. Final provisional agent reference says logic; original gold says algorithm. |
| EX02-S209 | Lỗi logic | TP | [14, 23] | supported_static: temp and count are read without initialization and temp never receives n. |
| EX02-S209 | Lỗi vòng lặp | TP | [14, 23] | supported_static: Digit-count loop takes remainder instead of removing a digit, preventing progress for nonzero terminal digit; this is a newly recovered gold TP. |
| EX02-S216 | Lỗi logic | TP | [29, 35] | supported_static: Repeated squaring computes digit raised to 2^t instead of digit raised to t required by Armstrong definition. |
| EX02-S216 | Lỗi mảng/chuỗi | FP | [21, 27] | gold-disagreement: Array has nine entries, while permitted n=1000000000 has ten digits; index 9 is written. Supported by final provisional agent mapping, absent from original gold. |
| SYN-DIGITSUM-0005 | Lỗi hard-code | FP | [3, 16] | unsupported: Computation reads n, repeatedly extracts its digits, and prints the computed sum. Scratch constants are commented out; no hard-coded answer or special-case substitution is present. Unbounded numeric domain remains a separate dispute. |
| SYN-BASE2-0004 | Lỗi biên dịch | FP | [1, 18] | unsupported: Required headers, valid char/string operations, helper and main are present. Static source provides no compilation defect. No fresh compiler evidence was added. Unbounded numeric domain does not establish a compilation failure. |
| SYN-SUMEVEN-0007 | Lỗi logic | FP | [3, 17] | gold-disagreement_conditional: Ordinary inputs sum even numbers correctly. Unbounded statement permits n>100 (array overflow) and, on 32-bit int, two even 2147483646 values overflow the sum. Functional/category mapping remains disputed, so do not treat this source as verified clean. |
| SYN-DIGITSUM-0011 | Lỗi hàm | FP | [18, 20] | gold-disagreement_boundary: main performs no input, helper call or output. A defect is real, but function vs input/output naming differs from the provisional agent reference and original logic gold. |
| SYN-SUMEVEN-0016 | Lỗi logic | TP | [15, 26] | supported_static_boundary: The input index never advances and summation/output are unreachable for positive n. Original gold includes logic; provisional mapping prefers loop only. Keep both authorities separate. |
| SYN-FACT-0007 | Lỗi logic | TP | [20, 22] | supported_static_boundary: main returns without reading, invoking factorial helper, or printing. Original gold calls this logic; provisional mapping calls it input/output. TP under original gold only. |
| SYN-BASE2-0010 | Lỗi nhập/xuất | FP | [16, 18] | gold-disagreement: main immediately returns, so required input and binary output never occur. Provisional agent mapping supports input/output; original gold says logic. |


- So L2: thêm 4 TP (EX01-S105 logic, EX01-S107 logic, EX02-S205 nhập/xuất, EX02-S209 vòng lặp), mất 1 TP (SYN-DIGITSUM-0011 logic); thêm 9 FP, bỏ 1 FP (EX01-S115 biên dịch). Có lợi ích source-supported thực, không chỉ gắn nhãn trên một source thiếu căn cứ. Tất cả FP vẫn tính đủ trong gold metrics kể cả gold-disagreement.

- Gate 1/2 đạt: 20 valid; micro-F1 0,352941 > 0,300000; EM 3 = 3. Gate 4 đạt về việc có TP mới có căn cứ, với chi phí FP đã công khai.

- **Gate 3 không đạt**: nhãn chức năng không có căn cứ lặp lại mới ở SYN-DIGITSUM-0005 (hard-code) và SYN-BASE2-0004 (biên dịch), đều rỗng ở R15 L2. Đây là nhận định source review theo điều kiện đã khóa, không phải đặt thêm ngưỡng số mới sau kết quả. Không coi SYN-SUMEVEN-0007 là clean để tăng số lỗi giả: domain/capacity của nó vẫn disputed.

- First attempt mới: 4 object hợp schema, 16 array không hợp schema. Một retry định dạng cho mỗi array, tất cả thành valid. Có 9 source đổi tập nhãn trong retry định dạng; không có semantic retry do runner yêu cầu, nhưng model tự đổi nội dung. Ví dụ nguyên văn ngắn: SYN-BASE2-0004 first raw `[]`, final `{"taxonomy_error":["Lỗi biên dịch"]}`; SYN-DIGITSUM-0011 first raw `["Lỗi logic"]`, final `{"taxonomy_error":["Lỗi hàm"]}`. Không chấm array như object hợp lệ và không thay final bằng first attempt để lấy điểm tốt.

- Dùng chung taxonomy làm biến thiên giữa projection bằng 0/20 **theo construction**, không phải ba lần dự đoán độc lập chứng minh model ổn định. ∅ trên source gold không rỗng giảm 16/20 ở L1 xuống 1/20, nhưng precision so L2 giảm; chưa chứng minh giữ độ chính xác.

- **Không thực hiện bước feedback**: 0 feedback calls, không output feedback thử nghiệm hoàn chỉnh. Không chạy submission validator trên taxonomy-only projections vì thiếu feedback có chủ đích; không gọi schema-valid là chứng cứ nội dung đúng. Không có bảng feedback giả, placeholder hoặc fallback mới.

## Chi phí, kiểm thử và review code

- Taxonomy: 36 model calls / 20 source, 16 schema retries, 0 invalid sau retry, 0 runtime error, 0 fallback. Generated tokens 598, tổng input tokens qua calls 33920, tổng generation latency 10.798270 s; load latency 8.572231 s. Không đo riêng tổng wall-clock end-to-end.

- VRAM peak allocated 7071596544 bytes (6.586 GiB); peak reserved 7205814272 bytes. Qwen storage chứa float16 nonquantized parameters + uint8 packed weights; BF16 là compute dtype của NF4, không khẳng định toàn bộ storage BF16.

- R15 đối ứng: 68 calls sinh taxonomy + feedback cho 60 ID, 4051 generated tokens, 102.204051 s generation latency từ raw journal. So 36 taxonomy-only calls với 68 joint calls không phải cost benchmark end-to-end của hai hệ thống hoàn chỉnh; không có phép đo feedback pipeline mới.

- TDD: 22 test mới thất bại trước implementation, sau đó 22/22 qua. Tổng targeted regression: **126 passed**, gồm source/hash/ID mapping, một prediction cho ba Level, actual-render allowlist, invalid không thành ∅, nhãn/key/schema, bound retries, chống rerun, gate so sánh nghiêm ngặt; cùng audit/metrics và R15 parser/runner/disclosure tests. Mock/scripted outputs trong test chỉ là fixture, không phải model measurements.

- Không chạy toàn bộ suite ngoài phạm vi. Test feedback-packaging có điều kiện không áp dụng vì không chạy feedback; guard R15 được giữ nguyên và regression guard Levels 1/2 đã chạy. Không có kết luận mới về Level 2 feedback chất lượng hoặc chỗ guard bỏ sót từ thí nghiệm taxonomy-only.

- Áp dụng skills using-superpowers, brainstorming, test-driven-development, verification-before-completion và requesting-code-review. Một agent reviewer độc lập chỉ đọc ba file code/test, không đọc dữ liệu hoặc outputs, chạy 22 test và không sửa file. Đây là agent review, không human verification.

- Reviewer ghi hai giới hạn ngoài đường chạy thực tế: audit này không hỗ trợ tổng quát baseline có last raw unparseable kèm fallback (Round24 thực tế mọi last raw đều parse được); seal runtime liệt kê selected implementation files, chưa tự kiểm toàn dependency graph. Không sửa code/design đã khóa sau khi xem output. Postrun integrity đối chiếu mọi tracked Python module trong src/task3, src/synth, src/utils với HEAD đầu; tất cả khớp. Official label-space files đã nằm trong pre-inference seal. Đây là chứng cứ code không đổi trong run hiện tại; hardening cho thí nghiệm sau còn để ngỏ.

## Tái hiện và bàn giao

Chạy từ `/workspace/llm-final-project`, dùng `.venv-task3/bin/python`. Lệnh thực tế:

```bash

.venv-task3/bin/python scripts/task3_level_blind.py --phase audit

.venv-task3/bin/python -m pytest tests/test_task3_level_blind.py tests/test_task3_round24_review.py tests/test_task3_round24_audit.py tests/test_task3_round15.py tests/test_task3_round15_runner.py tests/test_task3_round15_disclosure.py -q

.venv-task3/bin/python scripts/task3_level_blind.py --phase freeze

.venv-task3/bin/python scripts/task3_level_blind.py --phase verify

.venv-task3/bin/python scripts/task3_level_blind.py --phase taxonomy

.venv-task3/bin/python scripts/task3_level_blind.py --phase score

```

Không chạy lại inference ở handoff hiện có: started.json chặn rerun. `verify`/`score` là replay offline không gọi model. Một xác nhận model mới phải là thí nghiệm được khóa riêng; không xóa marker hoặc đổi folder để thử prompt lần hai trong lượt này.

- Code mới: `src/task3/level_blind.py`, `scripts/task3_level_blind.py`. Test mới: `tests/test_task3_level_blind.py`. Report: file này. Raw/code/prompt/attempts/evidence/reviews và handoff đều ở ignored `outputs/task3/level-blind-20261022/`.

- R15 config và submission không được sửa, không stage artifact private, không inference public, không tạo 328-ID candidate, không upload, push, clone, worktree, đổi gold/split/generator hoặc huấn luyện. Hash đầu vào/baseline được kiểm lại sau run. Git diff/status và staged paths được kiểm trước commit.

- Nếu cần kiểm khả năng tổng quát hóa: chỉ đề xuất một split train-only mới theo source/family độc lập, khóa trước một lượt xác nhận khác. Chưa tạo hoặc chạy split đó. Không suy offline F1 thành điểm leaderboard.

## Input và baseline SHA-256

Các hash sau được ghi trong manifest trước inference. Full per-source text/raw-code hashes, provenance và exact 60 query IDs nằm trong manifest/audit riêng; bảng source ở trên chỉ rút gọn hash.

| Artifact trong repository | SHA-256 |
| --- | --- |
| configs/task3/r15_common.yaml | 74b3f89076843c25aae75756bc3aa177565f123c17ca642e3ea4a53c3057c5c2 |
| configs/task3/r15_selected.yaml | 04de3a280eff7448f93ef58b85a0241caaf3bd0bbfa873b7da1258cf15f2dfaa |
| configs/task3/r15_zero_shot.yaml | 846defe2e2e63b441ef264c7eca7dd7b20d1476af24d4e4c1c7d3f30bd3edae8 |
| data/processed/task3/real-train.jsonl | 12f2e897c1e374233754bec187de87c903f2142a582e6ad5eb72b81c9f58b1b4 |
| data/processed/task3/synthetic-train.jsonl | 27a00fddb3bf17b0ee6af7ebaac14ffdf3deb6bdc98ebc57233d6cf7aac789e4 |
| data/raw/sample_dataset/label_space.json | 2e21d225a20609c3adac8c0c95110d08c18dc8982d083879b8029fea2286c715 |
| data/raw/sample_dataset/submissions/EX01/EX01-S101.cpp | e66ff20525bb9236e194cc863f2e407278b951ee4b3a69c1c61112ddaae1d6f7 |
| data/raw/sample_dataset/submissions/EX01/EX01-S103.cpp | 2773a782ad88b8a3411f0a29b3adda7c736b17803804113b6a2d510a53902860 |
| data/raw/sample_dataset/submissions/EX01/EX01-S105.cpp | 24585a3812d36738e66445004d202f3c322eeb1f63a226a0ebec9c1ee4b1a815 |
| data/raw/sample_dataset/submissions/EX01/EX01-S107.cpp | 396f6fedbfdd81bc07841fd353436827613cdc82024feb59cda2f619301c3c03 |
| data/raw/sample_dataset/submissions/EX01/EX01-S113.cpp | 4893932d2266c2a23eb7582bad6919aee588e46ddfff4bdb3631ae969cb1e4e8 |
| data/raw/sample_dataset/submissions/EX01/EX01-S115.cpp | cd348457aa46c424bcd0eb84c05b0fc51609b2ed4e85b36c32c75a4df9cf5160 |
| data/raw/sample_dataset/submissions/EX02/EX02-S202.cpp | 504cf40dead51dec4e7114db44cab3000c1f496d76ffa987aef2298cfc55fecf |
| data/raw/sample_dataset/submissions/EX02/EX02-S203.cpp | 2ec0c125df370e31012de7f9b56e9f73f0cc96ee920ee3956b51fa010954fcf7 |
| data/raw/sample_dataset/submissions/EX02/EX02-S205.cpp | b4c902c4f28d6d8b1be793c8851478484f980d9d384875a1251c1ee0da1eb68f |
| data/raw/sample_dataset/submissions/EX02/EX02-S207.cpp | 8e158849bc4a10c7aefccdc7bb4834a49973f66aa4c4ee42ef8a6b009089d993 |
| data/raw/sample_dataset/submissions/EX02/EX02-S209.cpp | 34daa7a893b52eb1ee7a9b95621b30777265cb449829ee382b9e81d9464c548d |
| data/raw/sample_dataset/submissions/EX02/EX02-S216.cpp | 1cd8312126d13cc4f9f75943a324f000f3bdbddec0bc2564cb500cb1889be9ba |
| data/raw/sample_dataset/task3_feedback.json | d27118a81b0723bc68aecb7c4cf4096d3f6712a85dc938ef39ba57fe71d2c47e |
| data/synth/generate-dataset/label_space.json | 056a4d1a0ccfd60688b43efdf5df64a4c1310e3c6f1d99ab813691a2da27a9dc |
| data/synth/generate-dataset/submissions/SYN-BASE2/SYN-BASE2-0004.cpp | b37a5e03fbebc3a889692ed6611f2516ab59ffb9e9b94efd482f46470c527dbe |
| data/synth/generate-dataset/submissions/SYN-BASE2/SYN-BASE2-0010.cpp | 7b1090cc74f616e086c5aaec214b9b6068b2d089117ffe21908825c18279f0de |
| data/synth/generate-dataset/submissions/SYN-DIGITSUM/SYN-DIGITSUM-0005.cpp | f1b77f2f9b0170793cfb0378c26e51b7e2a4429c314f2d07a86dbea852a6e746 |
| data/synth/generate-dataset/submissions/SYN-DIGITSUM/SYN-DIGITSUM-0011.cpp | 79cb238393ef30a9d8706cabf82a8256e65730fae33a9850bf52a58abcf50ae0 |
| data/synth/generate-dataset/submissions/SYN-FACT/SYN-FACT-0003.cpp | dfd69e4a39c4123759db1b4e9385a497956c64f2fdf2c5ab29b831e1f1f2ebcf |
| data/synth/generate-dataset/submissions/SYN-FACT/SYN-FACT-0007.cpp | 27290fbbe31a1ac5569a134edd9bc4290119ff93df09faaf1931b473cec38278 |
| data/synth/generate-dataset/submissions/SYN-SUMEVEN/SYN-SUMEVEN-0007.cpp | e167d1d3ec146bbf0376b087d9fd04bb9ea1555615dca2111ebe81ead5da7f41 |
| data/synth/generate-dataset/submissions/SYN-SUMEVEN/SYN-SUMEVEN-0016.cpp | bb744689e3bae87bf074d5d0e68c82b991e63f46715ee49728b54db8080728cb |
| data/synth/generate-dataset/task3_feedback.json | 122d3736634394741ea8eaddb89dd1f068e4d23cd037f380a94c35b67f04bf4f |
| outputs/task3/level-blind-20261022/audit.private.json | 2a5f24eb26b0b8f706ba24ce9f017af0d75735136c6ecdee57783c108bc32325 |
| outputs/task3/level-blind-20261022/rendered-prompts.private.json | 61c0f2b4abf303a783049f8f8145a250c15f7e82c464b8dedbc7d601822b5397 |
| outputs/task3/round24-20261022/R15/attempts.jsonl | 527dc867d6dc2f6f1ea5d41091be6e5502e39615d54a13f19f4a7bbf217287c3 |
| outputs/task3/round24-20261022/R15/decisions.jsonl | b1ee060447238de40f3f8c3054e783280a72ca17e70050c731e9242b5865cc9d |
| outputs/task3/round24-20261022/R15/predictions.json | 8297343687469d6026374052f1b0bc509a3bc40124eb23f622cc9145184a0211 |
| outputs/task3/round24-20261022/R15/progress.json | 6d99fa364311f3ff54e66c87eab3d4a5b7993db3fdca9c4dec878a997196f3c8 |
| outputs/task3/round24-20261022/R15/run.json | effb2afbe09840495ed7123855c8614c722e8adc8c02908818fdc429b6198ea8 |
| outputs/task3/round24-20261022/R15/traces.json | c1e72207489b5bd487661d1e74d33caf2f72082b570ad77879cbf56cdc9f161c |
| outputs/task3/round24-20261022/history-dedup.private.json | 2a2ed45ead081969d571ca2c737bd7817b87ad2fb0bc953bec78f0f644196942 |
| outputs/task3/round24-20261022/human-decisions.private.json | 37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570 |
| outputs/task3/round24-20261022/model-inputs.private.json | a1a2a1a9d876db24fca08046b73ca636530cc90d889eb73c85e3e9bbd2f605c1 |
| outputs/task3/round24-20261022/protected-before.private.json | 8df4b093b72e99fc5daf3311112f45b4ed194126398d46ee89202dc86541dcd1 |
| outputs/task3/round24-20261022/reference-rulebook-v2.private.json | bf99492ed6f079e390829bec658db151737aa75f5189137bc0f51bf14980c8e2 |
| outputs/task3/round24-20261022/reference.private.json | e1717b40104b2be8a2cf0d3200c4895bf8f292c390b0602f542fcbd78db8e71a |
| outputs/task3/round24-20261022/selection-freeze.json | 8fd6a2966fc7c2a0c37fb871c22dda22f82beae63be3fa3de867406566a6c0d8 |
| outputs/task3/round24-20261022/sources.private.json | b401eeb9b7066a022603d58244976d7dcc913229d6bf8542401ff32b2c84ce29 |
| scripts/task3_level_blind.py | 31c3d2b40177c2101ed0f8aaa53dd481dad0b71aed4e51c8175e65b18ecbf753 |
| src/task3/inference.py | 84c4b0166dfcadc1d79aba365ed9dba84058e55954c459f6f4eb3724c452eea2 |
| src/task3/level_blind.py | 0f89ff8b6840d673b74ed36d1b67aeee85460eb98deacf268f12d72db17d3bf2 |
| src/task3/round15.py | 9f367db21ee0bffba82a56950734e830606b52fafa32b70f4f8312e6492c3f9c |
| src/task3/round15_disclosure.py | 3b8a7009c491e4def66ee63f849c15580842b88fcdc74315324e81798496e941 |
| src/task3/round24_review.py | c762912f6dabe19a0cb7b9d69ceba9b88fccfa28ff40e059fcae9436846f68f1 |
| tests/test_task3_level_blind.py | 085096b96ff96d174e1c5f58c9143333d99511c084eefcce0c8c9c2cb415b64a |


## Giới hạn và kết luận

Dữ liệu đã được xem nhiều vòng; ranh giới confirmation không còn độc lập. Nhiều gold-disagreement và 13 disputed source khiến gold-F1 không tự chứng minh nội dung kỹ thuật đúng. Gold và nhãn tham chiếu gốc giữ nguyên; provisional agent mapping chỉ là sensitivity, không nâng thành human verified. Chỉ một prompt/lượt, không có kiểm định độc lập hoặc CI đáng tin từ 20 source tương quan.

Giả thuyết giảm bỏ nhãn L1 có tín hiệu hỗ trợ trong thí nghiệm này, nhưng giả thuyết đầy đủ “khắc phục bỏ nhãn mà vẫn giữ độ chính xác” **chưa đủ bằng chứng**: schema retry nhiều, precision giảm, FP mới không có căn cứ và synthetic/confirmation không nhất quán. Quyết định: **GIỮ R15; không chạy bước feedback hoặc public**.
