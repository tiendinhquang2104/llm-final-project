# Task 3 feedback prompting implementation plan

> Execute inline using executing-plans, test-driven-development and verification-before-completion. User explicitly authorizes this plan followed immediately by offline execution and a commit on the current branch; no worktree, push, public inference or submission.

**Goal:** compare two direct prompts with immutable R15 using source-grounded Level-specific feedback review on base Qwen 7B.
**Architecture:** reuse the R15 backend/parser/controller without editing their files; a prompt adapter changes only messages. Keep sources, rendered prompts, reviews and outputs in ignored `outputs/task3/feedback-prompt-20261021`. A sealed manifest binds inputs, bank, prompts, runtime config and reviews.
**Tech stack:** existing Python environment, NF4 Qwen2.5-Coder-7B-Instruct, pytest, SHA-256.
**Spec:** user's attached 19-step request (2026-10-21); constraints/protocol transcribed here and in the experiment rubric.

## Global constraints

- Branch `feat/task3-quality-round5`, initial HEAD `1a5c32386f29dc20acb0260da387694e8384013c`. Preserve all pre-existing files/artifacts. No training/adapters/model >=10B.
- R15 revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`, original template, NF4/BF16, greedy, 3 attempts, original parser and Level guard; same token/time caps for all arms.
- Public metadata only: no public source, ID, output or score used for design, targets, examples or selection. Historical public scores only in report context.
- Evaluation-only fields never reach renderer; bank requires train provenance and source binding. No teacher prose as examples.
- No untrusted C++ execution on host. If sandbox unavailable: static reasoning/testcase trace, agent-reviewed, never compiler-confirmed.

## Review focus

- Hidden evaluation annotations nested in records: whitelist prompt payload and adversarial sentinel tests.
- Duplicate sources via renamed identifiers: raw/token/renamed identity and lexical/structural shingle screening against train, previous eval and bank; inspect nearest matches.
- L1/L2 semantic disclosure missed by regex: manual source review independent of guard.
- Generic or wrong claims with valid JSON: explicit useful diagnosis and serious false-claim flags, unknown never pass.
- Resume/output drift: frozen files, prompt/model/input/output hashes and controller attempt identity; tamper tests.

## Tasks

- [x] 1. Audit metadata sample/release hashes, model pin, historical artifact hashes and calibration sources; add Level-specific rubric and locked decision conditions under `reports/task3/`.
- [x] 2. Write failing tests then add `src/task3/feedback_prompt.py`, `scripts/task3_feedback_prompt.py`, `configs/task3/feedback_prompt_20261021.json`. Test gold/teacher isolation, train-only bank, Level leakage, proxy scores, manifest tampering, schema and full-source budget behavior. Preserve original R15 modules.
- [x] 3. Create private train-derived synthetic source set (target 48 independent sources; 12 each Level) with source quotes, static testcase traces, clean/defect references, provenance. Select reviewed train-only bank (target >=6 families), no shared evaluation families. Screen against 521 prepared train records, 53 prior calibration records, prior reserved/reviewed references and bank; reject ambiguous/near cases. Freeze all before inference. Record any quota shortfall honestly.
- [x] 4. Lock A/B/C prompts and bank; run all three on all 53 exposed calibration requests. Review every output with source quotes/evidence; choose at most one B/C by feedback proxy mean, ties fewer false claims then B; taxonomy never selection. Record wins/losses/disagreements. Freeze selection before fresh outputs.
- [x] 5. Run A and selected candidate exactly once on the new frozen set (bounded retries within that pass). Blind arm aliases for review if feasible; record every technical verdict with source/output quotes or static traces. No prompt/guard/bank changes after observing outputs.
- [x] 6. Compute proxy mean, paired win/loss and per-Level results, technical claims, false-clean, location/cause, feasible repair, generic feedback, coverage, semantic Level violations, taxonomy micro/macro-F1 as secondary and retries/fallback. Validate all outputs. Produce full per-ID report and >=12 full diverse pairs in private review bundle with SHA manifest.
- [x] 7. Run Task 3 tests and full pytest; document all failures and limitations. Review diff, commit only code/config/tests/plan/rubric/aggregate report. Report HEAD/status/artifact paths and stop.

## Locked selection and stop protocol

Calibration comprises six real-val plus all 47 synthetic-heldout: prior exposure, not blind. Fresh set is held out from prompt selection but agent-created/reviewed, not independent human benchmark. New source variants count independently only if different implementations survive identity/near/template review. No quota filler from public or ambiguous cases.

Proxy: 0/0.5/1 using rubric, L1/L2 repair disclosure forces zero. Serious false technical claim or false-clean forces zero. Generic uncertain feedback cannot receive full credit. Unknown earns zero with separate unknown flag. Primary is useful, source-correct feedback, never schema/length/F1.

Candidate eligibility locked before aggregate: all cases complete/valid; no L1/L2 concrete repair disclosure; false technical claim finals <=A; paired wins minus losses >=6 on 48; L2 net >=3; L3 net >=1; L1 false-clean <=A. If <48, report ratio and uncertainty, retain thresholds without relaxing. Failure or unresolved material unknown => keep R15. Success => candidate for independent review before public only. No public inference, no 328 predictions, no leaderboard upload.

## Execution ledger

- Tasks1–2: metadata and pin audited; rubric/config/prompts authored; protocol tests RED (missing module) then GREEN8/8; original R15 modules untouched.
- Task3: initial48 drafts screened; two rejected and one borderline draft replaced before fresh freeze.48 final cases frozen before inference. Later output-blinded source audit disputed4 cases; frozen input/reference unchanged. Material isolation unknown blocks promotion.44-case sensitivity is explicitly not a blind48-source benchmark.
- Task4:159 calibration finals reviewed before aggregate; C selected by frozen mean-proxy rule. No gold/teacher/public query or demonstration content. Selection seal precedes fresh inference.
- Task5: A/C completed48 each in one controller pass, bounded original retries; no prompt/bank/guard edits after observation.
- Task6:96 randomized X/Y verdicts sealed before unblinding. Every one of302 journal attempts exactly re-rendered; scalar input audit/schema validators pass. Added report-gate tests RED→GREEN and nested-metadata audit regression RED→GREEN;13 new tests pass. Source reviewer found a shallow-whitelist adversarial gap; current inputs safe, frozen renderer preserved and limitation documented.
- Task7: experiment/R15 tests108 pass; all Task3 checks1031 pass,2 skip,1 historical root-prediction hash failure. Whole-repo run without slow legacy synthesis:1290 pass,8 skip,12 fail,2 collection errors; full synthesis fixture interrupted after approximately11 minutes. No claim of full-suite pass. Preserve historic data rather than alter root predictions to satisfy stale expectation.
- Ruling: apply no worktree/approval pauses because user's request explicitly authorizes current-branch offline work and commit. No model/adapter changes.
- Ruling: quarantine post-freeze template doubts rather than regenerate cases or tune thresholds after outputs; cost is only44 usable sensitivity cases and no candidate promotion.
- Ruling: retain exact inference renderer after observation; add read-only nested annotation auditor and disclose general renderer contract gap. Cost: arbitrary future metadata needs hardening before reuse; this run's302 actual prompts pass the strict audit.
- Final review: independent agent code/source review read no model outputs and made no edits. Important findings above addressed through quarantine/read-only validation and explicit limitations, not retrospective prompt changes. Minor deferred: FPNEW-12-4 reference says dth power instead of explicitly digit-count power; correct source/trace preserved, wording caveat in audit.
- Decision: retain R15. No public inference, push, predictions328 generation, or submission. Final commit and bundle SHA are reported to the user after verification.
