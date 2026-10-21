# Task 3 — DIRECT SFT v2: audit trước train và một pilot (2026-10-21)

**Giữ R15 production và dừng huấn luyện tiếp.** V2 hoàn tất 60/60, giữ ngưỡng lợi ích taxonomy đã khóa và tăng L2 đúng vị trí/nguyên nhân lên 13/24. Tuy nhiên strict L2 giảm, false technical claim tăng so v1, L3 chỉ có một hướng sửa cục bộ khả thi và đi kèm claim sai. Không thay R15, không tạo candidate/public predictions, không public inference, leaderboard, submission hoặc push.

HEAD trước lượt này: `97b8cc608036722615bae82fbd24672ca4ed42c6`, branch `feat/task3-quality-round5`. Chỉ thêm file mới. DIRECT SFT v1, R15 và mọi seal/artifact cũ giữ nguyên. SHORT/two-stage vẫn đóng ở kết luận thất bại; không chạy lại. Đây là development có prior exposure, **không phải benchmark mù hoặc family-disjoint holdout**.

## Audit trước optimizer

Đối chiếu nguyên văn **56 target L3 optimizer v1** với đúng source và input đã token hóa: 52 defect có nguyên nhân được source hỗ trợ và thao tác sửa **cục bộ** cụ thể; 4 scoped-clean không bị ép sửa; không có target chỉ nói chung trong 52 ca. Điều này không chứng minh target đã bao phủ mọi lỗi hoặc sửa hoàn chỉnh chương trình. Ví dụ có sửa lời gọi nhưng helper còn lỗi; một số P3 chưa cài đặt vẫn chưa được target bao phủ. Không quy mọi thất bại v1 cho target chung chung.

56/56 source/statement thực đưa vào optimizer khớp snapshot. Một raw-file hash khác decoded-code hash do hai miền bytes khác nhau; hash decoded của example khớp đúng code model nhận. Đây không phải source drift. Không sửa metadata v1 để hợp thức hóa.

Phân tích riêng **6 cặp L3 defective** cùng source BASE/v1 và **11 ca L2 BASE-useful**: có 3 L2 mất hoàn toàn finding (COUNTUPPER-0012, MAXDIFF-0007, REVSTR-0007), 3 suy giảm diễn đạt nguyên nhân, 5 còn giữ; 3 cặp L3 mất ý đúng của BASE. TRAIN và development tách source, nên không ghép một target TRAIN với một source development khác rồi coi đó là cùng bài.

Bảng từng ca với target/output nguyên văn, quote, thao tác sửa, ý bị mất, claim không có căn cứ và giới hạn nằm tại [private case analysis](../../outputs/task3/direct-sft-v2-20261021/analysis/pretrain-case-analysis.private.md), cùng [audit JSON](../../outputs/task3/direct-sft-v2-20261021/analysis/v1-error-audit.private.json). Đây là agent static review, **không human-verified**; compiler-confirmed/testcase-executed đều 0.

Hai flag v1 được đọc lại bằng source: ARM-0026 có che khuất biến và tự khởi tạo đọc giá trị bất định; câu feedback có hai cách hiểu. GCDARR-0009 có cận gộp cố định và chữ ký main không chuẩn, nhưng câu điều kiện theo n vẫn mơ hồ. Cả hai giữ **unknown/null**, không ép verdict và không suy output số xác định sau undefined behavior. Bản v1 không đổi; ledger v2 chỉ bổ sung rationale reconsideration.

## Dữ liệu mở rộng và chất lượng target

ZIP hiện tại được hash theo bytes, vẫn `6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b`. Dùng inventory/opaque fingerprints DIRECT v1 đã kiểm hash: 26 real +495 synthetic candidates, gate/dedup còn 25 real +131 ZIP synthetic; thêm 18 supplement scoped-clean hợp lệ. Không đọc lại nội dung public, public predictions, prompt public hoặc leaderboard để viết target/chọn phương pháp.

Pool 174 source đã được review hết qua hai lượt: v1 giữ 70, loại 36; lượt này xét **68 còn lại**, giữ **40** (28 ZIP defects +12 scoped-clean supplement), loại **28/68 =41.18%**. Trong 28 ca: annotation thiếu/mâu thuẫn 1, mapping taxonomy tranh chấp 4, annotation rỗng nhưng có defect 2, style không có quy tắc hỗ trợ 11, whitespace-only I/O chưa rõ checker 10. Không sửa nhãn để nhận thêm source; tổng 64/174 bị loại sau source review, còn 110 source gồm validation.

Gate v2 có version riêng, tái dùng semantics identity cũ qua bản copy registry được khai báo rõ; không sửa/bypass âm thầm gate family lịch sử. Registry bảo vệ 520 signatures: 506 cũ và 14 validation v1. Kiểm ID/group/exact/decoded/token/identifier-renamed và shingle Jaccard >=0.85 ở before_targets và before_optimizer trên đúng source bytes. Cả 14 validation bị chặn tại hai boundary; không đặt family ban. Đây là screen lexical bảo thủ, không chứng minh loại mọi semantic near-duplicate. Optimizer v2 phủ 28 family, gồm cả 18 family của Evaluation v2; tập development này không còn family-disjoint.

Giữ nguyên **14 source validation v1**, 42 parsed target objects; toàn bộ source/Level cùng phía. 56 optimizer v1 được giữ và thêm 40 source. Teacher feedback chỉ tham khảo; 120 target mới tự viết từ source. Nhãn supplement là agent-authored, không gọi là official ZIP annotation.

| Split | Source | Origin real / ZIP / supplement | Defect / scoped-clean | L1/L2/L3 examples |
|---|---:|---:|---:|---:|
|Optimizer|96|11 /70 /15|80 /16 (16.67% clean)|96 /96 /96 =288|
|Internal validation|14|3 /8 /3|11 /3|14 /14 /14 =42|
| Nhãn | Optimizer source | Internal val source |
|---|---:|---:|
|Lỗi biên dịch|15|3|
|Lỗi nhập/xuất|14|2|
|Lỗi logic|27|0|
|Lỗi vòng lặp|9|1|
|Lỗi mảng/chuỗi|10|0|
|Lỗi hàm|10|5|
|Lỗi edge case|12|0|
|Lỗi thuật toán|1|0|
|Lỗi hard-code|10|2|
|Lỗi style|0|0|

Không tạo style hoặc quota giả; thuật toán chỉ có **1 optimizer source**, không đủ căn cứ tuyên bố đã cải thiện nhóm này. Validation thiếu nhiều nhóm hiếm; loss không chứng minh giữ được coverage. Không có L4 supervision.

Các bản target được giữ theo version. Sửa 10 L3 cũ để thao tác rõ hơn; audit độc lập còn làm rõ một finding hiệu trộn bản ghi ở cả L2/L3. Tổng 12/210 target cũ khác v1; trong đó L3 optimizer 11/56, L2 optimizer 1/56, L1 không đổi. 4/120 target mới được chỉnh diễn đạt phép tích/định lượng vòng thử ước. Tổng sửa trước freeze **16/330 =4.85%** so với việc ghép target v1 với bản authoring mới ban đầu; không đổi taxonomy. Cả 80 defect optimizer L3 có nguyên nhân và ít nhất một thao tác sửa cục bộ khả thi theo static review, không phải chứng nhận whole-program fix.

Pretrain audit đầu đã chặn 12 clean source thiếu scope model-visible và cách mô tả phép tích chưa chính xác. Bản cuối đưa đúng ràng buộc input gốc vào statement của 12 source mới, bỏ câu về counterexample/finding; không đưa proof sạch vào input. Sửa wording của hai phép so sánh và một quantifier; giữ bản đầu, script authoring, changelog và audit fail. [Final target audit](../../outputs/task3/direct-sft-v2-20261021/review/pretrain-target-audit.private.json) pass, SHA `0f9829fb4bb5a5b0e47f3cdb09c50437a48ae557e643e27521a1ab3a51c47aa6`. Final target SHA `e6e9df17916f8c072175ae7dc38c8c70f21a1150cb571314098678fca765721f`.

Giới hạn: target và clean invariant là agent review, không người xác nhận; 42 old L3 không sửa được rebind vào audit toàn bộ source trước đó, không giả là một reviewer mới đọc lại độc lập mọi dòng. Context scope chủ yếu hiện ở các clean supplement có thể tạo cue; không coi tăng clean support là một ablation độc lập. Định hướng kiểm tra L2/L3 xuất phát từ development đã xem; không đưa source/witness/gold development vào target TRAIN.

## Freeze và đúng một optimizer run

[Config](../../configs/task3/direct_sft_v2_20261021.json), [freeze metadata](TASK3_DIRECT_SFT_V2_FREEZE_20261021.json) và private manifest/seal khóa trước optimizer. Manifest SHA `d20c770aeab47a2c5bacc955d8675a581aa6ec452e2b257ca4c8f8ecfc2a0566`; seal SHA `d0636ee311155eaefe7ad7e43749dce2fbb403cb2f4f0753498c988cd7e7fcb9`. Pin 83 runtime files, thư viện, dữ liệu, audit và output BASE/v1 được tái dùng.

Qwen/Qwen2.5-Coder-7B-Instruct revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, khởi tạo **base mới**, không nối adapter v1. Base logical params 7,615,616,512 +LoRA 40,370,176 ~=7.656B <10B. NF4 double-quant/BF16 trên RTX5090; LoRA r16/alpha32/dropout0.05, q/k/v/o/gate/up/down; lr1e-4 cosine,warmup0.03,batch1×accum4,seed42,AdamW torch,2 epochs. Chỉ assistant final JSON, prompt/padding masked; không diagnosis, witness tự xác nhận hoặc chain of thought.

| Token audit /epoch | Optimizer | Validation |
|---|---:|---:|
|Examples|288|42|
|Input+target|257706|44238|
|Supervised|17709|2673|
|Max sequence /cap8192|3704|2498|

Không truncate; kiểm tokenizer prefix thật và encoded/source binding ở setup và ngay trước step đầu. **Một attempt, một durable optimizer marker, 144 steps**; 576 example exposures,515412 input+target và35418 supervised tokens cho hai epoch. 144/144 gradient checks hữu hạn/khác0; LoRA update hữu hạn/khác0. Không sweep/resume hoặc optimizer thứ hai.

Internal validation equal-source CE: trước train **2.4845881263**; epoch1(step72) **0.9219909733**; epoch2(step144) **0.9203681389**. Chọn epoch2 bằng min loss/earliest tie đã khóa, trước inference. Chênh hai epoch nhỏ; loss không chứng minh feedback đúng. **Không so CE với v1**: parsed output validation không đổi, nhưng v2 serialization sắp feedback trước taxonomy thay vì thứ tự v1. Cả42 serialized completion khác thứ tự khóa; input messages vẫn khớp42/42, token/supervised totals giảm33. Giữ nguyên bản v2 đã freeze, không sửa sau output.

Adapter tensor SHA `7e7fcf74c2fb22e4360cd3880e4beb68daa50f7661abd170a3c37cdfae88cd51`. Wall load/train/save **283.13s**, training GPU wall **256.13s** gồm val/save; peak allocated **14.64GiB**, reserved **16.96GiB**. Không compile/run C++ source TRAIN/development; thiếu sandbox không chặn pilot và không được đổi thành compiler-confirmed.

## Cùng 60 development primary requests

BASE và V1 tái dùng nguyên prediction/raw/actual messages đã lưu, không chạy lại để chọn kết quả. V2 chạy đúng một pass mới. Mọi 60 first system/user messages bằng nhau giữa ba arm; giữ R15 native direct prompt/parser/disclosure/controller tối đa3 attempts và fallback feedback. Greedy seed42,NF4/BF16,cùng revision,context16384,cap1024/L4cap1536,deadline60s,fewshot0. V2 chỉ khác adapter. Không chạy36 CF, không claim invariance.

| Completion/cost | BASE R15 | Adapter v1 | Adapter v2 |
|---|---:|---:|---:|
|Final completed/schema valid|60/60|60/60|60/60|
|Final unresolved/schema/runtime error|0|0|0|
|Raw calls/schema valid|77 /76|61 /61|60 /60|
|Extra retry /fallback requests|17 /6|1 /0|0 /0|
|Input /output tokens|59017 /5303|45338 /2971|44568 /3241|
|Generation latency tổng,s|90.98|87.72|94.80|

Latency là tổng generation, không phải end-to-end load/wall. Guard không phải ground truth về disclosure: không có retry v2 vẫn có repair leak khi review source.

### Taxonomy, đủ 10 nhãn

Annotation ZIP và source-reference chấm riêng; không đổi mapping sau output. Macro zero_division0 giữ style dù source support0. Exact set cũng báo, không lấy F1 thay feedback.

| Metric /60 primary | BASE | V1 | V2 |
|---|---:|---:|---:|
|Annotation micro-F1|0.1818|0.5200|0.4957|
|Annotation macro-F1|0.0826|0.3844|0.4036|
|Annotation exact set|13|33|26|
|Source micro-F1|0.1400|0.4950|0.5085|
|Source macro-F1|0.0744|0.3725|0.4059|
|Source exact set|11|30|28|

Taxonomy micro-F1 theo Level; macro/per-label theo Level cũng có trong Results JSON. L4 chỉ mô tả, không claim cải thiện.
| Level (n) | Annotation BASE /V1 /V2 | Source BASE /V1 /V2 |
|---|---|---|
|L1 (19)|0.0000 /0.5000 /0.4737|0.0870 /0.5000 /0.5263|
|L2 (27)|0.3265 /0.6047 /0.6000|0.2041 /0.5581 /0.6000|
|L3 (8)|0.1111 /0.2353 /0.2000|0.1053 /0.2222 /0.1905|
|L4 (6)|0.0000 /0.7500 /0.6667|0.0000 /0.7500 /0.6667|

### Annotation TP/FP/FN và F1

| Nhãn | Support | BASE TP/FP/FN; F1 | V1 | V2 |
|---|---:|---|---|---|
|Lỗi biên dịch|4|2/2/2; 0.5000|3/0/1; 0.8571|3/2/1; 0.6667|
|Lỗi nhập/xuất|1|0/4/1; 0.0000|0/0/1; 0.0000|0/0/1; 0.0000|
|Lỗi logic|12|7/24/5; 0.3256|5/6/7; 0.4348|4/9/8; 0.3200|
|Lỗi vòng lặp|9|0/0/9; 0.0000|4/6/5; 0.4211|5/1/4; 0.6667|
|Lỗi mảng/chuỗi|9|0/0/9; 0.0000|5/0/4; 0.7143|5/3/4; 0.5882|
|Lỗi hàm|8|0/0/8; 0.0000|6/2/2; 0.7500|6/1/2; 0.8000|
|Lỗi edge case|2|0/0/2; 0.0000|0/0/2; 0.0000|2/11/0; 0.2667|
|Lỗi thuật toán|8|0/0/8; 0.0000|0/0/8; 0.0000|0/0/8; 0.0000|
|Lỗi hard-code|6|0/0/6; 0.0000|3/0/3; 0.6667|4/1/2; 0.7273|
|Lỗi style|1|0/0/1; 0.0000|0/0/1; 0.0000|0/0/1; 0.0000|

### Source-reference TP/FP/FN và F1

| Nhãn | Support | BASE TP/FP/FN; F1 | V1 | V2 |
|---|---:|---|---|---|
|Lỗi biên dịch|4|2/2/2; 0.5000|3/0/1; 0.8571|3/2/1; 0.6667|
|Lỗi nhập/xuất|5|0/4/5; 0.0000|0/0/5; 0.0000|0/0/5; 0.0000|
|Lỗi logic|10|5/26/5; 0.2439|4/7/6; 0.3810|5/8/5; 0.4348|
|Lỗi vòng lặp|10|0/0/10; 0.0000|4/6/6; 0.4000|5/1/5; 0.6250|
|Lỗi mảng/chuỗi|9|0/0/9; 0.0000|5/0/4; 0.7143|5/3/4; 0.5882|
|Lỗi hàm|9|0/0/9; 0.0000|6/2/3; 0.7059|6/1/3; 0.7500|
|Lỗi edge case|2|0/0/2; 0.0000|0/0/2; 0.0000|2/11/0; 0.2667|
|Lỗi thuật toán|6|0/0/6; 0.0000|0/0/6; 0.0000|0/0/6; 0.0000|
|Lỗi hard-code|6|0/0/6; 0.0000|3/0/3; 0.6667|4/1/2; 0.7273|
|Lỗi style|0|0/0/0; 0.0000|0/0/0; 0.0000|0/0/0; 0.0000|

V2 annotation micro thấp hơn v1 nhưng cả bốn micro/macro giữ ngưỡng **BASE+0.9×max(0,V1−BASE)** đã khóa. Source micro/macro cao hơn v1; exact set giảm ở cả hai reference. Không chọn adapter theo metric thuận lợi nhất.

## Feedback source-grounded theo Level

Có review record cho **180/180 final**: 120 BASE/v1 reuse review cũ có binding,60 v2 được hai agent mới chia30/30 và đọc source trước verdict. Không xem aggregate F1 trước verdict v2. Root đối chiếu sáu L3 và các ca mất finding. Reviewer không mù; đây là **agent static review, không human-verified**, không atomic-claim precision. Quote/schema/feedback ngắn không chứng minh nội dung đúng.

| Chỉ số semantic | BASE | V1 | V2 |
|---|---:|---:|---:|
|False technical claim /FC-assessed final|32/60|15/58 +2unknown|24/57 +3unknown|
|False-clean /51 defect final|12/51|1/51|3/51|
|L1 completion|19/19|19/19|19/19|
|L1 false-clean /17 defect|9/17|0/17|0/17|
|L1 disclosure /19 final|2/19|0/19|0/19|
|L1 false claim /19|10/19|0/19|0/19|
|L2 completion|27/27|27/27|27/27|
|L2 đúng vị trí+nguyên nhân /24 defect|11/24|10/24|13/24|
|L2 false claim /assessed|15/27|8/26 +1unknown|17/24 +3unknown|
|L2 concrete repair leak /27|6/27|0/27|4/27|
|L2 strict useful /assessed defect|7/24|9/23 +1pending|5/22 +2pending|
|L2 strict, **cùng21 assessed IDs**|6/21|9/21|5/21|
|L3 completion|8/8|8/8|8/8|
|L3 cause+feasible local repair /6 defect|1/6|0/6|1/6|
|L3 useful và không false claim, cùng5 assessed IDs|0/5|0/5|0/5|
|L3 false claim /assessed|5/8|5/7 +1unknown|5/8|
|L4 completion, chỉ mô tả|6/6|6/6|6/6|
|L4 false claim, chỉ mô tả|2/6|2/6|2/6|

Khi xét cùng **55 IDs có FC verdict ở cả ba arm**, false claim là BASE29/55,V1 13/55,V2 22/55. Strict L2 trên21ID chung vẫn giảm9→5 từ v1, nên không giải thích suy giảm chỉ bằng mẫu số unknown khác nhau. Ngay cả đặt hai unknown v1 là sai và ba unknown v2 là đúng, count sai v2 tối thiểu24 vẫn cao hơn tối đa17 của v1.

Các unknown mới v2: COUNTUPPER-0011 (ý nghĩa look-ahead/invalid access), DIGITSUM-0007 (mệnh đề hậu quả mơ hồ), DISTINCT-0000 (mô tả điểm dừng khó phân giải). Cả60 output đã được review; `reviewed=57` trong scorer là số chốt được false-claim flag, không phải thiếu3 review records. Những property khác vẫn có verdict độc lập. Không chuyển null thành pass hoặc 0.

COUNTUPPER-0012 lấy lại finding bị v1 bỏ; MAXDIFF-0007 và REVSTR-0007 vẫn giải thích sai đường chạy. Một số finding đúng tại FACT-0008, PROD-0003 và PERFECT-0007 được giữ. Tăng13/24 L2 không thành strict gain vì có claim sai kèm theo hoặc repair leak; v2 còn làm mất một finding của FACT-0006 và thêm assurance sạch sai.

MINA-0004 là L3 v2 duy nhất có nguyên nhân đúng và thao tác sửa cục bộ rõ cho lỗi singleton, nhưng cũng nêu sai về bản ghi đầu: useful=true, false_claim=true, strict=false. BASE PRIME-0010 tương tự có hướng modulo nhưng kèm claim sai. Do đó L3 v2 không tốt hơn BASE theo rate đã khóa và không có một final defect L3 đạt strict. PROD-0017 nêu được lỗi phép tính nhưng chuyển việc tạo tích sang chỗ đọc mà chưa nối đúng pipeline; MAXDIFF-0003 chưa chỉ cách tích lũy đúng ở P2; không thưởng hướng sửa chung.

L1 lời nhắc chung có thể đúng contract nhưng không chứng minh model đã chẩn đoán đúng. Flag ancillary missing_core của generic L1 trong ledger v1 có ranh giới không nhất quán; v2 giữ verdict cùng nghĩa trên cùng source và ghi riêng caveat. Không dùng hay tuyên bố cải thiện missing_core từ các flag ấy. Không có target L4 và **không tuyên bố cải thiện L4**.

## Từng source: kết quả v2 và lỗi còn lại

Bảng giữ đủ60 ID, không chỉ ca thắng; mọi ID có tiền tố SYN-. Đây là diễn giải review, không chứa source/raw nguyên văn. Exact feedback, source quotes/proofs và flags từng arm nằm ở [review a](../../outputs/task3/direct-sft-v2-20261021/review/semantic-a.private.json), [review b](../../outputs/task3/direct-sft-v2-20261021/review/semantic-b.private.json); [Results metadata](TASK3_DIRECT_SFT_V2_RESULTS_20261021.json) khóa source/output hashes và verdict ba arm.

| ID | L | Nhận định source-grounded, giới hạn/lỗi còn lại |
|---|---:|---|
|ARM-0000|1|Gợi ý chung đúng mức 1; chưa thể chứng minh phản hồi đã nhận diện lỗi cụ thể.|
|ARM-0008|4|Khẳng định bài đúng dù phép đổi ký tự sang chữ số sai; mô tả sai vị trí phép cộng.|
|ARM-0026|2|Chưa nêu đúng nguyên nhân che khuất biến và tự khởi tạo; còn chỉ hướng sửa ở mức 2.|
|ARM-0027|1|Gợi ý chung đúng mức 1; chưa thể chứng minh đã nhận diện lỗi cụ thể.|
|BASE2-0000|2|Bỏ sót phần xuất thừa, mô tả sai cách ghép bit và khẳng định bài không lỗi.|
|BASE2-0006|4|Nhận diện đúng việc truyền số kế tiếp và đưa hướng sửa phù hợp mức 4.|
|BASE2-0007|1|Gợi ý chung đúng mức 1; chưa thể chứng minh đã nhận diện việc đọc thừa dữ liệu.|
|COUNTGT-0000|4|Bịa lỗi ở vùng cấp phát dư và cách tìm cực đại; chưa có lỗi được chứng minh trong phạm vi xét.|
|COUNTGT-0004|1|Gợi ý chung đúng mức 1; chưa thể chứng minh đã nhận diện lỗi tìm cực đại.|
|COUNTGT-0005|1|Gợi ý chung đúng mức 1; chưa thể chứng minh đã nhận diện lỗi truy cập và cập nhật.|
|COUNTUPPER-0001|3|Nhận định phù hợp trong phạm vi chuỗi ASCII được xét.|
|COUNTUPPER-0007|2|Khẳng định phù hợp nhưng bỏ sót hai chữ cái ở biên khoảng kiểm tra.|
|COUNTUPPER-0011|2|Nêu được việc trộn hai vị trí ký tự; cách nói về cuối chuỗi còn mơ hồ.|
|COUNTUPPER-0012|2|Chỉ đúng nguyên nhân chương trình không đọc và không in kết quả.|
|DIGITSUM-0001|2|Mô tả phù hợp với cách cộng chữ số trong phạm vi xét.|
|DIGITSUM-0006|2|Nêu đúng việc trừ chữ số thay vì cộng và không chỉ hướng sửa.|
|DIGITSUM-0007|2|Chỉ đúng việc tính trên số kế tiếp; phần diễn đạt hậu quả còn khó hiểu.|
|DIGITSUM-0016|3|Nhận ra khác biệt với tổng chữ số nhưng mô tả sai phép toán và chưa đưa cách sửa đủ rõ.|
|DISTINCT-0000|2|Mô tả điểm dừng còn mơ hồ; chưa đủ cơ sở kết luận một khẳng định kỹ thuật sai.|
|DISTINCT-0001|1|Gợi ý chung đúng mức 1; không có khẳng định kỹ thuật cụ thể để bác bỏ.|
|DISTINCT-0010|1|Gợi ý chung đúng mức 1; chưa thể chứng minh đã nhận diện việc bỏ phần tử cuối.|
|DISTINCT-0017|2|Nêu đúng hạn chế của đếm thay đổi liên tiếp nhưng nói sai rằng phần tử đầu bị bỏ.|
|FACT-0001|3|Gợi ý chung không đưa khẳng định sai cụ thể; chương trình đúng trong miền đã xét.|
|FACT-0004|1|Gợi ý chung đúng mức 1; chưa thể chứng minh đã nhận diện lỗi phép toán.|
|FACT-0006|2|Bịa yêu cầu loại bỏ số không và chưa giải thích đúng hậu quả truyền số kế tiếp.|
|FACT-0008|2|Chỉ đúng lỗi thiếu dấu kết thúc khai báo, không đưa chỉ dẫn sửa.|
|FIB-0000|2|Bịa lỗi ở các trường hợp cơ sở và bỏ sót phần xuất thừa.|
|FIB-0007|2|Bịa lỗi ở nhánh cơ sở và bỏ sót sự lệch vị trí lưu bộ nhớ đệm.|
|FIB-0014|2|Bịa lỗi ở hai trường hợp cơ sở và bỏ sót biến lặp không thay đổi.|
|GCDARR-0005|2|Nghi ngờ các bước đúng của thuật toán, bỏ sót việc đọc thừa và phần xuất thừa.|
|GCDARR-0009|3|Nhận ra giới hạn cố định nhưng diễn giải sai phần tử được duyệt và đề xuất chưa tạo phép gộp đúng.|
|GCDARR-0013|2|Chẩn đoán đúng việc dùng giá trị nhỏ nhất, nhưng nhầm với cực đại và đưa hướng sửa ở mức chỉ chẩn đoán.|
|MAXDIFF-0003|3|Nhận ra hàm trả hằng số nhưng giải thích sai chỉ số và chưa nêu thao tác sửa khả thi.|
|MAXDIFF-0007|2|Bỏ sót nguyên nhân vòng lặp không tiến và quy sai thành thiếu phần tử cuối.|
|MAXDIFF-0008|2|Chẩn đoán đúng tệp cố định nhưng đưa thao tác sửa ở mức chỉ chẩn đoán.|
|MINA-0000|2|Bịa việc không cập nhật số bản ghi và thiếu dữ liệu truyền vào; đồng thời đưa hướng sửa.|
|MINA-0004|3|Nhầm việc xét bản ghi đầu, nhưng có hướng sửa cục bộ đúng cho trường hợp một bản ghi.|
|MINA-0016|2|Chẩn đoán đúng tệp cố định nhưng bịa thiếu tham số số lượng.|
|PERFECT-0007|2|Nêu đúng vị trí và nguyên nhân phép chia không nhận diện ước.|
|PERFECT-0011|4|Nêu đúng việc đọc thừa dữ liệu và hướng sửa dùng một lần đọc.|
|PERFECT-0018|2|Hiểu sai định nghĩa ước thực sự và bỏ sót vòng lặp không tiến.|
|PRIME-0005|2|Nhận ra loại nhầm số nguyên tố nhỏ nhất nhưng giải thích sai bước thử ước.|
|PRIME-0008|1|Lời nhắc chung tuân thủ mức nhẹ; không chứng minh đã nhận diện lỗi cụ thể trong mã.|
|PRIME-0010|3|Giải thích sai điều kiện xét căn bậc hai và chưa sửa đúng phép kiểm tra ước.|
|PRIME-0024|1|Lời nhắc chung tuân thủ mức nhẹ; không chứng minh đã nhận diện lỗi cụ thể trong mã.|
|PROD-0003|2|Nêu đúng việc bỏ tích của bản ghi cuối mà không đưa hướng sửa.|
|PROD-0015|1|Lời nhắc chung tuân thủ mức nhẹ; không chứng minh đã nhận diện lỗi cụ thể trong mã.|
|PROD-0017|3|Nhận ra phép tính sai và thiếu bản ghi cuối nhưng hướng sửa chưa gắn thành thao tác khả thi.|
|REVSTR-0001|4|Phản hồi chung chung, không nêu lỗi kỹ thuật cụ thể trên bài đảo chuỗi đúng trong phạm vi đã xét.|
|REVSTR-0007|2|Nhận ra biểu thức đáng ngờ nhưng mô tả sai vị trí ghi và chiều dịch chỉ số.|
|REVSTR-0009|1|Lời nhắc chung tuân thủ mức nhẹ; không chứng minh đã nhận diện lỗi cụ thể trong mã.|
|SECONDMAX-0004|1|Lời nhắc chung tuân thủ mức nhẹ; không chứng minh đã nhận diện lỗi cụ thể trong mã.|
|SECONDMAX-0006|1|Lời nhắc chung tuân thủ mức nhẹ; không chứng minh đã nhận diện lỗi cụ thể trong mã.|
|SECONDMAX-0009|1|Lời nhắc chung tuân thủ mức nhẹ; không chứng minh đã nhận diện lỗi cụ thể trong mã.|
|SUMB-0003|1|Lời nhắc chung tuân thủ mức nhẹ; không chứng minh đã nhận diện lỗi cụ thể trong mã.|
|SUMB-0005|1|Lời nhắc chung tuân thủ mức nhẹ; không chứng minh đã nhận diện lỗi cụ thể trong mã.|
|SUMB-0034|2|Nhận ra lỗi cú pháp nhưng thêm kết luận không có căn cứ về địa chỉ và cấp phát.|
|SUMEVEN-0000|1|Phản hồi chung chung, không tiết lộ chi tiết; bài đúng trong phạm vi bộ nhớ đã xét.|
|SUMEVEN-0008|4|Giữ được phát hiện bỏ sót phần tử đầu và nêu hướng duyệt đủ dãy.|
|SUMEVEN-0012|1|Lời nhắc chung tuân thủ mức nhẹ; không chứng minh đã nhận diện lỗi cụ thể trong mã.|

## Quyết định và kiểm chứng

Rule đã khóa trước optimizer đòi complete60, chốt semantic flags; giữ ít nhất90% positive taxonomy gain v1 trên cả hai reference; L2 location/cause và strict đều vượt BASE/v1; L3 vượt cả hai và đạt ít nhất2/6; false claims không quá v1 và thấp hơn BASE; L1 false-clean không tăng. V2 qua completion, taxonomy retention và L1 false-clean, nhưng trượt strict L2, L3, false claims và còn unknown. **Giữ R15, dừng huấn luyện tiếp; không chạy public để tìm cấu hình.**

Đây là một thay đổi dataset gồm số source, tỷ lệ clean/strata, wording target và JSON serialization; không phải ablation chứng minh riêng target repair hoặc lượng dữ liệu gây ra kết quả. Không chọn lại prompt/threshold/checkpoint theo output development. Một run không chứng minh generalization sang source/family chưa từng biết.

Runtime audit độc lập: một optimizer, epoch selection, source masks/guard,83 runtime hashes, adapter, raw→attempt→decision→final và60 first prompts đều đúng. [Independent score audit](../../outputs/task3/direct-sft-v2-20261021/review/independent-score-audit.private.json) tái tính **2699** numeric/value comparisons không dùng evaluate/feedback_summary/production_decision, không discrepancy. Hash `f5abeaa86ff44d23c23b0775b520d9164db3c117164edf21e99d1d3d898341bc`.

Private root: `/workspace/llm-final-project/outputs/task3/direct-sft-v2-20261021/`. `analysis/` giữ56target/6L3/11L2/unknown và mọi version; `data/` giữ68candidate/40accepted/28excluded, registry và authoring; `targets/` giữ constraints/changelog/final330targets; `frozen/` giữ inputs/split/config/rubric/token/seal; `training/` giữ one marker/log/epochs/adapter; `inference/arm-V2/` giữ actual messages/raw/final; `review/` giữ source proofs/ledgers/audits. Source/raw/weights/predictions không vào Git.

Commands **đã chạy**, không hướng dẫn optimizer/inference lần hai:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/workspace/llm-final-project/outputs/task3/hf-cache .venv-task3/bin/python scripts/task3_direct_sft_v2_prepare.py prepare
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/workspace/llm-final-project/outputs/task3/hf-cache .venv-task3/bin/python scripts/task3_direct_sft_v2_train.py --run
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/workspace/llm-final-project/outputs/task3/hf-cache .venv-task3/bin/python scripts/task3_direct_sft_v2_infer.py --arm V2 --start
.venv-task3/bin/python scripts/task3_direct_sft_v2_report.py --score
.venv-task3/bin/python scripts/task3_direct_sft_v2_prepare.py verify
.venv-task3/bin/python -m pytest -q tests/test_task3*.py
.venv-task3/bin/python -m pytest -q
```

Prepare/start/optimizer/report output dùng exclusive names. Không xóa seal/marker để chạy lại; dùng `verify` cho artifact hiện tại. Private authoring/assembly/combine và independent audit scripts được giữ cùng hashes để tái kiểm; judgment ngữ nghĩa không thể được chứng minh chỉ bằng chạy script.

Pre-model Task3 **1019 passed,2 skipped**, gồm30 artificial tests mới. Final verification/commands/log hashes và preservation ở [Verification JSON](TASK3_DIRECT_SFT_V2_VERIFICATION_20261021.json). Global pytest collect lỗi hai module Task1 `test_clm_zeroshot_task1.py`, `test_task1_clm_probe.py` vì thiếu sklearn; không tuyên bố full repo pass, không cài dependency ngoài phạm vi. Các test C++ có sẵn chỉ chạy artificial fixtures, không chứng minh đã compile/run source của pilot.

**897 baseline files giữ nguyên bytes**, gồm R15, DIRECT v1, các seal và artifact được bảo vệ. Public predictions chỉ hash bảo toàn, vẫn `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`. Commit chỉ code/config/test/metadata/report mới; HEAD cuối bàn giao trong chat, không push.
