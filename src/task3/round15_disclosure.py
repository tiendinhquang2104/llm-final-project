"""Round15 surface disclosure screen, separate from JSON/schema validation.

Only Levels 1/2 have content rejections. Passing these small language patterns
establishes neither correctness nor compliance with every disclosure rule.
Audit cues are observations for review, never rejection reasons or assessments
of factual accuracy, relevance, coherence, or pedagogical adequacy.
"""

from __future__ import annotations

import re
import unicodedata


_INLINE_QUOTE = re.compile(r'(?<!`)`[^`\n]+`(?!`)|"[^"\n]*"|\'[^\'\n]*\'')
_FENCE = re.compile(r'^\s*(?:```|~~~)', re.M)
_CODE = re.compile(
    r'#\s*include|\b(?:int|long|bool|void|auto)\s+\w+\s*\([^)]*\)\s*\{'
    r'|(?:^|\n)\s*(?:return\b[^\n]*;|\w+\s*=\s*[^\n]*;'
    r'|(?:for|while|if)\s*\(|(?:std::)?(?:cout|cin)\s*(?:<<|>>))',
    re.I,
)
_REPAIR = re.compile(
    r'\b(?:thay|doi|sua|replace|change)\b[^\n.!?]{0,100}\b(?:thanh|bang|to|with)\b'
    r'|\b(?:de sua|cach sua|fix(?: it)? by|loi giai la|dap an la)\b'
    r'|\b(?:them|bo sung|chen|xoa|bo|sua lai|viet lai|khai bao|khoi tao)\s+'
    r'(?:(?:mot|cac|cau|tu|phan|lenh|dong)\s+){0,3}'
    r'(?:return|break|continue|code|ma|ham|bien|dieu kien|vong lap|lenh|dong|dau)\b'
    r'|\b(?:add|insert|remove|rewrite|declare|initialize|use)\s+'
    r'(?:(?:a|an|the|new|missing|final)\s+){0,3}'
    r'(?:return|statement|line|function|variable|condition|loop|code)\b'
    r'|\b(?:hay|nen|can|phai)\s+(?:dung|su dung|thay|doi|sua)\s+[`\'"]?'
    r'(?:return|ham|bien|lenh|dieu kien|vong lap|code|ma)\b',
)
_LOCATION = re.compile(r'\b(?:dong|line)\s*\d+|\bP\d+\b|\S+\.(?:cpp|cc|c|h|hpp):\d+', re.I)
_IDENTIFIER = re.compile(
    r'`[^`\n]+`|\b(?:ham|function|bien|variable)\s+'
    r'(?!(?:khong|chua|nay|cua|da|bi|con|tra|o|trong|thieu|cuoi|duoc)\b)[a-z_]\w*'
    r'|\b[a-z_]\w*\s*\(',
)
_DIAGNOSIS = re.compile(
    r'\b(?:vi|because|nguyen nhan|off.by.one|return)\b'
    r'|\b(?:vong lap|loi bien dich|loi logic|truy cap ngoai|phep chia|phep lay du)\b'
    r'|\b(?:thieu|thua|sai)\s+(?:dau|dinh dang|ky tu|dieu kien|bien)\b',
)


def _normalized(text: str) -> str:
    value = unicodedata.normalize('NFD', text)
    return ''.join(char for char in value if unicodedata.category(char) != 'Mn').replace('đ', 'd').replace('Đ', 'D').casefold()


def _validate_level(level: int) -> None:
    if isinstance(level, bool) or not isinstance(level, int) or level not in (1, 2, 3, 4):
        raise ValueError('level must be an integer from 1 to 4')


def disclosure_violations(text: str, level: int) -> list[str]:
    """Return explicit Level1/2 surface disclosures; Level3/4 always return [].

    Level2 may quote identifiers, source expressions, and compiler diagnoses.
    Explicit repair language is checked with quoted content retained,
    so wrapping suggested replacement code in quotes does not exempt a repair.
    This is a limited heuristic screen, not a semantic or factual verifier.
    """
    _validate_level(level)
    if level >= 3:
        return []

    normalized = _normalized(text)
    violations = []
    if _REPAIR.search(normalized.translate(str.maketrans('', '', '`\"\''))):
        violations.append('explicit_repair_disclosure')
    code_text = text
    if level == 2:
        code_text = _INLINE_QUOTE.sub('', code_text)
        # Numbered compiler source quotations are diagnosis, not proposed code.
        # Keep all text for the repair screen and all Level1 disclosure checks.
        code_text = re.sub(r'^\s*\d+\s*[|│].*$', '', code_text, flags=re.M)
    if _FENCE.search(text) or _CODE.search(code_text):
        violations.append('code_solution_disclosure')
    if level == 1:
        if _LOCATION.search(normalized):
            violations.append('level1_location_disclosure')
        identifier_text=re.sub(r'\bham\s+(?:can thiet|phu hop|tuong ung)\b','chuc nang',normalized)
        if _IDENTIFIER.search(identifier_text):
            violations.append('level1_identifier_disclosure')
        if _DIAGNOSIS.search(normalized):
            violations.append('level1_diagnosis_disclosure')
    return violations


def audit_flags(text: str, level: int) -> list[str]:
    """Return optional surface cues for human review; never rejection reasons.

    Cue presence or absence does not establish truth, completeness, coherence,
    relevance, or the adequacy of the advice. No model or code is evaluated.
    """
    _validate_level(level)
    normalized = _normalized(text)
    flags = []
    if re.search(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]', text):
        flags.append('contains_cjk')
    if re.search(r'\b(?:tot lam|khoi dau tot|rat tot|good job|well done|excellent)\b', normalized):
        flags.append('praise_cue')
    if re.search(r'\b(?:doc ky de|kiem tra lai|on luyen|check again|review your work)\b', normalized):
        flags.append('generic_advice_cue')
    if re.search(r'\b(?:loi giai hoan chinh|complete solution)\b|\b(?:int|void)\s+main\s*\(', normalized):
        flags.append('complete_solution_cue')
    return flags
