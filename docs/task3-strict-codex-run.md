# Codex execution prompt — Task 3 strict D+, English/BF16

You are implementing and validating Task 3 in `tiendinhquang2104/llm-final-project`. Finish the work and return concrete artifacts. Do not start another framework rewrite, model sweep, precision experiment or prompt tuning loop.

## Establish the correct code

The reviewed D+ base is `584efe9cc11772fb3d3b1012abe9acd8036a8f55` on `task3/arm-d-plus`. The originally shared `feat/task3-quality-round5` pointed to `26a9d9b10c32e8daf95d8ef29dc76af61332bda0`, a different implementation. Check the current branch/HEAD and working tree before modifying anything. Preserve unrelated work. Apply the supplied strict patch to the D+ base, or use the supplied `fix/task3-strict-feedback` checkout. Do not overwrite the historical branch or v1.3 outputs.

The implementation is already in `src/task3/arm_d_plus.py`; exact English prompts are exported in `docs/task3-strict-prompts.md`. Read the diff and the audit report. Do not replace these with an untested longer prompt. Public examples must not become case-specific rules, hardcoded IDs, gold labels or few-shot answers.

## Required behavior

1. Preserve full detector input: statement, code, all problems/prototypes, constraints, I/O, restrictions, prerequisites, language, compile/test evidence and source metadata. Exclude teacher/gold annotations. Use the actual requested Level, never an ID suffix. Keep missing evidence distinct from successful execution.
2. Stage 1 emits exactly `findings`, each with `problem_id`, `location`, `evidence`, `error`, `labels`. Require the current sample's problem ID, an actual diagnosis and a short exact source/log quote. Empty evidence is allowed for genuine omissions; it is not proof that the omission claim is true. Reject the known copied schema placeholder. Never manufacture an empty findings list after validation failure.
3. Preserve the ten official Vietnamese taxonomy names. Unknown labels must resolve to one of those ten through the existing same-model constrained A–J choice; do not discard the finding or add a new category. Mapping validity is not diagnostic accuracy.
4. Level 1 uses the implemented bounded Vietnamese templates without a renderer call. Level 2 renders the supplied location/cause without a concrete repair and without resending the full source. Levels 3–4 receive the task context needed for their permitted repair detail. Do not rediagnose at rendering time.
5. One corrective attempt per failed stage maximum. Record the original response, failure kind, precise parser error/context, corrected response and costs. Do not repeat an unchanged malformed JSON response, strip arbitrary text with regex, guess missing diagnoses, raise token budgets indefinitely, or hide unresolved samples with old predictions.
6. Preserve pinned Qwen2.5-Coder-7B-Instruct revision, actual BF16, no NF4/FP32 switch, greedy decoding, seed42, concurrency1 and the existing time/context budgets. Read resolved runtime metadata to verify actual dtype and no CPU offload. Never truncate source/logs to make preflight pass.

## Execute and verify

Use the project's CUDA environment and `requirements-task3.txt`. The review environment had CPU only; **no new Qwen inference or semantic improvement has been measured**. Do not describe unit-test fixtures or historical replay as a new model run.

Run:

```bash
python -m pytest -q tests/test_task3_strict_feedback.py tests/test_task3_strict_contract_audit.py tests/test_task3_arm_d_plus.py tests/test_task3_arm_d_plus_runner.py tests/test_task3_dataset.py tests/test_task3_public_contract.py tests/test_task3_submission.py tests/test_task3_language_precision_ablation.py tests/test_task3_two_pass.py tests/test_task3_compile_evidence.py
```

Locate the original archive, public release, synthetic/internal30 data, historical D run and local model cache; the runner's original defaults assume `/workspace/llm-final-project` and `/workspace/llm-final-project-ablation`. If paths differ, supply the existing root/history flags and make path-only configuration adjustments before freezing. Do not fabricate unavailable files. Verify the real tokenizer's full prompts fit, including actual findings and correction messages; MockTokenizer tests are not that check.

Run the same internal30 once in a NEW output directory, then inspect the saved summary and raw findings. Compare taxonomy against historical D and v1.3 D+ on identical IDs. Inspect initialization, loop/index claims, output-token spelling, omissions, placeholder/evidence failures and Level 2 repair leakage. Record regressions as regressions; do not infer improvement from enum validity.

```bash
python scripts/task3_arm_d_plus.py --phase internal --out outputs/task3/internal-arm-d-plus-v1.4-strict
```

If internal validation is complete and no systematic contract failure remains, freeze that exact code/config and run public **once**:

```bash
python scripts/task3_arm_d_plus.py --phase public --out outputs/task3/public-arm-d-plus-v1.4-strict --method-freeze outputs/task3/internal-arm-d-plus-v1.4-strict/method-freeze.json
```

Do not modify frozen prompts or code mid-run. Resume only the same method and inputs using its generated `REPRODUCE.md`; a changed method needs a new identity/directory. If the strict evidence contract produces many failures, report the actual failure rate and representative raw cases before spending another full public run. Do not weaken validation silently or call the run complete.

## Deliverables and acceptance

- A real public `predictions.json` only after exact-ID/schema validation: expected328, completed328, missing0, duplicate0, extra0; official taxonomy and nonempty feedback for every sample. If incomplete, supply the partial artifact and precise unresolved list, not a fake final file.
- Private audit bundle: method freeze, resolved dtype/config, original inputs/bindings, all prompts/raw attempts, mapping decisions, normalized findings, renderer modes, failures, validation and total token/time costs, including failed calls.
- A brief Vietnamese report comparing measured metrics and failures, with a reproducible fixed sample of outputs covering requested Levels and representative defect/clean cases. Print actual input snippets, findings and feedback side by side; separate factual correctness, Level compliance and schema validity. Do not select only attractive examples.
- State whether diagnostics, Level compliance and costs actually improved. Keep public semantic accuracy unmeasured if no gold or independent review supports it. Do not upload student artifacts, submit to the leaderboard, or push private data.

Stop only for a concrete blocker such as missing model/data, unavailable GPU, failed validation or a demonstrated systematic regression. Provide the exact error, completed work and the next executable command. Do not claim a successful rerun that did not happen.
