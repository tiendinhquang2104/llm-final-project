# Sample dataset — Challenge chấm điểm & phản hồi bài lập trình

Bộ mẫu **32 bài nộp** đã ẩn danh, dùng để sinh viên hiểu định dạng input/output của 3 task.
Đây **không phải** tập train/test chính thức; tập đầy đủ sẽ được phát sau.

## Các file

| File | Nội dung |
|---|---|
| `exams.json` | 2 đề bài (statement + metadata + trọng số từng câu). Mọi sample tham chiếu qua `exam_id`. |
| `label_space.json` | Rubric 6 chiều, 10 nhãn taxonomy lỗi, 4 mức phản hồi kèm định nghĩa và điều cấm. |
| `task1_grading.json` | 32 mẫu cho Task 1. |
| `task2_error_taxonomy.json` | 32 mẫu cho Task 2. |
| `task3_feedback.json` | 32 mẫu cho Task 3. |
| `submissions/<exam_id>/<sample_id>.cpp` | Code sinh viên, mỗi bài một file. JSON chỉ tham chiếu qua `code_file`. |

Ba file task dùng **chung một tập sample_id**, chỉ khác trường `output` — cùng một bài nộp có thể
được dùng cho cả ba task.

Code **không** nằm trong JSON. Trường `code_file` là đường dẫn tương đối tính từ thư mục gốc của
bộ dữ liệu, đặt tên theo `<mã đề>-<mã sinh viên ẩn danh>.cpp`:

```
sample_dataset/
├── exams.json
├── label_space.json
├── task1_grading.json
├── task2_error_taxonomy.json
├── task3_feedback.json
└── submissions/
    ├── EX01/  EX01-S101.cpp ... EX01-S115.cpp   (15 bài)
    └── EX02/  EX02-S201.cpp ... EX02-S217.cpp   (17 bài)
```

```python
import json, pathlib
root = pathlib.Path("sample_dataset")
data = json.load(open(root/"task1_grading.json", encoding="utf-8"))
for s in data["samples"]:
    code = (root/s["input"]["code_file"]).read_text(encoding="utf-8")
```

## Hai loại đề

| | `EX01` | `EX02` |
|---|---|---|
| `exam_type` | `multi_problem` | `single_problem` |
| Cấu trúc | 4 câu trong 1 file, trọng số 1/4/2/3 | 1 câu, stdin/stdout |
| Ràng buộc riêng | P1 sai → P2–P4 **không** được chấm | có testcase công khai |
| `compile_log` | `g++ -std=c++11 -fsyntax-only` (bài nộp không có `main`) | `g++ -std=c++11` đầy đủ |
| `test_report` | `null` | 8 test công khai, mỗi test có `input/expected/actual/passed` |

Rubric 6 chiều **giống nhau** cho cả hai loại — đó là điểm chung để mô hình xử lý được cả hai.

## Task 1 — Chấm điểm theo rubric

```
input : exam_id, exam_type, language, code_file, compile_log?, test_report?
output: rubric{compilable 0-1, io_format 0-1, logic 0-4, edge_case 0-2,
               complexity 0-1, code_quality 0-1}, total_score 0-10
metric: QWK trên total_score, MAE, exact-match từng chiều
```

Ví dụ (rút gọn):

```json
{
  "sample_id": "EX02-S204",
  "input": { "exam_id": "EX02", "code_file": "submissions/EX02/EX02-S204.cpp",
             "compile_log": "", "test_report": [...] },
  "output": { "rubric": {"compilable":1,"io_format":1,"logic":4,"edge_case":2,"complexity":1,"code_quality":1},
              "total_score": 10 }
}
```

## Task 2 — Phân loại lỗi (đa nhãn)

```
input : giống Task 1
output: taxonomy_error — list các nhãn trong 10 nhãn của label_space.json
metric: micro-F1, macro-F1
```

`[]` là output hợp lệ và có ý nghĩa: bài không mắc lỗi nào. Một bài có thể có nhiều nhãn.

## Task 3 — Sinh phản hồi có kiểm soát mức độ

```
input : exam_id, exam_type, language, code_file, compile_log?, target_feedback_level
output: taxonomy_error, feedback — đoạn văn tiếng Việt
metric: (a) level compliance — Level 1/2 mà đưa code sửa hoặc lời giải là VI PHẠM;
        (b) độ chính xác chẩn đoán so với feedback của giảng viên
```

Nhãn lỗi được cho sẵn ở input để Task 3 độc lập với Task 2 — sai ở Task 2 không kéo theo sai ở Task 3.

## Lưu ý về chất lượng dữ liệu (đọc trước khi dùng)

- **`compile_log` là tín hiệu phụ, không phải nhãn.** Có 4/75 bài `EX02` và 5/46 bài `EX01` mà
  `compiles_locally = false` nhưng giảng viên vẫn chấm `compilable = 1` — do sinh viên viết theo
  MSVC (`void main`, dùng `pow` không `#include <cmath>`). Nhãn của giảng viên là ground truth.
- **Không dùng `feedback` làm input cho Task 1/2** — đó là rò rỉ nhãn.
- `EX01` toàn bộ ở `Level 2`, `EX02` chủ yếu `Level 1`/`Level 3`. Đây là bias của bộ mẫu nhỏ, tập
  đầy đủ sẽ cân bằng hơn.
- Cột "Điểm theo test" của bản gốc **không** được đưa vào bộ mẫu vì chưa nhất quán.

## Ẩn danh

MSSV, họ tên, mã lớp, tên trường và email đã được thay thế (`S1xx`/`S2xx`, `[NAME_REDACTED]`,
`[CLASS_REDACTED]`). Bảng ánh xạ ngược do giảng viên giữ riêng, không phát kèm bộ dữ liệu.
