"""Grade a multi_problem submission one question at a time (prompt.split_problems).

Each question Pk gets its own prompt: the whole statement (questions refer to each other, e.g. "the list created in
Problem 2", and shared structs sit inside earlier sections; it is ~1k tokens) plus the code that matters for Pk:
everything outside function bodies (includes, structs, globals, prototypes), probK and the functions it calls,
directly or not. The bodies of the other questions and of unrelated helpers are hidden; line numbers stay those of
the submission. If probK is not defined, nothing but the other questions is hidden (the attempt may sit in a helper).

The answers are merged by `merge_parts`, following `is_prerequisite_for` in exams.json: a question is graded only if
none of its prerequisites (transitively) has an error; labels are the union over the graded questions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.task2.prompts_cot import ALL_COMMENTED, HIDDEN, strip_comments

_HEADING = re.compile(r"^[ \t#>*_]*(?:problem|question|exercise|câu|bài)\s*(\d+)\b", re.I | re.M)
_IDENT = re.compile(r"[A-Za-z_]\w*")
_NAME = re.compile(r"([A-Za-z_]\w*)\s*\(")
_NOT_FUNC = {"if", "for", "while", "switch", "return", "sizeof", "catch", "else", "do", "case", "new", "delete"}


@dataclass
class FuncDef:
    name: str
    start: int   # 1-based first line (return type line when it stands alone above the name)
    end: int     # 1-based line of the closing brace
    calls: set = field(default_factory=set)


@dataclass
class Part:
    pid: str
    func: str | None          # prototype function name (probK), None when the prototype has none
    found: bool               # probK is defined in the submission
    code: str                 # submission with hidden lines replaced by HIDDEN
    lines: set                # 1-based visible lines
    own: set                  # 1-based lines of probK's definition(s)


def statement_for(statement: str, problems: list[dict], pid: str) -> str:
    """The statement without the sections of the questions after `pid` (a later question is never a prerequisite;
    earlier sections stay, they hold shared structs and the lists later questions reuse). The full statement when
    its question headings ("**Problem 1 (1 điểm).**", "## Câu 2", ...) do not match the problems one to one."""
    pids = [p.get("pid") for p in problems]
    heads = [m for m in _HEADING.finditer(statement or "")]
    if pid not in pids or len(heads) != len(pids) or [int(m.group(1)) for m in heads] != list(range(1, len(pids) + 1)):
        return statement
    k = pids.index(pid)
    return statement if k + 1 == len(heads) else statement[:heads[k + 1].start()].rstrip() + "\n"


def _skip_literal(code: str, i: int) -> int:
    q = code[i]
    i += 1
    while i < len(code) and code[i] != q:
        i += 2 if code[i] == "\\" else 1
    return i + 1


def _match(code: str, i: int, open_c: str, close_c: str) -> int:
    """Index after the bracket matching code[i] (== open_c); len(code) when unbalanced."""
    depth = 0
    while i < len(code):
        c = code[i]
        if c in "\"'":
            i = _skip_literal(code, i)
            continue
        if c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(code)


def function_defs(code: str) -> list[FuncDef]:
    """Top-level function definitions (not inside a struct/class/namespace body) of comment-free code."""
    defs, i, depth = [], 0, 0
    line_of = lambda k: code.count("\n", 0, k) + 1  # noqa: E731
    while i < len(code):
        c = code[i]
        if c in "\"'":
            i = _skip_literal(code, i)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        elif depth == 0 and (c.isalpha() or c == "_") and (i == 0 or not (code[i - 1].isalnum() or code[i - 1] == "_")):
            m = _IDENT.match(code, i)
            name, j = m.group(), m.end()
            k = j
            while k < len(code) and code[k] in " \t\r\n":
                k += 1
            if name not in _NOT_FUNC and k < len(code) and code[k] == "(":
                after = _match(code, k, "(", ")")
                b = after
                while b < len(code) and (code[b] in " \t\r\n" or _IDENT.match(code, b)):
                    b = _IDENT.match(code, b).end() if _IDENT.match(code, b) else b + 1  # const / noexcept
                if b < len(code) and code[b] == "{":
                    end = _match(code, b, "{", "}")
                    start = line_of(i)
                    bol = code.rfind("\n", 0, i) + 1
                    if not code[bol:i].strip() and start > 1:  # "General*\nprob1(...)": return type on the line above
                        prev = code.rfind("\n", 0, bol - 1) + 1
                        if code[prev:bol - 1].strip() and not code[prev:bol - 1].rstrip().endswith((";", "}", "{")):
                            start -= 1
                    body = code[b:end]
                    defs.append(FuncDef(name, start, line_of(end - 1),
                                        {n for n in _NAME.findall(body) if n not in _NOT_FUNC}))
                    i = end
                    continue
            i = j
            continue
        i += 1
    return defs


def _func_name(prototype: str | None) -> str | None:
    m = _NAME.search(prototype or "")
    return m.group(1) if m else None


def split_submission(code: str, problems: list[dict]) -> list[Part] | None:
    """One Part per problem with a prototype, or None when the submission cannot be split (no prototypes, the whole
    code commented out, or no probK defined at all)."""
    names = [(p.get("pid"), _func_name(p.get("prototype"))) for p in problems]
    if not names or any(n is None for _, n in names):
        return None
    clean = strip_comments(code)
    if clean == ALL_COMMENTED or not clean.strip():
        return None
    defs = function_defs(clean)
    by_name: dict[str, list[FuncDef]] = {}
    for d in defs:
        by_name.setdefault(d.name, []).append(d)
    if not any(n in by_name for _, n in names):
        return None
    prob_names = {n for _, n in names}
    n_lines = clean.count("\n") + 1
    in_func = {ln for d in defs for ln in range(d.start, d.end + 1)}
    parts = []
    for pid, name in names:
        found = name in by_name
        if found:  # probK plus every function it reaches, other questions excluded
            keep, todo = set(), [name]
            while todo:
                f = todo.pop()
                if f in keep or (f in prob_names and f != name):
                    continue
                keep.add(f)
                todo.extend(c for d in by_name.get(f, []) for c in d.calls if c in by_name)
            shown = {ln for d in defs if d.name in keep for ln in range(d.start, d.end + 1)}
            visible = {ln for ln in range(1, n_lines + 1) if ln not in in_func} | shown
        else:      # not defined: hide only the other questions
            others = {ln for d in defs if d.name in prob_names for ln in range(d.start, d.end + 1)}
            visible = {ln for ln in range(1, n_lines + 1) if ln not in others}
        own = {ln for d in by_name.get(name, []) for ln in range(d.start, d.end + 1)}
        lines = clean.split("\n")  # comment-free: a hidden line never splits a /* */ pair
        masked = "\n".join(line if i in visible else HIDDEN for i, line in enumerate(lines, 1))
        parts.append(Part(pid, name, found, masked, visible, own))
    return parts


_ERR_LINE = re.compile(r"^\S*?student\.cpp:(\d+):\d+: (?:fatal )?error:", re.M)


def compile_error_lines(log: str | None) -> set:
    return {int(n) for n in _ERR_LINE.findall(log or "")}


def prerequisites(problems: list[dict]) -> dict[str, set]:
    """pid -> every question that must be right before it is graded (transitive closure of is_prerequisite_for)."""
    direct: dict[str, set] = {p["pid"]: set() for p in problems if p.get("pid")}
    for p in problems:
        for q in p.get("is_prerequisite_for") or []:
            direct.setdefault(q, set()).add(p["pid"])
    out = {}
    for pid in direct:
        seen, todo = set(), list(direct[pid])
        while todo:
            a = todo.pop()
            if a not in seen:
                seen.add(a)
                todo.extend(direct.get(a, ()))
        out[pid] = seen
    return out


def merge_parts(problems: list[dict], part_labels: dict[str, list[str]], failed_extra: set = frozenset()) -> tuple:
    """(labels, graded pids): a question is graded when none of its prerequisites failed; a question failed when its
    answer has a label or it is in `failed_extra` (a compiler error inside its own lines). Union of graded labels,
    in the order of the questions."""
    pre = prerequisites(problems)
    failed = {pid for pid, labs in part_labels.items() if labs} | set(failed_extra)
    graded = [p["pid"] for p in problems if p.get("pid") in part_labels and not (pre.get(p["pid"], set()) & failed)]
    labels = []
    for pid in graded:
        for lab in part_labels[pid]:
            if lab not in labels:
                labels.append(lab)
    return labels, graded
