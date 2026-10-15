"""Task 2 prompting: zero-shot chain-of-thought with a teacher persona (docs/task2_prompting.md).
Pure functions of (exam, sample, cfg); never use `feedback`."""
from __future__ import annotations

import dataclasses
import json
import re

from src.task2.augment import _comment_spans
from src.task2.labels import LABELS
from src.task2.prompts import LABEL_GUIDE, exam_text, submission_text

FINAL_MARKER = "KẾT LUẬN:"

SYSTEM_COT = (
    "Bạn là giảng viên môn Lập trình C++ nhập môn, đang chấm bài nộp của sinh viên. "
    "Nhiệm vụ: xác định các loại lỗi CHÍNH của bài (lỗi mà giảng viên sẽ trừ điểm), theo đúng danh sách nhãn bên "
    "dưới. Một bài có thể có 0, 1 hoặc nhiều lỗi. Bài đúng hoàn toàn thì trả về danh sách rỗng.\n\n"
    "DANH SÁCH NHÃN (chỉ dùng đúng tên này):\n" + LABEL_GUIDE + "\n\n"
    "NGUYÊN TẮC CHẤM:\n"
    "- Chỉ gán nhãn khi chỉ ra được dòng code cụ thể gây lỗi. Không đoán, không suy diễn lỗi không có trong code.\n"
    '- Nếu compile_log có "error" thì chắc chắn có "Lỗi biên dịch". Cảnh báo (warning) và lỗi liên kết thiếu hàm '
    'main ("undefined reference to `main\'") thì không tính; compile_log rỗng nghĩa là biên dịch được.\n'
    '- Lỗi mà compile_log đã báo (biến/hàm chưa khai báo, sai cú pháp, khai báo trùng...) chỉ thuộc "Lỗi biên dịch"; '
    "không gán thêm nhãn khác cho chính lỗi đó.\n"
    "- Bỏ qua mọi code nằm trong comment (// hoặc /* */): không chấm và không tính là lỗi.\n"
    '- Bám sát mục "YÊU CẦU CỦA ĐỀ": làm khác yêu cầu (ví dụ đề bắt dùng đệ quy, BST, làm in-place mà bài làm '
    'khác) là "Lỗi thuật toán"; dùng thư viện hoặc hàm bị đề cấm là "Lỗi style".\n'
    '- "Lỗi hàm" là khi bài thiếu hàm mà đề yêu cầu, khai báo khác prototype đề cho, hoặc định nghĩa/gọi hàm sai '
    "(thiếu return, truyền tham trị khi phải sửa dữ liệu). Sai bên trong thân hàm (công thức, điều kiện, vòng lặp) "
    'là "Lỗi logic" hoặc "Lỗi vòng lặp", không phải "Lỗi hàm".\n'
    "- Đề có câu điều kiện (ví dụ P1 đọc file sai thì không chấm các câu sau): nếu câu điều kiện sai thì chỉ ghi lỗi "
    "của câu đó, không ghi lỗi của các câu phụ thuộc.\n"
    "- Không ghi nhận xét chung không có bằng chứng (đặt tên, thiếu comment, có thể tối ưu hơn) thành lỗi."
)

STEPS = (
    ("Biên dịch", "compile_log có lỗi (error) không? Lỗi nào đã được compiler báo thì chỉ tính ở mục này."),
    ("Nhập/xuất", "đọc dữ liệu (stdin hoặc file) và định dạng in ra có khớp đề không?"),
    ("Vòng lặp và mảng/chuỗi", "chỉ số, điều kiện dừng, kích thước có đúng không? Có vòng lặp vô hạn không?"),
    ("Hàm", 'với MỖI hàm trong mục "YÊU CẦU CỦA ĐỀ", chép dòng khai báo tương ứng trong bài (kèm số dòng) và ghi '
            '"khớp", "khác ở ..." hoặc "không có trong bài". Đề không quy định hàm thì xét các hàm bài tự viết có '
            "định nghĩa/gọi sai không."),
    ("Logic, edge case, hard-code", "có nhánh/công thức sai, bỏ sót trường hợp biên, hoặc gán cứng giá trị/tên "
                                    "file/số lượng thay vì tính tổng quát không?"),
    ("Thuật toán", "cách làm và cấu trúc dữ liệu có đúng yêu cầu đề không?"),
    ("Style", "có dùng thư viện/hàm bị cấm, code lặp nặng, lạm dụng biến toàn cục không?"),
    ("Rà lại", "với mỗi nhãn định ghi, nêu 1 dòng code làm bằng chứng. Bỏ nhãn nếu: lỗi đã có trong compile_log mà "
               'nhãn không phải "Lỗi biên dịch"; chỉ là nhận xét chung không có dòng cụ thể; dòng đó đã được tính '
               "cho nhãn khác; hoặc lỗi nằm ở câu phụ thuộc khi câu điều kiện đã sai."),
)


def cot_instruction() -> str:
    """Asks for every step BEFORE the conclusion line, as a fill-in template: Qwen2.5-Coder answered with the
    conclusion line only when the instruction just said "finally write exactly one line"."""
    k = len(STEPS)
    steps = "\n".join(f"{i}. {name}: {q}" for i, (name, q) in enumerate(STEPS, 1))
    template = "\n".join(f"{i}. {name}: <nhận xét, dẫn số dòng hoặc đoạn code làm bằng chứng>"
                          for i, (name, _) in enumerate(STEPS, 1))
    return (f"## CÁCH CHẤM\nChấm lần lượt {k} bước sau:\n"
            f"{steps}\n\n"
            "## ĐỊNH DẠNG TRẢ LỜI (bắt buộc)\n"
            f"Viết đủ {k} mục theo đúng khung dưới đây, mỗi mục 1-3 câu, rồi mới đến dòng KẾT LUẬN ở cuối cùng. "
            f"Không được bỏ mục nào và không được viết KẾT LUẬN trước khi xong {k} mục.\n\n"
            f"{template}\n"
            f'{FINAL_MARKER} {{"taxonomy_error": ["<nhãn>", ...]}}\n\n'
            "Trong dòng KẾT LUẬN chỉ được dùng các nhãn sau, viết nguyên văn (kể cả chữ \"Lỗi\"), không dùng tên "
            f"mục chấm: {json.dumps(list(LABELS), ensure_ascii=False)}. Chỉ ghi các nhãn còn lại sau bước Rà lại; "
            "[] nếu bài không có lỗi.")


_LIB_SENTENCE = re.compile(r"[^\n]*(?:thư viện|librar)[^\n]*", re.I)
_NOT_USE = r"(?:không được dùng|không được sử dụng|không dùng|do not use|don't use)[\s*_]*(?:hàm|function)?[\s*_]*"
_BANNED_TICK = re.compile(_NOT_USE + r"`([A-Za-z_]\w*)`", re.I)        # statement: only a `name` in backticks
_BANNED_BARE = re.compile(_NOT_USE + r"`?([A-Za-z_]\w*)`?", re.I)       # constraints field: short, structured
_PARAM = re.compile(r"\bstring\s*&?\s*([A-Za-z_]\w*)")


def allowed_libraries(statement: str) -> list[str]:
    """Libraries from a sentence like "Chỉ được dùng các thư viện: `a, b`" / "only `a, b,` and `c` library is
    allowed"; [] when no such sentence (the line is then left out of the prompt rather than guessed)."""
    sentences = [x for line in _LIB_SENTENCE.findall(statement or "") for x in re.split(r"(?<=[.!?])\s+", line)]
    for sent in sentences:
        if not re.search(r"thư viện|librar", sent, re.I):
            continue
        if not re.search(r"chỉ|only", sent, re.I):
            continue
        libs = [x.strip() for chunk in re.findall(r"`([^`]+)`", sent) for x in chunk.split(",")]
        libs = [x for x in libs if re.fullmatch(r"[A-Za-z_][\w./]*", x)]
        if libs:
            return libs
    return []


def banned_functions(exam: dict) -> list[str]:
    """Functions the exam forbids: `name` in backticks after "không được dùng / do not use" in the statement (prose
    like "không dùng thêm mảng" is not a function), or any name after it in a problem's constraints field."""
    found = []
    for name in _BANNED_TICK.findall(exam.get("statement") or ""):
        found.append(name)
    for p in exam.get("problems") or []:
        for name in _BANNED_BARE.findall(str(p.get("constraints") or "")):
            if re.fullmatch(r"[a-z_]\w*", name) and name not in {"thêm", "các", "mảng", "the", "any", "extra"}:
                found.append(name)
    return list(dict.fromkeys(found))


def exam_requirements(exam: dict) -> str:
    """Checklist built only from structured exam fields (exams.json) and two narrow statement patterns; every line
    is optional, nothing is specific to one exam, so an unseen (private) exam gets the lines its fields support."""
    problems = exam.get("problems") or []
    lines = []
    multi = exam.get("exam_type") == "multi_problem"
    no_main = "không có main" in (exam.get("note") or "").lower() or multi
    if no_main:
        lines.append("Dạng đề: nhiều câu; bài nộp chỉ gồm các hàm, KHÔNG có main là đúng. Không chấm việc hàm có "
                     "được gọi hay không.")
    elif any(p.get("io_mode") == "stdin/stdout" for p in problems):
        lines.append("Dạng đề: một chương trình hoàn chỉnh, đọc từ bàn phím (stdin) và in ra màn hình (stdout).")
    protos = [p for p in problems if p.get("prototype")]
    if protos:
        lines.append("Hàm bắt buộc (không được đổi prototype; hàm chưa làm vẫn phải có, để thân rỗng):")
        for p in protos:
            dep = f" (điều kiện để chấm {', '.join(p['is_prerequisite_for'])})" if p.get("is_prerequisite_for") else ""
            lines.append(f"  - {p['pid']}: `{p['prototype'].strip()}`{dep}")
    if exam.get("grading_policy"):
        lines.append(f"Chính sách chấm: {exam['grading_policy'].strip()}")
    cons = [str(p["constraints"]).strip() for p in problems if p.get("constraints")]
    if cons:
        lines.append("Ràng buộc: " + " | ".join(cons))
    libs = allowed_libraries(exam.get("statement") or "")
    if libs:
        lines.append("Thư viện được phép: " + ", ".join(libs) + ". Dùng thư viện khác là vi phạm.")
    banned = banned_functions(exam)
    if banned:
        lines.append("Hàm bị cấm: " + ", ".join(f"`{b}`" for b in banned) + ".")
    params = [m for p in protos for m in _PARAM.findall(p["prototype"]) if "file" in m.lower()]
    if exam.get("data_file") or params:  # a file-reading exam: data_file given, or a prototype takes a file name
        via = f"tham số `{params[0]}`" if params else "tham số nhận tên file"
        sample = f"đề cung cấp file mẫu `{exam['data_file']}`. " if exam.get("data_file") else ""
        lines.append(f"File dữ liệu: {sample}Bài phải mở file qua {via} và đọc số bản ghi thực tế; ghi cứng tên "
                     "file hoặc số bản ghi là \"Lỗi hard-code\".")
    if not lines:
        return ""
    return "## YÊU CẦU CỦA ĐỀ (tóm tắt từ đề, dùng để đối chiếu)\n" + "\n".join(
        x if x.startswith("  - ") else f"- {x}" for x in lines) + "\n"


ALL_COMMENTED = "// (toàn bộ code của bài nằm trong comment)"


def strip_comments(code: str) -> str:
    """Code with every // and /* */ comment removed; newlines are kept, so line numbers stay those of the
    submission. Lines left blank become empty. String and char literals are not touched."""
    out, last = [], 0
    for a, b in _comment_spans(code):
        out.append(code[last:a])
        out.append("\n" * code.count("\n", a, b))  # a block comment spanning lines keeps its line breaks
        last = b
    out.append(code[last:])
    stripped = "\n".join(line.rstrip() for line in "".join(out).split("\n"))
    return stripped if stripped.strip() or not code.strip() else ALL_COMMENTED


def _view(sample, cfg: dict):
    """The sample as the model sees it: comments stripped when prompt.strip_comments is on."""
    if not cfg.get("strip_comments"):
        return sample
    return dataclasses.replace(sample, code=strip_comments(sample.code))


def demos_text(demos: list, cfg: dict) -> str:
    """Graded examples (other submissions, possibly other exams): code + compile status + conclusion line only."""
    if not demos:
        return ""
    from src.task2.cot_demos import compile_status
    lim = int(cfg.get("demo_max_code_chars", 1800))
    parts = ["## VÍ DỤ BÀI ĐÃ ĐƯỢC GIẢNG VIÊN CHẤM (bài khác, chỉ để tham khảo cách gán nhãn: giảng viên chỉ ghi "
             "những lỗi rõ ràng, có bằng chứng trong code)"]
    for i, d in enumerate(demos, 1):
        smp = _view(d.sample, cfg)
        code = smp.code if len(smp.code) <= lim else smp.code[:lim] + "\n// ...(cắt bớt)"
        parts.append(f"### Ví dụ {i} (đề {smp.exam_id})\n```cpp\n{code}\n```\n"
                     f"compile_log: {compile_status(smp.compile_log)}\n"
                     f'{FINAL_MARKER} {json.dumps({"taxonomy_error": list(smp.labels)}, ensure_ascii=False)}\n')
    return "\n".join(parts) + "\n"


def build_cot_messages(exam: dict, sample, cfg: dict, demos=()) -> list[dict]:
    user = "\n".join(x for x in [exam_text(exam), exam_requirements(exam), demos_text(list(demos), cfg),
                                  submission_text(_view(sample, cfg), cfg), cot_instruction()] if x)
    return [{"role": "system", "content": SYSTEM_COT}, {"role": "user", "content": user}]
