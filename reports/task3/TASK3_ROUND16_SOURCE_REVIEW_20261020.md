# Round 16 — source expectations, frozen before reading generated outputs

Assistant-reviewed, not human-verified. Review dựa trên toàn bộ source/đề train, trước khi đọc output Round16; Round15 đã từng review cùng 24 ID. Không benchmark mù. Không sửa gold; không suy correctness từ compiler pass. Mỗi câu khẳng định kỹ thuật trong raw/final được đối chiếu với source dưới đây; claim chưa chứng minh đủ ghi unassessed. L1 chỉ nhẹ/khen có căn cứ, L2 chẩn đoán không chỉ hướng sửa, L3 nguyên nhân+hướng sửa khả thi; L4 được code. Missing diagnosis/repair không được tính là claim sai nếu model chỉ trả câu chung.

| ID (bỏ tiền tố SYN-) | Level | Căn cứ source / expectation |
|---|---:|---|
| COUNTEVEN-0000 | 1 | P2 khởi tạo c=0, duyệt i<n, kiểm tra a%2==0; P3 min b hợp lý khi n>0. P1 mảng100 chưa có bound file. Không chứng nhận mọi input, không bịa lỗi biến chưa khởi tạo. |
| MAXDIFF-0000 | 1 | P1 fin.close() rồi mở fin2; gán n=soDong trước cấp phát. P2 cộng a-b, P3 max a-b, P4 gọi P2. Không nhầm hai stream hoặc hàm phụ với code cần chạy. |
| MINA-0001 | 1 | P1 vector đọc đủ cặp hợp lệ; n=v.size(); P2 min a, P3 tổng b, P4 gọi P2; các cout debug/main trong comment không chạy. Không gọi vector lỗi compiler. |
| PALIN-0008 | 1 | s[i + 1] so với s[n-1-i] sai đối xứng; "TRUE" khác "True". Feedback L1 không được nêu identifier, vị trí/cause hoặc sửa dù taxonomy vẫn được xuất đầy đủ. |
| MAXDIFF-0002 | 2 | prob3 chỉ `return 0;`, không tính max a-b. Không nói prob2 tính tổng sai: `s += (dem[i].a - dem[i].b);`. |
| MINA-0005-L2 | 2 | prob3 chỉ `return 0;`, không tính tổng b. P4 tự tính min a vẫn đáp ứng mô tả, không bắt buộc gọi prob2. |
| PALIN-0012 | 2 | Đọc __n trước; nếu khác121 lại `cin >> n;` trong đề chỉ có một số. Lỗi input tiêu thụ số đầu, không phải thuật toán đảo số thiếu khởi tạo. |
| PERFECT-0004 | 2 | `if (n < 1)` bỏ qua n=1: dem=1 => trả true sai. `i * i < n` bỏ ước căn ở số chính phương; phân biệt điểm này với claim chung rằng hoàn hảo số chính phương bị phân loại sai (chưa có căn cứ). |
| PROD-0004 | 2 | P3 `arr[i].a * arr[i + 1].b` trộn hai bản ghi, cuối đọc ô chưa khởi tạo. new Rec[soDong+1] nên không nói chắc vượt allocation. |
| REVSTR-0003 | 2 | Thuật toán đảo chuỗi đúng; `cout << " ";` thêm khoảng trắng. Impact phụ thuộc exact-output checker chưa được cho, không khẳng định syntax/algorithm sai. |
| REVSTR-0004-L2 | 2 | `i <= n / 2`: chuỗi chẵn đảo lại cặp giữa, ví dụ abcd -> dbca; lẻ tự swap giữa vô hại. Không nói bỏ phần tử đầu/cuối. |
| SUMPAIR-0003 | 2 | P3 kq3=0 và i=1: bỏ a đầu, sai dãy toàn âm. P2 kq2=0 trước cộng đủ i=0..n-1, không có thiếu khởi tạo. |
| BASE2-0005 | 3 | Lưu bit0..soBit-1 nhưng in `mangBit[i + 1]` từ i=soBit-1; đọc bit chưa gán, bỏ bit0. Sửa in mangBit[i]. Không coi mọi lần đều vượt64. |
| BASE2-0011 | 3 | `string r = ""` thiếu dấu chấm phẩy. Compiler error là căn cứ; hướng sửa thêm ; tại đây khả thi. |
| COUNTEVEN-0006-L3 | 3 | P2 `arr[i + 1].a`, P3 gán `tong = arr[i + 1].b` trong khi so arr[i].b; cả hai cần dùng đúng bản ghi i. arr[n] còn trong allocation n+1 nhưng chưa gán. |
| DISTINCT-0008-L3 | 3 | Vòng đếm `i < n - 1` bỏ phần tử cuối; kq(dem,i,dem[i]) kiểm tra prefix đúng. Sửa duyệt đủ i<n. Không nói hàm kq bỏ phần tử trùng là lỗi. |
| FIB-0004 | 3 | `if (n == 1) return 0;` trái F(1)=1. Đổi trả1 hoặc bỏ nhánh để dùng f[1]. Đề không có bound n nên array100/overflow là limitation có điều kiện. |
| PERFECT-0008 | 3 | main gọi `tong(n + 1)` thay vì kiểm tra chính n. Hàm tong dùng <= sqrt và if n<=1 đúng. Sửa đối số n; không thêm pow hoặc công thức khác. |
| SUMEVEN-0007 | 3 | x1 tính tổng phần tử chẵn đúng, TODO/debug nằm comment. Đề không cấm tên x1 và không có bound n; chưa có actionable logic defect đã xác nhận. Không bắt model bịa repair theo gold style. |
| SUMPAIR-0011 | 3 | P2 i=1 bỏ bản ghi0; P3 cập nhật arr[i+1].a thay arr[i].a; P4 trộn arr[i].a với arr[i+1].b. Hướng sửa chỉ số phù hợp từng hàm, không nói t/kq chưa khởi tạo (đã gán0/arr0). |
| DISTINCT-0016 | 4 | Vòng đọc `i < n - 1` thiếu số cuối. Patch i<n giữ set, include set đã có, syntax hợp lệ. |
| FIB-0002 | 4 | Extra `cout << " ";` có impact output chưa xác định, Fibonacci recurrence đúng trong miền biểu diễn. Không bịa falta prototype/header/initialization. |
| PROD-0020-L2 | 4 | Level thật là4 dù ID chứaL2. P1 `ifstream f("data.csv");` bỏ tham số filename, có thể đọc sai file. Patch mở filename; không nói chưa mở file. |
| SUMEVEN-0014 | 4 | `for (int k = 0; k < 5; k++)` thay n; n<5 đọc ô chưa khởi tạo, n>5 bỏ số sau. Patch k<n, không biến a đã đọc thành lỗi compiler. |

Style: ưu tiên 1–3 câu tự nhiên gọi đúng hàm/Pn, không thưởng nếu claim sai. Contamination: đối chiếu từng claim với task/code query và hai ví dụ train; ghi definite/probable/unassessed riêng, không coi từ phổ thông như `n` hoặc `main` là contamination. CoT: review từng excerpt có trong active code, defect có thực sự suy ra, và có khớp taxonomy/feedback; schema pass không phải evidence pass.
