"""Prompt templates for Task 3: Pedagogical Feedback Generation in Vietnamese.

Enforces pedagogical levels, negative constraints (no-code in L1/L2),
and consistent feedback formatting matching challenge criteria.
"""

from __future__ import annotations

import json
from typing import Sequence


LEVEL_DEFINITIONS = {
    "Level 1": {
        "full_name": "Level 1 - Gợi ý nhẹ",
        "description": "Chỉ báo bài làm có vấn đề hoặc khen ngợi chung, không chỉ ra vị trí lỗi.",
        "constraints": (
            "- CẤM tuyệt đối đưa code C++ sửa hoặc cú pháp lập trình.\n"
            "- CẤM chỉ ra vị trí cụ thể (không nhắc số dòng, không nêu tên hàm bị lỗi cụ thể).\n"
            "- CẤM nêu nguyên nhân kỹ thuật chi tiết. Chỉ đưa gợi ý định hướng chung để sinh viên tự rà soát."
        ),
    },
    "Level 2": {
        "full_name": "Level 2 - Chẩn đoán",
        "description": "Chỉ ra lỗi ở đâu và nguyên nhân là gì.",
        "constraints": (
            "- CẤM tuyệt đối đưa code C++ sửa hoặc cú pháp lập trình.\n"
            "- CẤM đưa cách sửa cụ thể hay giải pháp chi tiết.\n"
            "- ĐƯỢC PHÉP chỉ ra vị trí (số dòng, tên hàm, câu con P1-P4) và giải thích nguyên nhân gây ra lỗi."
        ),
    },
    "Level 3": {
        "full_name": "Level 3 - Gợi ý sửa",
        "description": "Chẩn đoán lỗi + gợi ý hướng sửa cho sinh viên.",
        "constraints": (
            "- CẤM đưa lời giải hoàn chỉnh hay code hoàn chỉnh thay thế.\n"
            "- ĐƯỢC PHÉP chẩn đoán vị trí, nguyên nhân và gợi ý thuật toán/hướng tư duy để sinh viên tự sửa."
        ),
    },
    "Level 4": {
        "full_name": "Level 4 - Lời giải mẫu",
        "description": "Được phép đưa code sửa hoặc lời giải mẫu hoàn chỉnh.",
        "constraints": "- ĐƯỢC PHÉP đưa đoạn code C++ sửa chuẩn hoặc giải pháp mẫu hoàn chỉnh.",
    },
}

SYSTEM_PROMPT = """\
Bạn là Trợ giảng môn Lập trình C++ tại trường Đại học, phụ trách viết nhận xét (feedback) sư phạm bằng TIẾNG VIỆT cho bài làm của sinh viên.

QUY TẮC CỐT LÕI (BẮT BUỘC PHẢI TUÂN THỦ):
1. QUY TẮC BÀI ĐÚNG: Nếu bài làm không có lỗi (danh sách taxonomy_error rỗng []), phản hồi feedback BẮT BUỘC để chuỗi RỖNG "" (hoàn toàn không viết gì).
2. QUY TẮC CẤP ĐỘ SƯ PHẠM (PEDAGOGICAL LEVEL COMPLIANCE):
   - Bạn PHẢI tuân thủ nghiêm ngặt cấp độ yêu cầu trong `target_feedback_level`.
   - LUẬT THÉP: Ở Level 1 và Level 2, TUYỆT ĐỐI KHÔNG ĐƯỢC xuất hiện bất kỳ dòng code C++, khối code (```cpp) hay cú pháp sửa nào. Vi phạm sẽ bị đánh giá 0 điểm.
3. PHONG CÁCH VIẾT NHẬN XÉT:
   - Viết bằng tiếng Việt súc tích, trực diện, chuyên nghiệp theo phong cách chấm bài của giảng viên đại học.
   - Với đề nhiều câu (multi_problem: P1, P2, P3, P4): nhận xét rành mạch từng câu theo cấu trúc: "P1 đúng; P2 đúng; P3 crash: ...; P4 không làm".
   - Bám sát các nhãn lỗi trong taxonomy_error được cung cấp.

ĐỊNH DẠNG ĐẦU RA:
Trả về DUY NHẤT một đối tượng JSON hợp lệ (không kèm lời chào hay giải thích ngoài JSON):
{
  "taxonomy_error": ["..."],
  "feedback": "Nội dung nhận xét tiếng Việt ở đây (hoặc chuỗi rỗng nếu không có lỗi)"
}
"""


def format_numbered_code(code: str) -> str:
    """Format C++ source code with line numbers to assist precise diagnosis."""
    lines = code.splitlines()
    width = len(str(len(lines)))
    return "\n".join(f"{i + 1:>{width}} | {line}" for i, line in enumerate(lines))


def build_user_prompt(
    exam_id: str,
    exam_type: str,
    exam_statement: str,
    code: str,
    target_level: str,
    taxonomy_error: Sequence[str] | None = None,
    compile_log: str | None = None,
) -> str:
    """Build the user prompt containing problem context, code, errors, and target level."""
    # Normalize level key (e.g. "Level 2 - Chẩn đoán" -> "Level 2")
    level_key = "Level 2"
    for k in ("Level 1", "Level 2", "Level 3", "Level 4"):
        if target_level.startswith(k):
            level_key = k
            break

    level_info = LEVEL_DEFINITIONS.get(level_key, LEVEL_DEFINITIONS["Level 2"])
    tax_str = json.dumps(list(taxonomy_error or []), ensure_ascii=False)
    compile_log_str = compile_log.strip() if compile_log else "(biên dịch thành công / không có log)"

    return f"""\
### 1. THÔNG TIN BÀI TẬP:
- Mã đề: {exam_id} ({exam_type})
- Đề bài tóm tắt:
{exam_statement.strip()}

### 2. MÃ NGUỒN C++ CỦA SINH VIÊN:
```cpp
{format_numbered_code(code)}
```

### 3. THÔNG TIN BIÊN DỊCH & LỖI ĐÃ XÁC ĐỊNH:
- Log biên dịch: {compile_log_str}
- Danh sách nhãn lỗi (taxonomy_error): {tax_str}

### 4. YÊU CẦU CẤP ĐỘ PHẢN HỒI (TARGET LEVEL):
- Cấp độ yêu cầu: **{target_level}**
- Định nghĩa: {level_info['description']}
- Ràng buộc nghiêm ngặt:
{level_info['constraints']}

Hãy sinh nội dung nhận xét feedback phù hợp đúng cấp độ trên dưới định dạng JSON."""


def build_task3_messages(
    exam_id: str,
    exam_type: str,
    exam_statement: str,
    code: str,
    target_level: str,
    taxonomy_error: Sequence[str] | None = None,
    compile_log: str | None = None,
) -> list[dict[str, str]]:
    """Build messages list ready for LLM chat completion API."""
    user_content = build_user_prompt(
        exam_id=exam_id,
        exam_type=exam_type,
        exam_statement=exam_statement,
        code=code,
        target_level=target_level,
        taxonomy_error=taxonomy_error,
        compile_log=compile_log,
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
