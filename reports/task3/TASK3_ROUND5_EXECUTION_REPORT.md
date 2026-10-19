# Task 3 Round 5 execution report

## Repository and commits

- Repository: `/workspace/llm-final-project`
- Branch: `feat/task3-quality-round5`
- Starting/base commit: `f9d746a`
- No worktree, clone, push, PR, or submission was created.

Milestones committed on this branch:

| Commit | Work |
| --- | --- |
| `f03eff9` | Public submission schema and strict offline validator; requested-level contract and dataset checks. |
| `a19eb3d` | Predicted taxonomy metrics: per-label and aggregate scores plus empty/exact-match diagnostics. |
| `89da327` | Selected R7–R9 source/config/test baseline patches, with L1 R9 and R7 fallback described in docs. |

R9 raw bundles, checkpoints, reports, and generated outputs were not imported. Existing owner files (including `task3-autopilot.agent.md`, the R7/R8 execution reports, and existing quality/strategy tests) were preserved and not staged.

## Implementation in the working tree

Added a structured local self-diagnosis stage that excludes gold taxonomy, requested Level, and instructor feedback from its prompt. It requires source quotes, constrains problem IDs and prerequisite references to supplied values, validates the taxonomy/findings agreement, and keeps parse/generation failures in a private journal rather than silently producing `[]`. The validated diagnosis summary is passed to the feedback stage. The CLI supports reusing an audit for paired experiments and records separate feedback-model and taxonomy-model provenance. Added zero-shot and same-level train-only few-shot configs.

The public loader/CLI now require a separate requested-level file, verify its ID and Level contract, and reject partial public runs. `docs/task3.md` documents the updated workflow. Public inputs and outputs were not used for prompt selection or training.

## Verification and execution

- `.venv-task3/bin/pytest tests/test_task3_*.py -q` — **301 passed, 7 skipped**.
- `.venv-task3/bin/pytest -q` — **578 passed, 30 skipped, 4 failed**. Failures are in unrelated existing Task 1 Colab secret tests (2) and synthetic labeler gate tests (2); no Task 3 tests failed.
- Real Qwen on the six-record `real-val` split was attempted twice. It stopped at the first record, `EX01-S106`, because the model proposed an unsupported compile-error finding and returned a null problem ID despite supplied IDs P1–P4. Strict validation rejected it. No final predictions were written. The private raw attempt journals are in ignored `outputs/task3/task3-selfdiag-real-val-round5*.taxonomy-diagnosis.attempts.jsonl` files; they contain student code and must remain local.
- An initial malformed JSON response was a single fenced JSON object. The parser now accepts that one wrapper while retaining exact schema/evidence validation. The subsequent unsupported diagnosis still fails closed.
- Public inference and its output validator were **not run**. This checkout's `data/raw/public_test_release` lacks the required `task3_requested_levels.json`. Public predictions therefore do not exist.
- No oracle/predicted quality table is claimed: the real-model predicted run did not complete, and the real validation split has six records (Levels 1–3 only). The 47-record synthetic-heldout split is previously viewed development data, not a new benchmark. Level 4 prompt coverage is exercised by artificial regression tests, not a quality evaluation.
- Task 2 predictions/checkpoint were not present, so the Task2 taxonomy provider and F1/F2 model comparison could not be run. No new model training was performed.

Reproduction for the implemented real-validation attempt:

```bash
.venv-task3/bin/python scripts/run_task3.py \
  --config configs/task3/self_diagnosis_zero_shot.yaml \
  --split real-val --taxonomy-source self-diagnosis \
  --output outputs/task3/task3-selfdiag-real-val-<unique>.json
```

Before public inference, supply the official 328-ID `task3_requested_levels.json` alongside the release, freeze the method/config, then run public predicted-taxonomy inference and `scripts/validate_task3_submission.py` against that file.

## Remaining working-tree changes

Final implementation/report commit: `368dfa2` (`feat(task3): add evidence-backed self diagnosis`). The branch is four commits ahead of `origin/feat/task3-quality-round5`. At report time, `git status --short` showed only these pre-existing untracked owner files, which were left untouched: `reports/task3/R7_CODEX_EXECUTION_REPORT.md`, `reports/task3/R8_LEVEL1_EXECUTION_REPORT.md`, `reports/task3/TASK3_GPU_EXECUTION_REPORT_20261018T1135Z.md`, `task3-autopilot.agent.md`, `tests/test_task3_quality_v2.py`, and `tests/test_task3_strategy.py`. No Codex-created changes remain uncommitted. Raw attempt logs are ignored local outputs and are intentionally excluded from Git.
