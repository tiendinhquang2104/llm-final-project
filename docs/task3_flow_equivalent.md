# Task 3: clone and reproduce fresh flows

This is the current runbook for a fresh checkout. The only valid method names
are:

- `r15-repro-v1`: direct R15-style controller, zero-shot prompt.
- `sft-v2-repro-v1`: SFT V2-style one-attempt controller with an external
  PEFT adapter.

Both use `Qwen/Qwen2.5-Coder-7B-Instruct` revision
`c03e6d358207e414f1eca0bb1891e29f1db0e242`, seed 42, greedy decoding, NF4
double quantization and C++11 syntax-only checks. They are logically equivalent
profiles, not byte-identical historical replays.

## 1. Define the external roots

The runner expects `--data-root` to contain `processed/task3/` and
`raw/public_test_release/` directly. Do not pass the repository root if those
directories are under its `data/` child.

```bash
REPO=/path/to/llm-final-project-arm-d-plus
PY=/path/to/.venv-task3/bin/python
TASK3_DATA=/path/to/task3-data
TASK3_ARTIFACTS=/path/to/task3-artifacts
HF_CACHE=/path/to/hf-cache
```

Required layout:

```text
/path/to/task3-data/
  processed/task3/
  raw/public_test_release/

/path/to/task3-artifacts/
  r15/
    selected-prompt-freeze.json
    train-examples.json
    round14-public-candidate.json
  sft-v2/
    adapter/                        # adapter_model.safetensors + adapter_config.json
```

`HF_CACHE` must be an already-downloaded Hugging Face cache containing the
pinned revision. The runner sets offline safeguards and never downloads a
model.

The public loader needs `raw/public_test_release/task3_requested_levels.json`.
If the authorized release supplies only the official ZIP, extract only that
member; do not unpack or invent a replacement file:

```bash
unzip -p /path/to/public-test-cham-diem-phan-hoi-files.zip \
  t3-feedback/task3_requested_levels.json \
  > "$TASK3_DATA/raw/public_test_release/task3_requested_levels.json"

sha256sum "$TASK3_DATA/raw/public_test_release/task3_requested_levels.json"
# expected: 17b8d690f2d86a53a6908da7b95a966194671c9e06117d635da24b1edd70bfa5
```

## 2. Check the CLI and run offline preflight

```bash
cd "$REPO"
"$PY" scripts/task3_bootstrap.py --help
"$PY" scripts/task3_run.py --help
"$PY" scripts/task3_run.py r15-repro-v1 --help
"$PY" scripts/task3_run.py sft-v2-repro-v1 --help
```

R15 preflight:

```bash
"$PY" scripts/task3_run.py r15-repro-v1 --check \
  --artifact-root "$TASK3_ARTIFACTS" \
  --data-root "$TASK3_DATA" \
  --model-dir "$HF_CACHE" \
  --out "$REPO/outputs/task3/reproductions/r15-repro-v1-check"
```

SFT V2 preflight must receive the explicit adapter directory:

```bash
ADAPTER="$TASK3_ARTIFACTS/sft-v2/adapter"
"$PY" scripts/task3_run.py sft-v2-repro-v1 --check \
  --artifact-root "$TASK3_ARTIFACTS" \
  --data-root "$TASK3_DATA" \
  --model-dir "$HF_CACHE" \
  --adapter-dir "$ADAPTER" \
  --out "$REPO/outputs/task3/reproductions/sft-v2-repro-v1-check"
```

Preflight is model-free: it checks the data directories, pinned model snapshot
and, for SFT V2 inference, the adapter's PEFT config and weights.

## 3. Run actual inference

Actual inference omits `--check`. Use a fresh output directory for every run.
One visible CUDA device is required.

```bash
"$PY" scripts/task3_run.py r15-repro-v1 \
  --artifact-root "$TASK3_ARTIFACTS" \
  --data-root "$TASK3_DATA" \
  --model-dir "$HF_CACHE" \
  --out "$REPO/outputs/task3/reproductions/r15-repro-v1-run1"

"$PY" scripts/task3_run.py sft-v2-repro-v1 \
  --artifact-root "$TASK3_ARTIFACTS" \
  --data-root "$TASK3_DATA" \
  --model-dir "$HF_CACHE" \
  --adapter-dir "$ADAPTER" \
  --out "$REPO/outputs/task3/reproductions/sft-v2-repro-v1-run1"
```

The current runner evaluates the public 328-record contract; it has no
development/smoke subset flag. It writes `predictions.json`/`run.json` for R15
and `generations.jsonl`/`run.json` for SFT V2. It never submits or writes under
`submission-candidates/`.

## 4. Troubleshooting

- `invalid choice: r15`: use `r15-repro-v1`, not `r15`.
- `public release requires a separate task3_requested_levels.json file`: extract
  the official ZIP member shown above.
- `sft-v2-repro-v1 requires --adapter-dir`: pass the checkpoint's adapter
  directory explicitly.
- `Linear4bit ... compute_dtype`: use a checkout containing the PEFT-wrapper
  precision-audit fix in `src/task3/inference.py`.
- Never replace missing artifacts with a different checkpoint or a fake file;
  stop and supply the authorized external bytes.
