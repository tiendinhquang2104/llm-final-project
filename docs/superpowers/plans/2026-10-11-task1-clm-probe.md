# Task 1 không cần API — probe hồi quy trên embedding CLM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sinh `predictions.json` cho Task 1 cuộc thi (rubric 6 chiều + `total_score`, 360 bài public) không cần API key, chạy cùng hạ tầng Task 2 (local MLX hoặc Kaggle), train chỉ trên 32 bài gold.

**Architecture:** `src/task1/clm_probe.py`: embedding "context" của mỗi bài (đề + compile log tự sinh + code; đúng văn bản Task 2 dùng nên trúng cache) + cột `has_compile_error` → Ridge riêng cho từng chiều rubric → làm tròn, kẹp khoảng → rule compile-gate có sẵn của Task 1 (`apply_rules`, không có rule tiên quyết vì không có trạng thái từng câu) → `total_score` = tổng. Chọn `alpha` theo QWK out-of-fold (k-fold) trên gold; baseline "trung bình của fold train". Script `scripts/run_task1_clm.py` dùng chung config encoder/compile/text của Task 2.

**Tech Stack:** Python 3.12 `.venv`, numpy, scikit-learn (Ridge), pytest.

**Spec:** `docs/superpowers/specs/2026-10-09-task2-design.md` (§9: không dùng gì từ tập test để train/chọn; §10: tự compile). Thiết kế Task 1 này đã được người dùng duyệt trong hội thoại 2026-10-11.

## Global Constraints

- Train/chọn `alpha` chỉ trên 32 bài gold (`sample_dataset/task1_grading.json`); tập test chỉ để dự đoán.
- Văn bản context phải giống hệt Task 2: `build_state_texts(exam, sample, encoder.tokenizer, **cfg["text"])["context"]` với mẫu đã gắn compile log tự sinh (`attach_compile_logs`), để dùng lại cache embedding.
- Output Task 1: `[{"sample_id", "output": {"rubric": {6 chiều int trong khoảng}, "total_score": tổng}}]`, đủ đúng tập id của `public_test_release/task1_grading.json`; ghi file chỉ sau khi `src.task1.evaluator.validate_predictions` trả `[]`.
- Rule: `apply_rules(rubric, None, policy_from_exam(exam), RuleConfig(prerequisite=False, compile_gate=cfg_task1_rules.compile_gate, clamp=True))`.
- Metric: `src.task1.evaluator.evaluate` (QWK trên total, MAE, exact-match từng chiều), out-of-fold trên gold.
- Seed 42. Không gọi API, không tải model trong test. Baseline suite: 151 pass, 5 skip, 2 lỗi có sẵn (`tests/test_colab_task1_secrets.py`).
- Không ghi file id Drive vào repo (repo công khai). Nhánh `task-2`; trailer `Co-Authored-By` ghi đúng model viết commit.

---

### Task 1: Module, script, config, test

**Files:**
- Create: `src/task1/clm_probe.py`, `scripts/run_task1_clm.py`, `tests/test_task1_clm_probe.py`
- Modify: `src/task2/clm/encoder.py` (thêm `build_from_config`, chuyển từ `scripts/run_task2_clm.py`), `scripts/run_task2_clm.py` (dùng `build_from_config`), `configs/task2/clm_base.yaml` (khối `task1`)

**Interfaces:**
- `src/task2/clm/encoder.py`: `build_from_config(enc_cfg: dict, max_tokens: int, root: Path) -> tuple[encoder, heads_path]` — nội dung y hệt `build_encoder` hiện có trong `scripts/run_task2_clm.py` (MLX: `snapshot_download(..., local_dir=root / enc_cfg["local_dir"], allow_patterns=[...])`; HF: `hf_hub_download` head + `HFEncoder`). `scripts/run_task2_clm.py` import và gọi hàm này thay cho bản cục bộ (giữ hành vi).
- `src/task1/clm_probe.py`:
  - `load_rubrics(root, task_file="task1_grading.json") -> dict[str, dict]` — `{sample_id: {"rubric": {d: int}, "total_score": int}}` cho các mẫu có `output`.
  - `embed_contexts(samples, exams, encoder, text_cfg) -> np.ndarray[n, d+1]` — embedding context + cột cuối `has_compile_error(s.compile_log)` (0/1).
  - `class RubricProbe(alpha=1.0)`: `fit(X, R[n,6]) -> self` (cột hằng → lưu hằng số), `predict(X) -> np.ndarray[n,6]` float.
  - `to_rubric(row) -> dict[str, int]` (làm tròn, kẹp `0..DIM_MAX[d]`).
  - `finalize(rubric, exam, compile_gate=True) -> tuple[dict, int]` (gọi `apply_rules` như Global Constraints).
  - `run_task1_clm(cfg, encoder, gold, rubrics, public, public_ids, out_dir, registry=REGISTRY) -> dict` — `gold`, `public` là `Task2Dataset` đã gắn compile log; `public_ids` = id trong `public_test_release/task1_grading.json`.
    Ghi `out_dir/metrics.json` = `{"name", "n_gold", "cv_folds", "evaluation": "out-of-fold over gold", "alpha_selection": {str(alpha): oof_qwk}, "chosen_alpha", "systems": {"ridge": evaluate(...), "mean_baseline": evaluate(...)}, "compile": {"enabled", "compiler_id"}}`, `predictions.json`, `predictions_full.json` (float trước khi làm tròn + rubric sau rule), `resources.json`, `config.json`; một dòng `experiments/registry.csv` (task `task1`).
    Chọn alpha: QWK OOF cao nhất, hoà → alpha lớn hơn. QWK NaN tính như -inf.
- Config `configs/task2/clm_base.yaml`: thêm
```yaml
task1:
  alphas: [0.1, 1.0, 10.0, 100.0]   # ridge strength, chosen by out-of-fold QWK on the 32 gold samples
  compile_gate: true                 # Task 1 rule: compilable=0 zeroes the policy's dimensions
```
- `scripts/run_task1_clm.py --config configs/task2/clm_local.yaml [--no-compile] [--gold-root] [--public-root] [--output-dir outputs/task1]`: nạp gold/public bằng `load_task2` (code, exam_type), rubric gold bằng `load_rubrics(gold_root)`, id public từ `public_root/task1_grading.json` (assert trùng tập id của task2 file), `attach_compile_logs(cfg["compile"], [gold.samples, public.samples], enabled=not a.no_compile, root=ROOT)`, `build_from_config`, `CachedEncoder(encoder, ROOT / cfg["cache_dir"])`, `cfg["_compiler_id"]`, gọi `run_task1_clm`, in QWK/MAE OOF của `ridge` và `mean_baseline` cùng đường dẫn output. Tên run = `"task1_" + cfg["name"].removeprefix("task2_")` (ví dụ `task1_clm_kaggle`), output tại `<output-dir>/<tên run>/`. Public lọc theo `cfg["data"]["public_per_exam"]` (dùng `_select_public` của Task 2); `public_ids` khi đó = id đã chọn.

- [ ] **Step 1: Test (RED)** — `tests/test_task1_clm_probe.py` dùng `tests/_task2.make_dataset`, `FakeEncoder`, `CachedEncoder`; viết `task1_grading.json` cho gold root (8 mẫu, rubric đa dạng, total = tổng) và public root (4 mẫu, không `output`). Test:
  1. `RubricProbe` học được cột tuyến tính đơn giản và trả hằng cho cột hằng; `to_rubric` làm tròn/kẹp đúng (ví dụ `logic` 4.7 → 4, -0.4 → 0).
  2. `finalize` với exam có statement chứa `"Nhận 0 điểm nếu: vi phạm quy định, giống bài người khác, không biên dịch được"` và `compilable=0` → mọi chiều 0, total 0; exam không có câu đó → giữ `code_quality`.
  3. `run_task1_clm` end-to-end: `predictions.json` hợp lệ theo `validate_predictions` với 4 id public; `metrics["systems"]["ridge"]["n"] == 8`; `chosen_alpha` thuộc `alphas`; `alpha_selection` đủ khoá; `mean_baseline` có mặt.
  4. Văn bản context truyền cho encoder trùng `build_state_texts(...)["context"]` (kiểm tra bằng một encoder giả ghi lại texts).
  Run: `.venv/bin/python -m pytest tests/test_task1_clm_probe.py -q` → FAIL.
- [ ] **Step 2: Code** theo Interfaces. Ridge: `sklearn.linear_model.Ridge(alpha=a)` trên X chuẩn hoá theo fold (StandardScaler fit trên fold train). Baseline: trung bình rubric của fold train cho mọi bài held-out (qua `to_rubric` + `finalize`).
- [ ] **Step 3: GREEN + suite** — test liên quan, `tests/test_task2_*` (vì đổi `build_from_config`), rồi toàn bộ suite.
- [ ] **Step 4: Commit** — `"Add API-free Task 1 rubric probe on CLM embeddings"`.

### Task 2: Notebook Kaggle + docs (sau khi controller chạy local)

- [ ] `kaggle/task2_clm.ipynb` (tái tạo JSON, giữ 7 cell, `/kaggle/tmp`, `DRIVE_ID`, pin transformers): cell chạy thêm `subprocess.run(['python', 'scripts/run_task1_clm.py', '--config', 'configs/task2/clm_kaggle.yaml'], check=True)` sau Task 2; cell cuối copy `outputs/task1/task1_clm_kaggle/predictions.json` → `/kaggle/working/task1_predictions.json` và kiểm tra bằng `src.task1.evaluator.validate_predictions` (in số bài và lỗi). Markdown: thêm dòng "Ra cả `task1_predictions.json` (Task 1, probe trên embedding CLM)".
- [ ] `docs/task1.md`: mục mới "Hướng không API (probe trên embedding CLM, 2026-10-11)": cách làm, lệnh local/Kaggle, kết quả CV do controller cung cấp, hạn chế (32 gold, 2 đề khác đề thi, không có rule câu tiên quyết vì không có trạng thái từng câu).
- [ ] Kiểm tra: notebook 7 cell; `git ls-files | xargs grep -l <drive-id>` rỗng. Commit `"Run Task 1 probe in the Kaggle notebook and document it"`.
