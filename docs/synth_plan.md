# Plan sinh 500 bài tổng hợp cho cả 3 task

Đầu vào: [task1_rulebook.md](task1_rulebook.md), bao gồm các quyết định Q1–Q5. Mục tiêu: 500 bài C++ tổng hợp, **mỗi bài có nhãn cho cả 3 task**,
**cùng định dạng với `sample_dataset`**, để fine-tune CLM local.

| Task | File | Nhãn sinh ra từ đâu |
|---|---|---|
| 1 | `task1_grading.json` | rubric 6 chiều, do labeler áp rule (bên dưới) |
| 2 | `task2_error_taxonomy.json` | `taxonomy_error`, map từ defect đã gài (§ Task 2) |
| 3 | `task3_feedback.json` | `target_feedback_level` (input) + `taxonomy_error` + `feedback` tiếng Việt (§ Task 3) |

Ba file dùng **chung `sample_id` và chung bài nộp**, giống bộ mẫu.

## Nguyên tắc bất biến
1. **Public test chỉ được dùng để tham chiếu văn phong khi sinh code** (xem § "Quy định dùng public test"). **TUYỆT ĐỐI không** gán nhãn bài public test, không dùng bài public test làm bài gốc để gài lỗi, và không chỉnh dữ liệu hay phân bố cho thiên lệch về public test. Nhãn chỉ đến từ 32 mẫu và từ đề do nhóm tự viết.
2. Nhãn sinh ra **từ cách tạo bài**: lỗi được gài có chủ đích rồi **kiểm chứng bằng cách chạy code** trên bộ test chuẩn (viết tay). Không có bước LLM tự chấm.
3. **Áp nghiêm ngặt quy tắc tiên quyết (Q5):** với multi_problem, P1 khác `ok` thì P2–P4 = 0 và T = 1, kể cả khi P2–P4 được viết đúng.
4. **Đánh giá trên 2 tập, không bao giờ train trên chúng:**
   - 32 mẫu thật, leave-one-exam-out (S214 đã sửa nhãn thành 0);
   - **4 đề tổng hợp giữ riêng** (leave-problem-out), để đo khả năng chấm *đề chưa gặp*.
5. **Tách theo fold khi dùng code thật làm gốc:** record sinh ra từ bài thật của đề X mang tag `fold = X`, và bị loại khỏi tập train khi đánh giá trên đề X.
6. Cố định seed và lưu provenance cho từng record: đề, bài gốc (nguồn: lời giải chuẩn, persona viết tay, hoặc bài thật đã sửa), defect, rule, trạng thái từng câu, cặp đối chứng, cờ bẫy.

## Pipeline

```
          ┌──────────── ngân hàng 32 đề (28 train + 4 giữ riêng) ───────────┐
          │                                                                 │
   test chuẩn (viết tay)                                  auto-oracle (LLM, tự động hoàn toàn)
   → dùng để GÁN NHÃN                                     → dùng để tạo INPUT exec_report
          │                                                                 │
 bài gốc: ① persona viết tay ② bài thật đã sửa (repair)                         │
          │                                                                 │
   gài defect D00..D23 ─► chạy trên test chuẩn ─► hành vi khớp defect? ─ không → loại
          │                                         │ có
          ▼                                         ▼
   cặp đối chứng + bẫy                       labeler(rulebook) → rubric, taxonomy, feedback
          │                                         │
          └──────────► chạy trên auto-oracle ─► exec_report (đưa vào input) ─► dedup ─► data/synth/v1/
```


## Quy định dùng public test (quyết định của nhóm, 2026-10-13)

Public test **được** dùng làm *tham chiếu* để code sinh ra giống code sinh viên thật hơn. Đổi lại, phải có hàng rào để nó **không rò rỉ vào nhãn và không làm dữ liệu thiên lệch** về public test.

| Được phép | Không được phép |
|---|---|
| Thống kê **tổng hợp** về văn phong: phân bố độ dài, tỉ lệ comment, `#include` hay dùng, kiểu đặt tên (tiếng Việt hay Anh, viết tắt), tỉ lệ dồn hết vào `main`, cách đọc file, các lỗi cú pháp kiểu sinh viên | Gán nhãn (rubric, taxonomy, feedback) cho **bất kỳ** bài public test nào, bằng tay hay bằng LLM |
| Rút ra **mô tả persona** dạng văn bản (ví dụ "hay dùng `while(!f.eof())`", "tên hàm tiếng Việt không dấu") để đưa vào prompt sinh code cho **đề của nhóm** | Dùng bài public test làm **bài gốc** để sửa, phá hay gài lỗi; copy hoặc diễn đạt lại một bài cụ thể |
| Đưa ≤ 3 **đoạn ngắn** (≤ 15 dòng, đã bỏ phần lời giải) làm ví dụ văn phong trong prompt persona, chỉ khi sinh code cho đề **khác chủ đề** với đề chứa đoạn đó | Soạn đề tổng hợp trùng hay gần trùng với 6 đề public test (Armstrong, xoá trùng, chuỗi tên, Generals, Battles, BST trên Generals) |
| | Chỉnh tỉ lệ bucket, tỉ lệ nhãn hay tỉ lệ mức phản hồi theo những gì *đoán* về public test |
| | Chọn mô hình hay checkpoint dựa trên dự đoán trên public test ngoài các lượt nộp leaderboard chính thức |

**Hàng rào kỹ thuật** (tự động, chạy ở bước đóng gói; vi phạm thì dừng build):
1. **Kiểm tra độ giống:** mọi bài tổng hợp được so MinHash (token chuẩn hoá, 5-gram) với **toàn bộ** bài public test. Jaccard ≥ 0.5 với bất kỳ bài nào thì **loại**. Báo cáo phân bố độ giống lớn nhất.
2. **Chặn ở cấp đề:** so statement đề tổng hợp với 6 đề public test (embedding + từ khoá chủ đề). Đề quá giống thì phải đổi.
3. **Cách ly mã nguồn:** module thống kê văn phong (`src/synth/style_stats.py`) chỉ xuất **file thống kê và mô tả persona** (`style_profile.json`, không chứa code). Mọi bước sinh dữ liệu chỉ đọc file này, **không** đọc thư mục public test.
   - Ngoại lệ duy nhất là ≤ 3 đoạn văn phong, lưu riêng trong `style_snippets.json` kèm nguồn.
4. **Provenance:** mỗi record ghi `style_ref` (persona và đoạn văn phong đã dùng, nếu có) để có thể kiểm tra lại.
5. **Ablation chứng minh không thiên lệch:**
   - So sánh sinh dữ liệu có và không có `style_profile` từ public test.
   - Đánh giá trên **32 bài thật và 4 đề giữ riêng** (không đánh giá trên public test).
   - Nếu chỉ public leaderboard tăng mà 2 tập này không tăng, coi là dấu hiệu thiên lệch và bỏ cải tiến đó.

---

## Cải tiến 1. Code giống sinh viên thật

Gài lỗi lên lời giải chuẩn sạch sẽ thì ra những bài "quá gọn, mỗi bài một lỗi". Mô hình sẽ học dấu vết của bước gài lỗi thay vì học cách chấm. Vì vậy dùng **hai nguồn bài gốc**:

**① Persona viết tay (quyết định 2026-10-15: không dùng LLM sinh code).**
Mỗi đề có **4 lời giải đúng viết tay** theo các persona khác nhau (`src/synth/persona_bases/<exam_id>/<persona>__0.cpp`):

| Persona | Đặc điểm |
|---|---|
| năm 1 dài dòng | biến tạm thừa, `if-else` lồng nhau, tên biến tiếng Việt (`dem`, `tich`) |
| dồn hết vào `main` | không tách hàm, hoặc tách hàm nhưng vẫn dùng biến toàn cục |
| kiểu thi cử | `#define ll long long`, `bits/stdc++`, viết tắt |
| cẩn thận, hướng đối tượng | nhiều hàm phụ, comment tiếng Việt |
| còn code debug | `cout` debug đã bị comment, `main` tự test |

Chỉ giữ lời giải **pass 100% test chuẩn**.

**② Sửa rồi phá lại (repair-then-break) trên 32 bài thật.**
- Bài thật đúng thì dùng trực tiếp làm gốc.
- Bài thật sai thì LLM sửa **tối thiểu** (diff nhỏ nhất) cho đến khi pass test chuẩn, rồi mới làm gốc.
- Sau đó gài **lỗi khác** với lỗi ban đầu của sinh viên. Bài sinh ra giữ nguyên văn phong thật: tên biến, cách xuống dòng, code thừa.
- Chỉ áp cho EX01, EX02. Mọi record sinh ra mang tag `fold` (nguyên tắc 5).

**Lỗi chồng lỗi.** Khoảng 30% bài mang 2–3 defect cùng lúc (ví dụ D22 style + D08 logic + D07 output). Nhãn Task 1 lấy theo rule ưu tiên cao nhất. Nhãn Task 2 là hợp các nhãn.

## Cải tiến 2. Nhiều đề, mỗi đề ít bài

Bộ test có 4/6 đề mới, nên mục tiêu là học **chấm một đề chưa gặp**. Đổi từ 9 đề × 55 bài sang **28 đề train × khoảng 18 bài**, cộng **4 đề giữ riêng**:

| Loại đề | Đề train | Đề giữ riêng | Record train |
|---|---|---|---|
| single_problem | EX02 + 17 đề tự soạn = 18 | 2 | 300 (khoảng 17/đề) |
| multi_problem | EX01 + 9 đề tự soạn = 10 | 2 | 200 (20/đề) |
| **Tổng** | **28** | **4** (khoảng 80 record, chỉ để đánh giá) | **500** |

**Chủ đề đề tự soạn** (kiến thức nhập môn kinh điển; **không** lấy theo đề nào của bộ test):
- **single (17 đề):**
  - *Hàm, số học:* số hoàn hảo, palindrome số, tổng chữ số, số nguyên tố, ước chung lớn nhất, đổi hệ cơ số.
  - *Mảng:* đếm phần tử phân biệt, dãy con tăng dài nhất, xoay mảng, in phần tử xuất hiện đúng 1 lần, trộn hai mảng đã sắp xếp.
  - *Chuỗi:* đảo từ, đếm nguyên âm, chuẩn hoá khoảng trắng, kiểm tra anagram, nén chuỗi `aaab → a3b1`.
  - *Ma trận:* tổng đường chéo.
- **multi (9 đề):** khung "P1 đọc CSV (tiên quyết) → P2–P4", **mỗi câu 2.5 điểm**.
  - 3 đề DSLK: chèn, xoá theo điều kiện, đảo danh sách.
  - 2 đề BST: chèn, duyệt, tìm min/max, đếm node.
  - 2 đề mảng struct: sắp xếp, lọc, thống kê.
  - 1 đề stack hoặc queue.
  - 1 đề DSLK đôi.
  - CSV do nhóm tự tạo, có ngày kèm era, danh sách phân tách bằng `|`, trường thừa không dùng.
- Mỗi đề viết theo **cùng khuôn với `exams.json`** (statement markdown, `problems`, `grading_policy`, `constraints`). Statement có thể nhờ LLM viết, sau đó nhóm duyệt **ở cấp đề** (không duyệt từng bài).

**Test chuẩn cho mỗi đề** (viết tay hoặc LLM viết rồi nhóm duyệt; dùng để **gán nhãn**):
- ≥10 test thường;
- ≥3 **nhóm test biên** có tên (`min`, `max/tràn số`, `rỗng`, `trùng`, …), mỗi nhóm ≥2 test;
- 1 test hiệu năng;
- với multi: harness chấm từng câu, trả về `ok`, `edge`, `partial` hoặc `fail`.

## Cải tiến 3. Kết quả chạy code làm input (`exec_report`)

Prompt của CLM có thêm một trường `exec_report`. Mô hình không phải tự đoán "code có chạy đúng không" mà chỉ cần **ánh xạ tín hiệu sang rubric, taxonomy và feedback**.

```
[exec_report]
compile: OK (g++ -std=c++11)        | warnings: 0
run: 12 test tự sinh | pass 9/12 | timeout 0 | crash 0
output_format: khớp sau chuẩn hoá 12/12, khớp chặt 0/12 (thừa khoảng trắng đầu dòng)
edge_probe: min=pass, max=FAIL(sai kết quả), zero=pass
perf_probe: pass (0.02s)
# multi_problem:
per_problem: P1=ok  P2=ok  P3=TIMEOUT  P4=crash(segfault)
```

**Quan trọng: train và test phải dùng cùng một nguồn tín hiệu.**
- Lúc suy luận, bài test **không có testcase**, nên `exec_report` phải đến từ một **auto-oracle** tự động.
- Do đó `exec_report` trong dữ liệu train **cũng phải sinh bằng auto-oracle**, không lấy từ test chuẩn viết tay. Như vậy mô hình học được cả *độ nhiễu* của oracle.
- Test chuẩn viết tay chỉ dùng để **gán nhãn**.

**Auto-oracle** (chạy tự động hoàn toàn cho mỗi đề, không có người can thiệp từng bài):

| Bước | Cách làm |
|---|---|
| a. Đọc đề | parse statement: ví dụ input/output, ràng buộc (`1 <= n <= 10^9`), prototype các câu, `data_file` |
| b. Lời giải tham chiếu | LLM viết K = 5 lời giải. Chỉ giữ lời giải pass **ví dụ trong statement** |
| c. Sinh input | ví dụ trong đề + input ngẫu nhiên trong ràng buộc + input biên tự suy từ ràng buộc (min, max, 0, rỗng) + 1 input lớn |
| d. Output mong đợi | **bỏ phiếu đa số** giữa các lời giải tham chiếu. Input nào không đạt đồng thuận ≥ 3/5 thì bỏ |
| e. Multi-problem | LLM viết harness gọi `prob1..prob4` từ prototype và file CSV của đề, kiểm tra từng câu bằng lời giải tham chiếu |
| f. Đóng gói | xuất `exec_report` dạng text như trên |

- Đánh giá chất lượng oracle trên 28 đề train bằng cách so `exec_report` của oracle với kết quả trên test chuẩn. Báo cáo độ khớp trong phần phân tích.
- ✅ **Đã chốt (2026-10-13):** auto-oracle **được đọc statement của đề public test và đề private test** để sinh testcase và `exec_report`, cả lúc suy luận lẫn khi chuẩn bị dữ liệu train.
  - Ranh giới: oracle chỉ sinh *input và output mong đợi cho testcase của đề*. **Không** LLM nào được gán rubric, taxonomy hay feedback cho bài public test.
  - `exec_report` của bài public test **không** phải nhãn và **không** được đưa vào tập train như record có nhãn.
  - Mặc định `exec_report: full`. Cờ `minimal` (chỉ `compile` + ví dụ trong statement) giữ lại để làm ablation.

## Cải tiến 4. Cặp đối chứng và bẫy

**Cặp đối chứng (khoảng 100 record = 50 cặp, nằm trong 500).** Hai bài từ **cùng một bài gốc**, khác nhau ≤ 3 dòng, nhưng **nhãn khác nhau** ở đúng ranh giới của rule:

| Cặp | Bài A | Bài B |
|---|---|---|
| ranh giới IO | `" True"` → S5 = 9 | `"True"` → S6 = 10 |
| ranh giới biên | sai 1 nhóm → S11 = 9 | sai 2 nhóm → S10 = 8 |
| ranh giới token | `TRUE` + logic sai hẳn → S3 = 3 | `TRUE` + logic sai một phần → S9 = 6 |
| tiên quyết | P1 ok, P3 `partial` → 9 | P1 hard-code, P2–P4 giữ nguyên → **1** |
| vòng lặp | có `cur = cur->next` → 10 | thiếu dòng đó → M2 = 2 |
| hard-code | thuật toán thật → 10 | `if` cứng theo ví dụ → S7 = 4 |

- Hai bài trong cặp **luôn nằm cùng một split** (cùng train, hoặc cùng tập giữ riêng).
- Provenance ghi `pair_id`.

**Bẫy (khoảng 50 record = 10%).** Bài **trông như sai nhưng nhãn chỉ phản ánh lỗi thật**, nhằm dạy mô hình không bắt lỗi theo bề ngoài:

| Loại bẫy | Ví dụ | Nhãn đúng |
|---|---|---|
| prompt nhập | `cout << "Nhap n: "` trước `cin` | không trừ IO (S-io-prompt) |
| cách làm lạ nhưng đúng | đệ quy thay vòng lặp, `string` thay tính số, `long long` khắp nơi | 10, `[]` |
| tên biến xấu nhưng code gọn | `a`, `b`, `x1` trong hàm ngắn, rõ ràng | 10 (**không** phải S12; S12 chỉ cho style rất kém: dồn `main` + code chết + tên vô nghĩa) |
| code thừa vô hại | hàm phụ không dùng, `#include` thừa, comment cũ | 10 |
| kiểu MSVC | `void main()`, `pow` không include `<cmath>` (G4) | C = 1 dù g++ báo lỗi; `exec_report` ghi rõ "lỗi kiểu MSVC" |
| trông nguy hiểm nhưng an toàn | `while(true)` có `break` đúng chỗ | không phải M2/S2 |

- 30 bẫy nằm trong các bucket 10 điểm.
- 20 bẫy nằm ở các bucket khác: có "mùi" lạ, nhưng nhãn chỉ theo **lỗi thật duy nhất** của bài.

---

### Thư viện defect (ánh xạ 1-1 vào rulebook)

**single_problem**

| Defect | Cách gài | Kiểm chứng bằng chạy | Rule → T |
|---|---|---|---|
| D00 comment toàn bộ hoặc file rỗng | bọc toàn bộ code bằng `//` | không có `main` | S0 → 0 |
| D01 cú pháp | xoá `;` hoặc `}`, `return true` thiếu `;` | g++ báo lỗi | S1 → 1 |
| D02 biến hoặc hàm chưa khai báo | đổi tên biến ở một chỗ dùng | g++ báo lỗi | S1 → 1 |
| D04 vòng lặp vô hạn | xoá lệnh tăng biến lặp | timeout | S2 → 2 |
| D05 lõi bỏ dở | xoá phần thân tính toán | timeout hoặc sai 100% | S2 → 2 |
| D06 sai token và logic sai hẳn | `TRUE`, kết hợp phép tính sai bản chất | 0 test pass, kể cả khi bỏ qua hoa/thường | S3 → 3 |
| D17 hard-code đáp án | `if (n==1634\|\|n==153) True else False`, hoặc chỉ xử lý ví dụ trong đề | pass ví dụ trong đề, sai phần lớn test ẩn | S7 → 4 |
| D18 brute force sai biên | duyệt thô hoặc dùng `int` gây tràn, sai mọi nhóm biên | test hiệu năng TLE, sai mọi nhóm biên, đúng một phần test thường | S8 → 5 |
| D19 sai token và logic sai một phần | `TRUE` kết hợp D08 | đúng một phần khi bỏ qua hoa/thường | S9 → 6 |
| D08 sai lõi thuật toán | `*d` thay `^d`, lệch chỉ số, khởi tạo sai | ≥1 test thường sai, chương trình kết thúc | S4 → 7 |
| D09 hàm phụ sai | biến shadow trong hàm luỹ thừa, lặp `<=` thay `<` | như D08 | S4 → 7 |
| D16a lỗi biên nhiều nhóm | `while(n>0)` sai với chữ số 0, `int` tràn ở `10^9`, sai ở `n` nhỏ nhất | pass mọi test thường, sai ≥2 nhóm biên | S10 → 8 |
| D16b lỗi biên một nhóm | chỉ một trong các lỗi trên | pass mọi test thường, sai đúng 1 nhóm | S11 → 9 |
| D07 thừa ký tự trước đáp án | `cout << " True"` | đúng khi `strip`, sai khi so chặt | S5 → 9 |
| D20–D23 | xem § Task 2 | | |

**multi_problem** (mọi defect áp lên một câu cụ thể; trạng thái câu do harness quyết định)

| Defect | Cách gài | Trạng thái câu | Rule |
|---|---|---|---|
| D01, D02, D03 | lỗi cú pháp, biến lạ, `#include "x.csv"` | — | M1 → 0 |
| D04 | quên `cur = cur->next` ở P2–P4 | timeout | M2 → 2 |
| D10 | P1 dùng `stoi`/`stof` sai trường hoặc sai dấu phân tách | P1 `crash` | M3 → 1 |
| D11 | P1 trả về mảng tĩnh cục bộ | P1 `fail` | M3 → 1 |
| D15 | P1 hard-code `"filename"` hoặc `new X[21]`, **có thể kèm P2–P4 viết đúng** | P1 `fail` | M3 → 1 (dạy mô hình quy tắc tiên quyết) |
| D12 | thân P2, P3 hoặc P4 rỗng | câu đó `missing` | M4 |
| D13 | sai công thức hoặc điều kiện | câu đó `partial` | M4 |
| D14 | sai ở biên: danh sách rỗng, xoá node đầu, giá trị bằng nhau, BC | câu đó `edge` | M4 + `Lỗi edge case` |

T tính theo M4: `round_half_down(Σ điểm câu)`, sau đó tách thành 6 chiều theo bảng trong rulebook.
Muốn có T = 3, 4, 5, 6, 7 thì ghép D12, D13, D14 trên nhiều câu. Ví dụ:

| Mục tiêu | Trạng thái P1–P4 | Σ |
|---|---|---|
| T = 5 | ok, ok, missing, missing | 5 |
| T = 4 | ok, partial, missing, missing | 3.75 → 4 |
| T = 6 | ok, ok, partial, missing | 6.25 → 6 |
| T = 7 | ok, ok, edge, missing | 7 |

**Biến đổi phong cách (không đổi nhãn):** tên biến tiếng Việt, prompt nhập, `main` debug, comment thừa, BOM, kiểu MSVC, code chết đã comment.
Phần lớn độ đa dạng giờ đến từ persona và bài thật đã sửa. Biến đổi phong cách chỉ còn là lớp bổ sung.

### Labeler (tất định) và cổng chất lượng
`label(exam_type, signals, defects) → rubric, taxonomy, rule_id, nguồn_rule`
- `signals` lấy từ **test chuẩn** (không phải auto-oracle): biên dịch, timeout, so khớp chặt và sau chuẩn hoá, nhóm biên, hiệu năng, trạng thái P1..Pn.
- **Cổng chất lượng:**
  - Chạy labeler trên 32 bài thật, với S214 tính là 0. Loại các mẫu nhiễu N2 (S108, S110, S112) và N5 (S102), còn 28 bài. Mục tiêu khớp tổng điểm **≥ 24/28**, và các rule có nguồn "mẫu" phải khớp 100%.
  - Các rule mới (S7–S12, T 4/5 của multi) cần **unit test trên bài viết tay**.
  - Không đạt thì sửa rulebook trước, không sinh dữ liệu.

### Lọc và đóng gói
- Loại các bài trùng (token chuẩn hoá + MinHash ≥ 0.9). **Không** loại bài trùng trong cùng một cặp đối chứng.
- **Hàng rào public test:** loại mọi bài có Jaccard ≥ 0.5 với bất kỳ bài public test nào (xem § Quy định dùng public test).
- Kiểm tra phân bố độ dài code và tỉ lệ dòng comment so với 32 bài thật.
- Thư mục `data/synth/` đặt trong gitignore.

## Phân bổ 500 record train

Đủ mọi mức tổng điểm từ 0 đến 10. Cặp đối chứng và bẫy **nằm trong** các bucket dưới đây, không cộng thêm. Mỗi đề nhận số record xấp xỉ đều nhau trong từng bucket.

**single_problem (300 record, 18 đề)**

| Rule | T | Record | Có `Lỗi edge case` |
|---|---|---|---|
| S6 đúng hết (gồm khoảng 20 bẫy) | 10 | 45 | |
| S5 thừa ký tự output | 9 | 20 | |
| S11 sai 1 nhóm biên | 9 | 20 | ✓ |
| S12 đúng nhưng style rất kém | 9 | 20 | |
| S10 sai ≥2 nhóm biên | 8 | 25 | ✓ |
| S4 logic sai | 7 | 50 | |
| S9 sai token, logic sai một phần | 6 | 15 | |
| S8 brute force sai biên | 5 | 20 | ✓ |
| S7 hard-code đáp án | 4 | 20 | |
| S3 sai token, logic sai hẳn | 3 | 15 | |
| S2 lặp vô hạn hoặc bỏ dở | 2 | 20 | |
| S1 không biên dịch được | 1 | 25 | |
| S0 rỗng hoặc comment hết | 0 | 5 | |

**multi_problem (200 record, 10 đề)**

| T | Record | Cách tạo |
|---|---|---|
| 10 | 25 | lời giải gốc, gồm khoảng 10 bẫy |
| 9 | 25 | 13 bài một câu `partial`, 12 bài một câu `edge` |
| 8 | 20 | một câu `missing`, hoặc kết hợp logic và biên |
| 7 | 15 | ghép D12 và D14 |
| 6 | 15 | ghép D12 và D13 |
| 5 | 20 | chỉ P1 và P2 đúng |
| 4 | 15 | P1 đúng, P2 `partial` |
| 3 | 15 | chỉ P1 đúng |
| 2 | 15 | M2, lặp vô hạn |
| 1 | 20 | M3: P1 hỏng; trong đó ≥10 bài D15 có P2–P4 viết đúng (đi cặp với bài P1 đúng) |
| 0 | 15 | M1, không biên dịch được |

**Tập giữ riêng:** 4 đề (2 single, 2 multi), khoảng 80 record sinh theo **cùng tỉ lệ bucket**. Chỉ dùng để đánh giá.

## Kiểm tra sau khi sinh
1. Cổng labeler.
2. **So sánh fine-tune LoRA** (đánh giá trên 32 bài thật **và** 4 đề giữ riêng):
   - (a) chỉ dùng 32 mẫu thật;
   - (b) 500 tổng hợp + 32 thật;
   - (c) như (b) nhưng có `exec_report`.

   Đo QWK, MAE và exact-match từng chiều.
3. **Ablation**, tương ứng với 4 cải tiến:

   | Cải tiến | So sánh |
   |---|---|
   | 1 | chỉ bài gốc từ persona, so với có thêm bài thật đã sửa; có hoặc không có lỗi chồng lỗi |
   | 2 | 9 đề × 55 bài, so với 28 đề × 18 bài (cùng 500 record) |
   | 3 | không có `exec_report` / `minimal` / `full` |
   | 4 | có hoặc không có cặp đối chứng và bẫy |
   | khác | có hoặc không có các bucket 4, 5, edge case; có hoặc không có D15 |

## Thứ tự triển khai

| # | Việc | Đầu ra |
|---|---|---|
| 1 | Harness chạy code có timeout (stdin, multi-problem, nhóm biên, hiệu năng) | `src/synth/verify.py` |
| 2 | Labeler theo rulebook, unit test, cổng kiểm tra trên 32 bài thật | `src/synth/labeler.py` |
| 3 | Ngân hàng 32 đề (YAML) + test chuẩn + CSV | `src/synth/problems/` |
| 4a | Thống kê văn phong từ public test → `style_profile.json` (không chứa code) | `src/synth/style_stats.py` |
| 4 | Bài gốc: persona viết tay + sửa bài thật (có tag `fold`) | `src/synth/persona_bases/`, `src/synth/bases.py` |
| 5 | Mutator D00–D23, lỗi chồng lỗi, cặp đối chứng, bẫy | `src/synth/mutators.py` |
| 6 | **Auto-oracle** + đánh giá oracle trên 28 đề train | `src/synth/oracle.py` |
| 7 | Sinh, lọc, đóng gói (3 file task, tập giữ riêng) | `scripts/build_synth_dataset.py` → `data/synth/v1/` |
| 8 | Fine-tune CLM và chạy ablation | registry trong `experiments/` |

---

# Mở rộng cho Task 2: phân loại lỗi đa nhãn

**Vì sao chưa đủ:** metric chính là **macro-F1**. Với phân bổ ở trên, nhãn sẽ rất lệch:
- `Lỗi logic` hơn 120 bài;
- `Lỗi style` khoảng 5 bài, `Lỗi mảng/chuỗi` khoảng 10 bài.

Như vậy mô hình sẽ không học được các nhãn hiếm. Cần đặt **chỉ tiêu tối thiểu cho từng nhãn**.

## T2.1 Bảng map defect → taxonomy (tất định)
Mỗi defect có **nhãn chính** (luôn gán) và **nhãn phụ** (gán khi defect thoả điều kiện), theo đúng cách giảng viên gắn nhãn trong 32 mẫu:

| Defect | Nhãn chính | Nhãn phụ (điều kiện) |
|---|---|---|
| D00 comment toàn bộ | `Lỗi biên dịch` | `Lỗi style` |
| D01, D02 lỗi biên dịch | `Lỗi biên dịch` | `Lỗi vòng lặp` (nếu lỗi nằm trong vòng lặp), `Lỗi logic` (nếu bài bỏ dở) |
| D03 `#include "x.csv"` | `Lỗi biên dịch` | `Lỗi hard-code` |
| D04 vòng lặp vô hạn | `Lỗi vòng lặp` | `Lỗi logic` |
| D05 lõi bỏ dở | `Lỗi logic` | — |
| D06, D19 sai token output | `Lỗi nhập/xuất` | `Lỗi logic` |
| D07 thừa ký tự output | `Lỗi nhập/xuất` | — |
| D08 sai lõi thuật toán | `Lỗi thuật toán` hoặc `Lỗi logic` (tuỳ kiểu: sai công thức là thuật toán, sai điều kiện là logic) | `Lỗi vòng lặp` (lệch chỉ số vòng lặp) |
| D09 hàm phụ sai | `Lỗi hàm` | `Lỗi logic` |
| D10 `stoi`/`stof` crash | `Lỗi hàm` | — |
| D11 trả về mảng cục bộ | `Lỗi mảng/chuỗi` | `Lỗi logic` |
| D15, D17 hard-code | `Lỗi hard-code` | — |
| D16, D14 lỗi biên | `Lỗi edge case` | — |
| D18 brute force | `Lỗi thuật toán` | `Lỗi edge case` |
| D12 thiếu câu | (không gắn nhãn, giống S101 của giảng viên) | — |
| D13 sai công thức một câu | `Lỗi thuật toán` | — |

**Defect mới để phủ các nhãn hiếm.** Các defect này không làm đổi rule Task 1 của bucket mà chúng được ghép vào:

| Defect | Cách gài | Nhãn | Tác động Task 1 |
|---|---|---|---|
| D20 mảng/chuỗi | truy cập ngoài mảng (`a[n]`), lệch chỉ số chuỗi, mảng cố định quá nhỏ, chuyển `char` sang `int` sai (`s[1]` thay `s[1]-'0'`) | `Lỗi mảng/chuỗi` | tuỳ hành vi: S4 (7) nếu sai test thường, S10/S11 nếu chỉ sai biên |
| D21 hàm | truyền tham trị thay tham chiếu, quên `return`, gọi hàm sai (`if (f)` thay vì `if (f(x))`, như S208) | `Lỗi hàm` | S4 (7) |
| D22 style trên **bài sai** | đặt tên biến vô nghĩa, dồn hết vào `main`, để lại code chết hoặc debug | `Lỗi style` (+ nhãn của lỗi chính) | không đổi (giống S204: Q vẫn = 1) |
| D23 style trên **bài đúng** | như D22 nhưng logic đúng 100% | `Lỗi style` | **rule mới S12:** `1 1 4 2 1 0` = 9 |

## T2.2 Chỉ tiêu nhãn (trên 500 bài)

| Nhãn | Tối thiểu | Lấy từ đâu |
|---|---|---|
| `[]` (không lỗi) | 60 (khoảng 12%, gần tỉ lệ 4/32 của bộ mẫu) | S6 + M4 đúng hết |
| `Lỗi biên dịch` | 45 | S0, S1, M1 |
| `Lỗi nhập/xuất` | 45 | S3, S5, S9 |
| `Lỗi logic` | 45, **trần 130** | nhiều bucket |
| `Lỗi vòng lặp` | 45 | S2, M2, D08 dạng lệch chỉ số |
| `Lỗi mảng/chuỗi` | 45 | D11, D20 |
| `Lỗi hàm` | 45 | D09, D10, D21 |
| `Lỗi edge case` | 45, **trần 100** | S8, S10, S11, D14 |
| `Lỗi thuật toán` | 45 | D08, D13, D18 |
| `Lỗi hard-code` | 45 | D03, D15, D17 |
| `Lỗi style` | 45 | D00, D22, D23 |

- Số nhãn trung bình mỗi bài khoảng **1.4**, gần bộ mẫu (≈ 1.3). Bài có 2 nhãn chiếm khoảng 35%, có 3 nhãn khoảng 5%.
- **Cách đạt chỉ tiêu:** sampler chọn defect theo trọng số ngược với số lần nhãn đó đã xuất hiện. Chỉ tiêu được kiểm tra ở bước đóng gói; nhãn nào thiếu thì sinh thêm.
- Bảng phân bổ theo tổng điểm Task 1 ở trên giữ nguyên. Defect D20–D22 được **chèn vào trong** các bucket S4, S10/S11 và M4 sẵn có. Riêng D23 tạo bucket mới S12 (9 điểm) với 20 bài, lấy bớt từ S4 (70 → 50). Nhờ vậy `[]` vẫn còn 45 + 25 = 70 bài.

---

# Mở rộng cho Task 3: sinh phản hồi có kiểm soát mức độ

**Vì sao chưa đủ:** plan cũ chưa sinh `feedback` và chưa có `target_feedback_level`.

Định dạng một record Task 3 (giống bộ test: **input không chứa `taxonomy_error`**):

```json
{"sample_id": "SYN-EX02-0042",
 "input":  {"exam_id": "...", "exam_type": "...", "language": "cpp11", "code_file": "...",
            "compile_log": "...", "exec_report": "...", "target_feedback_level": "Level 2 - Chẩn đoán"},
 "output": {"taxonomy_error": ["Lỗi vòng lặp", "Lỗi logic"],
            "feedback": "..."}}
```

> Bộ mẫu có `taxonomy_error` nằm trong `input` của Task 3, nhưng bộ test thì không. Đây là chỗ không nhất quán của dữ liệu
> (ghi vào danh sách nhiễu của rulebook). Dữ liệu tổng hợp làm theo **bộ test**.

## T3.1 Phân bổ mức phản hồi
- Mỗi bài được gán **1 mức**. Thêm 150 bài được nhân bản với **mức thứ 2**, để mô hình học cùng một lỗi viết ở các mức khác nhau. Tổng cộng **650 record Task 3**.

| Mức | Tỉ lệ | Ghi chú |
|---|---|---|
| Level 1 – Gợi ý nhẹ | 30% | |
| Level 2 – Chẩn đoán | 40% | |
| Level 3 – Gợi ý sửa | 20% | |
| Level 4 – Lời giải mẫu | 10% | ít nhưng vẫn cần, để mô hình phân biệt được khi nào *được phép* đưa code |

- Bài đúng hoàn toàn (`[]`) chủ yếu nhận Level 1, nội dung là lời khen ("Tốt.", "Bài làm đúng và gọn.").

## T3.2 Sinh feedback từ metadata của defect
Vì lỗi do chính mình gài, mình biết chính xác **vị trí (dòng, hàm, câu P_i), nguyên nhân, hướng sửa và đoạn code sửa** (lấy từ lời giải gốc).
Feedback được dựng bằng **template theo từng mức**, bám theo văn phong giảng viên trong 32 mẫu:
- EX01 viết ngắn, liệt kê theo từng câu: "P1 đúng; P2 đúng; P3 …".
- EX02 viết 1–2 câu, xưng "em".

| Mức | Được nói | Cấm (theo `label_space.json`) | Ví dụ (defect D04 ở P3) |
|---|---|---|---|
| L1 | có vấn đề hay không, lời khen hoặc động viên | vị trí, nguyên nhân cụ thể, code | "Bài còn một chỗ khiến chương trình không dừng, em kiểm tra lại nhé." |
| L2 | vị trí + nguyên nhân | cách sửa cụ thể, code | "P1 đúng; P2 đúng; P3 lặp vô tận vì con trỏ duyệt danh sách không được dịch chuyển → theo quy định là 0." |
| L3 | L2 + hướng sửa | lời giải hoàn chỉnh | "… Em cần cập nhật con trỏ sang node kế tiếp ở mỗi vòng lặp." |
| L4 | L3 + đoạn code sửa | — | "… Sửa: thêm `cur = cur->next;` cuối thân `while`." |

- **Đa dạng câu chữ:** mỗi mức có 5–8 template cho mỗi loại defect. Có thể dùng thêm LLM local để diễn đạt lại, nhưng **chỉ diễn đạt lại template, không chẩn đoán lại**.
- **Diễn đạt có kiểm soát:** sau khi LLM viết lại, câu phải vẫn nhắc đúng vị trí và nguyên nhân (kiểm bằng từ khoá của defect). Sai thì quay về template gốc.

## T3.3 Bộ kiểm tra tuân thủ mức (compliance checker)
Dùng cho cả dữ liệu sinh ra **và** cho output của mô hình khi suy luận (đây cũng là metric (a) của đề):
- **L1, L2:** (ngoại trừ khối log g++, hợp lệ ở L2) không có code fence, không có đoạn giống code (`;`, `cout`, `==`, `->`, `[i]`, tên hàm kèm ngoặc), không có động từ ra lệnh sửa ("sửa thành", "thêm dòng", "thay bằng").
- **L1:** không có số dòng, tên hàm hay tên biến cụ thể.
- **L3:** có hướng sửa nhưng không có khối code dài hơn 1 dòng.
- Record nào vi phạm mức của chính nó thì **loại**.

## T3.4 Cổng chất lượng cho Task 3
- Chạy compliance checker trên 32 feedback thật để kiểm tra checker:
  - Không được báo sai các feedback L1/L2 của giảng viên.
  - ✅ **Đã chốt:** feedback có **dán log biên dịch g++** (như EX01-S109, S111) là **hợp lệ** ở Level 2. Checker nhận diện khối log (`file.cpp:<dòng>:<cột>: error: …` và dòng trích code kèm số dòng do g++ in ra) và **bỏ qua khối này** khi kiểm tra "có code". Code do *người viết feedback tự đưa ra* vẫn là vi phạm.
  - Khi sinh feedback L2 cho các defect biên dịch (D01–D03), khoảng 30% record dán log g++ thật lấy từ harness, giống văn phong giảng viên.
- Lấy mẫu ngẫu nhiên 30 record tổng hợp để nhóm đọc lại văn phong. Chỉ đọc, không sửa tay từng bài.

---

# Tổng hợp đầu ra

```
data/synth/v1/
├── exams.json                 # 28 đề train: EX01, EX02 + 26 đề tự soạn (multi: 2.5đ/câu)
├── heldout/                   # 4 đề giữ riêng, cùng cấu trúc, chỉ để đánh giá
├── label_space.json           # copy từ bộ mẫu
├── task1_grading.json         # 500 record
├── task2_error_taxonomy.json  # 500 record (cùng sample_id)
├── task3_feedback.json        # 650 record (500 + 150 bài nhân bản với mức thứ 2)
├── submissions/<exam_id>/<sample_id>.cpp
├── exec_reports.jsonl         # exec_report do auto-oracle sinh (đưa vào input cả 3 task)
└── provenance.jsonl           # defect, rule, trạng thái câu, bài gốc, fold, pair_id, cờ bẫy, seed
```

## Danh sách kiểm tra theo task

| Hạng mục | Task 1 | Task 2 | Task 3 |
|---|---|---|---|
| Định dạng file giống bộ mẫu/test | ✓ | ✓ | ✓ (không có `taxonomy_error` trong input) |
| Phủ đủ nhãn | tổng điểm 0–10 | 10 nhãn, mỗi nhãn ≥45, có `[]` | 4 mức, có cả bài đúng và bài sai |
| Nhãn có bằng chứng | harness + labeler | map từ defect đã kiểm chứng | metadata defect + compliance checker |
| Cổng trên dữ liệu thật | khớp ≥24/28 | macro-F1 của map rule trên 32 mẫu (báo cáo, không chặn) | checker không báo sai feedback thật |
| Validation | 32 mẫu thật + 4 đề giữ riêng | như Task 1 | như Task 1 |
| Input có `exec_report` (auto-oracle) | ✓ | ✓ | ✓ |

## Bổ sung vào thứ tự triển khai (đánh số theo bảng "Thứ tự triển khai" ở trên)

| # | Việc | Đầu ra |
|---|---|---|
| 5b | Map taxonomy + defect D20–D23 + sampler cân bằng nhãn | `src/synth/taxonomy.py` |
| 6b | Template feedback theo mức + compliance checker | `src/synth/feedback.py`, `src/synth/compliance.py` |
| 7b | Xuất cả 3 file task (input có `exec_report`) + kiểm tra định dạng bằng validator sẵn có | `scripts/build_synth_dataset.py` |

---

# Ghi chú triển khai (2026-10-14, sau lần kiểm tra `data/synth/v1` đầu tiên)

Lần build đầu không đạt plan; dưới đây là các thay đổi đã làm và các điểm lệch có chủ đích.

| Hạng mục | Cách làm hiện tại |
|---|---|
| Kiểm chứng nhãn | Mọi record đi qua: bài gốc đã xác minh → gài lỗi → **biên dịch + chạy** → rulebook áp lên **hành vi quan sát được** → chỉ giữ nếu rule quan sát khớp với slot. Không đạt thì thử vị trí, bài gốc hoặc đề khác (tối đa 60 lần); slot không lấp được ghi vào `shortfall`, không làm giả. |
| `exec_report` | Chế độ `minimal`: kết quả biên dịch (kèm lỗi đầu tiên) + chạy **ví dụ trong statement**. Không chứa defect, rule hay test dùng để gán nhãn. Chế độ `full` (thêm input do LLM sinh, bỏ phiếu K lời giải) cần chạy LLM. |
| Đề nhiều câu | Harness chung cho schema `Rec{a,b}`: chạy `prob1..prob4` trên 2 bộ dữ liệu thường + 3 bộ biên (một dòng, cực trị ở hai đầu, số âm), so với lời giải chuẩn → `ok / edge / partial / fail / missing / crash`. |
| Tổng điểm 3 của đề nhiều câu | **Không đạt được** với 2.5 điểm/câu và làm tròn xuống ở .5 (chỉ P1 đúng = 2.5 → 2; mức kế tiếp là 3.75 → 4). 15 slot được chuyển sang tổng 4, 5, 6. |
| Bài gốc | Lời giải chuẩn + **4 persona viết tay** (128 bài, `src/synth/persona_bases/`) + 1 biến thể đổi tên mỗi bài → 10 bài gốc/đề; tất cả phải pass 100% test. Phương án sửa rồi phá lại trên bài thật (`fold`) **chưa làm**. |
| Bẫy | Bẫy giờ thực sự sửa code (prompt nhập, `void main`, `while(true)…break`, `long long`, include/hàm thừa) và vẫn phải qua kiểm chứng. |
| Cặp đối chứng | Hai bài cùng bài gốc, khác nhau ≤ 3 dòng, nhãn khác nhau. |
| Kiểm tra | `scripts/validate_synth.py --data data/synth/v1 --compile` (trả mã lỗi 1 khi có FAIL). |

### Kết quả build `data/synth/v1` (2026-10-15)

Số liệu đầy đủ: [synth_v1_stats.md](synth_v1_stats.md) (sinh bằng `scripts/synth_stats.py`).
`scripts/validate_synth.py --data data/synth/v1 --compile` → **PASS**.

| Chỉ số | Kết quả |
|---|---|
| Record | 462 train · 60 held-out · Task 3 gồm thêm 150 bản nhân bản mức khác |
| Bài gốc | lời giải chuẩn + 4 persona viết tay + 1 biến thể đổi tên mỗi bài → 10 bài gốc/đề |
| Số bài / đề | 8 – 26 (trước: 9 – 37); giới hạn mỗi đề ⌈bucket/số đề⌉+1, gấp đôi cho bucket hiếm (S3, S8, S9, S10) |
| Tổng điểm (train) | 0:20 · 1:44 · 2:33 · 3:15 · 4:36 · 5:28 · 6:27 · 7:65 · 8:41 · 9:84 · 10:69 |
| Task 2 | edge case 110 · hàm 80 · logic 62 · mảng/chuỗi 58 · style 55 · vòng lặp 54 · hard-code 47 · nhập/xuất 46 · biên dịch 45 · thuật toán 37 · `[]` 69 |
| `Lỗi vòng lặp` ∧ `Lỗi edge case` | 18 bài (trước: 90) — vòng lặp chỉ khi lỗi làm sai logic, sai riêng ở biên → edge case |
| Build | tất định; cache chạy (`data/synth/run_cache.sqlite`) → build lại ~4 phút |

Còn lệch (WARN): S8 6/20 và S9 11/15 (chỉ vài đề sinh được), multi tổng 6 16/20, `Lỗi thuật toán` 37 < 45,
`Lỗi edge case` 110 > trần 100. Hướng sửa gốc: thêm test biên / test hiệu năng cho các đề còn thiếu.
