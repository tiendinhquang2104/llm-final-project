"""Task 2 label space: the 10 taxonomy labels (official order) with Vietnamese working definitions.

The dataset ships no definitions; these descriptions are our reading of the label names and are shared by the
API prompts (Hướng 1) and the CLM yes/no questions (Hướng 2).
"""
from __future__ import annotations

import re

from src.data.schema import TAXONOMY_LABELS

LABELS: tuple[str, ...] = tuple(TAXONOMY_LABELS)

DESCRIPTIONS: dict[str, str] = {
    "Lỗi biên dịch": "code không biên dịch được: sai cú pháp, dùng biến/hàm chưa khai báo, sai kiểu nghiêm trọng, "
                     "thiếu thư viện bắt buộc (lỗi chỉ riêng trình biên dịch MSVC như void main vẫn chấp nhận được).",
    "Lỗi nhập/xuất": "đọc hoặc ghi dữ liệu sai: in thừa/thiếu chuỗi, sai định dạng, sai hoa thường, đọc stdin hoặc "
                     "file sai cách, tách/chuyển đổi dữ liệu đầu vào sai.",
    "Lỗi logic": "điều kiện, công thức hoặc luồng xử lý sai làm kết quả sai với một số hoặc mọi đầu vào.",
    "Lỗi vòng lặp": "vòng lặp sai: điều kiện dừng sai, lặp thừa/thiếu một lần (off-by-one), vòng lặp vô hạn, "
                    "cập nhật biến chạy sai.",
    "Lỗi mảng/chuỗi": "xử lý mảng hoặc chuỗi sai: truy cập ngoài chỉ số, sai kích thước, sai ký tự kết thúc, "
                      "xoá/chèn/dịch phần tử sai.",
    "Lỗi hàm": "định nghĩa hoặc dùng hàm sai: sai prototype/kiểu trả về, thiếu return, truyền tham trị thay vì "
               "tham chiếu, không viết hoặc không gọi hàm theo yêu cầu đề.",
    "Lỗi edge case": "không xử lý trường hợp biên: n = 0 hoặc 1, số âm, mảng/danh sách/chuỗi rỗng, phần tử đầu "
                     "hoặc cuối, dữ liệu đặc biệt.",
    "Lỗi thuật toán": "chọn thuật toán hoặc cấu trúc dữ liệu sai/không đúng yêu cầu (ví dụ không dùng linked list, "
                      "BST theo đề), thiếu bước then chốt, độ phức tạp quá cao.",
    "Lỗi hard-code": "gán cứng giá trị, kết quả hoặc dữ liệu theo test/ví dụ thay vì tính toán tổng quát.",
    "Lỗi style": "trình bày kém: đặt tên khó hiểu, thụt lề lộn xộn, code lặp, lạm dụng biến toàn cục, dùng thư viện "
                 "hoặc hàm bị đề cấm.",
}


def _key(x: str) -> str:
    return re.sub(r"\s+", " ", x).strip().casefold()


_BY_KEY = {_key(lab): lab for lab in LABELS}


def normalize_label(x) -> str | None:
    """Canonical label for `x` (case/whitespace-insensitive, like the leaderboard), else None."""
    return _BY_KEY.get(_key(x)) if isinstance(x, str) else None


def normalize_labels(xs) -> list[str]:
    """Valid labels of `xs`, deduplicated, in canonical order; anything that is not a list gives []."""
    if not isinstance(xs, (list, tuple)):
        return []
    found = {normalize_label(x) for x in xs}
    return [lab for lab in LABELS if lab in found]


def to_vector(labels) -> list[int]:
    s = set(labels)
    return [int(lab in s) for lab in LABELS]


def from_vector(v) -> list[str]:
    return [lab for lab, b in zip(LABELS, v) if b]
