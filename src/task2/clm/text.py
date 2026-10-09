"""Texts the CLM encoder sees for Task 2, in the layout its heads were trained on (context first, question last).

Each (submission, label) pair is a CLM `noul` question: state = context + "\\n\\n" + question; candidates =
"false: No. This is false: <question>" / "true: Yes. This is true: <question>" (clm.schema.candidates).
The encoder keeps only the first `max_tokens` tokens, so we cut the context ourselves to keep the question.
"""
from __future__ import annotations

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


def context_text(exam: dict, sample, tok, budget: int, max_statement_tokens: int = 512) -> str:
    """Exam header + (truncated) statement + student code, at most ~`budget` tokens. No compile_log/test_report:
    the public test has neither, so training and test inputs look alike."""
    head = f"Đề bài {exam['exam_id']} ({exam['exam_type']}, môn {exam.get('course', '')}):\n"
    statement = head_truncate(exam.get("statement", "").strip(), max_statement_tokens, tok)
    mid = "\n\nBài nộp C++ của sinh viên:\n"
    used = len(tok.encode(head + statement + mid))
    return head + statement + mid + middle_truncate(sample.code, max(32, budget - used), tok)


def build_state_texts(exam: dict, sample, tok, max_tokens: int = 2048, max_statement_tokens: int = 512) -> dict:
    questions = {lab: label_question(lab) for lab in LABELS}
    q_tokens = max(len(tok.encode("\n\n" + q)) for q in questions.values())
    ctx_q = context_text(exam, sample, tok, max_tokens - q_tokens - SLACK, max_statement_tokens)
    return {"context": context_text(exam, sample, tok, max_tokens - SLACK, max_statement_tokens),
            "questions": {lab: f"{ctx_q}\n\n{q}" for lab, q in questions.items()}}
