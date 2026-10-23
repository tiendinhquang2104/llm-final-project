# Task 3 compact diagnosis: preflight dừng ở P1 — 23/10/2026

**Giữ R15. Không chạy P2, evaluation mới hoặc public inference.** P1 v1 và v2
đều0/8 diagnosis dùng được, dù đã có một lần sửa contract có căn cứ. Rescue
cũng0/8. Không đổi uncertainty/parser failure thành[] để đủ completion. Vòng này
hoàn tất phần mềm, thử nghiệm có giới hạn, review và báo cáo âm; chưa giải quyết
được chất lượng production. Không gọi đây là cải thiện hệ thống đã được chứng minh.

## 1. Repo, phạm vi và artifacts

HEAD đầu `63a5763f7c4e0a5b1243aa6e12b802c8f804d02c`, branch
`feat/task3-quality-round5`, git status đầu sạch. HEAD cuối là commit chứa báo cáo
này; hash/status sau commit ở bàn giao và ignored `compact-20261023/handoff.private.json`.
Không clone/worktree, push, PR, training hay leaderboard upload.

File mới: `src/task3/compact{,_runner}.py`,
`scripts/task3_compact{,_renderer,_report}.py`,
`configs/task3/compact_20261023.json`, `docs/task3_compact_rulebook.md`,
`tests/test_task3_compact{,_runner}.py`, plan và hai report/aggregate này.
Không sửa module/config R15, grounded round trước, dữ liệu, gold, SFT v1 hay
raw outputs cũ. **2.734/2.734 protected hashes unchanged**.

Đã đọc source/config/runner/compiler/rulebook, label_space thực, báo cáo và
metrics gần nhất. Public contract vẫn cần cả taxonomy và feedback; không đưa
gold/teacher/Level vào diagnosis. Public chỉ kiểm SHA để bảo toàn; không dùng
nội dung source hoặc attempts public để phát triển. Tập60 cũ được dùng đúng quyền mới cho replay kỹ thuật; nó đã exposed,
không trở thành benchmark mù. Không đổi số liệu/gold của vòng trước.

Private root: `outputs/task3/compact-20261023`. Raw prompts/responses, code,
review evidence và exact runtime snapshots chỉ ở đó, không commit. Aggregate
[không chứa source/feedback/raw](TASK3_COMPACT_PREFLIGHT_METRICS_20261023.json)
giữ đủ10 nhãn, casebook và cost để kiểm số liệu.

## 2. P0 — replay offline và root cause

Không gọi model trong P0. Auditor độc lập và root đọc một raw thực tế đại diện
cho đủ8 nhóm, đối chiếu source/đề. Evaluation cũ có116 diagnosis calls:
60 first attempts+56 second attempts;111 rejected calls=56 first+55 second.
**5 resolved samples,55 unresolved samples**, không phải111 bài lỗi.
Development cũ có16 calls/16 rejects,0/8 resolve. Đây là first-reject categories;
mỗi raw có thể còn nhiều lỗi khác bị che bởi lỗi đầu tiên.

Audit private SHA
`8ac6f9495f446d479d399615aa7541d700ef54b87956621bba60a6270dc03dbc`;
có attempt key, raw/prompt/source/journal hashes, excerpts private và nhận định.
Không suy ra tỷ lệ lỗi ngữ nghĩa toàn nhóm từ một đại diện.

| Reject calls | Trường / A: cần model suy luận | B: runner tính | C: sửa cú pháp không đổi nghĩa | D: vẫn phải từ chối; ví dụ đã ẩn source |
|---:|---|---|---|---|
|43|status/confidence; lỗi có thật và đủ căn cứ?|Bỏ confidence/disputed trùng lặp; derive trạng thái từ verdict và findings đã screen, giữ uncertainty|Không tự đổi uncertain thành error|ARM0000 nói khởi tạo tích bằng1 không thể tính lũy thừa, dù vòng nhân làm đúng. Không hợp thức hóa bằng cách flip status.|
|18|finding thuộc yêu cầu nào?|Schedule từng PID có thật; tính assessed/unassessed/blocked|Scope toàn bài single là metadata; giữ location prose riêng, không lấy làm PID|COUNTGT0000 nói stream không được dùng dù source có đọc từ stream. Sửa coverage không cứu nhận định sai.|
|17|chọn nhóm lỗi|Kiểm enum, union nhãn, primary/secondary/support map|Chép đúng enum; không đổi syntax/E1/Logic thành nhãn chính thức bằng alias|BASE20000 phê biểu diễn số0 đúng và đề xuất trả chuỗi rỗng; vừa sai nhãn vừa sai nội dung.|
|13|anchor và lời giải thích hiện tượng|Match source, active region, offset/span/hash|Chỉ token-whitespace khi giữ token/literal và không có ngữ cảnh preprocessing nhạy cảm|ARM0027 phê nhân lặp vốn đáp ứng yêu cầu không dùng pow; không fuzzy-match quote rồi chấp nhận nguyên nhân sai.|
|9|mốc nguồn hoặc vị trí nếu không trích được|Không có mốc kiểm được thì giữ candidate_unverified, log và retry|Không tự chế quote còn thiếu|ARM0027 hiểu yêu cầu parser “trích dẫn” thành yêu cầu bài sinh viên phải có một trích dẫn.|
|5|quote thực sự hỗ trợ hành vi?|Phân biệt code/comment/literal, giữ offset đúng|Không chuyển comment thành executable code|DISTINCT0001 nói sort làm mất giá trị phân biệt; comment naming algorithm không phải bằng chứng đó.|
|5|P1 có lỗi được hỗ trợ hay chỉ nghi vấn?|Policy từ đề; P1 defect được screen mới block câu sau; P1 unknown giữ unassessed|Không bắt model serialize danh sách blocked|MAXDIFF0007 bịa lỗi thiếu kiểm file-open; không coi nghi vấn là P1 failure đã xác nhận.|
|1|generation còn đủ nội dung?|Parser ghi truncation/failure|Chỉ bỏ một fence hoàn chỉnh|PRIME0010 lặp văn bản tới token limit, chưa đóng JSON. Không phải wrapper vô hại; không nối ngoặc hay mine nhãn từ prefix.|

Case mixed MINA0004 cho thấy một finding độc lập có thể đúng trong khi hai
finding khác sai. Parser mới giữ positives tốt và log phần bị loại; điều này
**không chứng minh đầy đủ taxonomy**, không cho phép chuyển global uncertainty
thành clean. Các đại diện ngữ nghĩa không được đưa làm few-shot inference.

## 3. Contract/runner mới và rescue

Model chỉ sinh `verdict`, `reason`, findings gồm quote/observed/conflict/when/
labels, optional location/overlap_reason. Runner gán ID, span và source hash,
compiler/test availability, requirement/PID, support projection và prerequisite
scheduling. Trạng thái: confirmed_findings, candidate_unverified,
reviewed_no_error_found, generation_or_tool_failure. “Confirmed” ở đây vẫn là
model assertion đã kiểm provenance và qua một Qwen screen fallible, không phải
semantic proof hoặc human verification.

Chỉ reviewed_no_error_found có lý do, không positive claims và qua model clean
check mới có thể xuất[]. Parse/tool/uncertainty không thành clean. Findings sai
bị loại riêng; một finding tốt không bị hủy vì optional finding khác sai. Một
finding được hai nhãn nếu có rationale riêng cho từng nhãn trong allowed overlap,
primary/secondary ghi trace và semantic screen kiểm lại; không tự cộng Logic.
Chưa có accepted production finding để đo hiệu quả overlap trên dữ liệu thật.

Multi_problem dùng metadata schedule từng PID, tối đa hai attempts/PID; không
bắt model chứng minh coverage toàn bộ trong mỗi response. Empty/duplicate PID
metadata bị từ chối. P1 supported defect theo policy đã biết block P2–P4; P1
unknown giữ các câu sau unassessed, không xác minh chúng như unconditional clean.
P1 preflight thực tế chỉ single_problem nên phần này mới kiểm bằng fixture,
không được quảng cáo là đã đo trên multi_problem.

Compiler g++ hiện **có** trong Docker; docker/bwrap hoặc compiler isolation đáng
tin chưa có. Compiler helper hiện tại dùng syntax-only subprocess nhưng chưa
cô lập filesystem/resource đầy đủ cho source không tin cậy. Không gọi nó trên
bài sinh viên; ghi executable-present/isolation-unavailable, compiler evidence
unavailable, tests not_run. Không thực thi C++, không model-generated expected
output hoặc claim đã compile/test. Fixture C++ trong test là nhân tạo.

Rescue được đăng ký trước: cùng Qwen với prompt R15 direct, tối đa hai attempts,
strict schema/lexical disclosure, tái dựng source support rồi semantic support/
Level guard. Không gọi legacy R15 placeholder controller; output giữ origin
grounded/rescue. Multi_problem direct rescue hiện fail-closed nếu chưa xây được
per-scope support, không giả đủ coverage. Đây là giới hạn phần mềm, chưa được
đo bởi P1. Không file submission khi thiếu ID.

L1 mới có topic dẫn từ statement và trạng thái/giới hạn; không source, vị trí,
biến hoặc cause. L2 có diagnosed behavior/cause và span, không repair field;
semantic screen kiểm cả sửa gián tiếp. L3 có repair hoặc suy hướng sửa từ
diagnosis; L4 được giải pháp nhưng không bắt full code. Mọi câu khẳng định lỗi
có finding ID trong private trace. Oracle provenance bị production từ chối.

## 4. P1 và quyết định dừng P2

Khóa đúng8 ID cũ/5 family trước code mới, SHA
`0be1d906812193388ff53da761cca73e720427c702c950bbcb67cc2585c7a301`.
Tất cả synthetic, single_problem; L1/L2/L3=2/4/2. Real n=0, metrics N/A.
Không gọi đây là tập đánh giá sạch hoặc kết luận chất lượng nhãn hiếm nói chung.

| sample_id | Level | Source-only reference A/B | Diagnosis v1 | Diagnosis v2 | Final+rescue v2 |
|---|---:|---|---|---|---|
|SYN-COUNTVOWEL-0010|3|Compile, A/B đồng ý|unverified|unverified|unresolved|
|SYN-MAXARR-0010|1|Loop, A|unverified|unverified|unresolved|
|SYN-MAXARR-0011|2|Compile, A/B đồng ý|unverified|unverified|unresolved|
|SYN-PALIN-0015|2|Logic + I/O, A|unverified|unverified|unresolved|
|SYN-PALIN-0017|3|Logic + I/O, A/B đồng ý|unverified|unverified|unresolved|
|SYN-PALIN-0019|2|Compile, A|unverified|unverified|unresolved|
|SYN-POWER-0007|2|Compile, A/B đồng ý|unverified|unverified|unresolved|
|SYN-UPPER-0005|1|Array/string, A|unverified|unverified|unresolved|

V1 có16 diagnosis calls:15 error verdict,1 uncertain, nhưng labels/scope không
đạt contract. Phần mềm/prompt v2 sửa **một lần có căn cứ**: bỏ scope machine-known
khỏi required model fields, giữ descriptive location nonauthoritative, reject PID
sai; prompt ngắn và enum nguyên chuỗi. Không map synonyms hoặc bịa source.

V2 có16 diagnosis calls:14 uncertain,2 error;9 calls không findings. Các positive
claims còn thiếu condition/fields hoặc là lời sai về source. Không nâng chúng
thành accepted findings. Chỉ0/8 vượt diagnosis gate; semantic diagnosis checker
chưa được gọi trong production preflight vì không có publishable parse để kiểm.
Rescue mỗi variant thử8/8 bài,16 direct calls +6 support calls;0 thành công.
Không gọi phần rescue là thành công của grounded diagnosis.

**P2: không chạy,0 ID generated. P3/evaluation mới: không mở.** Đã dùng đủ hai
phiên bản prompt và một lần sửa contract theo giới hạn. Không tiêu thêm GPU cho
một bảng0/20 hoặc0/60; không âm thầm thêm prompt thứ ba. Raw/code snapshots của
cả hai variants được giữ riêng, không chọn best response theo từng bài.

### Taxonomy/feedback trên cùng8 ID, mẫu số đầy đủ

Control tái dùng byte-identical R15 outputs trên8 source từ vòng trước; không
resample control và không có fresh C0 model calls. Vì đây development và control
được reuse, không phải fresh paired evaluation. Production G=grounded,
GR=grounded+rescue; v1 cùng0/8 như v2.

| Arm | Hợp lệ | Macro-F1 đủ10 | Micro-F1 | Exact /8 | Explicit[] | False-clean gold / source A |
|---|---:|---:|---:|---:|---:|---:|
|R15|8|0,171429|0,666667|3|1|1 /1|
|G v2|0|0|0|0|0|0 /0|
|GR v2|0|0|0|0|0|0 /0|

Unresolved vẫn mang mọi gold-positive FN; không exact-clean credit. Zero false
claims/leaks trên nhánh không output **không phải safety evidence**. Không so
candidate trên completed subset. Source-A taxonomy riêng: R15 macro0,152381,
micro0,588235,exact3; G/GR0. Gold khác source reference ở MAXARR0010 (gold thêm
Logic); giữ nguyên cả hai và rationale, không sửa gold. Không human adjudication.

| Nhãn | Support gold | R15 TP/FP/FN | R15 F1 | G và GR TP/FP/FN, F1 |
|---|---:|---|---:|---|
|Lỗi biên dịch|4|3/0/1|0,857143|0/0/4;0|
|Lỗi nhập/xuất|2|0/0/2|0|0/0/2;0|
|Lỗi logic|3|3/1/0|0,857143|0/0/3;0|
|Lỗi vòng lặp|1|0/0/1|0|0/0/1;0|
|Lỗi mảng/chuỗi|1|0/0/1|0|0/0/1;0|
|Lỗi hàm|0|0/0/0|0|0/0/0;0|
|Lỗi edge case|0|0/0/0|0|0/0/0;0|
|Lỗi thuật toán|0|0/0/0|0|0/0/0;0|
|Lỗi hard-code|0|0/0/0|0|0/0/0;0|
|Lỗi style|0|0/0/0|0|0/0/0;0|

Review A cho R15:main covered2/8,false claim4,inconsistent4,Level noncompliant5,
natural8,generic3; L1 leaks0/2,L2 repair leak1/4,L3 actionable1/2.
Strict joint0/8, proxy cũ cũng0/8. G/GR strict joint0/8 vì unresolved8/8, mọi
feedback-specific observable denominator bằng0. Review này độc lập với review
cũ; khác một số nhận định không được dùng để sửa metric vòng trước.

Family counts:COUNTVOWEL1,MAXARR2,PALIN3,POWER1,UPPER1; aggregate có đủ casebook
để tái tính theo family/Level, không suy rộng từ n nhỏ này.

## 5. Renderer trên CÙNG reviewed findings — oracle, không production

Reviewer A source-only8 cases trước mọi output/gold, reviewer B chấm trùng4 ID
định trước. Source taxonomy agreement4/4, không phải human verification hay
đảm bảo agreement trên dữ liệu mới. Không có combined preview như vòng trước.
Sau source seal mới cấp output packets đã ẩn tên nhánh/xáo thứ tự; reviewer không
nhận generator findings/rationale hoặc guard decisions.

Oracle dùng đúng findings của A cho cả C1/C2. Tám original Levels và thêm L4 trên
hai index đã định0,3 thành10 paired cases/8 distinct sources,2/4/2/2 theo Level.
Đây là oracle isolation trên development; không đưa findings/gold oracle vào
production và không gọi taxonomy oracle F1 là production performance.

| Oracle feedback, mẫu số10 | C1 full task/findings | C2 isolated view + guard |
|---|---:|---:|
|Completed|8|3|
|Main error covered (A)|7|2|
|False claims (A)|1|3|
|Taxonomy/feedback inconsistent (A)|1|0|
|Level noncompliant (A), completed only|2|0|
|Natural / generic|8 /1|3 /0|
|L1 leak / observable|0/0|0/0|
|L2 repair leak / observable (A)|0/4|0/1|
|L3 actionable / observable (A)|1/2|0/0|
|Old joint proxy A /10|5|0|
|Strict joint A /10|5|0|
|Conservative strict joint /10|4|0|

Strict joint gồm source-supported taxonomy, main coverage, no false claim,
consistency, đúng Level, **non-generic và natural**. Proxy cũ giữ nguyên code,
báo riêng. Conservative withholding credit khi reviewer trùng ca bất đồng, không
tự tính disputed thành pass. Theo A:C1 thắng C2 ở5 cặp,thua0,hòa5; đây không phải
bằng chứng pipeline production thắng R15.

Overlap output review có22 slots, kể cả unresolved; một số khác biệt rubric trên
unresolved là cách ghi nhãn thiếu, không quan sát được chất lượng câu chưa sinh.
Giữ A/B riêng trong aggregate. B coi việc nêu chính xác dấu chấm phẩy còn thiếu
ở L2 là implicit repair; A coi đó là mô tả nguyên nhân được phép. PALIN0017 còn
bất đồng về câu diễn đạt nhánh/literal được làm rõ bởi câu sau. Không sửa câu,
đổi nhãn hoặc chọn reviewer thuận lợi để tăng pass; giữ disputed conservatively.

### Guard false accept/reject

Reviewer A chấm29 renderer attempts, không nhìn guard verdict. Trong11 C2 calls
đã thực sự đi qua semantic guard:3 false accept,0 false reject theo A,8 true
reject; không có acceptable-positive trong11 này nên **không ước lượng được
sensitivity**. Regex/schema rejects trước guard báo riêng, không gộp thành
semantic decisions. Reviewer đánh giá cả claim sai/cause lệch, không chỉ code fence.

Tám policy fixtures nhân tạo không dùng làm few-shot:3 hợp lệ,5 vi phạm.
Qwen guard reject cả8 → **3 false reject,0 false accept**, parse failure0.
Reviewer B độc lập đồng ý expected acceptance8/8 trước khi thấy model verdict.
Fixtures cho thấy guard có thể quá chặt; generated feedback cho thấy nó vẫn có
false accept. Không tối ưu guard/prompt theo các kết quả này rồi rerun lại.

## 6. Một số ca đối chiếu, không chép source vào Git

Exact source/feedback quotes và lý do ở private output-review-a/b và guard-review-a;
bảng này chỉ diễn giải. Không chạy C++ để chứng minh các nhận định.

| ID / Level | Quan sát và giới hạn |
|---|---|
|SYN-COUNTVOWEL-0010 /3|R15 bịa vấn đề delimiter; diagnosis mới không resolve. Oracle C1 chỉ chẩn đoán thiếu dấu kết thúc khai báo mà chưa hướng sửa L3; A/B khác nhau về độ actionable.|
|SYN-COUNTVOWEL-0010 /4 oracle|C1 được A/B hỗ trợ. C2 hướng dẫn thêm dấu phẩy thay vì dấu chấm phẩy nên A xác nhận false claim; guard vẫn accept. B khác diễn giải usefulness, giữ bản review riêng.|
|SYN-MAXARR-0010 /1|C0 lời nhắc chung bỏ lỗi vòng lặp; G/GR unresolved. Gold thêm Logic vào Loop trong khi A chỉ Loop; không chỉnh gold.|
|SYN-MAXARR-0011 /2 oracle|C1 nói đúng vị trí/cause thiếu dấu kết thúc khai báo; A pass, B coi nêu token thiếu là implicit repair. Conservative không cấp pass ca disputed.|
|SYN-PALIN-0015 /2 oracle|C1 mô tả đảo kết quả và hoa/thường đúng theo A. C2 vừa nêu literal in hoa sai yêu cầu, vừa tự nêu literal đúng ở câu khác; guard accept nhưng A giữ false claim.|
|SYN-PALIN-0015 /4 oracle|C2 gán output string cho giá trị trả về bool của helper, sai cơ chế; A false claim dù Level cho phép lời giải.|
|SYN-PALIN-0017 /3|R15 wording về nhánh gây bất đồng; không coi phản hồi mượt là đúng source. Oracle C1 có hướng sửa nhưng A thấy một phát biểu literal trái đề, B cho rằng câu sau làm rõ.|
|SYN-POWER-0007 /2|R15 bịa chưa khởi tạo dù source khởi tạo. Oracle C1 chỉ nói trả lời chưa đúng, quá generic và không phủ lỗi biên dịch; C2 unresolved.|
|SYN-UPPER-0005 /1|R15[] là false-clean theo cả gold/source A. C1/C2 oracle đều không hoàn tất;0 L1 leaks/0 outputs không chứng minh an toàn.|

## 7. Model, hashes và chi phí

Qwen2.5-Coder-7B-Instruct revision
`c03e6d358207e414f1eca0bb1891e29f1db0e242`, local NF4/double-quant, BF16 compute,
CUDA0 RTX5090, seed42, greedy, không adapter/CPU offload. Runtime kiểm đúng
revision/precision; reuse HF cache/environment của round trước, không tải model
khác. Budget1024 output tokens/45s, context16384; diagnosis≤2/PID,
renderer≤2, rescue≤2 cộng source/semantic checks. No truncated input.

| Component | Calls | Input tokens | Output tokens | Generation seconds |
|---|---:|---:|---:|---:|
|P1 v1 diagnosis|16|14.019|2.805|47,854|
|P1 v1 direct rescue +support|22|16.905|2.082|33,881|
|P1 v2 diagnosis|16|11.128|1.125|19,741|
|P1 v2 direct rescue +support|22|15.855|1.963|33,150|
|Oracle renderers|29|21.996|1.852|33,399|
|Oracle semantic guard|11|6.910|540|10,193|
|Artificial guard probes|8|3.671|407|6,966|
|Tổng actual vòng này|124|90.484|10.774|185,183|

Không tính C0 reuse như fresh GPU calls; run cũ C0 có14 calls/11,930s, không cộng
vào tổng124. Model loads riêng18,187/12,949/9,874s; không lẫn generation latency.
Không quy đổi tiền khi không có billing telemetry; Codex implementation/review
cost không nằm trong token counts Qwen này.

Config SHA `be560936cc61a43c3cb88cd761f228ad92fe0117945b3ef0258b5c5c25346e68`.
Prompt bundles P1 v1/v2:
`63d3416304c22986ff84a46cd63e12e438bf664f23ceee4a7cf2e5a775d8d8e6` /
`cdc53fb3df088e07addeacaf36dd187feb2ea29ce3cd84c33ec8750634b61b6c`.
Freeze P1 v1/v2:
`b4f412a3c19ea38352758507bb6bb6e1633982db56031ba8b6ac41b2f20bb48a` /
`25c5f326f247ec5a18cb739ff22be802a1ede02bdfba0554493e189faf7ee1a8`.
Oracle freeze `acff83c209efddc645a54a992860f8fab44c0bec9750fab49dd63e28f5bf0682`.
Source seal `608d20c8d501b665dde014d12c81db2d087c161036bf271d9f0bc3b0a22bfa22`;
review seal `36c2ef6f56df36c698fbadae65f55c4a66ffdbcf493c18e413bc38e1fb2b4367`;
artifact supplement `18dce5598575c441a0721b3cb754de0ad7f4e2abec0efda9f07baf81fe409961`.
Current software hashes và các reference/hash khác có trong aggregate. Source/
raw artifact integrity, ID mapping và review quotes được kiểm trước score.

## 8. Software review, tests và replay

Code reviewer độc lập không đọc student sources, outputs hoặc gold. Phát hiện
ba Important issues trên fixture: token whitespace làm đổi exponent/compound
operator/macro; production C1 có đường bỏ semantic guard; metadata multi rỗng
do all([]) tự thành clean. Đã sửa trong một pass với reproductions RED→GREEN,
thêm literal suffix/member-pointer/preprocessing regressions. **42 tests mới
passed**; integration gate gồm R15 runner/submission/public contract/provenance:
**102 passed**.

Các sửa correctness này xảy ra **sau model runs**. Exact code của từng run đã
snapshot trước sửa; không sửa freeze/results, không tuyên bố current code đã
được model-evaluate. Không gọi model lại hoặc thêm prompt thứ ba. Production
P1 dùng C2 và single_problem; oracle C1 được phép không guard để làm ablation.
Các lỗi phần mềm vẫn đáng sửa dù không tạo winner của thí nghiệm này.

Toàn Task3: **1.361 passed,5 skipped,1 failed**:
`test_v2_plan_preserves_v1_and_does_not_read_prediction_or_public_inputs` vẫn
đòi root predictions.json theo SHA R15 lịch sử, trong khi root đã mang SFT v1
SHA từ đầu vòng trước và vòng này. Không đổi root file/hash để ép xanh.
Full pytest có2 collection errors vì thiếu sklearn trong
`test_clm_zeroshot_task1.py`, `test_task1_clm_probe.py`; không sửa Task1/2.
Logs ở `focused-tests-final.log`, `task3-tests-final.log`, `full-tests.log`.

Replay metrics không load model, một lệnh:

```bash
.venv-task3/bin/python scripts/task3_compact_report.py score
```

Kiểm exact runtime snapshot:

```bash
.venv-task3/bin/python scripts/task3_compact_report.py verify
```

Không dùng current-runtime inference verify để giả vờ code chưa đổi: nó đúng
thiết kế sẽ từ chối code drift so với old freeze. Chạy lại generation phải dùng
runtime snapshot đã lưu và một run riêng, nhưng vòng này đã hết hai prompt
versions nên không thực hiện. Code Git không kèm private data/model weights;
replay cần các private artifacts. P2 CLI có gate và không được gọi trong vòng này.

## 9. Quyết định, public và bước tiếp theo

Giữ R15 vì candidate chưa qua P1, không phải vì R15 đã đạt chất lượng tốt.
Không có mới evaluation để chọn winner, không có public inference/file mới,
không nộp thiếu ID hoặc placeholder. R15 hiện có giữ nguyên tại
`/workspace/llm-final-project/outputs/task3/round15/public-candidate-zero/predictions.json`,
SHA `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`.
Validator log328/328 của vòng trước giữ nguyên, không trình bày như mới chạy lại.
Không push, tạo PR hoặc upload leaderboard.

Blocker cụ thể: model vẫn trả uncertainty/thiếu core condition trên diagnosis,
rescue support không resolve; guard vừa false reject các câu hợp lệ vừa false
accept câu sai. Chỉ làm gọn metadata chưa đủ. Bước thử tiếp theo cần một nghiên
cứu development riêng được cho phép: tách task phát hiện vị trí/cơ chế lỗi khỏi
JSON serialization bằng constrained decoding, trước hết kiểm Qwen có phân biệt
được lỗi với clean trên source pairs nhân tạo và negative controls hay không;
đo precision/false-clean trước thêm renderer. Đồng thời kiểm guard trên tập policy
phân biệt cause/replacement, với hai reviewer giữ disputed. Không tự training,
mở20/60 evaluation hoặc đổi prompt tiếp trong vòng này.
