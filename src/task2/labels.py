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


# Short names the CoT model writes in its conclusion instead of the label (the 7 step headers of
# src/task2/prompts_cot.py, with or without "Lỗi"); keys are compared after _key().
_ALIASES = {
    "biên dịch": "Lỗi biên dịch", "compile": "Lỗi biên dịch",
    "nhập/xuất": "Lỗi nhập/xuất", "nhập xuất": "Lỗi nhập/xuất", "input/output": "Lỗi nhập/xuất", "i/o": "Lỗi nhập/xuất",
    "logic": "Lỗi logic",
    "vòng lặp": "Lỗi vòng lặp", "loop": "Lỗi vòng lặp",
    "mảng/chuỗi": "Lỗi mảng/chuỗi", "mảng": "Lỗi mảng/chuỗi", "chuỗi": "Lỗi mảng/chuỗi",
    "hàm": "Lỗi hàm", "function": "Lỗi hàm",
    "edge case": "Lỗi edge case", "edge-case": "Lỗi edge case", "trường hợp biên": "Lỗi edge case",
    "thuật toán": "Lỗi thuật toán", "algorithm": "Lỗi thuật toán",
    "hard-code": "Lỗi hard-code", "hardcode": "Lỗi hard-code", "hard code": "Lỗi hard-code",
    "style": "Lỗi style",
    # English glosses used by the prompt.lang: en prompt (a trailing "error" is dropped first, see coerce_label)
    "compilation": "Lỗi biên dịch", "input/output": "Lỗi nhập/xuất", "io": "Lỗi nhập/xuất",
    "array/string": "Lỗi mảng/chuỗi", "array": "Lỗi mảng/chuỗi", "string": "Lỗi mảng/chuỗi",
    "function misuse": "Lỗi hàm", "hard-coding": "Lỗi hard-code", "hardcoding": "Lỗi hard-code",
    "hard-coded": "Lỗi hard-code", "hardcoded": "Lỗi hard-code",
}


def coerce_label(x) -> list[str]:
    """Labels meant by a free-text conclusion entry: the exact label, a short name ("Vòng lặp" -> Lỗi vòng lặp,
    with or without a leading "Lỗi"), or a step header naming several ("Vòng lặp và mảng/chuỗi" -> both).
    Unknown text -> []."""
    if not isinstance(x, str):
        return []
    exact = normalize_label(x)
    if exact:
        return [exact]
    k = _key(x)
    k = k[4:] if k.startswith("lỗi ") else k
    k = re.sub(r"\s+errors?$", "", k) if k not in _ALIASES else k  # "Logic error" -> "logic"
    if k in _ALIASES:
        return [_ALIASES[k]]
    parts = [p for p in re.split(r"\s*(?:,|;|\bvà\b|\band\b|\+)\s*", k) if p]
    found = []
    for p in parts:
        p = p[4:] if p.startswith("lỗi ") else p
        p = re.sub(r"\s+errors?$", "", p) if p not in _ALIASES else p
        lab = _BY_KEY.get(_key("lỗi " + p)) or _ALIASES.get(p)
        if lab is None:
            return []  # any unknown part -> do not guess
        found.append(lab)
    return found


def coerce_labels(xs) -> list[str]:
    """normalize_labels, but recovering short names via coerce_label."""
    if not isinstance(xs, (list, tuple)):
        return []
    found = {lab for x in xs for lab in coerce_label(x)}
    return [lab for lab in LABELS if lab in found]
