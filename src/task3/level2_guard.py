"""Optional offline Level2 repair-language screen, never a semantic verifier.

It rejects whole responses and delegates retries/fallback to R15. It never
removes words, repairs prose, checks truth, or certifies source grounding.
"""
from __future__ import annotations
import re
from src.task3.round15_disclosure import disclosure_violations as old_screen, _normalized

VERSION = 'level2-explicit-actions-v1'
_ACTION = r'(?:them|bo sung|chen|xoa|bo|doi|thay|sua|dung|su dung|khoi tao|khai bao|chuyen|viet lai|kiem tra|duyet|giam|tang|la kieu)'
_MODAL = re.compile(r'(?<!khong )\b(?:hay|nen|can|phai)\s+' + _ACTION + r'\b')
_IMPERATIVE = re.compile(r'(?:^|[.!?]\s+)\s*' + _ACTION + r'\b(?!\s+vi\b)')
_REPLACEMENT = re.compile(r'\b(?:thay|doi|sua|replace|change)\s+(?!vi\b)[^\n]{1,140}\b(?:thanh|bang|to|with)\b')


def disclosure_violations(text: str, level: int) -> list[str]:
    result = old_screen(text, level)
    if level != 2:
        return result
    normalized = _normalized(text).translate(str.maketrans('', '', '`\"\''))
    if (_MODAL.search(normalized) or _IMPERATIVE.search(normalized)
            or _REPLACEMENT.search(normalized)):
        if 'explicit_repair_disclosure' not in result:
            result.append('explicit_repair_disclosure')
    return result
