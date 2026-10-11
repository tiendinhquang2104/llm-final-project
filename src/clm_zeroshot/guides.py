"""Prompt texts for the zero-shot CLM approach (Task 1 rubric + Task 2 labels).

Every text below is written from how the instructor labelled/graded the 32 public sample submissions
(`data/raw/sample_dataset`: exams, rubric scores, taxonomy labels, code, compile_log, test_report). The
`feedback` field / task3 file was NOT read. No student code is copied here — only the kinds of mistakes.
Texts are kept short (≤ ~60 words) because they are embedded by Qwen3-8B and matched by the CLM heads.
"""
from __future__ import annotations

LABEL_QUESTIONS: dict[str, str] = {
    "Lỗi biên dịch": (
        "Bài nộp trên có mắc Lỗi biên dịch không? Có nếu g++ báo error thật: thiếu dấu chấm phẩy, biến chưa khai "
        "báo, khai báo trùng, return thiếu giá trị trong hàm có kiểu trả về, #include một file dữ liệu. "
        "Chỉ có warning, hoặc chỉ thiếu hàm main khi link, thì không tính."
    ),
    "Lỗi nhập/xuất": (
        "Bài nộp trên có mắc Lỗi nhập/xuất không? Có nếu chuỗi in ra không khớp chính xác yêu cầu đề, ví dụ sai "
        "hoa thường, thêm khoảng trắng hoặc ký tự thừa quanh kết quả, đọc dữ liệu sai định dạng. In thêm dòng "
        "nhắc nhập dữ liệu thì không tính."
    ),
    "Lỗi logic": (
        "Bài nộp trên có mắc Lỗi logic không? Có nếu điều kiện, công thức hoặc luồng xử lý sai làm kết quả sai: "
        "tính sai tổng hoặc tích, không cập nhật biến, xoá phần tử mà không nối lại cấu trúc, tách dữ liệu sai "
        "trường, thiếu hẳn một bước tính."
    ),
    "Lỗi vòng lặp": (
        "Bài nộp trên có mắc Lỗi vòng lặp không? Có nếu vòng lặp sai: không tiến biến chạy hoặc con trỏ nên lặp "
        "vô hạn, bắt đầu sai chỉ số làm bỏ sót phần tử, điều kiện dừng sớm bỏ sót phần tử cuối, lặp thừa hoặc "
        "thiếu một lần, vòng lặp con lặp sai số lần."
    ),
    "Lỗi mảng/chuỗi": (
        "Bài nộp trên có mắc Lỗi mảng/chuỗi không? Có nếu dùng mảng hoặc chuỗi sai về bộ nhớ hay chỉ số: mảng "
        "cục bộ kích thước biến rồi trả về con trỏ tới nó, ghi qua con trỏ chuỗi chưa cấp phát, truy cập ngoài "
        "chỉ số, sai kích thước mảng."
    ),
    "Lỗi hàm": (
        "Bài nộp trên có mắc Lỗi hàm không? Có nếu hàm được viết hoặc dùng sai: chỉ làm một hàm và bỏ trống các "
        "hàm được yêu cầu, quên gọi hàm (dùng tên hàm như giá trị), hàm thiếu return, hàm phụ tính trên sai "
        "biến, hàm đệ quy sửa biến toàn cục."
    ),
    "Lỗi edge case": (
        "Bài nộp trên có mắc Lỗi edge case không? Có nếu thuật toán đúng với dữ liệu thông thường nhưng sai "
        "riêng ở trường hợp biên: n nhỏ nhất hoặc chỉ một chữ số, dữ liệu rỗng, phần tử đầu hoặc cuối, giá trị "
        "âm hay đặc biệt."
    ),
    "Lỗi thuật toán": (
        "Bài nộp trên có mắc Lỗi thuật toán không? Có nếu cách giải hoặc công thức cốt lõi sai dù code chạy được: "
        "công thức tính toán chính không đúng cho mọi loại dữ liệu, hàm tính toán tự viết trả về sai, tìm cực "
        "trị mà không duyệt đúng, giải phóng dữ liệu đầu vào khi còn dùng."
    ),
    "Lỗi hard-code": (
        "Bài nộp trên có mắc Lỗi hard-code không? Có nếu gán cứng thay vì dùng tham số: mở file bằng tên cố định "
        "thay vì tham số tên file, cấp phát mảng kích thước cố định theo dữ liệu mẫu, gán sẵn kết quả, đọc từ "
        "bàn phím thay vì nguồn dữ liệu được truyền vào."
    ),
    "Lỗi style": (
        "Bài nộp trên có mắc Lỗi style không? Có nếu trình bày làm hỏng bài: toàn bộ code bị comment lại, nhiều "
        "biến khai báo mà không dùng, đoạn code thừa vô nghĩa. Đặt tên tiếng Việt hay dùng hàm phụ thì không "
        "tính."
    ),
}

RUBRIC_QUESTIONS: dict[str, str] = {
    "io_format": (
        "Chấm chiều io_format cho bài nộp trên theo thang 0 đến 1: bài có chạy được và in đúng chính xác chuỗi "
        "kết quả đề yêu cầu (hoặc đúng prototype hàm) không?"
    ),
    "logic": (
        "Chấm chiều logic cho bài nộp trên theo thang 0 đến 4: thuật toán chính đúng đến mức nào? Đề nhiều câu "
        "thì tính theo các câu làm đúng có trọng số."
    ),
    "edge_case": (
        "Chấm chiều edge_case cho bài nộp trên theo thang 0 đến 2: bài xử lý các trường hợp biên và dữ liệu đặc "
        "biệt đến mức nào?"
    ),
    "complexity": (
        "Chấm chiều complexity cho bài nộp trên theo thang 0 đến 1: chương trình có chạy xong với độ phức tạp "
        "hợp lý, không lặp vô hạn hay crash không?"
    ),
    "code_quality": (
        "Chấm chiều code_quality cho bài nộp trên theo thang 0 đến 1: code có rõ ràng, chia hàm hợp lý, đúng "
        "ràng buộc đề và là một bài làm thực sự không?"
    ),
}

RUBRIC_LEVELS: dict[str, list[str]] = {
    "io_format": [
        "0 điểm: không biên dịch được, không chạy ra kết quả, hoặc in sai chuỗi kết quả: sai hoa thường, "
        "thêm khoảng trắng hoặc ký tự thừa.",
        "1 điểm: biên dịch và chạy được, in đúng chuỗi kết quả theo đề hoặc đúng prototype hàm; in thêm dòng "
        "nhắc nhập vẫn chấp nhận.",
    ],
    "logic": [
        "0 điểm: sai hoàn toàn: không biên dịch được, chỉ làm dở câu đầu, lặp vô hạn, crash hoặc không tính "
        "ra kết quả.",
        "1 điểm: chỉ đúng rất ít, ví dụ đọc dữ liệu sai nguồn nên hầu hết các câu sau không đúng.",
        "2 điểm: đúng khoảng một nửa: ý tưởng đúng nhưng một bước tính sai làm hỏng nhiều test, hoặc đề nhiều "
        "câu chỉ làm đúng khoảng một nửa số câu.",
        "3 điểm: gần đúng, chỉ sai nhỏ ở một câu hoặc một công thức phụ.",
        "4 điểm: đúng hoàn toàn mọi câu, kết quả đúng với mọi test.",
    ],
    "edge_case": [
        "0 điểm: không xử lý trường hợp biên vì logic sai hoàn toàn hoặc bài không chạy được.",
        "1 điểm: xử lý được một phần, còn sai ở một số trường hợp biên hoặc dữ liệu đặc biệt.",
        "2 điểm: xử lý đầy đủ các trường hợp biên như n nhỏ nhất, dữ liệu rỗng, phần tử đầu hoặc cuối, giá "
        "trị đặc biệt.",
    ],
    "complexity": [
        "0 điểm: không biên dịch được, lặp vô hạn, crash hoặc gần như chưa có thuật toán.",
        "1 điểm: chương trình chạy xong với độ phức tạp hợp lý cho đề.",
    ],
    "code_quality": [
        "0 điểm: bài gần như bỏ trống hoặc hỏng nặng: không biên dịch được, chỉ có hàm đầu làm dở, các hàm "
        "chính sai cấu trúc.",
        "1 điểm: code là một bài làm thực sự, chia hàm chấp nhận được, đúng thư viện cho phép.",
    ],
}

PROBLEM_QUESTION: str = (
    "Câu {pid} ({prototype}) trong bài nộp trên có được làm đúng hoàn toàn không? Đúng nghĩa là hàm được viết "
    "đầy đủ, đúng prototype, chạy hết và trả về kết quả đúng."
)

EVIDENCE: dict[str, str] = {
    # Task 2 labels (32 samples: 15 EX01 multi_problem, 17 EX02 single_problem; 4 have no label).
    "Lỗi biên dịch": "6/32 (S103,S109,S111,S203,S212,S217); đúng bằng tập compilable=0, đều có error thật trong "
                     "compile_log. Warning-only (S206,S208,S210) và lỗi link thiếu main (S214) không gán.",
    "Lỗi nhập/xuất": "2/32 (S205 in khoảng trắng trước True, S206 in TRUE/FALSE), cả hai io_format=0; in dòng nhắc "
                     "nhập (S211, S216) không bị gán.",
    "Lỗi logic": "12/32, nhãn phổ biến nhất (5 EX01, 7 EX02); đi kèm logic ≤2; thường đồng nhãn với vòng lặp, hàm, "
                 "mảng/chuỗi.",
    "Lỗi vòng lặp": "6/32 (S106,S107: duyệt danh sách không tiến con trỏ / dừng sớm; S209: bắt đầu từ chỉ số 1; "
                    "S212,S215,S216: vòng luỹ thừa sai).",
    "Lỗi mảng/chuỗi": "1/32 (S105: mảng VLA cục bộ trả về con trỏ, ghi qua con trỏ string chưa cấp phát).",
    "Lỗi hàm": "5/32 (S113,S114: chỉ viết prob1, không làm các hàm còn lại; S208: không gọi hàm, thiếu return; "
               "S213: hàm luỹ thừa nhân sai biến; S215: đệ quy ghi đè biến toàn cục).",
    "Lỗi edge case": "0/32: giảng viên chưa gán nhãn này cho bài mẫu nào.",
    "Lỗi thuật toán": "4/32 (S102,S104: công thức tuổi BC / tìm max sai; S207: hàm luỹ thừa trả sai; S209). "
                      "Có thể đi cùng logic 3-4 (S102 logic=4, S104 logic=3).",
    "Lỗi hard-code": "3/32, chỉ ở EX01 (S103 include/tên file cố định; S108 mảng cố định 21 phần tử, đọc cin; "
                     "S112 mở chuỗi \"filename\").",
    "Lỗi style": "2/32 (S204 biến thừa/code thừa, S214 toàn bộ code bị comment) — cả hai vẫn code_quality=1.",
    # Task 1 rubric dimensions.
    "io_format": "0 ở 11/32: 6 bài lỗi biên dịch, S205/S206 sai chuỗi in, S113/S114/S210 không tạo ra kết quả.",
    "logic": "phân bố 0:13, 1:1, 2:9, 3:2, 4:7. EX02 chủ yếu 0/2/4 (2 khi pass một phần test hoặc sai một bước); "
             "EX01 0 khi lỗi biên dịch / chỉ làm prob1 / lặp vô hạn, 2-3 khi làm được nhiều câu.",
    "edge_case": "0:13, 1:9, 2:10; gần như hàm của logic: logic 0 -> 0; logic 1 -> 1 (S108, EX01); logic 2 -> 1 "
                 "(EX02) hoặc 2 (EX01: S101, S110); logic 3-4 -> 2 (trừ S102: 1).",
    "complexity": "0 ở 12/32: các bài logic=0 (biên dịch lỗi, lặp vô hạn, chỉ làm dở) trừ S206; còn lại 1.",
    "code_quality": "0 ở 8/32, toàn EX01 (3 lỗi biên dịch + S105-S107, S113, S114); EX02 luôn 1 kể cả bài lỗi "
                    "biên dịch hay nhãn style.",
}
