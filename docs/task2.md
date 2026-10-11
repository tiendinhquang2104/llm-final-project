# Task 2 — Phân loại lỗi đa nhãn

Spec: `docs/superpowers/specs/2026-10-09-task2-design.md` · Plan: `docs/superpowers/plans/2026-10-09-task2.md` · Plan điều chỉnh (bỏ silver): `docs/superpowers/plans/2026-10-11-task2-no-silver.md`

## Dữ liệu
- Giải nén: `python scripts/unpack_data.py data/public-test --dest data/raw` → `data/raw/public_test_release` (360 bài,
  không nhãn, không compile_log/test_report) và `data/raw/sample_dataset` (32 bài có nhãn, đề EX01/EX02).
- Nhãn: 32 bài gold là nguồn nhãn duy nhất. Hướng 1 dùng split 26/6 (`data/splits/`) để chọn cấu hình API; Hướng 2
  đánh giá bằng k-fold (4) trên cả 32 bài gold. Điểm leaderboard chỉ dùng để chọn cấu hình cuối.
- **Không** dùng nhãn sinh trên input tập test (phán quyết giảng viên 2026-10-11). Hướng 1 dự đoán 360 bài public
  chỉ để nộp, không đưa vào train, ngưỡng hay chọn epoch.
- Không dùng `feedback`. Không đưa compile_log/test_report vào input (public test không có).

## Hướng 1 — API
```bash
python scripts/run_task2_api.py --preflight                 # không gọi API
python scripts/run_task2_api.py --provider gemini --smoke    # 1 bài
python scripts/run_task2_api.py --provider gemini           # zero-shot + few-shot trên 6 bài gold val
```
Dự đoán 360 bài public để nộp: đặt `run.predict: true` trong `configs/task2/run_api.yaml` → `outputs/task2/task2_api_predict__*/`
gồm `predictions.json` (self-consistency n=5, nhãn = đa số phiếu) và `predictions_full.json`. Chi phí: `usage.jsonl`, `resources.json`.
Demo few-shot của lượt dự đoán chỉ lấy từ gold train (26 bài), không bao giờ từ gold val.
`--preflight` in `approx_input_tokens` đã nhân n (mỗi request gửi lại cả prompt) và, với OpenAI, `estimated_usd`
(lượt dự đoán 360×5 ≈ $0.85–1.25 với gpt-4o-mini; `openai.max_usd` = 3.0).
Thời gian lượt dự đoán trên Gemma free tier: ≈1800 request, bị giới hạn TPM, vài giờ; dừng giữa chừng thì chạy lại sẽ dùng cache.

## Hướng 2 — CLM-8B
CLM-8B = Qwen3-8B frozen (last-token pooling) + state/action head. Mỗi nhãn là một câu hỏi có/không (`noul`):
P(nhãn) = sigmoid(scale · (cos(state, "true: …") − cos(state, "false: …"))). Hệ thống:
- `clm_zero_shot`: head gốc, không train.
- `clm_noul`: fine-tune head trên 32 bài gold (BCE có trọng số).
- `clm_noul_aug`: như `clm_noul` nhưng train thêm mẫu chèn lỗi (augmentation). Một trong hai hệ thống CLM; learning rate chọn trên OOF (xem dưới).
- `probe`: logistic regression trên embedding context (ablation), không aug.
- `probe_aug`: probe với mẫu chèn lỗi. Đây là `final_system` mặc định của config (`final_system: probe_aug`), chọn chỉ dựa trên OOF trên gold: tốt nhất ở cả @0.5 (0.245) và @tuned (0.298) trong lần chạy local; không dựa trên đầu ra public.

Ngưỡng riêng từng nhãn + sàn tỉ lệ dự đoán 2%. Sàn 2% (`thresholds.min_rate`) tính trên tập dự đoán public: đây là bước transductive, không dùng nhãn, không dùng đầu ra LLM và không fit gì; vẫn nằm trong danh sách câu hỏi cho giảng viên. Phương án dự phòng: `thresholds.min_rate: 0`.

**Chọn learning rate.** `train.lr_grid` (mặc định `[1e-5, 1e-4, 1e-3]`; bỏ trống thì dùng `train.lr`). Với mỗi lr, chạy CV cho `clm_noul` và `clm_noul_aug` (probe không phụ thuộc lr, chạy một lần). Mỗi hệ thống CLM chọn lr có macro-F1 OOF cao nhất ở ngưỡng đã tune (hòa thì lr nhỏ hơn); model cuối train với lr đó. Kết quả ghi ở `metrics.json` mục `lr_selection`, lr dùng được ghi trong history từng fold. Như ngưỡng, việc chọn lr dùng chính OOF nên số @tuned lạc quan.

**Đánh giá k-fold.** 4 fold trên 32 bài gold; metric và ngưỡng lấy từ out-of-fold. Mỗi fold train trên ≈75% gold;
model cuối train trên toàn bộ gold + mẫu chèn lỗi, và ngưỡng (cùng lr) chọn trên OOF của các model fold (≈75% gold) được áp cho model cuối train trên toàn bộ gold + mẫu chèn lỗi.
Mẫu chèn lỗi của một bài chỉ đi vào fold train khi bài gốc thuộc fold train, nên không rò rỉ sang fold validation.

**Augmentation (chèn lỗi vào code gold).** `src/task2/augment.py`, 9 luật; mỗi luật thêm nhãn lỗi tương ứng vào
nhãn gốc của bài. Mẫu có `sample_id = "<id gốc>~<tên luật>"`. Không có luật cho `Lỗi thuật toán`.

| Luật | Nhãn được thêm | Số mẫu (164 tổng, trên gold thật) |
|---|---|---|
| `drop_return_semicolon` | Lỗi biên dịch | 30 |
| `alter_output_text` | Lỗi nhập/xuất | 16 |
| `flip_if_comparison` | Lỗi logic | 23 |
| `flip_loop_bound` | Lỗi vòng lặp | 24 |
| `off_by_one_size` | Lỗi mảng/chuỗi | 2 |
| `drop_reference_param` | Lỗi hàm | 16 |
| `remove_edge_guard` | Lỗi edge case | 8 |
| `hardcode_return` | Lỗi hard-code | 14 |
| `strip_indentation` | Lỗi style | 31 |

- Các luật bỏ qua code nằm trong comment (`//`, `/* */`), và bỏ qua các trường hợp không đổi gì.
- Config local (`configs/task2/clm_local.yaml`) giới hạn 4 mẫu mỗi luật; config Kaggle dùng mọi mẫu.
- Tuỳ chọn: chèn lỗi bằng API từ bài gold. `python scripts/augment_task2_api.py --preflight` (không gọi API), rồi
  `python scripts/augment_task2_api.py --provider gemini` (hoặc `openai`). Kết quả là `outputs/task2/augment_api/mutants.json`
  với `sample_id = "<id gốc>~api-<chỉ số nhãn>"`. Dùng bằng `augment.api_path` trong config hoặc `--augment-api PATH`
  của `scripts/run_task2_clm.py`.

Chạy:
- Local (Mac, MLX 4-bit, tối thiểu): `python scripts/run_task2_clm.py --config configs/task2/clm_local.yaml`
  (thêm `--augment-api PATH` nếu có mutants API).
- Kaggle (T4×2, đầy đủ): `kaggle/task2_clm.ipynb` (cần Secret `PUBLIC_TEST_DRIVE_ID`). Repo, dữ liệu sinh viên
  và cache embedding nằm trong `/kaggle/tmp` (không lưu cùng notebook version); chỉ `task2_predictions.json` và
  `task2_benchmark.md` được copy sang `/kaggle/working`.
- Benchmark: `python scripts/task2_benchmark.py` → `outputs/task2/benchmark.md`. Giây/bài ≈ 0 khi chạy lại hoàn toàn
  từ cache embedding (chỉ tính thời gian encode thật).
- Số `@tuned` là lạc quan: ngưỡng chọn trên OOF của các fold model (≈75% gold) rồi áp cho model cuối, nhưng
  OOF và số đo đều dựa trên cùng 32 bài. Số `@0.5` không phụ thuộc ngưỡng chọn.

Head chỉ hợp lệ với encoder đã sinh embedding: bản MLX 4-bit và bản HF fp16 phải train head riêng; số đo hai môi trường
không so trực tiếp.

## Kết quả local

### Lần chạy 2026-10-09 (thiết kế cũ, 6 bài val)

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
  - Lần chạy này train trên 26 bài gold, chưa có mẫu chèn lỗi nên fine-tune gần như chưa thay đổi head.
  - Với ngưỡng chọn từ 6 bài, hệ thống gán "Lỗi biên dịch" cho cả 6 bài public thử. Cần k-fold trên gold và Kaggle để có ngưỡng đáng tin.
- Đã kiểm tra: toàn bộ 4312 state text (gold + public) ≤ 2041 token với tokenizer Qwen3, câu hỏi không bị cắt.

### Lần chạy CV + augmentation

Lần chạy 2026-10-11 trên Apple M3 Pro 18GB, MLX 4-bit. Tổng thời gian 33 phút 20 giây (374 lần encode mới, 438 lấy từ cache của lần trước). Có 34 mẫu chèn lỗi (giới hạn 4 mỗi luật). CV 4 fold mất 14.5 giây, train bản cuối 4.2 giây. Bộ nhớ đỉnh 5.29 GB. "Giây/bài" = tổng thời gian encode / 72 mẫu (32 gold + 34 chèn lỗi + 6 public).

| Run | Hệ thống | Phần cứng | n val | macro-F1 | micro-F1 | giây/bài | train (s) | bộ nhớ đỉnh (GB) | token vào | token ra | USD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| task2_clm_local | clm_zero_shot@0.5 | Apple M3 Pro 18GB | 32 | 0.036 | 0.069 | 27.29 | 4.24 | 5.29 | — | — | 0.0000 |
| task2_clm_local | clm_zero_shot@tuned | Apple M3 Pro 18GB | 32 | 0.266 | 0.254 | 27.29 | 4.24 | 5.29 | — | — | 0.0000 |
| task2_clm_local | clm_noul@0.5 | Apple M3 Pro 18GB | 32 | 0.045 | 0.118 | 27.29 | 4.24 | 5.29 | — | — | 0.0000 |
| task2_clm_local | clm_noul@tuned | Apple M3 Pro 18GB | 32 | 0.247 | 0.273 | 27.29 | 4.24 | 5.29 | — | — | 0.0000 |
| task2_clm_local | clm_noul_aug@0.5 | Apple M3 Pro 18GB | 32 | 0.069 | 0.087 | 27.29 | 4.24 | 5.29 | — | — | 0.0000 |
| task2_clm_local | clm_noul_aug@tuned | Apple M3 Pro 18GB | 32 | 0.278 | 0.266 | 27.29 | 4.24 | 5.29 | — | — | 0.0000 |
| task2_clm_local | probe@0.5 | Apple M3 Pro 18GB | 32 | 0.192 | 0.252 | 27.29 | 4.24 | 5.29 | — | — | 0.0000 |
| task2_clm_local | probe@tuned | Apple M3 Pro 18GB | 32 | 0.261 | 0.317 | 27.29 | 4.24 | 5.29 | — | — | 0.0000 |
| task2_clm_local | probe_aug@0.5 | Apple M3 Pro 18GB | 32 | 0.245 | 0.268 | 27.29 | 4.24 | 5.29 | — | — | 0.0000 |
| task2_clm_local | probe_aug@tuned | Apple M3 Pro 18GB | 32 | 0.298 | 0.332 | 27.29 | 4.24 | 5.29 | — | — | 0.0000 |

Nhận xét:
- Augmentation giúp cả hai bộ học: probe 0.192 → 0.245 @0.5 và 0.261 → 0.298 @tuned; CLM noul 0.247 → 0.278 @tuned.
- `probe_aug` tốt nhất ở cả hai ngưỡng.
- Trong lần chạy này (trước khi có lưới lr), head CLM fine-tune gần như không đổi xác suất (lr 1e-5, 5 epoch), nên ngưỡng tuned rất thấp và `clm_noul_aug` mặc định lúc đó gán 5–8 nhãn cho mỗi bài public thử. Hệ thống cuối `final_system` mặc định là `probe_aug` (tốt nhất trên OOF gold); lưới lr đã được chạy local, xem đoạn dưới.
- `Lỗi edge case` F1 = 0 ở mọi hệ thống: gold chỉ có 0 ví dụ dương, và 8 mẫu chèn lỗi.
- Các số @tuned lạc quan vì ngưỡng được chọn trên chính OOF.

**Lưới lr (chạy lại 2026-10-11, embedding lấy hoàn toàn từ cache: 0 lần encode mới, 57 giây tổng, CV 40.7 giây, bộ nhớ đỉnh 4.41 GB).** Macro-F1 OOF @tuned trên 32 gold:
- `clm_noul`: lr 1e-5 → 0.247, 1e-4 → 0.225, 1e-3 → 0.230 → chọn 1e-5.
- `clm_noul_aug`: lr 1e-5 → 0.278, 1e-4 → 0.245, 1e-3 → 0.256 → chọn 1e-5.
Lr lớn hơn không cải thiện với 5 epoch và khoảng 26 bài train mỗi fold, nên head CLM fine-tune không vượt zero-shot (0.266) một cách đáng kể; hệ thống cuối vẫn là `probe_aug` (OOF tốt nhất). Với ngưỡng tuned từ OOF (một số nhãn có ngưỡng rất thấp, ví dụ 0.05), `probe_aug` gán 4–8 nhãn cho mỗi bài trong 6 bài public thử. Đây chỉ là quan sát, không được dùng để chọn cấu hình (quy định không dùng dữ liệu test). Giải pháp hợp lệ là chọn ngưỡng hoặc ràng buộc trên gold (ví dụ giới hạn số nhãn tối đa theo phân bố số nhãn của gold), hoặc hỏi giảng viên.

## Rủi ro / hạn chế
- Hướng 1: 6 bài val, khác đề thi: số đo rất nhiễu (cụm "6 bài val" chỉ áp dụng cho Hướng 1).
- CV chia theo bài, mà gold chỉ gồm đề EX01/EX02, nên OOF đánh giá quá cao khả năng tổng quát hóa sang 6 đề thi của cuộc thi.
- Nhiễu của augmentation: `remove_edge_guard` trúng 2 nhánh không phải guard trong 8 trường hợp thật (EX01-S110, EX01-S115); `hardcode_return` cũng đổi logic (chủ ý thiết kế).
- Ngưỡng và lr chọn trên OOF nên lạc quan; chúng đến từ model fold (~75% gold) nhưng áp cho model cuối train trên toàn bộ gold + mẫu chèn lỗi.
- `Lỗi edge case` không có ví dụ dương trong gold.
- Chỉ 32 bài gold để train và đánh giá: phương sai CV lớn; ngưỡng chọn trên OOF có thể không ổn định giữa các fold.
- Lỗi chèn nhân tạo có thể khác cách giảng viên gán nhãn; so `*_aug` với bản không aug trong ablation trước khi kết luận
  augmentation có lợi. Nên hỏi giảng viên xác nhận augmentation từ bộ mẫu.
- MLX 4-bit là bản chuyển đổi không chính thức (~91% đồng thuận top-1 với bản gốc).
- Macro-F1 chính theo quy ước sklearn (nhãn vắng = 0); báo cáo thêm `macro_f1_skip_absent`.

## Câu hỏi cho giảng viên
- (a) Có được sinh dữ liệu augmentation từ code của các bài mẫu có nhãn (sample_dataset) không?
- (b) Có được dùng sàn tỉ lệ dự đoán 2% tính trên tập dự đoán public (không nhãn, không đầu ra LLM) không?
- (c) Có được chọn cấu hình cuối bằng điểm leaderboard public không?
