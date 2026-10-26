# Task3 V2 context32768 — bàn giao

Candidate: [predictions.json](../submission-candidates/sft-v2-context32768/predictions.json),328/328,82623byte; SHA256 `fc4b7ac7d7e737f7b36f464dff2df7240d7833dbb8d78332745099f2a80974bf`. Đã xuất cục bộ, chưa submit. [Báo cáo](../reports/task3/TASK3_SFT_V2_PUBLIC_CONTEXT32768_20261026.md).

Run: `outputs/task3/sft-v2-public-context32768-20261026-run1`. Freeze/model/tokenizer/adapter/config và token parity được kiểm trước328 primary mới, longest-first. Không thay bất cứ file module/lượt8192 lịch sử nào. Context32768 là guard mới phù hợp model/tokenizer pinned; model/RoPE/SDPA/quantization không đổi.

Kiểm offline từ repo hiện tại:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_context32768.py verify
PYTHONDONTWRITEBYTECODE=1 /workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_context32768_verify.py
```

Kiểm checksum toàn run:

```bash
cd outputs/task3/sft-v2-public-context32768-20261026-run1
sha256sum --check artifact-sha256.txt
```

Resume an toàn trên chính run này:

```bash
/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_sft_v2_context32768.py infer
```

Lệnh bỏ qua completed và không replay uncertain reservation. Trên run hoàn tất không load model. Không gọi lại hoặc đổi settings khi parse fail/OOM. Fresh method/freeze identity được kiểm từ journal, không nhận320 output cũ dù prompt giống nhau. Giữ nguyên longest primary đầu tiên, official ordering cho export.

Test tái lập liên quan:

```bash
/workspace/llm-final-project/.venv-task3/bin/python -m pytest -q tests/test_task3_sft_v2_public_context.py tests/test_task3_sft_v2_context32768_report.py tests/test_task3_sft_v2_public.py tests/test_task3_sft_v2_public_runtime.py tests/test_task3_sft_v2_public_compare.py tests/test_task3_sft_v2_posthoc.py tests/test_task3_sft_v2_report.py tests/test_task3_sft_v1_evaluation.py tests/test_task3_submission.py
```

Các phase đã thực hiện: `scripts/task3_sft_v2_context32768.py prepare`, `verify`, `infer`, `export`, rồi `scripts/task3_sft_v2_context32768_report.py`. Các lệnh tạo output từ chối ghi đè. Chạy inference mới cần được giao riêng, dùng thư mục/identity mới và snapshot đúng trạng thái; không dùng resume để thử lại hoặc thay đổi prompt. Toàn bộ request, code/input/config hashes và commands được giữ ở run. Báo cáo/raw full tám mẫu tại `analysis/`, review riêng tại `eight-review/`; chỉ59 review cũ đủ binding byte/source để chuyển.
