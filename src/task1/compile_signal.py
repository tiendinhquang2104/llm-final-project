"""Deterministic compile verdict from the organizer's g++ log (API experiment e7).

Evidence, 32 teacher-graded samples joined with the compile logs of the first sample release:
- a compiler diagnostic `file:line:col: error:` -> compilable = 0 in 6/6 samples;
- warnings only -> compilable = 1 in 3/3, graded normally;
- only the linker's "undefined reference to `main'" -> compilable = 1, graded normally (EX02-S214, total 10);
- empty log -> compilable = 1 in 22/22.
So "compiler error <=> compilable 0" matches 32/32 and is decided in code, not by the model.
"""
from __future__ import annotations

import re

from src.data.prompts import COMPILE_LOG_MAX_CHARS, compile_errors_only

OK, ERROR, UNKNOWN = "ok", "error", "unknown"

_COMPILER_ERROR = re.compile(r"^\S+:\d+:\d+: (?:fatal )?error:", re.M)
_WARNING = re.compile(r"^\S+:\d+:\d+: warning:.*$", re.M)
_UNDEFINED = re.compile(r"undefined reference to [`'‘]([^'’]+)['’]")
_ENTRY_POINTS = {"main", "WinMain", "WinMain@16", "wmain"}


def release_has_logs(samples) -> bool:
    """A release that ships at least one log ran the compiler on every sample: an empty log then means 'no error'."""
    return any((s.compile_log or "").strip() for s in samples)


def compile_verdict(log: str | None, logs_informative: bool) -> str:
    log = (log or "").strip()
    if not log:
        return OK if logs_informative else UNKNOWN
    if _COMPILER_ERROR.search(log):
        return ERROR
    if any(name not in _ENTRY_POINTS for name in _UNDEFINED.findall(log)):
        return ERROR  # a declared function without a body: the build really fails
    return OK  # warnings, or only the missing entry point


def sample_log(sample, logs_informative: bool) -> tuple[str | None, bool]:
    """(log, informative) for one sample. An empty file has no evidence either way (no teacher-graded example):
    no verdict, the model decides as before."""
    if not sample.code.strip():
        return None, False
    return sample.compile_log, logs_informative


def compile_section(log: str | None, logs_informative: bool, max_warnings: int = 5) -> str:
    """Prompt text for the compile result: the verdict first, then only the lines that matter."""
    verdict = compile_verdict(log, logs_informative)
    log = re.sub(r"/tmp/tmp\w+/", "", (log or "")).strip()
    if verdict == UNKNOWN:
        return "(không có thông tin biên dịch)"
    if verdict == ERROR:
        errors = compile_errors_only(log)[:COMPILE_LOG_MAX_CHARS]
        return ("KẾT LUẬN: KHÔNG biên dịch được (g++ báo lỗi) -> compilable = 0.\n" + errors).strip()
    lines = ["KẾT LUẬN: biên dịch được (g++ không báo lỗi cú pháp) -> compilable = 1."]
    if _UNDEFINED.search(log):
        lines.append("Ghi chú: trình liên kết không tìm thấy hàm main. Đây KHÔNG phải lỗi biên dịch: "
                     "giảng viên vẫn chấm bài bình thường theo nội dung code.")
    warnings = list(dict.fromkeys(_WARNING.findall(log)))
    if warnings:
        lines.append("Cảnh báo (không làm mất điểm compilable, nhưng có thể chỉ ra lỗi logic, ví dụ hàm thiếu return):")
        lines += warnings[:max_warnings]
    return "\n".join(lines)
