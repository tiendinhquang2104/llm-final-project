# Task 3 Round15 prompt-only experiment

Goal: compare short zero-shot and the same prompt with concise train-only examples, attribute raw-vs-final quality loss, freeze a development-selected prompt, then produce a new328-record public candidate beside immutable Round14.

Constraints: same repository/currentbranch; no checkout/worktree, fine-tuning, Task2, extractor/certificate expansion, public examples/prompt selection, push or leaderboard. Keep existing Round14 code/config/candidate unchanged. Raw/student code/examples/model attempts/audits/predictions under ignored outputs/task3/round15. Only code/config/test/report committed.

Design: new opt-in direct prompt asks exactly taxonomy_error+Vietnamese feedback, full source/statement/compiler evidence/requestedLevel, official10labels and conciseL1–4definitions. Few-shot differs only by reviewed train examples selected byLevel/error-form diversity. Drop entire examples when context is tight; never crop querysource. Only schema+explicitL1/2disclosure gates; L3/4 content passes for review, no actionkeyword/fence/factual/CJK/praise rejection. CJK/praise/possiblefullsolution are audit flags, not claims of automaticsemanticjudgment. Bounded retries log raw response before parsing/guard and preserve global perIDbudget across resume; no exception-to-[]default.

- [x] VerifyHEAD/status/docs and Round14checksum; inventory compatible model/tokenizer/config and trainselection metadata.
- [x] Freeze new train-only development, excluding R14selection families/group/codehashes; disjoint trainexample bank with source-reviewed shortreferences. Recordlimitations of prior corpus exposure.
- [x] TDD prompt/fullsource budgeting, schema/rawcapture/disclosure boundaries and retry/resume. Implement independent opt-in CLI/config; no default/oldartifact edits.
- [x] Run zero/few/R14control on same newdevelopment IDs/Levels/model/shareddecoding. Save allraws, review perrecord model vs postprocess errors, usefulL2location/cause and usefulL3action. Reportlabels/claims separatelyfromschema/fallback. No publicsemanticinspection forselection.
- [x] Choose prompt on development and commit/hashfreeze. FullTask3suite includingC++sandbox; historicalfullrepomissingTask1dependencies remains a reportedlimit.
- [ ] Run selected frozenprompt on public328 to newoutputdir. ValidateofficialID/Level/schema, capture raw/audit/fallback and usefulfeedback assessment scope. PreserveRound14bytes, no public-derivedpromptrevision.
- [ ] Commitreport/config/code/tests, giveartifactSHA/path and honestqualitylimits; verifycleanstatus, no rawstaged/push/submission.

Implementation ownership: root prompt/controller/CLI/config/report; independent trainpartition and narrow disclosure modules/tests can be delegated under dispatching-parallel-agents skill. Independent source-based development review after outputs; publicquality review (if performed) only after freeze, never changesprompt.
