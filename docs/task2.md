# Task 2 — Phân loại lỗi đa nhãn

Spec: `docs/superpowers/specs/2026-10-09-task2-design.md` · Plan: `docs/superpowers/plans/2026-10-09-task2.md`

## Dữ liệu
- Giải nén: `python scripts/unpack_data.py data/public-test --dest data/raw` → `data/raw/public_test_release` (360 bài,
  không nhãn, không compile_log/test_report) và `data/raw/sample_dataset` (32 bài có nhãn, đề EX01/EX02).
- Nhãn: gold 32 bài (split 26/6 trong `data/splits/`) để đánh giá và chọn ngưỡng; silver = Hướng 1 gán nhãn 360 bài
  public (n=5, P = tỉ lệ phiếu) để train Hướng 2; leaderboard chỉ để chọn cấu hình cuối.
- Không dùng `feedback`. Không đưa compile_log/test_report vào input (public test không có).

## Hướng 1 — API
```bash
python scripts/run_task2_api.py --preflight                 # không gọi API
python scripts/run_task2_api.py --provider gemini --smoke    # 1 bài
python scripts/run_task2_api.py --provider gemini           # zero-shot + few-shot trên 6 bài gold val
```
Gán nhãn silver: đặt `run.predict: true` trong `configs/task2/run_api.yaml` → `outputs/task2/task2_api_silver__*/`
gồm `predictions.json` (nộp được) và `silver_labels.json`. Chi phí: `usage.jsonl`, `resources.json`.

## Hướng 2 — CLM-8B
CLM-8B = Qwen3-8B frozen (last-token pooling) + state/action head. Mỗi nhãn là một câu hỏi có/không (`noul`):
P(nhãn) = sigmoid(scale · (cos(state, "true: …") − cos(state, "false: …"))). Hệ thống:
`clm_zero_shot` (head gốc), `clm_noul` (fine-tune head, BCE có trọng số), `probe` (logistic regression trên
embedding context — ablation). Ngưỡng riêng từng nhãn + sàn tỉ lệ dự đoán 2%.

- Local (Mac, MLX 4-bit, tối thiểu): `python scripts/run_task2_clm.py --config configs/task2/clm_local.yaml`
- Kaggle (T4×2, đầy đủ): `kaggle/task2_clm.ipynb` (cần Secret `PUBLIC_TEST_DRIVE_ID`).
- Benchmark: `python scripts/task2_benchmark.py` → `outputs/task2/benchmark.md`.

Head chỉ hợp lệ với encoder đã sinh embedding: bản MLX 4-bit và bản HF fp16 phải train head riêng; số đo hai môi trường
không so trực tiếp.

## Kết quả local (Mac M3 Pro 18GB, 6 bài gold val — chỉ kiểm tra pipeline)

| Run | Hệ thống | Phần cứng | n val | macro-F1 | micro-F1 | giây/bài | train (s) | bộ nhớ đỉnh (GB) | token vào | token ra | USD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| task2_clm_local | clm_zero_shot@0.5 | Apple M3 Pro 18GB | 6 | 0.029 | 0.077 | 40.74 | 3.48 | 5.28 | — | — | 0.0000 |
| task2_clm_local | clm_zero_shot@tuned | Apple M3 Pro 18GB | 6 | 0.176 | 0.293 | 40.74 | 3.48 | 5.28 | — | — | 0.0000 |
| task2_clm_local | clm_noul@0.5 | Apple M3 Pro 18GB | 6 | 0.040 | 0.143 | 40.74 | 3.48 | 5.28 | — | — | 0.0000 |
| task2_clm_local | clm_noul@tuned | Apple M3 Pro 18GB | 6 | 0.197 | 0.400 | 40.74 | 3.48 | 5.28 | — | — | 0.0000 |
| task2_clm_local | probe@0.5 | Apple M3 Pro 18GB | 6 | 0.107 | 0.125 | 40.74 | 3.48 | 5.28 | — | — | 0.0000 |
| task2_clm_local | probe@tuned | Apple M3 Pro 18GB | 6 | 0.195 | 0.244 | 40.74 | 3.48 | 5.28 | — | — | 0.0000 |

- Thời gian chạy đầy đủ: 26 phút 07 giây (lần đầu, không cache).
- 438 lần encode (38 bài × 11 + 20 candidate) ≈ 40.7 giây/bài; train head 3.5 giây.
- Bộ nhớ đỉnh 5.28 GB. Tải model MLX 4-bit 4.5 GB, nạp 9 giây.
- Cảnh báo khi đọc bảng:
  - Chỉ 6 bài gold val, khác đề thi → số rất nhiễu.
  - Ngưỡng "tuned" và epoch tốt nhất đều chọn trên chính 6 bài này → số `@tuned` lạc quan.
  - Local chỉ train trên 26 bài gold (chưa có silver) nên fine-tune gần như chưa thay đổi head.
  - Với ngưỡng chọn từ 6 bài, hệ thống gán "Lỗi biên dịch" cho cả 6 bài public thử. Cần silver + Kaggle để có ngưỡng đáng tin.
- Đã kiểm tra: toàn bộ 4312 state text (gold + public) ≤ 2041 token với tokenizer Qwen3, câu hỏi không bị cắt.

## Rủi ro / hạn chế
- 6 bài val, khác đề thi: số đo rất nhiễu. `Lỗi edge case` không có ví dụ dương trong gold.
- Silver mang sai lệch của model API. Cần giảng viên xác nhận việc dùng nhãn tự động trên tập public để train.
- MLX 4-bit là bản chuyển đổi không chính thức (~91% đồng thuận top-1 với bản gốc).
- Macro-F1 chính theo quy ước sklearn (nhãn vắng = 0); báo cáo thêm `macro_f1_skip_absent`.
