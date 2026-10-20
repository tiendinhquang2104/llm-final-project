# Task 3: controlled Vietnamese pedagogical feedback

The Task 3 CLIs implement local preparation, zero/few-shot generation, completion-only CUDA QLoRA SFT, evaluation and public export. Model weights are never loaded by `--help` or `--dry-run`. Training starts only through an explicit non-dry `train_task3.py` command. Offline fixtures and mock outputs are not model measurements.

## Quickstart: Windows or CPU development

From the repository root, Python 3.10+ (tested with Python 3.12):

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/WSL: source .venv/bin/activate
python -m pip install pyyaml pytest
python scripts/task3_prepare.py --real data/raw/sample_dataset --synthetic data/synth/generate-dataset --synthetic-heldout data/synth/generate-dataset/heldout --public data/raw/public_test_release --output data/processed/task3 --seed 42 --filter-synthetic strict
python scripts/run_task3.py --config configs/task3/baseline.yaml --split real-val --taxonomy-source gold --dry-run
python scripts/train_task3.py --config configs/task3/qlora.yaml --dry-run
python -m pytest tests/test_task3_*.py -q
```

In PowerShell, expand the test glob with `python -m pytest (Get-ChildItem tests/test_task3_*.py).FullName -q`.

The tokenizer/collator integration tests skip if their optional dependencies are absent. The rest of Task 3 needs only YAML and pytest. Existing Task 1/2 tests need the team's dependencies. `bash run.sh --task3 --dry-run` forwards arguments to the same inference CLI. Do not run the older `prepare_data.py` or `create_split.py` to prepare Task 3: those commands may overwrite fixed splits.

## Data provenance, schemas and isolation

Raw data already present locally is used without modification; no archive extraction is necessary. All `code_file` references resolve against their own dataset root. Absolute paths, Windows drives, traversal and escaping symlinks are rejected. Missing `.cpp` references and malformed required fields fail explicitly. Source decoding tries UTF-8 with BOM, CP1258, CP1252 and Latin-1. There is no dependency on the existing all-three-tasks ID join.

| Source | Canonical directory | Task 3 taxonomy | Feedback |
|---|---|---|---|
| Real, 32 records | `data/raw/sample_dataset` | `input.taxonomy_error`, including known `[]` | Instructor target |
| Synthetic, 612 records | `data/synth/generate-dataset` | `output.taxonomy_error` | Synthetic target |
| Synthetic heldout, 65 records / 4 exams | `data/synth/generate-dataset/heldout` | `output.taxonomy_error` | Evaluation only |
| Public, 328 records / 6 exams | `data/raw/public_test_release` | Absent, requires Task 2 predictions | No completion |

The heldout release has no `label_space.json`; its parent's label-space metadata is used explicitly. All ten labels and four exact level strings are validated against project constants and on-disk metadata. Level definitions in the prompts come from `label_space.json`. Public metadata explicitly requires `output.taxonomy_error` and `output.feedback`.

`data/processed/task3/{real-train,real-val,synthetic-train,synthetic-heldout,public,quarantine}.jsonl` contains typed record metadata, a conversational `prompt` without feedback, and assistant-only `completion`. Public has a null prompt until predictions are supplied and **no completion key**. Real/synthetic gold feedback is present only as a target or evaluation reference, never an input feature; synthetic `exec_report` is audit-only. Private local records also retain the original target for evaluation, so processed files are as sensitive as raw files.

The official real split is fixed at 26 train IDs and 6 validation IDs. Its files, `data/splits/train_ids.json` and `data/splits/val_ids.json`, are restored in this workspace; loading is fail-closed and does not recover missing files from Git history. Preparation enforces seed 42, exact split membership and disjointness. A real train/validation code/provenance collision stops preparation instead of silently moving fixed IDs.

Connected groups combine original code-file identity, exact canonical token hashes, conservative identifier-renamed hashes, and available provenance (`base_id`, source variants, `pair_id`, `duplicate_of`). String literals are preserved; comments/formatting are ignored. Level clones referencing the original `.cpp` remain grouped. No random split by Task 3 record ID is performed: the provided 28-exam synthetic training pool and four-exam heldout pool retain their roles. Supplied heldout records sharing a group with another partition are quarantined. Synthetic training records overlapping validation/heldout/public groups are quarantined too. Fixed real training IDs remain fixed, including any public overlap; the public corpus is never used for fitting, target creation or model selection.

`manifest.json` contains input/processed checksums, fixed-split hashes, counts, group statistics, lexical code-length proxies, IDs/reasons for exclusions, long logs, optional missing fields, synthetic gold guard flags, placeholder Level 4 snippets and execution-signal contradictions. Counts inside `audit` describe the pool before strict quality selection; top-level `partitions` describes final outputs. Contradictions are noisy review flags, not automatic relabeling. Required schema mismatches abort; `schema_mismatches: 0` means all loaded records passed those checks. No source code, exam statement or feedback is copied into the manifest.

`--filter-synthetic strict` (CLI default) removes synthetic training records flagged for gold compliance, placeholder Level 4 or execution-signal contradictions. `none` retains these quality flags for an ablation; overlap quarantine still applies. Synthetic and mixed training require strict preparation. Originals are never modified. The current local audit yields **26 real train, 6 real validation, 505 synthetic train, 47 synthetic heldout, 328 public and 125 quarantine**. The quarantine comprises 30 cross-partition overlap exclusions plus 95 strict quality exclusions; 18 of the 65 original heldout records are quarantined for cross-partition group overlap. These counts depend on the checked input hashes and conservative grouping policy; they are data quality findings, not benchmark scores.

## Local model inference and taxonomy modes

The prompt-first R7–R9 baselines are retained as versioned configs: `r7_direct_k0/k1/k2.yaml`, `r8_level1_prompt4_guard2/guard3.yaml`, and `r9_p4_json_k0_g2`, `r9_p5_json_k0_g2`, `r9_p6_read_k0_g2`, `r9_p6_read_k1_g2`. R9 changes only the Level-1 wording/presentation in v5/v6; Levels 2–4 delegate to the R7 prompt. Its historical private raw-output bundle remains in the prior R9 worktree and is not copied into source control. These are reproducible baselines, not a claim that the best end-to-end method has been selected.

Configs pin `Qwen/Qwen2.5-Coder-7B-Instruct` to revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`. `AutoTokenizer.apply_chat_template` provides the real template. Student code, comments, statement and logs are delimited as untrusted JSON data. Prompt instructions preserve problem IDs and prerequisite context, and explicitly say missing logs do not imply successful compilation. Prompt injection resistance is an instruction/data boundary, not a security proof.

Generation is greedy by default; config keys include `do_sample`, `temperature`, `top_p`, `context_limit`, `max_new_tokens`, `few_shot_k` and bounded `max_retries` (0–5). Few-shot examples come only from permitted training partitions and exclude IDs, code variants and groups overlapping any selected evaluation record. Examples are ordered deterministically, with same-Level preference. Tokenizer measurements trim logs/test reports before demonstrations; source, problem context and target Level are never silently cropped. Overlength essentials raise an ID/count-only error.

On Linux/WSL with the inference/training dependencies installed:

```bash
# Oracle labels: same six fixed real validation IDs for every experiment
python scripts/run_task3.py --config configs/task3/baseline.yaml --split real-val --taxonomy-source gold --output outputs/task3/zero.oracle.json
python scripts/run_task3.py --config configs/task3/few_shot.yaml --split real-val --taxonomy-source gold --output outputs/task3/few.oracle.json
# Unseen synthetic exams; only isolated, non-quarantined entries are evaluated
python scripts/run_task3.py --config configs/task3/baseline.yaml --split synthetic-heldout --taxonomy-source gold --output outputs/task3/heldout.oracle.json
# Error propagation: supply Task2 predictions for exactly the selected validation IDs
python scripts/run_task3.py --config configs/task3/baseline.yaml --split real-val --taxonomy-source task2-json --taxonomy-json outputs/task2/real-val.json --output outputs/task3/zero.predicted.json
```

`--taxonomy-source gold` is oracle mode and is prohibited for public records. `task2-json` is the Task 2 predicted-label mode. Accepted taxonomy files are a map `{"TEST-ID": []}`, an official array `[{"sample_id":"TEST-ID","output":{"taxonomy_error":[]}}]`, or the team's internal array/map with `labels` and successful `parse_ok`. Invalid/duplicate labels, duplicate IDs, missing/extra IDs and `parse_ok:false` fail. An explicitly supplied empty list is retained; missing values never become `[]`.

If a verified Task 2 prediction export is unavailable, `self-diagnosis` provides a separate local Qwen baseline. It excludes gold labels, instructor feedback and requested Level from the taxonomy prompt; every emitted label must be tied to a source quote, a supplied problem ID when available, a confidence and stated evidence limits. Formatting errors receive one bounded retry. If formatting still fails, the audit records `diagnosis_unavailable`, an empty taxonomy, and `status: uncertain`; this is not a clean-code conclusion. Unsupported labels, invented IDs, unsupported compiler claims and taxonomy/finding disagreement are never accepted. An oracle run that must not reuse predicted diagnosis uses `--taxonomy-source gold` without `--diagnosis-audit`:

```bash
python scripts/run_task3.py --config configs/task3/self_diagnosis_zero_shot.yaml --split real-val --taxonomy-source self-diagnosis --output outputs/task3/self-diagnosis.real-val.json
python scripts/run_task3.py --config configs/task3/self_diagnosis_zero_shot.yaml --split real-val --taxonomy-source gold --diagnosis-audit outputs/task3/self-diagnosis.real-val.taxonomy-diagnosis.json --output outputs/task3/oracle.same-diagnosis.real-val.json
```

Private diagnosis attempts and prompts are stored beside the output under ignored `outputs/`. They may contain student code and must remain local. `self_diagnosis_few_shot.yaml` is the same-Level, train-only K=1 ablation. A saved diagnosis audit separates taxonomy-model provenance from the feedback run; do not tune these baselines with public output.

When a C++ compiler is available, selected records receive a syntax-only check (`g++`, `clang++`, or `c++`) with a five-second timeout, bounded source/diagnostic sizes, and no program execution. Compiler failures are passed as evidence; a successful syntax check does not establish logic correctness. A missing compiler or timeout is explicitly unknown, never “no compile error.” Narrow source contradiction checks cover initialized counters/accumulators, legal pointer subscripting, a rewind followed by consuming a file header, and input-domain constraints. These are regression safeguards, not a general C++ semantic proof.

The Level 3 diagnosis/direction screen is a warning-only quality review, separate from the disclosure guard. With `adequacy_retry_policy_version: 1`, review candidates can trigger a bounded retry. If a Level 3 answer still requires fallback after retries, inference stops with the sample ID and exports no generic Level 3 answer. Manual feedback correctness and Level review are reported separately from guard pass rates.

Every item in an array-form Task 2 export is checked for a valid, unique ID before projecting the selected IDs; extra prediction bodies are not interpreted, and their count/hash are recorded. Legacy label-only exports without `parse_ok` provenance are rejected by default. Use `--allow-unverified-task2-export` only when the source is a known legacy Task 2 writer; the run manifest explicitly marks provenance as unknown. This opt-in does not waive taxonomy validation or ID coverage checks.

```bash
# Fails before model loading if predictions are absent/invalid
python scripts/run_task3.py --config configs/task3/baseline.yaml --split public --requested-levels data/raw/public_test_release/task3_requested_levels.json --taxonomy-source task2-json --taxonomy-json outputs/task2/public.predictions.json --output outputs/task3/predictions.json --dry-run
# Explicit real public generation: remove --dry-run only after supplying actual Task2 predictions
python scripts/run_task3.py --config configs/task3/baseline.yaml --split public --requested-levels data/raw/public_test_release/task3_requested_levels.json --taxonomy-source task2-json --taxonomy-json outputs/task2/public.predictions.json --output outputs/task3/predictions.json
```

Dry-run still validates taxonomy coverage, then uses a TEST-ONLY generic mock backend. A requested `predictions.json` is saved as `predictions.mock.json` during dry-run. Never submit mock predictions. The strict local validator checks exact ordered IDs, unique IDs, exact output keys, valid labels and nonempty feedback. Example schema, using artificial data only:

```json
[{"sample_id":"TEST-ONLY-001","output":{"taxonomy_error":[],"feedback":"Em tự kiểm tra lại bài làm nhé."}}]
```

Public preparation requires `task3_requested_levels.json`, merges its ID/Level pairs with `task3_feedback.json`, and rejects missing, duplicate or mismatched IDs/Levels. Public inference also requires the file and orders output to match it. Public records still have no taxonomy or feedback target. Validate a prediction bundle offline against the same file before use:

```bash
python scripts/validate_task3_submission.py \
  --predictions outputs/task3/public.predictions.json \
  --requested-levels data/raw/public_test_release/task3_requested_levels.json
```

The validator checks UTF-8 JSON, exact row and field structure, requested ID order and coverage, taxonomy labels, and nonempty feedback. It reports only record and requested-Level counts.

No official validator was present among the local release files. Final leaderboard acceptance awaits that validator. Inference stores `.run.json`, `.traces.json`, `.metrics.json` and an ID-only `.review-template.csv` beside the prediction file. Raw guard violations, retries and fallback use are recorded without copying raw generated failures into the trace. Generated tokens/latency include all retries. Mock byte-token counts are clearly marked, use a separate smoke budget, and are never represented as Qwen measurements.

Inference preflight measures both the initial prompt and the strict-retry prompt, including the fixed retry hint and reserved output-token budget. A sample whose essential initial prompt cannot fit blocks generation; a sample that fits initially but not with the retry prompt is marked `passed_with_retry_fallback` and uses the conservative fallback if a retry is needed. The progress cache is bound to the exact prompt messages, tokenizer/chat-template identity, model/revision, adapter, inference settings, taxonomy, input and prepared-manifest hash. Completed rows are validated; malformed completed rows and duplicate IDs fail closed, while an incomplete final JSONL line is ignored and disclosed in trace audit metadata. Progress files are private and rewritten atomically.

Review CSVs are generated as `.review-template.csv` and contain no student code or target text. Existing nonempty templates are preserved by default; `--force-review-template` first retains a timestamped backup. When predictions and a run manifest are supplied, each row binds the annotations to the prediction hash, sample order and run identity. Scoring annotations requires a matching manifest (`--run-manifest`, or the adjacent `<predictions>.run.json`); unreviewed IDs and empty review rows do not count as completed reviews. Oracle-mode evaluation rejects predictions whose taxonomy differs from the supplied gold taxonomy.

## Linux/WSL2 CUDA QLoRA

Create a **separate** environment so Task 1/2 dependency versions remain untouched. The direct package pins are in `requirements-task3.txt`; transitive versions are captured by run metadata and `pip freeze`. TRL is pinned for interoperability; this implementation uses Transformers `Trainer` with explicit labels rather than relying on template generation markers.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements-task3.txt
python -m pip check
python -m pip freeze > outputs/task3/environment.txt
python scripts/train_task3.py --config configs/task3/qlora.yaml --dry-run
# Downloads tokenizer only, then audits both candidate sequence budgets. No model weights/training.
python scripts/train_task3.py --config configs/task3/qlora.yaml --audit-tokenizer
# The following commands explicitly start training, in three separate output directories:
python scripts/train_task3.py --config configs/task3/qlora.yaml --experiment synthetic --output-dir checkpoints/task3/synthetic
python scripts/train_task3.py --config configs/task3/qlora.yaml --experiment real --output-dir checkpoints/task3/real
python scripts/train_task3.py --config configs/task3/qlora.yaml --experiment mixed --output-dir checkpoints/task3/mixed
# Load the selected adapter for the same fixed validation set
python scripts/run_task3.py --config configs/task3/baseline.yaml --split real-val --taxonomy-source gold --adapter checkpoints/task3/mixed/adapter --output outputs/task3/mixed.oracle.json
```

NF4 uses double quantization; LoRA defaults to r=16, alpha=32, dropout=0.05 on attention and MLP projections. Defaults: seed 42, LR 1e-4, 3 epochs, batch 1, accumulation 4 and gradient checkpointing; BF16 if supported, otherwise FP16. Four-bit execution requires CUDA. Neither native Windows QLoRA nor Unsloth is required for CPU development.

The actual tokenizer audit on this strict pool found **13/537** training/validation examples over 2048 tokens, **0/537** over 4096, and a maximum fitted sequence length of **3755**. `auto` therefore chooses 4096. The audit is repeated against current input hashes; overlength examples cause an explicit stop rather than lost code/targets. These are local tokenization measurements, not GPU execution results.

For masking, the assistant-generation prefix must exactly equal the prefix of the fully templated prompt-plus-completion. Every prefix token gets label `-100`; completion/end-of-turn tokens remain supervised. The collator pads labels with `-100`. Templates without that prefix property fail explicitly. No `assistant_only_loss=True` assumption is made. Tests verify this with synthetic tokenizers and the real cached Qwen tokenizer when available. Sequence construction never truncates targets. Real feedback is used as the assistant target only.

`checkpoints/task3/<experiment>/` receives PEFT adapters, tokenizer, training/validation loss history, configuration, dataset hash, git commit, package versions, device/CUDA, tokens, wall time and peak GPU memory. Run metadata also records optimizer-step timing percentiles, session-only sample and supervised-token throughput, effective sample/step counts, and finite nonzero LoRA gradient/update audits. Resume requires a complete Trainer checkpoint, including adapter/model weights and optimizer, scheduler and RNG state, compatible config/model/data hashes, and matching step limits. Remote trainer reporting is disabled. Dry-run writes `dry-run.json` with `training_succeeded:false`; it never claims a checkpoint was trained. CPU-only dependency/API and masking validation does not verify CUDA kernels, VRAM fit or learning quality.

The explicit training path performs a runtime safety check before model loading. With the 5090 config it requires exactly one visible GPU, an NVIDIA GeForce RTX 5090 name, BF16 support, at least 24 GiB free, and a successful `nvidia-smi` check showing no competing compute process. If workload status cannot be verified or another GPU process is present, training stops without terminating or disturbing it. `stage2_learning_rate` defaults to `2e-5`; staged training uses that rate for the real-data adaptation stage, starts a fresh optimizer, and requires an explicit total `--max-steps`.

## Compliance and diagnosis evaluation

The Task 3 guard wraps the existing synthetic guard without changing it. It permits Level 2 inline diagnostic identifiers/expressions and compiler diagnostics, rejects obvious code/answer leakage at Levels 1/2, detects repair language at Level 2, specific diagnoses at Level 1, obvious complete solutions at Level 3, empty text and clearly irrelevant topics (including accentless Vietnamese phrasing). An optional local structured-check callback can add semantic/relevance violation reasons. Regex and lexical heuristics cannot guarantee correctness or detect every paraphrased answer. The guard was checked locally against all 32 instructor answers with **zero flags**, without printing their content.

Generation retries with stricter prompts up to `max_retries`, then emits a conservative non-diagnostic fallback. A fallback is disclosed in metrics and may be pedagogically insufficient. A final guard pass is never proof of accurate diagnosis; raw first-attempt compliance/severe leakage and fallback rate must be reported alongside final guard rates.

```bash
python scripts/evaluate_task3.py --data-dir data/processed/task3 --split real-val --predictions outputs/task3/zero.oracle.json --traces outputs/task3/zero.oracle.traces.json --taxonomy-source gold --output outputs/task3/zero.oracle.evaluation.json
python -m pytest tests/test_task3_*.py -q
python -m pytest tests/ -q
```

Metrics include overall/per-Level heuristic compliance, Level 1/2 severe leaks, empty responses, response characters, latency, generated tokens and taxonomy agreement **only in predicted mode when gold exists**. Diagnosis quality is reported as **not automatically measured**. There is no BLEU/ROUGE proxy for diagnostic correctness.

Human review: two reviewers independently open private source, instructor feedback and predictions locally using the ID-only CSV. Score diagnosis 0 (wrong/invented), 1 (partially supported/incomplete), 2 (supported core diagnosis); evidence 0–2; mark level compliance, severe leakage, invented errors and correct P1 dependencies. For Level 1, review whether the gentle response is consistent with the evidence without disclosing a diagnosis. Resolve disagreements before reporting agreement and mean diagnosis scores; never paste source or instructor feedback into CSV notes or public reports. Group results by level, exam type, taxonomy source and fallback status. Review is post-hoc evaluation, not intervention in the inference pipeline.

Level-swap tests hold exam/code/taxonomy constant across all four levels and check disclosure controls using scripted TEST-ONLY responses. Actual Qwen level-swap consistency, corrected-code validity and instructor-aligned diagnosis require real generation plus local human review; these have **NOT RUN**.

| Experiment | Baseline vs fine-tuned | Taxonomy | Compliance | Diagnosis quality | Runtime |
|---|---|---|---|---|---|
| Zero-shot | Baseline | Oracle | NOT RUN | NOT RUN | NOT RUN |
| Zero-shot | Baseline | Task2 predicted | NOT RUN | NOT RUN | NOT RUN |
| Few-shot | Baseline | Oracle / predicted, separate runs | NOT RUN | NOT RUN | NOT RUN |
| Synthetic SFT | Fine-tuned | Oracle / predicted, separate runs | NOT RUN | NOT RUN | NOT RUN |
| Real SFT | Fine-tuned | Oracle / predicted, separate runs | NOT RUN | NOT RUN | NOT RUN |
| Mixed clean SFT | Fine-tuned | Oracle / predicted, separate runs | NOT RUN | NOT RUN | NOT RUN |

Additional ablations: strict vs unfiltered synthetic quality, attention-only vs attention+MLP LoRA, zero vs two examples, and raw vs guarded generation. Preserve the same real validation IDs and isolated synthetic heldout entries; public records are for export, not development tuning. Default release metrics do not extend to quarantined heldout examples.

## Verification in this workspace

- Current implementation-pass verification: Task 3 offline tests **147 passed, 1 skipped**; all five Task 3 CLI `--help` entry points passed. GPU preflight, real Qwen smoke/training and human review are separate authorized/manual actions. Earlier hardware measurements below are historical and were not revalidated by offline tests.
- Relevant existing Task 1/2 regressions: **39 passed**.
- Full `tests/` suite: **397 passed, 24 skipped, 4 failed**. Failures are in the untouched Colab Task 1 secret-cell tests (2) and synthetic labeler-gate tests (2). Task 3 targeted tests pass; these failures are not attributed to the Task 3 changes and were not reproduced against a clean baseline in this run.
- Actual local preparation and manifest verification passed. The official 26/6 IDs are disjoint; all 32 real teacher targets passed their heuristic Level 1–3 compliance checks (4 Level 1, 18 Level 2 and 10 Level 3). Strict preparation retained 505 synthetic train and 47 heldout records; the additional 95 synthetic train examples were quarantined by the strict quality filter. Public records have no completion targets. Three unique overlapping groups were identified and audited. No local `predictions_full.json` was present.
- The pinned tokenizer audit passed for the 537 real train/validation records: 524 fit 2048 tokens and all 537 fit 4096 (maximum observed length 3,755); selected context length is 4096. Tokenizer revision: `c03e6d358207e414f1eca0bb1891e29f1db0e242`.
- Previously recorded RTX 5090 measurements (driver `590.48.01`, CUDA `12.8`, PyTorch `2.8.0+cu128`, BF16 and a tiny NF4-LoRA update) are historical and were **not rechecked in this implementation pass**. The tiny synthetic layer test is not a Qwen training test. The new training gate requires 24 GiB free and no other compute process for the `qlora_5090` configuration.
- A 20-step Qwen training smoke test was **NOT RUN**. No GPU utility was queried and no Qwen model weights were downloaded during this implementation pass. Full-model peak VRAM and training throughput are **NOT MEASURED**. No full training or real inference was started, and human annotation scores/leaderboard results remain **NOT RUN**.
- The benchmark `JSON`, `CSV` and `Markdown` templates were initialized with every experiment marked `NOT RUN`.
- `ruff check` and `pip check` passed. Mock inference and CLI tests exercise the TEST-ONLY paths only.

## RTX 5090 run commands

Use the prepared local Python environment and run these commands from the repository root. They do not install drivers or replace system CUDA:

```bash
# Rebuild the strict, privacy-safe prepared data and manifest
.venv-task3/bin/python scripts/task3_prepare.py --filter-synthetic strict

# Recheck CUDA + the tiny NF4/LoRA operation (not a model training smoke test)
.venv-task3/bin/python scripts/task3_gpu_preflight.py --smoke-4bit

# Re-measure tokenizer lengths before any Qwen weights are loaded
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --audit-tokenizer

# Optional bounded real Qwen training smoke: exactly 20 optimizer steps.
# Run only after the configured runtime gate confirms >=24 GiB free and no competing workload.
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --output-dir checkpoints/task3/qlora_5090_smoke --max-steps 20 --smoke-test
```

Do not run the 20-step smoke on a busy/shared GPU. It uses the real model, strict mixed-balanced data, the selected 4096-token context, and checks finite loss, finite nonzero LoRA gradients and parameter updates, exact optimizer-step completion and adapter reload. The runtime gate fails closed when it cannot verify GPU isolation; it never terminates other processes.

After the GPU is available and the smoke has been reviewed, the full three-epoch training runs can be launched separately. Use a distinct output directory for each experiment:

```bash
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --experiment synthetic --output-dir checkpoints/task3/qlora_5090_synthetic
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --experiment real --output-dir checkpoints/task3/qlora_5090_real
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --experiment mixed --output-dir checkpoints/task3/qlora_5090_mixed
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --experiment mixed_balanced --output-dir checkpoints/task3/qlora_5090_mixed_balanced
```

Each command starts the configured three-epoch QLoRA run and is intentionally **not** run by preparation, preflight or dry-run. `mixed_balanced` is the default configured 5090 experiment; the other commands are distinct source-data comparisons. Review the tokenizer audit, runtime gate, and resulting run manifest for every experiment. For a two-stage synthetic-to-real adaptation experiment, choose an explicit total step budget; stage 2 uses `stage2_learning_rate` and starts a fresh optimizer:

```bash
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --experiment staged --output-dir checkpoints/task3/qlora_5090_staged --max-steps 1000
```

The staged example requests 1,000 total optimizer steps (750 synthetic, 250 real with the default 0.75 fraction); replace the total if a different budget is intended. It is step-capped by design, not an epoch-based run. To resume a single-stage run, pass a complete compatible Trainer checkpoint directory while keeping the same config and step-limit arguments used by that run:

```bash
.venv-task3/bin/python scripts/train_task3.py --config configs/task3/qlora_5090.yaml --resume-from-checkpoint checkpoints/task3/qlora_5090/checkpoint-N
```

Replace `N` with the saved optimizer step. Resume rejects incomplete checkpoints or model/config/data-manifest mismatches. Staged checkpoints cannot be resumed through the single-stage resume option.

## Privacy and limitations

Raw/synthetic/processed data, all predictions/reviews, model assets and checkpoints remain under ignored directories. ZIP files and local environment directories are ignored. No student source or feedback is sent to an external model API; Hugging Face receives model/tokenizer artifact requests only. Keep hosted coding agents away from private record content: use local aggregate scripts and synthetic fixtures. Record AI coding assistance in the assignment report. Nothing is pushed or submitted automatically.

Limitations include the very small real validation set, templated synthetic targets, noisy execution flags, conservative hash/provenance grouping, incomplete semantic leakage/relevance detection, no automatic diagnosis judge, no official validator, and unexecuted Qwen training/inference quality experiments. Corrected Level 4 code is generated text and is not automatically compiled. Task 2 predictions must be supplied locally for predicted-taxonomy/public inference; the source Task 2 writer may encode an absent taxonomy as `[]`, which its output shape cannot distinguish from a genuinely empty prediction.

Implementation references: [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct), [PEFT quantization](https://huggingface.co/docs/peft/developer_guides/quantization), [Transformers 4.57.1 Trainer](https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/trainer), [TRL 0.24.0 SFT loss modes](https://huggingface.co/docs/trl/v0.24.0/en/sft_trainer).

### Round 11 diagnostic controls

`configs/task3/r11_compiler_control.yaml` supplies C++11 syntax-only evidence from `/usr/bin/g++` with a five-second timeout. Actual feedback prompts distinguish `compiled`, `compile_error` and `unavailable`; passing syntax does not establish program correctness. No student program is executed.

Real self-diagnosis now records `epistemic_status` and a nullable `taxonomy_prediction`. `uncertain` and `unavailable` are not clean-code predictions. If any selected record remains unresolved, the real CLI saves audits and a `blocked_uncertain_taxonomy` run manifest, then refuses complete prediction export. The submission schema has no unknown-label representation. The optional `r11_noncompile_rediagnosis.yaml` makes one bounded, generic non-compile recheck after an unsupported compile finding is filtered; it does not convert failure into an empty-label prediction.

Direct baseline controls `r11_direct_one_more.yaml` and `r11_direct_zero_more.yaml` differ only in the cardinality wording. The default builder says “zero or more”, consistent with legal empty taxonomies. New direct attempt journals capture exact prompt messages; older B prompts reconstructed from inputs remain explicitly reconstructed.

`--oracle-findings PATH` is restricted to non-public `gold` diagnostic mode. The input requires explicit review approval with provenance, exact source/statement hashes and exact source excerpts. Approval means approval for this experiment, not a claim of human verification. Finding context persists across retries; Level 1 receives only an issue-presence flag. Empty supplied findings do not establish clean code. These inputs must remain private under ignored `outputs/` and must never be used for public inference. See [the Round 11 report](../reports/task3/TASK3_ROUND11_MECHANISM_AND_ORACLE_20261020.md) for the approved annotation scope, failed runs and limits of the evidence.

### Round 12 structured oracle renderer

`python scripts/task3_render_oracle.py --config configs/task3/r12_adequacy_diagnostic.yaml --findings outputs/task3/mechanism-round11/findings-approved-C2.json --split real-val --output-dir outputs/task3/renderer-round12/reproduce-oracle` performs deterministic development-only rendering, with no model call or student program execution. It validates approval/source/statement binding, preserves approved fact/cause/action wording, checks compiler error severity at the source span, and projects only content permitted at Levels 1–3. Inputs and structured documents remain private under ignored outputs. Gold labels copied for schema compatibility are not model predictions. Empty supplied findings never establish clean code.

The optional `quality_review_policy_version: 4` recognizes a bounded family of positive, directed loop-bound relations to existing source values. It rejects generic declaration advice and unsupported direction/expression families; it is not a factual correctness checker. Legacy defaults and disclosure guards remain unchanged. See [the Round 12 report](../reports/task3/TASK3_ROUND12_RENDERER_AND_ADEQUACY_20261020.md) for fixture metrics, retained false acceptances, false-rejection limits, full Task 3 checks and the narrow compiler helper permission fix.

### Round 14 joint taxonomy and feedback candidate

The public release requires both taxonomy and Vietnamese feedback, although the sample training input includes taxonomy. Task 2 predictions are **optional**, not a dependency of the new Round14 CLI. The original CLIs/configs and R12/R13 diagnostic controls remain available with their historical restrictions.

`configs/task3/r14_direct.yaml` is candidate A (one Qwen request for model taxonomy, private rationales and feedback). `r14_two_stage.yaml` is B (model taxonomy followed by feedback). Both use pinned Qwen NF4, fresh C++11 syntax-only evidence, no student execution and K=0. Gold/teacher text is removed from model inputs. The independent-prompt classifier fallback makes explicit decisions; parsing errors never manufacture `[]`. Empty labels remain an unverified model prediction. Exact quotes do not certify causes.

The controller saves each completed ID and exact attempts under ignored outputs/task3; failed IDs remain unresolved and resumable. Resume identity binds all prompt inputs/config/implementation/tokenizer. Level1 uses a neutral projection; Level2 repair disclosure and CJK are blocked. Level3 action screens and Level4 code-presence checks are limited heuristics. A truthful epistemic feedback fallback is explicitly marked inadequate for diagnosis/action; it is never counted as useful feedback or verified clean code.

```bash
# Actual local model runs on the same train-derived development selection.
.venv-task3/bin/python scripts/task3_round14.py --config configs/task3/r14_direct.yaml --phase development --output-dir outputs/task3/round14/new-dev-A
.venv-task3/bin/python scripts/task3_round14.py --config configs/task3/r14_two_stage.yaml --phase development --output-dir outputs/task3/round14/new-dev-B
# Public execution requires a prior train-only selection freeze matching code/config.
# Follow the selected config and freeze recorded in the Round14 report; do not tune on public output.
```

The metadata verifier checks the supplied supplemental ZIP/member hashes, exact328 IDs, official Level counts115/163/50/0, label definitions and sample output **shape**. Public source is loaded only after the selection freeze passes. Final predictions are a candidate for review, not a leaderboard submission or quality certification. Historical QLoRA comparisons are documented in the final/follow-up reports; their adapters are absent in this Docker workspace and were not silently substituted.
