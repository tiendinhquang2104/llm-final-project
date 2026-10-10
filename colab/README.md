# Colab notebooks

| Notebook | Mục đích |
|---|---|
| [`01_prepare_data.ipynb`](01_prepare_data.ipynb) | Preprocess ChatML + EDA → Drive `data/` |
| [`02_task1_baseline_api.ipynb`](02_task1_baseline_api.ipynb) | Task 1 Gemma 4 qua Gemini API và GPT-4o-mini qua OpenAI, cùng split 26/6 và pipeline |
| [`03_task1_public_test.ipynb`](03_task1_public_test.ipynb) | Tải ZIP public test từ Drive, dự đoán 360 bài Task 1 và xuất file nộp |

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

Checkpoint nằm trên Drive theo provider, model, experiment và dấu vân tay dữ liệu. Một lượt bị ngắt vì giới hạn API có thể chạy lại cell đầy đủ; `predictions.json` chỉ được tạo khi đủ 360 bài và đạt kiểm tra định dạng. Public test không có nhãn nên không có QWK/MAE tại máy. Không nộp file tự động.

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
