# Task3 — paired 7B independent review, giữ R15 (2026-10-22)

**Giữ R15.** SFT v1 tăng agreement taxonomy với annotation gốc nhưng không tăng proxy feedback validation và tăng vi phạm Level; SFT v2/C1 giảm feedback; C2 không tăng feedback và xuất hiện L2 repair leak. Hai vòng thay đổi không đạt joint-quality gate, không thử vòng ba. Không training mới, public inference, upload leaderboard, push, worktree hay thực thi C++ sinh viên.

Branch `feat/task3-quality-round5`; preflight HEAD `a180efcd1b2bbad80ad42cbef705f7d7acc2efda`, working tree ban đầu sạch. Commit implementation/results mới `8b9e729345de7173890392d445dd773c2cdef3fe`; báo cáo này được commit kế tiếp, SHA cuối có trong final-handoff.private.json và phản hồi chat. Chỉ thêm file mới; mọi file tracked ban đầu nguyên bytes, code/runtime helpers khớp preflight commit. Thời điểm báo cáo 2026-10-22T20:50:47.348490+07:00 (UTC+7).

**Dữ liệu, selection và giới hạn kết luận**

24 source/24 query ID, chia trước candidate thành development12 và validation12; mỗi phía3 real +9 synthetic. Không tạo ba bản Level cho cùng source: original Level giữ riêng, requested Level chiếu theo rule đã khóa. Development L1/L2/L3/L4=4/3/4/1; validation=3/4/4/1. Không dùng số liệu lịch sử từ dataset khác để điền bảng mới.

|Artifact thật dùng|Version/bytes SHA-256|
|---|---|
|ZIP synthetic hiện có,627 root records|6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b|
|Official synthetic release label_space|056a4d1a0ccfd60688b43efdf5df64a4c1310e3c6f1d99ab813691a2da27a9dc|
|Real label_space (bytes khác, giữ nguyên)|2e21d225a20609c3adac8c0c95110d08c18dc8982d083879b8029fea2286c715|
|Prepared real-val6source|7ba34debaf0112cba9600adf1f28a797afd787d144687e7d0d200e3a862b6c55|
|Sealed evaluation-v2 source/reference60|66e445413b112e7c7c41a7dfb4eaa964993aa4ad20be15651401003eb84a4809|
|Selection manifest mới|d1530df2ff7746d5b4516bed9efb68b98a851ac26663f6138759b538b16d4cdd|
|Source-only reviewer freeze|d470354825afea26599572b4ddc1939b7234669e32b48d0f1480b9d1aaed63cd|
|C1 prompt freeze|ef3f39a0733b87dc2dcf50e8ee6e1ad3b77c4f9a59e9bd781ed8f45453434558|
|C2 prompt freeze|772c0e873e9682d4700d6b72fdfc12f3ef3efe9e18e67c9d4848590017949d88|

Synthetic chọn18source, một source mỗi18family evaluation-v2 theo metadata để phủ nhãn và original-clean; actual code/statement/hash được so trực tiếp với ZIP. Real code được đối chiếu raw file. Prepared synthetic cũ có495train/47heldout và metadata bytes khác ZIP; không dùng snapshot đó làm source/annotation cho phép so này. Annotation version là original prepared-real + frozen ZIP-v2 synthetic, giống hệt cho cả5phương pháp; không sửa gold.

Selection rule cụ thể và toàn bộ ID/source raw SHA/decoded SHA/Level/original Level nằm trong selection.private.json; model-inputs.private.json chỉ chứa thông tin được phép. Bộ lọc kiểm180 source rows SFT (v1 train56+internal-val14, v2 train96+internal-val14; có overlap nên không gọi180 unique) bằng ID, raw/decoded source, token, identifier-renamed identity và shingle Jaccard>=0.85; không source selected nào trùng/near, không bị loại sau chọn. EX01 và9synthetic family thuộc development; EX02 và9family còn lại thuộc validation. Không source/near/family cross-partition. Gold/teacher không vào prompt.

**Validation là phần tách độc lập cho vòng này nhưng không phải tập mù đáng tin hoàn toàn.** Nguồn/template/family đã phơi nhiễm trong nghiên cứu cũ; SFT học cảEX01/EX02 và nhiều synthetic family. Hai phía còn chung nguồn sinh ZIP. Lexical screen không chứng minh loại hết semantic/template leakage. Không thể tái dựng đầy đủ history đã thiếu/archived; không tuyên bố chưa từng thấy source/output. Vì vậy thiếu một holdout thật mới, độc lập về family/generator/history để chọn production chắc chắn; không ép winner trên12ID.

Source adjudication full-domain cuối:20defective,2clean,2unknown. Mỗi phía chỉ1clean synthetic có căn cứ (FACT/REVSTR); **real clean có căn cứ=0**, thiếu ít nhất1real-clean so với coverage yêu cầu. Hai original real-clean thực tế là EX201 unknown về độ rộng int và EX211 có output prompt. Không tạo/đổi nhãn để bù quota. Level4 chỉ1source/phía; validation thiếu original support4/10nhóm. Kết luận có giới hạn do các thiếu hụt này.

**Model/runtime và output contract**

Qwen/Qwen2.5-Coder-7B-Instruct, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, model7B hoặc adapter của đúng base (<10B). R15/C1/C2 không adapter. SFT1/SFT2 dùng selected epoch2 thực có; tensor SHA lần lượt `a193807c8e21c1d4bd9d826717e9c40dc32d6f18f891e39a78a7517f4c21de3e` và `7e7fcf74c2fb22e4360cd3880e4beb68daa50f7661abd170a3c37cdfae88cd51`; toàn bộ adapter files khớp training-result manifest.

RTX5090 32GB; NF4 4bit/double-quant/BF16 compute; seed42, greedy, context16384; cap1024output tokens (1536L4), generation max_time45s, tối đa3 native attempts. Cùng R15 config/controller/parser/guard cho mọi arm; giữ nguyên cặp taxonomy+feedback native, kể cả fallback native được đánh dấu. Không compiler stage: compiler evidence unknown; syntax claims là static source reasoning, không phải diagnostic đã chạy. Mỗi output hoàn chỉnh chạy validator của repo; schema không thay cho content review.

**Review độc lập và proxy**

Một Codex reviewer khác implementation đọc đủ statement/source/policy/Level trước prediction; khóa source findings SHA trước đọc gold. Reviewer chỉ đọc development/private packet, không đọc key, arm directories hoặc public; không sửa pipeline/prompt/prediction/gold. Sau source freeze mới đối chiếu annotation.36baseline development +24C1 development +24C2 development +48validation đầu +24C2 validation=156review rows, tương ứng120unique ID-method outputs và36control repeats. Mọi repeat giữ nguyên score/Level/claims; exact source findings, source hashes, Levels, output canonical SHA, native pairs và evidence quotes đều qua audit. Attestation được tạo SAU review, không giả seal trước; source freeze gốc được đối chiếu với seal C1 trước inference.

Usefulness0/0.5/1 là proxy nội bộ:1 đúng lỗi chính/ích lợi/Level;0.5 có ích một phần;0 có material false claim, nghiêm trọng Level, false-clean hoặc generic không ích lợi. Không gọi đây là công thức leaderboard. Primary không cộng success cho fallback hoặc material unknown; raw reviewer mean và domain sensitivities lưu riêng. Nhận định phụ thuộc int-width/charset được tách unknown; finding/claim/mapping disputes không biến thành human gold. Human-verified0, human scores N/A; không yêu cầu user duyệt từng finding.

**Cùng tập ID: taxonomy với annotation gốc và feedback**

development:12ID, annotation đã khóa; exact tính trên actual delivered labels, kể cả native fallback taxonomy. Cột F1-support chỉ tính nhóm có gold support; F1-10 tính đủ10nhóm. Bảng gated không credit fallback được giữ trong JSON để phân biệt label agreement với joint usefulness.

|Method|Exact|microF1|macro10|macro support|Proxy|Zero|Unknown|False/unsupported rows|Level rows|L2repair|Complete|RetryID|Fallback|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|R15|4/12|0.182|0.075|0.083|0.208|8|0|8|3|1|12/12|2|1|
|SFT1|3/12|0.261|0.190|0.211|0.292|7|0|5|4|0|12/12|1|1|
|SFT2|3/12|0.429|0.295|0.328|0.250|8|1|6|1|0|12/12|1|1|
|C1|4/12|0.182|0.065|0.072|0.167|9|0|7|3|0|12/12|3|1|
|C2|4/12|0.190|0.079|0.087|0.250|8|0|8|3|0|12/12|0|0|

validation:12ID, annotation đã khóa; exact tính trên actual delivered labels, kể cả native fallback taxonomy. Cột F1-support chỉ tính nhóm có gold support; F1-10 tính đủ10nhóm. Bảng gated không credit fallback được giữ trong JSON để phân biệt label agreement với joint usefulness.

|Method|Exact|microF1|macro10|macro support|Proxy|Zero|Unknown|False/unsupported rows|Level rows|L2repair|Complete|RetryID|Fallback|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|R15|5/12|0.125|0.029|0.048|0.250|9|2|6|2|0|12/12|2|1|
|SFT1|6/12|0.400|0.157|0.262|0.250|8|2|3|5|0|12/12|0|0|
|SFT2|1/12|0.273|0.173|0.289|0.167|10|2|7|2|0|12/12|0|0|
|C1|5/12|0.125|0.029|0.048|0.167|9|2|5|5|0|12/12|2|1|
|C2|5/12|0.125|0.029|0.048|0.250|9|1|6|3|1|12/12|0|0|

Raw means (chưa loại fallback/domain unknown), theo thứ tựR15/SFT1/SFT2/C1/C2: development=0.208/0.292/0.292/0.208/0.250; validation=0.333/0.333/0.250/0.250/0.333. Không dùng raw sensitivity để cứu selection gate.

**Proxy theo requested Level và source status**

development

|Method|L1|L2|L3|L4|Clean|Defective|Unknown(no credit)|Generic rows|Main covered L2/3|Feasible L3 direction|
|---|---|---|---|---|---|---|---|---|---|---|
|R15|0.250|0.167|0.250|0.000|1.000|0.136|N/A|5|4|1|
|SFT1|0.500|0.333|0.125|0.000|0.000|0.318|N/A|5|5|1|
|SFT2|0.500|0.333|0.000|0.000|0.000|0.273|N/A|6|6|3|
|C1|0.000|0.000|0.500|0.000|0.000|0.182|N/A|4|5|2|
|C2|0.500|0.167|0.125|0.000|0.000|0.273|N/A|5|3|0|

validation

|Method|L1|L2|L3|L4|Clean|Defective|Unknown(no credit)|Generic rows|Main covered L2/3|Feasible L3 direction|
|---|---|---|---|---|---|---|---|---|---|---|
|R15|0.000|0.250|0.250|1.000|1.000|0.222|0.000|7|2|1|
|SFT1|0.333|0.375|0.125|0.000|0.000|0.333|0.000|7|4|0|
|SFT2|0.333|0.000|0.250|0.000|0.000|0.222|0.000|6|2|2|
|C1|0.000|0.125|0.125|1.000|1.000|0.111|0.000|5|2|0|
|C2|0.000|0.250|0.250|1.000|1.000|0.222|0.000|5|4|1|

Feasible direction là một thành phần; có thể cùng xuất hiện với false claim nên không tự thành useful output. Level rows gồm thiếu diagnosis/repair và L4 generic, không phải mọi row là tiết lộ nghiêm trọng. L2 repair được reviewer xét cả văn xuôi; validation C2 có1ca thao tác sửa điều kiện, trong khi R15=0. L1 disclosure validation R15/SFT1/SFT2/C1/C2=0/0/0/1/1 (C2 bổ sung adjudication cho COUNTUPPER); development=0/0/0/2/1. Không phát hiện code sửa/full-solution ở L1/L2; native regex không được coi là review ngữ nghĩa.

**Đủ10nhóm: support và TP/FP/FN trên gold gốc**

development

|Nhóm chính thức|Support|R15|SFT1|SFT2|C1|C2|
|---|---|---|---|---|---|---|
|Lỗi biên dịch|2|1/1/1|0/1/2|0/0/2|1/2/1|1/1/1|
|Lỗi nhập/xuất|0|0/0/0|0/0/0|0/0/0|0/0/0|0/0/0|
|Lỗi logic|3|1/4/2|1/1/2|2/1/1|1/4/2|1/3/2|
|Lỗi vòng lặp|2|0/0/2|1/1/1|0/0/2|0/0/2|0/0/2|
|Lỗi mảng/chuỗi|1|0/1/1|0/3/1|1/1/0|0/0/1|0/1/1|
|Lỗi hàm|1|0/0/1|1/0/0|1/1/0|0/0/1|0/0/1|
|Lỗi edge case|1|0/0/1|0/0/1|1/5/0|0/0/1|0/0/1|
|Lỗi thuật toán|1|0/0/1|0/0/1|0/0/1|0/0/1|0/0/1|
|Lỗi hard-code|2|0/0/2|0/0/2|1/0/1|0/0/2|0/0/2|
|Lỗi style|1|0/0/1|0/0/1|0/0/1|0/0/1|0/0/1|

validation

|Nhóm chính thức|Support|R15|SFT1|SFT2|C1|C2|
|---|---|---|---|---|---|---|
|Lỗi biên dịch|1|0/0/1|0/0/1|1/1/0|0/0/1|0/0/1|
|Lỗi nhập/xuất|0|0/0/0|0/0/0|0/0/0|0/0/0|0/0/0|
|Lỗi logic|1|1/5/0|0/1/1|0/1/1|1/5/0|1/5/0|
|Lỗi vòng lặp|4|0/0/4|2/1/2|1/0/3|0/0/4|0/0/4|
|Lỗi mảng/chuỗi|1|0/0/1|1/0/0|1/1/0|0/0/1|0/0/1|
|Lỗi hàm|1|0/0/1|0/0/1|0/0/1|0/0/1|0/0/1|
|Lỗi edge case|0|0/0/0|0/0/0|0/6/0|0/0/0|0/0/0|
|Lỗi thuật toán|0|0/0/0|0/0/0|0/0/0|0/0/0|0/0/0|
|Lỗi hard-code|2|0/0/2|0/0/2|0/0/2|0/0/2|0/0/2|
|Lỗi style|0|0/0/0|0/0/0|0/0/0|0/0/0|0/0/0|

Development support0: I/O; validation support0: I/O, Edge case, Algorithm, Style. Macro10 coi F1 của nhóm0support bằng0 và giữ false positives; macro-support loại nhóm0support để tránh đánh đồng thiếu support với thất bại recall. Source thực có I/O nhưng gold gốc thiếu; không âm thầm đổi annotation.

**Source-grounded taxonomy và disputed tách riêng**

|Split|Method|Undisputed subset n|Agent microF1|Agent exact|Known source frozen TP/FP/FN|Disputed predicted labels|Falseclean labels|Functional label FA|
|---|---|---|---|---|---|---|---|---|
|development|R15|9|0.273|2/9|3/3/20|2|3/11|0/1|
|development|SFT1|9|0.182|2/9|4/1/19|4|2/11|0/1|
|development|SFT2|9|0.240|1/9|5/3/18|6|0/11|1/1|
|development|C1|9|0.273|2/9|3/3/20|2|3/11|0/1|
|development|C2|9|0.190|1/9|2/3/21|2|4/11|0/1|
|validation|R15|5|0.222|1/5|1/2/10|3|3/9|0/1|
|validation|SFT1|5|0.250|1/5|2/1/9|2|4/9|0/1|
|validation|SFT2|5|0.364|1/5|3/6/8|1|0/9|1/1|
|validation|C1|5|0.222|1/5|1/2/10|3|3/9|0/1|
|validation|C2|5|0.222|1/5|1/2/10|3|3/9|0/1|

Subset loại source unknown và mọi finding/category overlap còn tranh luận: chỉ9development/5validation, agent-authored reference, không human gold. Cột known-source TP/FP/FN là source-first frozen-review labels sau overlap overlay, loại unknown sources; domain adjudication mới của SUMEVEN ghi riêng và không được thêm vào gold hoặc dùng tự tăng TP. FA ở bảng này chỉ là non-Style taxonomy trên clean source; prose có thể false accusation dù taxonomy rỗng. Mẫu số clean mỗi phía1 nên không suy tần suất public.

Gold/source disagreements dưới đây giữ nguyên annotation. Review groups chỉ là primary có bằng chứng theo overlay, các alternative/unknown vẫn lưu riêng; khác nhau không tự chứng minh mọi gold sai.

|ID disputed/khác reference|Gold gốc giữ nguyên|Agent frozen groups|Status/giới hạn|
|---|---|---|---|
|EX01-S106|Lỗi logic, Lỗi vòng lặp|Lỗi logic, Lỗi mảng/chuỗi, Lỗi vòng lặp|defective; mapping overlap disputed|
|EX01-S111|Lỗi biên dịch|Lỗi biên dịch, Lỗi hàm, Lỗi mảng/chuỗi, Lỗi nhập/xuất|defective|
|EX01-S112|Lỗi hard-code|Lỗi hard-code, Lỗi logic, Lỗi mảng/chuỗi, Lỗi nhập/xuất, Lỗi vòng lặp|defective|
|SYN-ARM-0008|Lỗi mảng/chuỗi|Lỗi logic|defective|
|SYN-COUNTGT-0004|Lỗi logic|Lỗi logic, Lỗi vòng lặp|defective|
|SYN-PRIME-0008|Lỗi hàm|Lỗi logic|defective|
|SYN-BASE2-0000|[]|Lỗi nhập/xuất|defective|
|SYN-SUMB-0005|Lỗi logic, Lỗi style|Lỗi logic|defective|
|EX02-S201|[]|Lỗi edge case|unknown; mapping overlap disputed|
|EX02-S211|[]|Lỗi nhập/xuất|defective|
|EX02-S212|Lỗi biên dịch, Lỗi vòng lặp|Lỗi biên dịch|defective|
|SYN-COUNTUPPER-0001|[]|[]|unknown|
|SYN-FIB-0000|[]|Lỗi nhập/xuất|defective|
|SYN-MAXDIFF-0008|Lỗi hard-code|Lỗi hard-code, Lỗi nhập/xuất|defective|
|SYN-PERFECT-0018|Lỗi vòng lặp, Lỗi logic|Lỗi vòng lặp|defective|
|SYN-PROD-0015|Lỗi mảng/chuỗi, Lỗi vòng lặp, Lỗi hàm|Lỗi logic, Lỗi mảng/chuỗi, Lỗi vòng lặp|defective|

Domain riêng: EX201 chưa rõ int32/int64; COUNTUPPER chưa rõ charset/cctype. SUMEVEN literal statement cho phép n1001 vượt fixed capacity: primary defective, conditional clean khi bổ sung n<=1000; không tự coi điều kiện bổ sung là scope chính thức. FACT có explicit0..20 và REVSTR dùng string/reverse được giữ clean. Các thay đổi chỉ là adjudication/versioned overlays áp dụng đồng nhất mọi method; raw review/gold/source không đổi.

**Hai vòng thay đổi và quyết định**

|Vòng|Một thay đổi so với R15|Giả thuyết/ID development|Kết quả validation và rollback|
|---|---|---|---|
|C1|Thêm silent source-consistency self-check; không thêm call/schema|Giảm source-false claims: MINA,COUNTGT,EX111,EX112|microF1 .125→.125; proxy .250→.167; Level2→5; bác bỏ, dùng R15. Có gain DIGITSUM/MINA nhưng regression compile claims và L1.|
|C2|Thay C1 bằng Level-specific prose frames trên R15 gốc; L4 giữ nguyên|L1 đúng trạng thái, L3 có repair: EX106,SUMB,PRIME|microF1 .125→.125; proxy .250→.250; L2repair0→1, thêm L1 specific claim; bác bỏ. Không ghép C1/C2 hoặc chọn từng output.|

Hai prompt được khóa từ review development trước khi mở bất kỳ validation model output nào. C2 là alternative độc lập một delta từ R15, không cộng nhiều thay đổi vào C1. Đánh giá cả hai trên cùng validation sau freeze; cả hai không tăng joint quality, nên dừng ở2/3vòng. Không điều chỉnh prompt theo từng validation ID. Không thử router vì chưa có lợi thế Level ổn định: mỗi Level chỉ3–4source, L4 chỉ1. SFT1 .400taxonomy không đủ khi feedback không tăng và Level2→5; SFT2 .273taxonomy nhưng feedback.167 và clean false accusation nên không chọn.

Top5 nguyên nhân development (counts overlap, từ36baseline reviews, không suy public):

|Nguyên nhân|Rows/36|Ví dụ có bằng chứng|Ảnh hưởng|
|---|---|---|---|
|Source-false/unsupported claims|19|MINA nói bỏ đầu dù đã khởi tạo; COUNTGT quy sai việc mở lại file|Cả taxonomy và feedback|
|L1 không khớp trạng thái/cặp output|8|FACT false warning; EX106 false clean; ARM taxonomy[] nhưng warning|Cả hai|
|L3 thiếu hướng sửa|5|SUMB diagnosis đúng nhưng không có bước sửa; MINA/DIGITSUM/EX112|Feedback|
|Miss/bịa compile|7|EX111 static syntax bị bỏ; GCD thiếu-main-conformance; EX112 nhầm literal file thành compile|Cả hai|
|Bỏ output/Level contract|4|BASE2 có lời nhắc output dù gold[]; GCD chỉ thao tác sửa loop tạiL2|Cả hai|

**20case tiêu biểu: cải thiện và regression**

|ID|Lỗi/domain source hỗ trợ (diễn giải)|Proxy R15/SFT1/SFT2/C1/C2|Lý do reviewer/gain-regression|
|---|---|---|---|
|EX01-S106|P1 giữ con trỏ đến biến chuỗi cục bộ; các lỗi danh sách/vòng lặp quan trọng cũng tồn tại.|0.0 / 0.0 / 0.0 / 0.0 / 0.0|Nhiều arm false-clean; C2 conditional file warning không xác định đúng lỗi. Không có cải thiện chắc chắn.|
|EX01-S111|Nhiều static syntax/type defects; số ngoặc mở/đóng không phải defect.|0.5 / 0.0 / 0.0 / 0.0 / 0.0|C1/C2 thêm claim thiếu ngoặc sai, proxy .5→0 so repeated control. Không có compiler run.|
|EX01-S112|Tên file literal, không dùng tham số, P1 tiên quyết sai.|0.5 / 0.0 / 0.0 / 0.5 / 0.0|C1 giữ diagnostic tiên quyết đúng một phần; C2 bịa thiếu dấu ngoặc kép và sửa y hệt code, .5→0. Nhiều arm gán compile unsupported.|
|SYN-ARM-0008|Chuyển ký tự sang chữ số bằng phép cộng mã ký tự là sai.|0.0 / 1.0 / 1.0 / 0.0 / 1.0|C2 L1 warning đạt1 từ style advice0; taxonomy vẫn [] nên cặp chưa tốt. Gold mảng/chuỗi so source logic là disputed boundary.|
|SYN-FACT-0001|Giai thừa đúng trên explicit domain0..20, kiểu long long đủ.|1.0 / 0.0 / 0.0 / 0.5 / 0.0|Control clean1; C1 neutral .5; C2 bịa lỗi n>1 thành0. Regression rõ trên clean.|
|SYN-COUNTGT-0004|P1 two-pass hợp lệ; P3 bỏ phần tử đầu và max khởi tạo0 sai với số âm.|0.0 / 0.5 / 0.5 / 0.0 / 0.0|Nhiều arm bịa close/reopen mất dòng hoặc thất bại; C2 chê two-pass không cần thiết cũng không chữa lỗi.|
|SYN-DIGITSUM-0016|Thuật toán digital-root khác tổng chữ số.|0.5 / 0.0 / 0.0 / 1.0 / 0.5|C1 diagnosis mod9 và hướng chia/lấy dư giúp .5→1; C2 chỉ nhận return9 không tổng quát, thiếu repair nên .5.|
|SYN-GCDARR-0009|Cận cố định5 bỏ/sử dụng sai phần tử; entry point sai chuẩn C++.|0.0 / 0.5 / 0.5 / 0.0 / 0.5|C1 bỏ L2 repair leak nhưng bịa range; C2 đúng loop một phần .5, vẫn bỏ static compile defect. Category overlap không triple-credit.|
|SYN-MINA-0004|P2/P4 bỏ phần tử cuối, P3 trả0 sai cho singleton có b khác0.|0.0 / 0.0 / 0.0 / 0.5 / 0.0|C1 sửa đúng cận loop0→.5; C2 quay về bịa bỏ đầu,0. First element đã dùng để khởi tạo min.|
|SYN-SUMB-0005|P2 chỉ cộng b dương, không là tổng mọi b.|0.0 / 0.5 / 0? / 0.0 / 0.0|Control bịa allocation lỗi; C1 bịa compiler extraction trên struct; C2 quay về allocation. Không có gain; source allocation extra slot hợp lệ.|
|EX02-S201|Có signed-int32 overflow tại input hợp lệ; int width chưa khóa.|0? / 0? / 0? / 0? / 0?|Primary unknown: mọi warning/clean conclusion phụ thuộc width không credit success. Giữ raw scores để sensitivity; gold clean chỉ disputed conditional.|
|EX02-S211|Output có lời nhắc nhập dư mặc dù Armstrong arithmetic đúng.|0.0 / 0.0 / 0.0 / 0.0 / 0.0|Các arm bỏ IO defect; C2 còn nhầm yêu cầu không pow dù vòng nhân đã đáp ứng. Gold clean disputed.|
|EX02-S212|Biến dùng làm cận mũ chưa khai báo; số chữ số ở biến khác với bản sao n.|1.0 / 0.0 / 1.0 / 0.5 / 1.0|Một số arm diagnosis+repair hữu ích1; có arm nhầm bản sao n là count hoặc gọi compile defect là logic. C2 output lặp giữ1, taxonomy vẫn sai.|
|SYN-COUNTUPPER-0001|Đếm hoa đúng với ASCII/valid cctype; full charset domain chưa xác định.|0? / 0? / 0? / 0? / 0.0|Primary unknown, unconditional clean/warning không credit. C2 claim đọc token sai bị bác độc lập; không dùng domain unknown để tha false claim.|
|SYN-DISTINCT-0010|Chỉ nhập n-1 số thay n.|0.0 / 1.0 / 0.0 / 0.5 / 1.0|C2 từ abstention0→diagnosis1; taxonomy logic là boundary disputed so loop. Một arm L2 quote source code có sensitivity .5/1, không là code sửa.|
|SYN-FIB-0000|F0/F1 và recurrence đúng trong miền không tràn; output lời nhắc dư là defect chắc chắn.|0.0 / 0.0 / 0.0 / 0.0 / 0.0|Các arm false-clean hoặc bịa F1 sai; không cải thiện. Gold clean disputed theo output contract.|
|SYN-PERFECT-0018|Vòng duyệt ước không tăng biến nên vô hạn cho n>=4.|0.0 / 0.0 / 0.0 / 0.0 / 0.0|Không arm tìm main cause; nhiều arm bịa đếm đôi căn dù đã có guard; một arm giảng sai ước thực sự bao gồm chính n.|
|SYN-PROD-0015|Ghép trường khác record, bỏ cuối ở max và truyền số record thiếu khi in.|0.0 / 0.5 / 0.0 / 0.0 / 0.0|Một arm diagnostic một phần .5; control/C1 bịa out-of-allocation và compile error dù mảng cấp phát thêm1. C2 bỏ compile claim nhưng vẫn sai allocation,0.|
|SYN-SECONDMAX-0006|Cận cố định5 làm sort dùng sai miền phần tử.|1.0 / 0.5 / 0.0 / 0.0 / 0.0|Control diagnostic đúng1; C1 abstain0; C2 directive sửa loop condition làm L2 repair leak,0. Không chọn bằng chỉ mean proxy.|
|SYN-SUMEVEN-0000|Vòng nhập có break đúng và tổng chẵn đúng trong capacity; full-domain n1001 vượt capacity.|0.0 / 0.0 / 0.0 / 0.0 / 0.0|Các arm bịa infinite loop, đều0 độc lập capacity. Primary full-domain defective; conditional clean<=1000. Reviewer và implementer đã giải bất đồng domain theo literal statement.|

Dấu? là material unknown, primary không credit; score0cũng bao gồm fallback đã loại. Review và từng claim/evidence/full source/model finals chỉ trong ignored storage, không đưa vào báo cáo tracked. Wording “thay vì”/quote code ở L2 có sensitivity riêng: DISTINCT có thể.5→1 nếu cho phép trích source; không là repair leak và không làm candidate thắng. Review không phải điểm chính thức.

**Runtime, verification và bàn giao**

|Method|GPU calls|Input tokens|Output tokens|Generation seconds|Fallback/24|
|---|---|---|---|---|---|
|R15|30|27667|1744|51.001|2|
|SFT1|26|28012|1315|52.588|1|
|SFT2|26|28012|1620|63.035|1|
|C1|31|31132|2228|65.506|2|
|C2|24|24578|1329|40.790|0|

137native calls,272.920s generation ngoài model-load/tokenization/review. Tất cả137finish EOS;0runtime error,0schema-invalid attempt,120/120complete/schema-valid finals; không observed timeout/length/unknown finish.852payload/capture checks đối chiếu nguyên đề/source/Level, exact system prompt mỗiarm, retry capture và raw response identity.3protected production/source artifacts giữ hash; mọi original tracked file không đổi. Adapter/source/prompt/selection seals pass;7helper files khớp preflight commit trong retrospective audit. Retry/fallback theo bảng, không chọn best attempt hay ghép output nhiều model.

Kiểm thử thật:47focused tests pass (12new protocol/prompt/report tests), `git diff --check` sạch. Full Task3 run:1269passed,5skipped,4failed,5errors;9outcomes đều thiếu `outputs/task3/round16/development-selection.json` (đã có archive index, không restore/ghi đè). Failed: eval_snapshot::test_historical_inventory_is_complete_and_uses_metadata_only; eval_snapshot::test_candidate_pool_is_not_reported_as_model_output_exposure; eval_v2::test_real_v2_split_train_positive_and_disjoint; eval_v2::test_v2_plan_preserves_v1_and_does_not_read_prediction_or_public_inputs. Setup errors trong test_task3_freeze_cli: assembly_has_unique_sources_clean_scopes_and_fixed_cf; model_inputs_are_gold_free_and_cf_task_identical; every_finding_has_source_spans_and_level_rubric; assembly_rejects_reused_ids_and_missing_review; conditional_after_repair_is_not_a_required_primary_finding (đều prefix test_). Full `pytest -q` dừng collection tại test_clm_zeroshot_task1.py và test_task1_clm_probe.py vì thiếu sklearn. Không tuyên bố toàn repo xanh, không đổi tests/history để che lỗi.

Một code reviewer độc lập bổ sung phát hiện3Important/2Minor về binding/evidence/repeated verdict/fallback credit/hash inventory; đã sửa bằng test RED→GREEN và audit data thật. Code reviewer bị auto-review hạn chế đọc private review files nên phần đó dùng code và metadata; independent content reviewer riêng vẫn đọc/chấm đủ156rows. Các source-boundary/domain disagreements đã giải quyết bằng source inspection và separate conservative overlays; không chuyển quyền quyết định cho user để tiếp tục chạy.

Không tạo file public mới vì không có winner đủ căn cứ; không chạy lại public. Bản R15 thật còn tồn tại:

`/workspace/llm-final-project/outputs/task3/round15/public-candidate-zero/predictions.json`

SHA-256 `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`; **VALID328/328**, Levels115/163/50/0. Đường handoff cũ `outputs/task3/submission-r15-20261020/predictions.json` hiện KHÔNG tồn tại; không dẫn user nộp đường đó. Validator chỉ kiểm schema/ID/label/nonempty feedback và Level-map, semantic Level do reviewer kiểm.

```bash
.venv-task3/bin/python scripts/validate_task3_submission.py --predictions outputs/task3/round15/public-candidate-zero/predictions.json --requested-levels outputs/task3/submission-r15-20261020/task3_requested_levels.json
.venv-task3/bin/python scripts/task3_paired_review.py verify
.venv-task3/bin/python scripts/task3_paired_report.py
.venv-task3/bin/python -m pytest -q tests/test_task3_paired*.py tests/test_task3_round15.py tests/test_task3_round15_runner.py tests/test_task3_submission.py
```

Private root `/workspace/llm-final-project/outputs/task3/paired-review-20261022`: selection/inputs/source/annotations; adapter/code/runtime hashes; native raw attempts+responses+finals;156review rows; domain/claim/evidence overlays; post-review attestations; id-metrics CSV/JSON;20case summary; code-review findings/resolution; final-provenance audit; test logs; final handoff và manifest. Aggregate tracked: TASK3_PAIRED_REVIEW_RESULTS_20261022.json. Không force-add ignored artifacts. Sau commit cuối working tree được kiểm sạch; không push/upload. **Giữ R15; không tuyên bố đạt bất kỳ ngưỡng leaderboard mới nào.**
