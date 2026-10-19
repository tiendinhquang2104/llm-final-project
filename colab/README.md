# Colab notebooks

| Notebook | Mục đích |
|---|---|
| [`01_prepare_data.ipynb`](01_prepare_data.ipynb) | Preprocess ChatML + EDA → Drive `data/` |
| [`02_task1_baseline_api.ipynb`](02_task1_baseline_api.ipynb) | Task 1 Gemma 4 qua Gemini API và GPT-4o-mini qua OpenAI, cùng split 26/6 và pipeline |
| [`03_task1_public_test.ipynb`](03_task1_public_test.ipynb) | Tải ZIP public test từ Drive, dự đoán 328 bài Task 1 và xuất file nộp |
| [`04_task1_public_report.ipynb`](04_task1_public_report.ipynb) | Đọc output notebook 03 và vẽ điểm, rubric, trạng thái câu, rule, token |
| [`05_task1_finetune.ipynb`](05_task1_finetune.ipynb) | QLoRA Task 1: đối chứng gold-only với silver→gold, chọn adapter bằng 6 bài gold validation |
| [`06_task1_finetuned_public_test.ipynb`](06_task1_finetuned_public_test.ipynb) | Chạy 328 bài public test trên GPU bằng best adapter/epoch của notebook 05, có resume và xuất file nộp |
| [`../kaggle/task1_finetune.ipynb`](../kaggle/task1_finetune.ipynb) | Bản Kaggle của notebook 05 + dự đoán public bằng `best_adapter` (xem `docs/task1_finetune.md`) |

## Task 1 QLoRA

Mở notebook 05 với runtime GPU sau khi push code mới lên branch thử nghiệm `task-1-tien`. Notebook clone branch vào thư mục mới trên Colab mỗi lần chạy để giữ checkout cũ, tải **mới** `public-test-cham-diem-phan-hoi-files.zip` và `generate-dataset.zip` từ Drive, ghi SHA-256 và chuẩn bị 26/6 gold cùng 422 silver Task 1. Silver được lọc trùng code, mâu thuẫn `exec_report` và trùng gold/public; 65 heldout cùng 150 ID chỉ có ở Task 3 không vào train. Preflight kiểm tra split, leakage và độ dài token. Smoke test chạy một bước ở mỗi giai đoạn và một lượt suy luận. Lượt đầy đủ so sánh gold-only 3 epoch với silver 1 epoch → gold 3 epoch, đánh giá từng epoch gold trên 6 bài validation và chọn theo QWK rồi MAE; hòa hoàn toàn giữ gold-only. Mỗi lượt có thư mục dữ liệu và output riêng dưới `MyDrive/LLM/Final Project/data/`, kèm manifest nguồn, dự đoán, metric và adapter. Notebook không tự nộp public test.

## Task 1 public test sau fine-tune

Notebook 06 chạy public test sau fine-tune: chọn runtime GPU, sửa `TRAINING_RUN` thành thư mục output của notebook 05 (mặc định là run `20261015T080908454574Z-637a033e-88eff95f`), rồi Run all sau khi push source mới lên `task-1-tien`. Notebook đọc `training_summary.json` và `training_config.json`, load base model cùng `best_adapter` của epoch thắng gold validation; không dùng API key. Khi checkpoint gốc còn, SHA-256 của adapter phải khớp checkpoint được chọn.

Preflight kiểm tra prompt cùng format lúc train cho đủ 328 bài, không cắt code khi vượt context. Smoke chạy trước lượt đầy đủ trên cùng model; checkpoint hợp lệ được dùng tiếp khi chạy lại. File nộp chỉ được xuất khi đủ 328 bài tại `data/outputs/task1/public/peft/<model>/<training-run>__<variant>__epoch_<n>/<fingerprint>/predictions.json`. File `progress.json` và `config.json` ghi rõ best epoch, adapter hash và cấu hình. Có thể dùng notebook 04 với `RUN_DIR` trỏ vào thư mục này để xem phân bố điểm/rubric; model không sinh trạng thái từng câu hay rule trace.

Runner tương ứng: `python scripts/predict_task1_colab.py --training-run <training-output> --public-root <public-root> --output-root <outputs/task1> --preflight`. Bỏ `--preflight`, thêm `--smoke-first` để suy luận bằng GPU. `--max-length` cho phép tăng context rõ ràng nếu preflight phát hiện bài quá dài.

## Task 1 API baseline

1. Notebook 02 tự clone/cập nhật branch `task-1` trong `/content/llm-final-project-task1/`. Giữ dữ liệu ở `MyDrive/LLM/Final Project/data/` như notebook 01. Repo trên Drive có thể tiếp tục ở branch khác.
2. Chọn `PROVIDERS = ('gemini', 'openai')` hoặc chỉ một provider. Notebook lấy khóa từ biến môi trường, rồi Colab Secrets; nếu Secrets không phản hồi, notebook hỏi qua ô nhập ẩn. Không nhập khóa trực tiếp vào cell hoặc chat.
3. Mở notebook 02, chạy preflight cho cả hai provider (không gọi API). Đặt `RUN_LIVE = True` để chạy smoke test một bài rồi lượt đầy đủ 6 bài validation cho zero-shot và few-shot của provider đã chọn.
   Lượt đầy đủ dùng lại bài smoke test hợp lệ nếu model, prompt và cấu hình tạo sinh giống nhau.

Notebook 02 đồng bộ split 26/6 đã commit sang Drive. Nếu Drive có split khác, notebook lưu bản cũ ở `data/splits/history_before_26_6/` trước khi thay thế.

Notebook ghi `predictions.json`, `predictions_full.json`, `metrics.json`, `config.json` và `usage.jsonl` vào `data/outputs/task1/<experiment>__<provider>__<model>/` trên Drive. Nhật ký không chứa API key hay toàn bộ mã C++ của sinh viên. Số USD được tính từ token usage của mọi phản hồi OpenAI, kể cả lượt sửa; giới hạn mặc định là ước tính 1 USD mỗi lần chạy. Giá tham chiếu và ngày kiểm tra được lưu trong `config.json`.

Có thể chạy lại cùng pipeline bằng lệnh `python scripts/run_task1.py --provider openai --data-dir <raw-folder> --splits-dir <splits-folder> --output-dir <private-output-folder> --preflight`; đổi provider thành `gemini` hoặc bỏ `--preflight` khi muốn gọi API.

## Task 1 public test

Notebook 03 tải `public-test-cham-diem-phan-hoi-files.zip` từ [folder Drive của cuộc thi](https://drive.google.com/drive/folders/1kBd4pE4JHcDtm0WFYueFq6aTEuTanUNC). Nếu folder không cho `gdown` tải trực tiếp, đặt ZIP trong MyDrive và điền `DRIVE_ZIP` ở cell dữ liệu. Sau khi đồng bộ code mới lên branch `task-1`, chạy preflight rồi bật `RUN_LIVE` để chạy smoke và toàn bộ public test. Chỉ khóa của provider được chọn mới được hỏi.

Runner tương ứng: `python scripts/run_task1.py --provider gemini --data-dir <sample-root> --splits-dir <26-6-split> --predict-only --predict-root <public-root> --preflight`. Bỏ `--preflight` để gọi API. Thêm `--predict-ids ID1,ID2` cho smoke; mặc định `--predict-experiment e2_zero_shot_structured`.

Checkpoint nằm trên Drive theo provider, model, experiment và dấu vân tay dữ liệu. Một lượt bị ngắt vì giới hạn API có thể chạy lại cell đầy đủ; `predictions.json` chỉ được tạo khi đủ 328 bài và đạt kiểm tra định dạng. Public test không có nhãn nên không có QWK/MAE tại máy. Không nộp file tự động.

Notebook 04 đọc thư mục run đó (mặc định là lượt mới nhất đã đủ bài) và vẽ báo cáo. Không gọi API và không sửa `predictions.json`. `SAVE_REPORT = True` ghi PNG, CSV và `summary.md` vào `<run>/report/`.

## Per-person config via `.env`

**Commit** `.env.example` — **không commit** `.env`.

Mỗi người copy `.env.example` → `.env` (local và/hoặc Drive):

```bash
cp .env.example .env
# sửa REPO_BRANCH=dev/process_data   # hoặc branch của bạn
```

Đặt file riêng trên Drive (khuyến nghị cho Colab):

`MyDrive/LLM/Final Project/.env`

```env
REPO_URL=https://github.com/tiendinhquang2104/llm-final-project.git
REPO_BRANCH=dev/process_data
DRIVE_DATA_DIR=/content/drive/MyDrive/LLM/Final Project/data
REPO_DIR_ON_DRIVE=/content/drive/MyDrive/LLM/Final Project/llm-final-project
```

Notebook sẽ `git clone --branch $REPO_BRANCH` (hoặc `checkout`/`pull` nếu repo đã có trên Drive).

## Workflow

1. Làm việc trên branch riêng (`dev/process_data`, …).
2. Push branch đó khi muốn Colab lấy code mới.
3. Merge `main` chỉ khi ổn định.
4. Không dùng `%autoreload` trên Colab Python 3.13 (`imp` đã gỡ) — re-run cell load source.
