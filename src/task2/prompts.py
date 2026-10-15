"""Prompts for Task 2 Hướng 1 (API LLM). Pure functions of (exam, sample, demos, cfg); never use `feedback`."""
from __future__ import annotations

import json

from src.task1.prompts import clean_compile_log, format_test_report, number_lines
from src.task2.labels import DESCRIPTIONS, LABELS

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "taxonomy_error": {"type": "array", "items": {"type": "string", "enum": list(LABELS)}},
    },
    "required": ["rationale", "taxonomy_error"],
    "additionalProperties": False,
}

LABEL_GUIDE = "\n".join(f"- {lab}: {DESCRIPTIONS[lab]}" for lab in LABELS)

SYSTEM = (
    "Bạn là giảng viên chấm bài lập trình C++ nhập môn chuyên nghiệp, chấm kỹ lưỡng và phát hiện chính xác mọi loại lỗi. "
    "Nhiệm vụ: phân tích code của sinh viên và xác định tất cả các LOẠI LỖI mà bài nộp mắc phải trong 10 nhãn quy định (đa nhãn).\n\n"
    "HƯỚNG DẪN 10 LOẠI LỖI:\n"
    "- Lỗi biên dịch: Code vi phạm cú pháp C++, dùng thư viện/hàm chưa khai báo, sai kiểu nghiêm trọng khiến trình biên dịch báo error.\n"
    "- Lỗi logic: Điều kiện if/else sai, công thức tính toán sai, luồng xử lý sai làm sai kết quả với một số hoặc mọi test.\n"
    "- Lỗi vòng lặp: Vòng lặp vô hạn, điều kiện dừng sai, bước nhảy sai, lỗi off-by-one (lặp thừa hoặc thiếu 1 lần).\n"
    "- Lỗi mảng/chuỗi: Truy cập ngoài biên mảng (chỉ số âm hoặc >= kích thước n), tràn mảng, thiếu '\\0' kết thúc chuỗi, thao tác con trỏ sai.\n"
    "- Lỗi hàm: Quên tham chiếu '&' khi cần thay đổi giá trị biến, hàm non-void thiếu return, sai prototype hoặc kiểu trả về, gọi hàm sai.\n"
    "- Lỗi edge case: Bỏ sót trường hợp biên: n=0 hoặc 1, số âm, mảng/danh sách rỗng (head==NULL), chuỗi rỗng, phần tử đầu hoặc cuối.\n"
    "- Lỗi nhập/xuất: Đọc thiếu/thừa dữ liệu, in sai định dạng yêu cầu (thừa/thiếu khoảng trắng, sai hoa/thường, thiếu '\\n', in thừa prompt câu hỏi).\n"
    "- Lỗi thuật toán: Sai bản chất thuật toán/cấu trúc dữ liệu theo đề (ví dụ đề bắt dùng linked list nhưng dùng mảng), độ phức tạp quá cao.\n"
    "- Lỗi hard-code: Gán cứng kết quả cho vài test case ví dụ thay vì giải thuật toán tổng quát.\n"
    "- Lỗi style: Trình bày cẩu thả, thụt lề lộn xộn, đặt tên biến vô nghĩa (a, b, c, x1), lạm dụng biến toàn cục, code lặp nhiều lần.\n\n"
    "QUY TẮC:\n"
    "1. Sinh viên làm bài thường mắc từ 1 đến 3 lỗi. Hãy rà soát kỹ từng dòng code.\n"
    "2. Chỉ trả về danh sách rỗng [] khi bài nộp thực sự hoàn chỉnh, giải quyết trọn vẹn và chính xác tất cả các yêu cầu đề bài.\n"
    "3. Trả về DUY NHẤT một JSON hợp lệ."
)

OUTPUT_INSTRUCTION = (
    "## QUY TRÌNH RÀ SOÁT LỖI (BẮT BUỘC)\n"
    "Trước khi chốt nhãn, hãy kiểm tra lần lượt các lỗi phổ biến sau:\n"
    "1. Biên & trường hợp đặc biệt: Có kiểm tra n=0, n=1, số âm, mảng/danh sách rỗng không? -> nếu thiếu gán 'Lỗi edge case'\n"
    "2. Chỉ số mảng/chuỗi: Có duyệt i <= n (thay vì i < n), truy cập mảng ngoài phạm vi không? -> nếu có gán 'Lỗi mảng/chuỗi'\n"
    "3. Tham số hàm & return: Hàm có quên tham chiếu '&', quên return ở hàm int/bool không? -> nếu có gán 'Lỗi hàm'\n"
    "4. Định dạng I/O: In thừa prompt, sai ký tự phân cách, sai hoa thường? -> nếu có gán 'Lỗi nhập/xuất'\n"
    "5. Vòng lặp & dừng: Có vòng lặp vô hạn, sai điều kiện lặp? -> nếu có gán 'Lỗi vòng lặp'\n"
    "6. Tính toán & điều kiện: Sai nhánh if-else, tính sai công thức? -> nếu có gán 'Lỗi logic'\n"
    "7. Cấu trúc dữ liệu/thuật toán: Có làm sai cấu trúc (linked list, recursion) theo đề? -> nếu có gán 'Lỗi thuật toán'\n"
    "8. Hard-code & Style: Có gán cứng giá trị test hoặc trình bày cẩu thả? -> gán 'Lỗi hard-code' / 'Lỗi style'\n\n"
    "## YÊU CẦU ĐẦU RA\n"
    "Trả về DUY NHẤT JSON dạng:\n"
    '{"rationale": "<1-3 câu phân tích cụ thể các lỗi tìm thấy>", "taxonomy_error": ["<nhãn>", ...]}\n'
    "Chỉ dùng đúng các tên nhãn trong danh sách 10 nhãn trên; [] nếu bài hoàn toàn không có bất kỳ lỗi nào."
)


def exam_text(exam: dict) -> str:
    return (f"## ĐỀ BÀI ({exam['exam_id']}, loại {exam['exam_type']}, môn {exam.get('course', '')})\n"
            f"{exam.get('statement', '').strip()}\n")


def submission_text(sample, cfg: dict) -> str:
    s = f"## BÀI NỘP CẦN PHÂN LOẠI\n```cpp\n{number_lines(sample.code, cfg.get('max_code_chars', 12000))}\n```\n"
    if cfg.get("use_aux_signals", False):
        if sample.compile_log is not None:
            s += f"\n### compile_log\n```\n{clean_compile_log(sample.compile_log)}\n```\n"
        if sample.test_report:
            s += f"\n### test_report\n{format_test_report(sample.test_report)}\n"
    return s


def demo_text(demos: list, cfg: dict) -> str:
    if not demos:
        return ""
    lim = cfg.get("demo_max_code_chars", 3000)
    parts = ["## VÍ DỤ ĐÃ ĐƯỢC GIẢNG VIÊN GÁN NHÃN (đề khác, chỉ tham khảo cách gán nhãn)"]
    for k, d in enumerate(demos, 1):
        code = d.code if len(d.code) <= lim else d.code[:lim] + "\n// ...(cắt bớt)"
        parts.append(f"### Ví dụ {k} (đề {d.exam_id}, {d.exam_type})\n```cpp\n{code}\n```\n"
                     f"Nhãn của giảng viên: {json.dumps(d.labels, ensure_ascii=False)}\n")
    return "\n".join(parts) + "\n"


def build_messages(exam: dict, sample, demos: list, cfg: dict) -> list[dict]:
    user = "\n".join(x for x in [exam_text(exam), demo_text(demos, cfg), submission_text(sample, cfg),
                                  OUTPUT_INSTRUCTION] if x)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def select_demos(pool: list, sample, k: int) -> list:
    """Greedy, deterministic: pick labelled demos (never `sample`) that cover the most not-yet-covered labels,
    preferring the same exam type; one error-free demo ([]) counts as half a new label."""
    if k <= 0:
        return []
    cands = sorted((s for s in pool if s.has_gold and s.sample_id != sample.sample_id),
                   key=lambda s: (s.exam_type != sample.exam_type, s.sample_id))
    chosen, covered = [], set()

    def gain(s) -> float:
        if not s.labels:
            return 0.5 if all(c.labels for c in chosen) else 0.0
        return float(len(set(s.labels) - covered))

    while cands and len(chosen) < k:
        best = max(cands, key=gain)  # max keeps the first of equal gains -> stable order
        chosen.append(best)
        covered |= set(best.labels)
        cands.remove(best)
    return chosen
