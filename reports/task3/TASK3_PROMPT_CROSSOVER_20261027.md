# Task3 — prompt crossover dev80, 27/10/2026 (Asia/Saigon)

1. **160 generation mới, 160 output tái sử dụng; đủ320 records.** Chạy mới v2-old và v3-old. Tăng từ80 lên160 vì lịch sử v2-old thiếu chứng cứ môi trường đủ chặt; hai cell P_v3 được tái sử dụng sau audit. Không có retry hoặc reservation không rõ kết quả.
2. **Ma trận được đối sánh kỹ thuật** theo hợp đồng input/runtime/parser/tensor đã đóng băng. Guard8192/32768 chỉ là kiểm tra admission không chạm phép tính; prompt cộng allowance lớn nhất2271 token. Không phát hiện leakage hay input corruption. Không bảo đảm bitwise reproducibility của device microstate chưa đo.
3. **Prompt làm đổi chẩn đoán đáng kể và phụ thuộc adapter.** Với v3, P_old→P_v3: faulty miss gồm invalid51→10/60, chẩn đoán có căn cứ6→24/60, success19→40/80. Với v2: miss30→7/60, chẩn đoán15→20/60, nhưng clean false alarm0→16/20 và success32→20/80.
4. **V3 không cải thiện đồng đều dưới cùng prompt.** P_old: chẩn đoán15→6/60, miss30→51/60, success32→19/80 khi đổi v2→v3. P_v3: chẩn đoán20→24/60 và success20→40/80, clean false alarm16→0/20; đồng thời miss7→10/60 và hướng sửa faultyL3 đúng vẫn2/15. Trong hai so sánh giữ cố định prompt, v3 đều có regression trên ít nhất một trục chẩn đoán quan trọng.
5. **Một bước tiếp theo:** đánh giá các ứng viên trên một bộ dev mới chưa quan sát, gồm các cặp clean/faulty cùng cơ chế lỗi, trước khi chọn prompt/adapter. Giữ quyết định triển khai hiện tại; thí nghiệm tiếp theo chưa được khởi chạy.

Đây là **source-grounded agent review**, không phải human gold độc lập hoặc điểm public. Mỗi cell có80 targets =20 source (5 clean,15 faulty) ×4 Level, thuộc5 family. Cả bốn cell dùng cùng source/gold; không phải320 chương trình độc lập. Dev tổng hợp này đã được quan sát nhiều lần, nên không suy ra tổng quát hóa.

## Ma trận đầy đủ

| Cell | Valid /80 | Clean alarm /20 | Clean invalid /20 | Faulty empty /60 | Faulty invalid /60 | Miss+invalid /60 | Chẩn đoán /60 | L3 đúng /15 | Disclosure /80 | Required /80 | Success /80 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2-old | 70 | 0 | 2 | 22 | 8 | 30 | 15 | 1 | 70 | 53 | 32 |
| v2-v3 | 72 | 16 | 2 | 1 | 6 | 7 | 20 | 2 | 67 | 66 | 20 |
| v3-old | 80 | 0 | 0 | 51 | 0 | 51 | 6 | 2 | 80 | 70 | 19 |
| v3-v3 | 76 | 0 | 1 | 7 | 3 | 10 | 24 | 2 | 76 | 66 | 40 |

| Adapter | P_old: success | P_v3: success |
| --- | --- | --- |
| V2 step240 | 32/80 | 20/80 |
| V3 step480 | 19/80 | 40/80 |

“Chẩn đoán” cần assessment có căn cứ, bao phủ và trung thực, cùng taxonomy không rỗng trên faulty source. “L3 đúng” còn cần hướng sửa đúng. Nonempty taxonomy tự nó không chứng minh chẩn đoán đúng. Success đồng thời cần schema, error presence đúng, assessment, location/condition khi áp dụng, disclosure, required content, tiếng Việt và L3/L4 usefulness/code phù hợp. Invalid luôn ở mẫu số.

| Cell | Clean success /20 (5 nguồn) | Faulty success /60 (15 nguồn) | Taxonomy precision | Recall | F1 (auxiliary) | Mâu thuẫn taxonomy–feedback |
| --- | --- | --- | --- | --- | --- | --- |
| v2-old | 18 | 14 | 0.467 | 0.233 | 0.311 | 0 |
| v2-v3 | 2 | 18 | 0.435 | 0.500 | 0.465 | 0 |
| v3-old | 14 | 5 | 0.889 | 0.133 | 0.232 | 26 |
| v3-v3 | 17 | 23 | 0.580 | 0.483 | 0.527 | 0 |

Taxonomy dùng all-target conservative: invalid faulty góp gold vào FN. P/R/F1 là chỉ số phụ trợ; không chọn winner từ taxonomy, disclosure hoặc tổng success riêng lẻ. V3/P_old có disclosure80/80 nhưng success19/80, cho thấy tuân thủ giới hạn tiết lộ không thay thế tính đúng.

## Bốn so sánh ghép cặp

Hướng là cell trước→sau. Mỗi ô là **win/loss/tie/uncertain**. Assessment xét tính đúng, bao phủ và dữ kiện; invalid ở một vế làm semantic comparison uncertain. Số nhóm uncertain không bị bỏ khỏi80 target.

| So sánh | Assessment /80 | Disclosure /80 | Required /80 | Success /80 | FaultyL3 repair /15 |
| --- | --- | --- | --- | --- | --- |
| v2_prompt: v2-old→v2-v3 | 10/19/37/14 | 0/5/61/14 | 13/3/50/14 | 9/20/37/14 | 2/1/11/1 |
| v3_prompt: v3-old→v3-v3 | 26/4/46/4 | 0/0/76/4 | 7/7/62/4 | 26/4/46/4 | 4/3/8/0 |
| old_adapter: v2-old→v3-old | 3/18/49/10 | 0/0/70/10 | 11/4/55/10 | 3/18/49/10 | 3/1/11/0 |
| v3_adapter: v2-v3→v3-v3 | 23/8/39/10 | 5/0/65/10 | 4/8/58/10 | 22/6/42/10 | 2/1/11/1 |

Các transition **đầy đủ của taxonomy-set, error presence và parser status**, cùng phân rã từng Level/status và từng target, có trong [paired-differences.json](../../outputs/task3/prompt-crossover-20261027-run1/paired-differences.json); bảng transition tổng và mọi trục review có ở [phụ lục đầy đủ](../../outputs/task3/prompt-crossover-20261027-run1/full-generated-report.md). Không đổi cấu hình giữa cell để giải thích kết quả. Dữ liệu cho thấy tương tác prompt–adapter; không có cơ sở kết luận chỉ adapter hoặc chỉ prompt luôn tốt hơn.

## Từng Level và clean/faulty

Mỗi dòng clean có5 targets/5 source; faulty có15 targets/15 source. Mỗi Level có20 targets/20 source. Alarm/miss/diagnosis không áp dụng hiển thị0; L3 repair chỉ áp dụng faultyL3.

| Cell | L | Nhóm | n | Valid | Alarm | Miss+invalid | Diagnosis | L3 đúng | Disclosure | Required | Success |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2-old | 1 | clean | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 5 |
| v2-old | 1 | faulty | 15 | 15 | 0 | 7 | 8 | 0 | 15 | 15 | 8 |
| v2-old | 2 | clean | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 5 |
| v2-old | 2 | faulty | 15 | 15 | 0 | 6 | 4 | 0 | 15 | 5 | 4 |
| v2-old | 3 | clean | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 5 |
| v2-old | 3 | faulty | 15 | 15 | 0 | 6 | 2 | 1 | 15 | 8 | 1 |
| v2-old | 4 | clean | 5 | 3 | 0 | 0 | 0 | 0 | 3 | 3 | 3 |
| v2-old | 4 | faulty | 15 | 7 | 0 | 11 | 1 | 0 | 7 | 7 | 1 |
| v2-v3 | 1 | clean | 5 | 5 | 3 | 0 | 0 | 0 | 5 | 5 | 2 |
| v2-v3 | 1 | faulty | 15 | 15 | 0 | 1 | 13 | 0 | 15 | 15 | 13 |
| v2-v3 | 2 | clean | 5 | 5 | 5 | 0 | 0 | 0 | 3 | 5 | 0 |
| v2-v3 | 2 | faulty | 15 | 14 | 0 | 1 | 2 | 0 | 11 | 11 | 2 |
| v2-v3 | 3 | clean | 5 | 5 | 5 | 0 | 0 | 0 | 5 | 5 | 0 |
| v2-v3 | 3 | faulty | 15 | 14 | 0 | 1 | 4 | 2 | 14 | 11 | 2 |
| v2-v3 | 4 | clean | 5 | 3 | 3 | 0 | 0 | 0 | 3 | 3 | 0 |
| v2-v3 | 4 | faulty | 15 | 11 | 0 | 4 | 1 | 0 | 11 | 11 | 1 |
| v3-old | 1 | clean | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 5 |
| v3-old | 1 | faulty | 15 | 15 | 0 | 14 | 1 | 0 | 15 | 15 | 1 |
| v3-old | 2 | clean | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 3 |
| v3-old | 2 | faulty | 15 | 15 | 0 | 14 | 1 | 0 | 15 | 14 | 1 |
| v3-old | 3 | clean | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 2 |
| v3-old | 3 | faulty | 15 | 15 | 0 | 9 | 3 | 2 | 15 | 6 | 2 |
| v3-old | 4 | clean | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 4 |
| v3-old | 4 | faulty | 15 | 15 | 0 | 14 | 1 | 0 | 15 | 15 | 1 |
| v3-v3 | 1 | clean | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 5 |
| v3-v3 | 1 | faulty | 15 | 15 | 0 | 2 | 13 | 0 | 15 | 15 | 13 |
| v3-v3 | 2 | clean | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 5 |
| v3-v3 | 2 | faulty | 15 | 15 | 0 | 2 | 5 | 0 | 15 | 8 | 5 |
| v3-v3 | 3 | clean | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 5 | 4 |
| v3-v3 | 3 | faulty | 15 | 15 | 0 | 2 | 3 | 2 | 15 | 12 | 2 |
| v3-v3 | 4 | clean | 5 | 4 | 0 | 0 | 0 | 0 | 4 | 4 | 3 |
| v3-v3 | 4 | faulty | 15 | 12 | 0 | 4 | 3 | 0 | 12 | 12 | 3 |

## Runtime, prompt và review

Selection đã niêm phong xác định v2 step240 và v3 step480; file và392 tensor LoRA được so hash với adapter thực sự nạp. Base Qwen2.5-Coder-7B-Instruct revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`; RTX5090/driver590.48.01; torch2.8.0+cu128, transformers4.57.1, peft0.17.1, bitsandbytes0.48.1. Native preparation, NF4 double, BF16 compute/uint8 storage, LoRA FP32, SDPA, eval và một adapter active được kiểm tra trước mỗi cell mới. Constructor và flag ở196 Linear4bit chứng minh explicit BF16 khóa nhánh tự đổi compute dtype. Chỉ profile trước cell được đo trực tiếp; không gắn hook activation/first-forward hoặc đo profile cuối cell. Các phép đo đó được đề xuất trong addendum, chưa thực hiện; không coi chúng là bằng chứng đã quan sát. Profile trước v3-old gián tiếp xác nhận state sau v2-old. Xem [phạm vi quan sát runtime](../../outputs/task3/prompt-crossover-20261027-run1/audit/runtime-observation-scope.json).

Greedy, concurrency1, seed42;1024 token L1–3,1536 token L4; max_time45s; repetition_penalty kế thừa1.1 vẫn có hiệu lực, EOS151645/pad151643; không truncate/compress input. Guard32768 không sửa RoPE/cache/model computation. P_old có502–696 token (tổng46308); P_v3 có541–735 (tổng49428), tăng39/target. Đề/source/log/submission mode và user message khớp80/80. P_old giữ giới hạn L2 một câu và yêu cầu full code L4; P_v3 bỏ hai yêu cầu này và thêm faithful diagnosis/clean/conditions. Không chỉnh prompt trước đo.

Audit ngắn: [reuse-audit.md](../../outputs/task3/prompt-crossover-20261027-run1/reuse-audit.md); [audit máy đọc](../../outputs/task3/prompt-crossover-20261027-run1/reuse-audit.json); [prompt audit](../../outputs/task3/prompt-crossover-20261027-run1/audit/prompt-audit.md); [diff nguyên vẹn](../../outputs/task3/prompt-crossover-20261027-run1/prompts/system-prompt.diff); [cấu hình và hash đóng băng](../../outputs/task3/prompt-crossover-20261027-run1/manifest.json). Fresh v2-old khớp raw lịch sử80/80 trong kiểm tra phụ; vẫn tính80 calls mới. Một preflight dừng trước inference do guard symlink; manifest/log thất bại được giữ riêng.

Ba reviewer tách biệt đọc code/spec và từng response trong282 panel mù danh tính, rồi mở rộng đủ320 verdict. Disclosure chỉ xét giới hạn; required content L2/L3 xét loại nội dung; correctness chấm riêng. False praise có thể pass disclosure nhưng fail diagnosis/success. L2 nhiều câu hợp lệ; L4 thiếu code không tự fail. Mâu thuẫn empty taxonomy/bug feedback được ghi tường minh, không tính chẩn đoán hoàn chỉnh. Mọi raw invalid, verdict, code resolution và bằng chứng đều có trong [casebook80×4](../../outputs/task3/prompt-crossover-20261027-run1/paired-casebook.html). Historical semantic verdict không bị sửa.

## Chi phí và kiểm tra

| Cell | Nguồn chi phí | Calls | Invalid | Input tokens | Output tokens | Generation s | Peak allocated GiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v2-old | mới | 80 | 10 | 46308 | 6447 | 142.916 | 8.481 |
| v2-v3 | lịch sử, tái sử dụng | 80 | 8 | 49428 | 5254 | 145.615 | không đo ở pha mới |
| v3-old | mới | 80 | 0 | 46308 | 4165 | 93.548 | 8.476 |
| v3-v3 | lịch sử, tái sử dụng | 80 | 4 | 49428 | 6685 | 153.436 | không đo ở pha mới |

Chi phí generation mới:160 calls, gồm10 invalid và0 uncertain; 92616 input token, 10612 output token, 236.464s. Peak allocated 8.481GiB, reserved 10.828GiB; gồm model resident, đo trong pha inference, lấy max và không cộng hai cell. Hai cell reused có160 calls lịch sử/12 invalid/299.051s; không tính vào calls mới. Không có đơn giá hoặc telemetry chi phí review agent để suy ra tiền.

Feedback-code audit có15 compile và124 runtime mới; tái sử dụng160 evidence đã bind chính xác raw/case hash. Snippet extractor bỏ sót được review ngữ nghĩa riêng. Regression cuối: **2031 passed,15 skipped,12.85s**;39 tests tập trung crossover đã qua. Full repository suite dừng collection vì thiếu sklearn ở hai module Task1, không coi là suite xanh và không cài thêm dependency. Bộ đếm độc lập xác nhận mọi objective count và taxonomy P/R/F1. Strict parser recomputed320/320; journal160 reservations=160 completions,0 unknown. Bảo toàn85.460 file trước task, HEAD/branch và root predictions hash đã qua.

Không training, public inference/export, submit/upload, thay checkpoint selection hoặc git mutation. Kiểm tra và lệnh chính xác ở [reproduction.md](../../outputs/task3/prompt-crossover-20261027-run1/reproduction.md). Báo cáo ví dụ ngắn: [TASK3_PROMPT_CROSSOVER_EXAMPLES_20261027.md](TASK3_PROMPT_CROSSOVER_EXAMPLES_20261027.md).
