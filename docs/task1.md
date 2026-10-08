# Task 1 — Chấm điểm theo rubric (Hướng 1: Prompting qua API)

Chấm 6 chiều rubric (`compilable 0-1, io_format 0-1, logic 0-4, edge_case 0-2, complexity 0-1, code_quality 0-1`,
tổng 0–10) cho bài C++ bằng LLM gọi qua **Gemini API** (Gemma 4 / Gemini), kèm rule chính sách đề viết bằng code.

```
đề + code + compile_log + test_report
        │
        ▼
 src/task1/prompts.py ──► src/llm/api_client.py (Gemini) ──► src/task1/scorer.py (JSON robust, retry)
                                                                │  rubric + trạng thái từng câu P1..Pn
                                                                ▼
                                          src/task1/prerequisite_rules.py (chính sách đề, code thuần)
                                            clamp → câu tiên quyết → compile gate → total = Σ 6 chiều
                                                                │
                                                                ▼
                         src/task1/evaluator.py (QWK, MAE, exact-match) + src/evaluation/error_analysis.py
```

## Module

| File | Vai trò |
|---|---|
| `src/data/loader.py` | load đề / sample / code, split train/val cố định (seed) |
| `src/task1/prompts.py` | template `plain` (zero-shot tối giản) và `structured` (rubric chi tiết + JSON + trạng thái từng câu), chọn few-shot demo |
| `src/llm/api_client.py` | client Gemini `generateContent`: giới hạn RPM/TPM, chặn số request/run, retry 429/503 theo `retryDelay`, dừng khi hết quota ngày, tự tắt tính năng model không hỗ trợ, đếm token |
| `src/utils/json_extractor.py` | tách JSON từ output LLM (bỏ `<think>`, code fence, dấu phẩy thừa) — dùng chung cho mọi task |
| `src/task1/scorer.py` | output → rubric + trạng thái câu; gộp self-consistency (median / bỏ phiếu) |
| `src/task1/prerequisite_rules.py` | **rule câu tiên quyết + compile gate**, độc lập với prompt, hàm thuần |
| `src/evaluation/metrics.py` | QWK (khoảng 0–10 cố định), MAE |
| `src/task1/evaluator.py` | metric Task 1 (theo đề, từng chiều) + kiểm tra định dạng `predictions.json` |
| `src/evaluation/error_analysis.py` | bài lệch ≥ 2 điểm, gắn tag nguyên nhân |
| `src/task1/pipeline.py`, `experiment.py` | ghép các bước; chạy experiment, cache, checkpoint, ghi `experiments/registry.csv` |
| `scripts/run_task1.py` | điểm chạy duy nhất (đọc `configs/task1/run.yaml`) |
| `scripts/create_split.py`, `audit_task1_labels.py`, `compare_task1_runs.py` | split cố định, audit nhãn, bảng so sánh run |

## Cách chạy

1. Dữ liệu: giải nén bộ dữ liệu vào `data/raw/sample_dataset/` (`exams.json`, `task1_grading.json`, `submissions/...`).
2. API key (https://aistudio.google.com/apikey) vào `.env`: `GEMINI_API_KEY=...` (xem `.env.example`).
3. Chỉnh `configs/task1/run.yaml` (model, `rpm`/`tpm`, `test_mode`, danh sách experiment), rồi:

```bash
pip install pyyaml        # Task 1 chỉ cần pyyaml (gọi API bằng thư viện chuẩn)
python scripts/run_task1.py
```

- `test_mode: true` chỉ chạy `test_sample_ids` (kiểm tra code, vài request); `false` chạy toàn bộ validation.
- Mỗi bài = 1 request (+ tối đa 1 retry khi JSON lỗi). Rule và metric chạy local, không tốn request.
- Output: `outputs/task1/<config>[_test]__<model>/` gồm `prompt.md` (prompt thật), `config.json` (config, model
  phục vụ, token đã dùng `model_info.inference`), `raw_outputs.jsonl`, `predictions.json` (định dạng nộp),
  `predictions_full.json`, `metrics.json` (main / LLM-only / rule ablation), `error_analysis.md`.
- Cache theo nội dung request: chạy lại không gọi API lại; run bị ngắt chạy tiếp từ chỗ dở (checkpoint mỗi 4 bài).
- Test: `pytest tests/ -q` (không gọi mạng; test cần dữ liệu tự bỏ qua nếu thiếu `data/raw/sample_dataset`).

### Hạn mức free tier (AI Studio, 10/2026 — có thể thay đổi)

| Model | RPM / TPM / RPD | `rpm` / `tpm` nên đặt |
|---|---|---|
| `gemma-4-26b-a4b-it`, `gemma-4-31b-it` | 30 / 16K / 14.4K | 25 / 15000 (TPM là nút cổ chai: prompt few-shot ≈ 7–9k token) |
| `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite` | 15 / 250K / 500 | 12 / 0 |
| `gemini-3.8-flash` | 5 / 250K / 20 | 4 / 0 (chỉ đủ ~1 run/ngày) |

**Lưu ý dữ liệu:** free tier của Gemini được Google dùng nội dung để cải thiện sản phẩm — code sinh viên (đã ẩn danh)
được gửi cho Google. Cần xác nhận với giảng viên trước khi dùng tập đầy đủ.

## Experiment (validation cố định `data/splits/`: 13 train / 19 val)

| Config | Mô tả |
|---|---|
| `e1_zero_shot_plain` | baseline: zero-shot, prompt ngắn, chỉ 6 số (không có trạng thái câu → rule tiên quyết không chạy) |
| `e2_zero_shot_structured` | zero-shot + rubric chi tiết + structured output (lý do, trạng thái từng câu, rubric) |
| `e3_few_shot_structured` | + 3 bài mẫu cùng đề từ tập train (rải đều theo điểm), kèm điểm giảng viên |
| `e4_few_shot_thinking` | + thinking mode (CoT) |
| `e5_policy_in_prompt` | ablation: chính sách đề ghi trong prompt, **tắt** rule code |
| `e6_self_consistency` | n=5 mẫu, T=0.7, median từng chiều + bỏ phiếu trạng thái |
| `final` | pipeline cuối (hiện = e3 + full rules) |

### Kết quả hiện có — `gemma-4-26b-a4b-it`, 19 bài val

| | QWK | MAE | Bias | EM6 | QWK EX01 | QWK EX02 | QWK bỏ 2 nhãn mâu thuẫn |
|---|---|---|---|---|---|---|---|
| e1 zero-shot | 0.638 | 2.32 | −1.89 | 0.68 | 0.31 | 0.79 | 0.765 |
| e3 few-shot (+ rules) | **0.656** | **1.89** | −1.89 | **0.75** | 0.23 | **0.90** | **0.803** |
| e3 trước rule | 0.710 | 1.63 | | | | | |

Rule ablation (e3): no_rules 0.710 · compile_gate_only 0.714 · prereq_only 0.652 · full 0.656 · full+derive_logic 0.673.
Chi phí e3: 19 request, 93.6K token vào, 4.8K token ra (free tier).

Nhận xét chính:
- Few-shot cải thiện rõ EX02 (đề một câu, có test): QWK 0.79 → 0.90.
- EX01 (nhiều câu, không có test) yếu: model đoán P1 sai ở 8/9 bài (giảng viên: ~2/9) và tự đoán `runtime_error`
  khi không chạy được code. Rule tiên quyết khuếch đại lỗi P1 của model (S101: 8 → 2), đồng thời gặp 2 nhãn mâu thuẫn.
- Model khắt khe hơn giảng viên (bias −1.9), nhiều nhất ở `logic` và `edge_case`; giảng viên dễ hơn với lỗi in thừa
  chữ ("Input n:").
- 19 bài là mẫu nhỏ: chênh lệch QWK < ~0.05 chưa có ý nghĩa thống kê.

## Rule câu tiên quyết

Model chấm **từng câu độc lập** và trả về trạng thái (`correct | partial | wrong | runtime_error | not_attempted`).
Code mới áp dụng chính sách đề:

1. **Câu tiên quyết** (`is_prerequisite_for` trong `exams.json`): nếu câu tiên quyết `wrong / runtime_error /
   not_attempted` (thêm `partial` khi `prereq_strict`), các câu phụ thuộc không được chấm:
   `logic, edge_case, complexity, code_quality → 0`, giữ `compilable, io_format` (khớp EX01-S105/106/107).
2. **Compile gate**: `compilable = 0` → đề ghi "0 điểm nếu … không biên dịch được" (EX01) thì toàn bộ 0; ngược lại
   (EX02) giữ `code_quality` (khớp S203/S212/S217).
3. `total_score` luôn = tổng 6 chiều.

Rule chạy sau model nên mọi biến thể rule được đánh giá trên **cùng** raw output (ablation không tốn request).

## Vấn đề dữ liệu (`scripts/audit_task1_labels.py`) — ứng viên điểm thưởng

- **Nhãn vi phạm chính sách tiên quyết**: 3/6 bài feedback ghi P1 sai / "câu 1 là tiên quyết" vẫn được điểm các câu
  sau (EX01-S108 = 6, S110 = 8, S112 = 9). Bỏ S108, S112 khỏi val: QWK e3 0.656 → 0.803.
- **Trọng số đề lệch**: statement ghi P1–P4 = 1/4/2/3 điểm, `exams.json` ghi 2.5 mỗi câu.
- **Test vs nhãn**: 3 bài EX02 pass 0/8 test vẫn `logic ≥ 2` (S211 in thêm "Input number:" vẫn 10 điểm, `io_format = 1`;
  S205 thừa một dấu cách bị `io_format = 0`).
- **compile_log ≠ nhãn**: S214 lỗi link (code bị comment hết) vẫn `compilable = 1`.

## Tái lập

- Seed 42 cho split và từng request (`generationConfig.seed`); T=0; thinking ở mức thấp nhất của model.
- `config.json` ghi `modelVersion` Gemini trả về và số token; `experiments/registry.csv` ghi mỗi run kèm git commit.
- `feedback` **không** bao giờ vào prompt Task 1 (có test kiểm tra); chỉ dùng trong script audit nhãn.
