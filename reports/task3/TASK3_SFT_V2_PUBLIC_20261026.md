# Task 3 SFT v2 — hậu kiểm và public, 26/10/2026

**Public hợp lệ 320/328; `complete_export=false`.** Đã xuất cục bộ, **chưa submit**. File [partial.predictions.json](../../outputs/task3/sft-v2-public-20261026-run1/submission/partial.predictions.json) có SHA256 `8386c5a26ef82312f4fe446b3110aa19f81c5e4995f96e229b47eeef4d209359`. Đây là bản thiếu 8 ID, **chưa sẵn sàng về cấu trúc để nộp đủ bộ public**. Không tạo `submission/predictions.json` và không thay file ở gốc repo.

Cả 320 mẫu đủ context đã gọi đúng một lần và đều trả JSON hợp lệ, kết thúc EOS. Tám mẫu L2 không gọi model do prompt đầy đủ cộng allowance vượt context native8192. Không cắt log/source/yêu cầu, tăng context, gọi sửa, điền dự đoán sạch, ghép A/R15 hay sửa feedback. [validation.json](../../outputs/task3/sft-v2-public-20261026-run1/submission/validation.json) xác nhận lại byte thực tế theo validator của repo trên tập con320 ID, đúng thứ tự và hai khóa payload `taxonomy_error`, `feedback`. Validation tập con không chứng nhận bộ328 hoàn chỉnh hoặc chẩn đoán đúng.

## Phạm vi và danh tính

Worktree `/workspace/llm-final-project-arm-d-plus`, branch `fix/task3-strict-feedback`, HEAD `60c76dc1a1104557b5d10dca4f78baf57413cf4d`. Không train, đổi selection, tạo v3, commit, push, upload hoặc submit. Dùng nguyên môi trường `/workspace/llm-final-project/.venv-task3/bin/python`; không cài/nâng dependency.

Đã kiểm seal của manifest/selection, tính lại đúng luật chọn dev và kiểm từng file checkpoint, thay vì suy từ tên thư mục. Adapter là V2 step240 đã chọn từ trước; quyết định/policy lịch sử giữ nguyên. Model `Qwen/Qwen2.5-Coder-7B-Instruct`, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`; loader native V2 NF4, double quant, BF16 compute, SDPA và chuẩn bị base giống lượt đánh giá V2. Adapter chỉ inference, không optimizer. Tokenizer/chat template/system prompt/parser native giữ nguyên.

Identity mới: `task3-sft-v2-step240-native-public-primary-v1`. [public-freeze.json](../../outputs/task3/sft-v2-public-20261026-run1/public-freeze.json) SHA256 `66fbf5c75487247321668da5cac00ca07a0b08e51f6d3fddd0ee48f8a7b6fb30` khóa code, input/order/Level, source, adapter, tokenizer, prompt, parser, context preflight và review slice trước reservation đầu tiên. Freeze sơ bộ trước review được giữ riêng; ba lỗi triển khai về binding export/journal, OOM trước reservation và index lịch sử đã được sửa, kiểm thử rồi khóa lại **trước mọi lời gọi Qwen**. Không thay input/generation policy giữa lượt.

## Hậu kiểm clean/faulty: lợi ích chủ yếu ở clean

Tính lại trực tiếp 12 state đã lưu trên dev/final/observed regression; 915 đối chiếu, không sai khác. Không gọi Qwen mới cho phần này, không sửa verdict cũ. Một target là một Level; bốn target cùng source phụ thuộc nhau. Final160 target/40 source; regression80/20; dev80/20. Không có ID thiếu, trùng hoặc thừa trong các generation state. A/R15-dev có9 record `status=missing` do controller không xuất payload: tính là invalid output, phân biệt với ID vắng.

| Tập / chỉ tiêu | V1 | V2 |
|---|---:|---:|
| Final: false alarm clean | 56/80 | 6/80 |
| Final: joint clean | 10/80 | 53/80 |
| Final: joint faulty | 17/80 | 8/80 |
| Final: faulty taxonomy rỗng | 17/80 | 54/80 |
| Final: faulty invalid | 1/80 | 4/80 |
| Final: L3 faulty hướng sửa đúng | 1/20 | 2/20 |
| Regression: joint clean | 6/20 | 15/20 |
| Regression: joint faulty | 18/60 | 8/60 |
| Regression: faulty taxonomy rỗng | 11/60 | 38/60 |
| Regression: L3 faulty hướng sửa đúng | 1/15 | 2/15 |

Final V2 clean:6 nonempty,70 empty,4 invalid trên80; faulty:22 nonempty,54 empty,4 invalid trên80. Taxonomy nonempty trên source lỗi chỉ dự đoán có lỗi, chưa chứng minh đúng loại hoặc đúng chẩn đoán. Empty không mặc nhiên là joint success; invalid không chuyển thành clean. V2 giảm báo lỗi oan nhưng bỏ sót faulty nhiều hơn; hướng sửa L3 hữu ích vẫn rất ít.

Balanced joint hậu nghiệm = `0.5 × clean_joint_rate + 0.5 × faulty_joint_rate`: final V1 **0,16875** → V2 **0,38125**; regression **0,30000** → **0,44167**. Đây là mô tả post hoc, không phải điểm Task3 chính thức, không dùng chọn lại checkpoint. Joint giữ đúng verdict/điều kiện cũ, không đồng nghĩa taxonomy exact-match. Taxonomy F1 bảo thủ final V1 **0,3939** → V2 **0,3519**; precision tăng nhưng recall giảm (**0,4875 → 0,2375**). Không thay metric chính thức bằng chỉ số này.

Final V2 L1–L3 hợp lệ120/120; L4 32/40. Tám invalid lịch sử đều `malformed_json` dù kết thúc EOS, gồm4 clean/4 faulty. Code L4 vượt bộ test hữu hạn11/40, giải thích pass8/40; trong11 code pass có3 giải thích fail,1 uncertain. Regression code pass5/20, trong đó3 giải thích fail. Code qua test không cứu lời giải thích sai và không chứng minh đúng tuyệt đối.

Đủ các state, TP/FP/FN, precision/recall/F1 valid-only và bảo thủ, bảy trục semantic, per-Level, mẫu số source/target và taxonomy cross-Level tại [posthoc.md](../../outputs/task3/sft-v2-public-20261026-run1/posthoc/posthoc.md), [tables.json](../../outputs/task3/sft-v2-public-20261026-run1/posthoc/tables.json), `tables.csv`, `reconciliation.json`. Dữ liệu synthetic và agent review không phải gold độc lập của BTC.

## Audit taxonomy–feedback và errata

Đã đọc nguồn/đề cho toàn bộ120 final V2 L1–L3 và60 regression V2 L1–L3. Audit mới giữ riêng, không sửa review thí nghiệm:174 nhất quán nội bộ,2 mâu thuẫn,4 uncertain. Đánh giá căn cứ nguồn riêng:83 supported,93 unsupported,4 uncertain. **Nhất quán nội bộ không đồng nghĩa đúng**: `[]` cùng lời khẳng định đúng trên chương trình lỗi vẫn có thể nhất quán nhưng sai nguồn.

Hai mâu thuẫn rõ là `V2E03-D1-L3` và `V2E07-D1-L3`: taxonomy rỗng nhưng lời nhận xét tự mô tả lỗi; trường hợp thứ hai còn đưa hướng bổ sung nhánh xử lý `*`. Đã liên kết đủ60 bằng chứng L4 hiện có;6 trường hợp code qua bộ test nhưng giải thích fail và1 uncertain. Không chạy lại Qwen hay runtime test cho audit này.

[VIaudit.md](../../outputs/task3/sft-v2-public-20261026-run1/consistency-audit/VIaudit.md), `audit.rows.jsonl` và `l4-linked-evidence.json` chứa bằng chứng cụ thể. [errata.json](../../outputs/task3/sft-v2-public-20261026-run1/consistency-audit/errata.json) ghi riêng6 đề xuất sửa verdict có chứng cứ, gồm chẩn đoán status đúng nhưng bị fail và L2 false-clean được đánh Level pass. Các số lịch sử phía trên **chưa áp dụng** errata này.

## A/R15: implementation, input semantics và provenance khác nhau

Đã kiểm prompt thực tế của240 target synthetic/316 attempt A/R15 trong V2: full statement, source, Level, submission mode và syntax diagnostics khớp. `problems=[]`, `grading_policy=None` không làm thiếu ngữ nghĩa trong bộ single-problem này, vì toàn bộ yêu cầu đã nằm trong statement. Dev80 dùng so token; final32 exact-byte và128 token, quy tắc đều được giữ. Không thay metric cũ, không chạy lại A/R15.

Public A/R15 lịch sử giữ statement/P1–P4/source/Level, nhưng renderer bỏ một số metadata structured (`constraints`, `io_mode`, prerequisite) và exam note; supplied log chưa được quy nguồn riêng với local log. Ví dụ statement Armstrong có cận bị lỗi hiển thị, trong khi structured constraints ghi rõ `1 <= n <= 10^9`. Vì vậy không tuyên bố mapping public lịch sử bảo toàn mọi chi tiết. Mapping native public mới có identity riêng và giữ đầy đủ các trường đó; chưa có lượt A/R15 mapping sửa để so trực tiếp.

Comparator dùng duy nhất file gốc `/workspace/llm-final-project/outputs/task3/round15/public-candidate-zero/predictions.json`, SHA256 `9ba7411c35a3461b5747be367274631d5122455335061005c695276ed76c5a45`, hợp lệ328/328 và byte-identical A/public replay. Đã xác minh identity,361 prompt/attempt và đường trace→export;304 kết quả từ lượt đầu,15 retry,9 fallback. Đây là provenance implementation/artifact đã kiểm. **Liên kết với điểm người dùng báo0,3834 vẫn UNVERIFIED**, chưa có receipt gắn byte file đã upload. Không coi0,3834 là phép đo mới.

A/R15 có renderer/parser/guard/controller lịch sử, tối đa3 attempt và fallback L1/L2; native V2 public chỉ một lượt, không fallback. Khác biệt phương pháp và mapping hạn chế suy luận nhân quả từ public. Chi tiết: [audit.vi.md](../../outputs/task3/sft-v2-public-20261026-run1/ar15-audit/audit.vi.md), `audit.json`, `comparator-manifest.json`.

## Public mapping, context và tám trường hợp chưa giải quyết

Đã xác minh ZIP/requested mapping/label space chính thức:328 ID, L1=115, L2=163, L3=50, L4=0; không suy Level từ hậu tố ID. Có328 source file,326 SHA nguồn khác nhau. Mapping giữ nguyên full statement và source đã decode theo loader có sẵn; append phần yêu cầu structured được whitelist, prototype/P1–P4/prerequisite, grading policy, metadata exam/input liên quan qua trường `statement` của native renderer. ID/hash/group ở sidecar, không đưa vào prompt. Không thêm private witness/gold/teacher feedback.99 supplied log không rỗng được giữ nguyên, tách nhãn với local compiler diagnostics.

Compiler bị giới hạn bằng runner chroot/UID/seccomp/rlimit có sẵn, C++11 `-fsyntax-only -fmax-errors=3`, trên source không sửa;326 lời gọi mới và2 lần tái dùng cache khớp source/toolchain/flags/policy. Không link hoặc execute chương trình sinh viên; compile pass không phải chứng minh đúng.

Context **8192** được đọc từ guard thực tế của native `generate`, không lấy training max_length để suy ra và không thay bằng context16384 của A/R15. Allowance native L1–L3=1024, L4=1536 (public không có L4), greedy, concurrency1, max_time45s, EOS151645, pad151643, một reservation mỗi mẫu. Tokenizer thực retokenize full prompt trước inference, không truncation.

| ID chưa giải quyết, đều L2 | Prompt token | + allowance | Giới hạn |
|---|---:|---:|---:|
| Class01-Test1-S01 | 18.824 | 19.848 | 8.192 |
| Class01-Test1-S08 | 8.548 | 9.572 | 8.192 |
| Class01-Test1-S09 | 12.254 | 13.278 | 8.192 |
| Class01-Test1-S10 | 9.984 | 11.008 | 8.192 |
| Class01-Test2-S08 | 9.259 | 10.283 | 8.192 |
| Class01-Test2-S13 | 11.354 | 12.378 | 8.192 |
| Class02-Test1-S19 | 12.809 | 13.833 | 8.192 |
| Class02-Test1-S34 | 8.602 | 9.626 | 8.192 |

Supplied log của các mẫu này dài13.953–52.303 ký tự; giữ đủ log là một phần input contract. Mỗi mẫu có0 lời gọi và không có raw response; semantic verdict `not_evaluable`. [preflight-failure-review.json](../../outputs/task3/sft-v2-public-20261026-run1/preflight-failure-review.json), `context-preflight.json`, `public-inputs.private.jsonl` và `submission/unresolved.json` giữ token, input đầy đủ và history. Trường parser của unresolved là `termination_failure` do `not_called`; nguyên nhân gốc `context_preflight_failure` nằm rõ trong `raw_history`, sidecar và bảng này. Không có lỗi parse/timeout/length/OOM ở320 phản hồi thực tế.

## So sánh public mô tả

Align exact ID và Level chính thức: V2 hợp lệ320, không có payload8; comparator hợp lệ328, không thiếu/không tương thích. Trên320 cặp cùng hợp lệ: nonempty→nonempty176, empty→nonempty48, empty→empty72, nonempty→empty24;98 cặp đổi tập nhãn. Các chuyển đổi không chứng minh cải thiện. Public không có gold để báo accuracy/F1 hoặc điểm Task3 mới. Độ dài feedback, cờ ngôn ngữ heuristic và từng trạng thái có trong [comparison.json](../../outputs/task3/sft-v2-public-20261026-run1/public-comparison/comparison.json), `comparison.jsonl`.

Review metadata-only được freeze trước model:36 ID (12/Level, phân tầng exam family khi khả thi), seed `task3-v2-public-review-20261026`. Sau lượt chạy chọn thêm24 ID theo rule đã khóa: ưu tiên đổi empty/nonempty, rồi đổi tập nhãn, cờ ngôn ngữ, feedback>800 ký tự; tie SHA256(seed|ID); loại fixed slice. Không có invalid response thực tế cần review riêng; tám preflight failure được kiểm kỹ thuật riêng. Risk slice không đại diện cho accuracy. Một preflight failure nằm trong fixed36; tổng60 ID fixed+risk và8 technical có1 overlap, **67 ID duy nhất**.

Đã hoàn tất review cả60 ID, đọc full source/đề và120 vị trí output A/B, trong đó119 có phản hồi và1 không được sinh. Người review giữ kín khóa phương pháp, không chạy compiler/runtime/model; mở identity sau khi đã lưu verdict.120 binding SHA của payload (kể cả `null`) khớp. Review này là nhận định có chứng cứ của agent, không phải gold độc lập. [Casebook đã review](../../outputs/task3/sft-v2-public-20261026-run1/semantic-review/reviewed-casebook.html) chứa source, đầy đủ yêu cầu, nguyên phản hồi, verdict và evidence; [casebook toàn328](../../outputs/task3/sft-v2-public-20261026-run1/public-comparison/casebook.html) giữ cả các mẫu ngoài slice.

| Nhận định trong fixed36, không phải accuracy public | V2 | A/R15 |
|---|---:|---:|
| Chẩn đoán supported | 18 | 14 |
| Chẩn đoán unsupported | 15 | 22 |
| Chẩn đoán uncertain / không đánh giá được | 2 / 1 | 0 / 0 |
| Tuân thủ Level pass | 25 | 18 |
| Tiếng Việt pass | 35 | 35 |
| Taxonomy–feedback mâu thuẫn / uncertain | 2 / 3 | 2 / 0 |

Trong12 L3 fixed, V2 có1 hướng sửa pass,8 fail,2 uncertain và1 không áp dụng; A/R15 có3 pass/9 fail. Các chiều được chấm riêng: hint hữu ích không cứu chẩn đoán bịa, JSON hợp lệ không cứu Level leakage. Trong24 risk, V2 supported8/unsupported15/uncertain1; A/R15 supported7/unsupported16/uncertain1. Không gộp risk vào fixed để gọi đó là accuracy; không suy V2 tốt hơn toàn bộ public từ các số này. [summary.json](../../outputs/task3/sft-v2-public-20261026-run1/semantic-review/summary.json) và `review.rows.jsonl` giữ mẫu số/chiều chi tiết.

Một số ví dụ có bằng chứng nguồn:

- **Đúng và hữu ích — Class03-Midterm-2-S14, L3:** source chỉ so các phần tử kề nhau, nên `[1,2,1]` còn hai số1. V2 chỉ đúng điều kiện này và gợi ý kiểm phần tử đã xuất hiện trước đó. A/R15 lại nói thiếu phần tử cuối dù source thêm nó riêng; đề xuất kéo vòng đến `n` gây truy cập vượt biên. Review V2 pass cho chẩn đoán/điều kiện/hint; vẫn ghi riêng giới hạn mảng100 so với yêu cầu `n<=10000`.
- **Trạng thái đúng — Class03-Midterm-1-S34, L1:** `int sum` có thể tràn tại input hợp lệ999999999: `9*9^9=3486784401 > 2147483647`. V2 báo còn lỗi, phù hợp L1; A/R15 nói không có lỗi rõ ràng. Đây là chứng cứ source ở target int32, không phải kết quả runtime mới.
- **Báo oan — Class03-Final-1-S54, L1:** greedy nối ký tự đầu first, thêm các ký tự tiếp theo nhỏ hơn `last[0]`, rồi nối `last[0]` là đúng trong miền lowercase. V2 vẫn báo lỗi; A/R15 taxonomy rỗng nhưng bảo phải tạo tất cả tổ hợp. Cả hai chẩn đoán unsupported, A/R15 còn mâu thuẫn nội bộ và vượt Level.
- **Bỏ sót — Class03-Midterm-2-S26, L1:** logic dò trùng xét cả các ô0 chưa dùng, có thể bỏ mất phần tử0 hợp lệ. V2 trả `[]`/“Bài làm đáp ứng yêu cầu của đề.”; không thể coi taxonomy rỗng là cải thiện. Bằng chứng chỉ rõ trong source ở casebook.
- **Mâu thuẫn V2 — Class01-Test2-S11 và S41, L2:** cả hai trả taxonomy `[]` nhưng lần lượt nói “Hàm prob4 trong đề có lỗi…” và “prob4 bỏ qua một số trường hợp…”. S41 thực tế gom người **đã** tham gia rồi xóa, trái yêu cầu xóa người **không** tham gia; câu nhận xét cũng thiếu điều kiện đảo này. S11 còn có lỗi P1 truy cập vector chưa resize và các vấn đề tree; không được coi chỉ nhắc prob4 là bao phủ đủ. Hai verdict consistency fail được giữ với evidence cụ thể.

Những trường hợp thiếu CSV gốc hoặc cảnh báo non-void return được đánh uncertain khi cần; không đồng nhất warning với compile failure. Reviewer không dựa keyword để chấm ngữ nghĩa và không sửa feedback.

## Chi phí, kiểm chứng và tái lập

320 reservation/completion duy nhất,0 retry/uncertain/correction/verifier. Input515.785 token, output12.158 token. Load model+adapter đo riêng17,725s, bao gồm base6,003s; không cộng hai số này. Generation phase320,628s gồm tất cả lời gọi và persistence; tổng thời gian trong từng call315,016s. Peak CUDA toàn generation phase sau load: allocated9.911.225.856B (**9,231GiB**), reserved11.622.416.384B (**10,824GiB**), reset một lần trước pha, không reset từng mẫu. Đây là CUDA allocator/reserved, không phải NVML toàn hệ thống.326 syntax calls tổng32,991s;252 pass/74 error,0 link/0 runtime chương trình public. [costs.json](../../outputs/task3/sft-v2-public-20261026-run1/costs.json) có mẫu số, scope và hash nguồn tính.

[final-integrity.json](../../outputs/task3/sft-v2-public-20261026-run1/final-integrity.json):4.270 checks,0 fail; token/prompt/ID/Level/adapter/freeze khớp, payload export nguyên giá trị, tám history unresolved đủ. Đã kiểm nguyên hash61 file có trước,2.714 artifact V2,366 artifact V1 và root `predictions.json`. Test liên quan mapping, aggregation, invalid/clean denominator, context, journal, export saved bytes và comparator: **85 passed**. Full-suite collection có hai test Task1 cần `sklearn` chưa có; không cài dependency hoặc sửa ngoài phạm vi. Chi tiết review code ở `code-review/`.

Review độc lập phần comparator kiểm thêm3.677 đối chiếu artifact,0 fail và không có lỗi Critical/Important. Hai ghi nhận Minor về readiness của progress helper với raw rỗng và phân loại placeholder interruption đã được lưu riêng trong `comparison-review.json`; không làm thay đổi kết quả cuối của lượt này (0 interruption,8 preflight đã tách đúng). Mã GPU được freeze giữ nguyên sau khi chạy. GPU thực tế: NVIDIA GeForce RTX5090,32607MiB, driver590.48.01.

Các lệnh và điểm vào nằm ở [hướng dẫn tái lập](../../docs/task3_sft_v2_public.md). Không có phép đo leaderboard mới, chưa có căn cứ khẳng định tốt hơn A/R15; file hiện tại là partial cục bộ, chưa đủ328 để thử submit hợp lệ.
