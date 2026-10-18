# Task 3 Two-Track Quality Review — Round 5

## STATUS
COMPLETE_WITH_LIMITATIONS. P2v2/P3v2 and the preserved P0/P1/P2/P3/F1/F2 baselines were evaluated on matched 6 real-val and 47 synthetic-heldout IDs. No adapter was retrained. Human semantic review is NOT_MEASURED; no winner is claimed.

## GIT_COMMIT+DIRTY_DIFF
- Branch: `feat/task3-quality-round5`; current base commit: `91c7c98e9df8fe14f8a97d9eadd5b6e77f16fb2c`.
- Round 5 tracked plus added-file change-set SHA-256: `ec6b039e58f8e618d069a81e99e0695575b3ef75097c8e553321d9ff3e777f42`; tracked diff SHA-256: `3b39dfe60026d2f3ffc07ca6d96ee417d47d70f44ca64c97cd0be65fc05d357f`.
- Original six baselines were generated at `238cf82b50b296810d6c31773d058b61900c36a5`; v2 runs record the current base commit and included a local dirty diff. The diff is bundled in the aggregate ZIP.
- No commit or push was performed by this run.

## METHODS_RUN
P0 zero-shot; P1 few-shot; P2 structured CoT; P3 few-shot + structured CoT; F1 existing synthetic-only QLoRA adapter; F2 existing mixed-balanced QLoRA adapter; P2v2 grounded structured CoT; P3v2 curated real-only few-shot + grounded CoT.

## N_REAL_VAL / N_HELDOUT
- N_REAL_VAL: 6; N_HELDOUT: 47; each method has exactly one output for every ordered ID (424 method-cases total).
- Synthetic-heldout has been repeatedly inspected and used for iteration; it is development/evaluation data, not a pristine unseen final benchmark.

## MATCHED_CONFIG
- Model/revision: `Qwen/Qwen2.5-Coder-7B-Instruct` / `c03e6d358207e414f1eca0bb1891e29f1db0e242`. Prepared manifest SHA-256: `42a6f6d35b0ec87246e2e28018f48a1c46b25d71f5c534d71fc571dce8693fc8`.
- All runs use gold/oracle taxonomy as input; Task 2 classification accuracy is not evaluated. Shared context 8192, greedy decoding, feedback cap 512 tokens; structured plans use a 256-token cap and one plan retry; feedback allows two retries. Existing adapters were reused exactly (fingerprints in `RUN_PROVENANCE.json`); no training occurred.
- P3v2 requests K=2, uses only eligible real-train references, excludes EX02-S202/EX02-S203/EX02-S204, and requires same-Level examples. Effective K is per sample and can be 0, 1, or 2; it is never reported as two-shot unless two examples survive context budgeting.

## FIRST_PASS_BY_METHOD / FALLBACK_BY_METHOD
Raw first pass is the disclosure-guard rate among samples with an actual first final-feedback generation. The all-case success column counts plan failures as unsuccessful. Final guard pass includes generic fallbacks and is not adequacy/correctness.

| Split | Method | Raw first pass | All-case first-pass success | Fallback | Severe first L1/L2 | Retries rescued | Plan status |
|---|---|---:|---:|---:|---:|---:|---|
| real-val | P0 | 3/6 (50.0%) | 3/6 (50.0%) | 3/6 (50.0%) | 3/5 | 0 | `{"not_applicable": 6}` |
| synthetic-heldout | P0 | 9/47 (19.1%) | 9/47 (19.1%) | 37/47 (78.7%) | 33/37 | 1 | `{"not_applicable": 47}` |
| real-val | P1 | 5/6 (83.3%) | 5/6 (83.3%) | 1/6 (16.7%) | 1/5 | 0 | `{"not_applicable": 6}` |
| synthetic-heldout | P1 | 33/47 (70.2%) | 33/47 (70.2%) | 11/47 (23.4%) | 12/37 | 3 | `{"not_applicable": 47}` |
| real-val | P2 | 3/6 (50.0%) | 3/6 (50.0%) | 1/6 (16.7%) | 3/5 | 2 | `{"validated": 6}` |
| synthetic-heldout | P2 | 11/47 (23.4%) | 11/47 (23.4%) | 34/47 (72.3%) | 29/37 | 2 | `{"validated": 47}` |
| real-val | P3 | 5/6 (83.3%) | 5/6 (83.3%) | 1/6 (16.7%) | 1/5 | 0 | `{"validated": 6}` |
| synthetic-heldout | P3 | 37/47 (78.7%) | 37/47 (78.7%) | 7/47 (14.9%) | 8/37 | 3 | `{"validated": 47}` |
| real-val | F1 | 6/6 (100.0%) | 6/6 (100.0%) | 0/6 (0.0%) | 0/5 | 0 | `{"not_applicable": 6}` |
| synthetic-heldout | F1 | 42/47 (89.4%) | 42/47 (89.4%) | 4/47 (8.5%) | 3/37 | 1 | `{"not_applicable": 47}` |
| real-val | F2 | 6/6 (100.0%) | 6/6 (100.0%) | 0/6 (0.0%) | 0/5 | 0 | `{"not_applicable": 6}` |
| synthetic-heldout | F2 | 46/47 (97.9%) | 46/47 (97.9%) | 0/47 (0.0%) | 0/37 | 1 | `{"not_applicable": 47}` |
| real-val | P2v2 | 1/4 (25.0%) | 1/6 (16.7%) | 5/6 (83.3%) | 3/3 | 0 | `{"parse_failed": 2, "validated": 4}` |
| synthetic-heldout | P2v2 | 8/33 (24.2%) | 8/47 (17.0%) | 36/47 (76.6%) | 24/27 | 3 | `{"parse_failed": 14, "validated": 33}` |
| real-val | P3v2 | 1/4 (25.0%) | 1/6 (16.7%) | 4/6 (66.7%) | 3/3 | 1 | `{"parse_failed": 2, "validated": 4}` |
| synthetic-heldout | P3v2 | 19/33 (57.6%) | 19/47 (40.4%) | 28/47 (59.6%) | 12/27 | 0 | `{"parse_failed": 14, "validated": 33}` |

## TOKENS / LATENCY / EFFECTIVE_K
Plan and final-feedback tokens and latencies are separated. Generation calls count attempted plan and feedback generations; context-blocked attempts are excluded from plan calls. K histograms show per-example effective demonstrations after context budgeting, not requested K.

| Split | Method | Plan tokens | Feedback tokens | Mean plan s | Mean feedback s | Plan calls | Feedback calls | Requested K | Effective K distribution |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| real-val | P0 | 0 | 2137 | 0.00 | 4.47 | 0 | 12 | 0 | `{"0": 6}` |
| synthetic-heldout | P0 | 0 | 21090 | 0.00 | 5.50 | 0 | 122 | 0 | `{"0": 47}` |
| real-val | P1 | 0 | 271 | 0.00 | 1.03 | 0 | 8 | 2 | `{"1": 2, "2": 4}` |
| synthetic-heldout | P1 | 0 | 3067 | 0.00 | 1.23 | 0 | 72 | 2 | `{"2": 47}` |
| real-val | P2 | 937 | 2708 | 2.05 | 5.56 | 7 | 10 | 0 | `{"0": 6}` |
| synthetic-heldout | P2 | 4856 | 17783 | 1.31 | 4.69 | 49 | 117 | 0 | `{"0": 47}` |
| real-val | P3 | 937 | 456 | 2.02 | 1.39 | 7 | 8 | 2 | `{"1": 2, "2": 4}` |
| synthetic-heldout | P3 | 4856 | 2666 | 1.30 | 1.10 | 49 | 64 | 2 | `{"2": 47}` |
| real-val | F1 | 0 | 647 | 0.00 | 2.33 | 0 | 6 | 0 | `{"0": 6}` |
| synthetic-heldout | F1 | 0 | 2803 | 0.00 | 1.30 | 0 | 56 | 0 | `{"0": 47}` |
| real-val | F2 | 0 | 93 | 0.00 | 0.53 | 0 | 6 | 0 | `{"0": 6}` |
| synthetic-heldout | F2 | 0 | 866 | 0.00 | 0.47 | 0 | 48 | 0 | `{"0": 47}` |
| real-val | P2v2 | 1590 | 2096 | 3.33 | 4.36 | 8 | 10 | 0 | `{"0": 6}` |
| synthetic-heldout | P2v2 | 13004 | 19106 | 3.36 | 4.97 | 62 | 80 | 0 | `{"0": 47}` |
| real-val | P3v2 | 1590 | 1234 | 3.32 | 2.79 | 8 | 9 | 2 | `{"1": 5, "2": 1}` |
| synthetic-heldout | P3v2 | 13004 | 5155 | 3.36 | 1.70 | 62 | 61 | 2 | `{"0": 4, "1": 22, "2": 21}` |

## LEVEL / NATURALNESS_FINDINGS
- Per-Level generated denominators and raw pass/severe counts are in `PER_LEVEL_METRICS.csv`; all are heuristic disclosure checks, not semantic correctness.
- P2v2 validated 4/6 plans on real-val and 33/47 on heldout; P3v2 had identical plan hashes. On heldout P2v2 final feedback fell back in 36/47 cases; P3v2 fell back in 28/47. Plan failure is counted as no first feedback generation, not a model pass.
- Baseline P2/P3 likewise share identical plans. The original P1/P3 used effective K=1 on EX01-S106 and EX01-S112 despite requested K=2. P3v2 effective K distribution is recorded per ID; heldout includes four rows with K=0 and no Level 4 real-train demos.
- P2v2/P3v2 both fall back on EX01-S106; P3v2 addresses P2 on EX01-S112 although P1 is a prerequisite and failed. On EX02-S212, P2v2 adds an unsupported `x` claim while P3v2 gives a count-variable direction. These are source-based preliminary observations, not human grades.
- For SYN-HO-SINGLE-0006, v2 provides a modulo correction but includes an incorrect prose explanation of integer division. For SYN-HELDOUT-0011, the generated code adds declarations and uses `>>` (not the incorrect comma operator), but diagnoses missing declarations rather than the source's missing semicolon. For SYN-HO-MULTI1-0007, v2's `int` max-b correction matches the prototype but it also questions P4, which the reference marks correct.
- The warning-only screen found baseline F2 mixed CJK in real-val; v2 has occasional Level/naturalness candidate flags. Warning counts are in `RUN_METRICS.csv`/`PER_ID_REDACTED_AUDIT.jsonl`. No automated adequacy or fluency score is claimed. `CASE_REVIEW_NOTES.csv` is AI_PRELIMINARY_NOT_HUMAN.
- The built-in training audit flags all 522 train records for missing compile logs/test reports (and synthetic provenance), but produces no specific semantic-quality flags. Manual spot-checking found repeated synthetic Level 1 targets (123 examples, 15 exact phrases; one phrase occurs 15 times) and confirmed multiple broken/unrelated Level 4/3 references listed in `CURATION_PLAN.csv`. Original data/splits remain unchanged; no retraining is justified yet.

## PAIRED_RESULTS
Paired all-case first-feedback success is a secondary binary view: a missing final generation after plan failure counts as unsuccessful. Exact McNemar p-values and Wilson intervals are exploratory only; these repeatedly inspected data do not support a winner claim.

| Split | Pair | n | Left pass | Right pass | Left only | Right only | Exact McNemar p |
|---|---|---:|---:|---:|---:|---:|---:|
| real-val | P0 vs P1 | 6 | 3 | 5 | 0 | 2 | 0.500 |
| real-val | P1 vs P3 | 6 | 5 | 5 | 0 | 0 | 1.000 |
| real-val | P2 vs P2v2 | 6 | 3 | 1 | 2 | 0 | 0.500 |
| real-val | P3 vs P3v2 | 6 | 5 | 1 | 4 | 0 | 0.125 |
| real-val | P1 vs P3v2 | 6 | 5 | 1 | 4 | 0 | 0.125 |
| synthetic-heldout | P0 vs P1 | 47 | 9 | 33 | 1 | 25 | <0.001 |
| synthetic-heldout | P1 vs P3 | 47 | 33 | 37 | 2 | 6 | 0.289 |
| synthetic-heldout | P2 vs P2v2 | 47 | 11 | 8 | 7 | 4 | 0.549 |
| synthetic-heldout | P3 vs P3v2 | 47 | 37 | 19 | 18 | 0 | <0.001 |
| synthetic-heldout | P1 vs P3v2 | 47 | 33 | 19 | 14 | 0 | <0.001 |

## SEMANTIC_REVIEW_STATUS
NOT_MEASURED. The private queue has 424 sample-method rows for two independent reviewers and is blank. Fallbacks receive no semantic-quality score by default. The automated adequacy/language screen is candidate-only and is not human annotation.

## DATA_AND_GUARD_LIMITS
- Task 2 predicted-taxonomy/public evaluation: BLOCKED_DATA; no provenance-verified Task 2 export.
- Guard pass is disclosure-only and includes fallback; rejected raw generation text was not stored and is marked RAW_REJECTED_TEXT_NOT_RECORDED. False-positive guard calibration is therefore not possible from raw attempts.
- Official external validator was not supplied; local schema and heuristic checks only.
- The requested independent-review markdown was not present as a workspace file; its pasted findings were used as the hard-case checklist.

## NEXT_DECISION
Do not retrain yet. First conduct blind two-reviewer scoring on the fixed IDs and audit/rewrite the named synthetic gold candidates. Treat P2v2/P3v2 as diagnostic variants, not a replacement winner; consider another prompt iteration only after reviewing plan failure and Level errors. Evaluate predicted taxonomy only after a provenance-verified Task 2 export exists.

## FILE_PATHS
- Report: `reports/task3/FINAL_TWO_TRACK_QUALITY_REVIEW.md`
- Aggregate ZIP: `outputs/task3/TASK3_ROUND5_AGGREGATE_REVIEW.zip`
- Full private ZIP: `outputs/task3/TASK3_ROUND5_FULL_PRIVATE_REVIEW.zip`
- Immutable run directory: `outputs/task3/two_track_round5/20261018T100959Z`
- ZIP checksums are appended to the detached report after archives are created; member checksums are in each archive's SHA256SUMS.txt.

Aggregate ZIP SHA-256: `b2c195effd1e4c41297d81544d623cddf109b243b36a7f9b1c81cf3dc7ac81da`.
Private ZIP SHA-256: `3f52314cb2b288712f18b99f13dfd64333bf8990d05c57a4b4eaeefc70a68a58`.
