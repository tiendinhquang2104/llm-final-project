"""E2: test suites generated from the exam statement by the pipeline's own local LLM, once per exam, at inference.

Nothing here is written for a particular exam. For every exam the model (Qwen2.5-Coder, local) reads what the exam
gives (statement, constraints, prototypes, the data file) and writes:

- K reference solutions (sampled, temperature > 0);
- single_problem: an input generator (C++, one input per index: edge cases first, then random ones);
- multi_problem: a driver `main` that calls the exam functions by their prototypes and prints the results, plus
  the arguments of the problems that take any (JSON).

Expected outputs are decided without any human: references that do not compile, or that fail an example quoted in
the statement, are dropped; every test keeps the answer of the majority of the remaining references and is dropped
when there is no clear majority. A suite with fewer than 2 usable references is not built (the exam then has no
execution signal and the labels fall back to F-cls). Multi-problem runs also get resized copies of the exam data
file (fewer / more rows) for P1, which is how a file read sized by a constant shows up.

Programs run through src/task2/compile.py (g++, time / memory / output limits). Generations are cached on disk by
model, revision, prompt and sampling settings, so a rerun reuses them.
"""
from __future__ import annotations

import hashlib
import json
import re
import textwrap
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace

from src.task2 import compile as _compile
from src.task2.compile import compare_output
from src.task2.examples import statement_examples
from src.task2.prompts_cot import strip_comments

GEN = {"temperature": 0.7, "top_p": 0.95, "max_new_tokens": 2048, "seed": 2026}
K_REFS = 6
K_REFS_MULTI = 10     # multi-problem references fail the data-file check more often
MIN_REFS_MULTI = 3   # a multi suite needs this many references passing the check
N_INPUTS, N_EDGE = 30, 10
N_LISTED = 20
HEAD_ROWS = 6          # data file lines shown to the model
REPAIR_ROUNDS = 3
SEP = "====="     # separator line between the inputs a generator prints
GEN_OUTPUT_CHARS = 400_000

SYSTEM = "You are an expert C++ programmer and teaching assistant. You write correct, standard C++11."

REF_SINGLE = """Write a complete C++11 program that solves the exam below exactly as specified. Read from standard \
input, write to standard output, print nothing else (no prompts, no extra text) and follow the output format exactly.

EXAM:
{statement}

CONSTRAINTS: {constraints}

Answer with one ```cpp code block only."""

GEN_SINGLE = """Write a C++11 program that prints {n} test inputs for the exam below, each exactly in the input \
format of the exam, and after each input a line containing only `{sep}`. It reads nothing.
- The first {n_edge} inputs: edge cases (smallest and largest allowed values, smallest and largest sizes, special \
values or situations the statement mentions).
- The other inputs: varied valid inputs from a deterministic generator (std::mt19937 rng(2026)).
- Make the inputs discriminating: about half of them should be inputs whose correct answer is the less common one \
(for a yes/no question, inputs where the answer is yes), plus inputs that catch typical student mistakes (off-by-one, \
a wrong formula, sizes at the limits, repeated or special values).
- Every input must satisfy the constraints. Keep each input under 20000 characters.

EXAM:
{statement}

CONSTRAINTS: {constraints}

Answer with one ```cpp code block only."""

LIST_SINGLE = """List {n} small test inputs for the exam below, each exactly in the input format of the exam (as \
standard input would receive it, lines separated by \\n). Cover edge cases (smallest values and sizes, the limits of \
the constraints when small enough to write), inputs whose correct answers differ from each other, and inputs that \
catch typical student mistakes. Every input must satisfy the constraints.

EXAM:
{statement}

CONSTRAINTS: {constraints}

Return JSON only: a list of strings, for example ["3\\n1 2 3", "1\\n5"]."""

PLAN_MULTI = """The exam below asks for a function that reads the data file `{data_file}` into these structs:
```cpp
{struct_code}
```
First lines of the data file:
```
{head}
```
For every field of the structs that the file fills, say which column it comes from and exactly how to convert the \
text of that column (number format, date format and era, the separator of a column that holds a list and how a count \
field relates to it). Say which columns are not used. Answer as a short list, no code.

EXAM:
{statement}"""

REF_MULTI = """Implement the functions of the exam below in C++11. These structs are already defined, do not define \
them again:
```cpp
{struct_code}
```
Write the #include lines you need, `using namespace std;` and every function with exactly the given prototype. Do \
NOT write a main function.

PROTOTYPES:
{protos}

First lines of the data file `{data_file}` ({rows} data rows after the header line; the real file may have any \
number of rows):
```
{head}
```
How the columns map to the struct fields:
{plan}

Read every row of the file (do not assume its size) and skip the header line.

EXAM:
{statement}

Answer with one ```cpp code block only."""

REPAIR_SINGLE = """The C++11 program below is meant to solve the exam that follows, but it is wrong:
{problem}

Fix the program. It must read from standard input and print only the answer, exactly in the output format of the exam.

CODE:
```cpp
{code}
```

EXAM:
{statement}

CONSTRAINTS: {constraints}

Answer with the whole corrected program in one ```cpp code block only."""

REPAIR = """The C++11 code below is meant to solve the exam that follows, but it has a problem:
{problem}

Fix the code. Keep every function prototype unchanged and do not add a main function.

CODE:
```cpp
{code}
```

EXAM:
{statement}

These structs are already defined, do not define them again:
```cpp
{struct_code}
```
First lines of the data file `{data_file}`:
```
{head}
```
How the columns map to the struct fields:
{plan}

Answer with the whole corrected code in one ```cpp code block only."""

DRIVER_MULTI = """Write a C++11 test driver for the exam below. The structs of the statement and these functions are \
already defined elsewhere, with exactly these prototypes:
{protos}
Do NOT define any struct or any of these functions and do not add #include lines; write only helper functions whose \
names start with drv_ and `int main()`.

main must:
1. read the problem id (P1, P2, ...) from the first line of standard input and the data file name from the second \
line; every following line is one argument (read them with getline);
2. for P1: call the first function on the file and print the number of records, then every field of every record, \
one record per line;
3. for the other problems: build the data with the functions of the earlier problems (in order) and then
   - for a problem that builds a structure: print every element in traversal order (pre-order for a tree), all \
fields of each element, one element per line;
   - for a problem that returns a value: call it with the arguments converted to the parameter types and print the \
returned value (every field if it is a struct);
   - for a problem that modifies the structure: call it with the arguments, then print every remaining element in \
traversal order.
Print values only, separated by single spaces. Never dereference a null pointer.

EXAM:
{statement}

Answer with one ```cpp code block only."""

ARGS_MULTI = """For the exam below, propose test arguments for every problem whose function takes arguments other \
than the data structure built by the earlier problems:
{protos}
Use values that occur in the data file (first lines below), and edge cases: a value that matches nothing, a value \
matching the first element, a value matching many elements.

EXAM:
{statement}

First lines of the data file `{data_file}`:
```
{head}
```

Return JSON only, for example {{"P3": [["value"], ["other value"]], "P4": [["value"]]}}: up to 5 argument lists per \
problem, every argument a string."""

PRELUDE = """#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cstring>
#include <cmath>
#include <cctype>
#include <vector>
#include <algorithm>
#include <map>
#include <set>
#include <iomanip>
#include <climits>
using namespace std;
"""

# the driver's output is captured, whitespace-normalised and hashed: long outputs (P1 prints every record) compare
# in full although compile.py keeps only the first MAX_ACTUAL_CHARS characters of a run
WRAPPER = """
static const char* tg_files[][2] = {%(files)s};
int main() {
    for (auto& f : tg_files) { std::ofstream o(f[0], std::ios::binary); o << f[1]; }
    std::ostringstream tg_buf;
    std::streambuf* tg_old = std::cout.rdbuf(tg_buf.rdbuf());
    int tg_rc;
    try {
        tg_rc = tg_driver_main();
    } catch (const std::exception& e) {  // reported like a crash (exit code 3), with the message for the repair prompt
        std::cout.rdbuf(tg_old);
        std::cout << "#exception " << e.what() << "\\n";
        return 3;
    }
    std::cout.rdbuf(tg_old);
    std::string s = tg_buf.str(), t;
    bool sp = false;
    for (unsigned char c : s) {
        if (std::isspace(c)) { sp = !t.empty(); continue; }
        if (sp) { t += ' '; sp = false; }
        t += (char)c;
    }
    unsigned long long h = 1469598103934665603ULL;
    for (unsigned char c : t) { h ^= c; h *= 1099511628211ULL; }
    std::cout << "#" << std::hex << h << std::dec << " " << t.size() << "\\n" << t.substr(0, 300) << "\\n";
    return tg_rc;
}
"""


@dataclass
class Suite:
    exam_id: str
    exam_type: str
    model: str
    revision: str | None
    tests: list[dict] = field(default_factory=list)    # {id, group|pid, stdin, expected}
    driver: str | None = None                            # multi: driver code, main renamed to tg_driver_main
    files: dict = field(default_factory=dict)            # multi: file name -> text
    pids: list[str] = field(default_factory=list)        # multi: problem ids in order
    prereq: dict = field(default_factory=dict)           # pid -> pids not graded when it fails (grading_policy)
    struct_names: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)            # refs generated / kept, tests kept / dropped, ...
    probe: bool = False                                  # multi without agreed answers: tests carry "rows" (the
                                                         # record count the first problem must read) instead of an
                                                         # expected output, and later problems are only watched for
                                                         # crashes / endless runs

    def to_json(self) -> dict:
        return asdict(self)

    def as_probe(self) -> "Suite":
        """The same runs judged without expected outputs (see `probe`): the first problem by the record count of
        the data file it reads, the others by crashes and endless runs."""
        first = self.pids[0] if self.pids else None
        tests = []
        for t in self.tests:
            row = {**t, "expected": None}
            fname = t["stdin"].split("\n")[1] if t.get("pid") == first and "\n" in t["stdin"] else None
            if fname in self.files:
                row["rows"] = max(0, len(self.files[fname].rstrip("\n").split("\n")) - 1)
            tests.append(row)
        return replace(self, tests=tests, probe=True)

    @classmethod
    def from_json(cls, d: dict) -> "Suite":
        return cls(**d)


# ------------------------------------------------------------------------------------------- exam parsing (generic)

def extract_code(text: str) -> str:
    """The longest ```cpp / ``` block of an answer; an answer cut by the token limit leaves its last block open,
    so an opening fence without a closing one keeps the rest; else the whole answer."""
    fence = r"```[ \t]*(?:c\+\+|cpp|cc|C\+\+)?[ \t]*\n"
    blocks = re.findall(fence + r"(.*?)```", text, re.S)
    if blocks:
        return max(blocks, key=len).strip()
    m = re.search(fence + r"(.*)", text, re.S)
    return (m.group(1) if m else text).strip()


def extract_json_list(text: str) -> list[str]:
    """The strings of the first JSON list in an answer ([] when there is none)."""
    m = re.search(r"\[.*\]", text, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        return []
    return [str(x) for x in items if isinstance(x, (str, int, float))] if isinstance(items, list) else []


def extract_json(text: str):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def struct_names(statement: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\bstruct\s+([A-Za-z_]\w*)\s*\{", statement or "")))


def prototypes(exam: dict) -> dict[str, str]:
    """pid -> prototype (comment removed), for the problems that have one."""
    out = {}
    for p in exam.get("problems") or []:
        proto = (p.get("prototype") or "").split("//")[0].strip()
        if proto:
            out[p["pid"]] = proto if proto.endswith(";") else proto + ";"
    return out


def func_name(proto: str) -> str | None:
    m = re.search(r"([A-Za-z_]\w*)\s*\(", proto)
    return m.group(1) if m else None


def stub(proto: str) -> str:
    """A definition of a function the submission does not define at all, so the rest still links."""
    head = proto.rstrip(";").strip()
    ret = head[:head.index(func_name(proto))].strip()
    return head + (" {}" if ret == "void" else " { return {}; }")


_SCALAR = re.compile(r"^(const\s+)?(std::)?(string|int|long|long long|double|float|char|bool)\s*&?\s*(\w+)$")


def arg_params(proto: str) -> list[str]:
    """Parameters a test has to supply (strings and numbers), not the data built by earlier problems; a size
    parameter `n` belongs to the data."""
    inside = proto[proto.index("(") + 1:proto.rindex(")")] if "(" in proto else ""
    out = []
    for p in filter(None, (x.strip() for x in inside.split(","))):
        m = _SCALAR.match(p)
        if m and m.group(4) != "n" and "&" not in p.replace("const", ""):
            out.append(p)
    return out


def prereq_map(exam: dict) -> dict[str, list[str]]:
    return {p["pid"]: list(p["is_prerequisite_for"]) for p in exam.get("problems") or [] if p.get("is_prerequisite_for")}


def defined_functions(code: str, names) -> set[str]:
    src = strip_comments(code)
    return {n for n in names if n and re.search(rf"\b{re.escape(n)}\s*\([^;{{]*\)\s*\{{", src)}


def file_variants(name: str, text: str) -> dict[str, str]:
    """The exam data file and resized copies (header kept): about a third of the rows, and the rows plus two
    thirds of them again. Generic: rows are only copied, never edited."""
    lines = text.replace("\r\n", "\n").rstrip("\n").split("\n")
    head, rows = lines[:1], lines[1:]
    if len(rows) < 3:
        return {name: text}
    stem, dot, ext = name.rpartition(".")
    short = rows[:max(2, len(rows) // 3)]
    long = rows + rows[:max(1, 2 * len(rows) // 3)]
    return {name: text,
            f"{stem}_short{dot}{ext}": "\n".join(head + short) + "\n",
            f"{stem}_long{dot}{ext}": "\n".join(head + long) + "\n"}


def _cstr(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "") + '"'


def assemble(student_code: str, suite: Suite, protos: dict[str, str]) -> str:
    """Submission (or reference) + stubs for the functions it lacks + the driver + the file-writing main."""
    names = [func_name(p) for p in protos.values()]
    have = defined_functions(student_code, names)
    stubs = "\n".join(stub(p) for p in protos.values() if func_name(p) not in have)
    files = ", ".join(f"{{{_cstr(k)}, {_cstr(v)}}}" for k, v in suite.files.items())
    return (PRELUDE + "#define main tg_student_main_renamed\n" + student_code.lstrip("\ufeff")
            + "\n#undef main\n" + stubs + "\n" + suite.driver + "\n" + WRAPPER % {"files": files})


def statement_struct_code(statement: str) -> str:
    """Every struct definition the statement gives, verbatim (from its code blocks), in order."""
    out = []
    for block in re.findall(r"```[^\n]*\n(.*?)```", statement or "", re.S):
        for m in re.finditer(r"\bstruct\s+\w+\s*\{", block):
            i, depth = block.index("{", m.start()), 0
            j = i
            while j < len(block):
                depth += {"{": 1, "}": -1}.get(block[j], 0)
                j += 1
                if depth == 0:
                    break
            end = j + 1 if block[j:j + 1] == ";" else j
            out.append(textwrap.dedent(block[m.start():end]).strip() + ("" if block[j:j + 1] == ";" else ";"))
    return "\n".join(dict.fromkeys(out))


def strip_structs(code: str, structs) -> str:
    """Code without its own definitions of the exam structs (the statement's are used instead)."""
    return strip_driver(code, structs, []).strip() if structs else code


def rename_driver_main(code: str) -> str | None:
    if not re.search(r"\bint\s+main\s*\(", code):
        return None
    return re.sub(r"\bint\s+main\s*\(\s*(void)?\s*\)", "int tg_driver_main()", code, count=1)


def strip_driver(code: str, structs, names) -> str:
    """Drop #include / using lines and any struct or exam function the driver defines anyway."""
    src = re.sub(r"^\s*#\s*include.*$|^\s*using\s+namespace\s+std\s*;", "", code, flags=re.M)
    for n in list(structs) + list(names):
        m = re.search(rf"\b(struct\s+{re.escape(n)}\s*\{{|[\w:<>\*&\s]+\b{re.escape(n)}\s*\([^;{{]*\)\s*\{{)", src)
        if not m:
            continue
        i, depth = src.index("{", m.start()), 0
        j = i
        while j < len(src):
            depth += {"{": 1, "}": -1}.get(src[j], 0)
            j += 1
            if depth == 0:
                break
        end = j + 1 if src[j:j + 1] == ";" else j
        src = src[:m.start()] + src[end:]
    return src


# ------------------------------------------------------------------------------------------------- generation

class SuiteBuilder:
    """Builds (and caches) one Suite per exam. `llm`: a src/llm/local_backend.py backend; `compiler`: a
    src/task2/compile.py compiler (native g++ on Linux, Docker GCC on macOS)."""

    def __init__(self, llm, compiler, cache_dir="outputs/task2/_testgen", k: int = K_REFS, gen: dict | None = None):
        self.llm, self.compiler, self.k = llm, compiler, k
        self.k_multi = max(k, K_REFS_MULTI) if k == K_REFS else k
        self.gen = {**GEN, **(gen or {})}
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)

    def _run_long(self, jobs):
        """compiler.run keeping the whole stdout (an input generator prints every input in one run)."""
        keep = _compile.MAX_ACTUAL_CHARS
        _compile.MAX_ACTUAL_CHARS = GEN_OUTPUT_CHARS
        try:
            return self.compiler.run(jobs)
        finally:
            _compile.MAX_ACTUAL_CHARS = keep

    # cached sampling: key = model, revision, prompt, settings, n
    def _ask(self, tag: str, prompt: str, n: int) -> list[str]:
        model = getattr(self.llm, "model", "?")
        rev = getattr(self.llm, "revision", None)
        key = hashlib.sha256(json.dumps([model, rev, SYSTEM, prompt, self.gen, n]).encode()).hexdigest()[:32]
        path = self.cache / f"gen_{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["answers"]
        req = {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
               "sample": SimpleNamespace(sample_id=tag)}
        gen = {**self.gen, "n": n} if n > 1 else {**self.gen, "n": 1}
        answers = self.llm.generate([req], gen)[0]
        path.write_text(json.dumps({"tag": tag, "model": model, "revision": rev, "gen": gen, "prompt": prompt,
                                    "answers": answers}, ensure_ascii=False), encoding="utf-8")
        return answers

    def build(self, exam: dict, data_dir=None) -> Suite | None:
        key = hashlib.sha256(json.dumps([exam, getattr(self.llm, "model", "?"), getattr(self.llm, "revision", None),
                                         self.gen, self.k, self.k_multi, MIN_REFS_MULTI, REF_SINGLE, GEN_SINGLE, LIST_SINGLE, REPAIR_SINGLE, PLAN_MULTI, REF_MULTI, REPAIR, DRIVER_MULTI,
                                         ARGS_MULTI, WRAPPER, "probe-v1"], sort_keys=True, default=str).encode()).hexdigest()[:12]
        path = self.cache / f"suite_{exam['exam_id']}_{key}.json"
        if path.exists():
            d = json.loads(path.read_text(encoding="utf-8"))
            return Suite.from_json(d) if d else None
        if exam.get("exam_type") == "multi_problem":
            suite = self._multi(exam, data_dir)
        else:
            suite = self._single(exam)
        path.write_text(json.dumps(suite.to_json() if suite else None, ensure_ascii=False), encoding="utf-8")
        return suite

    def _model_info(self):
        return getattr(self.llm, "model", "?"), getattr(self.llm, "revision", None)

    # ---------------------------------------------------------------------------------------- single_problem
    def _single(self, exam: dict) -> Suite | None:
        eid, st = exam["exam_id"], exam.get("statement") or ""
        cons = "; ".join(p.get("constraints") or "" for p in exam.get("problems") or []) or "see the statement"
        refs = [extract_code(a) for a in self._ask(f"{eid}:ref", REF_SINGLE.format(statement=st, constraints=cons),
                                                    self.k)]
        gens = [extract_code(a) for a in self._ask(f"{eid}:gen", GEN_SINGLE.format(
            statement=st, constraints=cons, n=N_INPUTS, n_edge=N_EDGE, sep=SEP), 2)]
        examples = statement_examples(exam)
        inputs, seen = [], set()
        for g in gens:  # inputs of every generator that builds and prints at least 3 of them
            (log, rc, runs), = self._run_long([(g, "single_problem", [""])])
            if not runs:
                continue
            parts = [p.strip("\n") for p in runs[0].get("actual", "").split(SEP)]
            parts = parts[:-1]  # after the last separator: nothing, or an input cut by a crash / the time limit
            parts = [p + "\n" for p in parts if p.strip()]
            if len(parts) < 3:
                continue
            for i, s in enumerate(parts):
                if s not in seen:
                    seen.add(s)
                    inputs.append(("edge" if i < N_EDGE else "normal", s))
        listed = extract_json_list(self._ask(f"{eid}:list", LIST_SINGLE.format(
            statement=st, constraints=cons, n=N_LISTED), 1)[0])
        for s in listed:  # small hand-picked-style inputs written directly by the model
            s = s if s.endswith("\n") else s + "\n"
            if s.strip() and s not in seen:
                seen.add(s)
                inputs.append(("listed", s))
        cases = [("example", e["input"], e["expected"]) for e in examples] + [(g, s, None) for g, s in inputs]
        stdin = [c[1] for c in cases]

        def check(codes):
            """(runs, problem) per reference; problem is None when it builds and prints every example right."""
            res = []
            for code, (log, rc, runs) in zip(codes, self.compiler.run([(r, "single_problem", stdin) for r in codes])):
                if runs is None:
                    errs = [ln for ln in log.splitlines() if "error" in ln][:6]
                    res.append((None, "It does not compile:\n" + "\n".join(errs)))
                    continue
                problem = None
                for (_, s, exp), run in zip(cases, runs):
                    if exp is None:
                        continue
                    got = run.get("actual", "")
                    if run.get("timeout") or run.get("returncode") or compare_output(got, exp) != "pass":
                        problem = (f"For the example input\n{s}the expected output is\n{exp}\nbut the program "
                                   + ("never ends." if run.get("timeout") else
                                      f"crashes (exit code {run.get('returncode')})." if run.get("returncode") else
                                      f"prints\n{got.strip()[:300]}"))
                        break
                res.append((runs, problem))
            return res

        res = check(refs)
        built = sum(r is not None for r, _ in res)
        repaired = 0
        for rnd in range(REPAIR_ROUNDS):  # references that fail an example get it back to fix
            if sum(p is None for _, p in res) >= max(2, len(refs) // 2):
                break
            bad = [(i, p) for i, (_, p) in enumerate(res) if p is not None]
            fixes = [extract_code(self._ask(f"{eid}:repair{rnd}.{i}", REPAIR_SINGLE.format(
                problem=p, code=refs[i], statement=st, constraints=cons), 1)[0]) for i, p in bad]
            for (i, _), code, r in zip(bad, fixes, check(fixes)):
                refs[i], res[i] = code, r
                repaired += r[1] is None
        kept = [runs for runs, p in res if p is None]
        stats = {"refs": len(refs), "refs_built": built, "refs_kept": len(kept), "repaired": repaired,
                 "examples": len(examples), "inputs": len(inputs)}
        if len(kept) < 2:
            print(f"[testgen] {eid}: {len(kept)} usable references, no suite", flush=True)
            return None
        tests, dropped = [], 0
        for k, (group, s, exp) in enumerate(cases):
            if exp is not None:
                tests.append({"id": f"t{k:02d}", "group": group, "stdin": s, "expected": exp})
                continue
            answer = _majority([r[k] for r in kept])
            if answer is None:
                dropped += 1
            else:
                tests.append({"id": f"t{k:02d}", "group": group, "stdin": s, "expected": answer})
        model, rev = self._model_info()
        stats.update(tests=len(tests), dropped=dropped)
        print(f"[testgen] {eid}: {stats}", flush=True)
        return Suite(eid, "single_problem", model, rev, tests=tests, stats=stats)

    # ----------------------------------------------------------------------------------------- multi_problem
    def _multi(self, exam: dict, data_dir) -> Suite | None:
        eid, st = exam["exam_id"], exam.get("statement") or ""
        protos = prototypes(exam)
        dname = exam.get("data_file")
        dpath = Path(data_dir or ".") / dname if dname else None
        if not protos or dpath is None or not dpath.exists():
            print(f"[testgen] {eid}: no prototypes or data file, no suite", flush=True)
            return None
        data = dpath.read_text(encoding="utf-8-sig")
        head = "\n".join(data.splitlines()[:HEAD_ROWS])
        ptxt = "\n".join(f"{pid}: {p}" for pid, p in protos.items())
        structs, names = struct_names(st), [func_name(p) for p in protos.values()]
        n_rows = max(0, len(data.rstrip("\n").split("\n")) - 1)
        struct_code = statement_struct_code(st)
        plan = self._ask(f"{eid}:plan", PLAN_MULTI.format(
            statement=st, data_file=dname, head=head, struct_code=struct_code), 1)[0].strip()
        refs = [struct_code + "\n" + strip_structs(extract_code(a), structs) for a in self._ask(
            f"{eid}:ref", REF_MULTI.format(statement=st, protos=ptxt, data_file=dname, head=head, rows=n_rows,
                                           struct_code=struct_code, plan=plan), self.k_multi)]
        drivers = [rename_driver_main(strip_driver(extract_code(a), structs, names))
                   for a in self._ask(f"{eid}:driver", DRIVER_MULTI.format(statement=st, protos=ptxt), 3)]
        with_args = {pid: p for pid, p in list(protos.items())[1:] if arg_params(p)}
        args = {}
        if with_args:
            args = extract_json(self._ask(f"{eid}:args", ARGS_MULTI.format(
                statement=st, protos="\n".join(f"{pid}: {p}" for pid, p in with_args.items()), data_file=dname,
                head=head), 1)[0]) or {}
        pids = list(protos)
        files = file_variants(dname, data)
        rows = {f: max(0, len(t.rstrip("\n").split("\n")) - 1) for f, t in files.items()}
        cases = [{"id": f"{pids[0]}{c}", "pid": pids[0], "stdin": f"{pids[0]}\n{f}\n"}
                 for c, f in zip("ABC", files)]
        for pid in pids[1:]:
            lists = [a for a in (args.get(pid) or []) if isinstance(a, list)][:5] if arg_params(protos[pid]) else []
            for j, a in enumerate(lists or [[]]):
                cases.append({"id": f"{pid}{j}", "pid": pid,
                              "stdin": f"{pid}\n{dname}\n" + "".join(f"{str(v)}\n" for v in a)})
        n_first = len(files)
        prereq = prereq_map(exam)

        def check(suite: Suite, codes: list[str]) -> list[tuple[list | None, str | None]]:
            """(runs, problem) per reference: problem is None when it builds with the driver and the first problem
            reads every variant of the data file into exactly as many records as it has rows."""
            outs = self.compiler.run([(assemble(r, suite, protos), "single_problem", [c["stdin"] for c in cases])
                                      for r in codes])
            res = []
            for code, (log, rc, runs) in zip(codes, outs):
                if runs is None:
                    (own, _), = self.compiler.run([(PRELUDE + code, "multi_problem")])
                    errs = [ln for ln in own.splitlines() if "error" in ln][:6]
                    res.append((None, "It does not compile:\n" + "\n".join(errs) if errs else "It does not compile."))
                    continue
                problem = None
                for c, run in zip(cases[:n_first], runs[:n_first]):
                    fname = c["stdin"].split("\n")[1]
                    if run.get("timeout") or run.get("returncode"):
                        exc = re.search(r"#exception (.*)", run.get("actual", ""))
                        problem = (f"Reading the data file `{fname}` ({rows[fname]} data rows) with the first "
                                   f"function " + ("never ends." if run.get("timeout") else
                                                   f"throws an exception: {exc.group(1)}." if exc else
                                                   f"crashes (exit code {run.get('returncode')})."))
                        break
                    got = (run.get("actual", "").split("\n", 1) + [""])[1].split()
                    if not got or got[0] != str(rows[fname]):
                        problem = (f"Reading the data file `{fname}`, which has {rows[fname]} data rows after the "
                                   f"header, the first function returns n = {got[0] if got else 'nothing'}.")
                        break
                res.append((runs, problem))
            return res

        best = None
        for drv in drivers:  # the driver with which the most references pass the check
            if not drv:
                continue
            suite = Suite(eid, "multi_problem", *self._model_info(), driver=drv, files=files, pids=pids,
                          prereq=prereq, struct_names=structs)
            res = check(suite, refs)
            score = (sum(p is None for _, p in res), sum(r is not None for r, _ in res))
            if best is None or score > best[2]:
                best = (suite, res, score)
        if best is None or best[2][1] == 0:
            print(f"[testgen] {eid}: no driver builds with a reference, no suite", flush=True)
            return None
        suite, res, _ = best
        # repair rounds: every reference that fails the check gets its current problem back
        repaired = 0
        for rnd in range(REPAIR_ROUNDS):
            bad = [(i, p) for i, (_, p) in enumerate(res) if p is not None]
            if not bad:
                break
            fixes = [extract_code(self._ask(f"{eid}:repair{rnd}.{i}", REPAIR.format(
                problem=p, code=strip_structs(refs[i], structs), statement=st, data_file=dname, head=head,
                struct_code=struct_code, plan=plan), 1)[0]) for i, p in bad]
            fixes = [struct_code + "\n" + strip_structs(f, structs) for f in fixes]
            for (i, _), code, r in zip(bad, fixes, check(suite, fixes)):
                refs[i], res[i] = code, r  # keep the latest attempt: its problem is the one to fix next
                repaired += r[1] is None
        kept = [runs for runs, p in res if p is None]

        def probe(why: str) -> Suite | None:
            """No agreed answers: keep the cases the driver can judge without them. Needs one reference that passes
            the data-file check with this driver (so the driver prints the record count right)."""
            if not kept:
                print(f"[testgen] {eid}: {why}; no reference passes the data-file check, no suite", flush=True)
                return None
            tests = [{**c, "expected": None, **({"rows": rows[c["stdin"].split(chr(10))[1]]} if k < n_first else {})}
                     for k, c in enumerate(cases)]
            out = Suite(eid, "multi_problem", *self._model_info(), tests=tests, driver=suite.driver, files=files,
                        pids=pids, prereq=prereq, struct_names=structs, probe=True,
                        stats={"refs": len(refs), "refs_kept": len(kept), "repaired": repaired, "probe": why,
                               "cases": len(cases), "args": args})
            print(f"[testgen] {eid}: {why}, probe suite (record counts, crashes, endless runs) {out.stats}",
                  flush=True)
            return out

        if len(kept) < MIN_REFS_MULTI:
            return probe(f"{len(kept)} references pass the data-file check")
        tests, dropped = [], 0
        for k, c in enumerate(cases):
            answer = _majority([r[k] for r in kept])
            if answer is None:
                dropped += 1
            else:
                tests.append({**c, "expected": answer})
        suite.tests = tests
        suite.stats = {"refs": len(refs), "refs_kept": len(kept), "repaired": repaired, "drivers": len(drivers),
                       "cases": len(cases), "tests": len(tests), "dropped": dropped, "args": args}
        if sum(t["pid"] == pids[0] for t in tests) < n_first:
            # the prerequisite decides every label of a wrong submission: without an agreed answer on each copy of
            # the data file, a suite would judge right submissions wrong, so the exam gets no suite
            return probe(f"no agreement on every {pids[0]} case")
        print(f"[testgen] {eid}: {suite.stats}", flush=True)
        return suite


def _majority(runs: list[dict]) -> str | None:
    """The output most references agree on, when they ran cleanly and the agreement is a strict majority of at
    least 2; else None (the test is dropped)."""
    outs = [r.get("actual", "").strip() for r in runs if not r.get("timeout") and not r.get("returncode")]
    if not outs:
        return None
    norm = Counter(" ".join(o.split()) for o in outs)
    answer, n = norm.most_common(1)[0]
    if n < 2 or n <= len(runs) / 2:
        return None
    return next(o for o in outs if " ".join(o.split()) == answer)


def multi_header(actual: str) -> str:
    """The `#hash length` line the wrapper prints first (the comparable part of a multi run)."""
    return actual.strip().split("\n", 1)[0] if actual else ""
