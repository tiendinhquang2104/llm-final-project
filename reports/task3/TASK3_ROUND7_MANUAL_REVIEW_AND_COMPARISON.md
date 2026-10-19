# Task 3 Round 7 manual review and paired comparison

## Scope and review method

This report reviews the six previously seen `real-val` records from Round 6. They are a six-record development validation split, not a new benchmark. A single reviewer compared the unchanged reference taxonomy, source code, statements, supplied compiler/test evidence, diagnosis audit, generated feedback, and the Level definitions in `data/raw/sample_dataset/label_space.json`. Guard pass is reported only as a mechanical metric; it is not used as a content-quality score.

Private per-record notes, prompts, source, raw attempts, and outputs remain in the Git-ignored file `outputs/task3/task3-round7-private-manual-review.json` (mode 0600). This tracked report contains no submitted code or raw prompt/output text. Official reference labels were not edited.

Feedback review uses two separate 0–2 scales:

- **Factual safety/accuracy:** 0 = wrong or unsupported claims; 1 = mixed/partial; 2 = accurate or neutral without a false factual claim. A neutral fallback may score 2 here while scoring 0 for coverage.
- **Issue coverage:** 0 = no useful diagnosis; 1 = partial; 2 = covers the confirmed issue(s) adequately.

“Level review” is a separate human judgment of the requested disclosure contract. It does not inherit the guard result.

## Internal issue mapping

These internal review tags are not written into `taxonomy_error`. Official outputs retain only the ten Vietnamese labels.

| Internal finding | Official group used for analysis | Rule |
| --- | --- | --- |
| `syntax_error`, `undeclared_identifier` | Lỗi biên dịch | Map only when the source/compiler evidence supports a compile failure. |
| `infinite_loop` | Lỗi vòng lặp | A loop with no progress is a loop defect. |
| `off_by_one` | Lỗi edge case; sometimes Lỗi vòng lặp | Add the loop group only when the loop control itself is wrong, consistent with the official D14b mapping. |
| `pointer_indexing` | Lỗi mảng/chuỗi | Only when a real bound/access defect exists. Pointer subscripting itself is valid C++. |
| `hardcoded_filename` | Lỗi hard-code | A literal filename used instead of the supplied parameter. |
| `extra_prompt_output` | Lỗi nhập/xuất | An interactive prompt on stdout violates the required output format. |
| valid `d=0`, `p=1`, digit traversal, header rewind/read | No label | These are not defects by themselves; claims against them require separate evidence. |

## Manual review by sample

| Sample | Level | Reference taxonomy (unchanged) | Confirmed source/compiler finding | Round 6 review | Round 7 predicted-diagnosis review | Round 7 feedback review |
| --- | ---: | --- | --- | --- | --- | --- |
| `EX01-S106` | 2 | logic, loop | P3 loop never advances; P2 allocates one `Node` then indexes multiple nodes. Further lifetime and head-deletion concerns are candidates. | Diagnosis invented a compile error. Feedback falsely said the header reread skips data and pointer indexing is illegal. | Compile claim was rejected; remaining diagnosis was explicitly `uncertain`, with no labels. | Pipeline feedback repeated both false claims (accuracy 0/2, coverage 0/2). Direct and oracle emitted neutral fallbacks (2/2 factual safety, 0/2 coverage). |
| `EX01-S111` | 2 | compile | Source contains malformed `getline`, type/name errors and redeclarations. Compiler execution was unavailable, so this is source-confirmed, not compiler-confirmed in this run. `d` is initialized and incremented. | Diagnosis falsely said `<fstream>` was undeclared. Feedback falsely called `d` uninitialized and missed the malformed `getline`. | Diagnosis remained unavailable after one exact-quote format retry; output stayed `uncertain`. | Pipeline feedback repeated the false `d` claim, included a non-Vietnamese fragment, and advised how to change the code (Level 2 violation; 0/2). Direct feedback named one real syntax error but still made false claims and gave a repair instruction (1/2). Oracle feedback had some correct redeclaration observations but also unsupported causes (1/2). |
| `EX01-S112` | 2 | hard-code | P1 opens the literal string `"filename"` rather than the parameter. P1 is a prerequisite for P2–P4; downstream issues are not counted as reference omissions. | Diagnosis mislabeled the literal filename as a compile error. Feedback noticed the hard-coded name but added an unsupported null-pointer claim. | Diagnosis unavailable after a bounded format retry; output remained `uncertain`. | Pipeline output correctly described the filename issue, then added unsupported P2/P3 claims (1/2). Direct and oracle gave neutral fallbacks (2/2 factual safety, 0/2 coverage). |
| `EX02-S201` | 1 | `[]` | Digit counting and repeated multiplication match the stated Armstrong-number domain and no-`pow` rule. | Diagnosis and feedback incorrectly criticized valid digit traversal. | Diagnosis unavailable after a bounded format retry; output remained `uncertain`. | All Round 7 tracks used a neutral fallback (2/2 factual safety, 0/2 coverage). This avoids the earlier false positive but gives little help. |
| `EX02-S211` | 1 | `[]` | `d` and `p` are initialized; `p=1` is the normal accumulator. The program also prints an interactive prompt to stdout, a possible I/O format defect. | Diagnosis falsely called `p` uninitialized; feedback asked the student to revisit a correct accumulator. | Diagnosis unavailable after a bounded format retry; output remained `uncertain`. | All Round 7 tracks used a neutral fallback (2/2 factual safety, 0/2 coverage). **The empty reference may be incomplete** because the prompt text can violate the required output. This is a review candidate only; gold remains `[]`. |
| `EX02-S212` | 3 | compile, loop | `cnt` is used without a declaration, a source-confirmed compile defect. The compiler was unavailable. A separate runtime loop defect is not established before repairing `cnt`. | Diagnosis focused on the valid `x=1` accumulator, missed `cnt`, then feedback fell back. | Diagnosis returned explicit uncertainty; no label was emitted. | Pipeline, direct and oracle all fell back to generic feedback. Each fails Level 3’s diagnosis-plus-useful-direction requirement (accuracy-safe but coverage 0/2). |

### Level contract review

The mechanical guard passed all six rows in all three final tracks (6/6 each). Manual review found that Level 2 content was incomplete or materially inaccurate in all three samples; some responses also included repair advice forbidden at Level 2. All three Level 3 outputs were generic fallback text and did not contain a supported diagnosis plus useful direction. Level 1 outputs avoided technical disclosure but were neutral fallbacks rather than useful hints. Therefore manual Level/content compliance is **2/6 per track** (the two Level 1 rows satisfy the disclosure ceiling); the guard’s 100% pass rate is not a quality result.

## Paired experiment

All tracks used the same six `real-val` IDs, Qwen `Qwen/Qwen2.5-Coder-7B-Instruct` revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, greedy generation, and `configs/task3/self_diagnosis_zero_shot.yaml`, including the Level 3 adequacy retry policy. The direct-feedback arm used the pipeline’s predicted label arrays only to isolate the effect of diagnosis context; it did not receive the diagnosis summary. Its Task2-shaped handoff is marked unverified and is not an independent Task 2 prediction. The oracle arm received gold labels and did not load or reuse predicted diagnosis.

| Track | Taxonomy input | Taxonomy macro-F1 | Micro-F1 | Exact match | Feedback fallback | Feedback tokens in/out | Feedback latency | Diagnosis tokens in/out | Diagnosis latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pipeline | Self-diagnosis; diagnosis context passed to feedback | 0.00 | 0.00 | 2/6 | 3/6 | 15,819 / 1,162 | 15.01 s | 18,624 / 2,519 | 30.93 s |
| Direct feedback | Same predicted labels; no diagnosis context | 0.00 | 0.00 | 2/6 | 5/6 | 24,449 / 1,848 | 23.69 s | — | — |
| Oracle | Gold labels; no predicted diagnosis context | Not a model score (labels copied from gold) | Not applicable | 6/6 by construction | 5/6 | 24,538 / 2,192 | 27.72 s | — | — |

The self-diagnosis returned `[]` for all six. Four diagnoses were explicitly marked `diagnosis_unavailable` after bounded format retries; the other two were uncertain after unsupported findings were removed. Exact match is 2/6 only because two reference rows are empty; no positive label was predicted. The direct arm inherits the same predictions, so its taxonomy score is identical. Oracle taxonomy is an upper-bound input by construction, not an end-to-end result.

| Official taxonomy group | Reference support | Predicted count | TP | FP | FN | Predicted F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Lỗi biên dịch | 2 | 0 | 0 | 0 | 2 | 0.00 |
| Lỗi nhập/xuất | 0 | 0 | 0 | 0 | 0 | n/a |
| Lỗi logic | 1 | 0 | 0 | 0 | 1 | 0.00 |
| Lỗi vòng lặp | 2 | 0 | 0 | 0 | 2 | 0.00 |
| Lỗi mảng/chuỗi | 0 | 0 | 0 | 0 | 0 | n/a |
| Lỗi hàm | 0 | 0 | 0 | 0 | 0 | n/a |
| Lỗi edge case | 0 | 0 | 0 | 0 | 0 | n/a |
| Lỗi thuật toán | 0 | 0 | 0 | 0 | 0 | n/a |
| Lỗi hard-code | 1 | 0 | 0 | 0 | 1 | 0.00 |
| Lỗi style | 0 | 0 | 0 | 0 | 0 | n/a |

The unmodified references contain six positive labels in total. The predicted macro-F1 over supported labels and micro-F1 are both 0.00. The possible missing I/O label for `EX02-S211` is not added to this score.

Human factual safety/accuracy averaged 1.17/2 for the pipeline and 1.83/2 for both direct and oracle; issue coverage averaged 0.17/2 for the pipeline and 0.17/2 for both direct and oracle. Neutral fallbacks improve the safety score but do not improve coverage. The higher direct/oracle safety score therefore does not mean those arms produced useful feedback.

## Compiler and source checks

The implementation now attempts a syntax-only C++ compile using an available `g++`, `clang++`, or `c++`, with a five-second timeout, source-size cap, bounded diagnostics, stdin input, and no execution/binary output. This environment had no compiler in PATH or the common local toolchain directories. All real records therefore carry `compiler unavailable / status unknown`; no generated finding was accepted as compiler-confirmed here. Regression tests use a fake compiler executable to exercise successful, error, missing-tool, and timeout states. Source review of `cnt` and the malformed `getline` remains separate from a real compiler result.

Narrow source checks now reject known contradictions: a scalar declared with an initializer is not “uninitialized”; pointer subscripting is legal absent an actual bounds defect; a rewind followed by consuming the header does not skip the next data row; and zero is outside the stated positive input domain. These checks are intentionally limited and do not establish general semantic correctness.

## Decision and limitations

This method is **not frozen**. The predicted taxonomy has 0.00 F1 on supported labels, diagnosis formatting is unavailable on four records, feedback fallback is 50% in the pipeline and 83% in both direct and oracle, and Level 3 remains generic. No 328-record public inference was run, no public content influenced method selection, no public few-shot/training data was used, no training occurred, and nothing was submitted to a leaderboard.

The three Qwen comparison artifacts above were generated immediately before adding the final fail-closed Level 3 gate. Their generic `EX02-S212` outputs are retained as review evidence; the strict current pipeline now raises an ID-specific error instead of exporting that Level 3 fallback after retries. The comparison therefore documents why the method is rejected, not a complete run accepted by the final strict gate. The exact Qwen comparison was not repeated after the gate because it would stop at that Level 3 case; no public inference was attempted.

The six records are previously seen validation data; per-group estimates are unstable, there is one human reviewer, gold may be incomplete (especially `EX02-S211`), and the local compiler limitation prevented live compile diagnostics. These results are a stop signal for this method, not evidence of expected public performance.

## Reproduction and private artifacts

```bash
.venv-task3/bin/pytest tests/test_task3_*.py -q
.venv-task3/bin/python scripts/run_task3.py --config configs/task3/self_diagnosis_zero_shot.yaml --split real-val --taxonomy-source self-diagnosis --output outputs/task3/task3-round7h-selfdiag-real-val.json
.venv-task3/bin/python scripts/run_task3.py --config configs/task3/self_diagnosis_zero_shot.yaml --split real-val --taxonomy-source task2-json --taxonomy-json outputs/task3/task3-round7h-selfdiag-labels.json --allow-unverified-task2-export --output outputs/task3/task3-round7h-direct-real-val.json
.venv-task3/bin/python scripts/run_task3.py --config configs/task3/self_diagnosis_zero_shot.yaml --split real-val --taxonomy-source gold --output outputs/task3/task3-round7h-oracle-real-val.json
```

Final Task 3 verification after implementation: **325 passed, 7 skipped**. The repository-wide run recorded **602 passed, 30 skipped, 4 failed**; the failures are the existing Task 1 Colab secret tests (2) and synthetic labeler gate tests (2), outside Task 3.

Final prediction SHA-256: pipeline `4402c2c043456d1f44a9a57851fc7576d119c9f12a19f2b59ada141eaed2efa8`; direct `77e0370745787b802f0a69b07d60797912ca96aa2b62447ff438de1573d75475`; oracle `cec59e2a730c639f1e23e8c50e0942ebbb10944ea723814bd2f1ff3611a07fc6`. Predictions, traces, attempt journals, manual notes and label handoff live under ignored `outputs/task3/` with owner-only file permissions.
