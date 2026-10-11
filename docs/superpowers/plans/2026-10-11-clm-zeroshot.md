# CLM zero-shot cho Task 1 và Task 2 (prompt rút từ 32 bài mẫu, không train) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dự đoán Task 1 (rubric) và Task 2 (nhãn lỗi) cho 360 bài public bằng CLM-8B **giữ nguyên trọng số** (Qwen3-8B + head CLM gốc, không fine-tune, không probe). 32 bài mẫu chỉ dùng để **rút quy luật viết prompt** và **thống kê tần suất nhãn** cho quy tắc quyết định, và để **đo** (số đo lạc quan, ghi rõ).

**Architecture:**
- `src/clm_zeroshot/guides.py`: định nghĩa nhãn lỗi và mô tả từng mức điểm rubric, viết lại theo cách giảng viên chấm trong 32 bài (chỉ đọc code + nhãn + điểm, **không đọc `feedback`**, không đọc gì của tập test).
- `src/clm_zeroshot/scoring.py`: chấm một câu hỏi CLM với nhiều candidate bằng head gốc: `softmax(scale · cos(state_head(s), action_head(c_k)))`.
- `src/clm_zeroshot/task2.py`: câu hỏi có/không cho từng nhãn → P(có); ngưỡng từng nhãn = phân vị của P trên gold sao cho tỉ lệ dự đoán trên gold = tần suất thật của nhãn (sàn 1/n_gold); `Lỗi biên dịch` = `has_compile_error(compile_log)`.
- `src/clm_zeroshot/task1.py`: câu hỏi "score" cho từng chiều rubric (trừ `compilable`) → kỳ vọng → làm tròn; `compilable` = 0 nếu có lỗi biên dịch; đề nhiều câu: câu có/không "câu Pk làm đúng không" → trạng thái → rule câu tiên quyết + compile gate của Task 1.
- `scripts/run_task2_zeroshot.py`, `scripts/run_task1_zeroshot.py`; notebook Kaggle có biến `MODE`.

**Tech Stack:** Python 3.12 `.venv`, numpy, torch (chỉ forward head), pytest.

**Spec:** `docs/superpowers/specs/2026-10-09-task2-design.md` (§9, §10). Thiết kế này được người dùng duyệt trong hội thoại 2026-10-11.

## Global Constraints

- **Không train**: không fine-tune head, không fit probe/regression nào. Tham số duy nhất lấy từ gold: văn bản prompt và tần suất nhãn (Task 2). Không dùng gì từ tập test để chọn tham số.
- **Không đọc `feedback`** (cấm làm input cho Task 1/2) — kể cả khi viết guide.
- Head lấy từ checkpoint CLM gốc (`NoulModel.from_checkpoint(heads_path)`), dùng `.state`, `.action`, `.scale()`; không gọi `train_noul`.
- Văn bản state = `context` của `build_state_texts(..., **cfg["text"])` (có compile log tự sinh) + `"\n\n"` + câu hỏi; context được cắt sao cho câu hỏi dài nhất vẫn lọt trong `max_tokens` (dùng lại cơ chế `context_text(..., budget)` của `src/task2/clm/text.py`).
- Candidate có/không theo chuẩn CLM: `"false: No. This is false: <q>"`, `"true: Yes. This is true: <q>"`. Candidate "score": mỗi mức một văn bản mô tả, đúng thứ tự mức.
- Output Task 2/Task 1 đúng định dạng nộp, đủ đúng tập id public, ghi file chỉ sau khi validator tương ứng (`src.task2.evaluator.validate_predictions` / `src.task1.evaluator.validate_predictions`) trả `[]`.
- **Git: subagent KHÔNG được chạy `git commit`, `git push`, `git stash` hay đổi nhánh.** Chỉ sửa file trong working tree trên nhánh `task-2-zeroshot`. Người dùng tự commit.
- Test không gọi model thật/Docker/API. Baseline suite: 156 pass, 5 skip, 2 lỗi có sẵn (`tests/test_colab_task1_secrets.py`).
- Không ghi file id Drive vào repo.

---

### Task A: Guide rút từ 32 bài mẫu (`src/clm_zeroshot/guides.py`)

**Files:** Create `src/clm_zeroshot/__init__.py` (rỗng), `src/clm_zeroshot/guides.py`, `tests/test_clm_zeroshot_guides.py`; append mục "Quy luật rút từ 32 bài mẫu" vào `docs/task2_zeroshot.md` (tạo file).

**Cách làm:** đọc `data/raw/sample_dataset/` — `exams.json`, `task1_grading.json` (rubric), `task2_error_taxonomy.json` (nhãn), code trong `submissions/` — **không mở `task3_feedback.json`, không đọc trường `feedback`**. Với từng nhãn và từng chiều rubric, ghi lại quy luật quan sát được (ví dụ bài nào mang nhãn gì, mức `logic` 2 ứng với kiểu sai nào). Không sao chép code sinh viên vào guide (chỉ mô tả kiểu lỗi).

**Interfaces:**
- `LABEL_QUESTIONS: dict[str, str]` — với mỗi nhãn trong `src.task2.labels.LABELS`: một câu hỏi tiếng Việt dạng "Bài nộp trên có mắc <nhãn> không? <định nghĩa theo cách giảng viên gán, 1–3 câu, nêu dấu hiệu cụ thể>". `Lỗi biên dịch` vẫn có câu hỏi (dùng cho đo), dù quyết định dựa trên compile log.
- `RUBRIC_QUESTIONS: dict[str, str]` — cho `io_format`, `logic`, `edge_case`, `complexity`, `code_quality`: câu hỏi "Chấm chiều <x> cho bài nộp trên theo thang ...".
- `RUBRIC_LEVELS: dict[str, list[str]]` — cùng 5 chiều; danh sách mô tả mức theo thứ tự điểm 0..max (`io_format`, `complexity`, `code_quality`: 2 mức; `edge_case`: 3; `logic`: 5), mỗi mô tả bắt đầu bằng `"<điểm> điểm: "`.
- `PROBLEM_QUESTION: str` — mẫu có `{pid}` và `{prototype}`: "Câu {pid} ({prototype}) trong bài nộp trên có được làm đúng hoàn toàn không?" (diễn đạt tự do nhưng phải chứa 2 placeholder).
- `EVIDENCE: dict[str, str]` — với mỗi nhãn/chiều: 1 dòng tóm tắt bằng chứng từ gold (đếm, kiểu lỗi) để báo cáo.
- Test: đủ khoá cho 10 nhãn và 5 chiều; số mức đúng `DIM_MAX[d] + 1`; mỗi mức bắt đầu `"<i> điểm"`; không chứa chuỗi `"feedback"`; `PROBLEM_QUESTION.format(pid="P1", prototype="x")` chạy được.

- [ ] Viết guide + test + doc (không commit).

### Task B: Lõi chấm CLM + Task 2 zero-shot

**Files:** Create `src/clm_zeroshot/scoring.py`, `src/clm_zeroshot/task2.py`, `scripts/run_task2_zeroshot.py`, `tests/test_clm_zeroshot_task2.py`.

**Interfaces:**
- `scoring.py`:
  - `question_states(exam, sample, tok, questions: list[str], text_cfg: dict) -> list[str]` — context được cắt theo câu hỏi dài nhất (`context_text(exam, sample, tok, max_tokens - q_tokens - SLACK, max_statement_tokens, use_compile_log, max_compile_tokens)` — đọc `src/task2/clm/text.py` để dùng đúng chữ ký hiện tại), trả `[ctx + "\n\n" + q for q in questions]`.
  - `noul_candidates(question) -> tuple[str, str]` (false, true) theo chuẩn CLM.
  - `choice_probs(heads, S: np.ndarray[n,d], C: np.ndarray[k,d]) -> np.ndarray[n,k]` — softmax theo k của `scale · cos(state(l2(S)), action(l2(C)))`, `torch.no_grad()`.
  - `noul_prob(heads, S, C_false_true: np.ndarray[2,d]) -> np.ndarray[n]` = cột "true" của `choice_probs`.
- `task2.py`:
  - `label_probs(samples, exams, encoder, heads, text_cfg) -> np.ndarray[n,10]` (P(có) theo `LABEL_QUESTIONS`).
  - `prevalence_thresholds(P_gold, Y_gold, floor) -> np.ndarray[10]` — với nhãn có tần suất p = mean(Y) (≥ `floor`), ngưỡng = phân vị `1 - p` của P_gold cột đó (`np.quantile(..., method="higher")`).
  - `decide(P, thr, compile_err: np.ndarray[n] bool) -> bool[n,10]` — `P >= thr`, rồi cột `Lỗi biên dịch` = `compile_err`.
  - `run_task2_zeroshot(cfg, encoder, heads_path, gold, public, out_dir, registry=None) -> dict` — metrics `{"name", "mode": "clm_zeroshot", "evaluation": "in-sample over gold (prompts and thresholds derived from gold: optimistic)", "systems": {"clm_zeroshot_prompts": f1_scores(...)}, "thresholds": {...}, "prevalence": {...}}`; ghi `predictions.json` (public), `predictions_full.json`, `metrics.json`, `resources.json`, `config.json`.
- Script `scripts/run_task2_zeroshot.py --config configs/task2/clm_local.yaml [--no-compile]` — nạp gold/public (`load_task2`), `attach_compile_logs`, `build_from_config`, `CachedEncoder`, tên run `task2_zeroshot_` + `cfg["name"].removeprefix("task2_")`, output `outputs/task2/<tên>/`; public lọc bằng `_select_public` theo `cfg["data"]["public_per_exam"]`.
- Test (FakeEncoder, `make_fake_heads`, dataset tổng hợp): `choice_probs` hàng tổng = 1; `prevalence_thresholds` cho tỉ lệ dự đoán trên gold ≈ tần suất; nhãn tần suất 0 dùng sàn; `decide` đặt cột biên dịch theo log; end-to-end ghi `predictions.json` hợp lệ cho id public; không gọi `train_noul` (patch để raise).

- [ ] TDD, test liên quan + suite (không commit).

### Task C: Task 1 zero-shot

**Files:** Create `src/clm_zeroshot/task1.py`, `scripts/run_task1_zeroshot.py`, `tests/test_clm_zeroshot_task1.py`.

**Interfaces:**
- `dimension_scores(samples, exams, encoder, heads, text_cfg) -> dict[str, np.ndarray[n]]` — cho 5 chiều trong `RUBRIC_QUESTIONS`: `choice_probs` trên `RUBRIC_LEVELS[d]` → kỳ vọng `Σ i·p_i`.
- `problem_status(samples, exams, encoder, heads, text_cfg) -> list[dict[pid, str]]` — chỉ đề `multi_problem`: `noul_prob` với `PROBLEM_QUESTION` cho từng `pid` (prototype lấy từ `exams[...]["problems"]`) → `"correct"` nếu P ≥ 0.5 ngược lại `"wrong"`; đề đơn → `{}`.
- `assemble(scores_row, compile_err, statuses, exam) -> (rubric, total)` — làm tròn, kẹp; `compilable = 0 if compile_err else 1`; `apply_rules(rubric, statuses, policy_from_exam(exam), RuleConfig(prerequisite=True, compile_gate=True, clamp=True))`.
- `run_task1_zeroshot(cfg, encoder, heads_path, gold, rubrics, public, public_ids, out_dir, registry=None) -> dict` — metrics `{"name", "mode": "clm_zeroshot", "evaluation": "in-sample over gold (prompts derived from gold: optimistic)", "systems": {"clm_zeroshot_prompts": evaluate(...)}}`; ghi `predictions.json` (validated), `predictions_full.json` (kỳ vọng float, trạng thái câu, trace rule), `metrics.json`, `resources.json`, `config.json`.
- Script `scripts/run_task1_zeroshot.py --config ...` giống Task B; rubric gold bằng `src.task1.clm_probe.load_rubrics`; id public từ `public_test_release/task1_grading.json`; tên run `task1_zeroshot_` + tên config bỏ `task2_`; output `outputs/task1/<tên>/`.
- Test: kỳ vọng nằm trong [0, max]; `assemble` với compile_err → compilable 0 và compile gate; trạng thái P1 sai → rule tiên quyết đưa các chiều phụ thuộc về 0; end-to-end predictions hợp lệ; không fit gì (patch Ridge/train_noul để raise).

- [ ] TDD, test liên quan + suite (không commit).

### Task D: Notebook + docs

- [ ] `kaggle/task2_clm.ipynb` (giữ 7 cell, `DRIVE_ID = ''`, `/kaggle/tmp`, pin transformers): cell cấu hình thêm `MODE = 'zeroshot'  # 'zeroshot': CLM prompts, no training | 'probe': train on 32 gold`; cell chạy: `MODE == 'zeroshot'` → `run_task2_zeroshot.py` + `run_task1_zeroshot.py`, ngược lại → `run_task2_clm.py` + `run_task1_clm.py` (như hiện tại), luôn `--config configs/task2/clm_kaggle.yaml`; cell cuối copy đúng output của MODE sang `/kaggle/working/task1_predictions.json`, `task2_predictions.json` và in kết quả validator.
- [ ] `docs/task2_zeroshot.md`: cách làm, quy tắc quyết định, lệnh local/Kaggle, kết quả đo trên gold (controller điền), hạn chế (số đo lạc quan; P(có) của CLM chưa hiệu chỉnh; ngưỡng trạng thái câu 0.5 không có căn cứ từ gold).

### Task E (controller): chạy local trên 32 gold + 6 public, điền số liệu vào docs, đưa người dùng danh sách file và gợi ý commit message.
