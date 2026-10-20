# Task 3 Round 16 — one-shot, few-shot và evidence CoT, 20/10/2026

**Không có winner. Giữ Round 15 zero-shot làm control.** Few-shot tăng số phản hồi Level 3 có hướng sửa khả thi từ 0/7 lên 2/7, nhưng không giảm claim sai; one-shot không cải thiện đáng tin cậy. Evidence CoT đạt 3/7 Level 3 nhưng làm tăng lỗi đọc source, ba false-positive compiler labels và lộ thông tin ở cả bốn ca Level 1. Không chọn theo F1 hoặc độ ngắn, không sửa thêm prompt sau khi xem kết quả. Đây là development đã từng được xem, không phải benchmark mù.

## Phạm vi và dữ liệu đã đọc

Làm trên branch hiện tại `feat/task3-quality-round5`, không checkout/worktree, fine-tune, Task 2, extractor/rule chấm lỗi mới, đổi model/precision/decoding, sửa gold, public inference, push hoặc leaderboard. Code/config/output control R15 và hai public candidate không thay đổi. Chỉ thêm module/config/script opt-in Round16, bank metadata và báo cáo.

Đã đọc `sample_dataset/task3_feedback.json`, `label_space.json`, `exams.json`; đối chiếu hash source của đủ 32 sample với `sample_dataset.zip` nằm trong ZIP gốc, đọc source golden tương ứng, đặc biệt EX01-S104/S105/S106 và EX02-S203. Golden thường ngắn, gọi Pn/hàm và đi thẳng lỗi; không phải oracle về giới hạn Level. EX01-S104 Level2 chứa hướng sửa; EX02-S203 Level3 chỉ khuyên học cú pháp, không đưa sửa cụ thể. Chấm theo định nghĩa Level trong label_space, không thưởng việc giống teacher feedback.

Chỉ đọc metadata schema public `task3_feedback.json`, không dùng source/feedback của 328 public records để làm bank hoặc chọn prompt. Public không cung cấp taxonomy_error, output cần hai khóa taxonomy_error/feedback. Danh sách 10 nhóm trong core lấy nguyên văn qua `LABEL_SPACE`, đúng label_space.json. Taxonomy được yêu cầu độc lập requested Level và cho phép nhiều nhóm/[]; không ép dương theo Level. Annotation development có nhiễu: thiếu body có thể được gán “Lỗi hàm” nhưng model gọi “Lỗi logic”; style/TODO không phải proof thuật toán sai; extra whitespace chưa có exact-output contract.

## Prompt, bank và split khóa trước inference

A gọi nguyên `round15_runner.run_records` với nguyên config `r15_zero_shot.yaml` đã resolve và `examples=[]`; chạy lại trên cùng 24 query. B/C/D dùng nguyên core instruction người dùng yêu cầu, thêm chính xác danh sách nhóm lỗi và schema. Query giữ toàn bộ đề, problems/prototype, grading policy, active source lẫn comment nguyên văn, requested Level và C++11 compiler status/diagnostic; gold/teacher feedback/test report được xóa bằng sanitize trước render.

- B: **đúng một block ví dụ**, cùng requested Level, rồi query. Luôn chọn ví dụ lỗi viết hoa chuỗi đã khóa, không dựa vào gold/query feedback.
- C: **đúng hai block**, cùng Level: bài viết hoa có lỗi và bài GCD đúng được source-review. L2 chẩn đoán không sửa; L3 đưa hành động chuyển chữ thường thành chữ hoa; L4 có hàm sửa tích hợp được. Không cắt query; nếu không chứa đủ số ví dụ tối thiểu và full query thì fail budget, không lén biến few-shot thành zero-shot.
- D: không ví dụ; evidence tối đa hai finding gồm location/source_excerpt/requirement_or_diagnostic/defect. Runner kiểm tra **schema**, giữ evidence nguyên vẹn để review, chiếu taxonomy_error/feedback ra final. Không quote gate, confidence gate, keyword action gate hoặc câu thay thế chung. Nội dung sai vẫn được giữ và tính là lỗi nhánh.

Bank gồm tám bài làm giả (hai bài × bốn Level), từ đề train không thay đổi của `SYN-UPPER-0006` và `SYN-GCDARR-0007`. Source giả được biên soạn riêng: uppercase đang chuyển ngược hoa→thường; GCD đọc streaming và Euclid số dư, không phụ thuộc kích thước mảng. Không lấy code/public/teacher feedback làm reference. C++11 syntax pass cho cả hai; reasoning source cho lỗi uppercase có counterexample `aB → ab`, yêu cầu `AB`; GCD có invariant GCD của prefix, đọc đủ n số dương hợp lệ. Giọng ví dụ ngắn; L1 positive là gợi ý nhẹ, clean là khen có căn cứ. Provenance: **assistant-reviewed, not human-verified**.

Metadata từng ví dụ lưu ID, parent ID, partition, family, source SHA-256, statement hash, parent-code hash, lexical/renamed hash, lý do chọn và Level assignment chỉ trong bank. Full bank ở ignored `outputs/task3/round16/train-examples.json`, có builder tái hiện `round16_bank.py`. Hash bank: `07af215d6f86ab73c248d0f11ed3cf79d7384ea991712ea5a7f1256b2b7a861b`; chi tiết nằm trong [freeze JSON](TASK3_ROUND16_FREEZE_20261020.json). ID/family/code hash được kiểm tra với **toàn bộ 239 record của 12 family development**, không chỉ 24 query; hai parent train family UPPER/GCDARR khác toàn bộ family evaluation, code giả cũng không collision exact/identifier-renamed. Không có phép chọn ví dụ theo nhãn query. Pattern chuyển hoa↔thường và streaming Euclid khác các biểu thức lỗi query.

Tập 24 ID chọn bằng selector R15 cũ, train-only synthetic-train, quota **4/8/8/4**, 12 family ×2, đủ 10 nhóm gold và 3 gold[] ở L1. Selection identity `8201d48b8d2b211b0ba2a4d8cba4834c52feee0e4a2b4eba7765c4796aab2bba`. Đây là R14 reserve; R13 từng xem training corpus, R15 đã dùng/review đủ24. Không gọi split mới hoặc chưa từng thấy. Manifest chọn theo gold chỉ để phân tầng evaluation; inference không nhận gold. [Source expectations](TASK3_ROUND16_SOURCE_REVIEW_20261020.md) được viết trước khi đọc outputs mới.

Freeze ban đầu lưu bank/input/config/code hashes trước model run. Có hai sửa đóng gói được ghi rõ: (1) sau control, metric cũ không nhận thiếu first-raw JSON nên thêm coverage; (2) review độc lập phát hiện resume runtime-error và tổng attempt thiếu ID thất bại, đã sửa với test đỏ→xanh. Không thay prompt/bank/query/model hoặc response. Các freeze trước amendment được giữ ở `freeze.initial.json` và `freeze.generation.json`; `run.json` gắn hash freeze thực lúc generation. Freeze hiện tại ghi cả code generation cũ và code tái hiện đã sửa. Không có runtime error trong paired run; sửa resume không đổi kết quả. Không inference vòng prompt thứ hai.

## Điều kiện paired và raw capture

Cùng Qwen/Qwen2.5-Coder-7B-Instruct revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, NF4 double-quant, compute BF16, CUDA RTX5090; runtime xác nhận pinned revision/precision, không offload/adapter. Seed42, greedy `do_sample=false`, context16.384, output cap1.024/L4 1.536, cùng soft max_time45s, tối đa3 attempts. Chỉ prompt và đóng gói schema evidence thay đổi ở B/C/D; A giữ guard/controller R15. C++11 `-fsyntax-only`, không chạy chương trình sinh viên. Warning không phải error. Compiler input được khóa bằng hash, không đưa latency compiler vào query/identity.

Tokenizer preflight cả first/worst retry: tối đa **1.780 input tokens**, không bỏ ví dụ hoặc truncate query. Actual token count, rendered messages, prompt SHA, raw text, EOS/finish, output tokens, latency nằm trong durable journal trước parser. Runtime error cũng ghi nguyên, không tự sinh feedback. Resume kiểm tra identity/prompt hash/order và final so journal. A giữ disclosure retry cũ; B/C/D chỉ retry schema. Mỗi ID có first raw, retry raw, nguyên nhân retry và final hoặc unresolved reason trong `review/raw-final.private.json`; A retry reasons được lấy lại từ decisions.jsonl, không thay control.

B/C cùng thất bại `SYN-REVSTR-0003`: cả ba attempts lặp feedback chứa `cout << " ";` không escape dấu nháy trong JSON. Không sửa raw bằng parser lỏng, không thay []/câu chung. Vì vậy chỉ có `completed.predictions.json` 23 bài ở B/C, không có file giả vờ complete24. A retry ba ID do schema/disclosure; D không retry.

## Kết quả định lượng

Bảng F1 chính dùng **23 ID có final ở cả bốn nhánh**, loại cùng `REVSTR-0003` ở A/D để so paired. JSON completion vẫn tính trên đủ24. Không gán [] giả cho ID sai schema.

| Metric | A R15 zero | B one | C few | D evidence CoT |
|---|---:|---:|---:|---:|
| Final JSON hoàn tất | 24/24 | 23/24 | 23/24 | 24/24 |
| First raw schema hợp lệ | 23/24 | 23/24 | 23/24 | 24/24 |
| Micro F1, common23 | 0,0909 | 0,0833 | 0,0851 | 0,1538 |
| Macro F1, common23 | 0,1500 | 0,1091 | 0,1100 | 0,1297 |
| Exact set, common23 | 5/23 | 1/23 | 1/23 | 2/23 |
| Compiler final TP / FP / FN | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 3 / 0 |
| Compiler TN / coverage | 23/24 | 22/23 | 22/23 | 20/24 |
| Attempts, kể cả ID thất bại | 27 | 26 | 26 | 24 |
| Fallback thay feedback | 0 | 0 | 0 | 0 |
| Output tokens mọi attempt | 2.040 | 1.435 | 1.442 | 6.536 |
| Generation latency tổng (s) | 26,26 | 19,60 | 20,05 | 79,06 |

F1 trên toàn bộ final sẵn có (khác coverage, không phải bảng paired chính): A micro/macro **0,1304/0,1667**, exact6/24; B **0,0833/0,1091**, exact1/23; C **0,0851/0,1100**, exact1/23; D **0,1818/0,1458**, exact2/24. Raw-first compiler A/B/C cùng TP1/FP0/FN0/TN22 trên23 valid JSON; D như final. Per-label TP/FP/FN/P/R/F1, raw taxonomy và missing ID nằm trong [results JSON](TASK3_ROUND16_RESULTS_20261020.json). Không suy semantic correctness từ trùng nhãn nhiễu.

## Source và Level review

Một assistant đọc toàn bộ source trước, review đủ96 first-raw text × final, cả7 retry raw; schema-invalid text vẫn được review nội dung. Không reviewer người, không double-blind. Ledger [manual review](TASK3_ROUND16_MANUAL_REVIEW_20261020.json) ghi từng ID/nhánh, supported/false/unassessed, Level và lý do. Đơn vị dưới đây là **số record có ít nhất một claim tương ứng**, không phải số atomic claim hoặc factual precision/recall; supported và false có thể đồng thời đúng. Raw D gồm evidence; final chỉ còn hai trường nên giảm claim sau projection không phải sửa model.

| Manual metric | A | B | C | D |
|---|---:|---:|---:|---:|
| Có material claim supported, raw / final | 19 / 17 | 16 / 15 | 15 / 14 | 18 / 18 |
| Có materially false claim, raw / final | 10 / 10 | 10 / 10 | 11 / 11 | 20 / 16 |
| L1 false praise có thể xác nhận | 0/4 | 0/4 | 0/4 | 0/4 |
| L1 lộ vị trí/cause/repair raw = final | 1/4 | 0/4 | 2/4 | 4/4 |
| L1 exact repeated template: số record tham gia | 0/4 | 2/4 | 0/4 | 0/4 |
| L2 repair leak raw / final | 4/8 / 2/8 | 3/8 / 2/7 | 1/8 / 0/7 | 3/8 / 3/8 |
| L2 strict useful final, confirmed-defect denominator | 1/7 | 1/7 | 2/7 | 0/7 |
| L3 correct cause + feasible repair final | 0/7 | 1/7 | 2/7 | 3/7 |
| L3 repair có thể gây lỗi khác, ít nhất | 3 | 0 | 1 | 1 |
| Median final feedback chars | 172 | 91 | 102 | 153 |

L2 có8 bài, loại whitespace-only REVSTR-0003 khỏi denominator confirmed semantic defect; A có thêm một observation formatting có source, impact checker chưa rõ. L3 có8 bài nhưng SUMEVEN-0007 chưa có actionable semantic defect trong miền đọc hợp lệ được source-review xác nhận; không bắt bịa sửa để khớp gold style. Safety khi n>100 vẫn là limitation có điều kiện, không đồng nghĩa compiler error. Trên tất cả8 bài, số L3 useful vẫn0/1/2/3.

L2 strict tính task-restatement kiểu “Cần tính tổng b” như hướng sửa khi đề xuất thực hiện body còn thiếu; nếu coi đây chỉ là chẩn đoán thì A MINA-0005 có thể tăng usefulness từ1 lên2, không đổi quyết định. L3 strict yêu cầu hướng sửa được phát biểu, không chỉ nêu `n+1 thay vì n`; B PERFECT-0008 là borderline nếu chấp nhận hướng sửa ngầm. B/C BASE2 chỉ số chẩn đoán đúng nhưng hậu quả “bỏ phần tử cuối” sai (thực tế bỏ bit0), nên không strict pass. D SUMPAIR có sửa P3 đúng nhưng hướng sửa P2 không rõ và evidence P2 sai; không strict pass. D PERFECT-0008 final sửa đối số n đúng; lời nhắc kiểm tra n1 thừa, còn raw finding khẳng định n1 chưa xử lý là sai. Không chuyển finding sai thành final false claim nếu final chỉ nhắc kiểm tra chứ không khẳng định thiếu.

Harmful repairs có chứng cứ: A BASE2-0005 đòi in bit thấp trước làm n=6 ra011 thay110; A BASE2-0011 đề xuất dấu phẩy không sửa compile error; A FIB-0004 đổi f[n]→f[n-1] làm n=3 ra1 thay2. C PERFECT-0008 đề xuất kiểm tra n-1 làm n=6 kiểmtra5, raFalse sai. D DISTINCT-0008 đòi kiểm tra mọi phần tử kể cả chính phần tử hiện tại, có thể làm mọi phần tử bị coi đã xuất hiện. Không gọi hướng sửa chung hoặc phép thay tương đương là useful.

Bảy patch minh họa được C++11 syntax-check riêng: sáu pass (cả patch C PERFECT sai logic), patch A thiếu ;→dấu phẩy fail. Kết quả `review/repair-syntax-checks.json`. Compiler pass không được tính là sửa đúng semantics; counterexample ở trên là source reasoning, không có executable sinh viên chạy.

Giọng B/C thường ngắn và tự nhiên hơn A; B L1 chép nguyên ví dụ ở2/4 record, ba bài gold[] đều nhận negative generic thay lời khen có source. C vẫn có nhận xét lạc yêu cầu, như chê P4 tự tính lại thay vì gọi P2. D thêm false finding rồi biến chúng thành feedback dù excerpt đúng. Không chấm cao văn phong khi nội dung sai. L4 được phép code, không bắt buộc full solution: B có patch for i<n nhưng kèm claim x chưa khởi tạo sai; C có hướng sửa đủ n hữu ích; A/B/C có hướng bỏ whitespace nhưng impact chưa chắc. Không công nhận một lời giải hoàn chỉnh đã được xác minh trên mọi miền dữ liệu.

## Evidence CoT và contamination

[Evidence ledger](TASK3_ROUND16_EVIDENCE_REVIEW_20261020.json): **47 finding**, cả47 có code đang hoạt động tương ứng (một số trích cả hàm có comment; whitespace được đối chiếu thủ công). Chỉ **19 supported**, **23 contradicted**, **5 unassessed/subjective** về defect. Có excerpt thật không chứng minh suy luận đúng. Hai mâu thuẫn trực tiếp evidence→feedback: PERFECT-0004 finding nói bắt đầu2 đúng nhưng final bảo bắt đầu1; PROD-0004 finding muốn arr[i].b nhưng final nói arr[i-1]. D còn mâu thuẫn compiler pass ở COUNTEVEN-0000, MINA-0001, DISTINCT-0016. Không evidence gate nào âm thầm sửa những lỗi này. D không giúp giảm nhận định sai trên tập này.

B/C: **0 ca chắc chắn mang identifier/task viết hoa/GCD sang query**. Có **1 ca transfer sai đáng nghi ở mỗi nhánh**, cùng REVSTR-0004-L2: ví dụ L2 có câu “đầu vào aB cho ra ab thay vì AB”; B đổi sang “abc cho ra cba thay vì bca”, C thành “abc cho ra cba thay vì abc”. Source cho thấy cba chính là reverse đúng của abc; model bắt chước cấu trúc counterexample và bịa expected output. Đây là quan sát cụ thể; **attribution nhân quả chỉ probable**, không được single-run chứng minh. Positive-label/negative-template trên3/3 bài gold[] là thêm dấu hiệu ảnh hưởng ví dụ, không tự đếm thành definite contamination. Không lựa chọn lại bank sau quan sát.

## Những bất đồng quan trọng theo ID

| ID | Source/diagnostic chính xác | Raw/final đáng chú ý | Phán định |
|---|---|---|---|
| MINA-0005-L2 | `int prob3(Rec* arr, int n) { return 0; }`; P3 tổng b | A đúng body thiếu nhưng “Cần tính tổng” vượt L2; C đúng chẩn đoán, không sửa; D bịa thêm P4 sai | C hữu ích hơn ở ID này, không đủ kết luận toàn nhánh |
| REVSTR-0003 | `cout << " ";` | B/C cả3 raw sai escape dấu nháy, final absent | Schema failure; không có final để chấm tốt |
| REVSTR-0004-L2 | `for (int i = 0; i <= n / 2; i++)` | B đòi bca/C đòi abc cho inputabc; source ra cba đúng với input lẻ | Model chọn counterexample sai; case chẵn abcd mới lộ vòng swap thừa |
| PROD-0004 | `new Rec[soDong + 1]`; `arr[i].a * arr[i + 1].b` | A nói vượt allocation; B/C hiểu sai phép so; D evidence i, final i-1 | Vấn đề thật là trộn record/đọc chưa gán, không phải mọi lần vượt allocation |
| BASE2-0011 | `string r = ""` rồi `if`; compiler `error: expected ',' or ';' before 'if'` | A bảo dấu phẩy; B ngoặc nhọn; C ngoặc kép; D evidence semicolon và final ký hiệu(;) | D có hướng sửa khả thi, thuật ngữ “dấu phẩy (;)” vẫn chưa tự nhiên |
| DISTINCT-0016 | `for (int i = 0, x; i < n - 1; i++) { cin >> x; st.insert(x); }` | B sửa cận đúng nhưng bịa x chưa khởi tạo; D nói x chưa khai báo và compile error | x đã khai báo, đọc trước dùng; compiler pass thật |
| FIB-0004 | `if (n == 1) return 0;`; F(1)=1 | A đổi chỉ số sai; B khen dem đúng; D sửa return1 | D đúng final ở ca này |
| PERFECT-0008 | `cout << (tong(n + 1) ? "True" : "False");`; `if (n <= 1) return false;` | B chỉ chẩn đoán; C sửa n-1 sai; D sửa n đúng nhưng raw bịa thiếu xử lý1 | Review raw và final riêng; D vẫn có false finding |
| SUMEVEN-0007 | `if (a[i] % 2 == 0) s = s + a[i];` | A/B/D nói gán đè; C bảo đã qua tất cả kiểm tra | Cộng dồn đang đúng; compiler-only không chứng minh đã test hết |
| SUMPAIR-0011 | `kq3 = arr[i + 1].a;` | B/C chỉ đúng source và yêu cầu cập nhật arr[i].a | Hai nhánh có một hướng sửa thật, dù chưa sửa mọi lỗi trong bài |

Toàn bộ96 judgement ở ledger; bảng này chọn ca quan trọng, không phải toàn bộ audit.

## Các cặp raw/final minh họa

1. **A / PERFECT-0004, L2**: first raw đề xuất vòng1..n/2 → retry final `Biến 'dem' nên bắt đầu từ 0 thay vì 1.` Source đang dem=1 để tính ước1. Retry không cải thiện factual correctness và final vẫn vượt Level. Đây là model retry sai, không phải postprocessor tự bịa câu.
2. **B/C / REVSTR-0003, L2**: cả ba raw chứa feedback `... nên bỏ dòng cout << " "; ...` với dấu nháy chưa escape trong JSON → **không có final**, unresolved `strict JSON object required`. Không thay bằng câu chung.
3. **C / SUMPAIR-0011, L3**: raw chỉ ra `kq3` cập nhật `arr[i+1].a` và yêu cầu `arr[i].a` → final giữ nguyên taxonomy/feedback, hướng sửa đúng cho P3. Không có guard sửa ý.
4. **D / PROD-0004, L2**: evidence muốn `arr[i].a * arr[i].b`, feedback lại nói phải dùng `arr[i-1]` → final chỉ bỏ evidence, **giữ nguyên feedback sai**. Ghi thất bại nhánh D.
5. **D / DISTINCT-0016, L4**: raw evidence `cin >> x;` nhưng kết luận chưa khởi tạo/chưa khai báo và `Lỗi biên dịch` → final giữ claim sai, không factual fallback. Diagnostic C++11 pass.
6. **D / FIB-0004, L3**: raw evidence trích `if (n == 1) return 0;`, final yêu cầu trả1 khi n1 → final giữ hướng sửa đúng; advice đổi tên tong là thừa/subjective. Đây là improvement riêng lẻ, không làm D thành winner.

## Tái hiện và kiểm tra

Từ repo, dùng môi trường Task3 có checkpoint cache sẵn, không tải hoặc đổi revision:

```bash
.venv-task3/bin/python scripts/task3_round16.py --prepare --output-root outputs/task3/round16-repro
.venv-task3/bin/python scripts/task3_round16.py --output-root outputs/task3/round16-repro
.venv-task3/bin/python scripts/task3_round16_review.py --root outputs/task3/round16-repro
.venv-task3/bin/python -m pytest tests/test_task3*.py -q
```

`--prepare` yêu cầu directory chưa có freeze, không overwrite bank/split để tune. `--conditions control one_shot few_shot evidence_cot` có thể ghi rõ để chọn subset/resume; mặc định đủbốn. Review script không gọi model, dùng ledger thủ công đã commit; ledger được bind với hash từng raw/final: nếu generation mới khác, script dừng và **phải review lại ledger**, không dùng judgement cũ như chấm tự động cho output mới. Canonical freeze/report giữ provenance generation gốc. Journal/resume binding chặn đổi input/config/prompt bất hợp lệ. Raw/output/source ở ignored outputs; không commit raw student source, checkpoint hay generated predictions.

Test mới bao gồm: shot count/Level/full query/budget; evidence projection giữ cả claim sai; capture trước schema retry; resume identity; partial raw metric coverage; transient runtime error resume; failed IDs vẫn trong tổng attempt. Review độc lập xác nhận hai fix. **Kiểm tra cuối: 629 passed, 4 skipped, 0 failed** trong toàn bộ Task3; chi tiết ở [verification JSON](TASK3_ROUND16_VERIFICATION_20261020.json). Full repo trong `.venv-task3` không collect được hai module Task1 vì thiếu sklearn (`test_clm_zeroshot_task1.py`, `test_task1_clm_probe.py`); system python không có pytest. Chạy phần còn collect được gặp hai lỗi Task1 secrets có sẵn: `test_timeout_falls_back_to_hidden_input_once`, `test_selected_provider_only_requires_its_key`; dừng khi suite chờ lâu, kết quả40 passed/2 failed/5 skipped. Không sửa Task1 hoặc cài dependency ngoài phạm vi. Task3 được chạy riêng đầy đủ.

Hai candidate kiểm tra hash trước/sau:

- R14 `75f9acd13c183cf40154548eb3d530f14af6959c20b34b413d778eca756ba0d4`.
- R15 `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`.

Không đề xuất thay candidate/control. Giữ B/C/D dưới dạng thí nghiệm có thể tái hiện; C có một số sửa Level3 đáng quan tâm, nhưng chưa đủ lợi ích source/Level để chọn. D nên giữ evidence như artifact audit, chưa dùng làm prompt mặc định.
