"""Task 2 prompting: zero-shot chain-of-thought with a teacher persona (docs/task2_prompting.md).
Pure functions of (exam, sample, cfg); never use `feedback`."""
from __future__ import annotations

from src.task2.prompts import LABEL_GUIDE, exam_text, submission_text

FINAL_MARKER = "KẾT LUẬN:"

SYSTEM_COT = (
    "Bạn là giảng viên môn Lập trình C++ nhập môn, đang chấm bài nộp của sinh viên. "
    "Nhiệm vụ: xác định TẤT CẢ các loại lỗi có trong bài, theo đúng danh sách nhãn bên dưới. "
    "Một bài có thể có 0, 1 hoặc nhiều lỗi. Bài đúng hoàn toàn thì trả về danh sách rỗng.\n\n"
    "DANH SÁCH NHÃN (chỉ dùng đúng tên này):\n" + LABEL_GUIDE + "\n\n"
    "NGUYÊN TẮC CHẤM:\n"
    "- Chỉ gán nhãn khi chỉ ra được dòng code cụ thể gây lỗi. Không đoán.\n"
    '- Nếu compile_log có "error" thì chắc chắn có "Lỗi biên dịch". Cảnh báo (warning) thì không tính.\n'
    '- Bám sát yêu cầu đề: làm khác yêu cầu (ví dụ đề bắt dùng đệ quy mà dùng vòng lặp) là "Lỗi thuật toán".'
)

STEPS = (
    ("Biên dịch", "compile_log có lỗi (error) không?"),
    ("Nhập/xuất", "đọc dữ liệu và định dạng in ra có khớp đề không?"),
    ("Vòng lặp và mảng/chuỗi", "chỉ số, điều kiện dừng, kích thước có đúng không?"),
    ("Hàm", "prototype, kiểu trả về, return, cách truyền tham số có đúng không?"),
    ("Logic, edge case, hard-code", "có nhánh/công thức sai, bỏ sót trường hợp biên, hoặc gán cứng kết quả không?"),
    ("Thuật toán", "cách làm và cấu trúc dữ liệu có đúng yêu cầu đề không?"),
    ("Style", "đặt tên, thụt lề, code lặp, biến toàn cục có chấp nhận được không?"),
)


def cot_instruction() -> str:
    """Asks for all seven steps BEFORE the conclusion line, as a fill-in template: Qwen2.5-Coder answered with the
    conclusion line only when the instruction just said "finally write exactly one line"."""
    steps = "\n".join(f"{i}. {name}: {q}" for i, (name, q) in enumerate(STEPS, 1))
    template = "\n".join(f"{i}. {name}: <nhận xét, dẫn số dòng hoặc đoạn code làm bằng chứng>"
                          for i, (name, _) in enumerate(STEPS, 1))
    return ("## CÁCH CHẤM\nChấm lần lượt 7 bước sau:\n"
            f"{steps}\n\n"
            "## ĐỊNH DẠNG TRẢ LỜI (bắt buộc)\n"
            "Viết đủ 7 mục theo đúng khung dưới đây, mỗi mục 1-3 câu, rồi mới đến dòng KẾT LUẬN ở cuối cùng. "
            "Không được bỏ mục nào và không được viết KẾT LUẬN trước khi xong 7 mục.\n\n"
            f"{template}\n"
            f'{FINAL_MARKER} {{"taxonomy_error": ["<nhãn>", ...]}}\n\n'
            "Trong dòng KẾT LUẬN chỉ dùng đúng tên nhãn trong danh sách; [] nếu bài không có lỗi.")


def build_cot_messages(exam: dict, sample, cfg: dict) -> list[dict]:
    user = "\n".join([exam_text(exam), submission_text(sample, cfg), cot_instruction()])
    return [{"role": "system", "content": SYSTEM_COT}, {"role": "user", "content": user}]
