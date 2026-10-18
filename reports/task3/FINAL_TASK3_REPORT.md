# Báo cáo cuối Task 3

**Trạng thái: PARTIAL**
**Run ID:** `20261018T033618Z`
**Thời điểm:** 2026-10-18 (UTC)

## Tóm tắt điều hành

Đã xác thực zero-shot baseline, audit dữ liệu/tokenizer, chạy GPU preflight, huấn luyện Qwen thật với smoke 20 bước, huấn luyện hai adapter QLoRA cùng ngân sách 300 bước, suy luận oracle trên cùng 6 mẫu `real-val`, đánh giá độc lập và tổng hợp guard theo Level. GPU là RTX 5090, workload-isolation check báo không có process cạnh tranh; không có workload nào bị dừng hay sửa đổi.

Hai adapter đạt 6/6 lượt đầu qua heuristic guard trên validation nhỏ; điều này **không** chứng minh chẩn đoán đúng. Chưa có human annotation để đánh giá chất lượng chẩn đoán, và chưa tìm thấy Task 2 prediction export có provenance để chạy taxonomy-predicted/public. Vì vậy chưa thể chọn adapter phát hành.

## Môi trường và provenance

| Thuộc tính | Giá trị đã kiểm tra |
|---|---|
| Git | `feat/task3-qwen-feedback`, commit `2c2f011e7f1d7a46b4e3a4a4494ce42b7cbe730f` |
| Python / PyTorch | Python 3.12.3 / `2.8.0+cu128` |
| CUDA | PyTorch runtime 12.8; driver 590.48.01, `nvidia-smi` báo CUDA 13.1 |
| Thư viện | Transformers 4.57.1, PEFT 0.17.1, bitsandbytes 0.48.1, pytest 8.4.2 |
| GPU | NVIDIA GeForce RTX 5090, 32 GiB; BF16 hỗ trợ |
| Model | `Qwen/Qwen2.5-Coder-7B-Instruct`, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242` |
| Seed / config | Seed 42; `configs/task3/qlora_5090.yaml`, `configs/task3/baseline.yaml` |
| SHA-256 config | baseline `9a01fed5d6f08b54733da296379d57e033bcc51b2fe356cfa5efcdffd0dd4a22`; few-shot `d136c8a2648487528a2ffaa8caeaf592548787b5a40022e609569cc512e5650f`; QLoRA `4de631fc67bc1267fae96c393601d5a063ef4653859ec65f14469e3da24b8469` |
| Manifest dữ liệu | `42a6f6d35b0ec87246e2e28018f48a1c46b25d71f5c534d71fc571dce8693fc8` |

Working tree có thay đổi Task 3 tại `src/task3/train.py` và `tests/test_task3_train.py` do sửa smoke audit; file `task3-autopilot.agent.md` đã tồn tại dưới dạng untracked và được giữ nguyên. Artifacts được ghi vào thư mục run riêng, không ghi đè baseline/checkpoint cũ.

## Trạng thái các phase

| Phase | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|
| 0. Repo, tooling, tests | COMPLETE | Task 3 tests: 148 passed, 1 skipped; Ruff và `git diff --check` pass |
| 1. Data và tokenizer | COMPLETE | Manifest strict, checksum partitions đúng, split real 26/6 disjoint; context train 4096 |
| 2. Zero/few-shot baseline | COMPLETE | Zero-shot artifacts hiện hữu được xác minh; few-shot Qwen vừa chạy trên 6 validation IDs |
| 3. GPU preflight và Qwen smoke | COMPLETE | CUDA/NF4 pass; Qwen thật 20/20 bước, update audit và adapter reload pass |
| 4. Fine-tuning | COMPLETE | E1 synthetic-only và E2 mixed-balanced đều đạt đúng 300/300 bước |
| 5. Matched inference/evaluation | COMPLETE | 4 cấu hình, cùng 6 ID `real-val`, gold taxonomy; artifact alignment được kiểm tra |
| 6. Guard audit | COMPLETE | Tổng hợp trace và kiểm tra lại 32 instructor targets; raw rejected text không có |
| 7. Human review, Task 2 và public | BLOCKED_DATA / NOT MEASURED | Không có annotation đã chấm hay Task 2 export đã xác minh; public inference không chạy |
| 8. Báo cáo | COMPLETE | Tài liệu này; machine-readable ledger ở `outputs/task3/autopilot/20261018T033618Z/run_state.json` |

## Dữ liệu và tokenizer

| Partition | Số mẫu |
|---|---:|
| real-train / real-val | 26 / 6 |
| synthetic-train / synthetic-heldout | 496 / 47 |
| public / quarantine | 328 / 134 |

Manifest `filter_synthetic=strict`, `schema_mismatches=0`; 26/6 ID split cố định, giao rỗng. Tất cả sáu `processed_sha256` khớp nội dung file. Public có 328 mẫu và không có completion target. Quarantine có 134 mẫu; manifest ghi các reason counts gồm `signal_contradiction_clean=45`, `signal_contradiction_compile_fail=10`, `gold_compliance:repair_guidance=9`, `placeholder_level4=40`, `gold_compliance:specific_diagnosis=4` (reason có thể chồng lấp). Các số này thuộc manifest hiện tại; docs có số cũ 505 synthetic-train/125 quarantine và không khớp đầu vào hiện hành.

Tokenizer Qwen được pin đúng revision: audit train+validation gồm 528 record; 515 fit 2048 token, 13 vượt 2048; cả 528 fit 4096, max 3755 token, không target nào bị cắt. `auto` chọn 4096. Audit prompt real-val cho zero-shot, few-shot, E1 và E2 đều pass, 0/6 bị chặn. Few-shot dùng context 8192 và `few_shot_k=2`, nên không phải đối chứng context-matched với zero-shot 4096.

## Baseline zero-shot

`outputs/task3/zero.heldout.*` được giữ nguyên. Run manifest là `GENERATED`, split/hash/revision khớp local data, 47 prediction và trace ID duy nhất, đúng thứ tự; `test_only_mock=false`. Evaluator độc lập tái tạo các số sau:

| Level | n | First-pass guard pass | Severe L1/L2 flag lần đầu | Fallback | Retry cứu được | Final heuristic pass |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 22 | 0 | 21 | 22 | 0 | 22 |
| 2 | 15 | 3 | 12 | 11 | 1 | 15 |
| 3 | 6 | 2 | 0 | 4 | 0 | 6 |
| 4 | 4 | 4 | 0 | 0 | 0 | 4 |
| **Tổng** | **47** | **9** | **33/37 Level 1–2** | **37** | **1** | **47** |

37/47 generation dùng fallback sau retry; 75 retry tổng cộng. Trung bình latency 5.489 s, p50 5.664 s, p95 11.042 s; 21,090 output tokens cộng trên các lần thử. Tất cả 47 final output qua heuristic guard, nhưng đây chủ yếu là post-fallback compliance, không phải tỷ lệ model thành công.

Violation trên **first attempt** (các cờ có thể đồng thời xuất hiện): L1 `code_like` 21, `identifier` 18, `specific_diagnosis` 17, `code_fence` 14, `code_solution_leak` 14; L2 `code_fence`/`code_like`/`code_solution_leak` mỗi loại 12, `repair_guidance` 10; L3 `code_block_gt_1_line` 4 và `complete_solution` 1. Trace không lưu rejected raw text, nên các nhãn này không được coi là xác nhận rò rỉ ngữ nghĩa.

Cross-tab heldout: `single_problem` 5/30 first-pass, 22 severe flags L1/L2, 25 fallback; `multi_problem` 4/17 first-pass, 11 severe flags, 12 fallback. Cả hai nhóm là aggregate nhỏ và chỉ mô tả heuristic.

## QLoRA và hiệu năng

GPU preflight artifact `outputs/task3/autopilot/20261018T033618Z/gpu-preflight.json`: status `passed`, một RTX 5090, BF16, 33,122,680,832 byte free trước run, isolation `available`, 0 process ngoài; CUDA matmul và NF4 LoRA forward/backward/update đều pass.

| Run | Steps | Train rows / source sample | Train loss | Eval loss trên real-val | p50 / p95 step (s) | Peak allocated / reserved (GiB) | Wall time | Throughput samples/s |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| Qwen smoke, mixed-balanced | 20 | 522 / real+synthetic | 2.523 | 1.949 | 2.471 / 3.366 | 16.85 / 21.28 | 58.83 s | 1.62 |
| E1 synthetic-only | 300 | 496 synthetic | 0.430 | 2.037 | 1.591 / 1.827 | 11.64 / 15.93 | 508.76 s | 2.51 |
| E2 mixed-balanced | 300 | 522 unique (26 real, 496 synthetic) | 0.491 | 1.355 | 2.234 / 3.280 | 16.70 / 21.23 | 713.14 s | 1.76 |

Các run dùng cùng model revision, seed 42, BF16, context 4096, LoRA config và effective batch size 4; cả hai full run đạt đúng ngân sách đã khai báo trước. Mỗi run ghi 40,370,176 trainable LoRA parameters và 4,352,972,288 frozen base parameters. E1 ghi nguồn synthetic 496; E2 ghi 260 synthetic/262 real trong sampling histogram, gần 50/50. Với chỉ 26 real-train ID, mixed-balanced lặp lại ví dụ real khoảng 10 lần trung bình; đây là rủi ro oversampling, không phải 262 ví dụ real độc lập.

Smoke xác nhận finite nonzero gradient, parameter update `max_abs_delta=0.001004`, và adapter reload `PASS`; train/eval loss finite. E1/E2 adapter tồn tại và được load thành công ở inference. Loss thấp hơn không tự chứng minh feedback tốt hơn.

### Failure được điều tra

Checkpoint cũ `checkpoints/task3/qlora_5090_smoke/run.json` thất bại ở bước 20 vì `parameter_update_audit.max_abs_delta=0.0`, dù gradient hữu hạn và khác 0. `train.py` chỉ chốt audit ngay sau optimizer step đầu tiên, khi warmup learning rate là 0. Đã chuyển phép so sánh từ snapshot ban đầu sang cuối smoke (`on_train_end`) và thêm regression test cho trường hợp bước warmup không đổi tham số nhưng bước sau có update. Smoke mới pass. Checkpoint cũ được giữ nguyên.

Các artifact lịch sử khác cũng được giữ, không trộn vào benchmark mới: `checkpoints/task3/exp_synthetic/run.json` là COMPLETE 372 bước; `checkpoints/task3/exp_mixed_balanced/run.json` còn `STARTING`, thiếu completion metrics, nên không dùng làm kết quả.

## So sánh matched inference

Cùng 6 real-val IDs theo thứ tự, gold taxonomy, greedy decoding, max retries 2; E1/E2 dùng adapter và baseline decoding config. Level phân bố `L1=2, L2=3, L3=1, L4=0`; vì vậy không có bằng chứng validation cho Level 4.

| Cấu hình | First pass | Severe L1/L2 flags | Fallback | Final guard | Retries | Mean / p50 / p95 latency (s) | Output tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| Zero-shot | 3/6 | 3/5 | 3/6 | 6/6 | 6 | 4.501 / 2.275 / 12.163 | 2,137 |
| Few-shot (`k=2`) | 5/6 | 1/5 | 1/6 | 6/6 | 2 | 1.027 / 0.680 / 3.116 | 271 |
| E1 synthetic-only | 6/6 | 0/5 | 0/6 | 6/6 | 0 | 2.344 / 0.669 / 10.550 | 647 |
| E2 mixed-balanced | 6/6 | 0/5 | 0/6 | 6/6 | 0 | 0.523 / 0.453 / 1.111 | 93 |

Mọi trace/prediction có 6 ID duy nhất, cùng thứ tự; mọi inference là `GENERATED`, `test_only_mock=false`, data-manifest hash khớp. Adapter directory fingerprints trong run manifest khớp fingerprint tính lại từ toàn bộ file adapter. Latency p95 dùng nearest-rank trên n nhỏ; token totals gồm mọi generation attempt. E2 output ngắn hơn đáng kể, không phải bằng chứng chất lượng; không chọn model chỉ theo latency, loss hay guard pass.

Raw first-pass theo Level: zero-shot L1 1/2, L2 1/3, L3 1/1; few-shot L1 2/2, L2 2/3, L3 1/1; E1 và E2 đều L1 2/2, L2 3/3, L3 1/1. Với n=6, khác biệt này chỉ mang tính mô tả, chưa có ý nghĩa khái quát.

## Guard và phân tích nguyên nhân

- **A. Model oversharing:** Trace zero-shot heldout gắn severe heuristic flag cho 33/37 phản hồi Level 1–2 lần đầu. Đây là tín hiệu cần review, không phải khẳng định nội dung raw vi phạm thật; raw rejected generation không được lưu.
- **B. Prompt/retry:** Retry hint hiện là chỉ dẫn chung, không nêu violation cụ thể. Heldout có 75 retry nhưng chỉ 1 ca được retry cứu thành model response qua guard; 37 fallback. Mẫu này ủng hộ thử nghiệm prompt/retry có mục tiêu sau review, nhưng chưa tách được nguyên nhân model, prompt và sampling.
- **C. False positive/guard quá chặt:** Chưa thể xác nhận hoặc bác bỏ vì không có raw text. `code_block_gt_1_line` ở Level 3 là ứng viên cần người đánh giá xem xét, không được tự ý nới guard. Fallback chung qua mọi Level chỉ cho thấy output không vi phạm heuristic, không cho biết chất lượng chẩn đoán.
- Guard nguyên bản pass lại **32/32** instructor targets (L1 4, L2 18, L3 10), không có cờ. Bộ test Task 3 pass 148, skip 1. Không thay prompt/guard policy trong run này; chỉ sửa smoke update audit.

## Human review, Task 2 và giới hạn

Diagnosis correctness, evidence support, hallucinated-error rate, Level appropriateness, inter-rater agreement và chất lượng Level 4: **NOT MEASURED**. CSV review hiện tại là worklist 6 ID mỗi run, không có điểm human; không tìm thấy annotation đã hoàn tất. Cần hai reviewer chấm độc lập bằng dữ liệu riêng tư tại máy cục bộ.

Không tìm thấy Task 2 prediction export có `parse_ok` provenance cho validation/public. Vì vậy taxonomy-predicted inference, error propagation và public inference 328 ID đều **BLOCKED_DATA / NOT RUN**; không tự thay missing labels bằng `[]`. Official validator không có trong workspace; chỉ có local schema/evaluator.

Giới hạn chính: validation chỉ 6 mẫu và không có Level 4; synthetic target quality chưa được giáo viên xác thực đầy đủ; train mix lặp lại real examples; trace cố ý không giữ raw rejected text; heuristic guard không đo semantic correctness; generated code Level 4 chưa được compile/human review; few-shot đổi đồng thời số demo và context 8192.

## Artifacts và tái lập

Run ledger/plan/commands: `outputs/task3/autopilot/20261018T033618Z/`. Toàn bộ JSON/JSONL phát sinh trong run/checkpoint trees đã parse được; 90 JSON, 3 JSONL progress files, mỗi progress file có 6/6 entry hoàn tất. Các review CSV không có human score. Checksums chính:

| Artifact | SHA-256 |
|---|---|
| GPU preflight JSON | `beb763c58fe494f616c6b26d7136d28a851291502e816185d7c76006d9cfffe2` |
| Qwen smoke run.json | `5f3c3641da5a8f10ca5b2e5404a478fde8362400408007705c99cd00dd653cd4` |
| E1 training run.json | `eb427f4e4693814205e988182046e3302a2ecea00abbcd2313241d4b900a6d2b` |
| E2 training run.json | `47ab6a02467d0bad0ddf97e0ee002498eb4b450caf16c651faf8f8b9497c2acc` |
| Zero-shot heldout traces | `57eb8044e2cacc3ff59edd1f9f150eafd94e1ca793bacbe1198402a65396a229` |
| E1 adapter directory fingerprint | `97dc67c7a9eee0f3ee8852ee9c4b718e1f099661b3c5b825e1148ab0b6e8620f` |
| E2 adapter directory fingerprint | `cc668a6977b479d7a713642a4025aa01e4c24df31b33937e1d41650189426360` |

Các lệnh fine-tune đã chạy:

```bash
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --output-dir checkpoints/task3/autopilot-smoke-20261018T033618Z --max-steps 20 --smoke-test
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --experiment synthetic --max-steps 300 --output-dir checkpoints/task3/autopilot-20261018T033618Z-synthetic
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --experiment mixed_balanced --max-steps 300 --output-dir checkpoints/task3/autopilot-20261018T033618Z-mixed_balanced
```

Inference/evaluation sidecars (`.json`, `.metrics.json`, `.traces.json`, `.run.json`, `.tokenizer-audit.json`, `.evaluation.json`, review template) được lưu cho zero, few-shot, E1 và E2 trong `outputs/task3/autopilot/20261018T033618Z/`, ngoại trừ zero-shot baseline gốc được tham chiếu tại `outputs/task3/zero.oracle.*`. Command log đã lọc chỉ chứa commands/aggregate status, không chứa source code, target feedback hoặc raw generations.

## Ưu tiên tiếp theo

1. **P0: Human review** các worklist zero/few/E1/E2 trên cùng 6 ID; ưu tiên Level 1–2 và xác thực mức độ chẩn đoán. Không chọn adapter trước khi có điểm diagnosis/evidence.
2. **P0: Task 2 owner cung cấp export provenance đầy đủ** cho đúng IDs và labels; sau đó chạy predicted-taxonomy real-val, đo propagation, rồi mới quyết định public run.
3. **P1: Tăng real validation** theo exam type và Level, đặc biệt Level 4; giữ heldout tách biệt khỏi tuning.
4. **P1: Human audit rejected generations/fallback causes** trong môi trường local riêng tư; phân loại model oversharing, prompt failure và heuristic false positive trước khi sửa retry policy.
5. **P2: Kiểm tra thủ công/compile Level 4 output** và đánh giá few-shot với context/budget được kiểm soát.

**Khuyến nghị hiện tại:** chưa có model winner có thể bảo vệ về chất lượng sư phạm. E2 có eval loss thấp hơn và validation output ngắn/nhanh hơn trong mẫu nhỏ, nhưng diagnosis quality chưa được đo; giữ E1/E2 như ứng viên cho blind human review, không đưa vào public release.