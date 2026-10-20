# Task 3 Round 14 — gold-free public candidate, 20/10/2026

Đã xuất **328/328 public records** ở `outputs/task3/round14/public-candidate/predictions.json`, validator offline **VALID**, đúng Level **115/163/50/0**. Phương pháp cuối là **A Direct + bounded schema recovery amendment**, không dùng gold/teacher lúc suy luận. **Candidate chưa nộp**: có 74/328 feedback fallback, trong đó 35/50 Level 3; schema hợp lệ không chứng minh chất lượng. Chất lượng development còn thấp: macro-F1 0,148, micro-F1 0,3273, exact set 2/24; 9/24 feedback dùng câu fallback thừa nhận thiếu căn cứ. Quyết định này được commit **trước public inference**. Schema hợp lệ và có đủ output không chứng minh taxonomy, nguyên nhân hay hướng sửa đúng.

## Phạm vi, hợp đồng và dữ liệu

Tiếp tục tại `/workspace/llm-final-project`, branch `feat/task3-quality-round5`, từ `dbe2d0582f2a35d606c148fcb31eebc4e2fded5c`; working tree ban đầu sạch. Đã đọc docs/task3.md, báo cáo Round 10–13, code/config/test trước khi sửa. Không checkout/clone/worktree, không thay default Round 12/13 hoặc adequacy v4, không sửa dataset/gold. Mọi source sinh viên, prompt, attempts, compiler log, predictions và review chi tiết ở ignored `outputs/task3/round14/`; không stage ZIP/model/cache.

DOCX không có sẵn trong workspace; theo mô tả DOCX do người dùng cung cấp và `sample_dataset/task3_feedback.json` thực tế, Task 3 mẫu có taxonomy ở input. **Public release khác hợp đồng mẫu:** input không có taxonomy, output yêu cầu tự dự đoán cả taxonomy_error và feedback. Không giả định biết code chấm nội bộ. Metadata public cảnh báo vi phạm Level 1/2 bằng code/hướng giải có thể làm mẫu nhận 0; vì vậy chặn disclosure được ưu tiên, đồng thời ghi riêng thiếu adequacy.

Loader metadata kiểm tra đúng **328 ID duy nhất**, khớp requested-level metadata, cùng Level với target_feedback_level: **115/163/50/0** cho L1/L2/L3/L4. ZIP bổ sung có sẵn trong `/workspace`; SHA-256 `7ae1fc242e44aab07d8606fd17efca8b43a42139c65906bf6c4db843d37c2158`; member `t3-feedback/task3_requested_levels.json` SHA-256 `17b8d690f2d86a53a6908da7b95a966194671c9e06117d635da24b1edd70bfa5`. File requested-level ở đường dẫn raw không có trong Docker; dùng trực tiếp member đã xác minh, bản exact bytes ở `outputs/task3/round14/task3_requested_levels.official.json`. Sample submission chỉ dùng để kiểm tra **shape/type**, không đọc nhãn/feedback làm ví dụ hay đáp án.

Output là list `{sample_id, output:{taxonomy_error,feedback}}`; taxonomy list không trùng, chỉ đúng 10 nhóm trong label_space.json, không subtype/Level field. `[]` chỉ do classifier chủ động quyết định; compiler pass không chứng minh clean. Trước selection freeze chỉ kiểm tra metadata public ID/Level/schema, không đọc source public, không public few-shot/pseudo-label/tuning. Không chạy heldout mới hoặc sáu real-val để chọn prompt theo ID.

## Phương pháp và provenance

Code inference/selection chính thức: **`36594f530fcd0b49b91ba58a8fca130596b29687`**. Các mốc trước đó: `9cbba8a` API/runner; `c2f8fdb` disclosure/recovery; `8121b40` audit/resume; `3ccc76b` Unicode/metrics; `aadaaaf` empty-label coherence/oracle provenance. Nhánh phương pháp mới là configs/CLI opt-in, không đổi default pipeline cũ.

Cùng model **Qwen/Qwen2.5-Coder-7B-Instruct**, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, NF4 double quant, compute BF16, phần không quant FP16, toàn bộ CUDA. Không lặp BF16/NF4 sweep. Seed 42, greedy, K=0, context 16.384; classifier 768, direct 1.024, feedback 640, L4 1.536 token; tối đa một retry mỗi stage. HF generation max_time 45 giây là soft stopping limit bên cạnh token cap. Tokenizer Qwen2TokenizerFast, chat template SHA-256 `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`. Manifest lưu resolved model/config/tokenizer/code/prompt hash và actual dtype/device, không chỉ tên config. Model/cache hiện có, không tải checkpoint mới.

- **A Direct:** một yêu cầu Qwen dự đoán taxonomy, rationale nội bộ và feedback; parser kiểm tra official groups, assessment/uncertain và rationale cho từng nhãn dương. Feedback không đạt screen được sinh lại có giới hạn, không mặc nhiên tin raw direct.
- **B Two-stage:** Stage 1 classifier chỉ source/statement/compiler, không requested Level. Stage 2 nhận nhãn đã dự đoán, rationale được giữ là model claim chưa xác minh và finding compiler đã kiểm chứng. Mỗi nhãn dương phải có rationale; quote sai bị loại khỏi evidence, không biến nhãn thành confirmed hay ép về []. Negative-group rationale được giữ riêng. Compiler error xác thực có thể bổ sung nhãn biên dịch bị model bỏ, lưu riêng raw model labels và reconciliation; không suy error từ warning.
- R13 extractor và R12 projection dùng được khi finding có căn cứ và group phù hợp; không đọc `findings-approved-C2.json`, gold taxonomy hay feedback giảng viên trong inference. Không dùng cổng chứng minh coverage toàn bài của R13 làm điều kiện export.

`sanitize` loại gold_taxonomy/gold_feedback, synthetic execution report, teacher text và provenance cũ khỏi inference. Source/statement/problem metadata và **fresh** compiler evidence là input. C++11 syntax-only, timeout 3 giây/call, diagnostic artifact giới hạn 8.000 ký tự; prompt dùng tối đa 4.000 ký tự log cùng severity excerpts, không emit binary hoặc chạy executable sinh viên. Warning được giữ severity riêng; source-bound error mới hỗ trợ compiler finding. Quote tồn tại không là chứng minh cause; ngoài bounded verifier, model rationale vẫn unverified.

Screen dùng disclosure/identifier/claim/CJK/praise/coherence checks hẹp. Nhãn dương có rationale nội bộ; L1 không buộc nói lỗi ra feedback. Empty-label feedback không được đồng thời khẳng định lỗi/đưa repair. L2 chặn imperative/code sửa kể cả inline; L3 cần action gắn identifier/quan hệ hoặc bounded renderer; L4 kiểm tra có artifact giải thích/sửa, **không chứng minh lời giải đúng**. Không quảng cáo adequacy v4 là factual verifier; kết quả 15/16 false/mixed accept của Round 12 vẫn là giới hạn.

## Train-only development và lựa chọn

Chỉ đọc real-train 26 và synthetic-train 495. Tập chọn 24 record, mỗi Level 6; phủ 10 nhóm, có một gold [], nhiều lỗi và nhóm dễ lẫn. Selection ID `803f1023903748ddbe054358aa9a3b84049f42890f4dbf459a7527e06772520f`. Tách family/exam alias và canonical statement, group, source hash và identifier-renamed hash; 24 group/code khác nhau. 371 record reserve thuộc 22 family khác, không dùng để tuning; không đổi tên biến rồi gọi độc lập. Không huấn luyện/few-shot trên phần reserve này.

Development đã được xem và chạy lại trong sửa lỗi, có synthetic templates, một gold-clean duy nhất và family lớn; **không phải benchmark mù hoặc ước lượng tổng quát**. Gold chỉ evaluator sau inference đọc để tính metric và chọn candidate tổng thể; không đưa vào prompt A/B. Hai file train SHA-256 lần lượt `12f2e897c1e374233754bec187de87c903f2142a582e6ad5eb72b81c9f58b1b4` và `27a00fddb3bf17b0ee6af7ebaac14ffdf3deb6bdc98ebc57233d6cf7aac789e4`.

Pilot `dev-*` giữ nguyên trong outputs, không trộn với selection. **Chỉ `selection-A`, `selection-B`, `selection-B-oracle` ở commit 36594f5** là evidence lựa chọn cuối. Cùng 24 record/Level/model/config chung; khác kiến trúc yêu cầu được nêu rõ.

| Metric | A Direct | B Two-stage |
|---|---:|---:|
| Completed | 24/24 | 24/24 |
| Taxonomy macro-F1 | 0,1480 | 0,1375 |
| Taxonomy micro-F1 | 0,3273 | 0,2609 |
| Exact label set | 2/24 | 3/24 |
| False positive gold [] | 0/1 | 0/1 |
| Feedback fallback | 9/24 | 8/24 |
| Classification fallback | 0/24 | 1/24 |
| Final CJK | 0/24 | 0/24 |
| Wall seconds | 141,82 | 186,44 |
| Output tokens, kể cả attempts bị loại | 6.804 | 6.291 |
| Peak allocated GPU | 7.071.596.544 B | 7.071.596.544 B |

Wall/GPU là một lần chạy nhỏ trên RTX5090, không benchmark throughput tổng quát; generation latency cộng dồn 131,06/175,18 giây. Không coi schema completion hay guard pass là factual correctness.

### Precision/recall theo nhóm

Mỗi ô ghi precision / recall; “—” là không có prediction, không phải precision hoàn hảo. Hai phương pháp không dự đoán tám nhóm ngoài biên dịch/logic trong tập này.

| Nhóm chính thức | Support | A P/R | B P/R |
|---|---:|---:|---:|
| Lỗi biên dịch | 3 | 1 / 1 | 1 / 1 |
| Lỗi nhập/xuất | 6 | — / 0 | — / 0 |
| Lỗi logic | 9 | 0,375 / 0,667 | 0,429 / 0,333 |
| Lỗi vòng lặp | 3 | — / 0 | — / 0 |
| Lỗi mảng/chuỗi | 1 | — / 0 | — / 0 |
| Lỗi hàm | 2 | — / 0 | — / 0 |
| Lỗi edge case | 3 | — / 0 | — / 0 |
| Lỗi thuật toán | 5 | — / 0 | — / 0 |
| Lỗi hard-code | 2 | — / 0 | — / 0 |
| Lỗi style | 2 | — / 0 | — / 0 |

Taxonomy agreement không chứng minh source claim đúng; annotation clean cũng có trường hợp cần audit riêng, không sửa gold để khớp model.

### Feedback theo Level và review độc lập

| Level, 6 bài mỗi phương pháp | A fallback | B fallback | Legacy disclosure pass A/B |
|---|---:|---:|---:|
| 1 | 0 | 0 | 6/6, 6/6 |
| 2 | 1 | 3 | 6/6, 6/6 |
| 3 | 5 | 4 | 6/6, 6/6 |
| 4 | 3 | 1 | 6/6, 6/6 |

L1 luôn projection trung tính đúng trần Level, không khen clean chưa xác minh; không phạt vì không lộ technical diagnosis. Fallback L2–4 nói rõ thiếu căn cứ, không bịa vị trí/cause; **không đạt thông tin/hướng sửa được Level yêu cầu**, dù không leakage. Trong metrics, legacy disclosure pass được tách khỏi round14 policy/insufficiency; không đếm 24/24 guard pass như 24 feedback tốt.

Reviewer assistant độc lập đọc source/statement/fresh compiler và raw/final của một mẫu 14 bài train cố định, gồm L1–4, đúng/sai và nhóm dễ lẫn; không human-verified. Nguyên văn code/claim ở ignored `outputs/task3/round14/dev-review/`. Phân loại **final feedback** ở mẫu nhỏ:

| Level | A | B |
|---|---|---|
| L1, 4 | 4 neutral phù hợp Level | 4 neutral phù hợp Level |
| L2, 2 | 2 nontechnical, thiếu diagnosis có ích | 2 diagnosis có phần được hỗ trợ |
| L3, 3 | 1 action hữu ích một phần, 2 fallback | 1 mixed đúng/sai, 2 fallback |
| L4, 5 | 2 repair artifact có căn cứ khi tích hợp, 1 sai, 2 fallback | 2 có căn cứ, 2 sai, 1 mixed |

Đây là verdict theo record, không phải factual precision/recall của mọi atomic claim. Hai repair artifact đúng không được gọi là lời giải cả bài đã chứng minh. Raw reasoning còn bịa biến chưa khởi tạo khi caller đã khởi tạo, nói biến luôn bằng hằng dù code thay đổi, bỏ lỗi hard-code và nhầm overflow. Final guard vẫn nhận vector repair unsafe/dangling; B còn nhận output viết hoa trái contract. B có repair compiler hữu ích pha lẫn thao tác xóa declaration không sửa root cause. Câu thêm return đúng ở B vẫn bị action recognizer từ chối vì cách nói ngoài grammar; ghi false rejection, không tiếp tục khớp lại câu đã xem. Correct unfenced repair artifact từng bị chặn vì thiếu fence đã được sửa bằng fixture trước selection cuối. CJK/praise có audit riêng, final trong mẫu này không có, không suy mọi raw claim đúng.

Supplement review cùng 14 bài: internal/raw main finding coverage core/partial/none A = **2/4/8**, B = **4/5/5**; đây không phải accepted-useful feedback và không phạt L1 thiếu technical disclosure. Trong các record có technical final được nhận, reviewer tìm được ít nhất một false claim/action ở **A 1/4**, **B 3/8**, oracle **2/6**; useful raw repair bị từ chối có căn cứ A/B/oracle = **0/1/1**. Đây là số record trong mẫu tiện lợi, không guard FPR/FRR toàn dataset. Chưa có atomic claim inventory/reference issue set đầy đủ, nên factual precision/recall của mọi claim vẫn **unassessed**. Chi tiết `dev-review/supplementary-review-aggregates.json`.

Chọn A vì macro/micro tốt hơn trên development và ít artifact/hướng sửa gây hại hơn trong mẫu review, **không chọn vì completion** (hai nhánh đều 24/24). B có một số L2 hữu ích hơn và exact-set tốt hơn một mẫu; cỡ mẫu/quá trình lặp chưa cho kết luận phương pháp A tốt tổng quát. Config chọn `configs/task3/r14_selected.yaml` kế thừa direct, không thêm rule theo ID.

## Oracle taxonomy diagnostic

B được chạy paired trên cùng 24 bài với assessment Stage 1 cache giữ nguyên và chỉ thay taxonomy đầu vào Stage 2 bằng gold. Đây là **điều kiện oracle development**, không đường inference public hoặc cách tính taxonomy F1. Oracle không có teacher feedback hay approved finding; các model claim trong assessment vẫn có thể sai. CLI kiểm tra cùng selection/config/provenance; không classifier gọi lại ở oracle.

Kiểm tra paired: assessment giữ nguyên **24/24**, oracle chỉ có feedback calls; 17/17 initial feedback prompt có thể đối chiếu chỉ khác taxonomy_error. Hoàn tất 24/24, fallback L1/L2/L3/L4 = **0/2/5/2**, tổng 9/24 so với predicted 8/24; CJK 0/24. Wall 110,94 giây, 3.390 output tokens. Đây không là so throughput tương đương vì không chạy lại classifier.

Review cùng 14 bài: predicted B có supported/mixed/wrong/nontechnical/fallback = **4/2/2/4/2**; oracle = **4/1/1/4/4**; A = **3/0/1/6/4**. Supported là thông tin/repair có căn cứ trong phạm vi, chưa chứng minh full solution. Oracle tránh được một unsafe artifact nhưng chuyển thêm hai ca sang fallback; vẫn giữ output viết hoa trái đề và false rejection với return hữu ích. **Gold taxonomy không đủ sửa generator/guard**; gap không chỉ classifier. Không trộn điểm oracle với predicted hoặc coi gold taxonomy là finding có căn cứ. Control và verdict ở `dev-review/selection-oracle-control.json` và `final-paired-summary.json`.

Không có compiler reconciliation thực sự trong A/B 24 bài (model đã dự đoán nhãn compile ở ba ca fresh error); đây là capability có artificial tests, không là lợi ích quan sát được để cộng vào chất lượng development.

## Completion, unknown và Level 4

Parser failure/unknown giữ trong audit, không tự thành []. Primary classifier có tối đa hai attempts, rồi fallback được prompt độc lập: B thử direct, sau đó full 10 boolean label decisions; A thử full boolean classifier. Nếu vẫn hỏng, record là unresolved, lưu lỗi và tiếp tục record khác, không ghi predictions.json đủ giả. Model quyết định [] vẫn ghi `model_predicted_clean_unverified`; rejected quote/rationale, uncertain, confidence/assessment và raw model labels đều giữ riêng.

Feedback không qua bounded retries nhận **epistemic feedback fallback** đúng trần disclosure, có cờ `insufficient_for_requested_level`. Đây là thừa nhận chưa nêu diagnosis/repair, không phải placeholder được tính chất lượng, không đổi model taxonomy thành []. Mục tiêu đủ output được tách khỏi useful-feedback completion. Journal append-only fsync, resume theo ID và binding code/config/tokenizer/source/statement/problem/grading-policy/Level/compiler; không mix run hoặc mất 327 output vì một ID lỗi. Corrupt tail giữ bản raw; U+2028/0085 không phá JSONL. Tokenizer kiểm tra initial/retry budget và runtime payload, không âm thầm cắt source.

L4 đã được thử 6 development record và artificial fixtures, có solution/function artifact rộng hơn certificate return-constant của R13. Guard chỉ kiểm tra artifact/Level và một số claim, không chứng minh solution correct/complete; source review tìm cả sửa đúng và unsafe. Public có 0 L4 không là lý do gọi phương pháp đầy đủ Task 3.

## Fine-tuning và Task 2

Không có checkpoint/predictions Task 2 khả dụng; không làm dependency. Yêu cầu môn học so prompting với một open-weight fine-tuned đã có evidence **Task 3 QLoRA lịch sử**, không cần một vòng mới chỉ để đủ mục này: FINAL_TASK3_REPORT.md ghi E1/E2 Qwen7B 300 steps, 40.370.176 trainable parameters, update/reload verification, runtime/loss/VRAM và so zero/few-shot/QLoRA cùng phạm vi. Follow-up ghi best checkpoint ở step20/60, khác last300; không giả vờ best cũng train đủ300. Các so sánh cũ dùng sáu real-val đã xem lặp, không phải benchmark độc lập.

Hiện adapter/checkpoint lịch sử không còn trên disk (chỉ tài liệu/hash), nên **không freshly verify weights hoặc dùng nó làm candidate Round14**. Cache base Qwen/`.no_exist/adapter_config.json` không là adapter. Báo cáo lịch sử đáp ứng bằng chứng đã triển khai so sánh prompting/fine-tuned; Round14 hiện là prompting baseline, không quảng cáo có model fine-tuned mới hoặc checkpoint Task2.

## Kiểm thử và public execution

Trước public gốc: **506 passed, 4 skipped**; sau amendment đã review: **527 passed, 4 skipped** trong toàn bộ `tests/test_task3_*.py`, 6,79 giây; gồm C++ sandbox module. Test mới cho public loader/ID/Level/schema, gold/teacher sanitization, prompt budget, taxonomy–feedback coherence, warning/error, classifier repair, retry/resume, Unicode journal và output validator. Red/green logs ở outputs. Không gọi full-repository pass: Task1 thiếu sklearn trong môi trường, không cài dependency ngoài scope để che lỗi.

Tại commit quyết định **fc7a05e8ed63f6ecdc64dd91fe61ac9dcf1d6340**, public chưa chạy. Freeze gốc được ghi lúc **2026-10-20 12:19:26 UTC**, SHA-256 **959768c59d5b3cbbe489991c7d4a62f3d2cca60e644327412a5f20d0267d5372** tại `outputs/task3/round14/selection-freeze.json`. Code/config khớp freeze, working tree sạch trong lượt gốc.

### Amendment sau freeze: khôi phục lỗi schema, không đổi prompt

Lượt public gốc xử lý đủ 328 input nhưng chỉ hoàn tất **319/328**; cả **9 unresolved đều Level 2**. Không có final predictions.json được ghi ở trạng thái thiếu. Mỗi ca đã dùng hai direct attempts và hai classifier boolean attempts; validation từ chối nhãn compiler không có căn cứ, rồi thiếu rationale riêng cho nhãn dương ở fallback. Chỉ metadata lỗi/stage/token được đọc để điều tra; không đọc source/nhận định từng public bài để chọn phương pháp hoặc gán nhãn.

Lượt gốc: wall **1.719,02 giây**, 556 model attempts, 82.772 output tokens, generation latency cộng dồn 1.675,05 giây. Có **66/319 feedback fallback** (L2 31/154, L3 35/50); 10 classification fallbacks đã thành công. 326 source hash khác nhau được compile syntax-only; tính theo record, status compiled/compile_error là **254/74**. Có hai source trùng, nên count theo unique compiler calls là 252/74. Không chạy student executable.

**Đây là thay đổi protocol sau freeze**, không gọi kết quả sau sửa là một lượt nguyên vẹn của phương pháp đã đóng băng ban đầu. Bổ sung đường recovery explicit chỉ cho lỗi classification đã exhaust schema validation: dùng **prompt classify của B đã được đánh giá trước public**, tối đa hai attempts, rồi đường feedback cũ. Không sửa prompt, model, revision, precision, config, taxonomy rule hoặc claim/disclosure guard; không bỏ yêu cầu rationale, không biến failure thành []. Nếu classifier này vẫn hỏng, record vẫn unresolved.

Migration tái tính đúng identity gốc với original implementation hashes và mọi input; snapshot nguyên bytes progress/run/journal/metrics/traces/partial outputs vào `pre-schema-recovery/`. Sidecar `schema-recovery.json` lưu old/new identity, hashes và eligible IDs private. Identity mới dùng **hash implementation mới**, không giả gắn code mới với hash cũ. 319 completed output/trace mappings phải giữ nguyên canonical hash, journal gốc phải là exact byte prefix. Prepared→migrated checkpoint an toàn khi gián đoạn; số attempts rescue đã dùng được đếm từ journal qua mọi resume, không cấp lại budget. Không chạy lại các direct/boolean routes đã hết lượt.

Fixture nhân tạo kiểm tra completed preservation, đúng eligibility, mismatch source/config/identity, sidecar/snapshot/journal mutation, migration idempotence, gián đoạn, exhausted rescue và runtime resume chỉ dùng lượt còn lại. Replay **49 attempts A và 56 attempts B train**, không gọi model: prompt khớp nguyên văn và **24/24 output mỗi nhánh không đổi** sau sửa controller. Evidence `schema-amendment-train-replay.json`; không lấy public code/ID/output làm fixture hoặc quy tắc.

Amendment code/test/report được commit **5788da1d279f6281a0d5b3d144a020914d774ffb** trước recovery. Amended freeze tại `outputs/task3/round14/schema-recovery-freeze.json`, SHA-256 **cd5d943665701a860e77efb5e4a4768b68b65979fbd4b376b61d26292d9c0b30**, tạo lúc **2026-10-20 12:54:20 UTC**. Resolved model/config hash vẫn **dafc3e18734d92c1ffb343296ee25b2f15bb4521dec0819aa2c3297d351b2dd2**. Run sau sửa ghi đúng commit mới, implementation hashes mới và `worktree_dirty=false`.

Một cờ provenance `public_source_loaded_before_freeze=false` trong amended freeze bị kế thừa từ original: đúng cho **freeze gốc**, sai nếu hiểu là freeze amendment. Bytes freeze được giữ nguyên; `schema-recovery-freeze-provenance-correction.json` ghi rõ giá trị cho amendment phải là true. Cờ này không tham gia execution guard, không đổi code/config/prompt/outputs, không làm chạy lại model. Original freeze vẫn ghi đúng rằng public source chưa được đọc trước chọn phương pháp; amendment chỉ dùng metadata lỗi cấu trúc. Không che khác biệt thứ tự này.

### Kết quả cuối và artifact

Recovery chỉ gọi model cho 9 ID eligible, dùng 18 classifier attempts và 17 feedback attempts; hoàn tất **9/9**. **319 output/trace entries cũ giữ nguyên**, original attempt journal vẫn là exact byte prefix. Final taxonomy là quyết định classifier (hoặc compiler evidence trong phạm vi đã kiểm chứng), không có manual labeling hoặc exception-to-[] conversion. Các kiểm tra tự động không đọc nội dung từng bài để điều chỉnh phương pháp.

| Chiều audit public | Kết quả |
|---|---:|
| ID duy nhất / đúng thứ tự metadata / output không rỗng | 328/328 |
| Requested Level 1/2/3/4 | 115 / 163 / 50 / 0 |
| Feedback fallback L1/L2/L3/L4 | 0 / 39 / 35 / 0 |
| Classification fallback, kể cả recovery | 19/328 |
| Uncertain trong audit | 173/328 |
| Explicit model [] chưa xác minh clean | 112/328 |
| L1 neutral projection | 115 |
| L2 verified structured projection | 69 |
| Qwen best-effort feedback L2/L3 | 55 / 15 |
| Final CJK | 0/328 |
| Raw attempts có CJK ở bất cứ trường nào | 25/591 |
| Total attempts / bị schema hoặc screen từ chối | 591 / 241 |
| Unknown token counts / journal tail bị thiếu | 0 / không |

Raw CJK có thể ở rationale/quote/code, không tự coi 25 lượt là 25 Chinese-prose violations. Scan tự động không thấy private-key/GitHub-token/HF-token patterns trong feedback; đây không phải chứng nhận loại mọi dữ liệu nhạy cảm. Không stage public output/source hoặc raw attempts.

Automated disclosure screen không phát hiện leakage ở output cuối, nhưng **39 L2 fallback thiếu vị trí/cause và 35 L3 fallback thiếu action hữu ích**. Cả các câu Qwen không gắn fallback cũng có thể thiếu diagnosis, như đã thấy trên development. Vì vậy 254/328 “không fallback” **không là useful-feedback completion**; 115 câu L1 trung tính chỉ được đánh giá trong đúng trần Level. 69 structured projections chỉ giữ compiler finding có căn cứ tại vị trí nguồn, không là 69 proof root-cause/whole-program correctness. Public semantic factual accuracy, taxonomy F1 và đầy đủ lỗi vẫn **unassessed**; không có public gold và không đoán điểm leaderboard.

Aggregate taxonomy model: logic 141, biên dịch 74, nhập/xuất 4; bảy nhóm còn lại không được dự đoán. Đây là distribution output, **không phải nhãn thật hoặc precision**. Không dùng phân bố này để sửa prompt/config sau public. Không thêm nhãn nhằm làm đủ 10 nhóm.

Hai invocation public: original 1.719,02 giây + recovery 145,31 giây = **1.864,33 giây (~31,07 phút)**, chưa gồm thời gian viết/test amendment. Cộng journal: **86.384 output tokens**, **1.408.941 input tokens**, generation latency **1.785,32 giây**; peak allocated GPU cả hai 7.071.596.544 B, peak reserved 7.144.996.864 B. Invocation thứ hai kiểm tra lại 326 source hash syntax-only, nhưng không sinh lại 319 completed records. Không có student-program execution. Đây không là một benchmark tốc độ hoặc so precision mới.

Artifact cuối đều ignored dưới `outputs/task3/round14/`:

- **`public-candidate/predictions.json`** — file để người dùng lấy và xem xét. SHA-256 **`75f9acd13c183cf40154548eb3d530f14af6959c20b34b413d778eca756ba0d4`**.
- `public-candidate/run.json`, `metrics.json`, `audit-summary.json`, `public-aggregate.json`: manifest cuối, số đếm, audit từng ID, epistemic/fallback status. `traces.json`, `attempts.jsonl`, `progress.json` giữ raw riêng tư.
- `public-candidate/validation-report.json`, `validator-cli.log`: **VALID 328/328**, đúng thứ tự ID và schema; repo offline validator, không giả định đó là code chấm nội bộ leaderboard.
- `public-candidate/schema-recovery.json`, `pre-schema-recovery/`, `original-input-evidence/`: authenticated eligibility, original bytes/hash/output invariance, compiler/budget trước recovery. `public-candidate.log` và `public-schema-recovery.log` giữ hai invocation.
- `selection-freeze.json`, `schema-recovery-freeze.json`, correction provenance riêng; `selection-A/B/B-oracle/`, `dev-review/`, `schema-amendment-train-replay.json`, test red/green logs: evidence lựa chọn và amendment. Không thay evidence gốc bằng bản đã sửa.

## Tái hiện và tiếp tục

Các lệnh development bên dưới dùng thư mục output mới; model/cache hiện có phải được giữ. Không đọc public để tạo ví dụ. Oracle diagnostic chỉ được phép phase development. Public resume dùng đúng hai freeze và checkpoint hiện có; đổi input/config/tokenizer/implementation sẽ bị từ chối. Khi 328 đã hoàn tất, resume không gọi lại model cho completed IDs.

```bash
cd /workspace/llm-final-project
.venv-task3/bin/python -m pytest -q tests/test_task3_*.py
.venv-task3/bin/python scripts/task3_round14.py \
  --config configs/task3/r14_direct.yaml --phase development \
  --output-dir outputs/task3/round14/reproduce-dev-A
.venv-task3/bin/python scripts/task3_round14.py \
  --config configs/task3/r14_two_stage.yaml --phase development \
  --output-dir outputs/task3/round14/reproduce-dev-B
.venv-task3/bin/python scripts/task3_round14.py \
  --config configs/task3/r14_two_stage.yaml --phase development \
  --oracle-from outputs/task3/round14/reproduce-dev-B/traces.json \
  --output-dir outputs/task3/round14/reproduce-dev-B-oracle
# Exact authenticated public resume after the disclosed amendment:
.venv-task3/bin/python scripts/task3_round14.py \
  --config configs/task3/r14_selected.yaml --phase public \
  --freeze outputs/task3/round14/schema-recovery-freeze.json \
  --recover-from-freeze outputs/task3/round14/selection-freeze.json \
  --output-dir outputs/task3/round14/public-candidate
.venv-task3/bin/python scripts/validate_task3_submission.py \
  --predictions outputs/task3/round14/public-candidate/predictions.json \
  --requested-levels outputs/task3/round14/task3_requested_levels.official.json
.venv-task3/bin/python outputs/task3/round14/summarize_public.py
```

Lệnh resume trên cần checkpoint/raw artifacts, không là lệnh tự tái tạo original freeze từ code mới. Original pass command dùng r14_selected.yaml + selection-freeze.json ở commit fc7a05e; freeze guard chủ động từ chối chạy old freeze với implementation sau amendment. Không checkout để chạy lại trong nhiệm vụ này. Các script replay/aggregate cuối là công cụ nội bộ ignored; core controller/recovery/validator/test đã commit. Không chạy thêm heldout; các đánh giá lịch sử không được biến thành benchmark mới.

## Kết luận từng tầng

| Tầng | Kết quả | Blocker chất lượng còn lại |
|---|---|---|
| Extractor / evidence | Gold-free source/statement/fresh compiler; severity tách warning; bounded finding dùng được | Ngoài compiler, Qwen cause vẫn có false claim/missed defect; quote không entail cause |
| Taxonomy | Tự dự đoán đúng schema 10 nhóm cho phép, không phụ thuộc Task2 | Development F1 thấp, bỏ nhiều nhóm; output public chỉ có 3 nhóm được dự đoán, accuracy chưa biết |
| Renderer | Giữ R12 làm đối chứng oracle riêng; predicted verified findings có projection không gold | Closed projection chỉ bảo đảm conditional preservation; freeform guard còn FA/FR |
| Level | L1 neutral; chặn L2 repair; L3 relation check; đã thử L4 ngoài certificate nhỏ | L2 generic có thể qua; L3 thiếu useful action nhiều; L4 có unsafe/wrong artifact trong review |
| Completion | 328 schema-valid sau original319 + explicit9-ID recovery; không lấp unknown bằng [] | 74 feedback fallback, không useful; đây là amended protocol, không untouched one-pass result |
| Evaluation | Train-only A/B/oracle, independent assistant review, full527 Task3 tests | Mẫu development nhỏ/đã lặp, atomic factual P/R và public semantic quality chưa đánh giá; không claim chất lượng cao |

Không push, PR hoặc nộp leaderboard. Candidate được giao để người dùng xem xét; phần cần cải thiện chính là taxonomy/semantic finding và feedback hữu ích, không phải làm validator pass thêm lần nữa.
