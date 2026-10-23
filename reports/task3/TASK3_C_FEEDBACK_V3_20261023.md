# Task 3: C-feedback-v3, giữ nguyên stage1-v1

**Kết luận: giữ R15, không tiếp tục candidate C-feedback-v3.** C-new hoàn tất12/12, false claims giảm nhưng direct-em chỉ2/12, L1/L2 leak đều vượt R15, joint0/12; không đạt gate đã khóa trước inference.

[Metrics đầy đủ](TASK3_C_FEEDBACK_V3_METRICS_20261023.json).
Branch `feat/task3-quality-round5`, HEAD ban đầu
`0e06f6e8432cb3cc850efd7a58b3a6c24737aebe`, working tree sạch.
Chỉ thay renderer C và adapter chạy/report cần thiết; không sửa R15, B, C cũ,
stage1, gold, split hoặc artifact trước đó. Không D/E, fine-tune, public inference,
candidate328, push, PR hay upload.

## Casebook trước khi sửa prompt

Đã đối chiếu source/đề, Level, stage1 notes, C raw, rendered input và hai review
cũ cho10 case yêu cầu.9 case có generate/rendered input; DISTINCT-0017 dừng
trước renderer do inconsistency. Tokenizer đúng revision dựng lại9 rendered
inputs, token counts khớp journal; không có model call cho casebook.

a=issue stage1 sai; b=stage2 thêm nhận định sai; c=giọng/người nhận;
d=vượt Level; e=placeholder/thiếu hướng sửa L3. Đây là phân tích lỗi quan sát,
không suy ra chain of thought hay dùng ID để hard-code câu trả lời.

| SYN-ID suffix | Nhóm | Nguyên nhân quan sát |
|---|---|---|
|COUNTVOWEL-0010|c,e|Note cú pháp đúng bị thay bằng một câu kiểm tra lại, thiếu hướng sửa L3.|
|UPPER-0005|c,e|Câu chung không nói với em; L1 không cần chẩn đoán chi tiết nhưng cần lời gợi ý đọc được.|
|BASE2-0007|a,b,c,d|Issue coi nhánh đặc biệt tự nó là vi phạm; feedback vừa khen đúng vừa chê sai, lộ chi tiết ở L1.|
|DIGITSUM-0007|c,d|Chẩn đoán có căn cứ rồi chỉ luôn phép thay thế ở L2.|
|FACT-0008|a,c,d|Note sai loại dấu bị chép lại; thêm thao tác sửa tại L2.|
|REVSTR-0007|a,c,d|Lặp mô tả ký tự mất thiếu chuẩn và chỉ index thay thế ở L2.|
|DIGITSUM-0001|c|Đã bỏ meta nhưng vẫn gọi bạn.|
|FACT-0001|b|Bài đúng, stage2 tự bịa tối ưu bằng cách đổi vòng lặp.|
|SUMB-0005|a,b,c,d|Biến trong comment bị coi như khai báo thật; bịa đã đọc file; chi tiết không đúng L1.|
|DISTINCT-0017|a|Stage1 [] nhưng issue Logic; unresolved, không sửa taxonomy hay viết feedback clean.|

Casebook-analysis SHA256
`4abfa9b9a84f7360cad2df84d6d4ca4292c84fb85352e6530081c0b37869b77f`.
Raw source/rendered text/notes/review chỉ ở ignored
`outputs/task3/c-feedback-v3-20261023/`, không vào Git. Không generate mới trên16 ID cũ.

## Một candidate, một tập development khác

Khóa12 ID trước prompt/generate:9 families, **khác cả ID và family** so với16
casebook; L1/L2/L3=5/4/3, L4=0;8 single/4 multi;3 original-clean.
Cả12 đã được sinh/review ở grounded60, nên là **development đã lộ**, không phải
unseen hoặc benchmark độc lập mới. Manifest từng ID/family/source hash/exposure
trong JSON metrics. Không lấy public hoặc chọn ID theo output mới.

Gold có7 nhóm support, IO/edge/style=0. Macro vẫn chia đủ10; không bỏ nhãn
zero-support. Không có clean L3 trong tập12, nên không kết luận đã sửa được
clean-L3 behavior từ tập này; casebook FACT và fixture chỉ hỗ trợ thiết kế/test.
Units SHA256 `0a1667ba435e716684ee040aef3ce222b4f3c3734f4ab70d4fc9f0e76b1dcdde`.

Giữ JSON feedback-only: C cũ parse15/15 generate thành công; lỗi quan sát là
nội dung/vai/Level, chưa có bằng chứng plain text giải quyết chúng. C-new dùng
prompt ngắn theo **đúng một Level**, chỉ đưa own official definition/cấm. Đổi
cách quy định vai từ xưng em mơ hồ sang gọi người nộp là em, không gọi bạn.
Clean branch đứng trước yêu cầu chẩn đoán/sửa; chỉ xét source đang hoạt động,
không chép issue sai/comment, không bịa execution success hay tối ưu.

L1 chỉ gợi ý chung cho em; L2 chẩn đoán token hiện có và hậu quả nhưng không
token thay thế/thao tác sửa; L3 cần hướng sửa cụ thể, đúng source, khả thi.
Không chèn few-shot/câu trả lời thực của ID. Không mẫu riêng theo nhãn/ID,
không retry/reviewer/semantic guard hoặc thay bạn→em/xóa câu sai sau generate.
Parser giữ nguyên feedback string, kể cả khi nội dung vi phạm yêu cầu.

Freeze SHA256 `aa1dd3e580a3da67b0111ae69f2426b619facb0448c3f70ddd70ccea9166bc0d`;
prompt bundle `14b7252d3f2d545c5a43b534cb2ba6cc6010ba9ebe8b899a3732861e8616990c`.
Một bản duy nhất, đóng băng trước output; không sweep/v4 hay chọn response tốt nhất.

## Stage1 và đối chứng

| Arm | Cách sinh trên cùng12 ID |
|---|---|
|A|R15 one-pass có sẵn từ đúng grounded60 request, cùng code/đề/Level;12 call lịch sử, không fallback.|
|B|Chạy mới nguyên v1 vì không có two-pass-v1 output đúng provenance cho12 ID này.|
|C-old|Renderer v2 cũ, replay stage1 B của chính ID; không dùng output casebook khác.|
|C-new|Renderer v3 mới, replay cùng stage1 B; chỉ stage2 thay đổi.|

`stage1_messages is v1.messages_taxonomy`, `stage1_parse is v1.parse_taxonomy`;
file v1/hash/prompt/model-output/parser/mapping không thay đổi. Journal proof
đối chiếu12 stage1 raw→parsed và messages byte-identical với hàm gốc. Final
taxonomy của B/C-old/C-new bằng đúng prediction B; raw feedback→final không biên tập.
Không gọi prompt taxonomy-v2 của D. Helpers v2 chỉ dùng cho renderer C cũ,
input validation và consistency, không sinh taxonomy mới.

Production helper vẫn một ID: stage1-v1→stage2-v3→save trước ID tiếp, tối đa2
generate; test kiểm cả save boundary và interrupted-call resume. Phép thử thực
tế này là **renderer ablation replay**, không phải ba pipeline end-to-end chạy
stage1 riêng. B12 stage1+12 stage2, C-old12 stage2, C-new12 stage2; một model
load,48 generate mới. Mỗi generate chỉ hai messages của đúng một ID; không batch
nhiều source, history chung, hidden third call hay fallback/hybrid.

Input metadata ngoài allowlist bị reject trước generate, không sửa stage1
payload để làm sạch ngầm. Taxonomy/issue label mismatch vẫn unresolved, không
thêm/xóa nhãn. Lần này cả36 cặp B/C-old/C-new complete12/12, mismatch0.

Runtime nguyên v1: Qwen/Qwen2.5-Coder-7B-Instruct,
`c03e6d358207e414f1eca0bb1891e29f1db0e242`, NF4 double quant/BF16 compute,
seed42, greedy, zero-shot, context16384, max1024 output tokens/45s. Không đổi
decoding/precision đồng thời prompt. Qwen2TokenizerFast cùng revision/template
SHA `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`.
Runtime xác nhận CUDA4-bit/BF16 compute; tensor không quantize FP16. Load14,024s,
peak allocated7.072GB/reserved7.212GB. Không động vào process GPU khác.

## Review và kết quả

Hai agent mới đọc12 source trước prediction/gold, ghi exact evidence và seal
trước inference. Sau đó mỗi người chấm48 output ẩn arm A/B/C-old/C-new; không
xem key/notes/raw traces/gold/old reports hoặc review của người kia. Dùng lại
rubric và combine/bind/Level validator trước, thêm trục gọi bạn và placeholder.
Review dùng đúng official Level definitions đã frozen cho inference.

Giọng trực tiếp với em được chấm ngữ nghĩa, không lấy regex em làm bằng chứng.
L1 gợi ý chung hợp lệ không bị ép cụ thể kiểu L2. Current token+consequence có
thể chẩn đoán L2; token thay thế/insertion advice là leak. Level, factuality,
vai giao tiếp, meta được chấm riêng; bất đồng không ép thành credit. Reviewer
là agent, chưa human-verified; scope caveat chung tách khỏi actual source dispute.

|Chỉ số|A: R15|B: v1|C-old|C-new|
|---|---|---|---|---|
|Complete/unresolved/fallback|12/0/0|12/0/0|12/0/0|12/0/0|
|Ngôn ngữ tự nhiên (chưa xét vai)|12/12|12/12|12/12|12/12|
|Nói trực tiếp với em tự nhiên|0/12|0/12|1/12|2/12|
|Còn gọi bạn|4/12|2/12|10/12|2/12|
|Meta|2/12|2/12|0/12|0/12|
|False claim (ít nhất một reviewer)|9/12|5/12|7/12|4/12|
|Nhắc lỗi chính / khen đúng bài clean|3/12|4/12|4/12|5/12|
|Finding được cả hai xác nhận|3/12|4/12|5/12|7/12|
|Bịa lỗi trên original-clean|0/3|1/3|1/3|1/3|
|Level đúng (cả hai)|8/12|4/12|6/12|4/12|
|L1 lộ chi tiết|0/5|3/5|3/5|4/5|
|L2 lộ sửa (union / cả hai)|1/4 ; 1/4|2/4 ; 2/4|2/4 ; 2/4|2/4 ; 2/4|
|L3 có hướng sửa khả thi|1/3|2/3|3/3|3/3|
|Placeholder-only|0/12|2/12|0/12|1/12|
|Feedback pass đầy đủ|0/12|0/12|0/12|0/12|
|Strict joint|0/12|0/12|0/12|0/12|
|Output có ambiguity thực|1/12|3/12|0/12|2/12|

|Arm|Level|n|Đúng Level|Direct em|False claim|Leak / actionable|
|---|---|---|---|---|---|---|
|A|1|5|5|0|4|0|
|A|2|4|2|0|3|1|
|A|3|3|1|0|2|1|
|B|1|5|1|0|2|3|
|B|2|4|1|0|3|2|
|B|3|3|2|0|0|2|
|C-old|1|5|2|1|3|3|
|C-old|2|4|1|0|3|2|
|C-old|3|3|3|0|1|3|
|C-new|1|5|0|1|1|4|
|C-new|2|4|1|0|3|2|
|C-new|3|3|3|1|0|3|

C-new chỉ cải thiện vai một phần: direct-em **2/12**, C-old **1/12**, R15 **0/12**; gọi bạn giảm **10→2** so với C-old, meta vẫn0. Cả12 có ngôn ngữ trôi chảy ở mọi arm, nên “natural” một mình không chứng minh đúng vai hay nội dung.

False claims giảm **9→4** so với R15 và **7→4** so với C-old; main coverage tăng **3→5** và **4→5**. Tuy nhiên L1 leak **4/5** so với R15 **0/5**, C-old **3/5**; L2 leak **2/4** so với **1/4**, **2/4**, đều được cả hai xác nhận. L3 actionable **3/3**, bằng C-old và hơn R15 **1/3**, nhưng hai L3 bỏ primary defect và một L3 có ambiguity; không đồng nghĩa ba feedback hoàn toàn đúng. Placeholder vẫn **1/12**, feedback-pass và joint đều **0/12**.

**Clean cần phân biệt gold và source.** Gold gốc có3 bài clean; cả hai reviewer trước prediction phát hiện lỗi output prompt thừa ở ARM-0000 và FIB-0000. Chỉ SUMEVEN-0000 được cả hai coi clean (trong miền số/phần tử biểu diễn được). B/C-old/C-new đều bịa lỗi trên bài này: **1/3 original-clean**, cũng là **1/1 source-clean**, R15 **0/3**, **0/1**. Không thay gold; TP/FP/FN vẫn theo gold gốc. Hai reviewer bất đồng source taxonomy ở PROD-0017 và ARM-0026; JSON lưu riêng cả hai nhãn, không chọn nhãn thuận lợi. Các caveat capacity/overflow không được tự biến thành primary defect.

Gate đã đăng ký: feedback-pass phải tăng hơn max(R15,C-old), false claims không tăng so với R15, L1 và L2 leak không vượt R15. Kết quả lần lượt **FAIL / PASS / FAIL / FAIL**. **Giữ R15, dừng candidate này; chưa đủ bằng chứng cho một đánh giá nội bộ độc lập hơn.** Tập12 đã lộ, nhỏ và tổng hợp; hai reviewer agent chưa thay được kiểm chứng con người.

Strict joint cần completed + taxonomy có căn cứ theo hai source assessments,
không source dispute + main covered/factual/consistent/Level/natural/direct-em,
không meta/placeholder/bạn. L3 thiếu hướng sửa vẫn có thể complete về schema
nhưng **không** đạt feedback/joint; không gọi câu L3 chung là hoàn tất tốt.

## Taxonomy giữ nguyên, không quy công cho renderer

|Arm|TP/FP/FN|Micro-F1|Macro-F1 (10 nhóm)|Exact|
|---|---|---|---|---|
|A|1/5/12|0.105263|0.028571|3/12|
|B|3/7/10|0.260870|0.090000|4/12|
|C-old|3/7/10|0.260870|0.090000|4/12|
|C-new|3/7/10|0.260870|0.090000|4/12|

|Nhãn|Support gốc|R15 TP/FP/FN|R15 F1|B = C-old = C-new TP/FP/FN|F1 chung|
|---|---|---|---|---|---|
|Lỗi biên dịch|2|0/0/2|0.000000|1/1/1|0.500000|
|Lỗi nhập/xuất|0|0/1/0|0.000000|0/0/0|0.000000|
|Lỗi logic|2|1/4/1|0.285714|2/6/0|0.400000|
|Lỗi vòng lặp|2|0/0/2|0.000000|0/0/2|0.000000|
|Lỗi mảng/chuỗi|2|0/0/2|0.000000|0/0/2|0.000000|
|Lỗi hàm|1|0/0/1|0.000000|0/0/1|0.000000|
|Lỗi edge case|0|0/0/0|0.000000|0/0/0|0.000000|
|Lỗi thuật toán|2|0/0/2|0.000000|0/0/2|0.000000|
|Lỗi hard-code|2|0/0/2|0.000000|0/0/2|0.000000|
|Lỗi style|0|0/0/0|0.000000|0/0/0|0.000000|

Gold gốc được giữ nguyên, hash bound trước model, chỉ mở cho scoring sau paired
seal. Stage1-only metric tính từ B cho toàn12 và dùng chung C-old/C-new;
final-output metric báo riêng. Lần này completion đều12 nên hai metric B/C
trùng nhau. C-new **không cải thiện taxonomy**, dù feedback có thể đổi.
R15 stage1 one-pass khác B; không gán chênh A→B cho stage2-v3.

## Từng ID và ví dụ

Các nhãn viết gọn: BD=biên dịch, IO=nhập/xuất, LG=logic, VL=vòng lặp,
MC=mảng/chuỗi, H=hàm, E=edge case, TT=thuật toán, HC=hard-code, S=style.
J=joint; flags đầy đủ/bất đồng/source A/B trong JSON, không có student code/raw feedback.

Flags: em=đúng vai trực tiếp; bạn=sai cách gọi; F=false claim; M=nhắc lỗi chính; L1!/L2!=leak; L3+=có hướng sửa; P=placeholder; ?=ambiguity. Không có flag em không có nghĩa là thiếu trôi chảy. J=0 ở mọi ô.

|ID (bỏ SYN-)|Level|Gold gốc|A|B|C-old|C-new|
|---|---|---|---|---|---|---|
|ARM-0000|1|∅|∅ · F|∅ · F|∅ · bạn,F|∅ · P|
|SUMEVEN-0000|1|∅|∅ · M|LG · F,L1!|LG · bạn,F,L1!|LG · em,F,L1!|
|FIB-0000|2|∅|∅ · bạn,F|∅ · P|∅ · bạn,F|∅ · bạn,F|
|COUNTGT-0005|1|MC|∅ · F|LG · M,L1!|LG · em,F|LG · M,L1!|
|GCDARR-0009|3|BD,HC|LG · F|LG · ?|LG · bạn,L3+|LG · em,L3+|
|MAXDIFF-0003|3|MC|LG · bạn,F|LG · bạn,L3+|LG · bạn,L3+|LG · bạn,L3+|
|PROD-0017|3|TT,VL,H|LG · bạn,M,L3+|LG · M,L3+,?|LG · bạn,F,M,L3+|LG · M,L3+,?|
|PERFECT-0018|2|VL,LG|LG · F|LG · F,L2!|LG · bạn,F,L2!|LG · F,L2!|
|ARM-0026|2|TT|LG · F,?|LG · F,?|LG · bạn,F|LG · F,?|
|MAXDIFF-0008|2|HC|IO · bạn,M,L2!|BD · bạn,F,M,L2!|BD · M,L2!|BD · M,L2!|
|SECONDMAX-0009|1|BD|∅ · F|BD · P|BD · bạn,M,L1!|BD · M,L1!|
|SUMEVEN-0012|1|LG|∅ · F|LG · M,L1!|LG · bạn,M,L1!|LG · M,L1!|

Các thay đổi là từng trục, chưa phải chiến thắng joint:

- **GCDARR-0009 (L3):** C-new nói với em và đưa hướng duyệt toàn mảng có căn cứ; R15 chẩn đoán nhầm cú pháp, C-old vẫn gọi bạn. C-new vẫn bỏ lỗi biên dịch chính đã được source review xác định; hướng sửa phụ có ích không đủ đạt main/joint.
- **MAXDIFF-0003 (L3):** C-new và C-old đều đưa hướng sửa phép so sánh có căn cứ, tốt hơn nhận định sai của R15. C-new còn gọi bạn và bỏ phần hàm chính chưa triển khai; không đạt joint.
- **COUNTGT-0005 (L1):** C-new nhắc đúng lỗi source mà R15/C-old bỏ sót hoặc phủ nhận, nhưng lại lộ hàm và truy cập mảng. Đúng nội dung chi tiết không phải tiến bộ hợp lệ ở L1; cả R15/C-old không leak ở ID này.
- **SUMEVEN-0000 (L1, cả hai source reviewer xác nhận clean trong miền biểu diễn):** C-new đã nói với em nhưng vẫn chép chẩn đoán sai về cập nhật tổng và lộ biến. R15 khen đúng, C-old cũng bịa lỗi. Vai tốt hơn C-old nhưng factuality và Level vẫn sai, tệ hơn R15.
- **ARM-0000 (L1, original-clean):** C-new thay lời khen sai của R15/C-old bằng đúng một câu placeholder, không nêu được gợi ý cho em. Ít false claim hơn nhưng chưa trở thành feedback hữu ích. Source review phát hiện output prompt thừa, không coi đây là source-clean.
- **PERFECT-0018 (L2):** C-new vẫn chỉ ra một phép đổi khởi tạo sai, bỏ vấn đề vòng lặp chính. R15 cũng sai chẩn đoán nhưng không lộ thao tác sửa; C-new vừa sai factuality vừa leak.
- **MAXDIFF-0008 (L2):** C-new/C-old chẩn đoán đúng tên file không khớp nhưng đối chiếu luôn tên thay thế, nên là sửa ngầm; R15 cũng leak trên ID này. Taxonomy biên dịch giữ từ stage1 không phù hợp với chẩn đoán I/O; không âm thầm đổi nhãn để đồng bộ.
- **PROD-0017 (L3):** C-new sửa được phần cộng thay vì tích, nhưng câu về cận vòng lặp có hai cách đọc. Cả hai reviewer giữ ambiguity, không chứng nhận toàn bộ nội dung đúng dù vẫn ghi nhận hướng sửa P2. Không gộp ambiguity này thành false claim chắc chắn.
- **ARM-0026 (L2):** mô tả “ghi đè” không đúng cơ chế khai báo biến che khuất; cả hai reviewer giữ nghĩa lỏng/đọc chặt là ambiguity, đồng thời chấm false claim theo cách đọc chặt. Đúng hình thức L2 không bảo đảm đúng chẩn đoán.

|C-new so với|Vai thắng/thua|Factuality thắng/thua|Main thắng/thua|Level thắng/thua|L3 thắng/thua|
|---|---|---|---|---|---|
|A|2/0|6/1|3/1|2/6|2/0|
|C-old|2/1|3/0|1/0|0/2|0/0|

Thắng/thua chỉ tính boolean thay đổi trên cùng ID của từng trục, bỏ N/A; không cộng các trục thành một điểm tổng tùy ý. Feedback-pass và joint đều không có win/loss (cùng 0/12).

Không tự sửa gold hoặc taxonomy để che câu nhận xét sai. Một output có em
nhưng chẩn đoán sai hoặc lộ sửa vẫn thất bại. Các ví dụ chỉ minh họa số liệu,
không được dùng để chọn response hoặc tạo thêm bản prompt trên tập12.

## Chi phí, kiểm chứng và bàn giao

|Arm|Call lịch sử|Call mới|Stage1 replay|Input tokens|Output tokens|Tổng generate latency (s)|
|---|---|---|---|---|---|---|
|A|12|0|0|9840|685|9.124|
|B|0|24|0|19346|1458|40.465|
|C-old|0|12|12|12162|813|23.668|
|C-new|0|12|12|10233|604|17.859|

Tổng mới:48 calls, 41,741 input + 2,875 output tokens, 81.992s generate. Model load riêng14.024s; peak allocated7,071,596,544 bytes, reserved7,212,105,728 bytes. Đây là tổng latency call đo thực tế, không gồm thời gian review/test hoặc một benchmark end-to-end triển khai độc lập.

C-old/C-new mỗi arm replay12 stage1 đã sinh ở B; không cộng replay thành fresh
calls. A là trace lịch sử, latency không phải benchmark cùng thời điểm/tải GPU.
Không có inference mới trên casebook16, không D/E hoặc evaluation tiếp sau gate.

Validator chính thức trên ba file **thật** B/C-old/C-new: VALID12, Levels5/4/3/0.
Validator chỉ chứng minh schema/ID/Level map, không chứng minh giọng/Level đúng.
16 test mới pass; suite liên quan **127 passed**. Fixture chỉ kiểm contract,
không lấy mocked output làm bằng chứng Qwen tuân thủ Level. Output Qwen thật
và review ở trên là bằng chứng ngữ nghĩa.

Full Task3:1449 passed,5 skipped,1 failed. Lỗi có sẵn
`test_v2_plan_preserves_v1_and_does_not_read_prediction_or_public_inputs` do
baseline cũ kỳ vọng root predictions R15 `9ba741…`, file root đã là `c30c5c…`
trước lượt này. Không sửa baseline/file để làm test xanh. Bare pytest vẫn có2
lỗi collection Task1 thiếu sklearn (`test_clm_zeroshot_task1`, `test_task1_clm_probe`),
không sửa Task1/2 hoặc cài package ngoài phạm vi.

Independent code audit trước freeze:15 behavior tests pass; một finding về
policy review kế thừa Level cũ được sửa RED→GREEN bằng current frozen Level
rules, thêm1 regression test. Không sửa prompt/core/scorer sau freeze.
Đã kiểm3032 file cũ không đổi hash; raw source/prompt/response/review chỉ ở
ignored outputs. Commit chỉ file code/config/test/plan/report mới, không push.

Files: [renderer](../../src/task3/c_feedback_v3.py),
[adapter CLI/report](../../scripts/task3_c_feedback_v3.py),
[config](../../configs/task3/c_feedback_v3_20261023.json),
[behavior tests](../../tests/test_task3_c_feedback_v3.py),
[review-policy test](../../tests/test_task3_c_feedback_v3_report.py).

```bash
.venv-task3/bin/python scripts/task3_c_feedback_v3.py verify
.venv-task3/bin/python scripts/task3_c_feedback_v3.py score
.venv-task3/bin/python -m pytest -q tests/test_task3_c_feedback_v3.py tests/test_task3_c_feedback_v3_report.py
.venv-task3/bin/python scripts/validate_task3_submission.py --predictions outputs/task3/c-feedback-v3-20261023/C-new/predictions.json --requested-levels outputs/task3/c-feedback-v3-20261023/requested-levels.private.json
```

`run` đã thực hiện một lần, marker ngăn resampling. Replay audit cần private
inputs/cache có thật; không dùng fixture thay model rồi báo như inference.

Bốn câu trả lời cuối:

1. Có tín hiệu vai tốt hơn C-old nhưng rất yếu: em1→2/12, bạn10→2/12. Chưa sửa được giọng trên đa số bài.
2. False claims7→4/12; L1 leak3→4/5; L2 vẫn2/4; L3 actionable vẫn3/3. So với R15, cả L1 và L2 leak tệ hơn; clean false1/3 cũng tệ hơn0/3.
3. Không có cải thiện đồng thời: joint0/12 ở cả R15 và C-new. Taxonomy B/C-old/C-new giống hệt (micro0.260870, macro0.09); chênh với R150.105263/0.028571 là thay stage1, không phải công của renderer.
4. Giữ R15. Không đề nghị chạy public hay tập độc lập tiếp cho candidate này. Muốn phát triển C tiếp phải là yêu cầu/phép thử riêng; báo cáo hiện tại giữ nguyên thất bại và chưa có bằng chứng vượt leaderboard.
