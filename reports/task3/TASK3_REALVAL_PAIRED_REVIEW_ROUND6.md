# Task 3 real-validation paired review — Round 6 follow-up

## Scope and provenance

This report follows the pushed Round 5 baseline `d0fb568` on `feat/task3-quality-round5`. The six real-validation records are the project’s previously seen sample-dataset validation split, not a new benchmark. No public code was used for prompt, few-shot, or training changes.

Both tracks used `configs/task3/self_diagnosis_zero_shot.yaml`, Qwen `Qwen/Qwen2.5-Coder-7B-Instruct` revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, no adapter, and greedy decoding. The oracle track reused the exact diagnosis audit produced by the predicted track. The feedback configuration/data manifest/diagnosis-audit hashes match in both run manifests. The only intended prompt difference is the taxonomy field. Semantic quality is manually reviewed below; the guard’s mechanical compliance is not treated as a quality score.

The user-supplied `task3_requested_levels.json` was copied byte-for-byte from repository root to `data/raw/public_test_release/task3_requested_levels.json`. SHA-256: `73b3b092871a947e4749d7fccf01662f161fa96ba59b5311bedaa2b634e6bdcf`. It has 328 unique IDs (L1 115, L2 163, L3 50, L4 0), maps exactly to the ID/Level metadata in the release, and the copy is ignored by `.gitignore`. `scripts/task3_prepare.py` completed: 26 real-train, 6 real-val, 496 synthetic-train, 47 synthetic-heldout, 328 public, 134 quarantined.

## Six-record paired result

Predicted taxonomy exact match was **0/6** (0/2 Level 1, 0/3 Level 2, 0/1 Level 3). Macro-F1 and micro-F1 were both 0. Oracle taxonomy matches the reference labels by construction; that is an upper-bound feedback condition, not an end-to-end model score. All 12 feedback outputs passed the configured heuristic compliance guard, while semantic compliance remains unscored automatically. Manual review found multiple unsupported statements and wrong diagnoses, so the guard result is not evidence of good feedback.

| Sample | Level | Reference taxonomy | Predicted | Oracle | Internal subcategory review and feedback finding |
| --- | --- | --- | --- | --- | --- |
| `EX01-S106` | 2 | logic, loop | `[]` | logic, loop | Diagnosis falsely called a function definition a compile error; removed for missing compiler evidence. Predicted feedback falsely says pointer indexing is illegal and that resetting the stream skips the first data row. Source issues include a traversal loop that never advances and allocation of one node before indexing multiple elements. Oracle fell back to generic text. Internal tags: `infinite_loop`, `undersized_allocation`. |
| `EX01-S111` | 2 | compile | `[]` | compile | Diagnosis falsely claimed `<fstream>` was undeclared; removed because there was no compiler log. Predicted feedback says `d` is uninitialized although it is initialized, and does not identify the malformed `getline(sa,s,)` expression. Oracle feedback also makes unsupported claims about an uninitialized pointer. Internal tags: `syntax_error`, `array_indexing`. |
| `EX01-S112` | 2 | hard-code | `[]` | hard-code | Diagnosis mislabeled the literal filename as a compile error and was filtered. Predicted feedback correctly notices the hard-coded filename, but also incorrectly treats `0` as an invalid null pointer and misses that the node-removal function does not remove nodes. Oracle fell back. Internal tags: `hardcoded_filename`, `missing_node_deletion`. |
| `EX02-S201` | 1 | `[]` | logic | `[]` | False-positive logic label: dividing the temporary by 10 is the intended digit traversal for the Armstrong-number computation. Predicted feedback calls the correct digit-count/power loop a problem; oracle feedback gives the same unsupported criticism. Internal tag: `false_positive_digit_count`. |
| `EX02-S211` | 1 | `[]` | logic | `[]` | False-positive logic label: the accumulator `p` is initialized to 1 before exponentiation. Predicted diagnosis claims it is uninitialized and feedback suggests rechecking the power calculation. Oracle is vague but does not claim a specific error. Internal tag: `false_positive_uninitialized_accumulator`. |
| `EX02-S212` | 3 | compile, loop | logic | compile, loop | Predicted diagnosis focuses on `x = 1`, which is a normal power accumulator, and misses the undeclared loop-bound identifier `cnt`; predicted feedback falls back to a generic message. Oracle also falls back. Internal tags: `undeclared_identifier`, `loop_bound_name`. |

The internal subcategory tags above are analysis-only. Prediction JSON contains only the ten official Vietnamese taxonomy labels.

### Per official taxonomy label

| Official label | Reference support | Predicted count | TP | FP | FN | Predicted F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Lỗi biên dịch | 2 | 0 | 0 | 0 | 2 | 0.00 |
| Lỗi nhập/xuất | 0 | 0 | 0 | 0 | 0 | n/a |
| Lỗi logic | 1 | 3 | 0 | 3 | 1 | 0.00 |
| Lỗi vòng lặp | 2 | 0 | 0 | 0 | 2 | 0.00 |
| Lỗi mảng/chuỗi | 0 | 0 | 0 | 0 | 0 | n/a |
| Lỗi hàm | 0 | 0 | 0 | 0 | 0 | n/a |
| Lỗi edge case | 0 | 0 | 0 | 0 | 0 | n/a |
| Lỗi thuật toán | 0 | 0 | 0 | 0 | 0 | n/a |
| Lỗi hard-code | 1 | 0 | 0 | 0 | 1 | 0.00 |
| Lỗi style | 0 | 0 | 0 | 0 | 0 | n/a |

| Level | Samples | Predicted taxonomy exact | Oracle taxonomy exact | Predicted feedback fallback | Oracle feedback fallback |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2 | 0/2 | 2/2 | 0/2 | 0/2 |
| 2 | 3 | 0/3 | 3/3 | 0/3 | 2/3 |
| 3 | 1 | 0/1 | 1/1 | 1/1 | 1/1 |

## Attempt, token, latency, and output files

The diagnosis gate removed three unsupported compile-error findings and three unsupported prerequisite reviews. Each original response and filter decision is retained. The retry mechanism was used only for malformed/status-inconsistent output and the JSON string `"null"` where the schema requires a JSON null. There were 9 diagnosis generations: 14,796 input tokens, 1,373 output tokens, 17.41 seconds total generation latency.

| Track | Feedback generations | Retries | Fallbacks | Input tokens (all attempts) | Output tokens | Generation latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Predicted taxonomy | 10 | 4 | 1/6 | 14,543 | 991 | 12.86 s |
| Oracle taxonomy | 13 | 7 | 3/6 | 21,962 | 1,702 | 21.84 s |

Raw outputs are local and Git-ignored; they contain private student code in prompts/traces.

- Predicted bundle: `outputs/task3/task3-selfdiag-real-val-round6f.json`
  - diagnosis + raw/retry attempts: `outputs/task3/task3-selfdiag-real-val-round6f.taxonomy-diagnosis.json`, `outputs/task3/task3-selfdiag-real-val-round6f.taxonomy-diagnosis.attempts.jsonl`
  - feedback raw/retry/final, token/time/fallback traces: `outputs/task3/task3-selfdiag-real-val-round6f.traces.json`
  - metrics and provenance: `outputs/task3/task3-selfdiag-real-val-round6f.metrics.json`, `outputs/task3/task3-selfdiag-real-val-round6f.run.json`
  - prediction SHA-256: `01976a6bfced385d81cb5edee27d4aeb48e11cddc2f33227825bcb5df9f2e75e`
- Oracle bundle: `outputs/task3/task3-oracle-same-context-real-val-round6f.json`
  - traces, metrics, provenance use the same stem with `.traces.json`, `.metrics.json`, and `.run.json`
  - prediction SHA-256: `73f8fa92389b5e5d558a7ac5379f3fecd007e252752c6050fbf70bcb4810100b`

## Public inference decision and reproduction

The public requested-level contract now loads the supplied numeric schema and the prepared public split has exactly 328 IDs. The two paired six-record outputs were reviewed before any public inference. The review shows 0/6 predicted taxonomy exact matches, false-positive Level 1 diagnoses, several factually wrong Level 2 claims, and a generic Level 3 fallback. Therefore this run is preserved as an exploratory inference audit; it is not evidence of a submission-ready method. No public inference has been run yet and no leaderboard was submitted. Do not tune from public content; if public inference is run, use the frozen zero-shot method only and treat it as inference output.

Reproduction commands:

```bash
.venv-task3/bin/python scripts/task3_prepare.py
.venv-task3/bin/python scripts/run_task3.py \
  --config configs/task3/self_diagnosis_zero_shot.yaml \
  --split real-val --taxonomy-source self-diagnosis \
  --output outputs/task3/task3-selfdiag-real-val-round6f.json
.venv-task3/bin/python scripts/run_task3.py \
  --config configs/task3/self_diagnosis_zero_shot.yaml \
  --split real-val --taxonomy-source gold \
  --diagnosis-audit outputs/task3/task3-selfdiag-real-val-round6f.taxonomy-diagnosis.json \
  --output outputs/task3/task3-oracle-same-context-real-val-round6f.json
```

## Code follow-up to pushed baseline

Changes after pushed commit `d0fb568` accept integer `requested_level` values 1–4 without accepting bools; allow null scope for file-wide or unmappable findings; retry only bounded formatting inconsistencies; require compiler evidence for a compile taxonomy finding; and remove/audit unsupported compiler and prerequisite claims. If a valid finding explicitly names an official label but omits it from an otherwise empty taxonomy array, the parser reconciles the two fields to that finding label. All these changes have regression tests. The final follow-up commit and post-change test results are recorded in the chat summary and Git history.
