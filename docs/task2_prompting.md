# Task 2: Hướng prompting (Qwen2.5-Coder-7B-Instruct)

Đáp ứng yêu cầu đề: "Ít nhất một hướng prompting trên LLM: zero-shot, few-shot, chain-of-thought, self-consistency,
RAG trên tập train, hoặc kết hợp." Không fine-tune (không LoRA), model giữ nguyên, chỉ thay đổi prompt.

## Dữ liệu: gold và silver

"Gold quan trọng hơn silver" được thể hiện qua cách chọn ví dụ đưa vào prompt, không qua trọng số loss.

| Vai trò | Gold 32 (`data/raw/sample_dataset`) | Silver 500 (sinh từ luật, `docs/synth_plan.md`) |
|---|---|---|
| Ví dụ few-shot / RAG | **Ưu tiên lấy trước** (bài thật, nhãn thật) | Chỉ dùng để bù khi gold không có ví dụ phù hợp (ví dụ `Lỗi edge case`) |
| Chỉnh prompt | Không dùng | Dùng để thử và sửa prompt |
| Chấm điểm | **Thước đo cuối** (macro-F1) | Không dùng |

## Plan

1. **Zero-shot + CoT**: prompt gồm đề bài, code, `compile_log` (tự compile) và định nghĩa 10 nhãn. Model suy luận
   từng bước rồi xuất JSON nhãn.
2. **Thêm self-consistency**: chạy 5 lần (temperature ≈ 0.7), giữ nhãn được đa số chọn (≥ 3/5).
3. **Thêm RAG few-shot (kết hợp)**: với mỗi bài, tìm vài bài giống nhất (cùng đề, code gần giống). Lấy từ gold
   trước, thiếu thì lấy silver, rồi chèn vào prompt làm ví dụ mẫu.
4. **So sánh** 1 → 2 → 3 trên 32 gold, đặt cạnh `probe_aug` (0.362 @tuned, có compile). Chọn cấu hình nộp bài
   chỉ dựa trên điểm gold.

Phần cứng: Kaggle T4×2 cho lượt chạy đầy đủ (360 bài × 5 lần, dùng vLLM hoặc cache); Mac M3 Pro (MLX 4-bit) để
smoke test và chấm nhanh 32 gold.

### Lưu ý tránh rò rỉ dữ liệu
- Khi chấm một bài gold, **không được lấy chính bài đó làm ví dụ** trong prompt (leave-one-out hoặc k-fold).
- Chỉ lấy ví dụ từ gold và silver, **không lấy từ 360 bài public**, đúng với quy định của giảng viên.

### Rủi ro
- `Lỗi edge case` không có mẫu gold dương nào, nên F1 nhãn này trên gold không đo được.
- CoT có thể xuất JSON sai định dạng: cần parser chịu lỗi, parse không được thì retry.
- Silver lệch phân phối so với bài thật: vì vậy chỉ dùng silver để bù ví dụ và chỉnh prompt, không dùng để chấm điểm.

## Chạy (zero-shot CoT)

Plan code: `docs/superpowers/plans/2026-10-14-task2-cot-zero-shot.md`. Code: `src/task2/prompts_cot.py` (prompt),
`src/task2/pipeline.py` (`prompt.style: cot`, `parse_cot_labels`), `src/llm/local_backend.py` (MLX/HF),
`src/task2/cot_report.py` (debug report), `src/task2/cot_bundle.py` (bundle), `scripts/run_task2_cot.py`,
`scripts/predict_task2_cot.py`. Config: `configs/task2/cot_zero_shot.yaml`, `configs/task2/run_cot.yaml`.

```bash
.venv/bin/python scripts/run_task2_cot.py --preflight                        # in prompt bài đầu, không tải model
.venv/bin/python scripts/run_task2_cot.py --ids EX01-S101 EX01-S103          # vài bài gold (Mac, MLX 4-bit)
.venv/bin/python scripts/run_task2_cot.py                                    # 32 gold
.venv/bin/python scripts/run_task2_cot.py --backend hf --predict \
    --export-bundle outputs/task2/task2_cot_bundle                           # Kaggle: 32 gold + 360 public + bundle
.venv/bin/python scripts/run_task2_cot.py --silver                           # chỉnh prompt trên 462 bài silver
.venv/bin/python scripts/run_task2_cot.py --silver-heldout                   # 65 bài silver của 4 đề giữ riêng
```

**Tập silver** (`data/synth/v1/generate-dataset.zip`, sinh theo `docs/synth_plan.md`): 462 bài có nhãn Task 2
(28 đề `SYN-*`) và `heldout/` 65 bài (4 đề không dùng khi sinh, chỉ để đánh giá). `--silver` / `--silver-heldout`
dùng thư mục đã giải nén nếu có, nếu không thì giải nén zip, nếu chưa có zip thì tải từ Google Drive theo
`SILVER_DRIVE_ID` (biến môi trường, `.env` hoặc Kaggle secret; id không commit vì repo công khai). Tải/giải nén
riêng: `python scripts/fetch_synth_data.py [--drive-id ID]`. Kết quả có hậu tố `_silver` / `_silver_heldout`, và
script self-consistency so sánh với zero-shot trên cùng tập. Silver chưa có `compile_log`: bài được tự compile như
mẫu chèn lỗi.

- **Kaggle:** `kaggle/task2_cot.ipynb` (T4 x2, fp16). Output trong `/kaggle/working`: `task2_predictions.json`,
  `cot_gold/` và `cot_public/` (log + report), `task2_cot_bundle/`.
- **Log và debug:** mỗi thư mục kết quả có `run.log` (toàn bộ stdout/stderr, mỗi bài một dòng: token vào/ra, giây,
  tok/s, cảnh báo chạm `max_new_tokens`), `raw_outputs.jsonl` (lời chấm thô), `usage.jsonl` (token/giây/seed từng
  lần sinh), `debug.jsonl` (mỗi bài một dòng: gold, dự đoán, TP/FP/FN, lời chấm, code, compile_log) và
  `report.html` (mở bằng trình duyệt, không cần mạng): ô tổng quan, bảng theo nhãn (gold vs dự đoán, P/R/F1),
  phân bố số nhãn mỗi bài, bảng từng bài có lọc (Sai / Có FP / Có FN / Parse lỗi / Chạm max token / Retry) và bấm
  để xem lời chấm, code đánh số dòng, compile_log. Report được ghi cả khi lần chạy bị dừng giữa chừng.
- **"Xuất model" (bundle):** không có trọng số được train, nên bundle = model id + revision cố định + prompt
  (`prompt_system.txt`, `prompt_instruction.txt`, `prompt_sha256`) + generation + công thức compile + điểm gold.
  `--save-weights` (chỉ backend hf) chép thêm trọng số vào `model/` để chạy offline. Chạy lại:
  `python scripts/predict_task2_cot.py --bundle <dir> --data-root <dataset>`.
- Dự đoán 360 bài public: `--predict` (hoặc `run.predict: true`). Zero-shot không chọn gì trên gold nên số trên
  32 gold không bị lạc quan như số `@tuned` của CLM.

## Chạy (CoT + self-consistency)

Script riêng `scripts/run_task2_cot_sc.py`, config `configs/task2/cot_self_consistency.yaml` (kế thừa
`cot_zero_shot.yaml`: cùng prompt, compile_log). Mỗi bài sinh `n: 5` lời chấm (temperature 0.7, top_p 0.95), giữ
nhãn có ≥ 50% số lời chấm parse được nêu tên. Tỉ lệ phiếu từng nhãn nằm trong `predictions_full.json` (`probs`).
Hai script dùng chung CLI `src/task2/cot_cli.py` nên có cùng các option.

```bash
.venv/bin/python scripts/run_task2_cot_sc.py --ids EX01-S101 EX01-S103       # vài bài (Mac: 5 lần sinh tuần tự)
.venv/bin/python scripts/run_task2_cot_sc.py --backend hf --predict          # Kaggle: 32 gold + 360 public
.venv/bin/python scripts/run_task2_cot_sc.py --backend hf --skip-gold --public-shard 1/2   # chia public qua nhiều phiên
```

- **Tốc độ:** backend HF sinh 5 lời chấm trong một lần `generate` (`num_return_sequences`, prompt chỉ prefill một
  lần), nên chậm hơn zero-shot khoảng 1.3–2 lần thay vì 5 lần. MLX vẫn sinh tuần tự (chỉ dùng để kiểm tra).
- **So sánh:** sau lượt gold, script tìm thư mục kết quả zero-shot cùng model/backend trong cùng `--output-dir`,
  in bảng macro/micro/exact và F1 từng nhãn, ghi `compare.json` (cảnh báo nếu hai lần chạy khác tập bài).
- **Report:** ô "phiếu mỗi bài" và "bài có phiếu chia rẽ", bộ lọc "Phiếu chia rẽ"; trong chi tiết từng bài có bảng
  số phiếu từng nhãn (k/n, có đánh dấu nhãn gold) và nhãn mà từng lời chấm chọn.
- **Kaggle:** `kaggle/task2_cot_sc.ipynb`. `BASELINE = True` chạy zero-shot trên gold trước để có bảng so sánh.
  Nếu 360 bài vượt 12 giờ: `PUBLIC_SHARD = '1/2'`, rồi phiên sau thêm output phiên trước làm Input,
  `RESUME_FROM = [...]`, `PUBLIC_SHARD = '2/2'`; phiên cuối `PUBLIC_SHARD = ''` (mọi bài lấy từ cache) để có
  `task2_predictions.json` đủ 360 bài.
- Ngưỡng 50% là cố định (đa số), không chọn trên gold.

## Tái lập bằng một lệnh (bundle)

```bash
python scripts/predict_task2_cot.py
```

Dùng bundle ghi trong `bundles/task2_cot/BEST`, dự đoán 360 bài public, tự chọn backend (MLX trên Mac / HF trên
GPU) và ghi `outputs/task2/predict_cot/<bundle>/predictions.json` + `report.html` + `run.log`. Bundle (không có
trọng số được train) gồm model id + revision cố định, prompt (`prompt_sha256`), generation, quy tắc compile, git
commit, hash demo pool gold/silver và `demos.json` (demo từng bài). Script cảnh báo khi prompt, demo pool hoặc
compiler khác lúc export. Cách cập nhật bundle tốt nhất sau lượt Kaggle: `bundles/task2_cot/README.md`.
Đã kiểm tra: chạy lại EX02-S209 từ bundle `cot_fewshot` cho đúng 3 demo như `demos.json` và lời chấm giống hệt.

## Sửa sau lần chạy Kaggle đầu tiên (2026-10-15)

Lần chạy zero-shot CoT đầu trên 32 gold (T4 x2): macro-F1 0.053, micro-F1 0.132; chỉ `Lỗi biên dịch` có F1 (0.53).
Bốn lỗi chính và cách sửa (mục 1-2 sửa định dạng / quy tắc tất định; mục 3-4 phải chỉnh trên silver, gold chỉ để đo):

1. **Tên nhãn sai định dạng** — model ghi tên mục chấm ("Vòng lặp", "Hàm") nên parser bỏ cả nhãn đúng. Sửa:
   `coerce_labels` (`src/task2/labels.py`) map tên ngắn / tên mục ghép về nhãn chuẩn; prompt nhắc lại nguyên văn 10
   nhãn ngay trước dòng KẾT LUẬN.
2. **Bịa lỗi biên dịch** (7/13 dự đoán sai: log rỗng, chỉ warning, hoặc thiếu `main`). Sửa: `prompt.compile_rule:
   true` — `Lỗi biên dịch` := `has_compile_error(compile_log)` (quy tắc "+cr" của Hướng 2), áp sau bỏ phiếu, kể cả
   khi lời chấm không parse được; phiếu gốc của model giữ trong `model_compile_vote`. Cần compiler (Docker / g++):
   không có thì script in CẢNH BÁO và quy tắc không áp dụng.
3. **Không biết quy ước gán nhãn của giảng viên** (gold ghi 1-2 lỗi chính; model liệt kê mọi thứ). Sửa: RAG few-shot
   `configs/task2/cot_fewshot.yaml`, `scripts/run_task2_cot_fewshot.py`, `src/task2/cot_demos.py`: 3 bài giống
   nhất theo TF-IDF trên code; gold có độ giống ≥ 0.3 trước, silver bù; không bao giờ lấy bài public hay chính bài
   đang chấm; demo = code (≤ 1800 ký tự) + tình trạng compile + dòng KẾT LUẬN (không dùng `feedback`). Prompt dài
   hơn `max_prompt_chars` (24000) thì bỏ bớt demo ít giống nhất (tránh OOM trên T4).
4. **Nhãn ngẫu nhiên** — self-consistency kết hợp few-shot: `configs/task2/cot_fewshot_sc.yaml`
   (`run_task2_cot_sc.py --experiment cot_fewshot_sc`).

Report có thêm: demo đã dùng (nguồn:sample_id:độ giống) và nguồn của `Lỗi biên dịch` (quy tắc, kèm phiếu model).
Kiểm tra local (MLX, 3 bài gold từng sai): quy tắc compile bỏ đúng `Lỗi biên dịch` bịa ở cả 3 bài; few-shot + SC
giảm EX02-S209 từ 7 nhãn (greedy) còn 4. Số trên 3 bài không dùng để chọn cấu hình.

## Prompt theo quy luật giảng viên (2026-10-17)

Zero-shot CoT trên public chỉ được khoảng 0.20 macro-F1. Bộ nhãn tham khảo (chỉ dùng chạy thử, không nộp final)
được gán bằng các quy luật trong `docs/task2_teacher_rules.md` kèm bằng chứng chạy thật, và đạt 0.3514 macro /
0.4930 micro trên leaderboard. Kết quả này cho thấy các quy luật rút từ 32 bài gold đúng với cách thầy gán nhãn.
Vì vậy prompt CoT hiện tại được sửa tại chỗ, không tạo bản v2. Mọi quy luật chỉ lấy từ gold; không lấy gì từ nhãn
public.

- **Mô tả nhãn riêng cho CoT** (`TEACHER_GUIDE` trong `src/task2/prompts_cot.py`) mô tả cách thầy dùng từng nhãn.
  - `Lỗi hàm` là gọi/dùng hàm sai (`stoi`/`stof`, gọi hàm thiếu đối số, hàm phụ trả sai), không phải "thiếu hàm".
  - `Lỗi nhập/xuất` là sai hoa thường hoặc dấu cách; câu nhắc nhập không bị tính.
  - `Lỗi edge case` rất hiếm.
  - `Lỗi style` dùng khi toàn bộ bài nằm trong comment.
  - `DESCRIPTIONS` trong `labels.py` (dùng chung cho Hướng 2 và augment) giữ nguyên.
- **Nguyên tắc mới:**
  - chỉ ghi 1-2 lỗi chính (tối đa 3);
  - câu chưa làm thì không có nhãn;
  - câu tiên quyết sai thì chỉ ghi lỗi của câu đó;
  - lỗi biên dịch được kèm tối đa 1 nhãn nguyên nhân;
  - vòng lặp vô hạn ghi cả `Lỗi vòng lặp` và `Lỗi logic`;
  - bài comment toàn bộ là `Lỗi style`.
- **Thêm trường từ `exams.json` vào mục YÊU CẦU CỦA ĐỀ:**
  - `language` → chuẩn C++;
  - `learning_outcome` + `topic` → "Trọng tâm đề", kèm câu dặn: nhãn vẫn gán theo dòng code gây sai, không theo
    chủ đề;
  - `has_hidden_testcases: true` → output phải khớp chính xác, chỉ đúng ví dụ mẫu vẫn bị trừ điểm.

  Không đưa vào: `programming_skill` (trùng `topic`), `bloom_level` và `difficulty_teacher` (không cho biết bài sai
  ở đâu), `problem_type` (trùng thông tin suy ra từ `note`). Silver không có các trường này, nên trên silver các
  dòng tương ứng tự bỏ trống; tác động của chúng chỉ đo được trên gold.
- **9 bước thay cho 8:** thêm bước "2. Phạm vi chấm" (liệt kê câu đã làm / chưa làm, kiểm tra câu tiên quyết trước).
  Bước Hàm hỏi "dùng hàm sai" thay vì "có trong bài không".

**Tùy chọn `prompt.lang: vi | en`** (mặc định `vi`). Đây là cùng một phiên bản prompt với cùng quy tắc, chỉ khác
ngôn ngữ, dùng để A/B.

- **Bản tiếng Anh:** persona, quy tắc, 9 bước, các dòng yêu cầu đề, tiêu đề mục và demo few-shot được viết bằng
  tiếng Anh. Model chấm bằng tiếng Anh và kết thúc bằng dòng `CONCLUSION:`.
- **Giữ nguyên:** đề bài, giá trị trong `exams.json` và code sinh viên. Tên nhãn luôn là tiếng Việt nguyên văn (có
  chú thích tiếng Anh trong system prompt).
- **Parser:** đọc được cả `KẾT LUẬN:` và `CONCLUSION:`. `coerce_labels` map được "Loop error", "Function misuse"…
  về nhãn chuẩn.
- **Config:** `cot_zero_shot_en.yaml` và `cot_fewshot_sc_en.yaml`. Bundle ghi `prompt_sha256` theo ngôn ngữ.
- **Token đo trên 360 bài public:**

  | Bản | Trung vị | Lớn nhất |
  |---|---|---|
  | vi | 3143 | 7069 |
  | en | 2841 | 6765 |

  Chỉ giảm khoảng 10%, vì tên nhãn vẫn tiếng Việt và phần lớn prompt là đề và code.
- **Chạy thử 4 bài gold (MLX, không dùng để kết luận):**
  - bản en đúng `Lỗi logic` ở S206 và nhận ra bài in sai hoa thường ở bước 3, nhưng không gán `Lỗi nhập/xuất`;
  - cả hai bản đều lặp câu đến `max_new_tokens` ở S105;
  - cả hai bản đều không thấy lỗi của S215.

  Phải chọn ngôn ngữ dựa trên gold và silver chạy trên Kaggle.

Chạy lại zero-shot với lệnh cũ (`scripts/run_task2_cot.py`, notebook `kaggle/task2_cot.ipynb`). Prompt đầy đủ của
một bài được xuất vào `outputs/task2/prompt_preview/` (gitignored vì có code sinh viên). Các bundle trong
`bundles/task2_cot/` đã cũ (khác `prompt_sha256`), cần export lại sau khi chạy.

Chạy thử local (MLX, 4 bài gold S105/S114/S206/S215; chỉ để kiểm tra định dạng, không dùng để chọn cấu hình):
model viết đủ 9 bước và liệt kê đúng câu đã làm / chưa làm. Tuy vậy nó vẫn không tự thấy lỗi ngữ nghĩa:
- S215: không thấy hàm mũ sai;
- S206: không thấy in TRUE thay vì True;
- S114: không thấy `stoi` lỗi.

Có 1 bài bị lặp chuỗi số dòng đến `max_new_tokens`. Kết luận: chỉ sửa prompt là chưa đủ, cần thêm bằng chứng chạy
thật (xem đề xuất trong phần trả lời 2026-10-17).

## Backend vLLM và retry sau OOM (2026-10-18)

Lần chạy public trên Kaggle (HF backend, 2x T4) phải retry 258/328 bài vì CUDA OOM. Hai thay đổi:

- **Retry sau OOM:** trước đây câu `[OOM] ...` bị coi là câu trả lời của model, rồi model được yêu cầu "sửa lại
  JSON". Kết quả là nhãn từ một JSON trơn, không có suy luận. Giờ bài OOM được gửi lại bằng prompt gốc
  (`src/task2/pipeline.py`).
- **`--backend vllm`** (`VLLMChatBackend` trong `src/llm/local_backend.py`, mục `vllm:` trong `run_cot.yaml`):
  - continuous batching + paged KV cache được giữ trước (`gpu_memory_utilization`), nên prompt dài phải chờ
    chỗ trống chứ không OOM; `tensor_parallel_size` = số GPU;
  - mỗi lần gọi model gửi `checkpoint_every: 64` bài (thay cho 2–4 của config) và cache được ghi sau mỗi lô;
  - n câu SC của một bài dùng chung phần prefill; seed của từng bài giống các backend khác;
  - prompt dài hơn `max_model_len` nhận placeholder `[OOM]` để không làm hỏng cả lô.
  - attention dùng `TRITON_ATTN`: trên T4 vLLM tự chọn FlashInfer, mà FlashInfer phải tự build kernel và bị lỗi
    link trên Kaggle (`ld: cannot find -lcuda`); sampler FlashInfer cũng tắt vì cùng lý do.

  Hai notebook mặc định dùng `BACKEND = 'vllm'` và cài bản vLLM mới nhất cho Python của Kaggle (3.13: vLLM 0.9.x
  không cài được). Cell cài đặt thử `import vllm`; nếu lỗi thì in lỗi pip và chuyển `BACKEND = 'hf'`. Thư mục kết quả có `__vllm__` nên không dùng chung cache với
  `__hf__`. Kết quả greedy có thể lệch nhẹ so với HF, nên cần chấm lại 32 gold trước khi nộp.

## Ví dụ prompt (vai giáo viên chấm bài)

Bài code dưới đây là ví dụ tự viết để minh họa, không lấy từ tập public. Định nghĩa nhãn lấy từ `src/task2/labels.py`.

### 1. System prompt

```text
Bạn là giảng viên môn Lập trình C++ nhập môn, đang chấm bài nộp của sinh viên.
Nhiệm vụ: xác định TẤT CẢ các loại lỗi có trong bài, theo đúng danh sách nhãn bên dưới.
Một bài có thể có 0, 1 hoặc nhiều lỗi. Bài đúng hoàn toàn thì trả về danh sách rỗng.

Danh sách nhãn (chỉ dùng đúng tên này):
- Lỗi biên dịch: code không biên dịch được (sai cú pháp, biến/hàm chưa khai báo, sai kiểu nghiêm trọng).
- Lỗi nhập/xuất: đọc/ghi sai (in thừa/thiếu chuỗi, sai định dạng, sai hoa thường).
- Lỗi logic: điều kiện, công thức hoặc luồng xử lý sai làm kết quả sai.
- Lỗi vòng lặp: điều kiện dừng sai, off-by-one, vòng lặp vô hạn.
- Lỗi mảng/chuỗi: truy cập ngoài chỉ số, sai kích thước, sai ký tự kết thúc.
- Lỗi hàm: sai prototype/kiểu trả về, thiếu return, truyền tham trị thay vì tham chiếu.
- Lỗi edge case: không xử lý n = 0/1, số âm, mảng/chuỗi rỗng, phần tử đầu/cuối.
- Lỗi thuật toán: chọn thuật toán/cấu trúc dữ liệu sai hoặc không đúng yêu cầu đề.
- Lỗi hard-code: gán cứng giá trị/kết quả theo ví dụ thay vì tính tổng quát.
- Lỗi style: đặt tên khó hiểu, thụt lề lộn xộn, code lặp, lạm dụng biến toàn cục.

Nguyên tắc chấm:
- Chỉ gán nhãn khi chỉ ra được dòng code cụ thể gây lỗi. Không đoán.
- Nếu compile_log có "error" thì chắc chắn có "Lỗi biên dịch". Cảnh báo (warning) thì không tính.
- Bám sát yêu cầu đề: làm khác yêu cầu (ví dụ đề bắt dùng đệ quy mà dùng vòng lặp) là "Lỗi thuật toán".
```

### 2. User prompt (zero-shot + CoT)

````text
## Đề bài (EX99, single_problem)
Viết hàm `int sumArray(int a[], int n)` trả về tổng n phần tử của mảng a.
Hàm main đọc n, rồi n số nguyên, in ra "Tong = <kết quả>".

## Bài nộp của sinh viên
```cpp
#include <iostream>
using namespace std;
int sumArray(int a[], int n) {
    int s = 0;
    for (int i = 0; i <= n; i++) s += a[i];
    return s;
}
int main() {
int n; cin >> n;
int a[100];
for (int i = 0; i < n; i++) cin >> a[i];
if (n == 3) { cout << "Tong = 6"; return 0; }
cout << "Tong: " << sumArray(a, n);
}
```

## compile_log
(rỗng: không có lỗi hay cảnh báo)

## Cách chấm
Hãy chấm theo từng bước, mỗi bước ghi ngắn gọn bằng chứng (số dòng / đoạn code):
1. Biên dịch: compile_log có lỗi không?
2. Nhập/xuất: định dạng in ra có khớp đề không?
3. Vòng lặp và mảng: chỉ số, điều kiện dừng có đúng không?
4. Hàm: prototype, return, cách truyền tham số có đúng không?
5. Logic, edge case, hard-code: có nhánh nào sai, bỏ sót trường hợp biên, hoặc gán cứng không?
6. Thuật toán: cách làm có đúng yêu cầu đề không?
7. Style: trình bày có chấp nhận được không?

Cuối cùng xuất đúng một dòng JSON:
{"taxonomy_error": [...]}
````

### 3. Output mong muốn

```text
1. Biên dịch: compile_log rỗng, không có lỗi.
2. Nhập/xuất: đề yêu cầu "Tong = ", bài in "Tong: " → sai định dạng. Lỗi nhập/xuất.
3. Vòng lặp/mảng: `i <= n` lặp thừa 1 lần và đọc a[n] ngoài phạm vi dữ liệu → Lỗi vòng lặp, Lỗi mảng/chuỗi.
4. Hàm: prototype và return đúng.
5. Hard-code: `if (n == 3) cout << "Tong = 6"` trả kết quả cứng theo ví dụ → Lỗi hard-code.
   Edge case: n = 0 thì vòng lặp vẫn đọc a[0]; lỗi này đã nằm trong lỗi vòng lặp, không gán thêm.
6. Thuật toán: cộng dồn tuyến tính là đúng yêu cầu.
7. Style: main không thụt lề → Lỗi style.

{"taxonomy_error": ["Lỗi nhập/xuất", "Lỗi vòng lặp", "Lỗi mảng/chuỗi", "Lỗi hard-code", "Lỗi style"]}
```

Chương trình chỉ đọc dòng JSON cuối. Phần suy luận phía trên là chain-of-thought.

### 4. Nâng cấp từ bản zero-shot
- **Self-consistency**: gửi cùng prompt 5 lần với temperature ≈ 0.7, nhãn xuất hiện ≥ 3/5 lần thì giữ.
- **RAG few-shot**: chèn 2–3 bài đã chấm sẵn vào giữa system prompt và bài cần chấm, theo dạng
  `[Đề] [Code] [Lời chấm từng bước] [JSON]`. Bài mẫu lấy theo độ giống: gold trước, thiếu thì lấy silver. Lời chấm
  từng bước của bài silver sinh từ luật cài lỗi; bài gold chỉ có nhãn nên tự viết lời chấm ngắn hoặc chỉ ghi JSON.

### Hai điểm thiết kế chính
- "Chỉ gán nhãn khi chỉ ra được dòng code" giúp model bớt gán nhãn tràn lan, vấn đề `probe_aug` đang gặp
  (4–8 nhãn mỗi bài).
- Quy tắc cho `compile_log` giúp nhãn `Lỗi biên dịch` gần như chắc chắn đúng.
