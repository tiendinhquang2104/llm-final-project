# Task 2 CoT bundle: task2_cot_sc__mlx__mlx-community-Qwen2.5-Coder-7B-Instruct-4bit

Không có trọng số được train: "model" = backbone `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` (revision `019cc73c45c770444708a6dd8690c66243cc5c80`)
+ prompt giảng viên (`prompt_system.txt`, `prompt_instruction.txt`) + cấu hình sinh trong `bundle.json`.
Trọng số kèm theo: không (tải lại theo model id + revision).

Điểm trên gold lúc export (chỉ một phần bài: kiểm tra pipeline, không phải điểm chính thức): macro-F1 = 0.0, micro-F1 = 0.0, n = 1.

Không dùng few-shot.

## Chạy lại

```bash
python scripts/predict_task2_cot.py --bundle <thư mục bundle> --data-root <thư mục có exams.json + task2_error_taxonomy.json>
```

- `--backend hf|mlx` để đổi backend (mặc định: `mlx`).
- Kết quả: `predictions.json` (định dạng nộp bài), `predictions_full.json`, `debug.jsonl`, `report.html`, `run.log`.
- Prompt lấy từ code của repo (git `dd1f83ea0a`); script cảnh báo nếu prompt trong code khác
  `prompt_sha256` của bundle.
