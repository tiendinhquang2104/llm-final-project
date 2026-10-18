"""Task 2 prompting: zero-shot chain-of-thought with a teacher persona (docs/task2_prompting.md).
Pure functions of (exam, sample, cfg); never use `feedback`.

`prompt.lang` picks the language of OUR text (persona, rules, steps, requirement lines): "vi" (default) or "en".
Both carry the same rules. Exam statements, exams.json values and student code are data and stay as they are; the
labels in the conclusion line are always the official Vietnamese names."""
from __future__ import annotations

import dataclasses
import json
import re

from src.task2.augment import _comment_spans
from src.task2.labels import LABELS
from src.task1.prompts import clean_compile_log, format_test_report
from src.task2.prompts import exam_text, submission_text

FINAL_MARKER = "KẾT LUẬN:"
FINAL_MARKER_EN = "CONCLUSION:"
FINAL_MARKERS = (FINAL_MARKER, FINAL_MARKER_EN)
LANGS = ("vi", "en")


def prompt_lang(cfg: dict | None) -> str:
    lang = str((cfg or {}).get("lang") or "vi")
    if lang not in LANGS:
        raise ValueError(f"prompt.lang must be one of {LANGS}, got {lang!r}")
    return lang


def split_final(text: str) -> tuple[str, str | None]:
    """(reasoning, text after the last conclusion marker of either language); tail None when there is none."""
    text = text or ""
    pos, marker = max((text.rfind(m), m) for m in FINAL_MARKERS)
    if pos < 0:
        return text, None
    return text[:pos], text[pos + len(marker):]

ALL_COMMENTED = "// (toàn bộ code của bài nằm trong comment)"

# How the instructor uses each label, read off the 32 gold samples (labels + rubric + feedback, never fed to the
# model): docs/task2_teacher_rules.md. CoT-only; DESCRIPTIONS in labels.py stays the shared generic definition.
TEACHER_GUIDE: dict[str, str] = {
    "Lỗi biên dịch": 'compile_log có "error". Cảnh báo (warning), thiếu hàm main ("undefined reference to `main\'"), '
                     "void main và compile_log rỗng thì KHÔNG tính.",
    "Lỗi nhập/xuất": "output sai định dạng so với đề: sai hoa thường (in TRUE/FALSE khi đề yêu cầu True/False), thừa "
                     "hoặc thiếu dấu cách, sai chuỗi in ra. Câu nhắc nhập (ví dụ \"Nhap n: \") KHÔNG bị tính là lỗi.",
    "Lỗi logic": "điều kiện, công thức hoặc luồng xử lý sai làm kết quả sai; giả định sai về dữ liệu (coi số dòng n là "
                 "cho trước thay vì tự đếm); chương trình bỏ dở, chưa hoàn thiện; xoá/chèn node sai.",
    "Lỗi vòng lặp": "vòng lặp vô hạn (quên cur = cur->next, quên tăng biến chạy); sai chỉ số đầu/cuối làm bỏ sót "
                    "phần tử; vòng lặp tính toán ra sai (cộng dồn sai, khởi tạo lại biến trong vòng lặp).",
    "Lỗi mảng/chuỗi": "xử lý mảng/chuỗi sai: trả về mảng cục bộ của hàm, truy cập ngoài mảng, cắt/tách chuỗi sai.",
    "Lỗi hàm": "GỌI hoặc DÙNG hàm sai, kể cả hàm thư viện: stoi/stof trên chuỗi không phải số (dòng tiêu đề, ô rỗng) "
               "làm chương trình lỗi; gọi hàm mà không truyền đối số (if (isPrime) thay vì isPrime(n)); hàm phụ tự viết "
               "(tính mũ, tính tích...) trả về kết quả sai. Hàm/câu CHƯA LÀM không phải Lỗi hàm.",
    "Lỗi edge case": "rất hiếm, giảng viên gần như không dùng. Chỉ gán khi bài đúng với dữ liệu thường nhưng sai rõ "
                     "ràng ở một trường hợp biên mà đề nhắc tới.",
    "Lỗi thuật toán": "cách tính cốt lõi của đề sai (ví dụ tính tuổi sai với năm trước Công nguyên), cấu trúc dữ liệu "
                      "tạo ra sai (danh sách liên kết rỗng), hoặc làm khác phương pháp đề bắt buộc (đệ quy, BST, "
                      "in-place).",
    "Lỗi hard-code": "ghi cứng giá trị lẽ ra phải đọc/tính: tên file viết cứng (kể cả chuỗi \"filename\" thay vì "
                     "dùng tham số), kích thước mảng hoặc số bản ghi cố định khi đọc file, #include file dữ liệu.",
    "Lỗi style": "nộp bài mà toàn bộ code nằm trong comment; hàm phức tạp không cần thiết; dùng thư viện/hàm bị đề cấm.",
}
TEACHER_LABEL_GUIDE = "\n".join(f"- {lab}: {TEACHER_GUIDE[lab]}" for lab in LABELS)

SYSTEM_COT = (
    "Bạn là giảng viên môn Lập trình C++ nhập môn, đang chấm bài nộp của sinh viên. "
    "Nhiệm vụ: xác định các loại lỗi CHÍNH của bài (lỗi làm bài bị trừ điểm), theo đúng danh sách nhãn bên dưới.\n\n"
    "DANH SÁCH NHÃN (chỉ dùng đúng tên này; mô tả là cách giảng viên dùng nhãn):\n" + TEACHER_LABEL_GUIDE + "\n\n"
    "NGUYÊN TẮC CHẤM:\n"
    "- Chỉ ghi lỗi CHÍNH làm mất điểm: thường 1-2 nhãn, tối đa 3. Bài làm đúng yêu cầu thì [] (kết quả phổ biến).\n"
    "- Mỗi nhãn phải chỉ ra được dòng code gây lỗi; không đoán. Nhận xét chung (đặt tên, thiếu comment, có thể "
    "tối ưu hơn) không phải lỗi.\n"
    "- Câu/hàm CHƯA LÀM (không có, thân rỗng, chỉ return mặc định): không chấm, không gán nhãn. Riêng khi CẢ BÀI "
    'chưa làm hoặc bỏ dở thì ghi "Lỗi logic".\n'
    "- Câu tiên quyết (thường P1 đọc file) sai thì CHỈ ghi lỗi của câu đó, các câu sau không chấm.\n"
    '- Có "Lỗi biên dịch" thì thêm TỐI ĐA 1 nhãn cho nguyên nhân khi rõ ràng (biến chạy của for chưa khai báo: '
    '"Lỗi vòng lặp"; #include file dữ liệu: "Lỗi hard-code"; code bỏ dở: "Lỗi logic").\n'
    '- Vòng lặp vô hạn: ghi cả "Lỗi vòng lặp" và "Lỗi logic".\n'
    f'- Code trong comment không chấm; bài chỉ còn dòng "{ALL_COMMENTED}" thì kết luận ["Lỗi style"].\n'
    '- Đối chiếu mục "YÊU CẦU CỦA ĐỀ" (phương pháp bắt buộc, thư viện/hàm bị cấm, file dữ liệu).'
)

STEPS = (
    ("Biên dịch", "compile_log có error không? Nguyên nhân có rõ ràng thuộc nhãn khác không?"),
    ("Phạm vi chấm", "từng câu/hàm đề yêu cầu: \"đã làm\" hay \"chưa làm\"; câu tiên quyết (nếu có) đúng chưa. Đề một "
                     "câu thì ghi \"chấm toàn bài\"."),
    ("Nhập/xuất", "đọc dữ liệu và chuỗi in ra có khớp đề không?"),
    ("Vòng lặp và mảng/chuỗi", "chỉ số, điều kiện dừng, vòng lặp vô hạn, truy cập mảng/chuỗi có đúng không?"),
    ("Hàm", "có gọi/dùng hàm sai, hoặc khai báo khác prototype đề cho không?"),
    ("Logic và hard-code", "điều kiện/công thức, giả định về dữ liệu, giá trị ghi cứng?"),
    ("Thuật toán", "cách tính cốt lõi và cấu trúc dữ liệu có đúng yêu cầu đề không?"),
    ("Style", "bài toàn comment, thư viện/hàm bị cấm, hàm phức tạp không cần thiết?"),
    ("Rà lại", "giữ 1-2 lỗi chính (tối đa 3), mỗi nhãn 1 dòng code làm bằng chứng; bỏ nhãn trái NGUYÊN TẮC CHẤM, "
               "trùng dòng với nhãn khác, hoặc \"Lỗi edge case\" không thật rõ."),
)


def _cot_instruction_vi() -> str:
    k = len(STEPS)
    steps = "\n".join(f"{i}. {name}: {q}" for i, (name, q) in enumerate(STEPS, 1))
    template = "\n".join(f"{i}. {name}: <...>" for i, (name, _) in enumerate(STEPS, 1))
    return (f"## CÁCH CHẤM\nChấm lần lượt {k} bước sau:\n"
            f"{steps}\n\n"
            "## ĐỊNH DẠNG TRẢ LỜI (bắt buộc)\n"
            f"Viết đủ {k} mục theo khung dưới đây, mỗi mục 1-3 câu dẫn số dòng làm bằng chứng, rồi mới đến dòng "
            f"KẾT LUẬN ở cuối cùng (không bỏ mục nào, không viết KẾT LUẬN sớm).\n\n"
            f"{template}\n"
            f'{FINAL_MARKER} {{"taxonomy_error": ["<nhãn>", ...]}}\n\n'
            "KẾT LUẬN chỉ chứa nhãn còn lại sau bước Rà lại, viết nguyên văn tên nhãn trong DANH SÁCH NHÃN (kể cả "
            "chữ \"Lỗi\", không dùng tên mục chấm); [] nếu bài không có lỗi.")


# English version of the same rules (prompt.lang: en). Label names stay the official Vietnamese strings; the gloss in
# brackets is only a reading aid.
TEACHER_GUIDE_EN: dict[str, str] = {
    "Lỗi biên dịch": '(compile error) compile_log contains "error". Warnings, a missing main ("undefined reference '
                     "to `main'\"), void main and an empty compile_log do NOT count.",
    "Lỗi nhập/xuất": "(input/output) printed output does not match the format in the statement: wrong letter case "
                     "(prints TRUE/FALSE where the statement says True/False), extra or missing spaces, wrong printed "
                     'text. Input prompts such as "Nhap n: " are NOT an error.',
    "Lỗi logic": "(logic) wrong condition, formula or control flow giving wrong results; a wrong assumption about the "
                 "data (taking the number of lines n as given instead of counting it); an unfinished program; "
                 "deleting/inserting nodes wrongly.",
    "Lỗi vòng lặp": "(loop) infinite loop (forgot cur = cur->next, forgot to increment the counter); wrong start/end "
                    "index that skips elements; a loop that computes wrongly (wrong accumulation, a variable "
                    "re-initialised inside the loop).",
    "Lỗi mảng/chuỗi": "(array/string) wrong array or string handling: returning a function's local array, "
                      "out-of-bounds access, wrong splitting/slicing of strings.",
    "Lỗi hàm": "(function misuse) CALLING or USING a function wrongly, library functions included: stoi/stof on a "
               "non-numeric string (header line, empty field) that makes the program fail; calling a function "
               "without its arguments (if (isPrime) instead of isPrime(n)); a self-written helper (power, product...) "
               "that returns wrong results. A function/question NOT ATTEMPTED is not Lỗi hàm.",
    "Lỗi edge case": "(edge case) very rare, the lecturer almost never uses it. Only when the program is right on "
                     "normal data but clearly wrong on a boundary case the statement mentions.",
    "Lỗi thuật toán": "(algorithm) the core computation of the problem is wrong (e.g. age computed wrongly for years "
                      "BC), the data structure built is wrong (an empty linked list), or the method the statement "
                      "requires (recursion, BST, in-place) is not used.",
    "Lỗi hard-code": "(hard-coding) a value that should be read or computed is fixed in the code: a hard-coded file "
                     'name (including the literal string "filename" instead of the parameter), a fixed array size or '
                     "record count when reading the file, #include of the data file.",
    "Lỗi style": "(style) the whole submission is commented out; a needlessly complex function; a library/function "
                 "the statement forbids is used.",
}
TEACHER_LABEL_GUIDE_EN = "\n".join(f'- "{lab}" {TEACHER_GUIDE_EN[lab]}' for lab in LABELS)

SYSTEM_COT_EN = (
    "You are the lecturer of an introductory C++ programming course, grading a student's submission. "
    "Task: identify the MAIN error types of the submission (errors that cost points), using exactly the labels "
    "below. The exam statement and the code may be in Vietnamese; write your grading in English.\n\n"
    "LABELS (copy the label names exactly, in Vietnamese; each description says how the lecturer uses the label):\n"
    + TEACHER_LABEL_GUIDE_EN + "\n\n"
    "GRADING RULES:\n"
    "- Report only the MAIN errors that cost points: usually 1-2 labels, at most 3. A submission that does what is "
    "asked gets [] (a common outcome).\n"
    "- Every label must point to the line of code that causes it; do not guess. General remarks (naming, missing "
    "comments, could be faster) are not errors.\n"
    "- A question/function NOT ATTEMPTED (missing, empty body, only a default return): not graded, no label. Only "
    'when the WHOLE submission is unattempted or abandoned assign "Lỗi logic".\n'
    "- If a prerequisite question (usually P1, reading the file) is wrong, report ONLY its errors; later questions "
    "are not graded.\n"
    '- With "Lỗi biên dịch", add AT MOST 1 label for its cause when clear (loop variable of a for not declared: '
    '"Lỗi vòng lặp"; #include of the data file: "Lỗi hard-code"; abandoned code: "Lỗi logic").\n'
    '- An infinite loop gets both "Lỗi vòng lặp" and "Lỗi logic".\n'
    f'- Code inside comments is not graded; a submission that is only the line "{ALL_COMMENTED}" (whole code '
    'commented out) gets ["Lỗi style"].\n'
    '- Check against "EXAM REQUIREMENTS" (required method, forbidden libraries/functions, data file).'
)

STEPS_EN = (
    ("Compilation", "does compile_log contain an error? Is its cause clearly another label?"),
    ("Scope", 'each question/function the exam requires: "attempted" or "not attempted"; is the prerequisite '
              '(if any) right? Single-question exam: write "grade the whole program".'),
    ("Input/output", "are the data read and the printed text what the statement asks for?"),
    ("Loops and arrays/strings", "are indices, stop conditions, infinite loops, array/string access right?"),
    ("Functions", "is a function called/used wrongly, or declared differently from the required prototype?"),
    ("Logic and hard-code", "conditions/formulas, assumptions about the data, hard-coded values?"),
    ("Algorithm", "are the core computation and the data structure what the statement asks for?"),
    ("Style", "whole code commented out, forbidden library/function, needlessly complex function?"),
    ("Review", "keep the 1-2 main errors (at most 3), each with 1 line of code as evidence; drop labels that break "
               'the GRADING RULES, reuse a line already counted, or are an unclear "Lỗi edge case".'),
)


def _cot_instruction_en() -> str:
    k = len(STEPS_EN)
    steps = "\n".join(f"{i}. {name}: {q}" for i, (name, q) in enumerate(STEPS_EN, 1))
    template = "\n".join(f"{i}. {name}: <...>" for i, (name, _) in enumerate(STEPS_EN, 1))
    return (f"## HOW TO GRADE\nGo through these {k} steps in order:\n"
            f"{steps}\n\n"
            "## ANSWER FORMAT (mandatory)\n"
            f"Write all {k} items in English with the template below, 1-3 sentences each citing line numbers as "
            "evidence, and only then the CONCLUSION line at the very end (skip no item, no early CONCLUSION).\n\n"
            f"{template}\n"
            f'{FINAL_MARKER_EN} {{"taxonomy_error": ["<label>", ...]}}\n\n'
            "CONCLUSION holds only the labels left after Review, copied exactly from LABELS (Vietnamese, including "
            "\"Lỗi\"; never step names or English glosses); [] if the submission has no error.")


def system_prompt(lang: str = "vi") -> str:
    return SYSTEM_COT_EN if lang == "en" else SYSTEM_COT


def cot_instruction(lang: str = "vi") -> str:
    """Asks for every step BEFORE the conclusion line, as a fill-in template: Qwen2.5-Coder answered with the
    conclusion line only when the instruction just said "finally write exactly one line"."""
    return _cot_instruction_en() if lang == "en" else _cot_instruction_vi()


_PARAM = re.compile(r"\bstring\s*&?\s*([A-Za-z_]\w*)")
_FUNC_NAME = re.compile(r"([A-Za-z_]\w*)\s*\(")


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _proto_line(p: dict, statement: str, dep: str) -> str:
    """Full prototype, or only the function name when the statement already quotes the prototype verbatim
    (the requirements block adds what the statement does not say: which question is a prerequisite)."""
    proto = p["prototype"].strip()
    name = _FUNC_NAME.search(proto)
    if name and _squash(proto).rstrip(";") in _squash(statement):
        return f"  - {p['pid']}: `{name.group(1)}(...)`{dep}"
    return f"  - {p['pid']}: `{proto}`{dep}"


_REQ = {
    "vi": {
        "head": "## YÊU CẦU CỦA ĐỀ (tóm tắt từ đề, dùng để đối chiếu)",
        "multi": "Dạng đề: nhiều câu; bài nộp chỉ gồm các hàm, KHÔNG có main là đúng. Không chấm việc hàm có được gọi "
                 "hay không.",
        "stdio": "Dạng đề: một chương trình hoàn chỉnh, đọc từ bàn phím (stdin) và in ra màn hình (stdout).",
        "lang": "Chuẩn ngôn ngữ: {lang}.",
        "topic": "(chủ đề: {topic})",
        "focus": "Trọng tâm đề: {what} Chỉ để hiểu đề kiểm tra kỹ năng gì; nhãn vẫn gán theo dòng code gây sai, không "
                 "theo chủ đề.",
        "hidden": "Đề được chấm bằng test ẩn: output phải khớp CHÍNH XÁC định dạng trong đề (hoa thường, dấu cách, "
                  "xuống dòng); bài chỉ đúng với ví dụ mẫu mà sai với dữ liệu khác vẫn bị trừ điểm.",
        "protos": "Hàm bắt buộc (không được đổi prototype; hàm chưa làm vẫn phải có, để thân rỗng):",
        "dep": " (điều kiện để chấm {deps})",
        "policy": "Chính sách chấm: {policy}",
        "cons": "Ràng buộc: {cons}",
        "via_param": "tham số `{param}`", "via_any": "tham số nhận tên file",
        "sample_file": "đề cung cấp file mẫu `{file}`. ",
        "file": "File dữ liệu: {sample}Bài phải mở file qua {via} và đọc số bản ghi thực tế; ghi cứng tên file hoặc "
                "số bản ghi là \"Lỗi hard-code\".",
    },
    "en": {
        "head": "## EXAM REQUIREMENTS (summary of the exam, to check against)",
        "multi": "Exam type: several questions; the submission contains only the functions, and having NO main is "
                 "correct. Do not grade whether the functions are called.",
        "stdio": "Exam type: one complete program, reading from the keyboard (stdin) and printing to the screen "
                 "(stdout).",
        "lang": "Language standard: {lang}.",
        "topic": "(topic: {topic})",
        "focus": "Focus of the exam: {what} Only to understand which skill the exam tests; labels still follow the "
                 "line of code that causes the error, not the topic.",
        "hidden": "Graded with hidden tests: the output must match the format in the statement EXACTLY (letter case, "
                  "spaces, line breaks); a program that is only right on the sample examples still loses points.",
        "protos": "Required functions (the prototype must not change; an unattempted function is still present, "
                  "with an empty body):",
        "dep": " (prerequisite for grading {deps})",
        "policy": "Grading policy: {policy}",
        "cons": "Constraints: {cons}",
        "via_param": "the parameter `{param}`", "via_any": "the file-name parameter",
        "sample_file": "the exam provides the sample file `{file}`. ",
        "file": "Data file: {sample}The program must open the file through {via} and read the actual number of "
                "records; a hard-coded file name or record count is \"Lỗi hard-code\".",
    },
}


def exam_requirements(exam: dict, lang: str = "vi") -> str:
    """Checklist built only from structured exam fields (exams.json); every line is optional, nothing is specific
    to one exam, so an unseen (private) exam gets the lines its fields support. Field values (grading_policy,
    constraints, learning_outcome...) are quoted as they are, in any language. What the statement already says
    (allowed libraries, forbidden functions, prototypes quoted verbatim) is not repeated."""
    t = _REQ[lang]
    problems = exam.get("problems") or []
    lines = []
    multi = exam.get("exam_type") == "multi_problem"
    no_main = "không có main" in (exam.get("note") or "").lower() or multi
    if no_main:
        lines.append(t["multi"])
    elif any(p.get("io_mode") == "stdin/stdout" for p in problems):
        lines.append(t["stdio"])
    language = str(exam.get("language") or "")
    if language:
        lines.append(t["lang"].format(
            lang=f"C++{language[3:]}" if re.fullmatch(r"cpp\d+", language) else language))
    if exam.get("learning_outcome") or exam.get("topic"):
        topic = exam.get("topic")
        topic = ", ".join(topic) if isinstance(topic, list) else str(topic or "")
        what = " ".join(x for x in [str(exam.get("learning_outcome") or "").strip(),
                                    t["topic"].format(topic=topic) if topic else ""] if x)
        lines.append(t["focus"].format(what=what))
    if exam.get("has_hidden_testcases") is True:
        lines.append(t["hidden"])
    protos = [p for p in problems if p.get("prototype")]
    if protos:
        lines.append(t["protos"])
        for p in protos:
            dep = t["dep"].format(deps=", ".join(p["is_prerequisite_for"])) if p.get("is_prerequisite_for") else ""
            lines.append(_proto_line(p, exam.get("statement") or "", dep))
    if exam.get("grading_policy"):
        lines.append(t["policy"].format(policy=exam["grading_policy"].strip()))
    cons = [str(p["constraints"]).strip() for p in problems if p.get("constraints")]
    if cons:
        lines.append(t["cons"].format(cons=" | ".join(cons)))
    params = [m for p in protos for m in _PARAM.findall(p["prototype"]) if "file" in m.lower()]
    if exam.get("data_file") or params:  # a file-reading exam: data_file given, or a prototype takes a file name
        via = t["via_param"].format(param=params[0]) if params else t["via_any"]
        sample = t["sample_file"].format(file=exam["data_file"]) if exam.get("data_file") else ""
        lines.append(t["file"].format(sample=sample, via=via))
    if not lines:
        return ""
    return t["head"] + "\n" + "\n".join(x if x.startswith("  - ") else f"- {x}" for x in lines) + "\n"


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


_TEXT = {
    "vi": {"demos": "## VÍ DỤ BÀI ĐÃ ĐƯỢC GIẢNG VIÊN CHẤM (bài khác, chỉ để tham khảo cách gán nhãn: giảng viên chỉ "
                    "ghi những lỗi rõ ràng, có bằng chứng trong code)",
           "demo": "### Ví dụ {i} (đề {exam})", "cut": "// ...(cắt bớt)", "marker": FINAL_MARKER},
    "en": {"demos": "## SUBMISSIONS ALREADY GRADED BY THE LECTURER (other submissions, only to show how labels are "
                    "assigned: the lecturer reports only clear errors with evidence in the code)",
           "demo": "### Example {i} (exam {exam})", "cut": "// ...(truncated)", "marker": FINAL_MARKER_EN},
}
_COMPILE_STATUS_EN = {"không có compile_log": "no compile_log",
                      "chỉ có cảnh báo (warning), không có lỗi": "warnings only, no error",
                      "sạch (không lỗi, không cảnh báo)": "clean (no error, no warning)"}


def _compile_status(log, lang: str) -> str:
    from src.task2.cot_demos import compile_status
    st = compile_status(log)
    if lang != "en":
        return st
    if st.startswith("có lỗi biên dịch"):
        return "compile error" + st[len("có lỗi biên dịch"):]
    return _COMPILE_STATUS_EN.get(st, st)


def exam_text_lang(exam: dict, lang: str = "vi") -> str:
    if lang != "en":
        return exam_text(exam)
    return (f"## EXAM ({exam['exam_id']}, type {exam['exam_type']}, course {exam.get('course', '')})\n"
            f"{exam.get('statement', '').strip()}\n")


_DIAG_ERROR = re.compile(r"^\S+:\d+:\d+: (?:fatal )?error:")
_DIAG_SOURCE = re.compile(r"^\s*\d*\s*\|")  # gcc's "   28 |     code" and "      |     ^~~~" lines
_LOG_TEXT = {"vi": {"none": "(không có)", "empty": "(rỗng — không có lỗi hay cảnh báo)", "cut": "...(cắt bớt)",
                    "more": "...(còn {n} lỗi khác)", "sub": "## BÀI NỘP CẦN PHÂN LOẠI"},
             "en": {"none": "(none)", "empty": "(empty — no error, no warning)", "cut": "...(truncated)",
                    "more": "...({n} more errors)", "sub": "## SUBMISSION TO GRADE"}}


def compact_compile_log(log: str | None, max_chars: int = 800, lang: str = "vi") -> str:
    """compile_log for the prompt: the error diagnostics only, each with its source line and caret, first errors
    first, until max_chars; notes, include chains and warnings are dropped (a template error in getline() alone
    is ~50 kB of candidate notes). A log without errors is cut to max_chars. "Lỗi biên dịch" comes from the full
    log (prompt.compile_rule), so the cut never removes that label."""
    t = _LOG_TEXT[lang]
    if log is None:
        return t["none"]
    log = re.sub(r"/tmp/tmp\w+/", "", log).strip()
    if not log:
        return t["empty"]
    blocks, cur = [], None
    for line in log.splitlines():
        if _DIAG_ERROR.match(line):
            cur = [line]
            blocks.append(cur)
        elif cur is not None and _DIAG_SOURCE.match(line):
            cur.append(line)
        else:
            cur = None
    if not blocks:
        return log if len(log) <= max_chars else log[:max_chars] + "\n" + t["cut"]
    kept, used = [], 0
    for b in blocks:
        text = "\n".join(b)
        if kept and used + len(text) > max_chars:
            break
        kept.append(text)
        used += len(text) + 1
    if len(kept) < len(blocks):
        kept.append(t["more"].format(n=len(blocks) - len(kept)))
    return "\n".join(kept)


def numbered_code(code: str, max_chars: int = 12000, drop_blank: bool = False, cut: str = "// ...(cắt bớt)") -> str:
    """Code with its line numbers; `drop_blank` leaves out empty lines (comment-only lines become empty after
    strip_comments) but keeps the original numbers, so evidence like "line 28" still points at the submission."""
    if len(code) > max_chars:
        code = code[:max_chars] + "\n" + cut
    return "\n".join(f"{i:4d}| {line}" for i, line in enumerate(code.splitlines(), 1)
                     if line.strip() or not drop_blank)


def submission_text_lang(sample, cfg: dict, lang: str = "vi") -> str:
    """prompt.max_compile_log_chars (errors only, first ones first) and prompt.drop_blank_lines shorten the
    prompt; without them the block is the shared src.task2.prompts.submission_text one."""
    if "max_compile_log_chars" not in cfg and not cfg.get("drop_blank_lines"):
        s = submission_text(sample, cfg)
        return s.replace("## BÀI NỘP CẦN PHÂN LOẠI", "## SUBMISSION TO GRADE", 1) if lang == "en" else s
    t = _LOG_TEXT[lang]
    code = numbered_code(sample.code, cfg.get("max_code_chars", 12000), bool(cfg.get("drop_blank_lines")),
                         _TEXT[lang]["cut"])
    s = f"{t['sub']}\n```cpp\n{code}\n```\n"
    if cfg.get("use_aux_signals", False):
        if sample.compile_log is not None:
            log = (compact_compile_log(sample.compile_log, int(cfg["max_compile_log_chars"]), lang)
                   if "max_compile_log_chars" in cfg else clean_compile_log(sample.compile_log))
            s += f"\n### compile_log\n```\n{log}\n```\n"
        if sample.test_report:
            s += f"\n### test_report\n{format_test_report(sample.test_report)}\n"
    return s


def demos_text(demos: list, cfg: dict) -> str:
    """Graded examples (other submissions, possibly other exams): code + compile status + conclusion line only."""
    if not demos:
        return ""
    lang = prompt_lang(cfg)
    t = _TEXT[lang]
    lim = int(cfg.get("demo_max_code_chars", 1800))
    parts = [t["demos"]]
    for i, d in enumerate(demos, 1):
        smp = _view(d.sample, cfg)
        code = smp.code if len(smp.code) <= lim else smp.code[:lim] + "\n" + t["cut"]
        parts.append(t["demo"].format(i=i, exam=smp.exam_id) + f"\n```cpp\n{code}\n```\n"
                     f"compile_log: {_compile_status(smp.compile_log, lang)}\n"
                     f'{t["marker"]} {json.dumps({"taxonomy_error": list(smp.labels)}, ensure_ascii=False)}\n')
    return "\n".join(parts) + "\n"


def build_cot_messages(exam: dict, sample, cfg: dict, demos=()) -> list[dict]:
    lang = prompt_lang(cfg)
    user = "\n".join(x for x in [exam_text_lang(exam, lang), exam_requirements(exam, lang),
                                  demos_text(list(demos), cfg), submission_text_lang(_view(sample, cfg), cfg, lang),
                                  cot_instruction(lang)] if x)
    return [{"role": "system", "content": system_prompt(lang)}, {"role": "user", "content": user}]
