"""Defect injection (synth_plan.md section "Thư viện defect", implementation step 5).

Each mutator is a pure ``(code, ctx) -> str | None`` transform that injects exactly one defect
from the library in src/synth/taxonomy.py; ``None`` means "not applicable to this code, pick
another". Labels are *derived from the defect*, then verified by running the mutant against the
hand-written standard tests (src/synth/verify.py) — never assigned by an LLM.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Optional

Transform = Callable[[str, dict], Optional[str]]

# C++ keywords and standard-library names a rename must never touch (renaming them breaks the
# program: the old ``#include <x0>`` / ``x0 x2`` bug came from renaming ``string``).
CPP_RESERVED = frozenset("""
alignas alignof and asm auto bool break case catch char class const constexpr continue decltype default
delete do double else enum explicit extern false float for friend goto if inline int long mutable namespace
new noexcept not nullptr operator or private protected public register return short signed sizeof static
struct switch template this throw true try typedef typename union unsigned using virtual void volatile while
include define std main cout cin cerr endl string vector map set pair ifstream ofstream fstream istream
ostream stringstream istringstream getline stoi stof stol stod to_string size length push_back begin end
substr find erase insert clear empty abs sqrt pow max min swap sort reverse iostream cstring cmath sstream
algorithm iomanip cstdio cstdlib printf scanf NULL filename eof good open close is_open
""".split())


def _occurrence(ctx: dict) -> int:
    return int(ctx.get("occurrence", 0) or 0)


def _code_spans(code: str):
    """(start, end) of lines that are real code: not preprocessor lines, not comments."""
    pos = 0
    for line in code.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "//")):
            yield pos, pos + len(line)
        pos += len(line)


def _find(pattern: re.Pattern, code: str, ctx: dict):
    """The ``occurrence``-th match of ``pattern`` that lies on a code line (wraps around)."""
    hits = [m for a, b in _code_spans(code) for m in pattern.finditer(code, a, b)]
    if not hits:
        return None
    return hits[_occurrence(ctx) % len(hits)]


@dataclass(frozen=True)
class Mutator:
    defect_id: str
    name: str
    transform: Transform
    exam_types: tuple[str, ...] = ("single_problem", "multi_problem")


def comment_all(code: str, ctx: dict) -> str:
    return "\n".join("// " + line for line in code.splitlines())


def empty_file(code: str, ctx: dict) -> str:
    return ""


def missing_semicolon(code: str, ctx: dict) -> Optional[str]:
    hits = []
    for m in re.finditer(r"^([ \t]*\S[^\n;{}()]*?);", code, re.MULTILINE):
        line = code[code.rfind("\n", 0, m.start()) + 1:m.end()]
        if "for (" in line or "for(" in line or line.lstrip().startswith(("#", "//", "using")):
            continue
        hits.append(m)
    if not hits:
        return None
    m = hits[_occurrence(ctx) % len(hits)]
    return code[:m.end() - 1] + code[m.end():]


def undeclare_variable(code: str, ctx: dict) -> Optional[str]:
    m = re.search(r"^[ \t]*(?:int|long long|long|double|float|bool|char)\s+(\w+)\s*[=;].*$", code, re.MULTILINE)
    if not m:
        return None
    start = m.start()
    end = code.find("\n", m.end())
    end = len(code) if end == -1 else end + 1
    return code[:start] + code[end:]


def remove_loop_increment(code: str, ctx: dict) -> Optional[str]:
    for pat in (r"^[ \t]*\w+\s*\+\+;[ \t]*\n", r"^[ \t]*\+\+\w+;[ \t]*\n",
                r"^[ \t]*\w+\s*=\s*\w+\s*-\>\s*next;[ \t]*\n", r"^[ \t]*\w+\s*=\s*\w+\s*\+\s*1;[ \t]*\n"):
        m = re.search(pat, code, re.MULTILINE)
        if m:
            return code[:m.start()] + code[m.end():]
    for pat in (r"(;)(\s*)(\w+)\+\+(\s*\))", r"(;)(\s*)\+\+(\w+)(\s*\))"):
        m = re.search(pat, code)
        if m:
            return code[:m.start()] + m.group(1) + m.group(2) + m.group(4) + code[m.end():]
    return None


def empty_function_body(code: str, ctx: dict) -> Optional[str]:
    name = ctx.get("function")
    if name:
        m = re.search(rf"({re.escape(name)}\s*\([^)]*\)\s*\{{)", code)
        if m:
            depth, i = 1, m.end()
            while i < len(code) and depth:
                depth += (code[i] == "{") - (code[i] == "}")
                i += 1
            return code[:m.end()] + "\n" + code[i:]
    m = re.search(r"(main\s*\([^)]*\)\s*\{)", code)
    if m:
        return code[:m.end()] + "\n    return 0;\n}" + code[code.find("}", m.end()) + 1:]
    return None


def extra_output_char(code: str, ctx: dict) -> Optional[str]:
    m = re.search(r"cout\s*<<", code)
    if not m:
        return None
    return code[:m.start()] + 'cout << " ";\n    ' + code[m.start():]


def wrong_token(code: str, ctx: dict) -> Optional[str]:
    for good, bad in (('"True"', '"TRUE"'), ('"False"', '"FALSE"'), ("'T'", "'t'"), ("'F'", "'f'")):
        if good in code:
            return code.replace(good, bad)
    return None


def include_data_file(code: str, ctx: dict) -> Optional[str]:
    name = ctx.get("data_file")
    if not name:
        return None
    return f'#include "{name}"\n' + code


def hardcode_filename(code: str, ctx: dict) -> Optional[str]:
    """D15: read a fixed file instead of the parameter (P1 prerequisite break).

    Replaces the *use* (e.g. ``ifstream f(filename)``), not the parameter declaration."""
    if "filename" not in code:
        return None
    literal = ctx.get("literal", '"data.csv"')
    idx = code.rfind("filename")
    return code[:idx] + literal + code[idx + len("filename"):]


def _user_identifiers(code: str) -> list[str]:
    """Identifiers declared by the student (variables/functions), most frequent first."""
    body = "\n".join(line for line in code.splitlines() if not line.lstrip().startswith("#"))
    body = re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*', " ", body)
    declared = re.findall(r"\b(?:int|long long|long|double|float|bool|char|string|auto|[A-Z]\w*)\s*[*&]?\s*"
                          r"([A-Za-z_]\w*)\s*(?=[=;,()\[])", body)
    # struct members and struct names are part of the exam's interface (the harness uses them)
    interface = set(re.findall(r"\bstruct\s+(\w+)", body))
    for members in re.findall(r"\bstruct\s+\w+\s*\{([^}]*)\}", body):
        interface |= set(re.findall(r"[A-Za-z_]\w*", members))
    counts = Counter(re.findall(r"\b([A-Za-z_]\w*)\b", body))
    names = [n for n in dict.fromkeys(declared)
             if n not in CPP_RESERVED and n not in interface and not n.startswith("prob")
             and len(n) > 1 and not n.startswith("__")]
    return sorted(names, key=lambda n: -counts[n])


def garbage_style(code: str, ctx: dict) -> Optional[str]:
    """D22/D23: meaningless names for the student's own identifiers + dead/debug code.

    Only identifiers the student declared are renamed (never keywords, std names or #include)."""
    candidates = _user_identifiers(code)[:5]
    if not candidates:
        return None
    out = code
    for i, n in enumerate(candidates):
        out = re.sub(rf"\b{re.escape(n)}\b", f"x{i + 1}", out)
    return out + "\n// TODO: refactor later\n// int tmp2 = 0; cout << tmp2;\n"


_COMPARE = {"<": "<=", "<=": "<", ">": ">=", ">=": ">"}
# a comparison operator with spaces/operands around it, not part of <<, >>, -> or a template
_COMPARE_RE = re.compile(r"(?<=[\w)\] ])\s(<=|>=|<|>)\s(?=[\w(\-])")


def flip_comparison(code: str, ctx: dict) -> Optional[str]:
    """D16b: make one boundary condition off-by-one (edge case wrong)."""
    m = _find(_COMPARE_RE, code, ctx)
    if not m:
        return None
    op = m.group(1)
    return code[:m.start(1)] + _COMPARE[op] + code[m.end(1):]


def flip_two_comparisons(code: str, ctx: dict) -> Optional[str]:
    """D16a: two off-by-one boundary errors (>=2 edge groups wrong)."""
    once = flip_comparison(code, ctx)
    if once is None:
        return None
    return flip_comparison(once, {**ctx, "occurrence": _occurrence(ctx) + 1}) or once


_ARITH_RE = re.compile(r"(?<=[\w)\]]) ?([*+%]) ?(?=[\w(])")
_TYPE_BEFORE_RE = re.compile(r"\b(?:[A-Z]\w*|int|char|string|long|double|float|bool|void|auto)\s*$")


def break_operator(code: str, ctx: dict) -> Optional[str]:
    """D08: corrupt a core arithmetic operator (wrong algorithm). Pointer declarators are skipped."""
    hits = []
    for a, b in _code_spans(code):
        for m in _ARITH_RE.finditer(code, a, b):
            if m.group(1) == "*" and _TYPE_BEFORE_RE.search(code[a:m.start(1)]):
                continue  # ``Rec* arr`` / ``int *p`` is a declaration, not a multiplication
            hits.append(m)
    if not hits:
        return None
    m = hits[_occurrence(ctx) % len(hits)]
    repl = {"*": "+", "+": "-", "%": "/"}[m.group(1)]
    return code[:m.start(1)] + repl + code[m.end(1):]


def wrong_token_and_logic(code: str, ctx: dict) -> Optional[str]:
    """D06: wrong output token AND the answer logic inverted (every answer wrong, EX02-S206 style)."""
    if '"True"' in code and '"False"' in code:
        return code.replace('"True"', "\0T").replace('"False"', '"TRUE"').replace("\0T", '"FALSE"')
    token = wrong_token(code, ctx)
    if token is None:
        return None
    return break_operator(token, ctx) or token


# realistic student identifier pools (Vietnamese without accents / English), behaviour-preserving
NAME_POOLS = (
    ("dem", "tong", "kq", "tam", "so", "gt", "chiSo", "bien"),
    ("cnt", "total", "res", "tmp", "num", "val", "idx", "acc"),
    ("count", "sumVal", "answer", "temp", "x", "value", "pos", "result2"),
    ("d", "s", "ans", "t", "m", "v", "k2", "r"),
    ("biendem", "tongso", "ketqua", "bientam", "so1", "giatri", "vitri", "luu"),
)


def neutral_variation(code: str, variant: int) -> str:
    """Rename the student's own identifiers with a realistic name pool (behaviour-preserving).

    Used to turn one verified base into several base *variants* when no LLM persona solutions are
    available. Variant 0 returns the code unchanged."""
    if variant % (len(NAME_POOLS) + 1) == 0:
        return code
    pool = NAME_POOLS[(variant - 1) % len(NAME_POOLS)]
    existing = set(re.findall(r"\b([A-Za-z_]\w*)\b", code))
    out = code
    for name, new in zip(_user_identifiers(code), pool):
        if new in existing or new in CPP_RESERVED:
            continue
        out = re.sub(rf"\b{re.escape(name)}\b", new, out)
        existing.add(new)
    return out


def hardcode_example(code: str, ctx: dict) -> Optional[str]:
    """D17: hardcode the statement's example answer (passes example, fails the rest)."""
    ex_in, ex_out = ctx.get("example_in"), ctx.get("example_out")
    if ex_in is None or ex_out is None:
        return None
    m = re.search(r"int\s+main\s*\(\s*\)\s*\{", code)
    if not m:
        return None
    snippet = f'\n    {{ int __n; cin >> __n; if (__n == {ex_in}) {{ cout << "{ex_out}"; return 0; }} }}\n'
    return code[:m.end()] + snippet + code[m.end():]


_SQRT_LOOP_RE = re.compile(r"\b(\w+)\s*\*\s*\1\s*<=\s*(\w+)")


def brute_force_boundary(code: str, ctx: dict) -> Optional[str]:
    """D18: brute force — a sqrt-bounded loop becomes linear (``i * i <= n`` -> ``i <= n``): slow on
    large input and wrong at the boundary. Falls back to operator + boundary corruption."""
    m = _SQRT_LOOP_RE.search(code)
    if m:
        return code[:m.start()] + f"{m.group(1)} <= {m.group(2)}" + code[m.end():]
    broken = break_operator(code, ctx)
    if broken is None:
        return None
    return flip_comparison(broken, ctx) or broken


def array_string_bug(code: str, ctx: dict) -> Optional[str]:
    """D20: array/string error — off-by-one index or char<->int conversion."""
    m = _find(re.compile(r"-\s*'0'"), code, ctx)
    if m:
        return code[:m.start()] + "+ '0'" + code[m.end():]
    m = _find(re.compile(r"\[(\w+)\s*\+\s*1\]"), code, ctx)
    if m:
        return code[:m.start()] + f"[{m.group(1)}]" + code[m.end():]
    m = _find(re.compile(r"\[([A-Za-z_]\w*)\]"), code, ctx)
    if m:
        return code[:m.start()] + f"[{m.group(1)} + 1]" + code[m.end():]
    return None


def wrong_function_call(code: str, ctx: dict) -> Optional[str]:
    """D21: call a helper with a wrong argument (function error)."""
    pat = re.compile(r"\b([a-z]\w*)\s*\(\s*([a-zA-Z_]\w*)\s*\)")
    hits = [m for a, b in _code_spans(code) for m in pat.finditer(code, a, b)
            if m.group(1) not in CPP_RESERVED and not re.match(r"\s*\{", code[m.end():m.end() + 3])]
    if not hits:
        call = re.compile(r"\b(prob\d|[a-z]\w*)\s*\(([^()]*,\s*)(\w+)\s*\)")
        multi = [m for a, b in _code_spans(code) for m in call.finditer(code, a, b)
                 if m.group(1) not in CPP_RESERVED and not re.match(r"\s*\{", code[m.end():m.end() + 3])]
        if not multi:
            return None
        m = multi[_occurrence(ctx) % len(multi)]
        return code[:m.start()] + f"{m.group(1)}({m.group(2)}{m.group(3)} - 1)" + code[m.end():]
    m = hits[_occurrence(ctx) % len(hits)]
    return code[:m.start()] + f"{m.group(1)}({m.group(2)} + 1)" + code[m.end():]


def init_extreme_zero(code: str, ctx: dict) -> Optional[str]:
    """D14 (edge): initialise a running max/min with 0 instead of the first element."""
    m = _find(re.compile(r"=\s*(\w+)\[0\](\.\w+)?\s*;"), code, ctx)
    if not m:
        return None
    return code[:m.start()] + "= 0;" + code[m.end():]


def skip_first_element(code: str, ctx: dict) -> Optional[str]:
    """D13/D14: a loop that starts at index 1 instead of 0."""
    m = _find(re.compile(r"\bint\s+(\w+)\s*=\s*0\s*;\s*\1\s*<"), code, ctx)
    if not m:
        return None
    return code[:m.start()] + m.group(0).replace("= 0", "= 1", 1) + code[m.end():]


def drop_last_element(code: str, ctx: dict) -> Optional[str]:
    """D14 (edge): loop bound ``i < n`` becomes ``i < n - 1``."""
    m = _find(re.compile(r"(\w+)\s*<\s*(n|\w+\.size\(\)|\w+\.length\(\))\s*;"), code, ctx)
    if not m:
        return None
    return code[:m.end() - 1].rstrip() + " - 1;" + code[m.end():]


def stub_function(code: str, ctx: dict) -> Optional[str]:
    """D12: leave a function unimplemented (empty body / ``return 0;``)."""
    name = ctx.get("function")
    if not name:
        return None
    m = re.search(rf"\b(\w[\w*&\s]*?)\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", code)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(code) and depth:
        depth += (code[i] == "{") - (code[i] == "}")
        i += 1
    ret = m.group(1).strip()
    body = "\n" if ret == "void" else ("\n    return 0;\n" if "*" not in ret else "\n    return nullptr;\n")
    return code[:m.end()] + body + "}" + code[i:]


def function_span(code: str, name: str) -> tuple[int, int] | None:
    """(start, end) of the body of function ``name`` (between its braces)."""
    m = re.search(rf"\b{re.escape(name)}\s*\([^)]*\)\s*\{{", code)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(code) and depth:
        depth += (code[i] == "{") - (code[i] == "}")
        i += 1
    return m.end(), i - 1


def apply_in_function(defect_id: str, code: str, function: str, ctx: dict | None = None) -> str | None:
    """Inject a defect only inside one function (multi_problem: one question at a time)."""
    ctx = dict(ctx or {})
    if defect_id == "D12":
        return stub_function(code, {**ctx, "function": function})
    if defect_id == "D14d":  # needs the signature: only int-returning functions with an ``int n`` parameter
        m = re.search(rf"\b(int|long long)\s+{re.escape(function)}\s*\(([^)]*\bint\s+n\b[^)]*)\)\s*\{{", code)
        return code[:m.end()] + "\n    if (n == 1) return 0;" + code[m.end():] if m else None
    span = function_span(code, function)
    if span is None:
        return None
    a, b = span
    body = code[a:b]
    out = apply(defect_id, body, ctx)
    if out is None or out == body:
        return None
    return code[:a] + out + code[b:]


def ignore_negatives(code: str, ctx: dict) -> Optional[str]:
    """D14c (edge): an accumulation silently skips negative values (wrong only when data has negatives)."""
    m = _find(re.compile(r"(\b\w+)\s*\+=\s*([^;]+);"), code, ctx)
    if not m:
        return None
    var, expr = m.group(1), m.group(2).strip()
    return code[:m.start()] + f"if ({expr} > 0) {var} += {expr};" + code[m.end():]


def wrong_single_element(code: str, ctx: dict) -> Optional[str]:
    """D14d (edge): a special case that mishandles a one-element input (``if (n == 1) return 0;``)."""
    m = re.search(r"\b(int|long long)\s+\w+\s*\(([^)]*\bint\s+n\b[^)]*)\)\s*\{", code)
    if not m:
        return None
    return code[:m.end()] + "\n    if (n == 1) return 0;" + code[m.end():]


def hardcode_bound(code: str, ctx: dict) -> Optional[str]:
    """D15s: a loop bound hard-coded to a literal instead of the input size (``i < n`` -> ``i < 5``)."""
    m = _find(re.compile(r"(\b\w+\s*<=?\s*)(n|\w+\.size\(\)|\w+\.length\(\))(\s*;)"), code, ctx)
    if not m:
        return None
    return code[:m.start()] + m.group(1) + "5" + m.group(3) + code[m.end():]


# ---- traps: look suspicious, behaviour unchanged (label = the code's real behaviour) ----------

TRAP_PROMPT = "Nhap n: "


def trap_prompt_input(code: str, ctx: dict) -> Optional[str]:
    m = re.search(r"^([ \t]*)cin\s*>>", code, re.MULTILINE)
    if not m:
        return None
    return code[:m.start()] + f'{m.group(1)}cout << "{TRAP_PROMPT}";\n' + code[m.start():]


def trap_msvc_style(code: str, ctx: dict) -> Optional[str]:
    """``void main()`` (MSVC accepts it, g++ rejects it). Rulebook G4: still compilable=1."""
    m = re.search(r"\bint\s+main\s*\(\s*\)\s*\{", code)
    if not m:
        return None
    span = function_span(code, "main")
    body = re.sub(r"\n[ \t]*return\s+0\s*;", "", code[span[0]:span[1]])
    return code[:m.start()] + "void main() {" + body + code[span[1]:]


def trap_looks_dangerous(code: str, ctx: dict) -> Optional[str]:
    """``while (cond) {`` becomes ``while (true) { if (!(cond)) break;``."""
    m = re.search(r"\bwhile\s*\((.+?)\)\s*\{", code)
    if not m or m.group(1).strip() == "true":
        return None
    return code[:m.start()] + f"while (true) {{\n        if (!({m.group(1)})) break;" + code[m.end():]


def trap_weird_but_correct(code: str, ctx: dict) -> Optional[str]:
    """Local ``int`` variables widened to ``long long`` (looks over-engineered, same result)."""
    out, n = re.subn(r"(\n[ \t]+)int (\w+ = )", r"\1long long \2", code)
    return out if n else None


def trap_harmless_extra(code: str, ctx: dict) -> Optional[str]:
    """Unused include + unused helper + Vietnamese comment."""
    helper = ("\n// ham phu (chua dung toi)\nint hamPhu(int x) {\n    return x * 2;\n}\n")
    lines = code.splitlines(keepends=True)
    last_inc = max((i for i, l in enumerate(lines) if l.lstrip().startswith("#include")), default=-1)
    lines.insert(last_inc + 1, "#include <cmath>\n")
    out = "".join(lines)
    m = re.search(r"\busing namespace std;\n", out)
    pos = m.end() if m else 0
    return out[:pos] + helper + out[pos:]


TRAPS = {
    "prompt_input": (trap_prompt_input, ("single_problem",)),
    "msvc_style": (trap_msvc_style, ("single_problem",)),
    "looks_dangerous": (trap_looks_dangerous, ("single_problem", "multi_problem")),
    "weird_but_correct": (trap_weird_but_correct, ("single_problem", "multi_problem")),
    "harmless_extra": (trap_harmless_extra, ("single_problem", "multi_problem")),
}


MUTATORS: dict[str, Mutator] = {
    m.defect_id: m
    for m in (
        Mutator("D00", "comment all / empty", lambda c, ctx: comment_all(c, ctx),
                ("single_problem", "multi_problem")),
        Mutator("D01", "missing semicolon", missing_semicolon),
        Mutator("D02", "undeclared variable", undeclare_variable),
        Mutator("D03", "include data file", include_data_file, ("multi_problem",)),
        Mutator("D15", "hardcode filename/size", hardcode_filename, ("multi_problem",)),
        Mutator("D04", "remove loop increment", remove_loop_increment),
        Mutator("D05", "empty function body", empty_function_body),
        Mutator("D06", "wrong token + logic", wrong_token_and_logic),
        Mutator("D07", "extra output char", extra_output_char),
        Mutator("D08", "corrupt core operator", break_operator),
        Mutator("D16a", "two boundary errors", flip_two_comparisons),
        Mutator("D16b", "one boundary error", flip_comparison),
        Mutator("D17", "hardcode example", hardcode_example),
        Mutator("D18", "brute force + boundary", brute_force_boundary),
        Mutator("D19", "wrong output token", wrong_token),
        Mutator("D20", "array/string index or char bug", array_string_bug),
        Mutator("D21", "wrong function call", wrong_function_call),
        Mutator("D23", "garbage style", garbage_style),
        Mutator("D22", "garbage style on a wrong answer", garbage_style),
        Mutator("D12", "unimplemented function", stub_function),
        Mutator("D13", "skip first element", skip_first_element),
        Mutator("D14", "extreme initialised with 0", init_extreme_zero),
        Mutator("D14b", "drop last element", drop_last_element),
        Mutator("D14c", "skip negative values", ignore_negatives),
        Mutator("D14d", "wrong one-element case", wrong_single_element),
        Mutator("D15s", "hard-coded loop bound", hardcode_bound),
    )
}

# defects whose injector depends on a specific problem/function; selected at build time
_CTX_DEFECTS = {"D03", "D05"}


def apply(defect_id: str, code: str, ctx: dict | None = None) -> str | None:
    """Inject one defect; returns the mutated code or None when not applicable."""
    if defect_id not in MUTATORS:
        raise KeyError(f"no mutator for defect {defect_id!r}")
    return MUTATORS[defect_id].transform(code, ctx or {})


def applicable(defect_id: str, code: str, ctx: dict | None = None) -> bool:
    return apply(defect_id, code, ctx) is not None
