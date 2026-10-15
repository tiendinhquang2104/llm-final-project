# Task 1 — Hướng 2: fine-tune QLoRA (adapter riêng của Task 1)

Model nền: [`Qwen/Qwen2.5-Coder-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) (Apache-2.0, 7.6B).
Mỗi task có **một adapter LoRA riêng**. Tài liệu này mô tả adapter của Task 1: chấm rubric 6 chiều + `total_score`.

## Thiết kế

| Bước | File | Nội dung |
|---|---|---|
| Gold | `scripts/prepare_data.py` → `task1_{train,val}.jsonl` | 32 bài giảng viên chấm, split cố định 26/6 (`data/splits/`) |
| Silver | `scripts/prepare_task1_silver.py`, `src/task1/silver_data.py` | 462 bài tổng hợp (`generate-dataset.zip`). Loại bài trùng code, mâu thuẫn với `exec_report`, trùng gold/public → **422 bài**. `heldout/` và các ID chỉ có ở Task 3 không bao giờ được đọc. `exec_report` chỉ dùng để kiểm tra chất lượng, không vào prompt |
| Prompt | `src/data/prompts.py` (`build_task1_prompt`) | Cùng một prompt cho train, đánh giá và dự đoán: đề + code + compile log + test report; **không có `feedback`** |
| Train | `scripts/train_task1.py`, `configs/task1/lora_7b.yaml` | QLoRA 4-bit NF4, r 16 / alpha 32, lr 1e-4, loss chỉ tính trên phần JSON trả lời. Hai nhánh cùng seed: **gold-only** (3 epoch trên 26 gold) và **silver → gold** (1 epoch silver, lr 5e-5, rồi 3 epoch gold) |
| Chọn adapter | `src/task1/finetune.py` | Mỗi epoch gold được đánh giá trên **6 bài gold validation** (QWK, rồi MAE). Chọn epoch tốt nhất của mỗi nhánh, rồi chọn nhánh tốt hơn; hòa thì giữ gold-only → `best_adapter/` |
| Dự đoán | `scripts/predict_task1_finetuned.py` | `best_adapter` + greedy decoding trên 360 bài public. Checkpoint theo batch nên chạy lại sẽ tiếp tục từ chỗ dở. Kiểm tra định dạng trước khi ghi `task1_predictions.json` |

**Đầu ra của model** là `{"rubric": {...}, "total_score": n}`. `total_score` luôn được tính lại bằng tổng 6 chiều.
Bài nào model trả JSON hỏng thì nhận điểm trung vị rubric của các bài gold cùng dạng đề, có đánh dấu
`fallback_used`. Số bài bị fallback được ghi trong `run_info.json`.

**Rule câu tiên quyết (giống hướng API).** Với đề nhiều câu, adapter trả thêm trạng thái từng câu:
`{"problems":[{"pid":"P1","status":"wrong"},...],"rubric":{...},"total_score":n}`. Code áp chính sách đề bằng
`apply_rules`: P1 sai thì P2–P4 không được chấm, và áp compile gate. Áp dụng cả khi chọn adapter trên gold validation
lẫn khi dự đoán public. `metrics.before_rules` và `--no-rules` cho số liệu khi không áp rule (ablation).

Nhãn trạng thái để train lấy từ silver. `generate-dataset.zip` thiếu `provenance.jsonl` của tập train, nên
`scripts/derive_task1_silver_status.py` **chạy lại đúng harness của bộ sinh** (`src/synth/`, lấy từ nhánh
`task-1-synth`) trên code của từng bài silver nhiều câu, lấy trạng thái P1–P4 khi chạy thật. Script chỉ giữ trạng
thái khi rubric suy ra từ đó **trùng nhãn đã lưu**, và dừng hẳn nếu dưới 90% bài khớp. Bước này cần `g++` (Kaggle có
sẵn). Gold không có nhãn trạng thái, nên đáp án gold chỉ có rubric. `--no-status` (script một lệnh) quay về phiên
bản chỉ có rubric.

## Chạy bằng một lệnh

Trên máy có GPU CUDA (Kaggle, Colab, máy local có VRAM ≥ 16 GB khi train, ≥ 8 GB khi chỉ dự đoán):

```bash
bash run.sh --task1-finetune --gold-root <sample_dataset> --public-root <public_test_release> \
     --silver-root <generate-dataset> --work-dir <thư mục mới> [--smoke] [--preflight]
```

Lệnh này chạy lần lượt các bước sau (`scripts/run_task1_finetune.py`):
1. tạo gold ChatML và kiểm tra split 26/6 khớp `data/splits/`;
2. lọc silver;
3. preflight (độ dài token, chống rò rỉ);
4. train 2 phương án và chọn adapter;
5. viết `error_analysis.md`;
6. dự đoán tập release thành `task1_predictions.json`.

`--preflight` chỉ kiểm tra dữ liệu, không cần GPU. `--smoke` chạy 1 bước mỗi giai đoạn và dự đoán 1 bài mỗi đề.

So sánh điểm với hướng API trên cùng 6 bài gold validation:

```bash
bash run.sh --task1-compare --api-runs outputs/task1 --finetune <work-dir>/qlora/training_summary.json
```

## Chạy trên Kaggle (`kaggle/task1_finetune.ipynb`)

### 1. Chuẩn bị (một lần)
1. **Code:** notebook clone branch `task-1` từ GitHub, nên phải **push code mới nhất lên branch đó** trước khi chạy.
2. **Tài khoản Kaggle** đã xác minh số điện thoại (bắt buộc để bật GPU và Internet).
3. **Dữ liệu:** repo đang public, nên notebook **không chứa ID file Drive** (theo quy định không phát tán dữ liệu). Chọn
   một trong hai cách:
   - **Kaggle Dataset private (khuyến nghị):** Kaggle → Datasets → New Dataset → tải lên
     `public-test-cham-diem-phan-hoi-files.zip` và `generate-dataset.zip`, đặt **Private**. Notebook tự tìm theo tên file.
   - **Kaggle Secrets:** trong notebook, Add-ons → Secrets, thêm `TASK1_GOLD_PUBLIC_ZIP_ID` và `TASK1_SILVER_ZIP_ID`
     (ID file trên Drive; file phải có quyền xem qua link). Notebook tải bằng `gdown`.

### 2. Tạo notebook
1. Kaggle → **Code → New Notebook → File → Import Notebook** → chọn `kaggle/task1_finetune.ipynb`.
2. Panel **Settings:** Accelerator **GPU T4 x2**, **Internet On**. Nếu dùng dataset riêng: **Add Input → Datasets**.

### 3. Chạy thử (`MODE = 'smoke'`, mặc định)
**Run All**, khoảng 15–25 phút (phần lớn là tải model khoảng 15 GB). Trong output phải thấy:
- dữ liệu: gold 26/6 và silver 422/462;
- preflight: `max_gold_tokens`, `max_silver_tokens`, `max_val_prompt_tokens` đều nhỏ hơn 4096;
- smoke: train xong, có `error_analysis.md`, và dự đoán 6 bài public in ra `submission -> ...`.

### 4. Chạy đầy đủ (`MODE = 'full'`)
Đổi `MODE = 'full'` → **Save Version → Save & Run All**. Notebook chạy nền, có thể đóng tab. Ước tính trên 1 T4
(cần đo lại):

| Giai đoạn | Thời gian |
|---|---|
| Train gold-only (3 × 26) + silver (422) + gold sau silver (3 × 26) | ~1,5–3 giờ |
| Đánh giá 6 epoch × 6 bài val | ~15–30 phút |
| Dự đoán 360 bài public (batch 4) | ~40–90 phút |

Toàn bộ khoảng 3–5 giờ, nằm trong giới hạn 12 giờ mỗi phiên. Quota GPU của Kaggle là khoảng 30 giờ mỗi tuần.

### 5. Lấy kết quả
Version → tab **Output** → `task1_qlora/full/`:

| File | Dùng để |
|---|---|
| `best_adapter/` | **Adapter Task 1** (khoảng 160 MB) + tokenizer. Tải về `checkpoints/task1_qlora/best_adapter/` (git bỏ qua `checkpoints/*`) hoặc lưu thành Kaggle Dataset private |
| `training_summary.json` | Nhánh và epoch được chọn, QWK/MAE của cả hai nhánh, phiên bản thư viện |
| `error_analysis.md` | Bài lệch ≥ 2 điểm hoặc trả JSON hỏng, kèm các chiều chấm sai: dùng cho phần phân tích lỗi |
| `gold_only/`, `silver_then_gold/` | `validation_report.json`, `epoch_*/metrics.json`: dùng cho bảng ablation |
| `public_predictions/task1_predictions.json` | **File nộp** 360 bài, đã kiểm tra định dạng |
| `public_predictions/run_info.json` | GPU, VRAM, thời gian, số token, số bài fallback: dùng cho phần phần cứng và chi phí |

Điền các số này vào [`docs/task1_model_card.md`](task1_model_card.md).

### Dự đoán lại bằng adapter đã có (không train lại)

```bash
python scripts/predict_task1_finetuned.py --adapter checkpoints/task1_qlora/best_adapter \
  --public-root <release> --processed-dir <gold_processed> --splits-dir <gold_splits> --output-dir <out> --preflight
```

Bỏ `--preflight` để chạy. Với tập private test, đổi `--public-root`.

## Xử lý sự cố
- **`git clone` lỗi hoặc thiếu `run_task1_finetune.py`:** branch `task-1` trên GitHub chưa có code mới; push rồi chạy lại.
- **`Thiếu ...zip`:** chưa gắn Kaggle Dataset và chưa đặt Secret.
- **`CUDA out of memory`:** giảm `lora_r` xuống 8 trong `configs/task1/lora_7b.yaml`. Khi dự đoán, dùng `--batch-size 1`.
- **Assert số silver sai:** `generate-dataset.zip` đã đổi phiên bản. Kiểm tra `silver_manifest.json`.
- **Phiên bị dừng:** `/kaggle/tmp` không còn, nên chạy lại notebook. Mỗi lần chạy tạo thư mục mới, không ghi đè.

## Hạn chế (ghi vào báo cáo)
- **Chọn adapter trên 6 bài gold val** nên rất nhiễu. Chênh lệch QWK nhỏ giữa hai nhánh có thể không có ý nghĩa.
- **Silver là nhãn tổng hợp,** chấm theo rulebook. Đề tổng hợp có trọng số 2,5 điểm mỗi câu, còn đề thật là 1/4/2/3.
- **Tín hiệu đầu vào không đồng đều:** gold có `compile_log`/`test_report` của ban tổ chức, còn silver và public thì không.
- **Trạng thái P1–P4 chỉ học từ silver:** chính sách 2,5 điểm mỗi câu và kết quả chạy harness tự động. Gold không có
  nhãn trạng thái. Model báo sai P1 thì rule áp sai theo.
