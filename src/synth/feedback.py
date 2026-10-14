"""Level-controlled feedback templates (synth_plan.md section T3.2).

Feedback is built from the *metadata of the defect we injected ourselves* (location, cause, fix
direction, fix snippet), so we never need an LLM to diagnose. Per level there are several
templates; the caller passes a seeded ``random.Random`` so output is reproducible. An optional
``rephrase`` callable (e.g. a local LLM) may rewrite a line, but it is only accepted when it still
mentions the defect's keywords — otherwise the template is kept.

Generated text is expected to pass src/synth/compliance.py for its own level; see
tests/test_synth_feedback.py which renders every defect at every level and checks compliance.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from src.synth.compliance import check

FEEDBACK_LEVELS = (
    "Level 1 - Gợi ý nhẹ",
    "Level 2 - Chẩn đoán",
    "Level 3 - Gợi ý sửa",
    "Level 4 - Lời giải mẫu",
)


@dataclass(frozen=True)
class DefectText:
    cause: str
    fix: str
    code: str = ""
    keywords: tuple[str, ...] = ()


DEFECT_TEXT: dict[str, DefectText] = {
    "D00": DefectText("bài nộp để trống hoặc toàn bộ code đã bị comment", "mở lại phần code đang bị comment",
                      "// code bị comment hết nên chương trình không có gì để chạy", ("comment", "trống")),
    "D01": DefectText("có lỗi cú pháp nên chương trình không biên dịch được", "xem lại dấu chấm phẩy và dấu ngoặc ở chỗ báo lỗi",
                      "// bổ sung dấu ; còn thiếu", ("cú pháp", "biên dịch")),
    "D02": DefectText("dùng một biến hoặc hàm chưa được khai báo", "khai báo biến trước khi dùng",
                      "int x = 0; // khai báo trước khi dùng", ("khai báo", "biên dịch")),
    "D03": DefectText("include trực tiếp file dữ liệu nên không biên dịch được", "đọc file bằng ifstream thay vì include",
                      'ifstream f("generals.csv");', ("include", "file", "biên dịch")),
    "D04": DefectText("vòng lặp không kết thúc", "cập nhật biến điều khiển trong mỗi vòng lặp",
                      "cur = cur->next;", ("vòng lặp", "không dừng")),
    "D05": DefectText("phần tính toán chính còn bỏ dở", "hoàn thiện phần thân hàm",
                      "// viết nốt phần tính toán", ("bỏ dở", "hoàn thiện")),
    "D06": DefectText("sai cả định dạng token trả về lẫn thuật toán", "trả về đúng token đáp án và sửa lại phép tính",
                      'cout << (ok ? "True" : "False");', ("token", "định dạng", "thuật toán")),
    "D07": DefectText("in thừa ký tự trước kết quả", "in đúng token đáp án, bỏ ký tự thừa",
                      'cout << (ok ? "True" : "False");', ("thừa", "ký tự", "định dạng")),
    "D08": DefectText("sai bản chất phép tính ở phần lõi", "xem lại công thức tại chỗ tính chính",
                      "result = pow(d, 2);", ("công thức", "thuật toán")),
    "D09": DefectText("hàm phụ tính toán sai", "xem lại điều kiện dừng trong hàm phụ",
                      "for (int i = 0; i < d; i++)", ("hàm phụ", "điều kiện")),
    "D10": DefectText("gọi stoi hoặc stof trên chuỗi không hợp lệ nên chương trình dừng", "kiểm tra chuỗi trước khi chuyển sang số",
                      'if (!s.empty()) n = stoi(s);', ("stoi", "chuỗi", "dừng")),
    "D11": DefectText("trả về địa chỉ mảng cục bộ nên dữ liệu không còn sau khi ra khỏi hàm",
                      "cấp phát động cho mảng kết quả", "General* a = new General[n];", ("mảng", "cục bộ")),
    "D12": DefectText("hàm chưa được cài đặt (thân hàm rỗng)", "hoàn thiện hàm theo prototype đã cho",
                      "// viết phần thân hàm còn thiếu", ("chưa làm", "thiếu")),
    "D13": DefectText("sai công thức hoặc điều kiện ở câu này", "xem lại công thức và điều kiện của câu",
                      "// kiểm tra lại công thức", ("công thức", "điều kiện")),
    "D14": DefectText("xử lý sai ở trường hợp biên", "xử lý thêm trường hợp danh sách rỗng và phần tử đầu",
                      "if (head == nullptr) return;", ("biên", "rỗng")),
    "D14b": DefectText("vòng lặp bỏ sót phần tử cuối nên sai khi giá trị cần tìm nằm ở cuối", "xem lại điều kiện dừng của vòng lặp",
                       "for (int i = 0; i < n; i++)", ("vòng lặp", "cuối")),
    "D14c": DefectText("bỏ qua các giá trị âm nên sai khi dữ liệu có số âm", "xử lý cả trường hợp giá trị âm",
                       "s += arr[i].a;", ("âm", "biên")),
    "D14d": DefectText("xử lý sai trường hợp chỉ có một phần tử", "kiểm tra lại trường hợp n bằng 1",
                       "// không cần trường hợp đặc biệt cho n == 1", ("một phần tử", "biên")),
    "D15s": DefectText("gán cứng số lần lặp thay vì dùng kích thước thật của dữ liệu", "dùng kích thước đầu vào làm điều kiện lặp",
                       "for (int i = 0; i < n; i++)", ("cứng", "kích thước")),
    "D15": DefectText("gán cứng tên file hoặc kích thước thay vì đọc từ tham số", "đọc số phần tử thực tế từ file",
                      "ifstream f(filename);", ("cứng", "file")),
    "D16a": DefectText("chỉ chạy đúng ở test thường, sai ở nhiều nhóm test biên", "xử lý trường hợp nhỏ nhất và lớn nhất",
                       "long long p = 1;", ("biên", "tràn số")),
    "D16b": DefectText("chỉ chạy đúng ở test thường, sai đúng một nhóm test biên", "xử lý thêm trường hợp biên còn thiếu",
                       "// thêm kiểm tra trường hợp biên", ("biên",)),
    "D17": DefectText("chỉ đúng với ví dụ trong đề, chưa có thuật toán tổng quát", "viết thuật toán tổng quát thay vì kiểm tra cứng",
                      "// tính toán thay vì if cứng theo ví dụ", ("cứng", "tổng quát")),
    "D18": DefectText("thuật toán chạy quá chậm hoặc tràn số với input lớn", "dùng kiểu dữ liệu lớn hơn và thuật toán nhanh hơn",
                      "long long sum = 0;", ("chậm", "tràn số")),
    "D19": DefectText("sai định dạng token trả về và logic sai một phần", "sửa lại token và một phần điều kiện",
                      'cout << (ok ? "True" : "False");', ("token", "logic")),
    "D20": DefectText("truy cập ngoài phạm vi mảng hoặc chuyển ký tự sang số sai", "kiểm tra chỉ số mảng và chuyển char đúng cách",
                      "int v = s[i] - '0';", ("mảng", "chỉ số")),
    "D21": DefectText("gọi hàm hoặc truyền tham số chưa đúng", "kiểm tra lại cách gọi hàm và tham số",
                      "if (isArm(n))", ("hàm", "tham số")),
    "D22": DefectText("code khó đọc và đặt tên vô nghĩa", "đặt tên rõ ràng và tách thành hàm nhỏ",
                      "int tinhTong(int n) { /* ... */ }", ("style", "khó đọc")),
    "D23": DefectText("logic đúng nhưng code khó đọc và đặt tên vô nghĩa", "đặt tên rõ ràng và tách thành hàm nhỏ",
                      "int tinhTong(int n) { /* ... */ }", ("style", "khó đọc")),
}

_L1 = (
    "Bài còn một chỗ chưa đúng, em xem lại nhé.",
    "Em đã làm được phần lớn, còn một điểm cần chú ý.",
    "Chương trình chưa chạy đúng ở một trường hợp, em kiểm tra thêm nhé.",
    "Bài làm còn một vấn đề nhỏ, em chú ý xem lại.",
    "Cố lên em, bài vẫn còn một chỗ cần chỉnh.",
    "Em xem lại bài giúp cô nhé, còn một chỗ chưa ổn.",
    "Hướng làm của em ổn, nhưng kết quả chưa đúng hoàn toàn.",
    "Chưa hoàn thiện, em rà soát lại bài một lượt nhé.",
    "Bài chưa đạt yêu cầu, em thử chạy lại với nhiều input khác nhau.",
    "Em cần kiểm tra lại bài trước khi nộp nhé.",
    "Có tiến bộ, nhưng bài vẫn còn lỗi cần sửa.",
    "Em đọc kỹ lại đề và đối chiếu với bài làm của mình nhé.",
)
_L2 = (
    "{location} {cause}.",
    "Ở {location}, {cause}.",
    "Chỗ {location} bị sai vì {cause}.",
    "{location} có vấn đề: {cause}.",
    "Vấn đề nằm ở {location}, cụ thể là {cause}.",
    "{location}: {cause}.",
    "Lỗi ở {location}: {cause}.",
    "Em sai ở {location}, do {cause}.",
    "Tại {location}, {cause} nên kết quả không đúng.",
    "Kiểm tra {location}: {cause}.",
)
_L3 = (
    "{location} {cause} nên em cần {fix}.",
    "Ở {location}, {cause}; em nên {fix}.",
    "{location}: {cause}. Hướng khắc phục: {fix}.",
    "{cause} ở {location}, em thử {fix} xem.",
    "{location} bị {cause}. Em cần {fix}.",
    "Em sai ở {location} vì {cause}. Gợi ý: {fix}.",
    "Tại {location}, {cause}. Em có thể {fix}.",
    "{location} chưa đúng do {cause}; hướng sửa là {fix}.",
)
_L4 = (
    "{location} {cause} nên em cần {fix}.\n```cpp\n{code}\n```",
    "Ở {location}, {cause}. Hướng sửa:\n```cpp\n{code}\n```",
    "{location}: {cause}.\nSửa lại:\n```cpp\n{code}\n```",
    "Lỗi ở {location} ({cause}). Em tham khảo đoạn sau:\n```cpp\n{code}\n```",
)
_PRAISE = (
    "Tốt, bài làm đúng và gọn.",
    "Bài làm đúng, em làm tốt lắm.",
    "Tốt.",
    "Bài làm chính xác, em giữ phong độ nhé.",
    "Đúng hết, em làm tốt.",
    "Tốt, chương trình chạy đúng.",
    "Bài làm tốt, đúng yêu cầu đề.",
    "Rất tốt, em làm đúng.",
    "Chính xác, em làm tốt lắm.",
    "Tốt, em xử lý đúng các trường hợp.",
)
_PRAISE_MULTI = (
    "Các câu đều đúng, em làm tốt.",
    "Bài làm đúng cả bốn câu.",
    "Tốt, các hàm đều chạy đúng.",
    "P1 đúng; P2 đúng; P3 đúng; P4 đúng;",
    "Tốt, đọc file và xử lý đều đúng.",
)
_COMPILE_DEFECTS = ("D01", "D02", "D03")


def _pick(rng: random.Random, options: tuple[str, ...]) -> str:
    return options[rng.randrange(len(options))]


def render(level: str | int, *, cause: str = "", location: str = "trong bài làm",
           fix: str = "", code: str = "", rng: random.Random | None = None) -> str:
    """Render one feedback fragment at the requested level."""
    from src.synth.compliance import level_of

    lvl = level_of(level)
    rng = rng or random.Random(0)
    if lvl == 1:
        return _pick(rng, _L1)
    if lvl == 2:
        text = _pick(rng, _L2).format(location=location, cause=cause)
    elif lvl == 3:
        text = _pick(rng, _L3).format(location=location, cause=cause, fix=fix)
    else:
        text = _pick(rng, _L4).format(location=location, cause=cause, fix=fix, code=code or "// ...")
    return text[:1].upper() + text[1:] if text else text


def praise(level: str | int, rng: random.Random | None = None, multi: bool = False) -> str:
    rng = rng or random.Random(0)
    return _pick(rng, _PRAISE_MULTI if multi else _PRAISE)


def feedback_for(defect_ids, level: str | int, *, problem: str | None = None, location: str | None = None,
                 compile_log: str = "", rng: random.Random | None = None, rephrase=None) -> str:
    """Feedback for a record with the given defect(s) at the requested level.

    ``location`` names where the defect sits (e.g. ``hàm isArm``). For compile errors at Level 2 a
    real g++ diagnostic may be pasted (instructor style, valid per the 2026-10-13 decision)."""
    from src.synth.compliance import level_of

    if isinstance(defect_ids, str):
        defect_ids = [defect_ids]
    if not defect_ids:
        return praise(level, rng, multi=problem is not None)
    rng = rng or random.Random(0)
    location = location or (f"câu {problem}" if problem else "trong bài làm")
    if compile_log and level_of(level) == 2 and defect_ids[0] in _COMPILE_DEFECTS:
        return compile_log.strip()
    parts = []
    for did in defect_ids[:2]:
        text = DEFECT_TEXT[did]
        parts.append(render(level, cause=text.cause, location=location, fix=text.fix, code=text.code, rng=rng))
        if level_of(level) == 1:
            break
    out = " ".join(parts)
    return _maybe_rephrase(out, defect_ids, rephrase)


def multi_feedback(per_problem, level: str | int, *, rng: random.Random | None = None, rephrase=None) -> str:
    """EX01-style feedback: 'P1 đúng; P2 đúng; P3 <cause>; P4 không làm;'.

    ``per_problem`` is a list of ``(pid, defect_ids, status)``. Level 1 never names problems; Level
    3 adds the fix direction; Level 4 adds a short fix snippet for the first faulty question."""
    from src.synth.compliance import level_of

    rng = rng or random.Random(0)
    lvl = level_of(level)
    faulty = [(pid, d, st) for pid, d, st in per_problem if st != "ok"]
    if not faulty:
        return _pick(rng, _PRAISE_MULTI)
    if lvl == 1:
        return _pick(rng, _L1)
    chunks = []
    for pid, defects, status in per_problem:
        if status == "ok":
            chunks.append(f"{pid} đúng")
        elif status == "missing" or not defects:
            chunks.append(f"{pid} không làm" if status == "missing" else f"{pid} sai")
        else:
            text = DEFECT_TEXT[defects[0]]
            chunk = f"{pid} {text.cause}"
            if lvl >= 3:
                chunk += f", em cần {text.fix}"
            chunks.append(chunk)
    out = "; ".join(chunks) + ";"
    if per_problem and per_problem[0][2] != "ok":
        out += " Câu 1 là câu tiên quyết nên các câu sau không được chấm."
    if lvl == 4:
        first = next((d for _, d, st in faulty if d), None)
        if first:
            out += f"\n```cpp\n{DEFECT_TEXT[first[0]].code}\n```"
    return out


def _maybe_rephrase(text: str, defect_ids, rephrase) -> str:
    if rephrase is None:
        return text
    candidate = rephrase(text)
    if candidate is None:
        return text
    keywords = [k for did in defect_ids for k in DEFECT_TEXT[did].keywords]
    low = candidate.lower()
    if all(k.lower() in low for k in keywords):
        return candidate
    return text


def feedback_is_compliant(text: str, level: str | int) -> bool:
    return check(text, level).ok
