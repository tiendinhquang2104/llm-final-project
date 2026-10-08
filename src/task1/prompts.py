"""Prompt templates for Task 1. Every template is a pure function of (exam, sample, demos, cfg)."""
from __future__ import annotations

import json
import re

from src.data.loader import DIM_MAX, DIMENSIONS, Sample
from src.task1.prerequisite_rules import STATUSES

RUBRIC_GUIDE = """\
RUBRIC (6 chiều, tổng 0-10):
- compilable (0-1): 1 nếu code biên dịch được theo yêu cầu của đề. compile_log chỉ là TÍN HIỆU PHỤ: \
lỗi kiểu trình biên dịch MSVC (void main, dùng pow mà thiếu #include <cmath>, ...) giảng viên vẫn cho 1. \
Lỗi cú pháp thật, dùng biến/hàm chưa khai báo, #include file dữ liệu, sai kiểu trả về nghiêm trọng -> 0.
- io_format (0-1): đúng định dạng vào/ra. Đề stdin/stdout: in đúng chính xác chuỗi yêu cầu (ví dụ True/False, \
đúng hoa thường, không thừa ký tự/khoảng trắng). Đề nhiều câu dạng hàm: đúng prototype, đọc/ghi dữ liệu đúng, \
không crash khi parse dữ liệu (stoi/stof lỗi, ...).
- logic (0-4): mức đúng của thuật toán chính. 4 = đúng hoàn toàn; 3 = gần đúng, sai nhỏ; 2 = đúng khoảng một nửa \
(sai một phần đáng kể hoặc sai nhiều test); 1 = chỉ đúng rất ít; 0 = sai hoàn toàn / không làm / không chạy được. \
Đề nhiều câu: tính theo tỷ lệ câu làm đúng có trọng số.
- edge_case (0-2): xử lý trường hợp biên (số 1 chữ số, danh sách rỗng, phần tử đầu/cuối, dữ liệu đặc biệt...). \
2 = đầy đủ, 1 = thiếu một số, 0 = không xử lý / logic sai hoàn toàn.
- complexity (0-1): thuật toán có độ phức tạp hợp lý, không vòng lặp vô hạn rõ ràng.
- code_quality (0-1): code rõ ràng, chia hàm hợp lý, tuân thủ ràng buộc của đề (thư viện cho phép, không dùng hàm bị cấm).
"""

STATUS_GUIDE = """\
TRẠNG THÁI TỪNG CÂU (problems[].status):
- correct: đúng hoàn toàn
- partial: đúng một phần (sai một số trường hợp)
- wrong: sai logic / kết quả sai
- runtime_error: crash, truy cập con trỏ sai, vòng lặp vô hạn
- not_attempted: không làm / thân hàm rỗng / chỉ khai báo prototype
"""

POLICY_IN_CODE = (
    "Chấm TỪNG CÂU MỘT CÁCH ĐỘC LẬP theo đúng chất lượng code của câu đó. "
    "KHÔNG tự áp dụng chính sách câu tiên quyết — hệ thống sẽ tự áp dụng sau."
)

SYSTEM_PLAIN = (
    "Bạn là giảng viên chấm bài lập trình C++ của sinh viên. Hãy chấm theo rubric 6 chiều: "
    "compilable (0-1), io_format (0-1), logic (0-4), edge_case (0-2), complexity (0-1), code_quality (0-1). "
    'Chỉ trả về một object JSON dạng {"compilable": int, "io_format": int, "logic": int, '
    '"edge_case": int, "complexity": int, "code_quality": int}.'
)

SYSTEM_STRUCTURED = (
    "Bạn là giảng viên chấm bài lập trình C++ nhập môn, chấm nhất quán, công bằng và bám sát rubric. "
    "Bạn đọc đề, đọc code (có đánh số dòng), dùng compile_log/test_report làm tín hiệu phụ, "
    "rồi trả về DUY NHẤT một object JSON hợp lệ, không có văn bản nào khác.\n\n"
    + RUBRIC_GUIDE + "\n" + STATUS_GUIDE
)


def clean_compile_log(log: str | None, max_chars: int = 2000) -> str:
    if log is None:
        return "(không có)"
    log = re.sub(r"/tmp/tmp\w+/", "", log).strip()
    if not log:
        return "(rỗng — không có lỗi hay cảnh báo)"
    return log if len(log) <= max_chars else log[:max_chars] + "\n...(cắt bớt)"


def format_test_report(report: list[dict] | None, max_actual: int = 80) -> str:
    if not report:
        return "(không có)"
    passed = sum(1 for t in report if t.get("passed"))
    lines = [f"{passed}/{len(report)} test công khai PASS"]
    for t in report:
        actual = str(t.get("actual", ""))
        actual = actual if len(actual) <= max_actual else actual[:max_actual] + "..."
        lines.append(
            f"- input={t.get('input')!r} expected={t.get('expected')!r} actual={actual!r} "
            f"{'PASS' if t.get('passed') else 'FAIL'}"
        )
    return "\n".join(lines)


def number_lines(code: str, max_chars: int = 12000) -> str:
    if len(code) > max_chars:
        code = code[:max_chars] + "\n// ...(cắt bớt)"
    return "\n".join(f"{i + 1:4d}| {line}" for i, line in enumerate(code.splitlines()))


def problem_ids(exam: dict) -> list[str]:
    return [p["pid"] for p in exam.get("problems", [])] or ["P1"]


def exam_block(exam: dict, policy_in_prompt: bool) -> str:
    probs = "\n".join(
        f"- {p['pid']}: trọng số {p.get('max_score')}"
        + (f"; prototype `{p['prototype']}`" if p.get("prototype") else "")
        + (f"; là câu tiên quyết cho {', '.join(p['is_prerequisite_for'])}" if p.get("is_prerequisite_for") else "")
        for p in exam.get("problems", [])
    )
    s = (
        f"## ĐỀ BÀI ({exam['exam_id']}, loại {exam['exam_type']}, môn {exam.get('course', '')})\n"
        f"{exam['statement'].strip()}\n\n### Các câu\n{probs}\n"
    )
    if exam.get("grading_policy"):
        if policy_in_prompt:
            s += f"\n### Chính sách chấm (BẮT BUỘC áp dụng)\n{exam['grading_policy']}\n"
        elif exam["exam_type"] == "multi_problem":
            s += f"\n### Lưu ý\n{POLICY_IN_CODE}\n"
    return s


def submission_block(sample: Sample, cfg: dict) -> str:
    s = (
        f"## BÀI NỘP {sample.sample_id}\n```cpp\n{number_lines(sample.code, cfg.get('max_code_chars', 12000))}\n```\n\n"
        f"### compile_log\n```\n{clean_compile_log(sample.compile_log)}\n```\n"
    )
    if cfg.get("use_test_report", True) and sample.test_report is not None:
        s += f"\n### test_report\n{format_test_report(sample.test_report)}\n"
    return s


def demo_block(demos: list[Sample], cfg: dict) -> str:
    if not demos:
        return ""
    parts = ["## VÍ DỤ ĐÃ ĐƯỢC GIẢNG VIÊN CHẤM (tham khảo mức điểm, cùng đề)"]
    for k, d in enumerate(demos, 1):
        code = d.code
        lim = cfg.get("demo_max_code_chars", 4000)
        if len(code) > lim:
            code = code[:lim] + "\n// ...(cắt bớt)"
        part = f"### Ví dụ {k} ({d.sample_id})\n```cpp\n{code}\n```\ncompile_log: {clean_compile_log(d.compile_log, 600)}\n"
        if cfg.get("use_test_report", True) and d.test_report is not None:
            part += f"test_report: {format_test_report(d.test_report).splitlines()[0]}\n"
        part += f"Điểm của giảng viên: {json.dumps(d.gold_rubric)} -> tổng {d.gold_total}\n"
        parts.append(part)
    return "\n".join(parts) + "\n"


def output_instruction(exam: dict, template: str) -> str:
    if template == "plain":
        return 'Trả về JSON: {"compilable":..,"io_format":..,"logic":..,"edge_case":..,"complexity":..,"code_quality":..}'
    pids = problem_ids(exam)
    example = {
        "rationale": "<tóm tắt 1-3 câu: lỗi chính / điểm mạnh>",
        "problems": [{"pid": pid, "status": "|".join(STATUSES), "note": "<ngắn gọn>"} for pid in pids],
        "rubric": {d: f"<int 0-{DIM_MAX[d]}>" for d in DIMENSIONS},
    }
    return (
        "## YÊU CẦU ĐẦU RA\nTrả về DUY NHẤT một object JSON đúng schema sau (problems có đủ các câu "
        f"{', '.join(pids)}):\n```json\n{json.dumps(example, ensure_ascii=False, indent=1)}\n```"
    )


def build_messages(exam: dict, sample: Sample, demos: list[Sample], cfg: dict) -> list[dict]:
    template = cfg.get("template", "structured")
    policy_in_prompt = cfg.get("policy_in_prompt", False)
    system = SYSTEM_PLAIN if template == "plain" else SYSTEM_STRUCTURED
    user = "\n".join(
        x for x in [
            exam_block(exam, policy_in_prompt),
            demo_block(demos, cfg),
            submission_block(sample, cfg),
            output_instruction(exam, template),
        ] if x
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def select_demos(pool: list[Sample], sample: Sample, k: int, strategy: str = "spread") -> list[Sample]:
    """Pick k labelled demos from the train pool of the same exam (never the sample itself).

    spread: evenly cover the score range so the model sees low/mid/high anchors. Deterministic.
    """
    cands = sorted(
        (s for s in pool if s.exam_id == sample.exam_id and s.sample_id != sample.sample_id and s.has_gold),
        key=lambda s: (s.gold_total, s.sample_id),
    )
    if k <= 0 or not cands:
        return []
    if len(cands) <= k:
        return cands
    if k == 1:
        return [cands[len(cands) // 2]]
    idx = sorted({round(i * (len(cands) - 1) / (k - 1)) for i in range(k)})
    return [cands[i] for i in idx]
