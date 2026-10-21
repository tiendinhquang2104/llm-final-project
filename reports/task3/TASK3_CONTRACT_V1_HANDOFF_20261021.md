# Task 3 — Diagnosis contract v1, base 7B, TRAIN-only

**Đã chạy một pass R15 và một pass SHORT trên đúng30 source/Level đã khóa. SHORT không tạo được final nào: cả30 raw diagnosis có Markdown fence và bị parser JSON thuần từ chối. Không có feedback generation để so chất lượng L2/L3 của SHORT với R15. Dừng ở báo cáo; giữ R15 production, không submission/public inference/push.** Không train, không adapter, không chọn checkpoint, không chạy lại bằng prompt hoặc validator đã nới.

HEAD trước lượt này `1e54ddea9124b7c6415858f8fbce5cc14a81bb24`, branch `feat/task3-quality-round5`. Chỉ thêm file mới. Các seal cũ và bundle24 giữ nguyên. Đây là **TRAIN development có prior exposure**, không phải holdout/benchmark mù; kết quả không chứng minh generalization.

## Dữ liệu và khóa trước model

Chọn metadata-only từ88 source supplement đã seal; không đọc target feedback/teacher prose, Evaluation v2, public, leaderboard hoặc nội dung bundle24 để chọn source/prompt/config. Selection được ghi trước review source và trước mọi generation. Giữ stable exclusion `SUP1-PALIN-008`; không sửa source/target v1. Seed42, đúng30 source, mỗi source một requested Level.

| Phân bố | Số lượng |
|---|---:|
|Scoped-clean / defect|6 / 24|
|Single / multi|16 / 14|
|Family TRAIN|10|
|L1 / L2 / L3 / L4|8 / 12 / 8 / 2|
|Clean L1 / L2 / L3 / L4|2 / 2 / 2 / 0|
|Compile-error dự kiến L1 / L2 / L3 / L4|1 / 1 / 1 / 1|

Giữ16/14 thay15/15 để phủ cả9 nhóm được source supplement hỗ trợ. Annotation support: BC4, IO1, LG5, LP2, AR1, FN6, EC3, AL1, HC1, ST0. Không tạo style để đủ quota. Đủ10 family: UPPER3, RANGE3, MAXARR5, COUNTVOWEL4, GEN3, COUNT4, COUNTEVEN3, PALIN1, SUMPAIR1, POWER3.

SUP1 là code mới do agent viết; **không có official annotation v2 của ZIP cho chính30 code này**. Bảng annotation dưới dùng nhãn source supplement đã seal, là annotation do agent tạo. Bảng source-review dùng review tĩnh mới; không gán nhãn bài gốc khác code. Review giữ4 tập nhãn chưa chốt: MAXARR005/007/011 và UPPER006; mechanism vẫn được review, nhưng taxonomy source-reference=null, không đổi thành clean. Source-reference chấm26 source, annotation chấm30. Không ép taxonomy để đạt agreement.

Compiler-confirmed/testcase-executed đều0. Namespace probe với lệnh `true` bị `Operation not permitted`; không chạy/biên dịch C++ sinh viên trên host. Evidence là source quote + phản ví dụ/invariant suy luận tĩnh, **agent review, không human-verified**. GEN007 có caveat harness gọi P4 độc lập; COUNTEVEN008 dùng domain filename là tham số đầu vào. Các caveat được giữ trong private reference.

Audit trước model phát hiện và sửa ba lỗi implementation/projection bằng artificial regression tests: representation Level `L1`..`L4`; domain POWER có câu nhận định phép tính sai/counterexample; problem metadata khác native R15. Model chỉ nhận ràng buộc đầu vào sau projection, không nhận nhận định lỗi. Native R15 và SHORT dùng cùng statement/code/problem/prototype/grading_policy/compiler; domain được thêm giống nhau vào statement. Problem keys theo native R15 là pid/statement/prototype, prerequisite grading_policy giữ nguyên. Full domain/problem gốc ở private reference. Domain sanitizer là projection đã review cho30 source, không được gọi là máy phát hiện mọi leakage ngôn ngữ tự nhiên.

[Freeze manifest](TASK3_CONTRACT_V1_FREEZE_20261021.json) SHA-256 `971539a0ab9ceb5883cc3ada5e08c192def4b0911739f39292f5f77f75a4db40`; private seal `d5ba90181827eb6c54c47fa8684f6201b06d96a7755e069fa9d84e5c634934f4`. Selection SHA `9746efcb047e9b517ce7a97be04e5f89e030383e9302018d563a1d6257b0ecd0`, fresh source reference SHA `ef312c11c5de394ca82ae29c85215d52e637af1508bbeb64796a803c46395471`. Source/config/reference/rubric/runtime đều khóa trước model;50 artificial tests pass trước generation.

## Contract và giới hạn validator

Diagnosis có đúng status (`defective/clean/uncertain`), taxonomy_error (10 nhãn chính thức) và findings; mỗi finding gồm label/quote/location/cause_vi, tùy chọn line. Cho phép nhiều finding độc lập. Không yêu cầu model sinh input/expected/actual/evidence hoặc lời tự chứng nhận. Prompt yêu cầu đọc main/lời gọi, helper/comment không chạy, I/O, cập nhật vòng lặp, cận mảng và điều kiện đề; ưu tiên lỗi compiler/tiên quyết khi có căn cứ; JSON cuối, không chain of thought. Diagnosis không nhận Level.

Validator chỉ kiểm strict JSON/schema/labels, quote khớp source, các line claim ở line/location/cause_vi trỏ đúng quote. Comment-only được reject khi lexical scanner đủ căn cứ. Literal có thể là giá trị operand, nên chỉ ghi lexical class/cảnh báo; không reject mọi literal. C++ line-splice/trigraph/preprocessor/unterminated literal hoặc helper chưa xác định call path đều **unverified**, không được gọi là active/reachable đã chứng minh. Không có AST/compiler/callgraph proof; heuristic helper tên chỉ xuất hiện một lần là warning, không gate có vẻ chắc chắn. Kể cả accepted, semantic_correctness/reachability vẫn unverified.

Artificial fixtures phủ empty stdout (không đòi evidence string), comment, literal/raw string, helper không gọi, loop thiếu update, nhiều lỗi, nhãn/schema sai và line references mâu thuẫn. Test accepted chỉ chứng minh validation behavior, không chứng minh chương trình/finding đúng.

Feedback chỉ nhận source + predicted diagnosis + Level, taxonomy copy từ diagnosis. L1 nhẹ, không vị trí/cause/repair hoặc khen sạch khi uncertain; L2 vị trí/cause không repair; L3 thêm hướng sửa, không toàn lời giải; L4 giữ clear findings và có thể minh họa xử lý. Không thêm witness chưa xác minh hoặc câu tự xưng kiểm chứng. Không retry/fallback ở SHORT. Uncertain có thể tạo feedback thật nhưng taxonomy abstains và không được thưởng exact-clean. **Trong run thực tế không có diagnosis qua parser, nên toàn bộ feedback behavior của SHORT chưa được kiểm tra bằng model.**

## Một paired pass, không adapter

Qwen/Qwen2.5-Coder-7B-Instruct revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, chỉ base; RTX5090 32GB, NF4 double quant/BF16 compute, kiểm thực tế bnb layers và không PEFT. Greedy seed42, context16384, feedback cap1024/L4 cap1536, SHORT diagnosis cap1536, deadline60s. R15 giữ native joint prompt/controller, tối đa3 attempts, few-shot0. Không optimizer/checkpoint mới. Cả hai arm dùng canonical exclusive marker, không resume/overwrite.

| Chỉ số trên30 requests | R15 | SHORT |
|---|---:|---:|
|Xử lý đủ requests|30/30|30/30|
|Completed final|30/30|0/30|
|Schema-error final|0|30|
|Runtime error / uncertain delivered|0 / 0|0 / 0|
|Raw calls|38 joint|30 diagnosis +0 feedback|
|Raw schema valid / assessed|38/38|0/30|
|Extra retry / sources retried|8 / 5|0 / 0|
|Fallback requests|3|0|
|Raw→final changed requests|5|không có final|
|Input / output tokens|32642 / 2670|33714 / 4836|
|Generation latency tổng, s|39.47|73.43|
|Final feedback characters mean / median|141.10 / 136.5|không xác định|

R15 disclosure-reject events: explicit_repair_disclosure5, level1_identifier_disclosure6, level1_diagnosis_disclosure1; một attempt có thể có nhiều flags. Không có invalid JSON attempts R15. SHORT có cùng một first reject reason30 lần: `invalid diagnosis JSON: Expecting value: line 1 column 1 (char 0)`. Quote/evidence/line gates chưa tới, không báo các subcheck đó là pass. Không lấp `ERR` bằng `[]` hay feedback giả.

Diagnostic **chỉ đọc sau run**, không rescoring:30/30 raw có outer Markdown fence; phần trong fence30/30 decode được bằng json.loads.21 dùng location dạng object dù validator khóa string;9 chỉ qua kiểm tra basic shape (không phải9 accepted).29 raw status defective,1 uncertain. Optional top-level line không được dùng trong29 findings; zero mismatch của field này là không có quan sát, không phải compliance thành công.8 findings có location string,5 line claim không khớp quote start. Chi tiết là ignored `short-wrapper-format-diagnostic.private.json`; không bỏ fence để tạo lại predictions/điểm hoặc gọi model lần hai.

**Lỗi thiết kế cần ghi thẳng:** prompt yêu cầu JSON thuần nhưng base model vẫn dùng fence; R15 parser vốn nhận fence còn SHORT parser không nhận. Ngoài ra prompt chưa nói rõ location phải là string trong khi validator buộc string. Đây là chênh lệch prompt/parser thực tế, không chứng minh base model không biết chẩn đoán. Các thống kê inner JSON là chẩn đoán failure, không là một variant đã được chọn lại. Run chưa cô lập được tác động ngữ nghĩa của việc bỏ witness vì format gate chặn toàn bộ đầu ra.

## Taxonomy, hai reference tách biệt

Missing/error/uncertain không nhận exact-clean. Macro đủ10 nhóm, zero_division0. Annotation style0; source-review style/AR/EC support0 vì4 source có nhãn overlap chưa chốt được loại khỏi bảng source, không phải không có defect mechanism trong tập30.

| Metric | R15 | SHORT |
|---|---:|---:|
|Supplement annotation micro-F1,30 source|0.1702|0.0000|
|Supplement annotation macro-F1|0.0571|0.0000|
|Annotation exact set|6/30|0/30|
|Fresh source-review micro-F1,26 source|0.2000|0.0000|
|Fresh source-review macro-F1|0.0602|0.0000|
|Source-review exact set|6/26|0/26|

SHORT zero F1 là kết quả end-to-end với parse failure, không là score cho các label có trong raw fenced text. Không diễn giải zero F1 thành mọi reasoning đều sai.

| Nhãn | Annotation support | R15 TP/FP/FN | SHORT TP/FP/FN | Source support | R15 TP/FP/FN | SHORT TP/FP/FN |
|---|---:|---|---|---:|---|---|
|Lỗi biên dịch|4|1/2/3|0/0/4|4|1/2/3|0/0/4|
|Lỗi nhập/xuất|1|0/1/1|0/0/1|1|0/0/1|0/0/1|
|Lỗi logic|5|3/13/2|0/0/5|5|3/11/2|0/0/5|
|Lỗi vòng lặp|2|0/0/2|0/0/2|2|0/0/2|0/0/2|
|Lỗi mảng/chuỗi|1|0/0/1|0/0/1|0|0/0/0|0/0/0|
|Lỗi hàm|6|0/3/6|0/0/6|6|0/3/6|0/0/6|
|Lỗi edge case|3|0/0/3|0/0/3|0|0/0/0|0/0/0|
|Lỗi thuật toán|1|0/0/1|0/0/1|1|0/0/1|0/0/1|
|Lỗi hard-code|1|0/0/1|0/0/1|1|0/0/1|0/0/1|
|Lỗi style|0|0/0/0|0/0/0|0|0/0/0|0/0/0|

## Source-based paired review

Review **toàn bộ30 source ×2 arms**, không chọn lại ca theo output và không xem aggregate F1 trước verdict. Mỗi verdict gắn output SHA, source/evidence/rationale. Một reviewer tham gia viết protocol và một reviewer làm fresh source reference; đây là bias cần khai báo. Root đối chiếu lại các case nổi bật bằng source proof. Không coi agent judgment là ground truth của người.

| Final feedback được review | R15 | SHORT |
|---|---:|---:|
|Final thật /30 requests|30|0|
|False technical claim / final có review|25/30|không xác định|
|False-clean assurance / defect final|4/24|không xác định|
|Missing core theo Level / defect final|21/24|không xác định|
|L1 disclosure / L1 final|0/8|không xác định|
|L2 repair leak / L2 final|4/12|không xác định|
|L2 đúng vị trí/cause hữu ích / defect L2 final|0/10|không xác định|
|L3 cause + hướng sửa khả thi / defect L3 final|2/6|không xác định|
|L3 hữu ích và không false claim / defect L3 final|1/6|không xác định|
|Tiếng Việt / final thật|30/30|không xác định|
|D đúng nhưng feedback bỏ/sai ý: quan sát đủ điều kiện|không có stage D riêng|0 quan sát, FB chưa được gọi|

Một L3 R15 có hướng min-heap khả thi nhưng cũng đề xuất FIFO sai, nên không tính strict usefulness. SHORT thiếu output trên24/24 defective source là **delivery failure**, không chuyển thành30 semantic false/pass hoặc điểm usefulness0. Feedback/language/Level flags của mọi missing final đều null. Hai ca L4 không có observation đáp ứng điều kiện D đúng→FB mất; lỗi source bị bỏ sót/generic L4 của R15 được ghi riêng, không gọi là mất finding trong transition chưa quan sát.

Raw được review tách biệt: first raw joint R15 có ít nhất một false technical claim27/30 source; raw-D SHORT29/30. Counts gồm claim về tọa độ sai ngay cả khi cơ chế đúng; không phải29 nguyên nhân đều bịa, không phải atomic-claim precision. Lượng claim và nhiệm vụ joint/diagnosis khác nhau. Bốn raw SHORT nhận ra cơ chế rõ nhưng còn sai tọa độ/schema là MAXARR007, PALIN011, COUNTVOWEL009, MAXARR005. Không gọi đó là accepted diagnosis hoặc completed feedback.

Full source quote, exact output, điều kiện và phản ví dụ/invariant cho tất cả60 source-arm rows ở private **[review a](../../outputs/task3/diagnosis-contract-v1-20261021/review/review-a.private.json)** (15 source đầu) và **[review b](../../outputs/task3/diagnosis-contract-v1-20261021/review/review-b.private.json)** (15 source sau). [Results metadata](TASK3_CONTRACT_V1_RESULTS_20261021.json) có ID/Level/hash/verdict, không chứa source/raw/feedback. Ví dụ có căn cứ dưới đây là **static reasoning, chưa thực thi**:

| Source, bỏ tiền tố SUP1- | L | Source proof và paired finding |
|---|---:|---|
|MAXARR-007|3|Input `3 1 2 9`: chỉ xử lý cặp đầu, trả2 thay9. R15 có hướng sửa hữu ích; SHORT raw thấy tail bị bỏ nhưng ghi line8 thay10, rồi dừng ở format gate. Mất delivery, chưa phải D→FB mất.|
|COUNTEVEN-006|3|b=-3,7: default max-heap trả7 thaymin=-3. R15 gợi ý min-heap đúng nhưng thêm FIFO sai, nên strict fail. SHORT không có final.|
|COUNTVOWEL-005|2|`ae` cần2, kết quả recursion bị bỏ nên source trả1. R15 first raw thấy đúng cơ chế rồi retry bịa thiếu base case; đây là **joint retry degradation**, không transition diagnosis→feedback.|
|COUNTEVEN-008|1|Trong scope filename do caller cung cấp, mở path cố định có thể đọc1 record thay2 của alternate file. R15 false-clean; SHORT raw không sửa được thành feedback giao cho người dùng.|
|COUNT-010|2|Caller n=0, file có2 record: returned array đủ2 nhưng n không được gán nên còn0. R15 phê bình accumulate đúng và bỏ output parameter; SHORT raw không có final.|
|COUNT-005|2|Hai record có b=7,8: P4 gọi minimum nên in7 thay count2. R15 hiểu nhầm Rec* thành list và leak thay container; lỗi call thật bị bỏ.|
|PALIN-011|3|While thiếu dấu đóng `)` trước block; static syntax expectation, không compiler-confirmed. SHORT raw thấy nguyên nhân nhưng tọa độ/schema sai; không feedback.|
|COUNTVOWEL-009|2|`ae`: sau hit index0, nhảy search tới2, đếm1 thay2. SHORT raw nhận ra bỏ ký tự kề nhưng location sai; không accepted output.|
|MAXARR-005|1|Input `2 5 9`: source in index1 thay value9. SHORT raw chỉ ra cơ chế nhưng sai coordinate; fresh taxonomy chưa chốt, source mechanism vẫn rõ.|
|POWER-007|3|Input2,3: lời gọi đảo tham số tính9 thay8. R15 có nhận ra kết quả b^a nhưng cause/repair đầy đủ chưa đạt; SHORT không giao được feedback. Domain gửi model không chứa câu tiết lộ lỗi.|

**Quan sát và kết luận:** contract ngắn không mang lại cải thiện end-to-end trong phiên bản này; format và schema prompt/parser không khớp là bottleneck đầu tiên. Raw vẫn có nguyên nhân bịa và tọa độ sai, nên không có căn cứ chuyển sang public kể cả chỉ nhìn nội dung bên trong fence. Không đo được cải thiện L2/L3 hay finding retention của SHORT vì feedback chưa chạy. Không kết luận việc bỏ witness tự nó làm reasoning tốt/xấu hơn; so sánh này đồng thời đổi joint→two-stage, prompt và validator. Giữ toàn bộ thất bại, dừng tại báo cáo, không sửa sau output để tạo một winner mới.

## Artifacts và verification

[Config](../../configs/task3/diagnosis_contract_v1_20261021.json), [plan](../../docs/superpowers/plans/2026-10-21-task3-diagnosis-contract-v1.md), [freeze](TASK3_CONTRACT_V1_FREEZE_20261021.json), [results](TASK3_CONTRACT_V1_RESULTS_20261021.json), [verification](TASK3_CONTRACT_V1_VERIFICATION_20261021.json). Results SHA-256 `c24a005509f4bc230503c4ee48c524228c945ac74a619946670144f7ed0c94bb`.

Ignored private root: `/workspace/llm-final-project/outputs/task3/diagnosis-contract-v1-20261021/`. Source/selection/reference, frozen safe model inputs và rubric ở `frozen/`; actual messages/raw/config/token/time/decisions/final ở `inference/arm-R15/` và `inference/arm-SHORT/`; R15 legacy attempts giữ exact association với unified capture qua order+hash. Independent audit xác nhận bijection và full source/common context. Không có adapter/optimizer artifact.

`review/reviews-combined-v2.ledger.private.json` và `results-reviewed.private.json` là kết quả review cuối. Bản combined/results đầu được giữ audit nhưng superseded: một flag R15 L4 bị dùng nhầm cho source omission dù không có D→FB transition; đã sửa về null theo rubric gốc, với changelog, không sửa verdict source hoặc prediction. R15 L4 generic failure vẫn ghi riêng. Report-only source/request-binding check được thêm bằng artificial regression, không thay code chạy model.

Commands đã chạy (không hướng dẫn lặp inference):

```bash
.venv-task3/bin/python scripts/task3_contract_v1_prepare.py prepare
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv-task3/bin/python scripts/task3_contract_v1_infer.py --arm R15 --start
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv-task3/bin/python scripts/task3_contract_v1_infer.py --arm SHORT --start
.venv-task3/bin/python scripts/task3_contract_v1_report.py --score \
  --reviews outputs/task3/diagnosis-contract-v1-20261021/review/reviews-combined-v2.ledger.private.json \
  --output outputs/task3/diagnosis-contract-v1-20261021/results-reviewed.private.json
.venv-task3/bin/python -m pytest -q tests/test_task3*.py
.venv-task3/bin/python -m pytest -q
```

Chỉ tái kiểm bằng `.venv-task3/bin/python scripts/task3_contract_v1_prepare.py verify`; prepare/start/report output dùng exclusive names. Không xóa seal/marker để chạy lại. Các test mới dùng artificial TRAIN-only fixtures; broad regression chạy **sau khi cả hai model pass xong**, không dùng test/reference output để đổi phương pháp.

Verification cuối: **892 passed, 2 skipped** cho Task3, gồm56 test mới; global pytest dừng ở2 Task1 collection errors do thiếu sklearn (`test_clm_zeroshot_task1.py`, `test_task1_clm_probe.py`). Không tuyên bố full repo pass, không cài dependency ngoài phạm vi. Independent post-run audit có29 checks, metric tính độc lập khớp,50 tests trước model và6 reporter tests sau đó. Old production/seal/bundle preservation baseline776 file giữ nguyên SHA; old protected154 giữ nguyên. Bundle24 chỉ hash bảo toàn, không đưa vào context/prompt/ref/chọn phương pháp.

Commit chỉ file code/test/config/metadata/report mới, không source/target/raw/private review hoặc predictions. HEAD cuối bàn giao trong chat. Không push.
