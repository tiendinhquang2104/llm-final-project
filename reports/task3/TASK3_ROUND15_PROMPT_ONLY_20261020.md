# Task 3 Round 15 — prompt ngắn, raw Qwen và hậu xử lý, 20/10/2026

Chọn **zero-shot ngắn** trong hai prompt mới để tạo candidate public riêng; **không kết luận nó tốt hơn Round 14**. Development mới cho thấy model vẫn đọc sai code và bỏ lỗi: zero-shot có strict useful Level 2 **1/7** ca có lỗi được source-review xác nhận, Level 3 **0/7**; few-shot tương ứng **0/7** và **1/7**. Fallback ít không đồng nghĩa phản hồi có ích. Candidate Round 14 giữ nguyên SHA-256 `75f9acd13c183cf40154548eb3d530f14af6959c20b34b413d778eca756ba0d4`.

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
- **R14 postprocessing làm mất nội dung đúng:** raw SUMPAIR có hướng sửa local index đúng, nhưng indentation của quote không exact và action recognizer từ chối; retries vẫn nêu đúng repair rồi final thành câu chung. PROD L4 raw có hướng filename-parameter hữu ích nhưng bị missing-level4-solution; không tự gọi raw ấy là full solution. MINA L2 có false imperative detection do chữ “nên không tính tổng b”; final vẫn có diagnosis hữu ích. Có raw diagnosis observation bị mất nhưng raw cũng chứa repair leak thật, cần tách hai vấn đề.
- **Postprocess mới:** giữ mọi L3/L4 content kể cả generic hoặc sai. Same-text counterfactual trên16 raw L3 mới: R14 screen từ chối8/8 zero và7/8 few, screen mới0/8 cả hai; **không dùng chênh lệch acceptance này làm factual score**.

Phát hiện và sửa một false rejection Level1 mới: “các hàm cần thiết/phù hợp/tương ứng” là noun phrase, không phải identifier. Ba fixture nhân tạo tái hiện trước sửa; chỉ mask các noun phrase ngôn ngữ chung khi nhận diện identifier, không rule theo ID/code. Raw vẫn có subjective praise chưa xác minh, nên không gọi nó hoàn toàn tốt. Sau sửa replay **nguyên raw Qwen đã lưu**, không gọi model: zero dùng27/28 captured answers, chỉ đổi1 final; few dùng30/30, không đổi final. Hai pilot model runs giữ nguyên; final postfix replay ở `dev-zero-postfix-replay`, `dev-few-postfix-replay`. L2/L3 usefulness counts không đổi. Không khớp lại action grammar theo các câu đã thấy.

## Lựa chọn và đóng băng

Chọn **zero-shot** giữa hai prompt mới vì ít example contamination, taxonomy micro/exact tốt hơn và có actual-error Level2 diagnosis hữu ích hơn few. Few có một strict L3 success nhưng không bù được các wrong-cause/source-transfer claims. **Không chọn vì zero fallback=0**, không kết luận tốt hơn R14 control (control có L2/L3 strict useful nhiều hơn trên tập này). Config `r15_selected.yaml` kế thừa zero; không tiếp tục tìm prompt trên public.

Pre-public freeze sẽ ghi resolved config, code hashes sau noun-phrase fix, bank hash, selection/review/replay hashes và commit. Mẫu audit usefulness public được định trước bằng metadata/ID hash: L1=6, L2=10, L3=10, không đọc source/output để chọn mẫu. Source/feedback public chỉ review **sau inference đã đóng băng** để báo chất lượng, không sửa prompt/chọn lại model. Tỷ lệ useful sẽ ghi rõ mẫu/denominator, không gán cho toàn328 khi chưa review toàn bộ.

Full Task3 suite sau fix và kết quả public sẽ bổ sung dưới đây. Full repository đã thử, collect fail `test_clm_zeroshot_task1.py`, `test_task1_clm_probe.py` do thiếu sklearn; không cài hoặc sửa Task1 ngoài scope, không gọi Task3 pass là full-repo pass. Raw/model cache/predictions không stage, không push/nộp leaderboard.
