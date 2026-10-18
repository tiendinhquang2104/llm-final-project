# Báo cáo kỹ thuật Task 3 Follow-up

**Trạng thái: PARTIAL**
**FOLLOWUP_ID gói ban đầu:** `20261018T044055Z`
**HEAD gói ban đầu:** `2c2f011e7f1d7a46b4e3a4a4494ce42b7cbe730f` (`feat/task3-qwen-feedback`)
**Real-val recovery:** `20261018T061615Z`, HEAD `238cf82b50b296810d6c31773d058b61900c36a5`
**Manifest:** `42a6f6d35b0ec87246e2e28018f48a1c46b25d71f5c534d71fc571dce8693fc8`
**Quyết định phát hành:** **NO VERIFIED WINNER**. E1/E2 cần human diagnosis review trước khi chọn; public inference bị chặn do không có Task 2 export đã xác minh.

## Tóm tắt

Đã độc lập kiểm tra artifacts smoke/E1/E2, manifest/partition checksums, regressions và diff; chạy real-Qwen E1/E2 trên cùng 47 synthetic-heldout IDs; đánh giá độc lập E0/E1/E2 heldout. Sau khi các raw real-val sources cũ biến mất, đã tái chạy E0/E0b/E1/E2 trên cùng sáu IDs dưới commit `238cf82b…` và lưu predictions, traces, manifests, tokenizer audits, evaluator outputs ở `outputs/task3/followup/20261018T061615Z/`. Không retrain, không sửa prompt/guard, không overwrite output cũ, không dừng workload GPU nào. Task 3 test hiện tại: 148 passed, 1 skipped; Ruff và `git diff --check` pass.

Phát hiện quan trọng: zero-shot heldout có raw first-pass thấp và fallback cao. E1/E2 giảm mạnh fallback theo heuristic. E2 real-val đúng là chỉ sinh 93 tokens/6 outputs, mean 40 chars; E2 heldout cũng ngắn hơn E1 trên cả 47 mẫu. Đây là dấu hiệu cần review về underinformativeness, **không phải kết luận semantic collapse**. Diagnosis/evidence quality vẫn **NOT MEASURED**.

## Provenance và trạng thái

| Thuộc tính | Giá trị |
|---|---|
| Git | `2c2f011e7f1d7a46b4e3a4a4494ce42b7cbe730f`, branch `feat/task3-qwen-feedback` |
| Dirty patch hash | `d81bcd9946478d5e48efce91a1862222136695452b056cebec789cf4043c1af4` cho diff `src/task3/train.py` + `tests/test_task3_train.py` lúc bắt đầu follow-up |
| Python / PyTorch / CUDA | Python 3.12.3; PyTorch 2.8.0+cu128; runtime CUDA 12.8 |
| GPU | NVIDIA GeForce RTX 5090, 32 GiB; driver 590.48.01; read-only `nvidia-smi` trước/sau inference: 18 MiB, không process được liệt kê |
| Transformers / PEFT / bitsandbytes | 4.57.1 / 0.17.1 / 0.48.1 |
| Model | `Qwen/Qwen2.5-Coder-7B-Instruct`, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242` |
| Config hashes | baseline `9a01fed5d6f08b54733da296379d57e033bcc51b2fe356cfa5efcdffd0dd4a22`; few-shot `d136c8a2648487528a2ffaa8caeaf592548787b5a40022e609569cc512e5650f`; QLoRA `4de631fc67bc1267fae96c393601d5a063ef4653859ec65f14469e3da24b8469` |
| Manifest | Follow-up/current và zero-shot baseline: `42a6f6d35b0ec87246e2e28018f48a1c46b25d71f5c534d71fc571dce8693fc8` (khớp) |
| Prompt spec | `Task3_Copilot_Followup_Review_Prompt.md` không có trong repo; thực thi theo specification đầy đủ được cung cấp trong request |
| FOLLOWUP_ID | `20261018T044055Z`; work: `outputs/task3/followup/20261018T044055Z/`; bundle staging: `outputs/task3/review_bundle/20261018T044055Z/TASK3_REVIEW_BUNDLE_20261018T044055Z/` |

| Phase | Trạng thái | Bằng chứng |
|---|---|---|
| A. Existing artifacts | COMPLETE | Test/lint pass, partitions hash khớp, run manifests/adapter files hợp lệ |
| B. Heldout inference E1/E2 | COMPLETE | Mỗi run 47/47 ID cùng thứ tự, gold taxonomy, GENERATED, nonmock, tokenizer pass |
| P0. Real-val recovery E0/E0b/E1/E2 | COMPLETE | 4/4 current-HEAD runs; cùng 6 ordered IDs, gold taxonomy, nonmock, evaluator outputs saved |
| C. Metrics/guard analysis | COMPLETE | E0/E1/E2 heldout; E0/E0b/E1/E2 real-val; aggregates và review queue đã tạo |
| D. Task 2/public | BLOCKED_DATA | Không có export Task 2 với provenance; public inference không chạy |
| Human semantic evaluation | NOT MEASURED | Chưa có scored annotation; worklist nằm ngoài ZIP |
| Report/package | COMPLETE | Report này; ZIP gồm 14 file, kiểm tra CSV/JSON/hash/CRC sau khi tạo |

## Dataset và cách ly

Manifest hiện tại: strict filter; real train/val 26/6; synthetic train/heldout 496/47; public 328; quarantine 134. `schema_mismatches=0`; cả sáu processed JSONL SHA-256 khớp manifest; official real split 26/6 disjoint. Strict-filter reason counts trong manifest gồm signal contradiction clean 45, compile-fail 10, repair-guidance 9, placeholder Level 4 40, specific-diagnosis 4 (reason có thể chồng lấp). Docs cũ 505/125 không khớp manifest hiện tại 496/134; dữ liệu không bị regenerate.

Audit tokenizer train cũ: context 4096, max observed 3755, 0/528 over 4096. Follow-up heldout E1/E2 tokenizer audit: mỗi run 47 records, 0 blocked. Không có Task 2 export; không thay missing taxonomy bằng `[]` cho public.

## Training artifacts

| Run | Completed steps | Train loss | Best/restored real-val loss | p50/p95 step (s) | Peak allocated/reserved (GiB) | Wall (s) |
|---|---:|---:|---:|---:|---:|---:|
| Qwen_smoke_20 | 20 | 2.523 | 1.949 | 2.471/3.366 | 16.85/21.28 | 58.8 |
| E1_synthetic_only_300 | 300 | 0.430 | 2.037 | 1.591/1.827 | 11.63/15.93 | 508.8 |
| E2_mixed_balanced_300 | 300 | 0.491 | 1.355 | 2.234/3.280 | 16.70/21.22 | 713.1 |

Smoke xác nhận finite nonzero gradient, `max_abs_delta=0.001004`, adapter reload PASS. E1/E2 có 40,370,176 trainable và 4,352,972,288 frozen parameters; full-run update audit là smoke-only nên ở trạng thái unchecked. E1 sampling: 496 synthetic; E2: 260 synthetic/262 real draws, trong đó chỉ 26 unique real-train IDs (oversampling ~10x trung bình). Các adapters dùng lại đều có `adapter_config.json`/`adapter_model.safetensors` và inference fingerprint khớp.

Lưu ý: E1 `train_records=496` và E2 resampled pool 522 rows (260 synthetic/262 real) là kích thước/tỷ lệ của dataset đưa cho Trainer, **không** phải tổng lượt exposure. Effective batch=4 và 300 bước tạo khoảng 1,200 sample presentations. Theo tỷ lệ 262/522, E2 dự kiến khoảng 602 lượt real trên toàn run, tương đương khoảng 23.2 lượt/26 real-train ID; đây là kỳ vọng từ sampler, không phải số đo per-ID.

### Best-checkpoint selection và validation reuse

Trainer config bật `load_best_model_at_end=True`, eval mỗi 20 bước. `trainer_state.json` xác nhận E1 chọn `checkpoint-20` (best metric 2.037009), E2 chọn `checkpoint-60` (1.354778). SHA-256 của `adapter/adapter_model.safetensors` **khớp chính xác** với best checkpoint và **khác** file ở checkpoint-300:

| Run | Best step/loss | Step-300 periodic eval | Worsening from best | Exported adapter SHA-256 |
|---|---:|---:|---:|---|
| E1 | 20 / 2.037009 | 2.961736 | +45.4% | `80e5a22cf30e807cf5a6a3ed31c27a763ed18a40be000d4e9a8b428c8ef8dde7` |
| E2 | 60 / 1.354778 | 1.578935 | +16.5% | `3f848ce57f28dd7e02fd19af3d24ffa483006344f51e41f2929d31f91a9196ca` |

`loss_history` có hai entry step 300: periodic pre-restore evaluation và restored-best evaluation. Do đó `run.json.validation_metrics.eval_loss` và exported adapter là best state, không phải last step. Các bước optimizer 300 vẫn đã chạy, nhưng eval loss đã tệ hơn sau best checkpoint. Sáu real-val IDs cũng đã được dùng lặp lại để chọn checkpoint, nên inference trên chúng không độc lập với model selection. Exposure ước tính tại best: E1 step 20 ≈80 sample presentations; E2 step 60 ≈240 tổng presentations, khoảng 120 real theo sampler ratio. Không có counter per-ID chính xác.

Smoke-audit fix chuyển so sánh parameter từ first optimizer-step sang `on_train_end`, xử lý warmup LR=0. Test mới chứng minh helper nhận snapshot ban đầu và tham số sau thay đổi, nhưng không mô phỏng callback/Trainer hoặc optimizer thực; bằng chứng real-Qwen cho lifecycle là manifest smoke pass.

## Historical real-val inference (initial bundle)

Cùng sáu ordered IDs, gold taxonomy, baseline greedy decoding với max retries=2 cho E0/E1/E2. E0b dùng `few_shot_k=2`, context 8192 thay vì 4096, nên là đối chứng có confounder.

| Run | First pass | Severe L1/L2 flags | Fallback | Retry rescued | Retries | Output tokens | Mean chars | Mean latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| E0_zero_shot | 3/6 | 3/5 | 3/6 | 0 | 6 | 2137 | 153.0 | 4.501 |
| E0b_few_shot | 5/6 | 1/5 | 1/6 | 0 | 2 | 271 | 62.8 | 1.027 |
| E1_synthetic_only | 6/6 | 0/5 | 0/6 | 0 | 0 | 647 | 326.3 | 2.344 |
| E2_mixed_balanced | 6/6 | 0/5 | 0/6 | 0 | 0 | 93 | 40.0 | 0.523 |

Denominator severe flags trong bảng là số mẫu Level 1–2 (`5/6`); `first pass` và fallback denominators là toàn bộ n. Toàn bộ outputs match order, taxonomy gold, manifest/model identity và nonmock status. n=6 nên khác biệt chỉ mô tả, không suy rộng.

Bảng này là aggregate/hash tại thời điểm tạo bundle đầu, với code commit `2c2f011e…`; các raw E0b/E1/E2 files ở những paths đó hiện không còn. Không dùng các hàng này thay cho current-head recovery bên dưới.

E1 có 1/6 real-val output ở đúng 512 generated tokens, gồm Level 2; đây là possible `max_new_tokens` cap hit, không đủ dữ liệu finish reason/raw ending để khẳng định truncation. E2 real-val không có output nào đạt 512.

## Real-val recovery under current HEAD 238cf82b50b296810d6c31773d058b61900c36a5

The prior E0b/E1/E2 raw real-val files are absent from the historical paths recorded above. To fulfill the recovery action, all four modes (including E0 to avoid mixing code revisions) were generated again into `outputs/task3/followup/20261018T061615Z/` under current HEAD `238cf82b50b296810d6c31773d058b61900c36a5`, same ordered six real-val IDs, gold taxonomy, and non-mock Qwen. E0 is regenerated here because its existing raw run came from commit `2c2f011e…`; code changed in the current commit. E0b keeps its distinct `few_shot_k=2`, context 8192 setting; E0/E1/E2 use baseline 4096. All tokenizer audits pass and all current run manifests bind to the current data-manifest hash.

| Current-head run | First-pass | Severe L1/L2 | Fallback | Retries | Tokens | Mean chars | Mean latency (s) | Run commit |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| E0_zero_shot_current | 3/6 | 3/5 | 3/6 | 6 | 2137 | 153.0 | 4.490 | `238cf82b50b296810d6c31773d058b61900c36a5` |
| E0b_few_shot_current | 5/6 | 1/5 | 1/6 | 2 | 271 | 62.8 | 1.027 | `238cf82b50b296810d6c31773d058b61900c36a5` |
| E1_synthetic_only_current | 6/6 | 0/5 | 0/6 | 0 | 647 | 326.3 | 2.325 | `238cf82b50b296810d6c31773d058b61900c36a5` |
| E2_mixed_balanced_current | 6/6 | 0/5 | 0/6 | 0 | 93 | 40.0 | 0.523 | `238cf82b50b296810d6c31773d058b61900c36a5` |

The restored predictions/traces/run manifests and independent evaluator outputs are present for all four modes. E0b/E1/E2 real-val raw artifacts are therefore restored in this new run; this does not retroactively authenticate the missing old files. The new recovery worklist is `reports/task3/PRIVATE_HUMAN_REVIEW_WORKLIST_20261018T061615Z.csv`; all rating cells are blank. Human semantic scoring remains **NOT MEASURED**. Task 2 export is still absent, so predicted-taxonomy propagation/public remains **BLOCKED_DATA**.

## Matched inference: synthetic-heldout

E0 cũ được tái sử dụng do run/data hash khớp. E1/E2 được chạy mới dưới `20261018T044055Z` với cùng config/adapter loading settings. Tất cả ba runs có 47 unique ordered IDs, gold labels đúng, feedback nonempty, tokenizer audit pass, `status=GENERATED`, `test_only_mock=false`, manifest SHA khớp; adapter fingerprints E1/E2 đối chiếu đúng.

| Run | First pass | Severe L1/L2 flags | Fallback | Retry rescued | Retries | Output tokens | Mean chars | Mean latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| E0_zero_shot_heldout | 9/47 | 33/37 | 37/47 | 1 | 75 | 21090 | 145.8 | 5.489 |
| E1_synthetic_only_heldout | 42/47 | 3/37 | 4/47 | 1 | 9 | 2803 | 163.6 | 1.307 |
| E2_mixed_balanced_heldout | 46/47 | 0/37 | 0/47 | 1 | 1 | 866 | 52.0 | 0.477 |

Per-Level distribution (token/character lengths chỉ là proxy, không phải quality score):
- **E0_zero_shot_heldout:** L1: n=22, first-pass 0/22, fallback 22/22, mean chars 83.0, mean tokens 529.7, <=50 chars 0/22; L2: n=15, first-pass 3/15, fallback 11/15, mean chars 105.9, mean tokens 485.3, <=50 chars 0/15; L3: n=6, first-pass 2/6, fallback 4/6, mean chars 166.5, mean tokens 218.7, <=50 chars 0/6; L4: n=4, first-pass 4/4, fallback 0/4, mean chars 610.2, mean tokens 211.2, <=50 chars 0/4.
- **E1_synthetic_only_heldout:** L1: n=22, first-pass 18/22, fallback 3/22, mean chars 64.5, mean tokens 31.7, <=50 chars 10/22; L2: n=15, first-pass 14/15, fallback 1/15, mean chars 171.3, mean tokens 57.5, <=50 chars 7/15; L3: n=6, first-pass 6/6, fallback 0/6, mean chars 572.7, mean tokens 192.8, <=50 chars 1/6; L4: n=4, first-pass 4/4, fallback 0/4, mean chars 66.5, mean tokens 21.5, <=50 chars 1/4.
- **E2_mixed_balanced_heldout:** L1: n=22, first-pass 21/22, fallback 0/22, mean chars 34.9, mean tokens 13.3, <=50 chars 21/22; L2: n=15, first-pass 15/15, fallback 0/15, mean chars 69.7, mean tokens 23.9, <=50 chars 2/15; L3: n=6, first-pass 6/6, fallback 0/6, mean chars 63.7, mean tokens 21.3, <=50 chars 3/6; L4: n=4, first-pass 4/4, fallback 0/4, mean chars 61.5, mean tokens 21.8, <=50 chars 2/4.

E0 first pass 9/47, fallback 37/47, retries 75; E1 42/47, fallback 4/47, retries 9; E2 46/47, fallback 0/47, retry 1. Final heuristic pass 47/47 cho cả ba, nhưng E0 đạt kết quả đó phần lớn nhờ fallback template, không phải successful model generation. Severe flags là guard heuristics, không xác nhận semantic solution leakage.

Paired E1/E2 first-pass contingency trên cùng IDs: **41 cả hai pass, 1 chỉ E1 pass, 5 chỉ E2 pass, 0 cả hai fail**. Exact two-sided McNemar p=0.21875 trên sáu discordant pairs; đây là mô tả nhỏ-n, không chứng minh superiority, nhất là khi records có thể phụ thuộc exam/variant.

Paired length deltas trên cùng ID (mô tả; ngắn hơn không đồng nghĩa tốt hơn):
real-val E0→E1 chars: n=6, mean paired delta B-A=173.33, shorter in 3/6 cases; E1→E2 chars: n=6, mean paired delta B-A=-286.33, shorter in 5/6 cases; E1→E2 tokens: n=6, mean paired delta B-A=-92.33, shorter in 6/6 cases.
heldout E0→E1 chars: n=47, mean paired delta B-A=17.77, shorter in 30/47 cases; E1→E2 chars: n=47, mean paired delta B-A=-111.64, shorter in 33/47 cases; E1→E2 tokens: n=47, mean paired delta B-A=-41.21, shorter in 35/47 cases.

Cross-tab theo `exam_type`:
- **E0_zero_shot:** multi_problem: n=3, first-pass 1/3, fallback 2/3; single_problem: n=3, first-pass 2/3, fallback 1/3.
- **E0b_few_shot:** multi_problem: n=3, first-pass 2/3, fallback 1/3; single_problem: n=3, first-pass 3/3, fallback 0/3.
- **E1_synthetic_only:** multi_problem: n=3, first-pass 3/3, fallback 0/3; single_problem: n=3, first-pass 3/3, fallback 0/3.
- **E2_mixed_balanced:** multi_problem: n=3, first-pass 3/3, fallback 0/3; single_problem: n=3, first-pass 3/3, fallback 0/3.
- **E0_zero_shot_heldout:** multi_problem: n=17, first-pass 4/17, fallback 12/17; single_problem: n=30, first-pass 5/30, fallback 25/30.
- **E1_synthetic_only_heldout:** multi_problem: n=17, first-pass 15/17, fallback 2/17; single_problem: n=30, first-pass 27/30, fallback 2/30.
- **E2_mixed_balanced_heldout:** multi_problem: n=17, first-pass 17/17, fallback 0/17; single_problem: n=30, first-pass 29/30, fallback 0/30.

## E2 short-response / collapse audit

E2 real-val: 93 tokens tổng (mean 15.5/sample), 40 mean characters, 0 fallback/0 retries, 6/6 first-pass. E1 real-val có 647 tokens, mean 326.3 chars; difference in brevity là có thật trong artifacts. E2 heldout: 866 tokens trên 47 (mean 18.43), mean 52.0 chars; E1 heldout 2803 tokens, mean 59.64, 163.6 chars.

Candidate heuristic `<=50 chars` (không phải semantic label): E2 real-val 4/6; E2 heldout 28/47, so sparser outputs are not isolated to real-val. E2 heldout có 10 duplicate rows và 42 near-duplicate pairs; E1 có 6 duplicate rows và 10 near-pairs. “Duplicate rows” là `n - unique` sau lowercase + punctuation normalization; near-duplicate dùng `SequenceMatcher` ratio >=0.9. Đây là candidate-collapse statistics trên final output strings, không chứng minh ngữ nghĩa generic.

E2 real-val per-Level: L1 n=2, mean 19 chars; L2 n=3, mean 61; L3 n=1, 19 chars. Hai L1 instructor targets cùng validation có mean 4 chars; vì vậy ngắn hơn không tự động là sai. Heldout L4: E1 47–81 chars / 17–27 tokens; E2 38–108 chars / 15–37 tokens. Level 4 heuristic pass có ý nghĩa ngữ nghĩa hạn chế.

E1 outputs đạt đúng 512 generated tokens trong 1/6 real-val (Level 2) và 3/47 heldout (1 Level 2, 2 Level 3); các trường hợp trên không fallback. Đây là possible cap hits, không kết luận truncation vì finish reason/EOS không có trong share bundle. Per-Level summaries: `06_GUARD_BY_LEVEL.csv`; per-sample aggregate: `08_PER_SAMPLE_AUDIT_REDACTED.csv`. Instructor-target length baselines, numeric only: L1 n=2 mean/median 4/4 chars; L2 n=3 mean 128 median 106; L3 n=1 66/66. Đây là length context nhỏ-n, không phải adequacy score.

Hypothesis: E2 may have learned short generic acknowledgements or terse labels, especially where Level 2/3 requires evidence and useful direction. The length pattern supports human review but cannot distinguish concise/correct from generic/underinformative. All semantic accuracy, evidence support and Level correctness remain **NOT MEASURED**.

## Phản hồi technical review độc lập

Review ngoài xác nhận nội bộ ZIP/CSV và nêu thêm các điểm dưới đây; tôi đã đối chiếu lại bằng `trainer_state.json`, checkpoint weights hoặc CSV redacted:

- **Best checkpoint đã xác minh trực tiếp:** E1 `trainer_state.json` chọn step 20, best loss 2.037009; E2 chọn step 60, best loss 1.354778. Adapter export hash trùng đúng weight file checkpoint-20/checkpoint-60 và khác checkpoint-300. Eval periodic step 300 tăng tương ứng lên 2.961736 (+45.4%) và 1.578935 (+16.5%). Do vậy full run 300 bước hoàn tất, nhưng adapter dùng ở inference là restored-best checkpoint. Real-val sáu mẫu được dùng chọn checkpoint, nên so sánh trên đó có selection reuse.
- **Loss-history interpretation:** mỗi run có hai eval entries ở step 300; entry đầu là periodic eval trước restore, entry cuối là re-evaluation của best adapter sau restore. `04_TRAINING_LOSS_HISTORY.csv` đã được gắn `checkpoint_selection` để phân biệt.
- **Paired first-pass:** trên 47 heldout IDs, contingency E1/E2 là 41 cả hai pass, 1 E1-only, 5 E2-only, 0 cả hai fail. Exact two-sided McNemar p=0.21875, mô tả nhỏ-n với exam/variant correlation, không phải bằng chứng superiority.
- **Output cap:** redacted traces báo E1 có 1/6 real-val output đúng 512 tokens (L2) và 3/47 heldout (1 L2, 2 L3); E2 không chạm ngưỡng. Không có EOS/finish reason, vì vậy chỉ gọi là possible cap hits, chưa kết luận truncation.
- **Duplicates:** bundled redacted metric computation reports heldout E2 10 duplicate rows/42 near-pairs và E1 6/10 tại threshold >=0.9. Đây là exact/near duplicate signals của normalized final response text; không chứng minh semantic collapse.
- **Historical source availability:** sau khi bundle tạo xong, ba E0b/E1/E2 real-val raw prediction folders không còn trên disk. Aggregate/hash build-time evidence vẫn nằm trong ZIP nhưng không thể re-hash nguồn hiện tại; `02_EXPERIMENT_MATRIX.csv` và provenance index nay nói rõ điều này. Không dựng lại hoặc tuyên bố raw source còn tồn tại.

Các điểm về false praise, tính đúng Level 4, diagnosis/evidence accuracy và generic-answer semantics vẫn **HUMAN_REVIEW_REQUIRED / NOT MEASURED**. Với Level 1, E2 trung bình 19 chars còn instructor targets chỉ trung bình 4 chars trên hai mẫu đó; độ ngắn tự nó không phải lỗi. Level 4 heldout E1 là 47–81 chars/17–27 tokens, E2 là 38–108 chars/15–37 tokens, nhưng không có human score để phân loại.

## Guard analysis and uncertainty

Violation frequencies are in `07_VIOLATION_COUNTS.csv` split by run/Level, with first-attempt and all-attempt counts. `06_GUARD_BY_LEVEL.csv` separates first-pass, severe L1/L2 flags, retry rescue, retries, fallback and final pass. Traces retain violation names but not rejected raw model generations; false-positive rate and true semantic leakage are **NOT VERIFIED**. Regex labels such as `code_like`, `identifier`, `repair_guidance` cannot be called true positives or false positives from these artifacts alone. Existing local calibration artifact/test covered 32 real instructor targets and reported 32/32 pass; this does not establish guard recall.

Retry rescue is a model-generated response that first failed, later passed, and did not fallback. E0 heldout: 1 rescued; E1/E2 heldout counts and per-Level denominators are in CSV. Final fallback compliance is never described as model success.

## Human review and Task 2/public

`reports/task3/PRIVATE_HUMAN_REVIEW_WORKLIST.csv` is local-only and not in ZIP. It contains sample IDs, Level/exam-type, output lengths, and blank independent Reviewer 1/2 rubric columns. `reports/task3/HUMAN_REVIEW_INSTRUCTIONS.md` defines diagnosis/evidence 0/1/2 and leakage/hallucination review. Do not fill with AI. Diagnosis accuracy, evidence support, hallucination, inter-rater agreement and Level-4 correctness are **HUMAN_REVIEW_REQUIRED / NOT MEASURED**.

No Task 2 prediction export with complete-ID `parse_ok` provenance was found. Predicted-taxonomy real-val, error propagation and public inference are **BLOCKED_DATA**; required input is the authentic Task 2 export for all target IDs with provenance. No public inference was run. The old E0b/E1/E2 real-val files remain absent at their historical paths and their build-time hashes remain historical evidence only; replacement E0/E0b/E1/E2 real-val artifacts were regenerated under current HEAD in `outputs/task3/followup/20261018T061615Z/`, with all four ordered ID sets and manifests validated.

## Reproduction and artifact index

Inference commands for new runs:

```bash
.venv-task3/bin/python scripts/run_task3.py --config configs/task3/baseline.yaml --split synthetic-heldout --taxonomy-source gold --adapter checkpoints/task3/autopilot-20261018T033618Z-synthetic/adapter --output outputs/task3/followup/20261018T044055Z/e1.synthetic-heldout.oracle.json
.venv-task3/bin/python scripts/run_task3.py --config configs/task3/baseline.yaml --split synthetic-heldout --taxonomy-source gold --adapter checkpoints/task3/autopilot-20261018T033618Z-mixed_balanced/adapter --output outputs/task3/followup/20261018T044055Z/e2.synthetic-heldout.oracle.json
.venv-task3/bin/python scripts/evaluate_task3.py --data-dir data/processed/task3 --split synthetic-heldout --predictions <PREDICTIONS_JSON> --traces <TRACES_JSON> --taxonomy-source gold --output <WORK>/<RUN>.evaluation.json
```

Machine-readable inputs, hashes, config/model IDs and missing-evidence notes: `09_PROVENANCE_AND_ARTIFACT_INDEX.json`. Full 47-row redacted audits and training loss history are included; no prediction text, source data, gold feedback, adapter weights, or private human worklist is included in ZIP. The index preserves build-time hashes for historical real-val sources, but E0b/E1/E2 real-val bytes are currently unavailable at those paths; treat these historical hashes as unverified against current disk until originals are restored.

## Next-round plan

1. **P0 Human review:** Two independent reviewers score diagnosis/evidence 0/1/2 for E1/E2 on all 6 real-val and stratified heldout rows, emphasizing Level 2/3 and Level 4. Release gate proposal: at least 80% of reviewed cases score 2 on diagnosis and evidence, zero confirmed severe Level violations, and reviewer agreement reported; expand n before broad claims. Current state: NOT RUN.
2. **P0 Taxonomy integration:** Obtain authentic Task 2 export with `parse_ok`, complete exact IDs/order and source manifest. First run predicted `real-val`; do not proceed to public until mismatch/propagation is reviewed. Current state: BLOCKED_DATA.
3. **P1 Feedback-collapse falsification:** Blindly compare E1/E2 per-sample, including low-length, repeated-response, Level 2/3 and all Level 4 strata. Hypothesis: E2 short/near-duplicate outputs have lower evidence/diagnosis scores; E1 cap hits may be truncated. Decision: if E2 loses >0.25 mean diagnosis points or exceeds 20% underinformative ratings vs E1, do not select E2; privately inspect E1 finish reasons. No prompt/model changes before this check.
4. **P1 Guard audit:** Obtain authorized local review of rejected outputs in a protected environment, never the share bundle. Only propose regex/prompt edits when reviewers identify repeatable false positives; preserve 32-target calibration and add counterexample tests. Current state: NOT RUN.
5. **P2 Training/data:** Do not retrain yet. Best-step restoration is already verified: E1 step 20 and E2 step 60 adapters match saved best checkpoint weights. If human scores justify an ablation, compare existing best-vs-step-300 adapters first; only then consider lower real oversampling or regularization under a new isolated run ID. Compare human diagnosis/evidence, not eval loss alone.

**Final decision:** Continue blinded E1/E2 human review; do not retrain or submit public outputs yet. The heldout guard/length evidence is encouraging for compliance but is not semantic validation. No verified winner.
