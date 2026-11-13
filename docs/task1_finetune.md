# Task 1 — Hướng 2: fine-tune QLoRA (adapter riêng của Task 1)

Model nền: [`Qwen/Qwen2.5-Coder-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) (Apache-2.0, 7.6B).
Mỗi task có **một adapter LoRA riêng**. Tài liệu này mô tả adapter của Task 1: chấm rubric 6 chiều + `total_score`.

## Thiết kế

| Bước | File | Nội dung |
|---|---|---|
| Gold | `scripts/prepare_data.py` → `task1_{train,val}.jsonl` | 32 bài giảng viên chấm, split cố định 26/6 (`data/splits/`) |
| Silver | `scripts/prepare_task1_silver.py`, `src/task1/silver_data.py` | 462 bài tổng hợp (`generate-dataset.zip`). Loại bài trùng code, mâu thuẫn với `exec_report`, trùng gold/public → **422 bài**. `heldout/` và các ID chỉ có ở Task 3 không bao giờ được đọc. `exec_report` chỉ dùng để kiểm tra chất lượng, không vào prompt |
| Prompt | `src/data/prompts.py` (`build_task1_prompt`) | Cùng một prompt cho train, đánh giá và dự đoán: đề + code + compile log + test report; **không có `feedback`** |
| Train | `scripts/train_task1.py`, `configs/task1/lora_7b.yaml` | QLoRA 4-bit NF4, r 16 / alpha 32, loss chỉ tính trên phần JSON trả lời. Hai nhánh cùng seed: **gold-only** (3 epoch trên 26 gold, lr 1e-4) và **silver → gold** (v4: 2 epoch silver trộn 2 bản gold, lr 1e-4, rồi 2 epoch gold lr 3e-5; xem [v4](#v4-sửa-cách-train-sau-khi-v3-bị-mode-collapse)) |
| Chọn adapter | `src/task1/finetune.py` | Mỗi checkpoint (cả checkpoint cuối giai đoạn silver) được đánh giá trên **6 bài gold val + 10% silver giữ lại theo từng đề** (QWK, rồi MAE). Chọn checkpoint tốt nhất của mỗi nhánh, rồi chọn nhánh tốt hơn; hòa thì giữ gold-only → `best_adapter/`. `metrics` trong báo cáo vẫn là gold val để so được với hướng API |
| Dự đoán | `scripts/predict_task1_finetuned.py` | `best_adapter` + greedy decoding trên 360 bài public. Checkpoint theo batch nên chạy lại sẽ tiếp tục từ chỗ dở. Kiểm tra định dạng trước khi ghi `task1_predictions.json` |

**Đầu ra của model** là `{"rubric": {...}, "total_score": n}`. `total_score` luôn được tính lại bằng tổng 6 chiều.
Bài nào model trả JSON hỏng thì nhận điểm trung vị rubric của các bài gold cùng dạng đề, có đánh dấu
`fallback_used`. Số bài bị fallback được ghi trong `run_info.json`.

**Khác với hướng API:** adapter không trả trạng thái từng câu P1–P4, nên **không áp rule câu tiên quyết bằng code**.
Model phải tự học chính sách này từ điểm của dữ liệu. Đây là một dòng ablation để so sánh với hướng API (có rule).

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

## v3: silver được API chấm lại (distillation)

Hướng API (Gemini 3.5 Flash Lite, e2 zero-shot structured + rule) đạt QWK **0.8707** trên public, còn adapter v1 đạt
0.7188. Ở v3, API đóng vai "giáo viên" chấm lại 462 bài silver. Rubric cuối cùng (sau rule câu tiên quyết, compile
gate, làm tròn) thay cho nhãn của bộ sinh dữ liệu, rồi train adapter như cũ. Đề có cho phép dùng LLM thương mại qua API
để huấn luyện, nhưng **phải báo cáo chi phí**.

- **Chỉ chấm đề tổng hợp `SYN-*`.** Script từ chối mọi đề khác, nên input của public/private test không bao giờ được gán
  nhãn. Gold vẫn giữ điểm của giảng viên. Nhãn generator không xuất hiện trong prompt (zero-shot).
- **Chạy dần theo quota.** Có checkpoint từng bài: hết quota thì chạy lại đúng lệnh cũ vào hôm sau. 462 bài ≈ 1 ngày
  free tier (500 request/ngày; `max_requests_per_run: 480`).

```bash
python scripts/distill_task1_silver.py --preflight
python scripts/distill_task1_silver.py --limit 3
python scripts/distill_task1_silver.py
```

Kết quả là `data/synth/v1_api/` (gitignored), bản sao của silver với nhãn API. Thư mục có thêm `distill_manifest.json`
ghi model giáo viên, cấu hình prompt, **số request và token** (chi phí cần báo cáo), độ khớp với nhãn generator và phân
bố điểm. Lượt train ghi nguồn nhãn vào `silver_manifest.json` (`labels.source = api_teacher`).

Train: dùng `--silver-root data/synth/v1_api` (máy có GPU), hoặc trên Kaggle tải zip của `data/synth/v1_api` lên dataset
private và để `SILVER = 'api'` trong notebook (`'generator'` = nhãn gốc như v1).

**Kết quả v3 trên public:** QWK 0.7096, MAE 1.94 (v1: 0.7188 / 2.03; API e7: 0.8759 / 1.12). Đổi nhãn không cải thiện.

## v4: sửa cách train sau khi v3 bị mode collapse

Phân tích dự đoán v3 trên 328 bài public (so với dự đoán API e7 trên cùng các bài):

- **Mode collapse:** cả 328 bài chỉ có **6 tổ hợp rubric**; không bài nào có tổng 4, 5, 6, 8, 9. API có 27 tổ hợp, nhãn
  silver của thầy có 40.
- **Lỗi dồn vào đề 4 câu:** Class03-Final-1 MAE 2,86 (lệch −2,45), Midterm-1 1,72, Midterm-2 1,89; đề 1 câu chỉ
  0,65–0,93. Tổ hợp `1,0,0,0,0,0` xuất hiện 97 lần (API: 48 bài tổng 1).
- **Nguyên nhân từ cách train:** silver chỉ 1 epoch ở lr 5e-5 (≈105 bước), sau đó 3 epoch gold ở lr cao gấp đôi trên 26
  bài của 2 đề, nên giai đoạn gold ghi đè những gì học từ silver. Adapter được chọn bằng QWK trên 6 bài
  (0,456 so với 0,430), mức chênh này là nhiễu.

Thay đổi (`configs/task1/lora_7b.yaml`, nhánh gold-only giữ nguyên):

| | v3 | v4 |
|---|---|---|
| Giai đoạn silver | 418 bài, 1 epoch, lr 5e-5 | 377 bài + 2 × 26 gold (replay), 2 epoch, lr 1e-4 |
| Giai đoạn gold sau silver | 3 epoch, lr 1e-4 | 2 epoch, lr 3e-5 |
| Ứng viên khi chọn | 3 checkpoint gold | 2 checkpoint silver + 2 checkpoint gold |
| Tập chọn | 6 gold val | 6 gold val + 41 silver giữ lại (`silver_split.json`) |

Thời gian ước tính trên T4 tăng khoảng 1–1,5 giờ so với v3 (giai đoạn silver dài gấp đôi, đánh giá 47 bài × 7 checkpoint).
Notebook có thêm cell tải model trước, thử lại tối đa 5 lần, để lỗi CDN Hugging Face (HTTP 500) không làm hỏng lượt chạy.

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
| `gold_only/`, `silver_then_gold/` | `validation_report.json`, `epoch_*/metrics.json` (gold val), `epoch_*/silver_val_metrics.json`, `epoch_*/selection_metrics.json`: dùng cho bảng ablation. Trong `silver_then_gold/`, `epoch_1..2` là checkpoint silver, `epoch_3..4` là checkpoint gold |
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
- **Không có rule câu tiên quyết bằng code** (xem phần Thiết kế).
