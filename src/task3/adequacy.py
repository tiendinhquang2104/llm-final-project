"""Bounded source-relation recognizer; specificity is not factual correctness."""
from __future__ import annotations

import re
from src.task3.compliance import check, _without_diacritics


def _code_only(code):
    # Keep only identifiers in code, excluding comments and literals. This is a
    # surface relation check, not an AST/type/entailment proof.
    stripped = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', ' ', code, flags=re.S)
    return stripped


def _identifiers(code):
    return set(re.findall(r'\b[A-Za-z_]\w*\b', _code_only(code)))


def _declared(code):
    return set(re.findall(r'\b(?:int|long|short|char|bool|float|double|auto|string|size_t)\s+(?:(?:long|int|const|unsigned)\s+)*[*&\s]*([A-Za-z_]\w*)', _code_only(code)))


def assess_repair_action(record, feedback, *, source_quote=None):
    """Recognize a bounded loop-bound/value relation, never assess correctness.

    A declaration with no bound/value binding is deliberately generic. Unknown
    repair families fail closed instead of earning specificity from an action verb.
    """
    guard = check(feedback, 3, version=2)
    if 'complete_solution' in guard.violations:
        return {'kind':'complete_solution', 'relations':[], 'factual_support':'not_assessed'}
    if 'code_block_gt_1_line' in guard.violations:
        return {'kind':'disallowed_code', 'relations':[], 'factual_support':'not_assessed'}
    if re.search(r'hướng sửa\s*:', feedback, re.I):
        action = re.split(r'hướng sửa\s*:', feedback, flags=re.I)[-1]
    else:
        action = '\n'.join(s for s in re.split(r'(?<=[.!?])\s+|\n', feedback) if re.search(r'(?i)\b(?:hãy|nên|cần|khai báo|khởi tạo|đổi|thay|dùng|sử dụng|gán|đặt|cập nhật)\b', s) and not re.search(r'(?i)(?:chưa|không)\s+(?:được\s+)?khai báo', s))
    normalized = _without_diacritics(action).casefold()
    identifiers = _identifiers(record.code)
    declared = _declared(record.code)
    scope = source_quote if source_quote is not None else record.code
    relations = []
    # The target comes from the actual source comparison, not a name in the
    # feedback. A reference must already be declared in the supplied source.
    for condition in re.findall(r'\bfor\s*\([^;]*;([^;]+);', scope):
        target_match = re.search(r'[<>]=?\s*([A-Za-z_]\w*)\b', condition)
        if not target_match:
            continue
        target = target_match[1]
        for reference in sorted(declared - {target}):
            if not re.search(r'\b'+re.escape(reference)+r'\b', action):
                continue
            # Accept positive directed bindings, not disconnected word presence.
            # Negation/other expression families remain unsupported, fail closed.
            negated = bool(re.search(r"(?:^|[.!?;]\s*|\n)\s*(?:(?:hãy|nên|cần)\s+)?(?:không|đừng|chưa|tránh|not|never)\b", action, re.I))
            target_text = re.escape(target.casefold())
            reference_text = re.escape(reference.casefold())
            plain = normalized.replace('`', '').replace("'", '')
            clause = r"(?:^|[.!?;]\s*|\n)\s*(?:(?:hay|nen|can)\s+)?"
            binding = bool(re.search(
                clause + r"(?:khai bao(?: va khoi tao)?|khoi tao|gan|dat(?: gia tri)?|doi(?: ten bien)?|thay)\s+"
                r"(?:bien\s+)?" + target_text + r"\s+(?:(?:gia tri\s+)?bang|thanh)\s+"
                r"(?:(?:gia tri(?: da co)?(?: cua)?)\s+)?" + reference_text +
                r"\b(?=\s*(?:[.!?;]|$|truoc\b|sau\b|de\b|o\b|trong\b))", plain))
            assignment = bool(re.search(r"(?:^|[;\n])\s*(?:(?:int|long|auto)\s+)?" + target_text + r"\s*=\s*" + reference_text + r"\s*(?:;|$)", plain))
            bound_value = bool(re.search(
                clause + r"(?:dung|su dung)\s+(?:(?:gia tri(?: da co)?(?: cua)?|[a-z]+(?:-[a-z]+)+|bien)\s+)?" +
                reference_text + r"\s+lam\s+(?:can|bound|gioi han)\b", plain))
            if target in identifiers and not negated and (binding or assignment or bound_value):
                relations.append({'target':target,'reference':reference,'relation':'loop_bound_from_existing_value'})
    return {'kind':'specific' if relations else 'generic' if action.strip() else 'missing',
            'relations':relations, 'factual_support':'not_assessed',
            'limitations':'Surface source binding only; does not prove the chosen reference or claims are correct.'}
