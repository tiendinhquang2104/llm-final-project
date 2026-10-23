# Task 3: truy nguyên câu meta và ablation stage1/stage2 v2

**Giữ R15; không chạy E.** C bỏ được câu meta trong15 output nhưng chưa sửa được vai giao tiếp, clean hallucination và Level leak. D làm taxonomy giảm thêm; không có TP mới ở các nhóm từng bỏ sót.

Số liệu: [TASK3_TWO_PASS_V2_METRICS_20261023.json](TASK3_TWO_PASS_V2_METRICS_20261023.json).
Branch `feat/task3-quality-round5`; HEAD ban đầu
`26a9d9b10c32e8daf95d8ef29dc76af61332bda0`, working tree sạch.
Không sửa R15, two-pass-v1, gold, split hay artifact cũ; không public inference,
candidate328, upload, push hoặc PR. Raw chỉ ở ignored
`outputs/task3/two-pass-v2-20261023/`.

## 1. Câu meta xuất hiện ở đâu?

Truy nguyên **trước sửa prompt**, toàn bộ16 ID, gồm bảy case người dùng yêu cầu.
Không generate để trace: load tokenizer đúng revision, dựng lại rendered text
từ đúng messages trong journal v1, đối chiếu số token với trace đã chạy.

| Boundary DIGITSUM-0001 | Bằng chứng |
|---|---|
|Source/statement|Không có cụm “Giảng viên đã phân tích”; hash task `5ea64d6f…`.|
|Stage1 rendered input|Đúng source allowlist, không Level/gold/teacher/reviewer; rendered hash `3006c53e…`.|
|Stage1 raw|JSON taxonomy=[] và issues=[]; hash `36b3730c…`.|
|Stage1 parsed|Giữ nguyên hai danh sách rỗng, bằng result đã lưu.|
|Stage2 rendered input|Đúng cùng source + own prediction + own Level2; không có cụm meta; hash `00e1dc84…`.|
|Stage2 raw|Cụm meta **xuất hiện lần đầu ở đây**; raw hash `dc3a96a1…`.|
|Stage2 parsed|JSON parser trả lại nguyên chuỗi model sinh.|
|Final|Bằng nguyên parsed feedback; assembler không viết/thay nội dung.|

Journal messages stage2 hash đầy đủ
`42bfad52d784335a171ff21b859bbf8e8196a31e788058834f4fbb8656cbecca`;
raw-response SHA256
`dc3a96a12aa8f04c6b7dc5edc2b71089cf6a4de5448dde0aa47eeff2460f4372`.
Boundary-trace SHA256
`c6349495451dbdeaa5739a50531177d2127263512acf6d114586d92b287599d7`.
Không đưa rendered prompt, student source hay cả raw response vào Git.

Cả32 input v1 đều khớp messages được tạo từ source allowlist và prediction của
chính ID; không thấy teacher feedback, gold, reviewer text hay ví dụ ID khác lọt
vào input. Roles đúng `system,user`; `add_generation_prompt=True` tạo đúng prefix
assistant mở;32 token counts khớp trace. HFBackend chỉ decode suffix sinh mới.
Tokenizer/template đều đúng bản frozen; không có lỗi role serialization quan sát được.

Prompt v1 có cách gọi vai mơ hồ “Bạn viết nhận xét giảng viên”, chưa chỉ rõ lời
hiển thị nguyên văn cho sinh viên, xưng em, cấm bình luận về feedback/giảng viên.
V1 chỉ nhắc kiểm code khi taxonomy rỗng; chưa ưu tiên nhánh clean trước yêu cầu
chẩn đoán L2/hướng sửa L3. COUNTUPPER-0001 cho thấy [] không luôn sinh meta;
FACT-0001 lại bịa tối ưu, nên không thể quy mọi trường hợp [] vào một lỗi parser.

**Kết luận boundary:** lỗi sinh nội dung/định vị vai ở stage2. Chưa có bằng chứng
data leakage trong các input đã kiểm. Độ mơ hồ prompt là giả thuyết thiết kế cần
thử bằng C, không phải bằng chứng về suy luận nội bộ của model.

Một phép tái hiện nằm ngay trong D đã được yêu cầu: DIGITSUM-0001 lại có stage1
rỗng, nên stage2-v1 nhận **messages y hệt B và sinh raw y hệt B**, với hai hash
đầy đủ ở trên. Không gọi thêm model cho phép tái hiện này. C đổi prompt/raw hash
và chuyển sang khen bài tính tổng chữ số; chất lượng vai/Level vẫn chấm độc lập.

## 2. Thiết kế phép thử

| Nhánh | Stage1 | Stage2 | Ý nghĩa |
|---|---|---|---|
|A|R15 cũ|R15 cũ|Đối chứng có provenance, không generate mới.|
|B|two-pass-v1 cũ|two-pass-v1 cũ|Đối chứng có provenance, không generate mới.|
|C|Replay đúng stage1 B|v2|Cô lập renderer; không phải pipeline end-to-end mới.|
|D|v2 mới|Đúng prompt v1 frozen|Cô lập taxonomy; không phải pipeline E.|
|E|v2 mới|v2 mới|Chỉ chạy sau gate C/D; không lấy output D giả làm E.|

Giữ đúng16 ID cũ, đã xem ở các vòng trước:3 từ development8,13 từ evaluation60
cũ, nay là development. L1/L2/L3=5/5/6, L4=0;14 single,2 multi;4 gold-clean;
gold có support đủ10 nhóm. Không gọi là benchmark mới, không chọn best output
từng ID. Manifest/source hashes được giữ từ v1 và bound trong freeze.

Stage2-v2 quy định trợ giảng nói trực tiếp với sinh viên bằng em, không nhận xét
giảng viên/người chấm/model/feedback/rubric. Nhánh clean được xét trước Level:
[]/[] phải kiểm source rồi khen có căn cứ, không bịa lỗi hoặc tối ưu ở L2/L3.
Own Level rule chính thức và điều cấm đi theo từng bài. Không chèn câu trả lời
mẫu theo ID, few-shot hoặc teacher/gold/reviewer/public/history.

Stage1-v2 phân biệt đủ10 cơ chế: compile, I/O, loop, array/string, function,
edge, algorithm, hard-code, style và logic; chỉ nhóm có bằng chứng. Không coi
warning/comment/khác sở thích là lỗi compile/style. Output vẫn hai trường ngắn.

Contract code yêu cầu tập taxonomy labels bằng tập issue labels. Không thêm,
xóa hoặc sửa label/note. C giữ stage1 B nguyên vẹn; DISTINCT-0017 có [] nhưng
issue Logic nên **unresolved, không gọi stage2**. Raw stage1 gốc còn ở
`stage1_observed`; không lấp bằng [] hoặc feedback chung. C có15 call renderer,
D có32 call mới. Không fallback/hybrid.

Model/tokenizer load **một lần** cho C rồi D, từng ID tuần tự. Mỗi generate một
ID, hai messages mới, không chia sẻ hội thoại. D/E tối đa2 calls/ID, C tối đa1
call mới/ID. Journal reserve+fsync trước call, raw trước parse; interruption không
generate lại. Parser không áp semantic gate hay sửa xưng hô sau khi sinh.

D phải giữ đúng renderer v1: input metadata ngoài allowlist bị reject trước
generate thay vì lén đổi prompt v1. Trên16 input thật, allowed payload và own
Level definitions bằng nguyên v1; chỉ predicted stage1 mới thay đổi ở D.

Qwen/Qwen2.5-Coder-7B-Instruct, revision
`c03e6d358207e414f1eca0bb1891e29f1db0e242`, NF4 double quant/BF16 compute,
seed42, greedy, zero-shot, context16384,1024 output tokens/45 giây mỗi call.
Không fine-tune hay đổi precision. Runtime xác nhận CUDA4-bit, BF16 compute;
tensor ngoài quantization lưu FP16. Load16,240 giây; peak allocated6.814 GB,
reserved8.045 GB. Không động vào process GPU khác.

Freeze SHA256 `8a9b40a7cf7829b7682019fbfe1470f9db283526d15a9ad696ea35daa88fceaf`;
stage1-v2 prompt SHA `a57a0911212d51173dd2d5a0a0206c1b6aa6edd32373a1f899911ec4b98b9d8c`;
stage2-v2 bundle `3cfdf88f0831aa4fe788867497b754324c938e6d9ff69a1e5b14e15dc6d73e15`.
Một bản v2 duy nhất; không v3/v4/v5 hoặc resampling sau xem output.
Freeze gồm runner, audit/scorer, helper metric, source reviews và hash hai file
gold gốc; gold chỉ được mở cho scoring sau seal review mù.

## 3. Review và kết quả toàn bộ16 ID

Hai agent mới đọc nguồn trước output/gold, mỗi agent16 case; source được seal
trước generate. Sau C/D, mỗi người chấm64 output ẩn nhánh A/B/C/D, kể cả mẫu
unresolved. Không xem key, notes, raw generation, gold, báo cáo hoặc review của
người kia. Chấm vai giao tiếp, meta, factuality, Level, clean hallucination,
consistency, main defect và naturalness riêng. Có em trong chuỗi không đủ credit.
Reviewer là agent, chưa được con người xác minh.

|Toàn bộ16 ID|A: R15|B: v1|C: renderer|D: taxonomy|E|
|---|---|---|---|---|---|
|Complete / unresolved / fallback|16 / 0 / 0|16 / 0 / 0|15 / 1 / 0|16 / 0 / 0|NR|
|Calls mới|0|0|15|32|0|
|Micro-F1 gold gốc|0,3200|0,2857|0,2857|0,1935|—|
|Macro-F1 đủ10|0,1400|0,1133|0,1133|0,0649|—|
|Exact gold gốc|5/16|5/16|5/16|3/16|—|
|TP/FP/FN|4/5/12|4/8/12|4/8/12|3/12/13|—|
|False-clean gold gốc|4/16|1/16|0/16|0/16|—|
|Đúng Level đồng thuận|5/16|5/16|3/16|1/16|—|
|Meta bị ít nhất1 reviewer flag|1/16|1/16|0/16|4/16|—|
|Xưng em tự nhiên đồng thuận|0/16|0/16|3/16|0/16|—|
|False claims|11/16|10/16|8/16|14/16|—|
|Clean false error|1/4|3/4|2/4|4/4|—|
|Strict joint mới|0/16|0/16|0/16|0/16|—|

Metric taxonomy dùng nguyên gold gốc và cả16 ID; unresolved là None, không [];
macro luôn chia10, zero-denominator per-label F1 quy ước0. C không dự đoán lại
taxonomy; chênh completion/false-clean của C phản ánh contract, không phải taxonomy
model mới. E không chạy được ghi not_run/metric null, không báo điểm0 như đã đánh giá.

|Nhãn|Support|A TP/FP/FN|A F1|B TP/FP/FN|B F1|C TP/FP/FN|C F1|D TP/FP/FN|D F1|
|---|---|---|---|---|---|---|---|---|---|
|Lỗi biên dịch|2|2/0/0|1,0000|2/1/0|0,8000|2/1/0|0,8000|2/7/0|0,3636|
|Lỗi nhập/xuất|2|0/0/2|0,0000|0/0/2|0,0000|0/0/2|0,0000|0/1/2|0,0000|
|Lỗi logic|3|2/5/1|0,4000|2/7/1|0,3333|2/7/1|0,3333|1/3/2|0,2857|
|Lỗi vòng lặp|2|0/0/2|0,0000|0/0/2|0,0000|0/0/2|0,0000|0/0/2|0,0000|
|Lỗi mảng/chuỗi|2|0/0/2|0,0000|0/0/2|0,0000|0/0/2|0,0000|0/0/2|0,0000|
|Lỗi hàm|1|0/0/1|0,0000|0/0/1|0,0000|0/0/1|0,0000|0/0/1|0,0000|
|Lỗi edge case|1|0/0/1|0,0000|0/0/1|0,0000|0/0/1|0,0000|0/0/1|0,0000|
|Lỗi thuật toán|1|0/0/1|0,0000|0/0/1|0,0000|0/0/1|0,0000|0/1/1|0,0000|
|Lỗi hard-code|1|0/0/1|0,0000|0/0/1|0,0000|0/0/1|0,0000|0/0/1|0,0000|
|Lỗi style|1|0/0/1|0,0000|0/0/1|0,0000|0/0/1|0,0000|0/0/1|0,0000|

|Mẫu số cố định|A|B|C|D|E|
|---|---|---|---|---|---|
|L1 (5)|2/5|1/5|1/5|1/5|—|
|L2 (5)|2/5|1/5|1/5|0/5|—|
|L3 (6)|1/6|3/6|1/6|0/6|—|
|L1 detail leak /5|0/5|4/5|4/5|4/5|—|
|L2 repair leak union /5|1/5|1/5|3/5|0/5|—|
|L2 repair leak đồng thuận /5|1/5|0/5|2/5|0/5|—|
|L3 actionable /4 bài có lỗi|1/4|2/4|0/4|1/4|—|

C có0 meta trong15 output complete, nhưng chỉ3/16 natural em (đều L3), vẫn dùng bạn ở phần lớn bài. Clean false-error C2/4 (DISTINCT-0001, FACT-0001), cả hai reviewer xác nhận; B3/4, D4/4. L2 C3/5 bị ít nhất một reviewer đánh leak,2/5 đồng thuận. L3 C0/4 actionable; D1/4. Không thể coi giảm meta là sửa xong renderer.

A có1 meta flag ở SUMB-0005: reviewer A coi câu bàn về đủ thông tin đầu vào là bình luận quá trình, B không coi meta; giữ bất đồng (0 confirmed meta ở A). B1 và D4 case meta là các câu về giảng viên/feedback; C0. Có em không được kiểm bằng regex: hai reviewer tự chấm lời nói trực tiếp; em đi kèm nhận định sai không được joint credit.

D phát4 nhóm (BD/LG/IO/TT), nhưng IO mới ở BASE2 không bắt đủ hard-code, TT ở bài clean là false positive. TP ngoài Compile/Logic vẫn0; D micro0,1935 và macro10 0,0649, thấp hơn B0,2857/0,1133 và A0,3200/0,1400. Source-A sensitivity: B→D micro0,3571→0,3226, macro0,1262→0,1364; không chọn riêng macro thuận lợi để thay primary gold.

Gate đã đăng ký trước: C_no_meta: PASS; C_no_confirmed_clean_false_error: FAIL; C_no_unresolved_clean_false_error_disagreement: FAIL; C_direct_em_for_all_completed: FAIL; D_micro_improves: FAIL; D_macro10_improves: FAIL; D_new_TP_outside_compile_logic: FAIL. **E=NOT RUN,0 generate**. CLI thử kiểm gate đã trả ValueError trước load model. Không thử v3 hoặc đánh giá tập khác.

Level counts5/5/3/1 ở đây là lần chấm mới của hai reviewer đủ16 ID, lấy đồng thuận và giữ scope caveats. Chúng không phải cùng phép đo11/8 trong báo cáo trước (coverage/rubric/reviewers khác); A/B content giữ nguyên. Không dùng thay đổi điểm reviewer để tuyên bố model cũ đã thay đổi.

Strict joint mới cần complete, taxonomy exact theo nguồn, không source dispute,
factual/main/consistency/Level/natural, direct em và không meta/placeholder.
L1/2 leak hoặc L3 không actionable không được credit dù reviewer lỡ đánh LevelOK.
Rubric vai giao tiếp chặt hơn báo cáo v1: số2/16 cũ không bao gồm điều kiện em;
không so trực tiếp với joint mới rồi gọi đó là chất lượng control thay đổi.

Source reviews mới ghi khá nhiều caveat về miền input chưa được giới hạn và
overflow/capacity, kể cả khi lỗi chính có phản ví dụ rõ. Giữ nguyên flags và
withhold strict credit, không tự sửa chúng sau xem output. Per-ID JSON giữ
source A/B, source_disputed và bất đồng từng trục. Vì vậy strict joint là proxy
bảo thủ chịu ảnh hưởng độ dè dặt reviewer, không phải human ground truth.
Primary F1 vẫn gold gốc; sensitivity source-A ghi riêng, không thay gold để tăng F1.

## 4. Từng ID, lỗi sửa được và lỗi mới

BD=biên dịch, IO=nhập/xuất, LG=logic, VL=vòng lặp, MC=mảng/chuỗi,
H=hàm, E=edge case, TT=thuật toán, HC=hard-code, S=style.
U=unresolved; NR=not_run. Nhãn ngắn đều ánh xạ đúng10 tên chính thức.

|SYN-ID|L|A taxonomy|B taxonomy|C taxonomy|D taxonomy|E|Sai lệch chính|
|---|---|---|---|---|---|---|---|
|COUNTVOWEL-0010|3|BD|BD|BD|BD|NR|C placeholder; D sai loại dấu|
|PALIN-0017|3|LG|LG|LG|LG|NR|C/D sai diễn giải palindrome|
|UPPER-0005|1|[]|LG|LG|LG|NR|C/D placeholder, nhãn LG sai|
|BASE2-0007|1|[]|LG|LG|IO|NR|D thêm IO nhưng bỏ HC; false unused|
|DIGITSUM-0007|2|LG|LG|LG|LG|NR|C lộ sửa; D meta|
|REVSTR-0007|2|LG|LG|LG|BD|NR|D compile FP; C nội dung/leak sai|
|DISTINCT-0010|1|[]|LG|LG|LG|NR|C L1 lộ vị trí; D vẫn LG|
|FACT-0008|2|BD|BD|BD|BD|NR|C lộ sửa dấu sai; D sai dấu|
|DISTINCT-0017|2|LG|[]|U|BD|NR|C U; D compile FP thay lỗi thuật toán|
|MINA-0004|3|LG|LG|LG|BD|NR|C issue sai; D compile FP|
|SUMB-0005|1|[]|BD|BD|BD|NR|C lặp note sai; D bỏ lỗi tổng|
|PRIME-0010|3|LG|LG|LG|BD|NR|C hướng sửa chung; D compile/meta|
|COUNTUPPER-0001|3|[]|[]|[]|BD|NR|C khen; D compile FP mới|
|DIGITSUM-0001|2|[]|[]|[]|[]|NR|C hết meta nhưng bạn; D lặp meta|
|DISTINCT-0001|1|[]|LG|LG|TT|NR|C false error; D TT FP|
|FACT-0001|3|LG|[]|[]|BD|NR|C tối ưu bịa; D compile FP|

Các trường hợp chính, diễn giải ngắn thay vì chép raw student code/output:

- DIGITSUM-0001: B/D sinh lại cùng câu meta. C khen đúng phép tính, nhưng dùng
  bạn thay vì em. Đây là sửa được riêng nội dung meta tại một ID, chưa đạt vai.
- COUNTUPPER-0001: C giữ lời khen; D bịa lỗi thiếu thư viện và đổi clean thành
  compile error. Stage1 mới có thể làm hỏng clean case trước renderer.
- FACT-0001: C vẫn gợi ý chuyển vòng lặp không khớp code thực tế; D còn gán lỗi
  compile từ nhận định kiểu dữ liệu sai. Clean instruction không đủ ngăn hallucination.
- DISTINCT-0017: C dừng contract như thiết kế; D hết mismatch cấu trúc nhưng
  gán compile error cho vấn đề capacity, vẫn bỏ thuật toán đếm đoạn liên tiếp.
- SUMB-0005: C lặp chuyện biến trong comment và khẳng định đọc file; D đổi sang
  khuyên kiểm tra cấp phát mà không nhận ra tổng bỏ giá trị âm. Không sửa lỗi chính.
- BASE2-0007: D phát nhóm IO thay cho Logic, nhưng không đồng thời bắt hard-code;
  feedback vẫn bịa biến không dùng. C vẫn lộ chi tiết ở L1 và tự mâu thuẫn khen/sai.
- FACT-0008: đúng nhóm compile không bảo đảm nhận định đúng loại dấu; C còn đưa
  thao tác thêm token tại L2. COUNTVOWEL-0010 C tụt về placeholder-only ở L3.
- DIGITSUM-0007: C đưa hướng sửa rõ tại L2; D dùng lời bình về giảng viên.
  MINA C chỉ dẫn sửa từ issue không có căn cứ và còn thiếu lỗi thật ở nhiều câu.

Không hậu xử lý bạn→em, xóa câu meta hoặc remap compile→array để làm đẹp kết quả.
Không chọn cặp taxonomy/feedback khác nhau theo reviewer. Những output kém được giữ
nguyên để thấy giới hạn stage1 và stage2, cùng bảng đúng/sai từng trục trong JSON.

## 5. Chi phí, kiểm chứng, bàn giao

|Chi phí|A|B|C|D|E|
|---|---|---|---|---|---|
|Calls tính cả trace lịch sử|16|32|15|32|0 / NR|
|Calls mới|0|0|15|32|0 / NR|
|Input tokens|11002|21229|13084|25520|0 / NR|
|Output tokens|896|1864|915|1889|0 / NR|
|Generate latency (giây)|11,924|39,894|17,719|34,364|0 / NR|

C chỉ có15 call mới stage2, còn stage1 lấy từ16 call cũ của B; không gọi C là
pipeline một lượt mới. A/B là trace lịch sử, latency không cùng tải GPU/thời điểm;
không coi tỷ số latency là benchmark tốc độ. C/D có một model load16,240 giây
ghi riêng; E0 call. Tổng mới C+D:47 calls,41.408 tokens,52,083 giây generate.

Validator chính thức: D **VALID16**, Levels5/5/6/0. C khi kiểm với full16 requested
IDs thất bại do chỉ15 records; đây là incomplete đã báo, không phải file submit
hoàn chỉnh. Không dùng fixture giả để tuyên bố đã inference/validator thật.

Tests mới32 passed; suite liên quan cuối cùng111 passed: clean L2/3 prompt, consistency, no hidden input fields,
one-ID order/cap/resume, own Level rules, real HFBackend role serialization/
generation prefix/generated suffix, independent role rubric, seal/output binding,
E gate disagreements và frozen-reference drift. Những test Level kiểm contract/
prompt và rubric; không lấy mocked response làm bằng chứng model luôn đúng Level.
Semantic Level failures của model được đo bằng review thực tế ở trên.

Full Task3: **1433 passed,5 skipped,1 failed**. Lỗi cũ
`test_v2_plan_preserves_v1_and_does_not_read_prediction_or_public_inputs`
do baseline kỳ vọng root predictions hash R15 `9ba741…` trong khi file root đã
là `c30c5c…` từ HEAD ban đầu; không sửa để làm test xanh. Bare pytest vẫn dừng
ở hai test Task1 vì thiếu sklearn (`test_clm_zeroshot_task1`, `test_task1_clm_probe`).
Không sửa Task1/2 hoặc cài package ngoài phạm vi.

Audit trước freeze có regression RED→GREEN cho unsafe D evidence, kiểm tra
integrity bị Python-O bỏ qua, interrupted-call origin, packet leaf binding của
E, frozen gold/metric helper, clean-disagreement gate và rubric leak mâu thuẫn.
Tất cả sửa trước generate; không sửa prompt/core/scorer sau freeze. Lệnh/log và
review artifacts lưu private, report chỉ có metadata/hashes/diễn giải tối thiểu.

Files mới: [prompt/runner core](../../src/task3/two_pass_v2.py),
[CLI](../../scripts/task3_two_pass_v2.py), [audit/scorer](../../scripts/task3_two_pass_v2_audit.py),
[config](../../configs/task3/two_pass_v2_20261023.json),
[behavior tests](../../tests/test_task3_two_pass_v2.py),
[audit tests](../../tests/test_task3_two_pass_v2_audit.py).

```bash
.venv-task3/bin/python scripts/task3_two_pass_v2.py verify
.venv-task3/bin/python scripts/task3_two_pass_v2_audit.py score
.venv-task3/bin/python -m pytest -q tests/test_task3_two_pass_v2.py tests/test_task3_two_pass_v2_audit.py
.venv-task3/bin/python scripts/validate_task3_submission.py --predictions outputs/task3/two-pass-v2-20261023/D/predictions.json --requested-levels outputs/task3/two-pass-v2-20261023/requested-levels.private.json
```

`run-CD` đã chạy đúng một lần, marker chặn chạy lại; `run-E` kiểm gate và cả
leaf/current-output binding trước load model. Không xóa marker để resample.
Để replay audit/score cần private inputs và pinned tokenizer/cache có thật.
Manifest bảo toàn2918 file cũ kiểm tra0 thay đổi; không stage raw outputs/source.

Câu meta bắt đầu ở stage2 raw và tái hiện nguyên vẹn khi D dùng lại cùng input; sửa stage2 chỉ giảm meta, chưa đạt em/clean/Level. Stage1-v2 không tăng TP ở nhóm bỏ sót và làm F1 giảm. E chưa được chạy, nên không có bằng chứng E hơn R15 trên cả taxonomy lẫn feedback, cũng không có cơ sở đề xuất một vòng evaluation lớn hơn. Tập16 synthetic đã lộ, hai agent review chưa human-verified và nhiều source caveats khiến strict joint rất bảo thủ; không suy luận điểm leaderboard.

Giữ R15; không tiếp tục E trong phép thử này.
