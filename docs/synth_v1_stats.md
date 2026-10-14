# Thống kê tập dữ liệu tổng hợp `data/synth/v1`

Sinh ngày 2026-10-15 bằng `scripts/synth_stats.py` (chỉ số liệu tổng hợp, không chứa code).

| Thông tin build | Giá trị |
|---|---|
| Runner | cached:native:Apple clang version 21.0.0 (clang-2100.1.1.101) |
| Oracle (`exec_report`) | minimal |
| Bài gốc / đề (đã chuẩn bị) | 10, 7, 8, 9 |
| Guard public (train) | loại 0, Jaccard tối đa 0.422 |
| Guard trùng lặp (train) | loại 10, bù thêm 45 |
| Run cache | 35679 hit / 563 miss |
| Slot chưa lấp được | single:S10: 3, single:S9: 4, single:S8: 14, single:S7: 2, multi:10: 1, multi:9: 1, multi:8: 1, multi:6: 4, multi:5: 3, multi:4: 2, multi:2: 2, multi:1: 1, heldout:single:S11: 3, heldout:single:S10: 4, heldout:single:S9: 1, heldout:single:S8: 2, heldout:single:S3: 1 |

**Validator (`scripts/validate_synth.py --compile`): PASS** — 0 FAIL, 4 WARN

| Mức | Kiểm tra | Chi tiết |
|---|---|---|
| WARN | train:single-buckets | (thực tế, plan) lệch: {'S9': (11, 15), 'S8': (6, 20)} |
| WARN | train:multi-buckets | (thực tế, plan) lệch: {6: (16, 20)} |
| WARN | train:t2-quota | dưới 45: [('Lỗi thuật toán', 37)] |
| WARN | train:t2-cap | Lỗi edge case = 110 > trần 100 |

## Tập train

| Mục | Số lượng |
|---|---|
| Đề | 28 (18 single, 10 multi) |
| Bài nộp (Task 1 = Task 2) | 462 (277 single, 185 multi) |
| Record Task 3 | 612 (150 bản nhân bản mức khác) |

### Task 1 — chấm điểm rubric

**Phân bố tổng điểm**

| Tổng | Single | Multi | Tất cả |  |
|---|---|---|---|---|
| 0 | 5 | 15 | 20 (4%) | ██████████ |
| 1 | 25 | 19 | 44 (10%) | ██████████████████████ |
| 2 | 20 | 13 | 33 (7%) | ████████████████ |
| 3 | 15 | 0 | 15 (3%) | ████████ |
| 4 | 18 | 18 | 36 (8%) | ██████████████████ |
| 5 | 6 | 22 | 28 (6%) | ██████████████ |
| 6 | 11 | 16 | 27 (6%) | ██████████████ |
| 7 | 50 | 15 | 65 (14%) | ████████████████████████████████ |
| 8 | 22 | 19 | 41 (9%) | ████████████████████ |
| 9 | 60 | 24 | 84 (18%) | ██████████████████████████████████████████ |
| 10 | 45 | 24 | 69 (15%) | ██████████████████████████████████ |

Trung bình 6.13 · trung vị 7.0 · độ lệch chuẩn 3.20

**Theo rule của rulebook** (rule quan sát được khi chạy code)

| Rule | Ý nghĩa | Số bài | C IO L E X Q |
|---|---|---|---|
| M1 | không biên dịch được | 15 | 0 0 0 0 0 0 |
| M2 | lặp vô hạn | 13 | 1 1 0 0 0 0 |
| M3 | P1 hỏng (tiên quyết) | 19 | 1 0 0 0 0 0 |
| M4 | cộng điểm theo câu | 138 | theo câu |
| S0 | rỗng / comment hết | 5 | 0 0 0 0 0 0 |
| S1 | không biên dịch được | 25 | 0 0 0 0 0 1 |
| S2 | lặp vô hạn / bỏ dở | 20 | 1 0 0 0 0 1 |
| S3 | sai token + sai hết | 15 | 1 0 0 0 1 1 |
| S4 | logic sai | 50 | 1 1 2 1 1 1 |
| S5 | thừa ký tự output | 20 | 1 0 4 2 1 1 |
| S6 | đúng hết | 45 | 1 1 4 2 1 1 |
| S7 | hard-code đáp án | 18 | 1 1 1 0 0 1 |
| S8 | brute force + sai biên | 6 | 1 1 2 0 0 1 |
| S9 | sai token + sai một phần | 11 | 1 0 2 1 1 1 |
| S10 | sai ≥2 nhóm biên | 22 | 1 1 4 0 1 1 |
| S11 | sai 1 nhóm biên | 20 | 1 1 4 1 1 1 |
| S12 | đúng nhưng style kém | 20 | 1 1 4 2 1 0 |

**Phân bố từng chiều rubric**

| Chiều | =0 | =1 | =2 | =3 | =4 |
|---|---|---|---|---|---|
| compilable (0–1) | 45 | 417 |  |  |  |
| io_format (0–1) | 130 | 332 |  |  |  |
| logic (0–4) | 112 | 74 | 82 | 26 | 168 |
| edge_case (0–2) | 198 | 148 | 116 |  |  |
| complexity (0–1) | 139 | 323 |  |  |  |
| code_quality (0–1) | 72 | 390 |  |  |  |

**Đề nhiều câu — trạng thái P1..P4 quan sát được (top 10)**

| P1 / P2 / P3 / P4 | Số bài |
|---|---|
| ok / ok / ok / ok | 24 |
| ok / missing / ok / missing | 21 |
| ok / ok / missing / ok | 15 |
| fail / crash / crash / crash | 15 |
| missing / missing / missing / missing | 15 |
| ok / ok / edge / ok | 14 |
| ok / ok / crash / crash | 13 |
| ok / edge / edge / edge | 9 |
| ok / ok / partial / ok | 7 |
| ok / edge / missing / edge | 5 |

### Task 2 — phân loại lỗi đa nhãn

| Nhãn | Số bài | Tỉ lệ |  |
|---|---|---|---|
| Lỗi biên dịch | 45 | 10% | ███████████████ |
| Lỗi nhập/xuất | 46 | 10% | ███████████████ |
| Lỗi logic | 62 | 13% | █████████████████████ |
| Lỗi vòng lặp | 54 | 12% | ██████████████████ |
| Lỗi mảng/chuỗi | 58 | 13% | ███████████████████ |
| Lỗi hàm | 80 | 17% | ███████████████████████████ |
| Lỗi edge case | 110 | 24% | █████████████████████████████████████ |
| Lỗi thuật toán | 37 | 8% | ████████████ |
| Lỗi hard-code | 47 | 10% | ████████████████ |
| Lỗi style | 55 | 12% | ██████████████████ |
| `[]` (không lỗi) | 69 | 15% | ███████████████████████ |

Số nhãn/bài: trung bình 1.29 · 0 nhãn: 69 · 1 nhãn: 246 · 2 nhãn: 103 · 3 nhãn: 35 · 4 nhãn: 8 · 5 nhãn: 1

**Cặp nhãn hay đi cùng nhau (top 8)**

| Cặp nhãn | Số bài |
|---|---|
| Lỗi logic + Lỗi vòng lặp | 31 |
| Lỗi nhập/xuất + Lỗi logic | 26 |
| Lỗi edge case + Lỗi thuật toán | 24 |
| Lỗi mảng/chuỗi + Lỗi edge case | 22 |
| Lỗi hàm + Lỗi edge case | 20 |
| Lỗi vòng lặp + Lỗi edge case | 18 |
| Lỗi mảng/chuỗi + Lỗi style | 11 |
| Lỗi vòng lặp + Lỗi hard-code | 10 |

### Task 3 — phản hồi theo mức

| Mức | Số record | Tỉ lệ |
|---|---|---|
| Level 1 - Gợi ý nhẹ | 182 | 30% |
| Level 2 - Chẩn đoán | 216 | 35% |
| Level 3 - Gợi ý sửa | 150 | 25% |
| Level 4 - Lời giải mẫu | 64 | 10% |

| Chỉ số | Giá trị |
|---|---|
| Độ dài feedback (ký tự) | trung vị 76.0, p90 184 |
| Độ dài theo mức (trung vị) | L1: 42.0 · L2: 76.0 · L3: 123.0 · L4: 149.0 |
| Feedback khác nhau | 331/612 (54%) |
| L2 dán log g++ | 6 |
| Có khối code (chỉ hợp lệ ở L4) | 64 |
| Input có `taxonomy_error` | 0 |

### Theo đề

| Đề | Loại | Bài | Bài gốc dùng | Tổng điểm (điểm:số bài) |
|---|---|---|---|---|
| SYN-ARM | single | 26 | 8 | 0:1 1:2 2:2 3:4 4:3 6:4 7:3 9:4 10:3 |
| SYN-GEN | multi | 26 | 9 | 0:2 1:2 2:2 4:2 5:3 6:3 7:2 8:3 9:4 10:3 |
| SYN-COUNT | multi | 14 | 9 | 0:2 1:2 2:2 5:3 7:2 10:3 |
| SYN-PROD | multi | 26 | 9 | 0:2 1:2 2:2 4:3 5:3 6:3 7:2 8:2 9:4 10:3 |
| SYN-RANGE | multi | 17 | 9 | 0:2 1:2 2:2 4:1 5:1 7:2 9:4 10:3 |
| SYN-SUMB | multi | 14 | 9 | 0:2 1:1 5:2 7:2 8:3 9:2 10:2 |
| SYN-MINA | multi | 19 | 8 | 0:1 1:2 2:1 4:3 5:2 6:3 7:1 8:3 9:1 10:2 |
| SYN-COUNTGT | multi | 23 | 7 | 0:1 1:2 2:1 4:3 5:3 6:3 7:1 8:3 9:4 10:2 |
| SYN-SUMPAIR | multi | 13 | 5 | 0:1 1:2 2:1 4:2 5:1 7:1 9:3 10:2 |
| SYN-MAXDIFF | multi | 13 | 9 | 0:1 1:2 2:1 4:1 5:2 6:1 7:1 8:2 10:2 |
| SYN-COUNTEVEN | multi | 20 | 8 | 0:1 1:2 2:1 4:3 5:2 6:3 7:1 8:3 9:2 10:2 |
| SYN-PERFECT | single | 24 | 7 | 0:1 1:2 2:2 3:4 4:3 6:2 7:3 9:4 10:3 |
| SYN-PALIN | single | 23 | 8 | 0:1 1:2 2:1 3:4 4:3 6:4 7:3 9:2 10:3 |
| SYN-DIGITSUM | single | 16 | 8 | 0:1 1:2 2:1 4:3 7:3 9:3 10:3 |
| SYN-PRIME | single | 24 | 9 | 0:1 1:2 2:1 3:3 5:6 6:1 7:2 9:5 10:3 |
| SYN-BASE2 | single | 13 | 4 | 1:2 2:1 4:3 7:2 9:2 10:3 |
| SYN-REVSTR | single | 12 | 5 | 1:2 2:1 7:2 9:4 10:3 |
| SYN-DISTINCT | single | 17 | 7 | 1:1 2:1 7:2 8:6 9:4 10:3 |
| SYN-SUMEVEN | single | 19 | 6 | 1:1 2:1 7:4 8:5 9:5 10:3 |
| SYN-MAXARR | single | 12 | 6 | 1:1 2:1 7:3 9:5 10:2 |
| SYN-COUNTVOWEL | single | 13 | 7 | 1:1 2:1 7:2 8:5 9:2 10:2 |
| SYN-UPPER | single | 8 | 5 | 1:1 2:1 7:2 9:2 10:2 |
| SYN-FIB | single | 16 | 7 | 1:1 2:1 4:3 7:4 9:5 10:2 |
| SYN-FACT | single | 9 | 5 | 1:1 2:1 7:3 9:2 10:2 |
| SYN-SECONDMAX | single | 10 | 6 | 1:1 2:1 7:4 9:2 10:2 |
| SYN-GCDARR | single | 13 | 7 | 1:1 2:1 7:4 9:5 10:2 |
| SYN-POWER | single | 8 | 5 | 1:1 2:1 7:2 9:2 10:2 |
| SYN-COUNTUPPER | single | 14 | 7 | 1:1 2:1 7:2 8:6 9:2 10:2 |

### Code và nguồn gốc

| Mục | Giá trị |
|---|---|
| Số dòng code — single | trung vị 21, p10 15, p90 31 |
| Số dòng code — multi | trung vị 51, p10 22, p90 56 |
| Đã kiểm chứng bằng chạy code | 462 (100%) |
| Bài gốc (style_ref) | rename: 190, reference: 57, persona:debug_leftover: 54, persona:verbose_first_year: 53, persona:exam_style: 47, persona:globals_style: 32, persona:all_in_main: 29 |
| Fold | synthetic: 462 |
| Cặp đối chứng | 47 |
| Bẫy | harmless_extra: 11, weird_but_correct: 10, looks_dangerous: 9, prompt_input: 8, msvc_style: 8 |
| Bài chồng nhiều lỗi (≥2 defect) | 114 |
| Defect được dùng | D12: 90, CLEAN: 69, D20: 65, D14b: 47, D01: 40, D22: 35, D04: 26, D21: 22, D14d: 21, D07: 20, D23: 20, D15: 19, D13: 18, D17: 18, D06: 15, D08: 14, D16b: 12, D19: 11, D15s: 10, D14c: 9, D16a: 8, D14: 8, D05: 7, D18: 6, D00: 5 |

## Tập giữ riêng (heldout, chỉ để đánh giá)

| Mục | Số lượng |
|---|---|
| Đề | 4 (2 single, 2 multi) |
| Bài nộp (Task 1 = Task 2) | 65 (35 single, 30 multi) |
| Record Task 3 | 65 (0 bản nhân bản mức khác) |

### Task 1 — chấm điểm rubric

**Phân bố tổng điểm**

| Tổng | Single | Multi | Tất cả |  |
|---|---|---|---|---|
| 0 | 1 | 2 | 3 (5%) | ███ |
| 1 | 4 | 3 | 7 (11%) | ███████ |
| 2 | 3 | 2 | 5 (8%) | █████ |
| 3 | 1 | 0 | 1 (2%) | █ |
| 4 | 3 | 3 | 6 (9%) | ██████ |
| 5 | 1 | 4 | 5 (8%) | █████ |
| 6 | 1 | 3 | 4 (6%) | ████ |
| 7 | 8 | 2 | 10 (15%) | ██████████ |
| 8 | 0 | 3 | 3 (5%) | ███ |
| 9 | 6 | 4 | 10 (15%) | ██████████ |
| 10 | 7 | 4 | 11 (17%) | ███████████ |

Trung bình 5.95 · trung vị 7 · độ lệch chuẩn 3.26

**Theo rule của rulebook** (rule quan sát được khi chạy code)

| Rule | Ý nghĩa | Số bài | C IO L E X Q |
|---|---|---|---|
| M1 | không biên dịch được | 2 | 0 0 0 0 0 0 |
| M2 | lặp vô hạn | 2 | 1 1 0 0 0 0 |
| M3 | P1 hỏng (tiên quyết) | 3 | 1 0 0 0 0 0 |
| M4 | cộng điểm theo câu | 23 | theo câu |
| S0 | rỗng / comment hết | 1 | 0 0 0 0 0 0 |
| S1 | không biên dịch được | 4 | 0 0 0 0 0 1 |
| S2 | lặp vô hạn / bỏ dở | 3 | 1 0 0 0 0 1 |
| S3 | sai token + sai hết | 1 | 1 0 0 0 1 1 |
| S4 | logic sai | 8 | 1 1 2 1 1 1 |
| S5 | thừa ký tự output | 3 | 1 0 4 2 1 1 |
| S6 | đúng hết | 7 | 1 1 4 2 1 1 |
| S7 | hard-code đáp án | 3 | 1 1 1 0 0 1 |
| S8 | brute force + sai biên | 1 | 1 1 2 0 0 1 |
| S9 | sai token + sai một phần | 1 | 1 0 2 1 1 1 |
| S12 | đúng nhưng style kém | 3 | 1 1 4 2 1 0 |

**Phân bố từng chiều rubric**

| Chiều | =0 | =1 | =2 | =3 | =4 |
|---|---|---|---|---|---|
| compilable (0–1) | 7 | 58 |  |  |  |
| io_format (0–1) | 18 | 47 |  |  |  |
| logic (0–4) | 16 | 13 | 12 | 3 | 21 |
| edge_case (0–2) | 27 | 21 | 17 |  |  |
| complexity (0–1) | 22 | 43 |  |  |  |
| code_quality (0–1) | 11 | 54 |  |  |  |

**Đề nhiều câu — trạng thái P1..P4 quan sát được (top 10)**

| P1 / P2 / P3 / P4 | Số bài |
|---|---|
| ok / ok / ok / ok | 4 |
| ok / ok / edge / ok | 4 |
| ok / missing / ok / missing | 3 |
| ok / missing / edge / missing | 3 |
| ok / ok / edge / partial | 2 |
| ok / ok / missing / ok | 2 |
| ok / ok / partial / missing | 2 |
| ok / ok / crash / crash | 2 |
| fail / crash / crash / crash | 2 |
| missing / missing / missing / missing | 2 |

### Task 2 — phân loại lỗi đa nhãn

| Nhãn | Số bài | Tỉ lệ |  |
|---|---|---|---|
| Lỗi biên dịch | 7 | 11% | ███████ |
| Lỗi nhập/xuất | 5 | 8% | █████ |
| Lỗi logic | 9 | 14% | █████████ |
| Lỗi vòng lặp | 6 | 9% | ██████ |
| Lỗi mảng/chuỗi | 3 | 5% | ███ |
| Lỗi hàm | 14 | 22% | ██████████████ |
| Lỗi edge case | 12 | 18% | ████████████ |
| Lỗi thuật toán | 8 | 12% | ████████ |
| Lỗi hard-code | 6 | 9% | ██████ |
| Lỗi style | 3 | 5% | ███ |
| `[]` (không lỗi) | 11 | 17% | ███████████ |

Số nhãn/bài: trung bình 1.12 · 0 nhãn: 11 · 1 nhãn: 40 · 2 nhãn: 9 · 3 nhãn: 5

**Cặp nhãn hay đi cùng nhau (top 8)**

| Cặp nhãn | Số bài |
|---|---|
| Lỗi vòng lặp + Lỗi edge case | 4 |
| Lỗi logic + Lỗi vòng lặp | 4 |
| Lỗi hàm + Lỗi edge case | 4 |
| Lỗi nhập/xuất + Lỗi logic | 2 |
| Lỗi logic + Lỗi edge case | 2 |
| Lỗi mảng/chuỗi + Lỗi hàm | 2 |
| Lỗi nhập/xuất + Lỗi thuật toán | 1 |
| Lỗi logic + Lỗi thuật toán | 1 |

### Task 3 — phản hồi theo mức

| Mức | Số record | Tỉ lệ |
|---|---|---|
| Level 1 - Gợi ý nhẹ | 29 | 45% |
| Level 2 - Chẩn đoán | 21 | 32% |
| Level 3 - Gợi ý sửa | 10 | 15% |
| Level 4 - Lời giải mẫu | 5 | 8% |

| Chỉ số | Giá trị |
|---|---|
| Độ dài feedback (ký tự) | trung vị 58, p90 146 |
| Độ dài theo mức (trung vị) | L1: 42 · L2: 73 · L3: 122.5 · L4: 130 |
| Feedback khác nhau | 47/65 (72%) |
| L2 dán log g++ | 0 |
| Có khối code (chỉ hợp lệ ở L4) | 5 |
| Input có `taxonomy_error` | 0 |

### Theo đề

| Đề | Loại | Bài | Bài gốc dùng | Tổng điểm (điểm:số bài) |
|---|---|---|---|---|
| SYN-HELDOUT | single | 17 | 8 | 0:1 1:2 5:1 7:5 9:4 10:4 |
| SYN-HO-MULTI1 | multi | 19 | 8 | 0:1 1:2 2:1 4:2 5:2 6:3 7:1 8:3 9:2 10:2 |
| SYN-HO-MULTI2 | multi | 11 | 7 | 0:1 1:1 2:1 4:1 5:2 7:1 9:2 10:2 |
| SYN-HO-SINGLE | single | 18 | 7 | 1:2 2:3 3:1 4:3 6:1 7:3 9:2 10:3 |

### Code và nguồn gốc

| Mục | Giá trị |
|---|---|
| Số dòng code — single | trung vị 17, p10 4, p90 27 |
| Số dòng code — multi | trung vị 48.0, p10 22, p90 57 |
| Đã kiểm chứng bằng chạy code | 65 (100%) |
| Bài gốc (style_ref) | rename: 32, persona:debug_leftover: 7, persona:exam_style: 7, persona:all_in_main: 6, reference: 5, persona:verbose_first_year: 4, persona:globals_style: 4 |
| Fold | synthetic: 65 |
| Cặp đối chứng | 0 |
| Bẫy | 0 |
| Bài chồng nhiều lỗi (≥2 defect) | 14 |
| Defect được dùng | D12: 18, CLEAN: 11, D14b: 11, D08: 7, D01: 6, D07: 3, D23: 3, D21: 3, D17: 3, D05: 3, D20: 3, D15: 3, D16b: 2, D04: 2, D19: 1, D06: 1, D00: 1, D14d: 1, D18: 1 |

## So với plan (`docs/synth_plan.md`)

**Single — bucket theo rule**

| Rule | Ý nghĩa | Plan | Thực tế |  |
|---|---|---|---|---|
| S6 | đúng hết | 45 | 45 | ✓ |
| S5 | thừa ký tự output | 20 | 20 | ✓ |
| S11 | sai 1 nhóm biên | 20 | 20 | ✓ |
| S12 | đúng nhưng style kém | 20 | 20 | ✓ |
| S10 | sai ≥2 nhóm biên | 25 | 22 | thiếu 3 |
| S4 | logic sai | 50 | 50 | ✓ |
| S9 | sai token + sai một phần | 15 | 11 | thiếu 4 |
| S8 | brute force + sai biên | 20 | 6 | thiếu 14 |
| S7 | hard-code đáp án | 20 | 18 | thiếu 2 |
| S3 | sai token + sai hết | 15 | 15 | ✓ |
| S2 | lặp vô hạn / bỏ dở | 20 | 20 | ✓ |
| S1 | không biên dịch được | 25 | 25 | ✓ |
| S0 | rỗng / comment hết | 5 | 5 | ✓ |

**Multi — bucket theo tổng điểm** (tổng 3 không đạt được với 2.5 điểm/câu, 15 slot chuyển sang 4–6)

| Tổng | Plan | Thực tế |  |
|---|---|---|---|
| 10 | 25 | 24 | thiếu 1 |
| 9 | 25 | 24 | thiếu 1 |
| 8 | 20 | 19 | thiếu 1 |
| 7 | 15 | 15 | ✓ |
| 6 | 20 | 16 | thiếu 4 |
| 5 | 25 | 22 | thiếu 3 |
| 4 | 20 | 18 | thiếu 2 |
| 2 | 15 | 13 | thiếu 2 |
| 1 | 20 | 19 | thiếu 1 |
| 0 | 15 | 15 | ✓ |

**Task 2 — chỉ tiêu tối thiểu 45/nhãn và trần**

| Nhãn | Số bài | ≥ 45 | Trần |
|---|---|---|---|
| Lỗi biên dịch | 45 | ✓ | — |
| Lỗi nhập/xuất | 46 | ✓ | — |
| Lỗi logic | 62 | ✓ | ✓ |
| Lỗi vòng lặp | 54 | ✓ | — |
| Lỗi mảng/chuỗi | 58 | ✓ | — |
| Lỗi hàm | 80 | ✓ | — |
| Lỗi edge case | 110 | ✓ | vượt trần 100 |
| Lỗi thuật toán | 37 | thiếu | — |
| Lỗi hard-code | 47 | ✓ | — |
| Lỗi style | 55 | ✓ | — |

