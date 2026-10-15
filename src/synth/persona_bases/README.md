# Persona bases (viết tay)

Lời giải **đúng** cho từng đề tổng hợp, viết tay theo 4 kiểu sinh viên, dùng làm *bài gốc* để gài lỗi
(`scripts/build_synth_dataset.py --bases-dir`, mặc định trỏ vào thư mục này).

```
<exam_id>/<persona>__0.cpp
```

| Persona | Đề một câu | Đề nhiều câu (`Rec{a,b}`) |
|---|---|---|
| `verbose_first_year` | dài dòng, biến tạm thừa, if-else lồng, tên tiếng Việt không dấu | đếm dòng trước rồi mở lại file để đọc |
| `all_in_main` | dồn hết vào `main`, không tách hàm | — |
| `globals_style` | — | biến toàn cục, `getline` + `stringstream`, P4 tự tính lại |
| `exam_style` | `#define ll long long`, viết tắt, STL | đọc gọn một dòng, `max`/`min` |
| `debug_leftover` | còn `cout` debug đã comment | `vector` rồi chép sang mảng, `main` test đã comment |

Quy tắc:
- Không chép hay diễn đạt lại bài nộp của public test.
- Mỗi file phải **pass 100% test chuẩn** (đề một câu) hoặc ra `ok` ở cả 4 câu trên mọi bộ dữ liệu của
  harness (đề nhiều câu). Build tự kiểm tra và bỏ qua file không đạt.
- Đề nhiều câu: giữ nguyên prototype `prob1..prob4` và `struct Rec { int a, b; }`, **không** có `main`
  (harness tự thêm).
