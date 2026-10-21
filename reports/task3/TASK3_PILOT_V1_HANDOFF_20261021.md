# Task 3 — Một pilot QLoRA và paired Evaluation v2 (2026-10-21)

**Đã chạy đúng một optimizer run và một pass 96 requests cho mỗi nhánh A/B/C. C cao hơn B về schema-completion và micro/macro-F1 trong lượt này, nhưng chưa đủ bằng chứng cải thiện đồng thời chất lượng feedback. Không thay R15 bằng candidate này.** C hoàn tất ít hơn A; annotation exact set C12/60 cũng thấp hơn A13/60. Evaluation v2 vẫn là controlled holdout có prior exposure, không phải benchmark mù. Không dùng public score để quyết định; không public inference, leaderboard hoặc push.

HEAD trước lượt này: `c7376ec25c84cdbdb79fef3803e0203c30e1faa9`, branch `feat/task3-quality-round5`, working tree ban đầu sạch. Chỉ thêm file mới; Evaluation v1/v2, train supplement v1 và các seal giữ nguyên. Source, target, quote chi tiết, adapter, raw attempts và predictions nằm dưới ignored `outputs/task3/pilot-v1-20261021/`.

## Dữ liệu và kiểm tra trước optimizer

ZIP được kiểm theo bytes: `6bda70c29254a3bce91933b65f4a311d73a052e72d181c97e977152e14602f9b`. Không suy version từ tên ZIP. Verify lại source/target supplement, Evaluation v2 và train registry; guard kiểm identity/group/family/exact/token/rename/near-duplicate trên đúng source bytes ở `before_targets` và `before_optimizer`. Trainer kiểm lại ngay trước optimizer step đầu; marker độc quyền chặn train lần hai hoặc resume.

Review TRAIN-only chọn trước **32 source / 128 D,L1,L2,L3 targets**: cả 4 source dự kiến lỗi biên dịch, 1 AR, 3 LP, 3 EC, 6 FN, 10 scoped-clean và 13 multi_problem (các nhóm có thể chồng nhau). Không phát hiện diagnosis/counterexample gốc sai thực chất trong tập review này; phát hiện một hướng sửa L3 chưa đủ. **Loại `SUP1-PALIN-008` cùng cả 4 example**: lặp lại phép so hai đầu nhưng không giữ mismatch trước đó có thể ghi đè false thành true; phản ví dụ sửa giả định `123322` được suy luận tĩnh. Không sửa target seal v1. Exclusion/source/target hashes nằm trong [pilot freeze](TASK3_PILOT_V1_FREEZE_20261021.json).

Không có compiler sandbox dùng được: namespace probe bị `Operation not permitted`; không chạy/biên dịch mã sinh viên trên host. **Compiler-confirmed = 0, testcase-executed = 0**. Evidence là agent static review, không human-verified. Review không bảo đảm mọi target còn lại đúng. Diagnostic targets còn domain/evidence bằng tiếng Anh và provenance `author_static` cũ; giữ nguyên và khai báo hạn chế này.

Giữ 87 source / 348 examples. Chia theo **source**, seed42, khoảng 20% mỗi TRAIN family, làm tròn gần nhất và ít nhất một validation source/family. Bốn example của cùng source ở cùng phía. Family train/evaluation giữ nguyên supplement/v2; không tạo split evaluation mới.

| Phía | Source | D + feedback | Clean / defect | Single / multi |
|---|---:|---:|---:|---:|
|Optimizer TRAIN|70|70 + 210 = 280|17 / 53|41 / 29|
|Internal validation TRAIN-only|17|17 + 51 = 68|1 / 16|9 / 8|

| Family, bỏ tiền tố SYN- | Train | Internal val |
|---|---:|---:|
|COUNT|8|2|
|COUNTEVEN|6|2|
|COUNTVOWEL|9|2|
|GEN|5|1|
|MAXARR|10|2|
|PALIN|8|2|
|POWER|6|1|
|RANGE|6|2|
|SUMPAIR|4|1|
|UPPER|8|2|

| Nhãn | Train source | Internal val source |
|---|---:|---:|
|Lỗi biên dịch|2|2|
|Lỗi nhập/xuất|4|2|
|Lỗi logic|21|9|
|Lỗi vòng lặp|2|0|
|Lỗi mảng/chuỗi|1|0|
|Lỗi hàm|6|0|
|Lỗi edge case|3|0|
|Lỗi thuật toán|10|2|
|Lỗi hard-code|4|1|
|Lỗi style|0|0|

Validation thiếu nhiều nhóm hiếm và chỉ có một clean; loss không chứng minh giữ được những nhóm này. Supplement là synthetic có review; prior family/template exposure vẫn tồn tại.

## Protocol đã khóa và một lần training

[Config](../../configs/task3/pilot_v1_20261021.json) và [freeze manifest](TASK3_PILOT_V1_FREEZE_20261021.json) khóa trước optimizer và trước prediction evaluation. Manifest SHA-256 `4fe92d6c2437a18d41b724e909fc334820ce5d3e909989e0a207bc2f575b9dcf`; private seal `5311ee99b212994c97453c9c5cf4b2e2ebac2a1f5cbac965a1e44a2e07b749ca`. Pin cả runtime dependencies nội bộ, không chỉ file entrypoint. Reporter offline được viết riêng, không nằm trong runtime model.

Diagnosis có task marker riêng, nhận statement/problems/prototype/prerequisite/policy/code/compiler/domain được phép, **không requested Level**; trả status, taxonomy, finding/quote/location/cause/evidence/basis/domain. Feedback nhận source, diagnosis và Level, chỉ sinh feedback; final taxonomy copy từ diagnosis. TRAIN feedback dùng target diagnosis (teacher forcing); inference dùng predicted diagnosis. Domain TRAIN là giả định scoped ghi trong input; evaluation chỉ có ràng buộc đề tường minh, không lấy domain từ reference. Quote gate chỉ xác nhận quote tồn tại, không chứng minh suy luận đúng.

Prompt và padding được mask. Loss completion CE trung bình theo example, D weight2, từng feedback weight2/3; một D và ba feedback có tổng trọng số bằng nhau. Mỗi example xuất hiện một lần/epoch, không sampling ưu tiên feedback. Tokenizer thật kiểm prefix/supervised span; vượt cap thì fail, không truncate.

| Token audit / epoch | Train | Internal val |
|---|---:|---:|
|Input + target tokens|279014|70429|
|Supervised tokens|32205|8101|
|D supervised / feedback supervised|20494 / 11711|5402 / 2699|
|Sequence dài nhất, cap8192|1596|1525|

Model **Qwen/Qwen2.5-Coder-7B-Instruct**, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`; base logical parameters **7,615,616,512**, LoRA trainable **40,370,176**, tổng khoảng **7.656B**, dưới 10B. GPU RTX5090 32GB, NF4 double quantization, BF16 compute; kiểm thực tế 196 bitsandbytes layers. Torch2.8.0+cu128, transformers4.57.1, peft0.17.1, bitsandbytes0.48.1, accelerate1.11.0, datasets4.3.0.

LoRA r16/alpha32/dropout0.05 trên q/k/v/o/gate/up/down; lr1e-4 cosine, warmup0.03, batch1×accum4, seed42, **2 epochs / 140 optimizer steps trong một run**. Thực dùng 560 example exposures, 558028 input+target tokens và 64410 supervised tokens. Cả 140 gradient checks hữu hạn/khác0; LoRA update hữu hạn/khác0.

Chọn epoch theo internal validation equal-source/equal-task loss, earliest tie: trước train1.529214; epoch1 **0.504510**, epoch2 **0.486804**, chọn **epoch2**. Không dùng Evaluation v2 để chọn. Adapter tensor SHA-256 `3c9c7b625553a87f36fb6f6c71f081e8f00243b8c4dc460bfe76d07d9149311f`, 161533192 bytes. Loss thấp hơn không phải kết luận chất lượng.

Wall load/train/save284.40s; GPU training wall256.30s gồm epoch-validation/save callback; peak allocated11.44GiB, reserved16.98GiB. Một setup attempt trước đó dừng do thiếu `datasets`, **trước model load và optimizer**; cài đúng pin `datasets==4.3.0` trong requirements rồi chạy optimizer duy nhất. Giữ cả hai attempt logs; không đổi config/data. Không gọi đó là hai pilot.

## Paired inference trên nguyên Evaluation v2

Đúng 60 primary + 36 counterfactual requests / 12 source triples, mỗi arm xử lý đủ96/96. A là R15 joint base, B là diagnosis→feedback base, C cùng flow/prompt B với adapter đã chọn. B/C khác adapter; diagnosis prompt hashes bằng nhau theo source, feedback input có thể khác do predicted diagnosis. Không gold/reference/teacher feedback vào model inference. Evaluation reference chỉ dùng retrospective scoring/review sau khi training và cả ba arm hoàn tất; không sửa prompt/guard/checkpoint rồi chạy lại.

Cùng revision, greedy seed42, NF4 double/BF16, context16384, feedback cap1024/L4 cap1536; diagnosis B/C cap2048. A giữ R15 prompt/schema/disclosure/retry tối đa3; dùng deadline60s chung của pilot thay R15 mặc định45s. B/C không content retry hoặc clean fallback. Diagnostic schema/quote sai hoặc uncertain được giữ lỗi/unresolved; cache cả thành công và thất bại một lần/source, độc lập Level. Không lấp lỗi bằng `[]`.

| Chỉ số | A joint base | B hai bước base | C hai bước adapter |
|---|---:|---:|---:|
|Primary completed /60|60|2|54|
|Primary schema_error / unresolved|0 / 0|47 / 11|6 / 0|
|Tất cả completed /96|96|2|87|
|Tất cả schema_error / unresolved|0 / 0|77 / 17|9 / 0|
|Runtime error /96|0|0|0|
|Raw generation calls|118|62|147|
|Retry calls|22|0|0|
|Fallback requests /96|8|0|0|
|Raw schema valid|117/118 joint attempts|13/60 diagnosis|54/60 diagnosis|
|Resolved diagnosis /60|không có stage riêng|2|54|
|Feedback schema valid / attempted|96/96 final|2/2|87/87|
|Final feedback median words|27|25.5|28|
|Final feedback mean characters|132.51|116.00|119.72|
|Generation latency tổng, s|106.49|174.39|452.58|
|Input / output tokens|91892 / 8296|45968 / 14586|116291 / 22091|

Độ dài đếm trên final thật, gồm primary và CF; words tách whitespace. Latency là tổng generation time, không phải end-to-end wall/cache download/load; chi phí B/C gồm diagnosis. A có một raw schema failure được retry; C có hai generations chạm length cap, còn lại EOS. Unicode detector không thấy Han/kana/Hangul trong final; điều này không tự chứng minh tiếng Việt đúng hoặc không có lỗi ngữ nghĩa.

B bị chặn chủ yếu ở diagnosis: 22 evidence-schema errors, 20 finding ngoài taxonomy, 4 quote không có trong source/compiler, 1 diagnostic-schema error; thêm11 uncertain. C còn 6 diagnosis lỗi:3 strict-JSON,1 quote,1 taxonomy-list,1 evidence-field. Mọi feedback đã được gọi của B/C đều parse được. Gain completion đi cùng tỷ lệ tuân thủ schema cao hơn; chưa tách được học format khỏi chất lượng chẩn đoán. Không kết luận base không thể chẩn đoán chỉ từ gate rất chặt này.

## Taxonomy — chỉ 60 primary source

Đủ10 nhãn, macro zero_division0. Missing/schema/uncertain vẫn có FN, không nhận exact-clean. Hai reference được báo độc lập, không đổi mapping sau output. Source-reference style có support0; annotation v2 style có1. Không bịa style hoặc bỏ nhóm khỏi macro để tăng điểm.

| Reference và metric | A | B | C |
|---|---:|---:|---:|
|Annotation v2 micro-F1|0.1818|0.0000|0.2655|
|Annotation v2 macro-F1|0.0826|0.0000|0.1687|
|Annotation v2 exact set /60|13|2|12|
|Source-reference micro-F1|0.1400|0.0000|0.2982|
|Source-reference macro-F1|0.0744|0.0000|0.1806|
|Source-reference exact set /60|11|2|16|

Ô A/B/C dưới là TP/FP/FN; support là số source mang nhãn, có thể nhiều nhãn/source.

| Annotation v2 | Support | A | B | C |
|---|---:|---|---|---|
|Lỗi biên dịch|4|2/2/2|0/0/4|1/0/3|
|Lỗi nhập/xuất|1|0/4/1|0/0/1|0/1/1|
|Lỗi logic|12|7/24/5|0/0/12|7/22/5|
|Lỗi vòng lặp|9|0/0/9|0/0/9|2/0/7|
|Lỗi mảng/chuỗi|9|0/0/9|0/0/9|0/1/9|
|Lỗi hàm|8|0/0/8|0/0/8|1/2/7|
|Lỗi edge case|2|0/0/2|0/0/2|0/4/2|
|Lỗi thuật toán|8|0/0/8|0/0/8|4/8/4|
|Lỗi hard-code|6|0/0/6|0/0/6|0/0/6|
|Lỗi style|1|0/0/1|0/0/1|0/0/1|

| Source-reference | Support | A | B | C |
|---|---:|---|---|---|
|Lỗi biên dịch|4|2/2/2|0/0/4|1/0/3|
|Lỗi nhập/xuất|5|0/4/5|0/0/5|0/1/5|
|Lỗi logic|10|5/26/5|0/0/10|9/20/1|
|Lỗi vòng lặp|10|0/0/10|0/0/10|2/0/8|
|Lỗi mảng/chuỗi|9|0/0/9|0/0/9|0/1/9|
|Lỗi hàm|9|0/0/9|0/0/9|1/2/8|
|Lỗi edge case|2|0/0/2|0/0/2|0/4/2|
|Lỗi thuật toán|6|0/0/6|0/0/6|4/8/2|
|Lỗi hard-code|6|0/0/6|0/0/6|0/0/6|
|Lỗi style|0|0/0/0|0/0/0|0/0/0|

## Counterfactual — báo riêng, không nhân trọng số taxonomy

| 12 source × L1/L2/L3 | A | B | C |
|---|---:|---:|---:|
|Completed triples|12/12|0/12|11/12|
|Incomplete triples|0|12|1|
|Đổi taxonomy khi chỉ đổi Level, trên completed triples|11/12 (91.67%)|không xác định|0/11 (0%)|

C invariance được bảo đảm bởi flow/cache/copy, không chứng minh diagnosis đúng. Không gọi B invariant thành công khi không triple nào hoàn tất. Không gộp 36 CF vào 60 primary như quan sát độc lập.

## Review nội dung và quyết định

Chọn **24 primary ID trước prediction**, seed42 theo metadata, ít nhất một/source family: đủ18 evaluation family, Level1/2/3/4 = **9/12/2/1**, gồm21 defect và3 scoped-clean. Hai agent review từng source và A/B/C cùng nhau, không xem aggregate F1 trước verdict. Ledger gắn `output_digest`, reviewer/rationale/evidence và bool/null. Đây là **agent review**, nhạy với ranh giới disclosure và miền giả định, không human-verified; không dùng keyword gate hoặc model judge làm ground truth. False technical claim đếm nguyên nhân/số liệu cụ thể sai hoặc assurance sạch sai; taxonomy mismatch và generic concern không có căn cứ được ghi riêng, không tự đồng nhất với flag này.

| Trên 24 ID cố định | A | B | C |
|---|---:|---:|---:|
|Có final để review /24|24|0|21|
|Final có false technical claim / final được review|11/24|không xác định|11/21|
|False-clean assurance / defect final được review|4/21|không xác định|0/18|
|Missing core theo yêu cầu Level / defect final được review|10/21|không xác định|9/18|
|L1 disclosure / L1 final được review|1/9|không xác định|0/8|
|L2 concrete repair leak / L2 final được review|3/12|không xác định|0/10|
|L2 đúng vị trí/nguyên nhân hữu ích / defect L2 final|7/11|không xác định|2/9|
|L2 hữu ích **và** không repair leak/false claim / defect L2 final|5/11|không xác định|1/9|
|L3 đúng cause + feasible repair / defect L3 final|0/1|không xác định|0/1|
|Tiếng Việt / final được review|24/24|không xác định|21/21|
|CJK ngữ nghĩa / final được review|0/24|không xác định|0/21|

L2 strict ở trên là giao các verdict ledger, không thay định nghĩa evaluator gốc. Trên **21 common-completed A/C** cùng ID, false-claim là11/21 ở cả hai; riêng9 defect L2 common, usefulness A5/9 so C2/9, strict A4/9 so C1/9. Vì vậy không giải thích tỷ lệ khác nhau chỉ bằng việc C bỏ ba ca khó. B không có final trên24 selected; hai final khác của B không được chọn bổ sung sau output. **Không có bằng chứng paired conditional feedback C>B** từ tập review này.

Semantic ngoài selection vẫn pending: primary A36/60, B60/60, C39/60 (gồm output thiếu và completed chưa review); CF không được semantic review. Không suy0/pass cho missing hoặc unreviewed. L1 generic concern có thể đạt contract mà không nêu cause; điều đó không xác nhận diagnosis phía trước đúng. C không false-clean trong18 defect final đã review, nhưng vẫn có9/18 missing-core theo Level.

Raw diagnosis B có ít nhất một false technical claim trên **12/24** source reviewed; C **22/24**, gồm20/21 schema-accepted diagnoses trong selection. Các lỗi có phép tính counterexample sai, nguyên nhân bịa, dùng helper không được gọi và mô tả code không tồn tại. Đây là **record-level raw-D flags**, không atomic-claim precision; hai model có số/lượng claim khác nhau. Không nhập các claim raw bị bỏ khỏi feedback generic vào final false-claim count. Schema-valid/quote có thật không bảo đảm bằng chứng đúng; các câu tự xưng đã static-verified trong model raw không phải chứng nhận mới.

Bảng dưới giữ **toàn bộ24 ID selection**, không chỉ ca thắng. Mọi ID có tiền tố `SYN-`. B không có final ở cả24; `ERR` khác `[]`. Source quote, domain, counterexample/invariant và nguyên văn output nằm trong private review **[a](../../outputs/task3/pilot-v1-20261021/review/review-a.private.json)** cho12 dòng đầu và **[b](../../outputs/task3/pilot-v1-20261021/review/review-b.private.json)** cho12 dòng sau. [Results metadata](TASK3_PILOT_V1_RESULTS_20261021.json) khóa source hash, quote-list hash, raw/final hashes và verdict theo từng ID; không đưa private quote/source hoặc predictions vào Git.

| ID | Level | A so với C; source evidence và thay đổi |
|---|---:|---|
|ARM-0000|1|C tránh assurance sạch sai của A; cả hai bỏ stdout prompt. C raw tính4096+16+0+4096 thành8317 thay vì8208. Mixed, không là diagnosis gain.|
|BASE2-0006|4|Source gọi chuyển cơ số với n+1:10→1011 thay1010. C D thấy đúng, final chỉ concern chung; A giữ cause đúng. **Feedback C xấu đi**.|
|COUNTGT-0004|1|C taxonomy gần source hơn A[] nhưng raw counterexample sai; cả hai final generic. Không chứng minh reasoning cải thiện.|
|COUNTUPPER-0001|3|Scoped ASCII clean; ABc có2 chữ hoa. A đúng trong scope; C bịa thiếu một đơn vị và gợi ý đếm cặp kề nhau. **C gây lỗi cho code sạch**.|
|DIGITSUM-0006|2|C giảm repair leak của A nhưng thêm impact số âm/line sai; cause hữu ích không đủ thành strict pass.|
|DIGITSUM-0007|2|A thấy call n+1; C bịa tổng với chữ số cuối. n=9 source in1, bác bỏ C raw in10. **C xấu đi**.|
|DISTINCT-0001|1|Scoped-clean theo invariant đếm distinct; A sạch có căn cứ. C gán AL, raw đếm sai; generic concern không phát biểu cause sai nhưng diagnosis xấu đi.|
|FACT-0006|2|A có location/cause đúng; C bịa recursion trong hàm lặp và truncation, finalERR. **Mất completion và finding**.|
|FIB-0014|2|Biến i không được cập nhật; A/C đều mô tả sai skipped/insufficient iterations. Không có grounded improvement.|
|GCDARR-0005|2|C bỏ repair directive của A nhưng cả hai giữ claim thuật toán sai và bỏ hai finding thật. Mixed.|
|GCDARR-0013|2|Source lấy min thay GCD; A đúng. C bịa thứ tự và expected6 cho[6,4,2], GCD thật2. **C xấu đi**.|
|MAXDIFF-0007|2|A thấy thiếu cập nhật i nhưng leak repair. C bịa fixed-capacity truncation, raw bị cắt và finalERR. **C mất completion**.|
|MINA-0000|2|Scoped-clean theo file/min/sum invariant. A bịa file không tồn tại; C coi helper nhân đôi không được gọi là lỗi active. Cả hai false claim.|
|MINA-0004|3|Cận n-1 bỏ cuối, singleton P3 trả0; hai counterexample riêng chứng minh. A/C đều giải thích sai bỏ đầu, C hướng sửa sai. Không có L3 gain.|
|MINA-0016|2|Source mở data.csv thay filename ma.csv; cả hai nêu đúng. C cụ thể hóa prob1/prerequisite, nhưng raw witness đảo nội dung hai file. Gain nhỏ ở final, raw vẫn sai.|
|PERFECT-0018|2|Sau vòng chia, j đã vượt căn; A/C giải thích square/divisor sai. C raw còn giả định biến local có0 sau uninitialized read. Không claim output xác định sau UB.|
|PRIME-0008|1|B raw nêu đúng call n+1 nhưng sai schema; C format được nhưng witness đảo expected/actual cho4. Generic final không cứu độ đúng D.|
|PROD-0003|2|Hai products1,6: cận n-1 trả1 thay6. A thấy bỏ cuối; C bịa một phần tử giữa/tích giữa hai bản ghi cuối. **C mất cause đúng**.|
|REVSTR-0009|1|C raw nhận ra không gọi hàm/empty stdout; evidence actual_derived rỗng bị schema chặn. A có final fallback, CERR. **Guard chặn finding đúng**, không coi missing là lỗi ngữ nghĩa/pass.|
|SECONDMAX-0004|1|A chỉ trích sai thuật toán và disclosure; C generic concern phù hợp Level. C raw vẫn sai witness và bỏ indeterminate a[n]. Gain final contract, không diagnosis gain.|
|SUMB-0003|1|A assurance sạch sai; C concern đúng mức. Source gán giá trị bản ghi kế: a=1,3,2 trả2 thay3. C raw số witness sai. **Giảm false-clean final**.|
|SUMB-0005|1|Một b=-3 bị điều kiện dương bỏ, tổng0 thay-3. C tránh false-clean của A, nhưng D đổ lỗi allocation n+1 vô hại. **Gain final, D không đúng**.|
|SUMB-0034|2|Thiếu semicolon sau allocation. A bịa thiếu ngoặc đóng; C bịa resize/exception/capacity. Label BC đúng không cứu cause sai.|
|SUMEVEN-0012|1|Input2 bị phép chia/2 kiểm tra sai bỏ, tổng0 thay2. C tránh false-clean của A; witness raw2,4,5,6 lại sai (đúng expected12/actual0). **Gain final, D không đúng**.|

**Quan sát:** adapter tăng khả năng trả schema và primary micro/macro-F1 so với B, giữ taxonomy qua Level ở interface, giảm một số L1/L2 leak và assurance sạch sai so với A. Đồng thời raw-D false claims nhiều trong selection; L2 strict usefulness giảm so A, L3 selected defect không có repair đạt, một số cause đúng của A/B bị mất. BASE2 cho thấy D đúng nhưng chuyển sang feedback làm mất nội dung; REVSTR cho thấy schema evidence quá chặt cũng gây abstention không cần thiết.

**Suy luận có giới hạn:** diagnosis/evidence là bottleneck quan sát lớn của C, cộng thêm chuyển D→feedback và schema contract. TRAIN review đã loại một repair chưa đủ; target ít/không cân bằng, teacher forcing và prose mẫu có thể góp phần, nhưng pilot này không tách được tác động của target quality khỏi giới hạn generalization/model. Không kết luận mọi lỗi là do target, cũng không gọi F1/loss gain là reasoning gain. **Chưa chứng minh adapter cải thiện đồng thời taxonomy và feedback; giữ R15 baseline, không đóng băng candidate thay thế.**

## Artifacts và tái kiểm

[Results JSON](TASK3_PILOT_V1_RESULTS_20261021.json) chứa hai bảng taxonomy/per-label, completion, CF, semantic pending/assessed, chi phí và **mọi request raw/final SHA**; không chứa nội dung predictions. Results SHA-256 `7dc281df49bf26be6004bd9f54e4984cdbf0212229d7c309d7a3423d8dc3e550`. [Verification JSON](TASK3_PILOT_V1_VERIFICATION_20261021.json) lưu commands/log hashes, preservation và independent audit.

Root riêng tư: `/workspace/llm-final-project/outputs/task3/pilot-v1-20261021/`:

- `frozen/`: config, examples/source split, registry, token audit, selection, seal; `train-quality-audit.private.json` và exclusion có lý do/hash.
- `training/training-result.json`, `training/attempts/`, `training/epoch-{1,2}/adapter/`, `training/adapter/`, optimizer marker và gate evidence.
- `inference/arm-{A,B,C}/`: status96/96, raw/decisions/diagnoses, timing/token metadata và exact predictions; A giữ legacy attempts/traces/fallback.
- `review/review-{a,b}.private.json`, source quotes/proofs, normalized72 source-arm rows, combined `ledger-{A,B,C}.private.json`; chỉ24/0/21 completed rows có final ledger.
- `reports/{arm-A,arm-B,arm-C,comparison}.summary.private.json`: frozen scorer + final reporter, hash-bound ledger/input provenance. Early `raw-diagnostics-retrospective.private.json` giữ nguyên để audit; field A final-schema của bản early bị0 vì dùng nhầm log shape, đã sửa **chỉ reporter offline** và thêm artificial regression test. Final summary là bản đúng96/96; evaluator/model/config/seal không đổi.
- `independent-final-audit.private.json`: tái tính metric/tokenizer, một optimizer, cache/copy và preservation; không finding integrity/metric còn mở. Independent report review đã sửa hai câu suy diễn quá mức về completion/causal format learning.

Commands **đã chạy**, không hướng dẫn train/inference lần hai:

```bash
.venv-task3/bin/python scripts/task3_pilot_prepare.py prepare
.venv-task3/bin/python scripts/task3_pilot_prepare.py verify
.venv-task3/bin/python scripts/task3_pilot_train.py --run
.venv-task3/bin/python scripts/task3_pilot_infer.py --arm A --start
.venv-task3/bin/python scripts/task3_pilot_infer.py --arm B --start
.venv-task3/bin/python scripts/task3_pilot_infer.py --arm C --start
.venv-task3/bin/python scripts/task3_pilot_report.py --score \
  --ledger-A outputs/task3/pilot-v1-20261021/review/ledger-A.private.json \
  --ledger-B outputs/task3/pilot-v1-20261021/review/ledger-B.private.json \
  --ledger-C outputs/task3/pilot-v1-20261021/review/ledger-C.private.json
.venv-task3/bin/python -m pytest -q tests/test_task3*.py
.venv-task3/bin/python -m pytest --collect-only -q
```

Chạy `verify` để tái kiểm hiện trạng. Prepare/optimizer/inference start/report output names đều exclusive; không xóa marker/seal để chạy lại hoặc đổi kết quả. B/C dùng cùng default base cache, offline khi inference; A tải hai shard còn thiếu của đúng pinned revision trước generation. Checkpoint selection hoàn tất trước inference; không dùng adapter R18.

Kiểm thử cuối **836 passed, 2 skipped**, gồm57 test pilot mới. Hai test cũ trước đây skipped nay chạy được sau cài dependency TRAIN đã pin. Global collection:1132 tests collected nhưng **2 Task1 collection errors vì thiếu sklearn**, không tuyên bố full repo pass và không cài dependency ngoài phạm vi. Các test C++ sẵn có chỉ dùng artificial fixtures, không phải bằng chứng đã compile/run source TRAIN/evaluation.

Sau train/inference/review/test, **595 baseline files và154 protected artifacts giữ nguyên hash**. Public predictions chỉ hash, vẫn `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`. Seal v1/v2 và supplement không mở lại/ghi đè; dữ liệu/reference chưa được dùng để sửa prompt/checkpoint sau output. Một yêu cầu đọc reference sớm của reviewer bị auto-review từ chối trước khi mọi arm xong; giữ packet blocked, không đọc. Khi cả ba arm hoàn tất, quyền retrospective step4 được xác nhận và đọc mới được chấp nhận; không bypass bằng đường gián tiếp.

Commit chỉ code/test/config/metadata/report mới; HEAD cuối ghi trong bàn giao chat. Không push.
