# Task 2 CoT bundles

Một bundle = mọi thứ cần để tái lập một cấu hình prompting Task 2 (không có trọng số được train):
`bundle.json` (model id + revision cố định, prompt/generation/demo config, công thức compile, git commit,
`prompt_sha256`, hash của demo pool gold/silver, điểm gold lúc export), `prompt_system.txt`,
`prompt_instruction.txt`, `demos.json` (demo đã dùng cho từng bài, cấu hình few-shot) và `model/` nếu export với
`--save-weights`.

## Tái lập bằng một lệnh

```bash
python scripts/predict_task2_cot.py
```

Dùng bundle ghi ở dòng đầu của `BEST`, dự đoán 360 bài public, tự chọn backend (MLX trên Mac Apple Silicon, HF
transformers trên GPU), tải model theo revision cố định, ghi `outputs/task2/predict_cot/<bundle>/predictions.json`
cùng `report.html`, `run.log`. Cần: compiler (Docker trên Mac / g++ trên Linux) cho quy tắc `Lỗi biên dịch`, và
`SILVER_DRIVE_ID` (trong `.env` hoặc biến môi trường) cho bundle few-shot. Script cảnh báo khi prompt trong code,
demo pool hoặc compiler khác lúc export.

Chọn bundle khác: `--bundle cot_zero_shot` (tên thư mục ở đây) hoặc `--bundle <đường dẫn>`; chấm một tập có nhãn:
`--data-root data/raw/sample_dataset`.

## Các bundle

| Thư mục | Cấu hình | Nguồn |
|---|---|---|
| `cot_zero_shot` | prompt giảng viên, greedy | export local (Mac, MLX), 1 bài: kiểm tra pipeline |
| `cot_fewshot` | + 3 demo gold/silver | như trên |
| `cot_self_consistency` | zero-shot + 5 lời chấm, bỏ phiếu | như trên |
| `cot_fewshot_sc` | few-shot + 5 lời chấm, bỏ phiếu | như trên |

Bundle export local chỉ chấm 1 bài (`gold_metrics.partial = true`): chúng ghi đúng cấu hình để tái lập, không
phải điểm chính thức.

## Cập nhật sau lượt Kaggle

1. Tải `/kaggle/working/task2_cot_bundle` (notebook `kaggle/task2_cot.ipynb`) hoặc `task2_cot_sc_bundle`
   (`kaggle/task2_cot_sc.ipynb`) về, chép vào đây với tên cấu hình, ví dụ `bundles/task2_cot/cot_fewshot_sc/`
   (thay bản local). Bundle Kaggle có điểm 32 gold đầy đủ và backend `hf`.
2. So `gold_metrics.macro_f1` các bundle (đều trên 32 gold, cùng tập bài) và ghi tên bundle tốt nhất vào dòng đầu
   của `BEST`. Chỉ chọn theo gold (hoặc silver), không theo kết quả public.
3. Không commit thư mục `model/` (khoảng 15 GB) nếu bundle có kèm trọng số.
