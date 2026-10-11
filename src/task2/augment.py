"""Task 2 training-data augmentation: inject one known bug type into LABELLED gold code.

Only labelled training samples (sample_dataset) are mutated — never test inputs (instructor ruling 2026-10-11:
no labels derived from the test set). The injected label is known by construction; the mutant keeps the source
sample's own labels as well. compile_log/test_report are cleared because they no longer describe the code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable

from src.task2.labels import normalize_labels


@dataclass(frozen=True)
class Mutator:
    name: str
    label: str
    apply: Callable[[str], "str | None"]  # None = rule not applicable to this code


def _sub_first(pattern: str, repl, code: str, flags: int = 0) -> str | None:
    new, n = re.subn(pattern, repl, code, count=1, flags=flags)
    return new if n and new != code else None


def drop_return_semicolon(code: str) -> str | None:
    return _sub_first(r"(\breturn\b[^;\n{}]*);", r"\1", code)


def alter_output_text(code: str) -> str | None:
    return _sub_first(r'(\bcout\s*<<\s*"|\bprintf\s*\(\s*")', r"\1Ket qua: ", code)


_SWAP = {"==": "!=", "!=": "==", ">=": "<", "<=": ">", ">": "<=", "<": ">="}


def flip_if_comparison(code: str) -> str | None:
    return _sub_first(r"(\bif\s*\([^()\n]*?\s)(==|!=|>=|<=|>|<)(\s)",
                      lambda m: m.group(1) + _SWAP[m.group(2)] + m.group(3), code)


def flip_loop_bound(code: str) -> str | None:
    return _sub_first(r"(\bfor\s*\([^;]*;[^;<>]*?)(<=|<)([^;]*;)",
                      lambda m: m.group(1) + ("<" if m.group(2) == "<=" else "<=") + m.group(3), code)


def off_by_one_size(code: str) -> str | None:
    return _sub_first(r"(\.(?:size|length)\(\)|\bstrlen\s*\([^()]*\))", r"\1 + 1", code)


def drop_reference_param(code: str) -> str | None:
    return _sub_first(r"([(,]\s*(?:const\s+)?[\w:<>*]+)\s*&\s*(\w+)", r"\1 \2", code)


_GUARD = re.compile(r"^[ \t]*if\s*\((?:[^()\n]|\([^()\n]*\))*(?:==\s*0|<=\s*0|<\s*1|==\s*NULL|==\s*nullptr|!\s*\w+)"
                    r"\s*\)[^\n]*\n", re.M)


def _cut_guard(code: str, m: re.Match) -> str | None:
    line, end = m.group(0).rstrip(), m.end()
    if line.endswith(")"):  # body on the next line: one statement or a flat { } block
        nxt = re.match(r"[ \t]*\{[^{}]*\}[ \t]*\n|[ \t]*[^\n]*;[ \t]*\n", code[end:])
        if nxt:
            end += nxt.end()
    elif line.endswith("{"):  # flat block opened on the guard line; its closing brace must sit on its own line
        close = code.find("}", end)
        if close == -1 or "{" in code[end:close]:
            return None
        nl = code.find("\n", close)
        nl = len(code) if nl == -1 else nl
        if code[code.rfind("\n", 0, close) + 1:nl].strip() != "}":
            return None
        end = min(len(code), nl + 1)
    if re.match(r"\s*else\b", code[end:]):  # removing the guard would orphan an else branch
        return None
    return code[:m.start()] + code[end:]


def remove_edge_guard(code: str) -> str | None:
    """Delete the first edge-case guard (n == 0, n <= 0, ptr == NULL, !ptr, ...) and its body, if removable."""
    for m in _GUARD.finditer(code):
        new = _cut_guard(code, m)
        if new is not None:
            return new
    return None


def hardcode_return(code: str) -> str | None:
    """First non-main function returning a computed value now returns a constant."""
    for m in re.finditer(r"\b(?:int|bool|long|double|float)\s+(\w+)\s*\([^)]*\)\s*\{", code):
        if m.group(1) == "main":
            continue
        r = re.compile(r"\breturn\s+(?!0;|1;|true;|false;)[^;\n]+;").search(code, m.end())
        if r:
            return code[:r.start()] + "return 1;" + code[r.end():]
    return None


def strip_indentation(code: str) -> str | None:
    new = "\n".join(line.strip() for line in code.splitlines() if line.strip()) + "\n"
    return new if new != code else None


MUTATORS: tuple[Mutator, ...] = (
    Mutator("drop_return_semicolon", "Lỗi biên dịch", drop_return_semicolon),
    Mutator("alter_output_text", "Lỗi nhập/xuất", alter_output_text),
    Mutator("flip_if_comparison", "Lỗi logic", flip_if_comparison),
    Mutator("flip_loop_bound", "Lỗi vòng lặp", flip_loop_bound),
    Mutator("off_by_one_size", "Lỗi mảng/chuỗi", off_by_one_size),
    Mutator("drop_reference_param", "Lỗi hàm", drop_reference_param),
    Mutator("remove_edge_guard", "Lỗi edge case", remove_edge_guard),
    Mutator("hardcode_return", "Lỗi hard-code", hardcode_return),
    Mutator("strip_indentation", "Lỗi style", strip_indentation),
)


def source_id(sample_id: str) -> str:
    """Id of the gold sample a mutant was made from (the id itself for non-mutants)."""
    return sample_id.split("~", 1)[0]


def augment(samples, mutators=MUTATORS, max_per_mutator: int | None = None) -> list:
    """One mutant per (labelled sample, applicable mutator), sorted by sample id, at most `max_per_mutator` each."""
    out = []
    for mu in mutators:
        made = 0
        for s in sorted(samples, key=lambda s: s.sample_id):
            if max_per_mutator is not None and made >= max_per_mutator:
                break
            if not s.has_gold:
                continue
            new = mu.apply(s.code)
            if new is None:
                continue
            out.append(replace(s, sample_id=f"{s.sample_id}~{mu.name}", code=new, compile_log=None,
                               test_report=None, labels=normalize_labels([*s.labels, mu.label])))
            made += 1
    return out
