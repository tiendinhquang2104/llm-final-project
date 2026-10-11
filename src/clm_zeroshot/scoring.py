"""Generic zero-shot CLM scoring: question states, yes/no candidates, softmax over candidates. No training."""
from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from src.task2.clm.text import SLACK, context_text


def question_states(exam: dict, sample, tok, questions: list[str], text_cfg: dict) -> list[str]:
    """`context + "\\n\\n" + question` per question; the context is cut so the longest question still fits."""
    max_tokens = int(text_cfg.get("max_tokens", 2048))
    q_tokens = max(len(tok.encode("\n\n" + q)) for q in questions)
    ctx = context_text(exam, sample, tok, max_tokens - q_tokens - SLACK,
                       int(text_cfg.get("max_statement_tokens", 512)),
                       bool(text_cfg.get("use_compile_log", False)), int(text_cfg.get("max_compile_tokens", 256)))
    return [f"{ctx}\n\n{q}" for q in questions]


def noul_candidates(question: str) -> tuple[str, str]:
    """(false, true) candidate texts in CLM's `noul` format."""
    return f"false: No. This is false: {question}", f"true: Yes. This is true: {question}"


def choice_probs(heads, S: np.ndarray, C: np.ndarray) -> np.ndarray:
    """softmax over the k candidates of scale * cos(state(l2(S)), action(l2(C))) -> [n, k]."""
    with torch.no_grad():
        s = F.normalize(heads.state(F.normalize(torch.as_tensor(S, dtype=torch.float32), dim=-1)), dim=-1)
        c = F.normalize(heads.action(F.normalize(torch.as_tensor(C, dtype=torch.float32), dim=-1)), dim=-1)
        return torch.softmax(heads.scale() * (s @ c.T), dim=-1).numpy()


def noul_prob(heads, S: np.ndarray, C_false_true: np.ndarray) -> np.ndarray:
    """P(true) of the 2-way softmax -> [n]."""
    return choice_probs(heads, S, C_false_true)[:, 1]
