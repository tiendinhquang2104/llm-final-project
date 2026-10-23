# Task 3 — two-pass-findings-v1, development 2026-10-23

**Giữ R15.** Đã triển khai và chạy Qwen thật; nhánh mới hoàn tất29/30,
không fallback. Giọng tốt hơn nhưng joint theo gold gốc vẫn0/30, giống R15 và
C-old. Không chạy public, upload, push, fine-tune hoặc đổi default production.
Đây là development bổ sung đã phơi nhiễm, không phải kết quả generalization.

Số liệu tổng hợp ở `TASK3_TWO_PASS_FINDINGS_V1_METRICS_20261023.json`.
Toàn bộ source, raw, findings, gold, prompt, manifest, review và bảng đầy đủ từng
ID chỉ nằm trong ignored `outputs/task3/two-pass-findings-v1-20261023/`.

## Hợp đồng dữ liệu và nguồn

Branch `two-pass-findings-v1` từ `fee2c49` trên checkout
`/workspace/llm-final-project`; working tree ban đầu sạch. Không tìm thấy
AGENTS.md áp dụng. Tạo branch tại chỗ để dùng đúng ignored data/model/artifacts;
không reset/clean/rebase hoặc ghi đè thay đổi người dùng.

`DoAn-LLM-Challenge.docx.md` mô tả nhãn cho sẵn, nhưng metadata Task3 thực tế
trong nested `data/generate-dataset.zip` ghi **“Nhãn lỗi không cho sẵn (tự chẩn
đoán)”**. Input không có taxonomy_error; output có taxonomy_error và feedback.
Vòng này dùng mode tự chẩn đoán của synthetic-train. Loader/mode nhãn cho sẵn
của real data được giữ riêng, không dùng gold làm input.

Archive ngoài SHA256
`8c04e4e01be73952cb255fb5efd707c758205c19457fa651d944fc02780a3e1e`;
nested ZIP `88eff95f2841efd061ab0203907f9142ad6a2a2b72e266a4d55043a50aedac9c`.
Không trộn `generate-dataset_v2.zip`. Đối chiếu byte toàn bộ exams/task3/label
metadata với nested archive; từng source được chọn khớp code_file trong cùng
archive. Loader nối exam_id/code_file; kiểm tra cả đề, problems, prerequisite,
exam_type, family, code, Level và gold của prepared với raw trước sử dụng.
Manifest lưu hash file code thô, exam semantic object, archive và evidence.

Evidence chung cho mọi arm là compiler unavailable, tests not_run. Các chuỗi
exec_report không có binding đủ tin cậy cho phiên bản nguồn này nên không được
đưa vào prompt. Không compile hoặc thực thi bài sinh viên trên host. Mọi nhận
định nguồn là review tĩnh; không biến việc không tìm thấy lỗi thành test pass.

Khóa30 ID: L1/L2/L3=10/10/10,21 multi và9 single,3 gold-clean đều ởL1;
support đủ10 nhóm. Chọn chỉ trong127 synthetic-train thuộc7 family khác cả
old16 và C-feedback-v3-12, seed20261023;3 cleanL1 rồi ưu tiên nhãn hiếm theo
tần suất và cân bằng family. Không đổi split/gold cũ. Có27 code hash riêng vì
3 cặp clone khác Level; đây không phải30 source độc lập. Cả30 ID và7 family
có dấu vết trong lịch sử artifact: **seen**, không gọi unseen. Dấu vết chỉ chứng
minh đã xuất hiện, không chứng minh mọi ID đều được con người dùng chỉnh prompt.

Selection seal `0d987472e5a8882fa2e385a4d725459cd42be674f2f12700cae8f131713d7f56`.
Manifest/hash được khóa trước output mới, source references được seal trước
inference. Candidate chỉ một bản; không chọn response hoặc chỉnh prompt sau
khi xem development.

## Implementation và tái lập

- `src/task3/two_pass_findings.py`: detector độc lập mới, findings-only parser,
  union theo thứ tự10 nhãn nạp từ label_space, own-Level renderer, trạng thái.
- `scripts/task3_two_pass_findings.py`: select/freeze/verify/run; tái sử dụng
  loader, Journal, HFBackend và original control runners.
- `scripts/task3_two_pass_findings_report.py`: packet mù, seal, metrics offline;
  không gọi model hoặc chỉnh nội dung.
- `configs/task3/two_pass_findings_v1_20261023.json`,3 file test và
  `docs/superpowers/plans/2026-10-23-two-pass-findings-v1.md`.

Stage1 chỉ nhận đề, prerequisite có thật, code, evidence allowlist và official
labels; không Level/gold/teacher/reviewer/arm/sample ID ở metadata. Code được
JSON-framing riêng với system instruction, comment là dữ liệu. Mã câu lấy từ
metadata đề nếu có; `SINGLE` là mã ổn định khi không có problems/pid. Không tự
chia câu. Parser chỉ kiểm JSON/type/required fields/enum; không kiểm ngữ nghĩa,
không alias, regex diagnosis hoặc compiler-derived finding.

Runner reserve+fsync trước generate, raw trước parse; lưu parsed findings/union
trước lượt2 rồi lưu final/status trước ID tiếp theo. Lượt2 nhận chính bài đó,
findings/union và đúng một định nghĩa Level chính thức; chỉ trả feedback JSON.
Final giữ chuỗi feedback nguyên văn sau JSON-unescape và taxonomy của runner.
Không sửa bạn→em, cắt leak, vá câu hoặc gọi reviewer/JSON repair trong inference.

Malformed JSON/label lạ/termination không EOS/vượt context thành unresolved,
không thành clean. Journal bind code/evidence/Level/config/tokenizer/source
provenance; resume chỉ dùng raw đã có, không gọi lại reservation bị gián đoạn.
Từng generate chỉ một bài, hai message system/user mới, không history chung.

Freeze `7b125fa2acd1475eaeb699172a2f573b4a9a8cdab5b6877cbd8d4958ab62536c`;
prompt bundle `deb5391c48102eebbb747180d4bb79abf48e87f5523a6fc1367188577cfe623e`;
config `194942b78932ad5ad52dad733bfea1a0d71c2de31031313d850c04da56db4eac`.
Freeze giữ cả dependency control/parser, tokenizer, source/selection seals và
code snapshot. Packet seal giữ results, raw journals, reservations, fallback
traces và runtime; presence manifest phát hiện cả file thêm sau khi seal.

Qwen/Qwen2.5-Coder-7B-Instruct revision
`c03e6d358207e414f1eca0bb1891e29f1db0e242`,NF4 double quant,BF16 compute,
nonquantized tensor FP16,seed42,greedy,zero-shot,context16384; cùng controls.
Chat-template SHA256
`cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`.
Chỉ token cap của detector mới1536, renderer1024; không truncate đề/code.
Giữ generation max_time45s. Load model một lần10,219s trên RTX5090;
peak allocated7.071.596.544 bytes, reserved7.212.105.728 bytes; không CPU offload.

A là R15 original selected config, có bounded retry/disclosure fallback vốn có;
C-old là đúng v1 detector + v2 C renderer, runtime original two_pass config.
C là pipeline mới end-to-end. Chạy lại controls trên cùng30 ID và nguồn/evidence,
không reuse output khác phiên bản. Không D/E, stage1-v2 hoặc teacher feedback.

Có thêm exploratory replay renderer cũ trên label/error của findings mới,29
replay khả dụng trong30 ID được yêu cầu. Projection giữ nguyên error text/label,
nhưng schema issues cũ không giữ riêng location/evidence/problem_id. Vì vậy bảng
phụ này **không cô lập thuần tác động văn phong** trên input cấu trúc giống hệt;
không dùng nó làm bằng chứng causal riêng cho prompt. Giữ raw/cost đầy đủ, không
coi replay là end-to-end mới hoặc xây framework chuyển đổi thêm sau khi xem output.

```bash
.venv-task3/bin/python scripts/task3_two_pass_findings.py verify
.venv-task3/bin/python scripts/task3_two_pass_findings.py score
.venv-task3/bin/python -m pytest -q tests/test_task3_two_pass_findings.py tests/test_task3_two_pass_findings_experiment.py tests/test_task3_two_pass_findings_report.py
.venv-task3/bin/python scripts/validate_task3_submission.py --predictions outputs/task3/two-pass-findings-v1-20261023/C/completed.predictions.json --requested-levels outputs/task3/two-pass-findings-v1-20261023/completed-requested-levels.private.json
```

`select → source review/seal → freeze → run → packets → offline review/attribution
→ score` là CLI thực tế. Default destination là thư mục trên; run hoàn tất không
cho resample. Để tái lập ở thư mục khác phải chỉ rõ `--out` và thực hiện source
review/seal thật của manifest mới; không dùng fixture thay reviewer/model.

## Review và cách tính

Reviewer A độc lập đọc đủ30 nguồn trước prediction; B đọc12 nguồn được chọn
trước output để kiểm tra clean/biên nhãn/L2. Sau source seal, mỗi người chấm
120/48 output ẩn tên arm, xáo seed2026102305; không đọc gold/key/raw hoặc review
của người kia. Paired review được seal trước attribution. Đây là Codex agent
review, chưa có human validation; không thêm dịch vụ/API review.

A và B đồng ý về source taxonomy trên12/12 ID kiểm tra chéo. A có33 reference
findings,6 bài không có lỗi được xác lập trong phạm vi và15 source-domain dispute;
21/30 taxonomy nguồn khác gold gốc. Khác biệt gồm ranh giới loop/logic/hard-code,
nhãn style không có yêu cầu tương ứng, khoảng trắng, capacity/empty domain chưa
được đề khóa. Không sửa gold. Đo finding recall chỉ theo reference findings đã
seal trước output, không coi số gold labels là số lỗi.

Cùng rubric cho mọi arm: factuality, main coverage, Level, vai tự nhiên, false
claims, bạn/tự xưng/meta, placeholder, leak L1/L2 và L3 hữu ích. Câu kỹ thuật
không đại từ vẫn hợp lệ; có “em” không tự được credit. Kết hợp bảo thủ trên12 bài
hai review: good cần đồng ý, bad chỉ cần một người ghi nhận; giữ bất đồng riêng.
Có16/120 cặp ID-output bất đồng ít nhất một trường; không tự nâng điểm bằng
adjudication sau output.

Joint chính dùng **gold gốc**: complete + taxonomy exact + feedback factual,
bao phủ lỗi chính phù hợp Level, đúng Level/vai, không placeholder hay tranh luận
nội dung chưa giải quyết. Đây là cách vận hành rubric nghiêm cho yêu cầu joint;
source-joint là cột riêng, loại source dispute. Không so joint của báo cáo cũ như
cùng metric. Toàn bộ mẫu số30, unresolved fail exact/joint kể cả gold sạch; chỉ
TP/FP/FN coi dự đoán unresolved là rỗng, không tạo record rỗng giả. F1 zero_division=0,
macro luôn chia đủ10 nhóm; số complete luôn báo cạnh F1.

## Kết quả lượt1 và completion, mẫu số30

|Chỉ số|R15|C-old|Findings mới|Replay renderer cũ|
|---|---:|---:|---:|---:|
|Complete|30|30|29|29|
|Unresolved|0|0|1|1|
|Fallback|3|0|0|0|
|Micro-F1|0.259740|0.258824|0.380952|0.380952|
|Macro-F1 đủ10|0.195475|0.191717|0.307046|0.307046|
|Exact/30|8|6|4|4|
|TP|10|11|20|20|
|FP|14|21|32|32|
|FN|43|42|33|33|
|Joint gold/30|0|0|0|0|
|Joint source/30|0|0|1|0|

C có đúng29 cặp hai lượt +1 call stage1 thất bại enum tại SYN-COUNT-0012;
không retry/alias/fallback, không output giả. Raw còn nguyên, không gọi lượt2
cho ID lỗi. Status manifest giữ đủ30. C và replay chỉ có
`completed.predictions.json`29 record, không có `predictions.json` giả đủ30.
Không có findings=[] trên29 detector parse thành công: nhánh clean renderer mới
chỉ có kiểm tra fixture, không có empirical clean-branch success của Qwen trong
run này. Stage1 taxonomy valid29/30; lượt2 không đổi union nên metrics final bằng stage1
trong run này. Micro tăng nhờ thêm TP, nhưng FP cũng tăng và exact giảm; union
nhất quán chỉ là hợp đồng cấu trúc, không phải chứng nhận chẩn đoán đúng.

|Nhóm|Gold support|R15 TP/FP/FN;F1|C-old TP/FP/FN;F1|C mới TP/FP/FN;F1|
|---|---:|---|---|---|
|Lỗi biên dịch|5|3/2/2;0.6000|4/9/1;0.4444|2/4/3;0.3636|
|Lỗi nhập/xuất|3|3/1/0;0.8571|2/0/1;0.8000|3/0/0;1.0000|
|Lỗi logic|7|3/9/4;0.3158|3/12/4;0.2727|4/16/3;0.2963|
|Lỗi vòng lặp|10|1/0/9;0.1818|0/0/10;0.0000|8/2/2;0.8000|
|Lỗi mảng/chuỗi|8|0/2/8;0.0000|2/0/6;0.4000|2/9/6;0.2105|
|Lỗi hàm|3|0/0/3;0.0000|0/0/3;0.0000|0/0/3;0.0000|
|Lỗi edge case|6|0/0/6;0.0000|0/0/6;0.0000|0/0/6;0.0000|
|Lỗi thuật toán|2|0/0/2;0.0000|0/0/2;0.0000|0/0/2;0.0000|
|Lỗi hard-code|3|0/0/3;0.0000|0/0/3;0.0000|1/1/2;0.4000|
|Lỗi style|6|0/0/6;0.0000|0/0/6;0.0000|0/0/6;0.0000|

**Hard-code còn FN2/3 theo gold; mảng/chuỗi FN6/8, FP9.** Không chờ đọc
feedback mới thấy các nhóm này chưa đạt. Logic FP16; compile TP2 vẫn chưa chứng
minh model tìm đúng nguyên nhân compile, như finding review bên dưới chỉ ra.
Bốn nhóm hàm/edge/thuật toán/style không có TP theo gold; không ép model thêm
nhãn để tăng recall.

A chấm từng assertion stage1:82 findings gồm21 đúng (25,61%),33 sai (40,24%),
28 không đủ căn cứ (34,15%). Trong21 finding đúng,15 gán nhóm khác nhãn chính
của source reviewer (71,43%); không gộp15 lỗi nhãn này vào33 finding sai.
82 location anchors liên hệ được code, nhưng chỉ34 cause flags đúng hoặc có
phần nguyên nhân đúng; vị trí có thật không chứng minh chẩn đoán đúng.
Mixed finding có một gốc thật vẫn có thể sai tổng thể; không dùng số21 để suy
ra số reference được phát hiện.

Trên33 reference findings đã xác lập trước prediction: tìm được24, bỏ9,
recall tham chiếu24/33=72,73%; đây là reference inventory của static reviewer,
không tuyên bố gold có đủ mọi lỗi. Lỗi chính được tìm ở16/24 bài có lỗi được
xác lập, tương đương16/30 toàn tập. C vẫn báo findings ở6/6 bài source-clean trong
phạm vi; đây là FP theo reference, gồm sai hoặc thiếu căn cứ như đã tách. Trong3 gold-clean, cả3 cũng có finding; không phải mọi finding đó đã
được feedback nhắc cụ thể ởL1.

|Nhóm theo reference nguồn|Reference support|Được phát hiện|Bỏ sót|
|---|---:|---:|---:|
|Lỗi biên dịch|5|0|5|
|Lỗi nhập/xuất|1|1|0|
|Lỗi logic|0|0|0|
|Lỗi vòng lặp|11|8|3|
|Lỗi mảng/chuỗi|9|8|1|
|Lỗi hàm|1|1|0|
|Lỗi edge case|0|0|0|
|Lỗi thuật toán|0|0|0|
|Lỗi hard-code|6|6|0|
|Lỗi style|0|0|0|

Phân biệt detection và label:6/6 reference hard-code được chạm đến, nhưng nhiều
finding bị gán Logic; đó không phải hard-code taxonomy đạt. Với mảng/chuỗi,
8/9 reference được phát hiện, nhưng vẫn bỏ lỗi chỉ số của SUMPAIR-0012 và mắc
9 FP nhãn theo gold. Đặc biệt bỏ **cả5/5** reference thiếu dấu kết thúc khai báo;
model thường bịa lỗi compiler khác và đôi khi tình cờ trúng nhãn gold. Ba lỗi
vòng lặp bị bỏ ở MAXARR-0010,RANGE-0012,GEN-0021. Bài unresolved cũng chịu FN.

Reviewer B kiểm32 finding thuộc12 ID:7 đúng,14 sai,11 không đủ căn cứ;
A trên cùng subset là7/13/12. Có1 bất đồng verdict,1 bất đồng label_correct và9
finding bất đồng ít nhất một field. Giữ cả hai review; số chính82 ở trên là A,
không tuyên bố82 finding được hai người đồng thuận. Attribution cũng khác ở
một claim mới của SUMPAIR-0017 (A có1,B có0); không đổi paired reviews hoặc gold.

## Lượt2, faithful và đúng theo nguồn

|Trục, toàn bộ30 ID|R15|C-old|C mới|Replay renderer cũ|
|---|---:|---:|---:|---:|
|Factual|11|9|14|16|
|Lỗi chính được phản ánh|13|12|19|14|
|Đúng Level|15|12|17|12|
|Vai tự nhiên|17|6|25|4|
|False claim|18|21|15|13|
|Gọi bạn|10|23|4|24|
|Tự xưng mình/thầy/tôi|0|9|0|9|
|Meta|3|0|0|1|
|Placeholder-only|3|1|6|2|
|Feedback pass|3|1|6|1|

|Mức, mỗi mức10 ID|R15|C-old|C mới|Replay renderer cũ|
|---|---:|---:|---:|---:|
|L1 leak|1/10|5/10|2/10|7/10|
|L2 leak|6/10|5/10|3/10|3/10|
|L3 có hướng sửa đúng/hữu ích|3/10|2/10|5/10|3/10|

L3 có10 bài source-error, C chỉ9 complete:5/10 trên mẫu số khóa,5/9 nếu chỉ
complete (bảng phụ). Hướng sửa có ích không tự làm cả feedback factual/đúng vai;
C vẫn chỉ2/10 L3 đạt toàn bộ Level và1/10 feedback-pass.
L2 false claims C8/10, so R156/10 và C-old7/10: giọng tốt hơn che được rất ít
lỗi nội dung ở mức này. C L1 leak2/10 tệ hơn R151/10; C L2 leak3/10 thấp hơn
R156/10 và C-old5/10, nhưng chưa hết sửa ngầm.

Attribution A:21/30 faithful với findings (21/29 trong complete), trong khi
factual chỉ14/30 theo paired review bảo thủ. Có13 false assertions kế thừa ở7 ID
và8 false assertions mới ở8 ID;2 ID thuộc cả hai nhóm, union13 ID. Năm chẩn đoán
mới ở5 ID vi phạm ranh giới renderer. Một phần false claim mới là cách sửa nguy
hiểm/khẳng định storage/compile/loop, không chỉ tên lỗi mới.

False-claim paired có15 ID, khác union13 attribution: RANGE-0013-L4 và
COUNTEVEN-0012 còn bị paired review đánh unsupported/unresolved-domain claims,
trong khi attribution A không gọi là material-false assertion. Giữ khác biệt
định nghĩa/nhận định này, không ép hai lớp thành cùng metric. Nhận định đúng
nhưng ngoài findings vẫn là lỗi faithful; nhắc trung thành finding sai vẫn sai
với nguồn. Không dùng faithful21 để báo factuality21.

Vai cải thiện rõ: gọi bạn từ10/30 R15 và23/30 C-old xuống4/30; tự xưng0/30,
meta0/30, vai tự nhiên25/30. Tuy nhiên placeholder-only tăng tới6/30. Không có
joint-gold win (đều0); source-joint C1/30 chỉ là cột riêng, không thay0/30 chính.
So replay projection, C có vai25 so với4 và Level17 so với12 tốt hơn nhưng factual14 thấp
hơn16; khác input metadata như đã nêu nên không quy toàn bộ cho văn phong.

## Từng ID và ví dụ

Bảng đầy đủ có lỗi chuẩn, finding bỏ/nhầm, lỗi nhãn, inherited/new,
Level/voice/joint và tranh luận ở
`outputs/task3/two-pass-findings-v1-20261023/per-ID-review-table.private.json`.
`status-manifest.private.json` luôn có đủ30 ID. Bảng dưới chỉ tóm tắt, không
đưa source/feedback đầy đủ lên Git. Nhãn:BD biên dịch,IO nhập/xuất,LG logic,
VL vòng lặp,MC mảng/chuỗi,H hàm,E edge,TT thuật toán,HC hard-code,S style.
J là joint-gold của R15/C-old/C; Csrc là joint-source C.

|ID SYN-|Family|Code SHA8|L|C status|Gold|C predicted|TP/FP/FN|J A/old/C;Csrc|
|---|---|---|---:|---|---|---|---|---|
|COUNT-0002|COUNT|aac63d7f|1|resolved|[]|LG|0/1/0|0/0/0;0|
|COUNTEVEN-0001|COUNTEVEN|86d1b676|1|resolved|[]|BD,LG,MC|0/3/0|0/0/0;0|
|GEN-0002|GEN|eca74a77|1|resolved|[]|LG,MC|0/2/0|0/0/0;0|
|MAXARR-0002|MAXARR|ed5add97|1|resolved|IO|IO|1/0/0|0/0/0;0|
|MAXARR-0008|MAXARR|3f5d48d3|1|resolved|VL,HC|VL|1/0/1|0/0/0;0|
|MAXARR-0010|MAXARR|954ee5b4|1|resolved|LG,VL|LG|1/0/1|0/0/0;0|
|POWER-0002-L3|POWER|a0f98d76|1|resolved|IO|IO|1/0/0|0/0/0;0|
|POWER-0007-L2|POWER|e743c37c|1|resolved|BD|LG|0/1/1|0/0/0;0|
|RANGE-0012|RANGE|bcbb9335|1|resolved|LG,VL|LG|1/0/1|0/0/0;0|
|RANGE-0013-L4|RANGE|0e4fa413|1|resolved|LG,VL|BD,VL,MC|1/2/1|0/0/0;0|
|COUNT-0011|COUNT|4a0f6035|2|resolved|BD|BD,LG,MC|1/2/0|0/0/0;0|
|COUNTEVEN-0012|COUNTEVEN|6c3f0255|2|resolved|MC,H,S|LG,VL|0/2/3|0/0/0;0|
|GEN-0017|GEN|2944a068|2|resolved|H,S|LG,MC,HC|0/3/2|0/0/0;0|
|MAXARR-0008-L3|MAXARR|3f5d48d3|2|resolved|VL,HC|VL|1/0/1|0/0/0;0|
|POWER-0002|POWER|a0f98d76|2|resolved|IO|IO|1/0/0|0/0/0;0|
|RANGE-0004-L3|RANGE|ea46bd20|2|resolved|MC,E,S|LG,MC|1/1/2|0/0/0;0|
|RANGE-0011|RANGE|6764a4b6|2|resolved|MC,E,TT|LG|0/1/3|0/0/0;0|
|SUMPAIR-0005|SUMPAIR|78025d9a|2|resolved|MC,E,S|LG|0/1/3|0/0/0;0|
|SUMPAIR-0017|SUMPAIR|86839484|2|resolved|BD|LG,MC|0/2/1|0/0/0;0|
|SUMPAIR-0021|SUMPAIR|cefed4b3|2|resolved|LG,VL|BD,VL,MC|1/2/1|0/0/0;0|
|COUNT-0008-L3|COUNT|2da1a83d|3|resolved|LG,VL|LG,VL,MC|2/1/0|0/0/0;0|
|COUNT-0012|COUNT|118a9290|3|unresolved|BD|UNRESOLVED|0/0/1|0/0/0;0|
|COUNTEVEN-0015|COUNTEVEN|9afc0902|3|resolved|HC|HC|1/0/0|0/0/0;0|
|GEN-0021|GEN|46c7d53d|3|resolved|LG,VL|BD,LG,VL,MC|2/2/0|0/0/0;0|
|GEN-0026-L3|GEN|21bb1c10|3|resolved|BD|BD,LG,VL|1/2/0|0/0/0;0|
|MAXARR-0007|MAXARR|e2c206db|3|resolved|MC,S|LG|0/1/2|0/0/0;0|
|POWER-0006|POWER|befbbc3e|3|resolved|LG,VL|VL|1/0/1|0/0/0;1|
|RANGE-0004|RANGE|ea46bd20|3|resolved|MC,E,S|LG,MC|1/1/2|0/0/0;0|
|SUMPAIR-0011|SUMPAIR|02ad1263|3|resolved|MC,E,TT|LG|0/1/3|0/0/0;0|
|SUMPAIR-0012|SUMPAIR|d5e8c1bb|3|resolved|VL,MC,H,E|LG,VL|1/1/3|0/0/0;0|

- POWER-0006: C nhận được lỗi không tiến vòng lặp, đưa hướng sửa khả thi;
  R15/C-old bỏ hoặc chẩn đoán khác. C đạt source-joint, nhưng gold gán nhóm khác
  nên không đạt joint chính. Không đổi gold vì ví dụ đẹp.
- MAXARR-0010: C viết L1 phù hợp hơn C-old và được feedback-pass, nhưng detector
  vẫn bỏ lỗi không tiến vòng lặp. Lời nhắc tốt không cứu finding/taxonomy.
- GEN-0026-L3: C bỏ lỗi khai báo thật; renderer rơi vào nhận xét chung, không có
  hướng sửa chẩn đoán đúng. Factual trục hẹp tốt hơn R15 không có nghĩa L3 đạt.
- COUNT-0008-L3: detector bịa thiếu cấp phát và sai đếm; renderer lặp cả hai.
  Đây là lỗi kế thừa, dù vai nói với sinh viên đã khá hơn.
- SUMPAIR-0012: kế thừa nhận định thiếu return và sai chỉ số không có thật;
  còn thêm chẩn đoán vòng lặp ở routine chỉ gọi hàm. C tệ hơn R15/C-old về
  factuality trên ID này, không sửa feedback sau review.
- SUMPAIR-0011: C nhận được các lỗi traversal/index thật và hướng sửa hữu ích,
  nhưng không đạt mọi điều kiện Level/giọng/taxonomy; không tính là joint win.

Casebook cũ chỉ dùng smoke/source audit, không thêm vào tập chọn candidate.
MAXDIFF-0008 mở sai tên file là I/O/hard-code boundary, không tự là compiler;
GCDARR-0009 có static invalid main và cận cố định độc lập; COUNTGT-0005 có
arr[n] được cấp phát nhưng chưa nạp, không phải allocation overflow; SUMEVEN-0000
thực sự cập nhật tổng nên chẩn đoán cũ sai. FACT-0008 thiếu kết thúc khai báo,
DIGITSUM-0007 lệch đối số, REVSTR-0007 sai vị trí ghi; BASE2-0007 có thêm lần đọc
input chứ không chỉ một hằng số; COUNTVOWEL-0010 cần hướng sửa thật ởL3;
FACT-0001 đúng trong miền0..20, không có cơ sở bịa tối ưu. Tất cả10 case được
đối chiếu đúng historical task hash trong `casebook-analysis.private.json` và
raw/rendered index; không dựng lại kết quả cũ từ hội thoại. Trên toàn bộ16/12
artifact, chỉ15/16 và11/12 source trùng raw hiện tại, nên không reuse theo ID.

## Chi phí và verification

|Arm|Fresh calls|Stage1/one-pass calls|Stage2 calls|Input tokens|Output tokens|Generate latency s|
|---|---:|---:|---:|---:|---:|---:|
|A|40|40|0|34,610|3,054|38.614|
|C-old|60|30|30|54,508|4,481|57.192|
|C|59|30|29|62,420|9,706|118.666|
|renderer-ablation|29|0|29|31,951|2,725|35.020|

Tổng188 fresh calls,183.489 input tokens,19.966 output tokens,249,492s generate;
load10,219s riêng. A40 gồm10 retry thêm theo original controller,3 fallback;
không đổi R15 thành một prompt-only arm mới. C59 gồm30 detector+29 renderer;
không retry/fallback. Exploratory replay29 fresh renderer,29 stage1 cache khả
dụng trong30 ID được yêu cầu (1 unavailable). Trường cost.replayed_stage1=30
trong JSON biểu thị toàn bộ ID được cấu hình yêu cầu replay, không phải30 call
model hoặc30 parsed cache thành công. Không có reservation bị gián đoạn, không
length/context failure;1 enum failure của C. Không cộng replay vào fresh calls.

Thời gian từng lượt nằm trong cost.by_stage và trace, tổng trên là tổng latency
các generate, không phải wall-clock deployment benchmark. C stage1 verbose làm
cost tăng; không quy cost/quality khác biệt chỉ cho đại từ.

Validator chính thức: R15/C-old VALID30; C/replay VALID29 trên đúng complete-ID
Level map. Dùng map30 với C29 bị từ chối đúng vì thiếu ID; không gọi partial run
là submission hoàn tất. Trace audit xác nhận29 feedback giữ nguyên chuỗi,59 call
đúng thứ tự mỗi ID và2 generate trên mọi sample mới thành công.

66 test mới pass;120 test liên quan mới+cũ pass. Full Task3 **1515 passed,
5 skipped,1 failed**. Failure có sẵn:
`test_task3_eval_v2.py::test_v2_plan_preserves_v1_and_does_not_read_prediction_or_public_inputs`;
baseline kỳ vọng root predictions SHA `9ba741…`, HEAD ban đầu đã là `c30c5c…`.
Không sửa baseline hoặc predictions. Bare pytest có2 collection errors Task1
(`test_clm_zeroshot_task1`, `test_task1_clm_probe`) vì thiếu sklearn; không cài
hoặc sửa Task1/2. Fixture chỉ chứng minh runner/parser/template, không chứng
minh model tuân thủ Level.

Independent code audit trước freeze phát hiện và sửa metadata lồng nhau,
binding prepared exam, dependency/accounting hashes, Level lookup, stage1-None,
thứ tự ID, attribution indices/type và status/output inconsistency. Các bug có
RED→GREEN logs riêng, không chỉnh prompt sau model. Đã hash kiểm422.893 file
cũ nguyên vẹn. Git chỉ có code/config/tests/plan/report tổng hợp; raw code/gold
feedback vẫn ignored. Không push.

## Quyết định

1. Xưng hô tự nhiên hơn nhưng còn4/30 gọi bạn; tự xưng/meta0/30. Vai đạt25/30
   không bù placeholder6/30 hay factual14/30.
2. Detector còn33 finding sai,28 thiếu căn cứ;15/21 finding đúng gán nhóm sai
   theo reference chính. Hard-code vẫn FN2/3 và mảng/chuỗi FN6/8 theo gold;
   source-level HC detection6/6 nhưng label chưa đúng, MC bỏ1/9. Năm lỗi compile
   nguồn đều bị bỏ dù có2 gold compile TP tình cờ.
3. Micro/macro tốt hơn R15/C-old, exact4/30 thấp hơn8/30 và6/30; joint chính
   vẫn0/30. Thay đổi taxonomy thuộc detector mới, không phải riêng sửa giọng.
4. Stage2 có lỗi kế thừa lẫn tự thêm:13 assertions/7 ID và8 assertions/8 ID theo
   A;5 chẩn đoán mới. L1 leak tệ hơn R15, L2 giảm nhưng vẫn3/10; L3 hữu ích5/10
   tốt hơn3/10 và2/10 nhưng không đủ joint. Attribution có bất đồng, đã giữ riêng.
5. **Giữ R15, tiếp tục sửa detector và renderer trong một yêu cầu thí nghiệm
   mới.** Chưa đủ bằng chứng chuyển sang đánh giá nội bộ độc lập hơn hoặc public.
   Phần implementation và đánh giá Qwen/review đã hoàn tất; chất lượng chưa đạt.
   Giới hạn: development seen/clone, source/gold dispute, static evidence, L4
   chưa đánh giá, agent review chưa human-validated, exploratory replay không
   giữ nguyên toàn bộ structured-finding metadata.
