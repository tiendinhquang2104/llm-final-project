# Task 3 Round 15 — prompt ngắn, raw Qwen và hậu xử lý, 20/10/2026

Chọn **zero-shot ngắn** trong hai prompt mới để tạo candidate public riêng; **không kết luận nó tốt hơn Round 14**. Development mới cho thấy model vẫn đọc sai code và bỏ lỗi: zero-shot có strict useful Level 2 **1/7** ca có lỗi được source-review xác nhận, Level 3 **0/7**; few-shot tương ứng **0/7** và **1/7**. Fallback ít không đồng nghĩa phản hồi có ích. Candidate mới đã xuất **328/328**, validator offline **VALID**; fallback **9/328**, nhưng audit cho thấy Level 3 vẫn chưa có hướng sửa đạt tiêu chí nghiêm ngặt trong mẫu kiểm tra. Candidate Round 14 giữ nguyên SHA-256 `75f9acd13c183cf40154548eb3d530f14af6959c20b34b413d778eca756ba0d4`.

## Phạm vi và hai prompt

Tiếp tục cùng repository/branch từ `f950fdb4e1790432b0cbe3d230a01b29438bbac2`, working tree ban đầu sạch. Không checkout/worktree, fine-tune, Task 2, mở rộng extractor/certificate, sửa gold, push hoặc leaderboard. Round 14 code/config/candidate không đổi. Nhánh mới opt-in: `src/task3/round15*.py`, `scripts/task3_round15.py`, configs `r15_zero_shot.yaml`, `r15_few_shot.yaml`; raw/examples/review/predictions chỉ trong ignored `outputs/task3/round15/`.

Hai cấu hình dùng cùng system prompt ngắn: đề/prototype/grading policy được cung cấp, **toàn bộ code**, compiler status/diagnostic C++11 nếu có, requested Level; yêu cầu đúng hai khóa taxonomy_error và feedback tiếng Việt. Danh sách đúng 10 nhóm, cho phép [] khi không thấy lỗi; không ép nhãn dương. Nêu rõ error khác warning, compiler pass không chứng minh đúng, technical claim phải bám code/đề. Không đòi rationale/assessment riêng như Round 14. Không dùng taxonomy hoặc feedback đúng của query trong inference.

Level 1 chỉ gợi ý nhẹ, không vị trí/identifier/cause/repair; Level 2 vị trí+cause, không hướng sửa/code sửa; Level 3 cần hướng sửa gắn lỗi nhưng không full solution; Level 4 cho phép lời giải mẫu. Đây là yêu cầu **trong prompt**; hậu xử lý chỉ JSON/schema và disclosure rõ L1/L2. L3/L4 không có rejection nội dung: thiếu keyword, code fence, action grammar, factual/CJK/praise/coherence không làm mất response. Các cue chỉ để audit; full solution L3 vẫn là lỗi model phải review, không được tính tốt vì guard cho qua.

Few-shot chỉ thêm **2 ví dụ train mỗi Level**, cùng system và query như zero-shot. Bank 8 nguồn train khác nhau: mỗi Level một positive và một [] thận trọng; lỗi đa dạng gồm main chưa xử lý, missing semicolon, Euclid chia thay modulo, bỏ bản ghi đầu khi tính max. Không dùng claim yếu về dấu cách đầu ra làm mẫu lỗi. Teacher feedback không được sao chép; reference do assistant source-review viết, không human-verified. Các trường hợp thiếu ràng buộc chỉ nói chưa thấy lỗi rõ, không chứng nhận clean. Relevel ví dụ được ghi rõ trong bank, không sửa dataset/gold. Full source/statement được hash-bound về train; bank SHA-256 `731cc2b4caa43e4db83011a2bb73fb8919deb7138665e48964457e9962ee7938`.

Ví dụ serialized 1.023–1.789 ký tự; ưu tiên đủ source query, chỉ bỏ **nguyên ví dụ** nếu budget không đủ, không cắt query. Tokenizer preflight worst retry trên 24 bài có max khoảng 1.970 input tokens trước fresh diagnostic, không cần bỏ ví dụ. Artifact budget thực tế ghi số token và K từng attempt.

Cùng Qwen/Qwen2.5-Coder-7B-Instruct revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, NF4 double quant compute BF16/unquantized FP16, CUDA, seed42 greedy, context16.384, cap1.024/L4 1.536, soft HF max_time45 giây. Không đổi precision, không tải checkpoint mới. Compiler C++11 syntax-only timeout3 giây, diagnostic tối đa8.000 ký tự; không chạy executable sinh viên.

## Tập train-only mới và review

24 bài **synthetic-train** lấy từ R14 reserve chưa dùng để chọn prompt Round 14: Level **4/8/8/4**, 3 gold[] ở L1, đủ10 nhóm, 12 family×2. Không dùng sáu real-val hoặc public. Pool ví dụ130 record thuộc10 family khác; cách ly family/group/exact code hash/identifier-renamed hash khỏi toàn bộ239 record trong12 family development, không chỉ khỏi24 được chọn. Hai collision candidate bị loại. Selection ID `8201d48b8d2b211b0ba2a4d8cba4834c52feee0e4a2b4eba7765c4796aab2bba`.

Đã kiểm tra10 manifest lựa chọn R14: không trùng ID với pool reserve. R13 extractor từng đọc toàn train và corpus có synthetic templates; **không gọi đây là dữ liệu chưa từng thấy hoặc benchmark mù**. Metadata dùng gold train để phân tầng evaluation; query gold chỉ evaluator sau inference đọc. Nhãn noisy không là proof semantic: có bài thuật toán đúng chỉ còn TODO/style, dấu cách có impact chưa xác định do thiếu exact-output contract, arr[n] vẫn trong allocation n+1 nhưng đọc ô chưa khởi tạo. Không sửa annotation để khớp model.

Ba matched run trên cùng24 IDs/Level, code commit **044daf0e93dbdf63e994a8a5c58e7311626deb97**, working tree sạch: `dev-zero`, `dev-few`, `dev-round14-control`. Control gọi nguyên prompt/controller R14 với cùng model/decoding; không sinh lại candidate public R14. Wrapper lưu raw trước legacy parser/guard. Prompt hash và raw return được giữ nguyên; raw đầu tiên và mọi retry đều có audit.

Hai reviewer assistant chia L1/L2 và L3/L4, đóng source/spec expectations **trước khi đọc outputs**, sau đó review đủ24 bài×3 conditions×raw/final. Không teacher feedback/public/real-val; không human verification. Per-ID evidence, atomic material claims supported/contradicted/unassessed, coverage, Level/useful-action và attribution nằm trong `review/`. Counts không là exhaustive factual precision/recall toàn dataset.

| Metric development | Zero | Few | R14 control |
|---|---:|---:|---:|
| Output complete | 24/24 | 24/24 | 24/24 |
| Taxonomy micro-F1 | 0,1304 | 0,0952 | 0,0870 |
| Macro-F1 | 0,1667 | 0,2000 | 0,1500 |
| Exact set | 6/24 | 2/24 | 5/24 |
| Feedback fallback | 0 | 2 | 6 |
| Actual model output tokens | 2.121 | 1.556 | 5.824 |
| Wall seconds | 39,67 | 31,55 | 81,98 |

Không dùng F1/fallback làm tiêu chí duy nhất; taxonomy agreement so noisy annotation tách khỏi source-supported claim. Trên mỗi nhóm, chi tiết TP/FP/FN/P/R nằm trong metrics.json của từng run; không suy semantic từ trùng nhãn. Raw-schema của nhánh mới dùng đúng parser hai khóa như final; control ghi rõ projection từ schema joint R14, không đánh tráo hai contract.

| Chất lượng source-review final | Zero | Few | R14 control |
|---|---:|---:|---:|
| L1 nhẹ, không unexplained praise | 1/4 | 4/4 | 4/4 |
| L2 useful đúng vị trí/cause, actual-error denominator | 1/7 | 0/7 | 2/7 |
| L2 nếu tính observation dấu cách, impact chưa xác định | 2/8 | 0/8 | 2/8 |
| L3 strict correct cause+feasible useful action | 0/7 | 1/7 | 1/7 |
| L3 trên tất cả8 record | 0/8 | 1/8 | 1/8 |
| L3 raw strict trước xử lý | 0/7 | 1/7 | 2/7 |

L2 có8 record nhưng một whitespace case chưa xác minh là lỗi theo đề; L3 có8 nhưng một bài không có actionable semantic defect đã xác nhận. Không phạt câu thận trọng đúng ở bài ấy vì thiếu repair. Boundary sensitivity: coi task-restatement là chẩn đoán thay vì hướng sửa thêm một L2 success cho zero/few; bảng chính giữ giới hạn Level chặt. Người review vẫn tìm hai direction leaks ở mỗi nhánh final L2 mà screen không nhận ra; screen pass không là semantic Level pass.

Raw material claim inventory trên24 bài (supported/contradicted/unassessed): **zero20/16/8**, **few18/17/6**, **R14 control16/9/7**. Sau xử lý control có ít claim hơn cả đúng lẫn sai, không tự coi đó là chất lượng cao hơn. ReviewL3 thấy6/8 bài ở cảzero/few có materially false claim; việc newguard giữ nguyên chúng là evidence lỗi model, không là tăng usefulness.

L4 được review riêng: zero không có standalone solution có căn cứ trong4 bài; few có một patch DISTINCT đúng khi tích hợp nhưng không cung cấp full standalone solution; control có standalone DISTINCT được source-review hỗ trợ, một chương trình FIB syntax-pass nhưng validity toàn miền còn unassessed, và một patch SUMEVEN đúng khi tích hợp. Bốn proposed solution/patch syntax-only checks pass, không thực thi; compiler pass không là correctness.

## Model hay hậu xử lý?

Mỗi bài có verdict riêng trong review JSON; không stage mã sinh viên hoặc raw claim. Những cơ chế chính:

- **Model đọc sai code/đề:** đảo chiều in nhị phân vốn đúng thay vì sửa index; gọi ô sentinel trong allocation là out-of-bounds; bỏ lỗi n=1; coi helper đúng là nguyên nhân sai; đưa advice ghép record trước trái yêu cầu. L3 raw đã sai và được giữ nguyên sau xử lý, nên không đổ lỗi guard.
- **Few-shot contamination:** mang yêu cầu min-b từ ví dụ sang bài max-d; quy kết vector không đáp ứng dynamic-array dù source trả đúng. Một repair L3 hữu ích và một patch L4 đúng không đủ chứng minh few-shot cải thiện tổng thể.
- **R14 postprocessing làm mất nội dung đúng:** raw SUMPAIR có hướng sửa local index đúng; indentation của quote không exact bị đánh dấu rejected_support, **không phải hard parse failure**. Action recognizer báo level3_action_not_source_bound; retries vẫn nêu đúng repair rồi final thành câu chung. PROD L4 raw có hướng filename-parameter hữu ích nhưng bị missing-level4-solution; không tự gọi raw ấy là full solution. MINA L2 có false imperative detection do chữ “nên không tính tổng b”; final vẫn có diagnosis hữu ích. Có raw diagnosis observation bị mất nhưng raw cũng chứa repair leak thật, cần tách hai vấn đề.
- **Postprocess mới:** giữ mọi L3/L4 content kể cả generic hoặc sai. Same-text counterfactual trên16 raw L3 mới: R14 screen từ chối8/8 zero và7/8 few, screen mới0/8 cả hai; **không dùng chênh lệch acceptance này làm factual score**.

Phát hiện và sửa một false rejection Level1 mới: “các hàm cần thiết/phù hợp/tương ứng” là noun phrase, không phải identifier. Ba fixture nhân tạo tái hiện trước sửa; chỉ mask các noun phrase ngôn ngữ chung khi nhận diện identifier, không rule theo ID/code. Raw vẫn có subjective praise chưa xác minh, nên không gọi nó hoàn toàn tốt. Sau sửa replay **nguyên raw Qwen đã lưu**, không gọi model: zero dùng27/28 captured answers, chỉ đổi1 final; few dùng30/30, không đổi final. Hai pilot model runs giữ nguyên; final postfix replay ở `dev-zero-postfix-replay`, `dev-few-postfix-replay`. L2/L3 usefulness counts không đổi. Không khớp lại action grammar theo các câu đã thấy.

## Lựa chọn và đóng băng

Chọn **zero-shot** giữa hai prompt mới vì ít example contamination, taxonomy micro/exact tốt hơn và có actual-error Level2 diagnosis hữu ích hơn few. Few có một strict L3 success nhưng không bù được các wrong-cause/source-transfer claims. **Không chọn vì zero fallback=0**, không kết luận tốt hơn R14 control (control có L2/L3 strict useful nhiều hơn trên tập này). Config `r15_selected.yaml` kế thừa zero; không tiếp tục tìm prompt trên public.

Pre-public freeze đã ghi resolved config, code hashes sau noun-phrase fix, bank hash, selection/review/replay hashes và commit **f6a17b13a3954755dd55809d9082784e36391546**. Freeze tạo lúc **2026-10-20 13:54:44 UTC**, SHA-256 **031c546bb5a83236725a158176585183c78799f7a8c4adc502d197cb3c858795**, file `outputs/task3/round15/selected-prompt-freeze.json`. Mẫu audit usefulness public được định trước bằng metadata/ID hash: L1=6, L2=10, L3=10, không đọc source/output để chọn mẫu. Source/feedback public chỉ review **sau inference đã đóng băng** để báo chất lượng, không sửa prompt/chọn lại model. Tỷ lệ useful sẽ ghi rõ mẫu/denominator, không gán cho toàn328 khi chưa review toàn bộ.

Full Task3 suite sau fix: **622 passed, 4 skipped, 6,93 giây**, gồm C++ sandbox. Log `outputs/task3/round15/tests-task3-pre-public.log`; không sửa implementation sau freeze. Test bao phủ full-source/tokenizer budget, train-example binding/isolation, raw capture trước guard, schema/Level, per-ID retry/resume và validator. Full repository đã thử, collect fail `test_clm_zeroshot_task1.py`, `test_task1_clm_probe.py` do thiếu sklearn; không cài hoặc sửa Task1 ngoài scope, không gọi Task3 pass là full-repo pass. Raw/model cache/predictions không stage, không push/nộp leaderboard.


## Public candidate mới sau freeze

Chạy **một invocation** bằng zero-shot đã chọn, code/config đúng freeze, manifest `worktree_dirty=false`; hoàn tất **328/328**, không unresolved, không amendment hoặc chạy lại để chọn prompt. Public source không được dùng làm ví dụ, training hay chọn prompt; chỉ inference sau freeze và audit đánh giá sau đó. Không sửa output thủ công, không chuyển parse failure thành [], không gọi thêm model sau khi hoàn tất. Model có thể chủ động dự đoán [] nhưng đó là nhận định chưa xác minh clean.

Repo offline validator xác nhận schema, đúng328 ID duy nhất và thứ tự metadata, đúng10 nhóm cho phép, feedback không rỗng; requested Level **115/163/50/0**. Không suy điểm leaderboard hoặc semantic correctness từ validator. Metadata chính thức dùng ZIP bổ sung đã xác minh SHA-256 `7ae1fc242e44aab07d8606fd17efca8b43a42139c65906bf6c4db843d37c2158`; requested member SHA-256 `17b8d690f2d86a53a6908da7b95a966194671c9e06117d635da24b1edd70bfa5`. Sample submission chỉ shape, không làm reference feedback. Khác biệt input sample có taxonomy/public phải tự dự đoán vẫn như Round14; Round15 không giả định được cấp taxonomy.

| Public aggregate | Level 1 | Level 2 | Level 3 | Tổng |
|---|---:|---:|---:|---:|
| Records | 115 | 163 | 50 | 328 |
| Feedback fallback | 3 | 6 | 0 | **9 (2,74%)** |
| First raw khác final, gồm retry/fallback | 4 | 20 | 0 | 24 |
| Model tự dự đoán [] chưa xác minh clean | 112 | 7 | 1 | 120 |
| Final có CJK | 0 | 0 | 5 | 5 |

Fallback chỉ áp dụng khi có nhãn schema-valid nhưng disclosure L1/L2 vẫn không đạt sau bounded retries; không tạo [] bằng exception. L3/L4 schema-valid được giữ nguyên, nên **0 fallback L3 không chứng minh50 action hữu ích**. CJK giữ nguyên đúng thiết kế chỉ-schema/disclosure của thí nghiệm, vẫn là lỗi tiếng Việt cần báo. Final label distribution là logic86, biên dịch86, nhập/xuất32, hàm4, sáu nhóm khác0; chỉ là phân bố model, không nhãn thật hay precision. Không dùng phân bố này để thay prompt/config.

Tổng **361 attempts**, raw response được fsync vào `attempts.jsonl` **trước parser/guard**, decisions riêng; không mất journal tail/token count. Input **647.919 tokens**, output **23.419 tokens**, generation latency330,98 giây, wall **365,34 giây (~6,09 phút)**; peak GPU allocated7.071.596.544B, reserved7.212.105.728B. Đây là một lần chạy trên RTX5090, không benchmark tốc độ/chất lượng tổng quát. Compiler326 unique source syntax-only:252 compiled,74 compile_error; timeout3 giây, không chạy chương trình sinh viên. Compiler pass không chứng minh code đúng.

Candidate cũ giữ nguyên bytes/SHA cả trước và sau run. Candidate mới có thể xem riêng, **chưa nộp và chưa đủ bằng chứng tốt hơn Round14**:

- `outputs/task3/round15/public-candidate-zero/predictions.json`, SHA-256 **9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45**.
- `public-candidate-zero/run.json`, `metrics.json`, `public-aggregate.json`, `validation-report.json`, `validator-cli.log`: provenance, aggregate và VALID328/328.
- `attempts.jsonl`, `decisions.jsonl`, `progress.json`, `traces.json`, `raw-and-final.audit.json`: nguyên văn raw, prompt hash, retry reason và output theo ID; raw/source chỉ ignored outputs.
- `selected-prompt-freeze.json`, `public-usefulness-audit-plan.json`, `public-review/`: freeze và đánh giá mẫu cố định; không dùng kết quả audit để sửa phương pháp.

Scan tự động feedback không thấy private-key/GitHub-token/HF-token patterns; không gọi đây là chứng nhận mọi dữ liệu nhạy cảm. Không stage predictions, source, raw, bank, model/cache/ZIP.


## Audit usefulness public sau freeze

Mẫu **26 bài** được chọn trước bằng metadata/ID hash, gồm L1=6, L2=10, L3=10; kiểm tra tập ID trong cả hai review khớp đúng kế hoạch. Hai reviewer assistant ghi source/spec facts trước khi đọc output của mẫu, sau đó so new first raw/new final/old Round14 final trên cùng ID. Đây là đánh giá hậu kiểm, không human verification, không gán public gold taxonomy và không cung cấp findings trở lại inference. Không suy taxonomy F1 public hoặc tỷ lệ hữu ích toàn328; các Level được lấy mẫu với tỷ trọng khác tổng thể nên không gộp thành một tỷ lệ chung.

| Tiêu chí trên mẫu cố định | New raw | New final | Round14 final |
|---|---:|---:|---:|
| L1 gợi ý nhẹ, không praise/criticism thiếu căn cứ | 4/6 | **5/6** | 6/6 |
| L2 strict: đúng vị trí+cause hữu ích, không claim sai/hướng sửa | 4/10 | **3/10 (30%)** | 0/10 |
| L2 có thông tin partial | 4/10 | 4/10 | 9/10 |
| L2 material false claim | 3/10 | 3/10 | 0/10 |
| L2 có hướng sửa vượt Level | 3/10 | 3/10 | 1/10 |
| L3 strict: đúng cause+action cụ thể khả thi, không harmful claim | 0/9 | **0/9** | 0/9 |
| L3 safe partial diagnosis | 2/10 | 2/10 | 0/10 |
| L3 harmful/material false claim | 6/10 | 6/10 | 2/10 |
| L3 fallback | 0/10 | 0/10 | 8/10 |

L2 partial/uncertain là cờ riêng có thể chồng nhau, không cộng để tạo accuracy. Bảy ca L2 trong mẫu có compiler error: **Round14 định vị và thông báo diagnostic đúng7/7**, nên 0/10 strict không có nghĩa vô dụng. Nó thường chưa giải thích cause; strict vẫn chấp nhận cause compiler thông thường như thiếu dấu/ký hiệu, return value hoặc redeclaration, không đòi root cause ngữ nghĩa sâu. New raw giữ compiler-information7/7, final6/7. Mẫu thiên về compile errors không chứng minh cải thiện rộng cho semantic diagnosis. So paired final L2: **new tốt hơn3, cũ tốt hơn3, hòa3, chưa đủ căn cứ1**. L1: hòa5, cũ tốt hơn1; không phạt L1 vì không lộ technical diagnosis.

L3 có9 bài có actionable defect, một bài chưa xác lập lỗi cần sửa được chấm cách nói thận trọng riêng. Tính trên tất cả10, strict vẫn0/10 cả hai. New raw=final10/10; hai partial diagnoses có căn cứ nhưng thiếu action khả thi cụ thể, **không được nâng thành useful Level3**. Bốn paired safety losses (claim sai/hại mới nhiều hơn cũ), hai partial-utility gains, strict không có gain. Hai phản hồi mới trong mẫu chứa CJK; tổng toàn50 L3 là5. Không tìm thấy full-solution leak trong10 ca, không suy toàn50 đều tuân thủ.

**Attribution theo bài** giữ riêng trong review JSON. Một new L2 raw có cause đúng và chỉ trích điều kiện đang có trong source bị `code_solution_disclosure` hiểu thành code sửa; retry làm mất diagnosis ấy và thêm direction mơ hồ. Đây là **một raw-good → final-bad do hậu xử lý**, không lỗi model ban đầu. Một ca khác cũng mất diagnosis đúng sang fallback, nhưng raw đã kèm declaration sửa nên rejection có căn cứ về Level. Các lỗi model còn lại gồm định vị declaration sai thứ tự, quy literal của một hàm sang hàm khác đang dùng parameter đúng, đọc source đã comment như đang chạy, và hướng sửa cận vòng lặp làm phát sinh truy cập không hợp lệ. Raw L3 sai được final giữ nguyên đúng thiết kế, nên không quy các lỗi này cho guard.

Nhận xét đúng bị mất do guard cần là đối tượng sửa hậu xử lý trên **train/artificial** ở vòng sau; không đổi prompt/guard/output theo ca public vừa đọc, không chạy lại chọn candidate sau audit. Thí nghiệm development đã sửa false rejection noun phrase L1 trước freeze; lỗi source-quote L2 vẫn là blocker được phát hiện sau freeze. Việc giảm fallback từ74/328 xuống9/328 không chứng minh tăng phản hồi có ích: mẫu L3 cho thấy thêm claim sai nhưng chưa tăng strict repair usefulness. Candidate mới được giao để xem xét cạnh bản cũ, không khuyến nghị thay Round14 như một nâng cấp chất lượng đã chứng minh.

Artifacts: `public-review/l1-l2-new-vs-round14-review.json`, `l3-atomic-raw-final-old-review.json`, `l3-summary.json`, source-first facts và per-ID records. Trong một probe cấu trúc progress sau freeze, reviewer lỡ preview một đoạn record ngoài mẫu; `protocol-notes.json` ghi lại, loại hoàn toàn khỏi26 ca và không đổi mẫu/phương pháp/output. Không tuyên bố rằng chưa từng thấy bất kỳ record public nào ngoài mẫu; ranh giới chọn prompt vẫn được giữ vì toàn bộ exposure này xảy ra **sau freeze**.

## Tái hiện, kiểm thử và trạng thái bàn giao

Các lệnh development dùng output mới; cần giữ train data và bank ignored đã hash-bound, không lấy public làm ví dụ. Run gốc development dùng044daf0 trước sửa noun phrase, run public dùngf6a17b1; tái chạy development hiện tại có thể khác pilot ở một L1. Replay postfix đã giữ nguyên mọi raw và ghi khác biệt ấy. Public resume với freeze hiện tại tái sử dụng completed IDs, không sinh lại response cho328 ID đã hoàn tất; không cần chạy lại để lấy file hiện có.

```bash
cd /workspace/llm-final-project
.venv-task3/bin/python -m pytest -q tests/test_task3_*.py
.venv-task3/bin/python scripts/task3_round15.py \
  --config configs/task3/r15_zero_shot.yaml --phase development \
  --output-dir outputs/task3/round15/reproduce-zero-new
.venv-task3/bin/python scripts/task3_round15.py \
  --config configs/task3/r15_few_shot.yaml --phase development \
  --output-dir outputs/task3/round15/reproduce-few-new
.venv-task3/bin/python scripts/task3_round15.py \
  --config configs/task3/r15_zero_shot.yaml --phase development --baseline-round14 \
  --output-dir outputs/task3/round15/reproduce-r14-control-new
# Authenticated resume of the completed new candidate, not a fresh selection:
.venv-task3/bin/python scripts/task3_round15.py \
  --config configs/task3/r15_selected.yaml --phase public \
  --freeze outputs/task3/round15/selected-prompt-freeze.json \
  --output-dir outputs/task3/round15/public-candidate-zero
.venv-task3/bin/python scripts/validate_task3_submission.py \
  --predictions outputs/task3/round15/public-candidate-zero/predictions.json \
  --requested-levels outputs/task3/round15/task3_requested_levels.official.json
```

Full Task3 suite chạy lại sau public: **622 passed, 4 skipped, 6,93 giây**, log `outputs/task3/round15/tests-task3-final.log`. Validator độc lập VALID328/328. Commit triển khai044daf0, chọn/fix trước publicf6a17b1; commit báo cáo cuối chỉ bổ sung kết quả, không thay implementation/config/predictions. Round14 checksum vẫn nguyên75f9acd…ba0d4. Không fine-tune/Task2/mở rộng extractor, không sửa gold, không public-derived prompt tuning, không chạy heldout thêm, không push/PR/nộp leaderboard.
