# Task 3: hai prompt tuần tự — development 2026-10-23

**Giữ R15; dừng sau development.** Hai bước hoàn tất 16/16 mẫu, nhưng micro-F1
giảm 0,3200→0,2857, macro-F1 đủ 10 nhóm giảm 0,1400→0,1133; strict joint vẫn
2/16. Không chạy evaluation lớn hơn, public inference, oracle, candidate 328 ID,
upload, push hoặc PR. Đây là phép thử prompting với taxonomy **dự đoán**.

Số liệu máy đọc: [TASK3_TWO_PASS_METRICS_20261023.json](TASK3_TWO_PASS_METRICS_20261023.json).
Raw source, prompt, response, note, review và trace chỉ nằm trong thư mục ignored
`outputs/task3/two-pass-20261023/`; không đưa vào Git.

## Implementation và bản đóng băng

Branch `feat/task3-quality-round5`, HEAD ban đầu
`21400d0c936d2af62ff404a0b526d4b600d3278c`, working tree ban đầu sạch.
Chỉ thêm file cho thí nghiệm này; không sửa R15, dữ liệu, split, gold hoặc artifact cũ.

- [two_pass.py](../../src/task3/two_pass.py): một prompt taxonomy+issues ngắn,
  một prompt feedback; chỉ parse JSON/type/10 nhãn chính thức. Không semantic gate.
- [task3_two_pass.py](../../scripts/task3_two_pass.py): freeze/verify/run,
  load tokenizer/model một lần; một ID tại một thời điểm; taxonomy→feedback→save.
- [config](../../configs/task3/two_pass_20261023.json): một cặp prompt duy nhất,
  concurrency 1, tối đa hai generate/ID, không retry hay reviewer trong inference.
- [task3_two_pass_report.py](../../scripts/task3_two_pass_report.py): packet mù,
  seal, attribution, metric offline cho lần chạy hoàn chỉnh này; không generate.
- [tests runner](../../tests/test_task3_two_pass.py) và
  [tests report](../../tests/test_task3_two_pass_report.py): dữ liệu nhân tạo.

Stage1 không nhận Level/gold/teacher/reviewer. Stage2 nhận lại đúng đề/code/evidence,
taxonomy+issues thực tế của stage1, requested Level và định nghĩa chính thức của
riêng Level đó. Không có lịch sử hội thoại chung hoặc ví dụ của ID khác. Final giữ
nguyên taxonomy stage1; prompt feedback chỉ được trả trường feedback.

Reservation ghi và fsync **trước** generate, raw response ghi trước parse.
Resume chỉ đọc lại response có sẵn; reservation bị gián đoạn không được generate
lại. Parse lỗi stage1 bỏ stage2, parse lỗi stage2 unresolved; không đổi thành []
hoặc feedback mẫu. Hybrid được hỗ trợ bằng toàn bộ cặp R15 cho ID unresolved,
ở file riêng theo quy tắc cố định; lần chạy này không cần tạo hybrid.

Qwen/Qwen2.5-Coder-7B-Instruct, revision
`c03e6d358207e414f1eca0bb1891e29f1db0e242`, giống R15: NF4 double quant,
BF16 quantized compute, seed42, greedy, zero-shot, context16384, tối đa1024 output
tokens và45 giây/generate. Không fine-tune. Runtime xác nhận 4-bit trên CUDA,
compute BF16; các tensor không quantize lưu FP16. Peak GPU allocated6.648 GB,
reserved7.816 GB; load16,768 giây. Không đổi model hay precision giữa A/B.

Tokenizer `Qwen2TokenizerFast`, cùng revision; chat-template SHA256
`cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`.
Prompt version `two-pass-v1-20261023`, prompt-bundle SHA256
`be1d68524ac515d84335c86ee7b30b136def791f8b97bb1e4f577e67bc34bbf8`;
config SHA256 `779219ada49ae023c80b39f125fd59aa35f5781e76f5695cc7f669c6ebc4bb59`.
Freeze SHA256 `cfc9e591bd5bf2467df4f5cbb3fb9d2bae993b7f6a93f753b06234f6bd3447ec`.
Không sửa prompt/config/core sau freeze hoặc thử cặp prompt thứ hai.

## Tập development và đối chứng

Khóa16 ID trước viết prompt/generate: L1/L2/L3=5/5/6, L4=0;14 single-problem,
2 multi-problem;4 bài clean theo gold gốc, có support của đủ10 nhóm. Cả16 là
synthetic nội bộ **đã được xem ở vòng trước**, không phải tập đánh giá mới:
3 từ development8 của grounded/compact,13 từ evaluation60 cũ, nay dùng development.
Manifest từng ID, split cũ, source hash và mức exposure có trong JSON metrics.
Không dùng public để chọn ID, prompt, ngưỡng hoặc đánh giá chất lượng.

TRAIN style references chỉ xem độ dài/giọng của EX02-S202 (L1,4 ký tự),
EX01-S101 (L2,137), EX02-S203 (L3,73). Không chèn verbatim teacher feedback;
định nghĩa Level chính thức được ưu tiên khi ví dụ TRAIN diễn đạt chưa đúng Level.
Không đưa gold của ID đang chấm vào production.

Units SHA256 `6641bbea8f1d721f97915b8a5e126afd8dff818d0bcd57b7be1e1f69e6d5ab4d`;
selection-seal `38bbd7dd80572c5d6b57164665a78bbd77d39fc754e55684fc864f7573887c05`.
A là cặp R15 zero-shot có sẵn trên **cùng16 ID**, remap request_id về sample_id
bằng manifest; trace của cả16 xác nhận mỗi ID một generate, không fallback.
Không chạy lại A:0 fresh calls. Control SHA256
`f0e62cb2a74b97f5ab5eaed76c749535588a3d519721ce0bdf0e2c456232a4e3`.

## Completion và taxonomy

| Chỉ số, mẫu số16 | A: R15 | B: hai bước |
|---|---:|---:|
| Complete / unresolved / fallback |16 /0 /0|16 /0 /0|
| Model calls trên trace |16 lịch sử|32 mới|
| JSON/type/enum parse thành công |16 cặp|16 stage1 +16 stage2|
| Micro-F1, gold gốc |0,3200|0,2857|
| Macro-F1, đủ10 nhóm |0,1400|0,1133|
| Exact match |5/16 (31,25%)|5/16 (31,25%)|
| TP / FP / FN |4 /5 /12|4 /8 /12|
| Taxonomy [] |7/16|4/16|
| False-clean theo gold gốc |4/16|1/16|
| Strict joint |2/16 (12,5%)|2/16 (12,5%)|

Trace xác nhận thứ tự đúng16 cặp taxonomy→feedback; mỗi generate chỉ một ID,
không call thứ ba, retry, guard, semantic rejection hoặc label mutation. Không
loại mẫu nào khỏi mẫu số. Metric dùng nguyên gold gốc; zero-support F1 quy ước0
và macro luôn chia10. Support là số ID mang nhãn, không phải số ID clean/error.

| Nhóm chính thức | Support | A TP/FP/FN | A F1 | B TP/FP/FN | B F1 |
|---|---:|---|---:|---|---:|
|Lỗi biên dịch|2|2/0/0|1,0000|2/1/0|0,8000|
|Lỗi nhập/xuất|2|0/0/2|0|0/0/2|0|
|Lỗi logic|3|2/5/1|0,4000|2/7/1|0,3333|
|Lỗi vòng lặp|2|0/0/2|0|0/0/2|0|
|Lỗi mảng/chuỗi|2|0/0/2|0|0/0/2|0|
|Lỗi hàm|1|0/0/1|0|0/0/1|0|
|Lỗi edge case|1|0/0/1|0|0/0/1|0|
|Lỗi thuật toán|1|0/0/1|0|0/0/1|0|
|Lỗi hard-code|1|0/0/1|0|0/0/1|0|
|Lỗi style|1|0/0/1|0|0/0/1|0|

Stage1 B chỉ phát hai nhóm biên dịch/logic; giảm false-clean chưa giải quyết
việc gom nhiều nhóm khác thành logic. Có11/16 taxonomy không exact theo gold gốc.
Sensitivity với source-only reviewer A, không thay gold: A/B micro-F1
0,3846/0,3448; macro0,1545/0,1262; exact5/16 và6/16. Xu hướng giảm F1 vẫn còn.

## Review nguồn trước, output mù sau

Reviewer A khóa source-only16 trước output/gold; B khóa8 gồm toàn bộ5 L2
và3 L3. Sau đó nhận32/16 output ẩn tên nhánh, thứ tự cặp xáo cố định.
B đọc nguồn thêm3 ID disputed/borderline rồi mới nhận6 output bổ sung:
DISTINCT-0001, FACT-0001, SUMB-0005. Tổng11/16 ID được hai reviewer kiểm tra;
5 còn lại chỉ reviewer A. Notes stage1 được mở cho attribution **sau** seal
paired review. Reviewer là Codex agent, chưa được con người xác minh; không
tham gia inference, không chạy code sinh viên. Không dùng gold làm bằng chứng nguồn.

Chấm main defect, từng nhận định, consistency, Level, L2 leak, L3 actionable,
Vietnamese và genericness riêng. L1 cảnh báo chung có căn cứ có thể đạt Level;
riêng câu placeholder đứng một mình bị loại theo yêu cầu người dùng. L2 mô tả
token đang sai không tự động là leak. Strict joint cần output complete, taxonomy
exact theo nguồn, không source dispute, main covered, không false claim, nhất
quán, đúng Level, tự nhiên và không generic/placeholder; chỉ nhận credit khi các
reviewer có mặt đồng ý. Không adjudicate bằng cách sửa gold.

| Mẫu số theo Level | Đúng Level A→B | False claim A→B | Feedback pass A→B | Strict joint A→B |
|---|---:|---:|---:|---:|
|L1,5|5→1|3→3|0→0|0→0|
|L2,5|3→3|3→4|2→1|1→0|
|L3,6|3→4|5→3|1→3|1→2|
|Tất cả,16|11→8|11→10|3→4|2→2|

Main covered7→8/16, consistent15→11/16, supported claims4→6/16;
Vietnamese tự nhiên15→15/16. Generic-only theo reviewer3→1; B còn thêm một
placeholder-only ở UPPER-0005, nên không nhận feedback-pass cho mẫu đó.
L3 actionable2/4 bài có lỗi ở cả A/B (2/6 nếu lấy toàn bộ L3, hai bài nguồn
clean không cần hướng sửa). Hướng sửa đúng không bù cho taxonomy thiếu nhóm.

L2 A có1/5 repair leak được cả hai reviewer xác nhận. B có0/5 leak **đồng thuận**,
nhưng1/5 bị một reviewer đánh leak và reviewer kia đọc như chẩn đoán (REVSTR-0007).
Giữ case đó disputed và không cấp credit; không quảng bá B là đã loại sạch leak.
Attribution A cũng đánh1 leak, cùng case; đây không phải một case bổ sung.

Bất đồng nguồn: DIGITSUM-0007, A gọi logic, B gọi logic+hàm; gold gốc là hàm.
DISTINCT-0001 thiếu giới hạn n trong đề: A giữ rủi ro vượt capacity là disputed,
B coi thuật toán đúng trong capacity; không bỏ ID hoặc sửa gold clean.
Gold/source-A khác ở4 ID: BASE2-0007, DIGITSUM-0007, SUMB-0005, DISTINCT-0001.
Các bất đồng output ở PALIN, REVSTR, DISTINCT-0017, MINA, DISTINCT-0001,
FACT-0001 được giữ trong per-ID JSON; A-only joint3/16 cho cả A/B, conservative2/16.

## So sánh từng ID

Tên nhãn viết gọn trong bảng: BD=biên dịch, IO=nhập/xuất, LG=logic,
VL=vòng lặp, MC=mảng/chuỗi, H=hàm, E=edge case, TT=thuật toán,
HC=hard-code, S=style. Đều ánh xạ nguyên văn10 nhóm ở bảng trên.
J là strict joint; nhận xét được diễn giải, không chép raw output/code.

| ID (SYN-) | L | Gold gốc | A→B taxonomy | J A→B | Thay đổi nội dung/Level |
|---|---:|---|---|---|---|
|COUNTVOWEL-0010|3|BD|BD→BD|0→1|B nhận đúng lỗi kết thúc khai báo; A chỉ nghi ngờ chung.|
|PALIN-0017|3|LG,IO|LG→LG|0→0|B đề xuất khởi tạo sai; cả hai thiếu IO, wording A còn disputed.|
|UPPER-0005|1|MC|[]→LG|0→0|B bỏ false-clean nhưng nhãn sai, chỉ trả câu kiểm tra lại bị cấm.|
|BASE2-0007|1|HC|[]→LG|0→0|B nêu nhánh đặc biệt nhưng coi mọi xử lý riêng là vi phạm; lộ chi tiết L1.|
|DIGITSUM-0007|2|H|LG→LG|0→0|Hai feedback chẩn đoán đúng đối số lệch; phân loại nguồn/gold bất đồng.|
|REVSTR-0007|2|MC|LG→LG|0→0|B chỉ đúng phép ghi nhưng mô tả ký tự mất thiếu chuẩn; L2 leak disputed.|
|DISTINCT-0010|1|VL|[]→LG|0→0|B thấy bỏ phần tử cuối; nhãn sai và tiết lộ nguyên nhân ở L1.|
|FACT-0008|2|BD|BD→BD|0→0|Cả hai nói thiếu dấu phẩy thay vì dấu kết thúc khai báo.|
|DISTINCT-0017|2|TT|LG→[]|0→0|B false-clean, vẫn có issue LG; feedback bịa chưa tính phần tử đầu.|
|MINA-0004|3|VL,E|LG→LG|0→0|B chỉ phê bình hai routine giống nhau, bỏ lỗi cận lặp và n=1.|
|SUMB-0005|1|LG,S|[]→BD|0→0|B bịa unused variable từ comment và đã đọc file thành công; quá chi tiết L1.|
|PRIME-0010|3|LG,IO|LG→LG|0→0|B bỏ nhận định phụ sai, hướng sửa logic hữu ích; vẫn thiếu IO.|
|COUNTUPPER-0001|3|[]|[]→[]|1→1|Cả hai khen phù hợp phạm vi nguồn.|
|DIGITSUM-0001|2|[]|[]→[]|1→0|B tự bịa giảng viên đã phân tích lỗi dù bài đúng.|
|DISTINCT-0001|1|[]|[]→LG|0→0|B nhầm hiệu suất với sai logic và lộ chi tiết; nguồn còn dispute giới hạn n.|
|FACT-0001|3|[]|LG→[]|0→0|B sửa false-positive taxonomy nhưng bịa tối ưu từ vòng lặp không có.|

Joint có1 win,1 loss,14 tie. Cải thiện nội dung còn thấy ở PRIME và nhận ra
phần tử bị bỏ ở DISTINCT-0010; hai case này không phải joint win. Suy giảm rõ
ở DIGITSUM-0001, SUMB-0005 và DISTINCT-0017. Không biến cải thiện từng phần
thành tuyên bố phương pháp B tốt hơn.

## Lỗi ở bước nào và chi phí

Attribution source-grounded sau review mù:8/16 bộ notes được hỗ trợ;
6/16 feedback lặp nhận định sai có sẵn trong note;5/16 có nhận định sai mới ở
stage2;0/16 tự sửa rõ ràng note sai. Các nhóm này có thể giao nhau, không cộng
thành16; chỉ đo sự lặp assertion quan sát được, không suy ra suy nghĩ ẩn của model.

- Taxonomy/note sai rồi feedback lặp sai: BASE2, REVSTR, DISTINCT-0017, MINA,
  SUMB. FACT-0008 có đúng nhãn nhưng note sai loại dấu, renderer lặp nguyên lỗi.
- Đúng taxonomy vẫn sai feedback: FACT-0008, DIGITSUM-0001 và FACT-0001.
  Hai bài clean sau có notes rỗng, cho thấy lỗi mới ở renderer.
- PALIN thêm hướng khởi tạo sai ở stage2. SUMB thêm khẳng định đọc file thành công.
  Không quan sát case tự sửa một note sai thành assessment hoàn chỉnh đúng.
- DISTINCT-0017 là một taxonomy=[] nhưng issue LG; parser chấp nhận đúng vai trò
  kiểm cấu trúc. Mâu thuẫn được giữ nguyên để đo, không có gọi model sửa ẩn.

| Chi phí trace | A lịch sử | B stage1 | B stage2 | B tổng |
|---|---:|---:|---:|---:|
|Calls|16|16|16|32|
|Input tokens|11.002|9.723|11.506|21.229|
|Output tokens|896|1.128|736|1.864|
|Tổng tokens|11.898|10.851|12.242|23.093|
|Generate latency, giây|11,924|23,803|16,091|39,894|

B dùng gấp2 calls và khoảng1,94 lần tổng tokens. Không tính model load vào
generate latency; load B16,768 giây ghi riêng. A là trace lịch sử, không phải
benchmark latency đồng thời cùng tải GPU; không suy luận tốc độ hệ thống từ tỷ số này.

## Gate, validation và tái lập

Gate được ghi trong config trước model: completion>=15; joint gain>=2 ID;
micro-F1 không giảm quá0,02; không tăng false claims; không confirmed L2 leak;
rare-label TP không giảm. Kết quả: completion PASS, joint gain FAIL,
micro-F1 FAIL, false-claims PASS, confirmed-L2 PASS nhưng còn1 disputed,
rare-TP PASS ở mức0→0. Không đủ điều kiện đi tiếp.

Validator chính thức trên **output thật16 ID** báo VALID: L1=5,L2=5,L3=6,L4=0.
Chỉ chứng minh schema/ID/Level mapping, không chứng minh nội dung đúng.
Predictions SHA256 `872984d405b4983c28dbd3a8d32b944298781785cca6a15902d8a4e59525de8c`.
Review/source/output hashes đầy đủ trong JSON metrics và seal private.

18 behavior tests mới đạt;22 integrity regression tests mới đạt; suite liên quan
cuối cùng **108 passed**. Full Task3: **1401 passed,5 skipped,1 failed**.
Lỗi duy nhất có sẵn là
`test_v2_plan_preserves_v1_and_does_not_read_prediction_or_public_inputs`:
baseline cũ kỳ vọng root predictions hash `9ba741…`, trong khi file root đã là
`c30c5c…` ở HEAD ban đầu. Không sửa file hay baseline để làm test xanh.
Full repository collection vẫn có2 lỗi Task1 vì thiếu sklearn; không cài thêm
hoặc sửa Task1/2. Log từng lệnh nằm trong outputs ignored; một lệnh test sai tên
file được giữ ở `related-command-error.log`, sau đó đã chạy lại đúng suite.

Independent code review trước freeze phát hiện case mọi ID vượt context làm
summary lỗi vì không có reservation; đã sửa/test RED→GREEN trước model.
Audit report sau chạy phát hiện thiếu binding leaf seal/key/current-output và
cost-ID coverage; đã sửa và thêm22 test nhân tạo chống tráo key/output/Level,
extra review không seal và source seal sai. Không thay đổi runtime/prompt/results.
Audit cuối không còn finding quan trọng cho workflow complete-run này.

Lệnh kiểm tra/review lại từ repository (không generate mới):

```bash
.venv-task3/bin/python scripts/task3_two_pass.py verify
.venv-task3/bin/python scripts/task3_two_pass_report.py score
.venv-task3/bin/python scripts/validate_task3_submission.py --predictions outputs/task3/two-pass-20261023/B/predictions.json --requested-levels outputs/task3/two-pass-20261023/requested-levels.private.json
.venv-task3/bin/python -m pytest -q tests/test_task3_two_pass.py tests/test_task3_two_pass_report.py tests/test_task3_grounded.py tests/test_task3_grounded_metrics.py tests/test_task3_round15.py tests/test_task3_round15_runner.py tests/test_task3_submission.py
```

Lệnh `task3_two_pass.py run` đã chạy đúng một lần; marker chặn resampling.
Freeze không được ghi đè. Không giả định clone mới có dữ liệu private hoặc model
cache; thiếu chúng phải dừng, không thay bằng fixture để tuyên bố đã inference.
Manifest bảo toàn2848 file cũ xác nhận0 hash thay đổi. R15 public predictions
328 ID vẫn SHA256 `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`.

Tập16 nhỏ, synthetic và đã lộ trước; rubric agent chưa có human verification,
hai source dispute và nhiều nhãn support1. Completion16/16 so với compact0/8
chỉ cho thấy flow đơn giản vận hành được trên tập khác; không chứng minh quality
tăng hoặc điểm leaderboard tăng. Kết quả hiện tại không đủ thay thế R15.

Giữ R15.
