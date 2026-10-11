"""Texts the CLM encoder sees for Task 2, in the layout its heads were trained on (context first, question last).

Each (submission, label) pair is a CLM `noul` question: state = context + "\\n\\n" + question; candidates =
"false: No. This is false: <question>" / "true: Yes. This is true: <question>" (clm.schema.candidates).
The encoder keeps only the first `max_tokens` tokens, so we cut the context ourselves to keep the question.
"""
from __future__ import annotations

import re

from src.task2.labels import DESCRIPTIONS, LABELS

CUT = "\n// ...(cắt bớt)...\n"
SLACK = 8  # tokens of margin for BPE merges across concatenation boundaries


def label_question(label: str) -> str:
    return f'Bài nộp trên có mắc lỗi "{label}" không? {label}: {DESCRIPTIONS[label]}'


def candidate_texts(label: str) -> tuple[str, str]:
    q = label_question(label)
    return f"false: No. This is false: {q}", f"true: Yes. This is true: {q}"


def head_truncate(text: str, n: int, tok) -> str:
    ids = tok.encode(text)
    if len(ids) <= n:
        return text
    return tok.decode(ids[:max(0, n - len(tok.encode(CUT)))]) + CUT


def middle_truncate(text: str, n: int, tok) -> str:
    ids = tok.encode(text)
    if len(ids) <= n:
        return text
    keep = max(0, n - len(tok.encode(CUT)))
    head = keep // 2
    return tok.decode(ids[:head]) + CUT + tok.decode(ids[len(ids) - (keep - head):])


def compile_block(sample, tok, max_compile_tokens: int) -> str:
    """Self-compiled g++ output (organizer tmp dir prefix removed). None = not compiled -> no block."""
    log = getattr(sample, "compile_log", None)
    if log is None:
        return ""
    log = re.sub(r"/tmp/tmp\w+/", "", log).strip()
    if not log:
        return "\n\nKết quả biên dịch: không có lỗi hay cảnh báo."
    return "\n\nKết quả biên dịch (g++ -std=c++11):\n" + head_truncate(log, max_compile_tokens, tok)


def context_text(exam: dict, sample, tok, budget: int, max_statement_tokens: int = 512,
                 use_compile_log: bool = False, max_compile_tokens: int = 256) -> str:
    """Exam header + (truncated) statement [+ self-compiled log] + student code, at most ~`budget` tokens. The
    compile block sits before the code so the code's middle cut never removes it. No organizer compile_log/
    test_report: with_compile_logs overwrites them, so training and test inputs look alike."""
    head = f"Đề bài {exam['exam_id']} ({exam['exam_type']}, môn {exam.get('course', '')}):\n"
    statement = head_truncate(exam.get("statement", "").strip(), max_statement_tokens, tok)
    mid = "\n\nBài nộp C++ của sinh viên:\n"
    block = compile_block(sample, tok, max_compile_tokens) if use_compile_log else ""
    used = len(tok.encode(head + statement + block + mid))
    return head + statement + block + mid + middle_truncate(sample.code, max(32, budget - used), tok)


def build_state_texts(exam: dict, sample, tok, max_tokens: int = 2048, max_statement_tokens: int = 512,
                      use_compile_log: bool = False, max_compile_tokens: int = 256) -> dict:
    questions = {lab: label_question(lab) for lab in LABELS}
    q_tokens = max(len(tok.encode("\n\n" + q)) for q in questions.values())
    kw = {"use_compile_log": use_compile_log, "max_compile_tokens": max_compile_tokens}
    ctx_q = context_text(exam, sample, tok, max_tokens - q_tokens - SLACK, max_statement_tokens, **kw)
    return {"context": context_text(exam, sample, tok, max_tokens - SLACK, max_statement_tokens, **kw),
            "questions": {lab: f"{ctx_q}\n\n{q}" for lab, q in questions.items()}}
