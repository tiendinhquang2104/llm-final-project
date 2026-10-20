# Task 3 Docker recovery and development evaluation — 20 October 2026

## Git and experimental provenance

Workspace `/workspace/llm-final-project`, branch `feat/task3-quality-round5`; initial HEAD
`64e2e3746af851eb0bed812b83192d005bf501ed`, clean working tree.
Remote `git@github.com:tiendinhquang2104/llm-final-project.git`.
Commit `0c4ddfd3498cc8cd84d58d27be741a84ffa5b998` exists and is an ancestor of HEAD.
No clone, reset, clean, checkout, SSH key modification, push, public inference or leaderboard submission.

Round 9 code is present; its complete experimental state is not recoverable. Initial HEAD is one commit
beyond Round 9, with two Round 10 prompt changes, its config/test and historical review. These existing
changes are preserved. No new prompt, guard, taxonomy or method change was introduced in this session.
Switching to an R9 YAML at current HEAD alone would not recreate byte-identical R9 direct prompts,
because the later commit also changed the direct system/retry text. Exact R9 code requires a separate
checkout of `0c4ddfd`, without resetting this branch. Measurements here use the inherited R10 config.

Read `docs/task3.md` and the Round 9/Round 10 report sections. The user confirmed that old raw attempts,
predictions and model cache are unavailable, and authorized regenerating a manifest from the supplied ZIP
and downloading the pinned model. Old raw attempts were **not reviewed here**. The committed historical
review distinguishes B's unsupported diagnosis/Level-1 disclosure at EX02-S201, JSON fences plus Level
violations at its first heldout stop, and C's policy/content rejections causing four real-val fallbacks.
Those are historical findings, not new measurements.

## Recovery and data validation

Initially only Git-tracked split files and `.gitkeep` placeholders existed. Python was also absent.
The archive later appeared at `/workspace/llm-final-project/data-20261017T044357Z-1-001.zip`:
841,810 bytes; SHA-256 `8c04e4e01be73952cb255fb5efd707c758205c19457fa651d944fc02780a3e1e`.
Its three outer entries include a nested public-release bundle and `generate-dataset.zip`.
The release bundle contains `sample_dataset.zip` and `public_test_release.zip`.

Validated paths and symlink types before extracting; skipped `__MACOSX`; compared any existing target
bytes before writing only absent files. Extracted/checked 924 files: 39 sample files to
`data/raw/sample_dataset`, 335 public files to `data/raw/public_test_release`, 550 synthetic files to
`data/synth/generate-dataset`, including its `heldout/`. File hashes are in the ignored local
`outputs/task3/new-docker-extraction.json`. No unchecked overwrite, data regeneration or gold edit.
Public bytes were extracted for recovery, not used to select prompts/examples/methods.

| Data check | Current result | Comparison/limit |
|---|---|---|
| Real raw records | 32 | Historical count matches |
| Synthetic raw records | 612 | Historical count matches |
| Heldout raw records | 65 | Historical count matches |
| Official real split | 26 train / 6 val, disjoint | Same Git blobs as Round 9 |
| Strict development partitions | 26 real-train, 6 real-val, 495 synthetic-train, 47 heldout, 135 quarantine, 0 public | Development-only manifest, not historical all-source manifest |
| Schema mismatches | 0 | Existing loader/audit |
| Heldout provenance | 47/47, four exams | Levels 1/2/3/4: 22/15/6/4 |
| Heldout overlap vs remaining development | 0 IDs, original submission IDs, code hashes, group keys | Public overlap not checked in this development-only preparation |
| Requested public Levels | Missing | Public-stage prerequisite only; development remains usable |
| Round 9 private attempts/outputs | Unavailable, confirmed by user | No claim of raw-attempt re-review |

The original CLI failed first on missing `sample_dataset/exams.json`; after extraction, all-source CLI
preparation stops with `public release requires a separate task3_requested_levels.json file`.
Used the existing `src.task3.dataset.prepare` API with real/synthetic/heldout roots to prepare development
without guessing public ID/Level pairs. No preparation code or schema checks were changed.

Current strict filtering quarantines 30 overlaps plus 105 quality exclusions. Reason counts (can overlap):
45 clean-signal contradictions, 10 compile-fail contradictions, 10 repair-guidance, 40 Level-4 placeholders,
4 specific-diagnosis. Old docs say 505 train / 125 quarantine and 95 quality exclusions; later committed
FINAL reports say 496 / 134 and 9 repair-guidance flags. Current result is 495 / 135 and 10 such flags.
These differences are disclosed; data/gold/filter rules were not changed to force historical counts.
There is no old raw-input digest list available for byte-for-byte comparison. A historical manifest digest
alone cannot prove source equivalence; this is a current development evaluation, not an exact historical
experiment reproduction. Real-val and heldout counts and fixed split membership match the intended scope.

SHA-256 evidence:

- train IDs: `e69a9e27f7bc26e1fc969087878c03bd04a0d47abc2f0110923be20db04b258e`
- val IDs: `64225a4813eb4a0d8025c3f56e6d3b358d66178d4f26c98f132758896fe8bf80`
- current development manifest: `b311193f5c9fcf683019b1ae97c6e1017cfb4572cbcc1f3dfe2a3d9f3a753ee0`
- real code-file aggregate: `8e77fa0236de27732e73538834fcfcb6158761507894fccd6dbb0fc655a59e7a`
- heldout code-file aggregate: `463de2777b66ee629030843772bc789cd4abdeb89bcba745d8d267366a94f6a1`

`verify_prepared` checked every processed partition digest. The full new source/processed hashes remain
in the ignored manifest; no raw data or private predictions are staged.

## Runtime

| Component | Evidence |
|---|---|
| OS / Python | Ubuntu 24.04.3; installed Python 3.12.3 and venv support |
| Environment | New `.venv-task3`; shared `/data/.venv` initially had broken interpreter links and lacked Task 3 dependencies; no shared package edits |
| GPU / driver | RTX 5090, 32,607 MiB; driver 590.48.01, driver CUDA support 13.1 |
| VRAM snapshot | 27,623 MiB free in preflight; fluctuates with shared host activity |
| PyTorch / CUDA | `2.8.0+cu128`, runtime 12.8, sm_120 supported; one device; BF16 supported |
| CUDA execution | Matmul forward/backward passed |
| NF4 runtime | Tiny NF4/32-parameter LoRA forward/backward/update passed; not a Qwen training experiment |
| Libraries | Transformers 4.57.1, tokenizers 0.22.2, accelerate 1.11.0, PEFT 0.17.1, bitsandbytes 0.48.1, PyYAML 6.0.3, pytest 8.4.2, Pydantic 2.14.1 |
| Tokenizer/config | Qwen chat template passed; resolved revision matches pin exactly |
| Model | `Qwen/Qwen2.5-Coder-7B-Instruct`, revision `c03e6d358207e414f1eca0bb1891e29f1db0e242`; downloaded to ignored local HF cache |
| Compiler | `g++`, `clang++`, `c++` absent. Existing C++11/5-second syntax-only function returned unavailable on three development records; no program execution or compile-correct claim |

Initial Task 3 tests: 338 passed, 9 skipped, 1 failed because the Task 2 integration imports Pydantic.
Installed the dependency already required in `pyproject.toml`; no source/test workaround.
After dependency/tokenizer setup: **340 passed, 8 skipped**. Skips: five compiler cases, one explicitly
configured portable-toolchain case, one opt-in GPU test, one datasets-dependent training test.
Real NF4 smoke ran separately via the preflight CLI. `pip check` passed.
No training-specific `datasets`/TRL dependencies were installed solely to run optional training coverage.
Full package versions are recorded locally in `outputs/task3/new-docker-environment.txt`.

## Fixed method and evaluation policy

Config: `configs/task3/self_diagnosis_zero_shot_round10.yaml`; seed 42, greedy, context 8192,
feedback/output 512 tokens, diagnosis 384 tokens, two retries, K=0, NF4, prompt policy 7 and guard 2.
The inherited changes test (1) nonspecific evidence-consistent Level 1 review wording, and (2) Level 2
location/cause without action versus an explicit Level 3 useful direction. The 26 real-train rows contain
2 Level 1, 15 Level 2 and 9 Level 3 examples; official `label_space.json` definitions were checked.
No validation-ID rule, extra prompt change, public example, new training or guard relaxation.
Taxonomy remains the ten official groups; internal `off_by_one` belongs to `Lỗi vòng lặp`; gold unchanged.
C uses gold only to isolate feedback quality and is not a deployable public method.

Results and source review are recorded below after the new runs. Completed output bundles alone are
eligible for full-split taxonomy scoring and strict offline validation. Partial accepted records are counts,
not full-split metrics. Factual safety, issue coverage and Level ceiling are separate judgments; neutral
fallbacks can be safe and under the ceiling while teaching nothing useful.

## Six-row real-val results

All three arms loaded the real pinned Qwen checkpoint successfully and exported complete six-row bundles.

| Arm | Complete | Taxonomy macro-F1 / micro-F1 / exact | Fallback | Final heuristic Level pass | Source-review Level ceiling |
|---|---:|---|---:|---:|---:|
| A self-diagnosis pipeline | 6/6 | 0.000 / 0.000 / 2/6 | 1/6 | 6/6 | 6/6 |
| B independent strict direct | 6/6 | 0.040 / 0.167 / 0/6 | 0/6 | 6/6 | 5/6 |
| C gold taxonomy feedback | 6/6 | Gold supplied; not a model taxonomy score | 0/6 | 6/6 | 6/6 |

A still exports six actual empty taxonomy predictions. Three diagnosis records are unavailable after
non-exact source quotes exhaust bounded retries. Three are marked validated after evidence filtering
removes unsupported compile claims in the absence of a compiler. These statuses do not mean clean code.
B produced six valid JSON objects on the first attempt; its one correct label is incomplete against the
multi-label reference and no row exactly matches. Gold remains unchanged, including the historical
S201 overflow/S211 extra-stdout candidates, which are not added to the references.

Fallback reduction is not reliable semantic improvement. Compared with historical R9 A 5/6 and C 4/6,
current A 1/6 and C 0/6 are accompanied by accepted invented diagnoses and unsupported praise.
The historical comparison is descriptive, with the data/provenance differences above; it is not a paired
controlled measurement of the prompt effect.

Single-agent source review below is **not** independent human annotation or reviewer agreement.
Factual safety: 0 invented/wrong, 1 mixed/unsupported assertion, 2 supported or safe neutral text.
Technical issue coverage: 0 no supported issue explained, 1 partial supported issue, 2 supported core
issue plus useful direction where Level 3 requires it. Level 1's intentionally nonspecific flag can respect
the ceiling but gets no technical diagnosis coverage credit; this is not a reason to disclose more.
Safe fallback also receives zero coverage. Chinese text affects language quality separately.

| ID | A factual / coverage | B factual / coverage | C factual / coverage | Review finding |
|---|---:|---:|---:|---|
| EX01-S106 | 1 / 1 | 0 / 0 | 1 / 1 | A/C identify an invalid bounds access, but invent an n-element allocation and an incorrect previous-node deletion story; their causal explanation is unreliable. B invents a pointer assignment. The non-advancing traversal is missed. |
| EX01-S111 | 0 / 0 | 1 / 0 | 0 / 0 | A falsely says an initialized index is uninitialized and switches language; C falsely calls a declared variable undeclared. B offers generic file/path advice, misses actual syntax/redeclaration defects, and directs a repair at Level 2. |
| EX01-S112 | 2 / 0 | 1 / 1 | 2 / 1 | A uses neutral fallback after Level-2 repair/code leakage. B finds the hard-coded filename but names the wrong expected file. C identifies literal-versus-parameter hard-coding after two rejected repair attempts, with mixed Chinese text. |
| EX02-S201 | 1 / 0 | 2 / 0 | 1 / 0 | A/C claim the work is nearly correct without establishing that claim; B only flags need for review. No technical leakage or overflow diagnosis in final text. |
| EX02-S211 | 1 / 0 | 2 / 0 | 1 / 0 | Same nonspecific final behavior; the extra stdout issue is not explained. |
| EX02-S212 | 2 / 2 | 1 / 2 | 2 / 2 | All identify an undeclared loop bound and give a useful direction using the existing digit count. B additionally misidentifies its relation to the original-number variable. C's first overlong code attempt is rejected; concise repair accepted. |

Mean factual safety / technical coverage (0–2): A **1.17 / 0.50**, B **1.17 / 0.50**, C **1.17 / 0.67**.
These are transparent judgments on six repeatedly reviewed development rows, not population estimates.
The B Level-2 instruction at EX01-S111 is a semantic guard miss, not grounds to weaken the guard.
A/C have unsupported “nearly correct” praise at both Level-1 rows; A and C each contain Chinese in one
Level-2 answer. The Level ceiling table measures disclosure only, not language, truth or adequacy.
No accepted full solution at Level 3 and no generic Level-3 fallback were substituted.

All three complete files passed `validate_submission` with the exact development ID-to-Level mapping
loaded from prepared records: 2 Level 1, 3 Level 2, 1 Level 3. No public requested-level file was invented.
Offline evaluator reproduced the taxonomy numbers. Direct traces lack a guard-version field, so supplying
them to the generic pipeline evaluator together with the version-2 manifest correctly raises a mismatch.
For B, evaluation used the runner's existing no-trace interface with the actual manifest (guard 2); fallback
count comes from B's run manifest. Raw direct traces were preserved without edits. A/C evaluate with their
full versioned traces. This interface limitation is disclosed, not bypassed by changing any guard.

## Synthetic-heldout: full runs attempted, none exported a full split

| Arm | Requested | Completed feedback records | Stop ID | Exact cause | Fallback on completed prefix only | Full-split taxonomy / semantic metrics |
|---|---:|---:|---|---|---|---|
| A pipeline | 47 | 22 | SYN-HO-SINGLE-0014 | Three Level-3 `code_block_gt_1_line` violations; generic fallback refused | 1/22 (4.5% of prefix), not a 47-row rate | Not scored |
| B strict direct | 47 | 0 | SYN-HO-SINGLE-0000 | All three responses wrap JSON in markdown fences; strict JSON parser rejects | No fallback substitution; rate undefined with zero accepted rows | Not scored |
| C oracle feedback | 47 | 21 | SYN-HELDOUT-0010 | Three `level3_direction_candidate` retries; adequacy gate exhausted, generic fallback refused | 2/21 (9.5% of prefix), not a 47-row rate | Not scored; gold condition is not taxonomy prediction |

Completed counts refer to accepted feedback in private progress journals (A/C) or validated direct attempts
(B); none is a complete exported prediction bundle. A's taxonomy diagnosis stage processed all 47 rows,
but this does not mean 47 feedback records completed, and no whole-split A score is calculated from it.
No full-split prediction file, schema-validation claim or F1 is produced for these partial runs.

New raw-attempt review at the stops:

- A: source has a missing semicolon after a string declaration. All three responses call it a comma;
  later attempts additionally insist on initialization although the actual fault is punctuation. They
  do include repair headings and a semicolon in snippets, but repeatedly include more than the allowed
  one code line. The direct failure trigger is Level-3 guard exhaustion, not empty generation or JSON.
  Mixed/incorrect explanation and disclosure are separate problems; “no direction generated” would be inaccurate.
- B: the final Level-1 feedback text is a nonspecific review flag, with no technical disclosure. The raw
  taxonomy still predicts a logic error against unchanged empty gold, but the actual stop is schema-only:
  fenced JSON on all three tries. The split includes Level 4, so the existing whole-split fence-token
  constraint is not enabled; the retry wording chooses its Level-1 branch before its JSON-error branch.
  These design limits are documented and were not patched after seeing the heldout outcome.
- C: the missing semicolon is again described as a missing comma although the declaration already has
  its comma. The first attempt also falsely criticizes the GCD implementation's final sum: at termination
  one operand is zero, so that sum is the intended GCD. Later attempts advise adding an already-present
  comma. Repair headings exist, but the adequacy screen still flags all three. This is a factual/repair
  failure as well as the recorded adequacy stop, not a schema error or lack of model text.

A's sole prefix fallback is at SYN-HO-SINGLE-0010 (Level 2); C falls back there and at SYN-HO-SINGLE-0011
(Level 2). The journals record code/repair disclosure flags on the former and repeated explicit repair
advice on the latter. These neutral fallback rows have zero technical coverage. No Level-3 generic answer
was exported. Full heldout factuality, issue coverage, semantic Level rate and Vietnamese quality remain
unmeasured because the branches stopped; the stop reviews above are qualitative diagnostics, not scores
for unprocessed records. Guard pass on a partial prefix would not prove semantic compliance.

## Verification, remaining blockers and decision

After data preparation, reran Task 3: **340 passed, 8 skipped** in 3.43 seconds, zero failures.
All three complete six-row development files passed the offline validator and evaluator as described above.
There are no complete heldout files to validate. CUDA/NF4 preflight and `pip check` passed; C++11 evidence
remains unavailable. All GPU jobs ran sequentially and exited; no other workload was interrupted.

The two inherited prompt changes help real-val output completion and Level-1 disclosure control, but
accepted unsupported diagnoses, wrong taxonomy, mixed language, unsupported praise and low technical
coverage remain. All three wider development runs still stop under unchanged fail-closed checks.
The method is **not eligible to freeze** and is **not ready for public inference**.

Remaining work: obtain a compiler for syntax evidence; address taxonomy evidence quality and general
truthfulness/Level/JSON reliability using train-only design; then rerun complete development evaluation.
An original digest inventory would be needed to prove byte-identical historical data; current checksums
support reproducibility of this new run only. Public requested Levels remain absent and must be supplied
before a future public phase; they did not block development. Old raw attempts are permanently unavailable
for this session and are not a prerequisite for new experiments. No new per-ID rule or gold edit is justified.

## Reproduction commands

Use fresh output names; direct inference refuses to overwrite artifacts. Commands below intentionally
select only real-val and synthetic-heldout. They reproduce the current R10 configuration, not byte-identical
R9 code. First recover the checked archive roots above without overwriting unchecked files.

```bash
cd /workspace/llm-final-project
python3 -m venv .venv-task3  # only if no project venv exists
.venv-task3/bin/python -m pip install torch==2.8.0 transformers==4.57.1 tokenizers==0.22.2 accelerate==1.11.0 peft==0.17.1 bitsandbytes==0.48.1 pyyaml==6.0.3 pytest==8.4.2 pydantic==2.14.1
export HF_HOME="$PWD/outputs/task3/hf-cache"
.venv-task3/bin/python -m pip check
.venv-task3/bin/python scripts/task3_gpu_preflight.py --smoke-4bit --output outputs/task3/repro-gpu-preflight.json

# Existing preparation API; public requested Levels are not guessed.
.venv-task3/bin/python - <<'PY'
from pathlib import Path
from src.task3.dataset import prepare
roots = {
    'real': 'data/raw/sample_dataset',
    'synthetic': 'data/synth/generate-dataset',
    'synthetic-heldout': 'data/synth/generate-dataset/heldout',
}
m = prepare(roots, 'data/processed/task3', Path.cwd(), seed=42, filter_synthetic='strict')
print(m['partitions'])
PY
.venv-task3/bin/python -m pytest tests/test_task3_*.py -q -rs

# These are real Qwen runs, sequentially, with identical fixed config.
for split in real-val synthetic-heldout; do
  .venv-task3/bin/python scripts/run_task3.py --config configs/task3/self_diagnosis_zero_shot_round10.yaml --split "$split" --taxonomy-source self-diagnosis --output "outputs/task3/repro-r10-pipeline-$split.json"
  .venv-task3/bin/python scripts/run_task3_direct_baseline.py --config configs/task3/self_diagnosis_zero_shot_round10.yaml --split "$split" --output "outputs/task3/repro-r10-direct-$split.json"
  .venv-task3/bin/python scripts/run_task3.py --config configs/task3/self_diagnosis_zero_shot_round10.yaml --split "$split" --taxonomy-source gold --output "outputs/task3/repro-r10-oracle-$split.json"
done
```

Offline validation of complete current development bundles (without a public requested-Level file):

```bash
.venv-task3/bin/python - <<'PY'
from pathlib import Path
from src.task3.dataset import load_prepared
from src.task3.submission import validate_submission
for split, tag in [('real-val', 'real-val'), ('synthetic-heldout', 'heldout')]:
    levels = {r.sample_id: r.target_feedback_level for r in load_prepared('data/processed/task3', split)}
    for arm in ['pipeline', 'direct', 'oracle']:
        p = Path(f'outputs/task3/docker-r10-{arm}-{tag}.json')
        if p.exists():
            print(p.name, validate_submission(p, levels))
PY
```

Private new artifacts use prefix `outputs/task3/docker-r10-`; tokenizer/model cache and environment/data
audits use `outputs/task3/{hf-cache,new-docker-*}`. All remain ignored/local. This commit contains only the
sanitized report; inherited implementation/tests remain in `64e2e37`. No raw prompts, student source,
prediction bundles, datasets, ZIPs or checkpoints are staged.
