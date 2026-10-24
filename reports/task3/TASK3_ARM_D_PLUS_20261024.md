# Task 3 D+ — 24/10/2026

Đã IMPLEMENT + TEST và chạy đủ **328/328** public sample; chỉ **326/328 có output**, còn **2 unresolved do JSON sai cú pháp sau corrective retry**. **Chưa có bản nộp hoàn chỉnh.** Full validator FAIL vì thiếu2 ID; không tạo `predictions.json`. `partial.predictions.json` là checkpoint, không đủ để nộp. Không tự sửa escape, điền nhãn/feedback thay thế hoặc gọi vượt giới hạn retry.

Branch `task3/arm-d-plus`; source commit `6cbce043f3046f7876753da6c86def93723c5b90`; phương pháp `arm-d-plus-v1.3`. Qwen/Qwen2.5-Coder-7B-Instruct revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, BF16 thật trên cuda:0, không quantization/adapter/offload, seed42/greedy. Chỉ dẫn Anh; official labels/Level giữ tiếng Việt và yêu cầu feedback Việt.

Tách parse→mapping→validate→union→renderer; hỗ trợ labels đa nhãn và adapter label cũ. Exact/Unicode/whitespace/alias không gọi model; nhãn lạ được chọn bằng logits trên10 mã A–J của tokenizer thật, cùng model BF16. Không default Logic, không sửa nội dung finding. Bảo toàn statement/code/ngôn ngữ/constraints/io_mode/prototype/policy/ghi chú compiler và compile_log/test_report qua loader tới prompt. Log rỗng là unavailable, test thiếu là not_run. Compile log đầy đủ chỉ đưa một lần. Dùng native context32768 vì input thực đo vượt16384; max detector19444+allowance1536=20980, output caps1536/1024 và timeout45s giữ nguyên. Quote là locator, có thể rỗng cho omission; 10 findings thiếu quote được ghi riêng, không coi là verified.

| Public v1.3 | Kết quả |
|---|---:|
| Processed / output / unresolved | 328 / 326 / 2 |
| Unresolved enum / infrastructure | 0 / 0 |
| Exact / normalized / alias / constrained-choice label entries | 776 / 0 / 0 / 1 |
| Normal / corrective / resolver calls | 654 / 3 / 1 |
| Resolver forward passes | 1 |
| Input / generated output / selected decision tokens | 1.495.822 / 89.238 / 1 |
| Tổng token đã hạch toán | 1.585.061 |
| Model-call latency / wall time | 1.228,747s / 1.239,708s |
| Resolver latency | 0.097s |
| Peak allocated / reserved VRAM | 17,820 / 18,404 GiB |

294 tests Task3 liên quan pass, không tuyên bố toàn repository xanh. Regression bao phủ normalization, content-based resolver/ties, không mất finding, multi-label/empty findings, loader→rendered input, timeout/EOS, retry/resume identity, validator/export và quote omission. Audit kiểm tra658 journal calls, binding/raw nguyên vẹn, code/finding fields không đổi, feedback export nguyên văn;374 artifact lịch sử giữ nguyên hash.326 output có dấu Việt và không rỗng;1 output có CJK marker, chỉ là diagnostic Unicode, chưa đánh giá ngôn ngữ/ngữ nghĩa thủ công.

Nội bộ30 ID chỉ chạy một lần:30/30 complete;60 calls,58 exact labels,0 retry/resolver. Micro/macro-F1 .315789/.189020 so với D lịch sử .442308/.284108; exact2/30 ở cả hai, gold không đổi. D+ thấp hơn D về taxonomy F1. Sau fix input/schema, đối chiếu đủ60 actual prompts và settings model/generation không đổi, không chạy lại nội bộ. Factuality, unsupported diagnosis, Level và placeholder của output D+ mới chưa có review tương thích. Enum/schema hợp lệ không chứng minh chẩn đoán đúng.

Hai run v1.1/v1.2 đã dừng chỉ trên process do phiên này khởi động để sửa lỗi implementation; giữ822 calls đã ghi và2 reservation bị ngắt, không reuse output trong v1.3. Toàn phiên đã ghi 2,946,985 input tokens gồm input của call bị ngắt, 189,156 output tokens và 2577.901s call latency. Output/latency của hai call bị ngắt chưa đo được; không gọi đó là tổng chính xác. Chi phí từng run tách trong run-summary.json/session_costs.

Tài liệu Word binary không có trong workspace/archive; đã đọc bản `DoAn-LLM-Challenge.docx.md`. Tài liệu mô tả Task3 nhận nhãn cho sẵn, public release thực tế không có nhãn input và yêu cầu taxonomy_error+feedback; đã theo public contract. Operational definitions không phải gold taxonomy mới. Không đổi gold, không lấy Task2/lịch sử để điền public, không review rồi chọn lại public outputs. Không push dữ liệu hoặc nộp leaderboard.

Artifact riêng tư: `outputs/task3/public-arm-d-plus-v1.3-20261024/`. Partial, validation FAIL, config.resolved, raw attempts/rendered/resolver, normalized-findings, mapping audit, failure IDs/raw keys và chi phí đều có trong bundle. Main ZIP mang tên **partial**, audit ZIP riêng tư. Codex hỗ trợ implementation/test/audit; Qwen BF16 chạy inference.

Lệnh chạy lại (đã kiểm tra đầy đủ preflight khi thêm `--verify-only`, không chạy model thêm chỉ để test lệnh):

```bash
/workspace/llm-final-project/.venv-task3/bin/python /workspace/llm-final-project-arm-d-plus/scripts/task3_arm_d_plus.py --phase public --out /workspace/llm-final-project-arm-d-plus/outputs/task3/public-arm-d-plus-v1.3-20261024-reproduce --public-root /workspace/llm-final-project/data/raw/public_test_release --internal-root /workspace/llm-final-project/data/synth/generate-dataset --history /workspace/llm-final-project-ablation/outputs/task3/language-precision-ablation-20261024 --method-freeze /workspace/llm-final-project-arm-d-plus/outputs/task3/arm-d-plus-v1.3-lock/method-freeze.json
```

Lệnh resume (đã kiểm tra identity/input/freeze bằng preflight; giữ nguyên giới hạn retry, không cấp thêm attempt cho2 failure đã exhausted):

```bash
/workspace/llm-final-project/.venv-task3/bin/python /workspace/llm-final-project-arm-d-plus/scripts/task3_arm_d_plus.py --phase public --out /workspace/llm-final-project-arm-d-plus/outputs/task3/public-arm-d-plus-v1.3-20261024 --public-root /workspace/llm-final-project/data/raw/public_test_release --internal-root /workspace/llm-final-project/data/synth/generate-dataset --history /workspace/llm-final-project-ablation/outputs/task3/language-precision-ablation-20261024 --method-freeze /workspace/llm-final-project-arm-d-plus/outputs/task3/arm-d-plus-v1.3-lock/method-freeze.json --resume
```
