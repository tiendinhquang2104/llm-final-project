# Task 2 — Phân loại lỗi đa nhãn: thiết kế

Ngày: 2026-10-09 · Nhánh: `task-2`

## 1. Mục tiêu và phạm vi

Dự đoán tập nhãn lỗi (0..10 nhãn trong taxonomy) cho 360 bài nộp C++ của bộ public test. Leaderboard xếp theo
**macro-F1** trên 10 nhãn (micro-F1 phân hạng phụ). Đề yêu cầu ≥ 2 hướng, trong đó có một mô hình open-weight được
fine-tune và chạy cục bộ, kèm báo cáo phần cứng, chi phí, seed, phiên bản model.

| Hướng | Nội dung | Trạng thái lần này |
|---|---|---|
| 1 — Baseline API | Prompt zero/few-shot qua Gemini/OpenAI; sinh nhãn silver cho Hướng 2 | Viết code + test offline. Chưa chạy thật (chờ API key). |
| 2 — CLM-8B local | Fine-tune head của CLM-8B (A) + linear probe (B, ablation) trên embedding Qwen3-8B | Chạy tối thiểu trên Mac (MLX); script Kaggle chạy đầy đủ. |
| — | So sánh tốc độ / bộ nhớ / chi phí / chất lượng giữa Local CLM và API | Script benchmark sinh bảng. |

Ngoài phạm vi: LoRA sinh JSON (phương án C), Task 3.

## 2. Dữ liệu và nhãn

- **public_test_release** (360 bài, 6 đề, không có nhãn; `compile_log` rỗng và `test_report = null` cho mọi bài).
  Local: `data/public-test/public_test_release.zip`. Kaggle: tải từ Google Drive, file id đọc từ biến môi trường /
  Kaggle Secret `PUBLIC_TEST_DRIVE_ID` (không ghi link vào repo).
- **sample_dataset** (32 bài có nhãn, đề EX01/EX02 — khác 6 đề thi). Phân bố nhãn rất lệch: `Lỗi logic` 12,
  `Lỗi edge case` 0, `Lỗi mảng/chuỗi` 1; 4 bài `[]`.
- Cả hai giải nén vào `data/raw/` (gitignored). Không commit dữ liệu.

Chiến lược nhãn (đã chốt):

| Nguồn | Dùng cho |
|---|---|
| Gold — 32 bài, split cố định `data/splits/{train,val}_ids.json` (26/6) | Đánh giá local, chọn ngưỡng, few-shot demo cho Hướng 1, dữ liệu train |
| Silver — Hướng 1 gán nhãn 360 bài public, n mẫu self-consistency → P(nhãn) = tỉ lệ phiếu | Train head CLM (distillation). Ghi chi phí API. Cần giảng viên xác nhận trước khi dùng cho bản nộp cuối. |
| Leaderboard public (120 bài, 2 lượt/ngày/task) | Chỉ chọn giữa vài cấu hình cuối, không dò nhãn |

`feedback` không bao giờ là input (kiểm tra bằng test).

## 3. Kiến trúc

```
src/task2/
  labels.py        10 nhãn (thứ tự chuẩn của label_space.json) + mô tả tiếng Việt từng nhãn; normalize/validate nhãn
  data.py          Task2Sample, load_task2(root) cho cả public (không nhãn) và sample_dataset (có nhãn)
  prompts.py       prompt Hướng 1 (zero-shot / few-shot từ gold train), có mô tả nhãn
  pipeline.py      Hướng 1: build request → backend → parse JSON → lọc nhãn → gộp n mẫu thành xác suất
  evaluator.py     macro/micro-F1, F1 từng nhãn (2 quy ước cho nhãn vắng), validate_predictions, to_submission
  thresholds.py    chọn ngưỡng từng nhãn + sàn tỉ lệ dự đoán tối thiểu
  benchmark.py     gom số đo tốc độ/bộ nhớ/chi phí/chất lượng → benchmark.json + benchmark.md
  clm/
    text.py        state text + câu hỏi noul cho từng nhãn (layout của CLM: context trước, câu hỏi cuối), cắt token
    encoder.py     interface Encoder.embed(texts) -> np.ndarray[n, 4096] L2-norm; MLXEncoder, HFEncoder; cache .npy
    heads.py       nạp checkpoint CLM, NoulHeadModel (A), train/predict; LinearProbe (B)
scripts/
  run_task2_api.py   Hướng 1 (preflight không gọi API; eval trên gold val; predict public → silver + predictions)
  run_task2_clm.py   Hướng 2 (embed → train → threshold → eval → predict), cờ --limit cho chạy tối thiểu
configs/task2/       base.yaml, api_zero_shot.yaml, api_few_shot.yaml, clm_local.yaml, clm_kaggle.yaml
kaggle/task2_clm.ipynb
```

### 3.1 Hướng 1 — API

- Dùng lại `GeminiBackend` / `OpenAIBackend` (`src/llm/`), JSON extractor, cơ chế cache/registry của Task 1 ở mức
  cần thiết (không refactor Task 1).
- Output yêu cầu: `{"rationale": str, "taxonomy_error": [nhãn]}`. OpenAI dùng Structured Outputs với `enum` 10 nhãn.
- Parse: nhãn được normalize (bỏ khoảng trắng, không phân biệt hoa/thường), nhãn lạ bị loại. Parse lỗi → retry 1 lần
  → vẫn lỗi thì `[]` và đánh dấu `parse_ok=False`.
- Self-consistency `n` mẫu (T=0.7): `P(nhãn) = số phiếu / n`; dự đoán cứng = P ≥ 0.5. Với n=1, T=0.
- Prompt không có `compile_log`/`test_report` khi trường trống (public test luôn trống).

### 3.2 Hướng 2 — CLM-8B

CLM-8B (`sekkit/CLM-v0.1-8B`, Apache 2.0) = encoder Qwen3-8B frozen (last-token pooling, 4096-d, L2-norm) + state
head và action head (MLP → 512-d). Điểm = `exp(logit_scale) · cos(state_head(s), action_head(c))`.

**Mã hoá bài toán (noul):** với mỗi bài và mỗi nhãn ℓ:
- state text = `context` + `\n\n` + câu hỏi ℓ. Context = tên đề, loại đề, tóm tắt đề (cắt), code. Câu hỏi: "Bài nộp
  này có mắc <ℓ> không? <mô tả ℓ>".
- candidate: `"false: ..."` và `"true: ..."` (định dạng `schema.candidates` của CLM).
- `P(ℓ) = softmax(scale·cos)[true]`.
- Tổng độ dài state ≤ 2048 token; khi vượt, cắt tóm tắt đề trước rồi cắt giữa code, luôn giữ câu hỏi ở cuối.
- Mỗi bài cần 11 lần encode (10 câu hỏi + 1 context cho probe B) + 20 candidate dùng chung → embedding cache theo
  `sha256(encoder_id, text)`.

**(A) Fine-tune head:** khởi tạo từ checkpoint CLM; encoder frozen; train state head + action head + logit_scale bằng
BCE có trọng số (pos_weight theo nghịch tần suất, cắt trần) trên `P(ℓ)` với nhãn gold (0/1) và silver (xác suất mềm).
AdamW, lr nhỏ, early stop theo macro-F1 trên tập đánh giá. Zero-shot (head gốc, chưa train) được báo cáo như một
dòng ablation.

**(B) Linear probe:** embedding context (không câu hỏi) → 10 logistic regression (sklearn, `class_weight="balanced"`).
Nhãn chưa có ví dụ dương → xác suất 0 (ghi rõ trong báo cáo).

**Encoder theo môi trường** (head chỉ hợp lệ với encoder đã tạo embedding, nên mỗi môi trường train head riêng):

| Môi trường | Encoder | Head khởi tạo |
|---|---|---|
| Mac M3 Pro 18GB | `mlx-community/CLM-v0.1-8B-MLX-4bit` qua `mlx-lm` | head đi kèm bản MLX |
| Kaggle T4×2 | `Qwen/Qwen3-8B` fp16 `device_map="auto"` (fallback 8-bit nếu tràn số) | `CLM_v0.1-8B.pt` |

Model tải về `checkpoints/` hoặc `~/.cache` (không commit). Gói `contrastive-lm` cài `--no-deps` (chỉ cần
`clm.heads`, `clm.schema`; bỏ `vllm`).

### 3.3 Ngưỡng và hậu xử lý

- Ngưỡng riêng từng nhãn chọn theo F1 trên tập đánh giá (gold val ∪ silver held-out), lưới 0.05..0.95.
- Sàn: mỗi nhãn được dự đoán cho ít nhất `min_rate` (mặc định 2%) số bài, lấy các bài có P cao nhất.
- Nhãn không đủ dữ liệu để chọn ngưỡng → ngưỡng mặc định 0.5.

## 4. Đánh giá, nộp bài, benchmark

- `evaluator.py`: macro-F1 với hai quy ước cho nhãn vắng cả ở gold lẫn dự đoán (`zero` = F1 0, `skip` = bỏ khỏi trung
  bình), micro-F1, F1/precision/recall từng nhãn, exact-match tập nhãn.
- `validate_predictions`: đủ đúng tập sample_id, không trùng, `taxonomy_error` là list nhãn hợp lệ. File chỉ được
  ghi sau khi validate thành công. Mẫu thiếu dự đoán → `[]`.
- Output mỗi run: `outputs/task2/<run>/` gồm `config.json`, `predictions.json`, `predictions_full.json`
  (xác suất từng nhãn), `metrics.json`, `usage.jsonl` (API). Mỗi run ghi một dòng `experiments/registry.csv`.
- Benchmark (`outputs/task2/benchmark.{json,md}`): với mỗi hệ thống — phần cứng, giây/bài, thời gian train,
  bộ nhớ đỉnh (`mx.get_peak_memory()` / `torch.cuda.max_memory_allocated()`), token và USD (API), macro/micro-F1
  trên gold val.

## 5. Chạy local tối thiểu

1. `uv venv --python 3.12 .venv-mlx`; cài `mlx-lm`, `transformers`, `scikit-learn`, `torch`, `contrastive-lm --no-deps`.
2. Embed 32 bài gold + 12 bài public (2 bài/đề) → 44×11 + 20 ≈ 500 lần encode.
3. Train (A) và (B) trên 26 bài gold train, đánh giá trên 6 bài gold val, vài epoch.
4. Predict 12 bài public để kiểm tra đầu-cuối, ghi benchmark. Không cần nhãn silver.

## 6. Kaggle (`kaggle/task2_clm.ipynb`)

Clone repo (nhánh cấu hình được) → `gdown` dữ liệu theo `PUBLIC_TEST_DRIVE_ID` → cài phụ thuộc → nạp Qwen3-8B và head
CLM → embed 392 bài → nạp silver (`silver_labels.json` từ Kaggle dataset, hoặc chạy Hướng 1 nếu có API key trong Kaggle
Secrets) → train A, B → ngưỡng → `predictions.json` (đã validate) + benchmark. Seed 42 cho mọi bước.

## 7. Test (pytest, không mạng, không model)

- `labels`: normalize, nhãn lạ bị loại, thứ tự chuẩn.
- `evaluator`: F1 đúng trên ví dụ tay, trường hợp `[]`, hai quy ước nhãn vắng; validator bắt thiếu/trùng id, nhãn lạ.
- `pipeline` Hướng 1: parse JSON hợp lệ/lỗi/nhãn lạ, gộp phiếu, fallback `[]`; prompt không chứa `feedback`.
- `clm.text`: câu hỏi ở cuối, cắt độ dài đúng.
- `clm.heads`: train trên embedding ngẫu nhiên nhỏ làm loss giảm; nạp checkpoint giả đúng cấu trúc.
- `thresholds`: chọn ngưỡng đúng trên dữ liệu tay; sàn tỉ lệ dự đoán.
- Encoder dùng mock.

## 8. Rủi ro

- Tập gold val chỉ 6 bài, khác đề: số đo local nhiễu, chỉ dùng để kiểm tra pipeline.
- Nhãn silver mang sai lệch của model API; head CLM học lại sai lệch đó.
- Bản MLX 4-bit là bản chuyển đổi không chính thức (khoảng 91% đồng thuận top-1 với bản gốc).
- Qwen3-8B fp16 trên T4 có thể tràn số → fallback 8-bit.
- Leaderboard chưa nói rõ quy ước F1 cho nhãn vắng → báo cáo cả hai.
