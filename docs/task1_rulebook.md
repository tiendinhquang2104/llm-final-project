# Task 1 — Rulebook chấm điểm (suy ra từ 32 mẫu có nhãn, đã chỉnh theo quyết định của nhóm)

Nguồn: `data/public-test/sample_dataset.zip` (EX01 = 15 bài multi_problem, EX02 = 17 bài single_problem).
Đã đọc toàn bộ code, nhãn Task 1/2, phản hồi giảng viên (Task 3) và chạy thử EX02 trên 10 test thường + 9 test biên.
**Không dùng bất kỳ dữ liệu/nhãn nào của `public_test_release`.**

> Phản hồi giảng viên chỉ được dùng để *con người* hiểu cách chấm và viết rule. Nó không phải là input
> của mô hình Task 1/2, nên không vi phạm điều cấm "dùng feedback làm input".

Ký hiệu: `C IO L E X Q` = compilable, io_format, logic, edge_case, complexity, code_quality. `T` = tổng.

## Quyết định của nhóm (2026-10-13, ưu tiên cao hơn dữ liệu mẫu)

| # | Quyết định |
|---|---|
| Q1 | Tổng điểm **có** các giá trị 4 và 5 trên thực tế. Bộ mẫu không có chỉ vì nó nhỏ, nên **phải sinh mẫu cho 4 và 5** |
| Q2 | EX02-S214 (comment toàn bộ code) bị gán nhãn sai: đúng ra phải là **0 điểm**. Sửa nhãn thành 0 khi dùng mẫu này |
| Q3 | Đề multi_problem chấm **2.5 điểm mỗi câu × 4 câu = 10** (theo `exams.json`). Đây không phải lỗi dữ liệu |
| Q4 | Phải sinh mẫu cho nhãn `Lỗi edge case` (bộ mẫu chưa có mẫu nào) |
| Q5 | Áp **nghiêm ngặt** quy tắc tiên quyết: P1 sai thì P2–P4 = 0, dù sinh viên có làm các câu đó |

---

## 0. Rule toàn cục

| ID | Rule |
|---|---|
| G1 | `T = C + IO + L + E + X + Q`, mọi chiều nằm trong khoảng hợp lệ |
| G2 | Nhãn đi theo các **"template" cố định** (bảng S và M bên dưới). Template quan sát được giữ nguyên; template cho 4, 5 và edge case được **thiết kế mới** theo Q1 và Q4 |
| G3 | Ở đề một câu, giảng viên chấm theo *loại lỗi*, **không** theo tỉ lệ pass test (xem S4) |
| G4 | `compile_log` chỉ là tín hiệu phụ. Lỗi kiểu MSVC (`void main`, quên `#include <cmath>`) vẫn được `C=1` |
| G5 | Bài rỗng hoặc toàn bộ code bị comment thì **T = 0** (Q2) |

---

## 1. single_problem (stdin/stdout). Học từ EX02

Danh sách quyết định: **xét từ trên xuống, gặp rule đầu tiên khớp thì dừng.**
Cột "Nguồn" cho biết rule quan sát được từ mẫu (mẫu) hay được thiết kế theo Q1/Q4 (mới).

| ID | Điều kiện | C IO L E X Q | T | Taxonomy | Nguồn |
|---|---|---|---|---|---|
| S0 | Bài rỗng hoặc comment toàn bộ | 0 0 0 0 0 0 | **0** | `Lỗi biên dịch`, `Lỗi style` | Q2 (S214 đã sửa) |
| S1 | Không biên dịch được | 0 0 0 0 0 1 | **1** | `Lỗi biên dịch` (+ lỗi gây ra) | S203, S212, S217 |
| S2 | Biên dịch được nhưng **không kết thúc** hoặc lõi bỏ dở | 1 0 0 0 0 1 | **2** | `Lỗi logic`, `Lỗi vòng lặp` | S210 |
| S3 | Sai **token** output (`TRUE`, `true`) **và** logic sai hoàn toàn | 1 0 0 0 1 1 | **3** | `Lỗi nhập/xuất`, `Lỗi logic` | S206 |
| S7 | **Hard-code đáp án**: chỉ đúng các ví dụ trong đề hoặc một vài giá trị, không có thuật toán thật | 1 1 1 0 0 1 | **4** | `Lỗi hard-code` | mới (Q1) |
| S8 | Thuật toán đúng hướng nhưng **chỉ đúng một phần**, sai mọi test biên **và** quá chậm (TLE với input lớn) | 1 1 2 0 0 1 | **5** | `Lỗi thuật toán`, `Lỗi edge case` | mới (Q1, Q4) |
| S9 | Sai token output **và** logic sai một phần | 1 0 2 1 1 1 | **6** | `Lỗi nhập/xuất`, `Lỗi logic` | mới (kết hợp S3 và S4) |
| S4 | Format đúng, kết thúc bình thường, **logic sai** (sai cả test thường) | 1 1 2 1 1 1 | **7** | `Lỗi logic` / `Lỗi thuật toán` / `Lỗi hàm` / `Lỗi vòng lặp` | S204, S207, S208, S209, S213, S215, S216 (7/7) |
| S10 | Pass **mọi test thường**, sai **≥ 2 nhóm** test biên (n nhỏ nhất, n lớn nhất hoặc tràn số, rỗng, …) | 1 1 4 0 1 1 | **8** | `Lỗi edge case` | mới (Q4) |
| S11 | Pass mọi test thường, sai **đúng 1 nhóm** test biên | 1 1 4 1 1 1 | **9** | `Lỗi edge case` | mới (Q4) |
| S12 | Logic đúng 100%, output đúng, nhưng **style rất kém** (tên vô nghĩa, dồn hết vào `main`, code chết) | 1 1 4 2 1 **0** | **9** | `Lỗi style` | mới (để phủ nhãn `Lỗi style`) |
| S5 | Logic đúng 100% nhưng **thừa ký tự trên dòng đáp án** | 1 0 4 2 1 1 | **9** | `Lỗi nhập/xuất` | S205 |
| S6 | Đúng toàn bộ | 1 1 4 2 1 1 | **10** | `[]` | S201, S202, S211 |

Rule con:
- **S-io-prompt:** in lời nhắc nhập trước khi đọc input (`"Input n: "`) **không** bị trừ `io_format` (S211, S216). Chỉ sai **chính token đáp án** mới làm `IO=0`.
- **S-pass:** nhóm S4 không phân biệt theo tỉ lệ pass. Bài pass 0/10 (S209) và bài pass 7/10 (S208) đều được 7 điểm.
- **S-edge-groups:** mỗi đề phải định nghĩa trước các *nhóm test biên*, ví dụ với Armstrong:
  - giá trị nhỏ nhất `n = 1..9`;
  - giá trị lớn nhất `n = 10^9`, bài nào lưu kết quả luỹ thừa bằng `int` sẽ bị tràn số;
  - số có chữ số 0, ví dụ `10` và `100`.

  S10 và S11 đếm số **nhóm** bị sai, không đếm số test.

---

## 2. multi_problem (nhiều câu, chỉ có hàm, có câu tiên quyết). Học từ EX01

**Điểm theo câu (Q3):** mỗi câu P1..P4 tối đa 2.5 điểm.

| Trạng thái câu (do harness xác định) | Điểm câu |
|---|---|
| `ok`: pass mọi test của câu | 2.5 |
| `edge`: pass test thường, sai test biên (danh sách rỗng, xoá node đầu, BC cả hai mốc, tuổi bằng nhau) | 2.0 |
| `partial`: sai một phần test thường (sai công thức, sai điều kiện) | 1.25 |
| `fail` / `missing` / `crash` | 0 |

Thứ tự áp dụng:

| Bước | Rule |
|---|---|
| M1 | Không biên dịch được thì **T = 0**, mọi chiều = 0 (S103, S109, S111) |
| M0 | Bài rỗng hoặc comment hết thì T = 0 |
| M2 | Có **vòng lặp vô hạn** ở bất kỳ hàm nào thì `1 1 0 0 0 0`, **T = 2** (S106, S107) |
| M3 | **Tiên quyết (Q5):** P1 khác `ok` thì P2..P4 = 0 và kết quả là `1 0 0 0 0 0`, **T = 1** (S105, S113, S114). Áp cho mọi kiểu P1 sai, kể cả hard-code tên file hoặc kích thước |
| M4 | P1 = `ok`: `T = round_half_down(Σ điểm câu)`, sau đó tách T thành 6 chiều theo bảng dưới |

Bảng tách T thành 6 chiều (M4):

| T | C IO L E X Q | Khi nào |
|---|---|---|
| 10 | 1 1 4 2 1 1 | cả 4 câu `ok` (S115) |
| 9 | 1 1 3 2 1 1 | lỗi thuộc loại logic (S104) |
| 9 | 1 1 4 1 1 1 | lỗi thuộc loại biên (S102) |
| 8 | 1 1 2 2 1 1 | thiếu một câu (S101) |
| 8 | 1 1 3 1 1 1 | vừa có lỗi logic vừa có lỗi biên |
| 7 | 1 1 2 1 1 1 | |
| 6 | 1 1 1 1 1 1 | |
| 5 | 1 1 1 0 1 1 | ví dụ chỉ P1 và P2 đúng |
| 4 | 1 1 1 0 0 1 | ví dụ P1 đúng, P2 `partial` |
| 3 | 1 1 0 0 0 1 | chỉ P1 đúng |

`io_format` ở multi_problem = **"P1 đọc file đúng"**: P1 hỏng thì `IO=0`.

Taxonomy theo từng loại lỗi:

| Lỗi | Taxonomy |
|---|---|
| Không biên dịch được | `Lỗi biên dịch` (+ `Lỗi hard-code` nếu `#include "file.csv"`) |
| Vòng lặp vô hạn | `Lỗi logic`, `Lỗi vòng lặp` |
| P1 crash `stoi`/`stof` | `Lỗi hàm` |
| P1 trả về mảng tĩnh cục bộ | `Lỗi mảng/chuỗi`, `Lỗi logic` |
| P1 hard-code tên file hoặc kích thước | `Lỗi hard-code` |
| Câu ở trạng thái `partial` (sai công thức BC, sai điều kiện) | `Lỗi thuật toán` hoặc `Lỗi logic` |
| Câu ở trạng thái `edge` | `Lỗi edge case` |
| Đúng hoàn toàn | `[]` |

Ví dụ kiểm tra công thức trên mẫu thật:

| Mẫu | Trạng thái các câu | Σ | T dự đoán | T giảng viên |
|---|---|---|---|---|
| S115 | ok, ok, ok, ok | 10 | 10 | 10 ✓ |
| S104 | ok, ok, partial, ok | 8.75 | 9 | 9 ✓ |
| S102 | ok, ok, ok, edge | 9.5 | 9 | 9 ✓ |
| S101 | ok, ok, missing, edge | 7 | 7 | 8 ✗ |

---

## 3. Nhiễu nhãn và vấn đề dữ liệu (ứng viên cho điểm thưởng)

| # | Vấn đề | Xử lý |
|---|---|---|
| N1 | EX02-S214 comment hết code nhưng được 10/10 | sửa nhãn thành 0 (Q2) |
| N2 | Quy tắc tiên quyết áp không nhất quán: S112 = 9, S110 = 7, S108 = 6 dù feedback ghi "P1 sai, không chấm câu sau" | nhãn đúng theo Q5 phải là 1; loại khỏi cổng kiểm tra và báo cáo là nhiễu |
| N5 | S102: P3 lặp vô hạn (không tăng `pCurr` khi cập nhật max) nhưng được 9 điểm, feedback ghi "P3 đúng" | giữ nhãn, ghi nhận là nhiễu |
| N6 | `compile_log` và `test_report` rỗng trong JSON của cả bộ mẫu lẫn bộ test | tự sinh bằng harness |
| N8 | Task 3 ở bộ mẫu có `taxonomy_error` trong `input`, nhưng ở bộ test thì không (đề: "nhãn lỗi không cho sẵn") | dữ liệu tổng hợp làm theo bộ test |
| N9 | Feedback L2 của EX01-S109 và S111 dán nguyên log g++ (có code), có thể mâu thuẫn với quy định "L2 không đưa code" | ✅ chốt: **hợp lệ**. Log g++ không tính là "đưa code"; compliance checker bỏ qua khối log |
| N7 | Đề EX01 ghi điểm câu 1/4/2/3, còn `exams.json` ghi 2.5 mỗi câu | **chấm theo 2.5 mỗi câu (Q3)**; trong báo cáo chỉ ghi chú là đề và metadata không khớp |
