# CLM zero-shot (Task 1 + Task 2)

Plan: `docs/superpowers/plans/2026-10-11-clm-zeroshot.md`. Prompt texts: `src/clm_zeroshot/guides.py`
(`LABEL_QUESTIONS`, `RUBRIC_QUESTIONS`, `RUBRIC_LEVELS`, `PROBLEM_QUESTION`, `EVIDENCE`).

## Quy luật rút từ 32 bài mẫu

Nguồn: `data/raw/sample_dataset/` — `exams.json`, `task1_grading.json`, `task2_error_taxonomy.json`, code trong
`submissions/`, `compile_log`, `test_report`. **Không đọc** `task3_feedback.json` / trường `feedback`; không đọc tập
test. 32 bài: 15 bài EX01 (multi_problem, đọc file CSV + danh sách liên kết, 4 hàm) và 17 bài EX02 (single_problem,
số Armstrong, stdin/stdout, cấm `pow`). Không chép code sinh viên vào đây — chỉ mô tả kiểu lỗi.

### Task 2 — nhãn (đếm trên 32 bài; 4 bài không nhãn)

| Nhãn | Số bài | Kiểu lỗi giảng viên gán |
|---|---|---|
| Lỗi logic | 12 | phổ biến nhất; công thức/luồng sai, xoá nút không nối lại, tách trường sai, thiếu bước tính; đi kèm logic ≤ 2 |
| Lỗi biên dịch | 6 | trùng khớp tập `compilable = 0`; error thật (thiếu `;`, biến chưa khai báo, khai báo trùng, `return;` trong hàm trả con trỏ, `#include` file CSV). Chỉ warning hoặc lỗi link thiếu `main` → không gán |
| Lỗi vòng lặp | 6 | duyệt danh sách không tiến con trỏ (lặp vô hạn), dừng ở `next != null` bỏ nút cuối, bắt đầu chỉ số 1, vòng luỹ thừa sai số lần |
| Lỗi hàm | 5 | chỉ viết hàm đầu, bỏ các hàm yêu cầu; dùng tên hàm thay vì gọi; thiếu return; hàm phụ nhân sai biến; đệ quy ghi đè biến toàn cục |
| Lỗi thuật toán | 4 | công thức tuổi năm TCN sai, tìm max sai, hàm luỹ thừa tự viết sai, giải phóng mảng đầu vào; có thể đi cùng logic 3–4 |
| Lỗi hard-code | 3 | chỉ EX01: tên file cố định / chuỗi `"filename"`, mảng kích thước cố định theo dữ liệu mẫu, đọc `cin` thay vì file |
| Lỗi nhập/xuất | 2 | in `TRUE`/`FALSE`, khoảng trắng trước `True`; in dòng nhắc nhập **không** bị gán |
| Lỗi style | 2 | toàn bộ code bị comment; biến/đoạn code thừa — vẫn `code_quality = 1` |
| Lỗi mảng/chuỗi | 1 | mảng VLA cục bộ trả về con trỏ, ghi qua con trỏ `string*` chưa cấp phát |
| Lỗi edge case | 0 | chưa từng được gán trong bài mẫu |

Hệ quả: tần suất nhãn rất lệch (edge case 0, mảng/chuỗi 1) → câu hỏi cho các nhãn hiếm được viết hẹp, nêu rõ
"nhãn hiếm"; `Lỗi biên dịch` nên quyết định bằng compile log (error thật), câu hỏi chỉ dùng để đo.

### Task 1 — rubric

| Chiều | Phân bố | Quy luật |
|---|---|---|
| compilable | 0:6, 1:26 | 0 ⇔ error biên dịch thật; warning và lỗi link thiếu `main` vẫn 1 |
| io_format | 0:11, 1:21 | 0 = 6 bài lỗi biên dịch + 2 bài in sai chuỗi + 3 bài không tạo ra kết quả; in dòng nhắc nhập vẫn 1 |
| logic | 0:13, 1:1, 2:9, 3:2, 4:7 | EX02 gần như chỉ 0/2/4 (2 = pass một phần test hoặc sai một bước tính); EX01: 0 khi lỗi biên dịch / chỉ làm dở prob1 / lặp vô hạn, 1 khi đọc sai nguồn dữ liệu, 2–3 khi làm được nhiều câu |
| edge_case | 0:13, 1:9, 2:10 | gần như hàm của logic: logic 0 → 0; logic 1 → 1 (một bài EX01); logic 2 → 1 (EX02) hoặc 2 (EX01); logic 3–4 → 2 (một ngoại lệ 1) |
| complexity | 0:12, 1:20 | 0 gần trùng logic 0 (lỗi biên dịch, lặp vô hạn, chưa có thuật toán) |
| code_quality | 0:8, 1:24 | 0 chỉ ở EX01 (lỗi biên dịch, chỉ làm dở, hàm chính hỏng); EX02 luôn 1 |

Lưu ý: kết quả `test_report` của EX02 không quyết định tuyệt đối — một bài in dòng nhắc nhập fail 0/8 test vẫn
được 10 điểm, một bài toàn code bị comment cũng được 10 điểm.

## Cách làm

CLM-8B (Qwen3-8B đóng băng) **không huấn luyện**; mọi quyết định đến từ câu trả lời của mô hình cho prompt tiếng Việt (`src/clm_zeroshot/guides.py`).

- **Task 2**: với mỗi nhãn hỏi một câu có/không, lấy P(có). Ngưỡng theo nhãn lấy từ tần suất (prevalence) trong 32 bài gold, sàn `1/n_gold`; nhãn được gán khi P(có) vượt ngưỡng. `Lỗi biên dịch` không dựa vào CLM mà lấy từ compile log (có error thật).
- **Task 1**: mỗi chiều rubric là một câu hỏi chấm điểm; điểm = kỳ vọng (expected value) trên phân bố xác suất các mức. `compilable` lấy từ compile log. Với đề nhiều câu, hỏi trạng thái từng câu; áp quy tắc tiên quyết (câu sau cần câu trước) và cổng compile (không biên dịch được thì các câu không đạt).

## Lệnh chạy

```bash
# local
.venv/bin/python scripts/run_task2_zeroshot.py --config configs/task2/clm_local_full.yaml
.venv/bin/python scripts/run_task1_zeroshot.py --config configs/task2/clm_local_full.yaml
```

Kaggle: mở `kaggle/task2_clm.ipynb`, đặt `MODE = 'zeroshot'` (mặc định; `'probe'` quay lại huấn luyện trên 32 gold), Run All.

## Kết quả

Chạy thử local 2026-10-11 (Mac M3 Pro, MLX 4-bit, `configs/task2/clm_local.yaml`: 32 bài gold + 1 bài public mỗi đề) — chỉ để kiểm tra pipeline; bản nộp chạy trên Kaggle.

- **Task 2** (có tự compile): macro-F1 **0.195**, micro-F1 0.313 trên 32 gold (in-sample, lạc quan vì prompt và ngưỡng rút từ chính 32 bài; để so sánh, `probe_aug` đạt 0.362 qua 4-fold CV). F1 từng nhãn: biên dịch 1.0 (từ compile log), logic 0.33, thuật toán 0.25, hàm 0.20, vòng lặp 0.17, còn lại 0. Thời gian 28 phút, bộ nhớ đỉnh 5.26 GB.
- **Task 1**: lần chạy thử bị mất compile giữa chừng (Docker Desktop tắt → `compilable` luôn 1, không có compile log trong văn bản) nên số đo QWK 0.125 / MAE 3.44 **không đại diện**; cần chạy lại khi có compiler (Kaggle dùng g++ native nên không gặp lỗi này).

## Hạn chế

- Số đo trên gold lạc quan: prompt và ngưỡng được rút từ chính 32 bài gold.
- P(có) của CLM chưa hiệu chỉnh, nên ngưỡng theo prevalence chỉ là xấp xỉ.
- Ngưỡng 0.5 cho trạng thái từng câu không có căn cứ từ gold.
- Prompt tiếng Việt trong khi mô hình/head tiếng Anh là chủ yếu.
- Ví dụ trong prompt chỉ lấy từ 2 đề mẫu (EX01, EX02).
