# Task 2: quy luật gán nhãn của giảng viên (suy ra từ 32 bài sample)

Nguồn: `data/raw/sample_dataset`. Với mỗi bài đọc cùng lúc nhãn Task 2 (`taxonomy_error`), điểm rubric Task 1 và lời
nhận xét Task 3 (`feedback`) của giảng viên: lời nhận xét giải thích vì sao có nhãn. Chỉ dùng dữ liệu sample (có nhãn);
không dùng bài public. 32 bài là ít: mỗi quy luật dưới đây ghi số bài làm bằng chứng; quy luật chỉ có 1 bài thì coi là
giả thuyết, cần kiểm tra thêm trên silver.

## Quy luật chung

| # | Quy luật | Bằng chứng |
|---|---|---|
| G1 | Nhãn mô tả **lỗi chính làm mất điểm**, thường 1-2 nhãn (tối đa 3). Không liệt kê mọi khuyết điểm. | 32/32 bài; 0 nhãn: 6, 1 nhãn: 15, 2 nhãn: 10, 3 nhãn: 1 |
| G2 | **Câu/hàm không làm thì KHÔNG có nhãn.** | S101 (P3 không làm → chỉ `Lỗi logic` của P4), S108 (P3, P4 không làm → chỉ `Lỗi hard-code`), S113/S114 (không làm P2-P4 → nhãn chỉ từ lỗi của P1) |
| G3 | Đề nhiều câu: **P1 là câu tiên quyết**; P1 sai thì nhãn chỉ lấy từ lỗi của P1, các câu sau không chấm. | S105, S108, S110, S112, S113, S114 (feedback ghi "câu 1 là câu tiên quyết") |
| G4 | `compilable = 0` ⟺ có `Lỗi biên dịch` (6/6). Có thể kèm 1 nhãn nêu **nguyên nhân** của lỗi biên dịch. | S103 (+hard-code: `#include` file csv), S212 (+vòng lặp: biến `cnt` trong `for` chưa khai báo), S217 (+logic: "code chưa hoàn thiện"); S109, S111, S203 chỉ biên dịch |
| G5 | Bài đúng hết → `[]` (5/6 bài 10 điểm). Ngoại lệ: nộp bản **comment toàn bộ bài** → `Lỗi style` dù vẫn 10 điểm. | S115, S201, S202, S211; S214 |
| G6 | `Lỗi edge case` **không xuất hiện lần nào** trong 32 bài. | 0/32 |

## Theo từng nhãn

| Nhãn | Giảng viên dùng khi | Bằng chứng (lời nhận xét) |
|---|---|---|
| Lỗi biên dịch | code không compile (log có `error`) | 6 bài, xem G4 |
| Lỗi nhập/xuất | **output sai định dạng**: sai hoa thường, thừa dấu cách | S205 "in thừa 1 dấu cách ở trước", S206 "True/False chứ không phải TRUE/FALSE". Không phạt câu nhắc nhập ("Input number: ") — S211 được `[]`, 10 điểm |
| Lỗi logic | kết quả sai do công thức/luồng sai; giả định sai về dữ liệu; chương trình chưa hoàn thiện; xoá node sai | S101 "xoá node giữa list fail", S105/S110 "assume n là số dòng cho trước", S206 "nhân d thay vì mũ d", S210 "chưa hoàn thiện", S217 |
| Lỗi vòng lặp | **vòng lặp vô hạn** (thiếu `cur = cur->next`), vòng lặp sai chỉ số, vòng lặp tính toán sai | S106, S107 "lặp vô tận" (kèm `Lỗi logic`), S209 "for sai chỉ số, bỏ qua chữ số đầu", S215, S216 "sau vòng lặp sum quá lớn" |
| Lỗi mảng/chuỗi | trả về mảng tĩnh cục bộ (mất khi ra khỏi hàm) | S105 (1 bài, giả thuyết) |
| Lỗi hàm | **dùng/gọi hàm sai**, kể cả hàm thư viện: `stoi`/`stof` lỗi khi chuyển chuỗi; gọi hàm thiếu đối số (`if (is_armstrong_number)`); hàm tự viết tính sai | S113 "lỗi stof", S114 "lỗi stoi", S208 "gọi hàm chưa đúng", S213 "hàm tính tích bị sai", S215 "hàm tính mũ bị sai" |
| Lỗi thuật toán | **công thức/cách tính cốt lõi của đề sai** (tuổi với năm BC), cấu trúc dữ liệu tạo ra sai (list rỗng), hàm lũy thừa sai do khai báo lại biến trong vòng lặp | S104 "sai công thức tính tuổi với BC", S102 "P2 list rỗng", S207 "luythua sai, bỏ chữ int ở dòng 9", S209 |
| Lỗi hard-code | **P1 đọc file bằng giá trị cứng**: kích thước mảng cứng, tên file là chuỗi `"filename"`, `#include` file csv | S108, S112, S103 |
| Lỗi style | hàm phức tạp không cần thiết; nộp bản comment toàn bộ | S204 "hàm tính mũ có vẻ phức tạp", S214 |
| Lỗi edge case | (chưa thấy) | 0 bài |

## Ranh giới dễ nhầm

- **Hàm tính lũy thừa sai** (EX02, 5 bài) được gán khác nhau tuỳ nguyên nhân: sai do khai báo lại biến → thuật toán
  (S207); hàm tự viết trả sai → hàm (S213, S215); sai trong vòng lặp tính → vòng lặp/logic (S215, S216); hàm phức
  tạp + sai → logic + style (S204). Đây là ranh giới mờ nhất: nhãn theo **chỗ gây sai** (khai báo, hàm, vòng lặp).
- **"Giả định n là số dòng cho trước"** là `Lỗi logic` (S105, S110), còn **cấp phát mảng cố định** là `Lỗi hard-code`
  (S108): cùng là đọc sai số bản ghi, khác ở chỗ có giá trị cứng trong code hay không.
- **Vòng lặp vô hạn** luôn đi kèm `Lỗi logic` ở EX01 (S106, S107), có thể vì rubric cho 0 điểm logic.

## Đối chiếu với prompt CoT hiện tại (commit d3021cb)

| Prompt đang nói | Quy luật thật | Cần sửa |
|---|---|---|
| "Lỗi hàm là khi bài **thiếu hàm mà đề yêu cầu**" | Câu không làm **không** có nhãn (G2); `Lỗi hàm` = gọi/dùng hàm sai | **Sai** — bỏ "thiếu hàm", thêm "câu không làm không phải lỗi", ví dụ `stoi`/`stof` sai, gọi hàm thiếu đối số |
| Bước 4 đối chiếu prototype, "không có trong bài" | như trên | Đổi: hàm không có / thân rỗng = câu không làm, bỏ qua |
| Định nghĩa `Lỗi nhập/xuất` chung chung | sai hoa thường, thừa dấu cách bị phạt; câu nhắc nhập không bị phạt | Thêm ví dụ cụ thể |
| Không có hướng dẫn cho vòng lặp vô hạn | vô hạn → `Lỗi vòng lặp` + `Lỗi logic` | Thêm |
| Comment bị xoá trước khi chấm | comment toàn bộ bài → `Lỗi style` | Thêm quy tắc cho trường hợp `ALL_COMMENTED` |
| `Lỗi edge case` dùng như các nhãn khác | chưa từng xuất hiện | Chỉ gán khi rất rõ (hoặc thử bỏ hẳn, đo trên silver) |
| "Lỗi đã có trong compile_log chỉ thuộc biên dịch" | có thể kèm 1 nhãn nêu nguyên nhân (G4) | Nới: cho phép thêm tối đa 1 nhãn nguyên nhân khi rõ |
