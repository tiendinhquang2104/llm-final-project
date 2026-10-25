# Task 2 — Kế hoạch Local LLM + Fine-tune (bản kỹ thuật)

Mục tiêu: hệ thống Task 2 dùng mô hình open-weight ≤ 10B **được fine-tune**, có macro-F1 cao hơn zero-shot CoT
hiện tại, chạy trọn vẹn (train + predict) trên Kaggle 2×T4 và chạy suy luận được trên máy local.

## 1. Yêu cầu của thầy → cách đáp ứng

| Yêu cầu (`docs/requirements/task2.md`) | Cách đáp ứng |
|---|---|
| ≥ 2 hướng, trong đó 1 hướng prompting | Hướng P: zero-shot CoT hiện có (`cot_split_run_en`), giữ làm baseline |
| ≥ 1 mô hình open-weight ≤ 10B được fine-tune | Hướng F: `Qwen2.5-Coder-7B-Instruct` + QLoRA, 2 biến thể (mục 3) |
| Chạy được cục bộ, báo cáo phần cứng | Train trên Kaggle T4; suy luận local trên M3 Pro 18GB qua MLX (mục 7) |
| Pipeline tự động, không can thiệp từng bài | Một notebook Kaggle: dữ liệu → train → predict → `predictions.json` |
| Cố định seed, ghi phiên bản model | `seed=42`, ghi `revision` của HF; bundle ghi hash prompt/config/adapter |
| Cấm dùng trường feedback làm input | Input chỉ gồm đề bài, code, kết quả compile/chạy do mình tự sinh |
| Không gán nhãn test (kể cả bằng LLM) | Không train, tune ngưỡng hay chọn model theo public; nhãn tham chiếu public chỉ để quan sát |
| Metric chính macro-F1 | Mọi lựa chọn (ngưỡng, epoch, biến thể) tối ưu theo macro-F1 out-of-fold trên gold |

Ràng buộc dữ liệu đi kèm:
- Code public test không làm base để chèn lỗi.
- Mọi mẫu train có MinHash Jaccard < 0.5 với mọi file public.
- Không commit dữ liệu, `data/public-test`, `docs/requirements/` hay Drive id.

## 2. Chẩn đoán hiện trạng (vì sao zero-shot thấp)

- Zero-shot Qwen7B (`predictions_en`) đạt **0.18** trên public leaderboard. Bộ nhãn tham chiếu do Claude gán theo luật đạt **0.35**.
  - Mức 0.35 xấp xỉ trần của "quy ước gán nhãn của mình" so với nhãn thật của thầy.
  - Hệ thống fine-tune nên đặt mục tiêu 0.28–0.35 trên public. Vượt mức này đòi hỏi bắt được quy ước riêng của thầy.
- CLM probe (Qwen3-8B đóng băng + head) đạt macro-F1 **0.30** out-of-fold trên gold.
  - Có xác suất từng nhãn và ngưỡng tuned là lợi thế lớn với macro-F1.
- Zero-shot generative có 3 điểm yếu:
  - không có xác suất nên không chỉnh được ngưỡng theo nhãn;
  - prompt dài (~1.5k token luật) nên dễ loãng;
  - model không học được quy ước của thầy (ví dụ "logic" chiếm 12/32 bài gold, "edge case" 0/32).
- **Kết luận thiết kế:** fine-tune phải cho ra **xác suất từng nhãn** để chỉnh ngưỡng theo nhãn. Kết hợp với lớp luật
  tất định từ kết quả chạy thật (compile, format, timeout, hard-code tên file) vì các tín hiệu này gần như chắc chắn.

## 3. Kiến trúc đề xuất

```
đề + code ──► Lớp tín hiệu tất định (đã có: src/task2/compile.py, split.py)
              compile OK/FAIL, chạy ví dụ đề (pass/format/timeout/crash), toàn bộ bị comment,
              hard-code tên file, câu chưa làm (stub)
                 │
                 ▼
          Prompt gọn (≤ 2k token): danh sách nhãn + đề + code đánh số dòng + tóm tắt tín hiệu
                 │
       ┌─────────┴──────────┐
       ▼                    ▼
  F-cls (chính)        F-gen (phụ, giải thích được)
  Qwen7B + LoRA        Qwen7B + LoRA SFT
  + head 10 sigmoid    "lý do ngắn → dòng nhãn"
  → p(nhãn)            → k mẫu → tần suất nhãn
       └─────────┬──────────┘
                 ▼
     Ensemble xác suất → ngưỡng từng nhãn (OOF trên gold)
                 ▼
     Hậu xử lý theo luật gold: compile FAIL ⇒ "Lỗi biên dịch" (+ ≤ 1 nguyên nhân);
     bị comment toàn bộ ⇒ "Lỗi style"; câu không làm ⇒ không nhãn; P1 sai ⇒ chỉ nhãn của P1;
     tối đa 3 nhãn
                 ▼
            predictions.json
```

- **F-cls** (`Qwen2ForSequenceClassification`, multi-label, loss BCE có `pos_weight`):
  - một lần forward mỗi bài, không cần sinh văn bản: train nhanh, predict 360 bài chỉ mất vài phút;
  - ra trực tiếp xác suất, chỉnh ngưỡng được.
  - Đây là bản nâng cấp tự nhiên của CLM probe (0.30): backbone được tinh chỉnh thay vì đóng băng.
- **F-gen:** SFT sinh "lý do ngắn + nhãn", tái dùng parser và pipeline CoT hiện có.
  - Có lý do kèm số dòng, hữu ích cho báo cáo, phân tích lỗi và Task 3.
  - Xác suất lấy từ self-consistency (k = 5 mẫu).
- **Chấm từng câu cho multi-problem:** áp dụng cho cả hai biến thể, đã có `split.py` + `merge_parts`.
  - Nhãn từng câu lấy từ `why` (đã ghi "P2 …; P3 …") và `per_question_defects` trong provenance.
  - Bước này để giai đoạn 2, nếu giai đoạn 1 còn thời gian.

## 4. Dữ liệu

| Nguồn | Số mẫu | Vai trò |
|---|---|---|
| synth v1 train | 477 | train (nhãn theo tiêu chí mới, có 22 "Lỗi thuật toán") |
| synth v1 heldout | 65 | train (4 đề khác, thêm 6 "Lỗi thuật toán") |
| chèn lỗi trên code gold (`src/task2/augment.py`, 10 mutator) | ~200–400 | train, **chia theo đề EX01/EX02** cho fold |
| gold 32 bài | 32 | **chỉ đánh giá** (out-of-fold) |
| public 360 bài | 360 | chỉ suy luận; nhãn tham chiếu chỉ để quan sát |

Việc cần làm (`scripts/build_task2_sft.py` → `data/sft/task2/*.jsonl`, gitignored):

1. **Dùng chung một hàm dựng input cho train và suy luận** (tránh lệch train/serve).
   - Input gồm đề bài, code đánh số dòng và tóm tắt tín hiệu: `exec_report` cho synth; compile + chạy ví dụ đề cho gold/public.
2. **Đóng khoảng cách miền:** synth ngắn (trung vị 484 ký tự), gold/public dài (918/706, tối đa 8k).
   - Chèn lỗi trên code gold là nguồn code thật duy nhất được phép dùng.
   - Ghi trọng số mẫu gold-mutant ×2 khi train.
3. **Cân bằng nhãn cho macro-F1:**
   - `pos_weight` theo tần suất từng nhãn (giới hạn ≤ 10);
   - oversample bài có nhãn hiếm ("thuật toán", "hàm", "style");
   - giữ khoảng 20% bài nhãn rỗng.
4. **Giới hạn độ dài:** max 4096 token, cắt code theo dòng (giữ hàm của câu đang chấm) nếu vượt.
   - Kiểm tra p95 độ dài trước khi train.
5. **Guard:** MinHash Jaccard < 0.5 với mọi file public; không trùng `sample_id`; in phân bố nhãn sau trộn.
6. **Nhãn từng câu** (giai đoạn 2): parse `why` thành `{P1..P4: nhãn}`, kiểm tra hợp nhất lại khớp nhãn cả bài.

## 5. Huấn luyện trên Kaggle

| Mục | F-cls | F-gen |
|---|---|---|
| Thư viện | transformers + peft + bitsandbytes | transformers + peft + trl (`SFTTrainer`) hoặc Unsloth |
| Lượng tử hoá | 4-bit nf4, compute fp16 (T4 không có bf16) | như F-cls |
| LoRA | r=16, α=32, dropout 0.05, all-linear; `modules_to_save=["score"]` | r=16, α=32, all-linear |
| lr / epoch | 1e-4 (lưới {5e-5, 1e-4, 2e-4}) / 4 | 1e-4 / 3 |
| batch | 1 × grad-accum 16, gradient checkpointing | như F-cls |
| loss | BCE + `pos_weight` | CE chỉ trên phần assistant |
| seed | 42 | 42 |

- **Tận dụng 2 GPU:** mỗi T4 train một fold song song (fold EX01 trên GPU0, fold EX02 trên GPU1), rồi train model final trên toàn bộ.
  - Mỗi lần train ước khoảng 1–1.5h (F-cls) và 2–3h (F-gen).
- **Ngân sách Kaggle** (30h GPU/tuần, phiên 12h):
  - chạy F-cls trước (rẻ, kỳ vọng tốt nhất), sau đó F-gen;
  - lưu adapter mỗi 50 step vào `/kaggle/working`, xuất làm Kaggle Dataset để phiên sau dùng tiếp.
- **Không early-stop:** không có tập val riêng. Số epoch và lr chọn bằng OOF trên gold, chỉ trong lưới nhỏ (≤ 6 cấu hình)
  để tránh overfit vào 32 bài.

## 6. Suy luận, ngưỡng, hậu xử lý

1. **F-cls:** forward 1 lần/bài (hoặc 1 lần/câu nếu multi-problem), ra `p ∈ [0,1]^10`.
2. **F-gen:** vLLM `enable_lora=True`, `max_num_seqs=32`, `gpu_memory_utilization=0.85` (cấu hình đã chạy được trên T4).
   - Sinh k=5 mẫu, xác suất = tần suất nhãn.
3. **Ensemble:** `p = w·p_cls + (1−w)·p_gen`, với w ∈ {1, 0.7, 0.5} chọn theo OOF.
4. **Ngưỡng từng nhãn:**
   - quét trên xác suất OOF của gold (đã có `src/task2/thresholds.py`, ràng buộc `min_rate`);
   - nhãn không xuất hiện trong gold ("edge case") dùng ngưỡng mặc định cao.
5. **Hậu xử lý theo luật gold** (`docs/task2_teacher_rules.md`, đã cài trong `pipeline._postprocess_*`).
   - Luật tất định ghi đè xác suất khi tín hiệu chắc chắn (compile FAIL, bị comment toàn bộ).

## 7. Chạy local và báo cáo phần cứng

- **Máy:** Apple M3 Pro 18GB. Mô hình 4-bit khoảng 4.5GB.
- **F-gen:** chuyển adapter PEFT sang MLX (`mlx_lm.fuse` / convert), chạy bằng backend MLX đã có (`configs/task2/run_cot.yaml`).
- **F-cls:** viết khoảng 50 dòng MLX:
  - lấy hidden state token cuối của `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` (đã fuse LoRA);
  - nhân với trọng số head `score` xuất từ PEFT.
  - So khớp với kết quả Kaggle trên 32 bài gold (sai khác xác suất < 1e-2).
- **Báo cáo:** VRAM/RAM đỉnh, giây/bài, thời gian train, phiên bản thư viện (`outputs/task2/benchmark.md` đã có cột sẵn).
- **Phương án dự phòng:** nếu 7B quá chậm ở local, train thêm `Qwen2.5-Coder-3B-Instruct` làm dòng ablation kích thước model.

## 8. Đánh giá và quy trình chọn hệ thống

- **Metric chính:** macro-F1 out-of-fold trên 32 bài gold (2 fold theo đề), kèm micro-F1, F1 từng nhãn, khoảng tin cậy
  bootstrap 95% (32 bài, dao động lớn).
- **Quy trình chọn:**
  - chỉ chọn theo OOF gold;
  - public chỉ để quan sát sau khi đã chọn;
  - mỗi ngày nộp tối đa 2 lượt, hệ thống nộp phải là hệ thống đã chốt.
- **Điều kiện "tốt hơn":** OOF macro-F1 của hệ thống F ≥ baseline P + 0.05, và không nhãn nào tụt về 0 mà baseline có điểm.

## 9. Ablation (15% điểm) — làm theo thứ tự ưu tiên

| # | Hệ thống | Câu hỏi trả lời |
|---|---|---|
| 0 | P: zero-shot CoT | mốc xuất phát |
| 1 | F-cls, chỉ synth | fine-tune có thắng prompting không |
| 2 | F-cls + gold-mutant | code thật có giúp không |
| 3 | #2 bỏ tóm tắt tín hiệu chạy | đóng góp của compile/chạy thật |
| 4 | #2 bỏ `pos_weight`/oversample | cân bằng nhãn với macro-F1 |
| 5 | #2 ngưỡng 0.5 vs ngưỡng tuned | đóng góp của ngưỡng theo nhãn |
| 6 | F-gen (lý do + nhãn) | generative vs classification |
| 7 | ensemble F-cls + F-gen (+ luật) | hệ thống final |
| 8 | Qwen-3B vs 7B | kích thước model, tốc độ local |

## 10. Lịch triển khai (khoảng 2 tuần)

| Ngày | Việc | Sản phẩm |
|---|---|---|
| 1 | Baseline P trên gold OOF + public quan sát; khoá bộ đánh giá | dòng #0 trong `benchmark.md` |
| 2–3 | `build_task2_sft.py`: hàm dựng input chung, gold-mutant theo fold, cân bằng, guard | `data/sft/task2/*.jsonl` + thống kê |
| 4–5 | `src/training/train_task2_cls.py` + notebook `kaggle/task2_ft.ipynb`; train 2 fold song song | #1, #2 |
| 6 | Ngưỡng từng nhãn + hậu xử lý; ablation #3–#5 | bảng ablation phần F-cls |
| 7–8 | `src/training/train_task2_sft.py` (F-gen) + LoRA trong vLLM | #6 |
| 9 | Ensemble + chốt hệ thống theo OOF; nộp public | #7, `predictions.json` |
| 10–11 | Chạy local MLX + báo cáo phần cứng; (tuỳ chọn) 3B | #8, mục phần cứng |
| 12–14 | Bundle tái lập, nhãn từng câu (giai đoạn 2 nếu kịp), phân tích lỗi, viết báo cáo | bundle + báo cáo |

## 11. Rủi ro và cách giảm

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Model học quy ước synth (Claude gán), lệch quy ước thầy | Cao | gold-mutant giữ nhãn gốc của thầy; ngưỡng theo OOF gold; báo cáo agreement |
| 32 bài gold quá ít để chọn cấu hình | Cao | lưới nhỏ, bootstrap CI, không chọn theo public |
| Hết quota / timeout Kaggle | Trung bình | F-cls trước, checkpoint 50 step, adapter lưu thành Dataset |
| OOM trên T4 | Trung bình | 4-bit, batch 1, gradient checkpointing, max_seq 4096 (vLLM: `max_num_seqs=32`) |
| Lệch train/serve (prompt khác nhau) | Trung bình | một hàm dựng input duy nhất + test so khớp |
| Local không chạy nổi 7B | Thấp | 4-bit MLX khoảng 4.5GB vừa 18GB; dự phòng 3B |

## 12. Điểm thưởng (vấn đề dữ liệu, tối đa +10%)

Ghi lại bằng chứng định lượng trong lúc làm:
- "Lỗi edge case" xuất hiện 0/32 trong gold, gần như suy biến.
- Cùng một lỗi (hàm tính mũ sai) được gán 3 kiểu nhãn khác nhau (S207/S213/S204).
- Phân bố nhãn rất lệch, khiến macro-F1 nhạy với 1–2 bài.
- Đề xuất: gộp/định nghĩa lại nhãn và báo cáo macro-F1 chỉ trên các nhãn có hỗ trợ.

## 13. Quyết định cần chốt

1. **F-cls làm hướng chính, F-gen phụ** (khuyến nghị) — hay chỉ làm F-gen như plan cũ?
2. Dùng gold-mutant trong train (kèm 2 fold theo đề) — khuyến nghị **có**.
3. Thêm `peft`, `trl`, `bitsandbytes`, `accelerate` vào requirements cho Kaggle (local chỉ cần `mlx-lm`, đã có).

## 14. Cách chạy F-cls (đã cài đặt, nhánh `task-2-fcls`)

| Bước | Lệnh / file |
|---|---|
| Dữ liệu | `python scripts/build_task2_cls_data.py` → `data/sft/task2_cls/records.jsonl` (gitignored). Nguồn synth: `data/synth/v1/generate-dataset_v3.zip` |
| Train 1 run | `python scripts/train_task2_cls.py --holdout EX01|EX02|all --deadline <unix>` → `outputs/task2/cls/task2_cls_qwen7b__<holdout>/` |
| Đánh giá + nộp | `python scripts/eval_task2_cls.py` → `report.md`, `metrics.json`, `predictions.json` |
| Kaggle | `kaggle/task2_cls.ipynb` (2 fold song song trên 2 T4, rồi run `all`) |
| Code | `src/task2/cls_data.py` (record, fold, oversample, pos_weight), `src/task2/cls_post.py` (ngưỡng + luật gold), `src/training/task2_cls.py` (QLoRA, checkpoint/resume, predict) |
| Test | `tests/test_task2_cls.py` (có test train/pause/resume/predict với model tí hon trên CPU) |

Checkpoint và resume trên Kaggle:
- `save_steps` (25): lưu adapter + optimizer + scheduler vào `<run>/checkpoints/`.
- `--deadline`: lưu rồi dừng sạch trước giới hạn phiên (exit 3, `status.json` = `paused`).
- Lần chạy sau: thêm output của version trước làm Input. Notebook chép các run đã có về `/kaggle/working/cls`, rồi resume từ checkpoint mới nhất.
- Run đã `done` thì bỏ qua. Tuỳ chọn mirror checkpoint lên HF Hub (`--hub-repo`, `HF_TOKEN`).
