"""Execution oracle for Task 2 (hướng E): run every submission on tests built from its exam statement.

The instructor allowed the inference pipeline to read the test statements and build test cases from them; no label
of a test sample is ever used. Each exam of the competition is recognised from its statement (the 2 gold exams are
the same tasks: EX02 = Armstrong, EX01 = generals linked list):

- single_problem (stdin/stdout): Armstrong, remove duplicates, alphabetically earliest login. Inputs come from the
  statement examples plus cases the statement defines (constraints, edge values, a large input); expected outputs
  come from a reference written from the statement. Each run gets a compare_output status.
- multi_problem (functions only): generals in a linked list / in a BST, battles in a linked list. The submission is
  compiled together with a harness main (the student's own main, if any, is renamed); one run per case:
  P1 reads the exam CSV and two variants (fewer / more rows, another file name), P2-P4 get inputs the harness builds
  itself with the exam structs, so each problem is judged on its own. A problem whose body is empty is "missing".

Results are signals (per-test statuses, per-problem states), turned into labels by src/task2/exec_rules.py.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.task2.compile import RUN_TIMEOUT, compare_output, has_compile_error
from src.task2.prompts_cot import ALL_COMMENTED, strip_comments

DATA_DIR = Path("data/raw/public_test_release/data_files")
GENERALS_CSV = "50-best-european-generals-cleaned-first-20.csv"
BATTLES_CSV = "50-european-battles-first-20.csv"


def exam_kind(exam: dict) -> str | None:
    """Which known task an exam statement describes (None: unknown exam, no oracle)."""
    s = exam.get("statement", "")
    if "Armstrong" in s:
        return "armstrong"
    if "Remove Duplicates" in s or "duplicate elements" in s:
        return "dedup"
    if "login" in s and "prefix" in s:
        return "login"
    if "struct Battle" in s:
        return "battles_ll"
    if "struct General" in s and ("Binary Search Tree" in s or "Node* left" in s):
        return "generals_bst"
    if "struct General" in s:
        return "generals_ll"
    return None


# ---------------------------------------------------------------------------------------------- single_problem


def _armstrong(n: int) -> bool:
    d = str(n)
    return sum(int(c) ** len(d) for c in d) == n


def _login(first: str, last: str) -> str:
    return min(first[:k] + last[0] for k in range(1, len(first) + 1))


def single_tests(kind: str, seed: int = 7) -> list[tuple[str, str, str]]:
    """(group, stdin, expected stdout). Groups: example (statement), normal, edge, perf."""
    rng = random.Random(seed)
    out: list[tuple[str, str, str]] = []
    if kind == "armstrong":
        ex = [1634, 123]
        normal = [153, 370, 371, 407, 9474, 100, 154, 9475, 8208, 54748, 92727, 548834, 1741725, 4210818,
                  9800817, 24678050, 146511208, 472335975, 99999, 1000]
        edge = [1, 9, 10, 999999999, 1000000000, 912985153, 534494836]
        for g, xs in (("example", ex), ("normal", normal), ("edge", edge)):
            out += [(g, f"{n}\n", "True" if _armstrong(n) else "False") for n in xs]
    elif kind == "dedup":
        def case(a):
            seen, keep = set(), []
            for x in a:
                if x not in seen:
                    seen.add(x)
                    keep.append(x)
            return f"{len(a)}\n{' '.join(map(str, a))}\n", f"{len(keep)}\n{' '.join(map(str, keep))}"
        groups = {
            "example": [[1, 5, 3, 7, 2, 3, 2, 5, 2, 6, 5, 6, 5, 7, 2, 3], [5, 5, 5, 5, 5]],
            "normal": [[4, 1, 4, 2, 1, 3], [9, 8, 7, 6], [2, 2, 3, 3, 2, 3, 4], [10, 20, 10, 30, 20, 40, 50, 40],
                       [rng.randint(0, 9) for _ in range(30)]],
            "edge": [[7], [-3, -1, -3, 0, -1], [1000000000, -1000000000, 1000000000, 0], [0, 0],
                     [-5, 5, -5, 5]],
            # n = 10000 (an O(n^2) scan still runs in time); few distinct values: stdout fits MAX_ACTUAL_CHARS
            "perf": [[rng.randint(-150, 150) for _ in range(10000)], [rng.randint(1, 50) for _ in range(10000)]],
        }
        for g, cases in groups.items():
            out += [(g, *case(a)) for a in cases]
    elif kind == "login":
        ex = [("harry", "potter"), ("tom", "riddle")]
        normal = [("anna", "bell"), ("bob", "alice"), ("zed", "adam"), ("abc", "abc"), ("kevin", "lee"),
                  ("aab", "b"), ("hermione", "granger"), ("ron", "weasley")]
        normal += [("".join(rng.choice("abcdez") for _ in range(rng.randint(1, 10))),
                    "".join(rng.choice("abcdez") for _ in range(rng.randint(1, 10)))) for _ in range(6)]
        edge = [("a", "a"), ("z", "a"), ("a", "z"), ("abcdefghij", "z"), ("zzzzzzzzzz", "a"), ("ba", "b")]
        for g, xs in (("example", ex), ("normal", normal), ("edge", edge)):
            out += [(g, f"{f} {l}\n", _login(f, l)) for f, l in xs]
    else:
        raise ValueError(kind)
    return out


# ---------------------------------------------------------------------------------------------- multi_problem data


@dataclass
class Rec:
    name: str
    nat: str            # nationality (generals) / location (battles)
    born: tuple         # (day, month, year, era) for generals; from_date string for battles
    death: tuple
    items: list = field(default_factory=list)  # known battles / famous generals


def _date(s: str) -> tuple:
    d, era = s.strip().split(" ")
    day, month, year = (int(x) for x in d.split("-"))
    return day, month, year, era


def load_generals() -> list[Rec]:
    with open(DATA_DIR / GENERALS_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [Rec(r["Name"], r["Nationality"], _date(r["Born"]), _date(r["Death"]), r["KnownBattles"].split("|"))
            for r in rows]


def load_battles() -> list[Rec]:
    with open(DATA_DIR / BATTLES_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [Rec(r["BattleName"], r["Location"], r["FromDate"], r["ToDate"], r["ListFamousGenerals"].split(";"))
            for r in rows]


def _csv_text(kind: str, idx: list[int]) -> str:
    name = BATTLES_CSV if kind == "battles_ll" else GENERALS_CSV
    lines = (DATA_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n").split("\n")
    return "\n".join([lines[0]] + [lines[1 + i] for i in idx]) + "\n"


def _age(r: Rec) -> int:
    by, be, dy, de = r.born[2], r.born[3], r.death[2], r.death[3]
    b = -by if be == "BC" else by
    d = -dy if de == "BC" else dy
    return d - b


def _date_key(d: tuple) -> tuple:
    day, month, year, era = d
    return (-year if era == "BC" else year, month, day)


def _year_of(s: str) -> int:
    return int(s.strip().split("-")[-1])


# P1 files: the exam CSV, a shorter file and a longer one (rows repeated), each under its own name
P1_FILES = {"A": list(range(20)), "B": [0, 3, 6, 11, 14, 15, 2], "C": list(range(20)) + list(range(13))}


def multi_cases(kind: str) -> list[dict]:
    """Harness cases: {"id", "pid", "arg", "expected"} (expected is the exact harness output line(s))."""
    recs = load_battles() if kind == "battles_ll" else load_generals()
    cases = []
    for key, idx in P1_FILES.items():
        cases.append({"id": f"P1{key}", "pid": "P1", "arg": key, "expected": _p1_expected(kind, [recs[i] for i in idx])})
    subsets = [list(range(20)), [5, 1, 12, 0]] if kind != "generals_bst" else [list(range(20)), [8, 3, 15, 0, 18]]
    for k, idx in enumerate(subsets):
        sub = [recs[i] for i in idx]
        if kind == "generals_bst":
            exp = " | ".join(r.name for r in _bst_preorder(sub))
        else:
            exp = " | ".join(r.name for r in sub)
        cases.append({"id": f"P2{k}", "pid": "P2", "arg": idx, "expected": exp})
    if kind == "generals_ll":
        p3 = [list(range(20)), [13, 14, 11, 15, 0], [2, 11], [11, 2]]
        for k, idx in enumerate(p3):
            sub = [recs[i] for i in idx]
            best = max(range(len(sub)), key=lambda j: (_age(sub[j]), -j))
            cases.append({"id": f"P3{k}", "pid": "P3", "arg": idx, "expected": sub[best].name})
        p4 = [(list(range(20)), "England"), (list(range(20)), "Roman Republic"), (list(range(20)), "Soviet Union"),
              (list(range(20)), "Narnia"), ([14, 15], "Roman Republic")]
        for k, (idx, nat) in enumerate(p4):
            exp = " | ".join(recs[i].name for i in idx if recs[i].nat != nat)
            cases.append({"id": f"P4{k}", "pid": "P4", "arg": [idx, nat], "expected": exp})
    elif kind == "battles_ll":
        for k, (a, b) in enumerate([("1813", "1813"), ("1940", "1944"), ("1500", "1700"), ("1945", "1945"),
                                    ("1900", "1999")]):
            ya, yb = int(a), int(b)
            fr = sum(ya <= _year_of(r.born) <= yb for r in recs)
            both = sum(ya <= _year_of(r.born) and _year_of(r.death) <= yb for r in recs)
            over = sum(_year_of(r.born) <= yb and _year_of(r.death) >= ya for r in recs)
            to = sum(ya <= _year_of(r.death) <= yb for r in recs)
            cases.append({"id": f"P3{k}", "pid": "P3", "arg": [list(range(20)), a, b],
                          "expected": sorted({str(fr), str(both), str(over), str(to)})})
        for k, g in enumerate(["Napoleon Bonaparte", "Georgy Zhukov", "Joseph Joffre", "Nobody Here"]):
            exp = " | ".join(r.name for r in recs if g in r.items)
            cases.append({"id": f"P4{k}", "pid": "P4", "arg": [list(range(20)), g], "expected": exp})
    elif kind == "generals_bst":
        for k, y in enumerate(["1896 AD", "157 BC", "100 BC", "2000 AD", "1157 AD"]):
            yr, era = y.split()
            n = sum(r.born[2] == int(yr) and r.born[3] == era for r in recs)
            cases.append({"id": f"P3{k}", "pid": "P3", "arg": [list(range(20)), y], "expected": str(n)})
        for k, b in enumerate(["Battle of France", "Battle of Blenheim", "Battle of Arsuf", "Battle of Nowhere"]):
            keep = sorted((r for r in recs if b in r.items), key=lambda r: (_date_key(r.born), _date_key(r.death)))
            cases.append({"id": f"P4{k}", "pid": "P4", "arg": [list(range(20)), b],
                          "expected": " | ".join(r.name for r in keep)})
    return cases


def _p1_expected(kind: str, recs: list[Rec]) -> str:
    return " | ".join([str(len(recs))] + [r.name for r in recs])


def _bst_preorder(recs: list[Rec]) -> list[Rec]:
    root = None

    def key(r):
        return _date_key(r.born), _date_key(r.death)

    def ins(node, r):
        if node is None:
            return [r, None, None]
        if key(r) < key(node[0]):
            node[1] = ins(node[1], r)
        else:
            node[2] = ins(node[2], r)
        return node

    for r in recs:
        root = ins(root, r)
    out = []

    def pre(n):
        if n:
            out.append(n[0])
            pre(n[1])
            pre(n[2])
    pre(root)
    return out


# ---------------------------------------------------------------------------------------------- harness (C++)

PRELUDE = """#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cstring>
#include <cmath>
#include <vector>
using namespace std;
#define main __student_main_renamed
"""


def _cstr(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _make_general(kind: str, var: str, r: Rec) -> str:
    b, d = r.born, r.death
    s = (f"{var}.name = {_cstr(r.name)}; {var}.nationality = {_cstr(r.nat)}; "
         f"{var}.born.day = {b[0]}; {var}.born.month = {b[1]}; {var}.born.year = {b[2]}; {var}.born.era = {_cstr(b[3])}; "
         f"{var}.death.day = {d[0]}; {var}.death.month = {d[1]}; {var}.death.year = {d[2]}; {var}.death.era = {_cstr(d[3])}; ")
    if kind == "generals_bst":
        s += f"{var}.known_battles.clear(); " + "".join(f"{var}.known_battles.push_back({_cstr(x)}); " for x in r.items)
    else:
        s += (f"{var}.total_known_battles = {len(r.items)}; {var}.known_battles = new string[{len(r.items)}]; "
              + "".join(f"{var}.known_battles[{i}] = {_cstr(x)}; " for i, x in enumerate(r.items)))
    return s


def _make_battle(var: str, r: Rec) -> str:
    return (f"{var}.name = {_cstr(r.name)}; {var}.location = {_cstr(r.nat)}; {var}.from_date = {_cstr(r.born)}; "
            f"{var}.to_date = {_cstr(r.death)}; {var}.total_famous_generals = {len(r.items)}; "
            f"{var}.list_famous_generals = new string[{len(r.items)}]; "
            + "".join(f"{var}.list_famous_generals[{i}] = {_cstr(x)}; " for i, x in enumerate(r.items)))


def harness(kind: str, present=("P1", "P2", "P3", "P4")) -> str:
    """C++ appended after the student's code: main reads '<case id>' on stdin and prints one line. Only the
    problems in `present` (defined in the submission) are called, so a problem left out does not break the build."""
    recs = load_battles() if kind == "battles_ll" else load_generals()
    T = "Battle" if kind == "battles_ll" else "General"
    fld = "battle" if kind == "battles_ll" else "general"
    files = {k: _csv_text(kind, idx) for k, idx in P1_FILES.items()}
    lines = ["#undef main", "static const int HZ_CAP = 2000;"]
    # every record, built with the exam structs
    lines.append(f"static {T} HZ_REC[{len(recs)}];")
    lines.append("static void hz_build_recs() {")
    for i, r in enumerate(recs):
        lines.append("  " + (_make_battle(f"HZ_REC[{i}]", r) if kind == "battles_ll" else _make_general(kind, f"HZ_REC[{i}]", r)))
    lines.append("}")
    lines.append("static void hz_write_file(const string& path, const char* text) { ofstream f(path.c_str()); f << text; }")
    for k, txt in files.items():
        lines.append(f'static const char* HZ_FILE_{k} = R"CSVDATA({txt})CSVDATA";')
    if kind == "generals_bst":
        lines += [
            "static void hz_pre(Node* n, vector<string>& out, int& budget) { if (!n || budget-- <= 0) return;"
            " out.push_back(n->general.name); hz_pre(n->left, out, budget); hz_pre(n->right, out, budget); }",
            "static void hz_ino(Node* n, vector<string>& out, int& budget) { if (!n || budget-- <= 0) return;"
            " hz_ino(n->left, out, budget); out.push_back(n->general.name); hz_ino(n->right, out, budget); }",
            "static bool hz_earlier(const Date& a, const Date& b) { int ya = a.era == \"BC\" ? -a.year : a.year;"
            " int yb = b.era == \"BC\" ? -b.year : b.year; if (ya != yb) return ya < yb; if (a.month != b.month)"
            " return a.month < b.month; return a.day < b.day; }",
            "static bool hz_less(const General& a, const General& b) { if (hz_earlier(a.born, b.born)) return true;"
            " if (hz_earlier(b.born, a.born)) return false; return hz_earlier(a.death, b.death); }",
            "static Node* hz_ins(Node* n, const General& g) { if (!n) { Node* x = new Node(); x->general = g;"
            " x->left = NULL; x->right = NULL; return x; } if (hz_less(g, n->general)) n->left = hz_ins(n->left, g);"
            " else n->right = hz_ins(n->right, g); return n; }",
            "static string hz_join(const vector<string>& v) { string s; for (size_t i = 0; i < v.size(); ++i)"
            " { if (i) s += \" | \"; s += v[i]; } return s; }",
        ]
    else:
        lines += [
            f"static string hz_walk(Node* h) {{ string s; int k = 0; for (Node* p = h; p; p = p->next) {{"
            f" if (++k > HZ_CAP) return \"CYCLE\"; if (k > 1) s += \" | \"; s += p->{fld}.name; }} return s; }}",
            f"static Node* hz_mklist(const vector<int>& idx) {{ Node* h = NULL; Node* t = NULL; for (size_t i = 0;"
            f" i < idx.size(); ++i) {{ Node* x = new Node(); x->{fld} = HZ_REC[idx[i]]; x->next = NULL;"
            f" if (!h) h = x; else t->next = x; t = x; }} return h; }}",
        ]
    lines.append("static vector<int> hz_read_idx(istream& in) { int m; in >> m; vector<int> v(m); "
                 "for (int i = 0; i < m; ++i) in >> v[i]; return v; }")
    lines.append("int main() {")
    lines.append("  hz_build_recs(); string cid; cin >> cid;")
    # P1
    p1 = ("  if (cid[1] == '1') { string key = cid.substr(2); string path = \"input_\" + key + \"_data.csv\";"
          " hz_write_file(path, key == \"A\" ? HZ_FILE_A : key == \"B\" ? HZ_FILE_B : HZ_FILE_C);")
    if kind == "generals_bst":
        lines.append(p1 +"    vector<General> v = prob1(path); cout << v.size();"
                     " for (size_t i = 0; i < v.size() && i < HZ_CAP; ++i) cout << \" | \" << v[i].name; cout << endl; return 0; }")
    else:
        lines.append(p1 + f"    int n = 0; {T}* a = prob1(path, n); cout << n;"
                     " if (a) for (int i = 0; i < n && i < HZ_CAP; ++i) cout << \" | \" << a[i].name; cout << endl; return 0; }")
    lines.append("  vector<int> idx = hz_read_idx(cin);")
    # P2
    if kind == "generals_bst":
        lines.append("  if (cid[1] == '2') { vector<General> v; for (size_t i = 0; i < idx.size(); ++i)"
                     " v.push_back(HZ_REC[idx[i]]); Node* r = prob2(v); vector<string> o; int b = HZ_CAP; hz_pre(r, o, b);"
                     " cout << hz_join(o) << endl; return 0; }")
    else:
        lines.append(f"  if (cid[1] == '2') {{ {T}* a = new {T}[idx.size() + 1]; for (size_t i = 0; i < idx.size(); ++i)"
                     " a[i] = HZ_REC[idx[i]]; Node* h = prob2(a, (int)idx.size()); cout << hz_walk(h) << endl; return 0; }")
    # P3 / P4
    rest = "string arg; getline(cin >> ws, arg);"
    if kind == "generals_ll":
        lines.append("  Node* h = hz_mklist(idx);")
        lines.append("  if (cid[1] == '3') { General g = prob3(h); cout << g.name << endl; return 0; }")
        lines.append(f"  if (cid[1] == '4') {{ {rest} prob4(h, arg); cout << hz_walk(h) << endl; return 0; }}")
    elif kind == "battles_ll":
        lines.append("  Node* h = hz_mklist(idx);")
        lines.append("  if (cid[1] == '3') { string a, b; cin >> a >> b; cout << prob3(h, a, b) << endl; return 0; }")
        lines.append(f"  if (cid[1] == '4') {{ {rest} prob4(h, arg); cout << hz_walk(h) << endl; return 0; }}")
    else:
        lines.append("  Node* r = NULL; for (size_t i = 0; i < idx.size(); ++i) r = hz_ins(r, HZ_REC[idx[i]]);")
        lines.append(f"  if (cid[1] == '3') {{ {rest} cout << prob3(r, arg) << endl; return 0; }}")
        lines.append(f"  if (cid[1] == '4') {{ {rest} prob4(r, arg); vector<string> o; int b = HZ_CAP; hz_ino(r, o, b);"
                     " cout << hz_join(o) << endl; return 0; }")
    lines.append("  return 0;\n}")
    lines = [ln for ln in lines if not (ln.startswith("  if (cid[1] == '") and f"P{ln[17]}" not in present)]
    return "\n".join(lines) + "\n"


def case_stdin(c: dict) -> str:
    """stdin of one harness run: the case id, then the record indexes, then the problem's own arguments."""
    if c["pid"] == "P1":
        return c["id"] + "\n"
    arg = c["arg"]
    idx, extra = (arg, []) if isinstance(arg[0], int) else (arg[0], arg[1:])
    s = f"{c['id']}\n{len(idx)} {' '.join(map(str, idx))}\n"
    return s + (" ".join(extra) + "\n" if extra else "")


# ---------------------------------------------------------------------------------------------- code analysis

_PROTO = re.compile(r"\bprob([1-4])\s*\(([^)]*)\)\s*\{")


def function_bodies(code: str) -> dict[str, str]:
    """Body text of prob1..prob4 (comments removed); a problem absent from the code has no key."""
    src = strip_comments(code)
    out = {}
    for m in _PROTO.finditer(src):
        depth, i = 1, m.end()
        while i < len(src) and depth:
            depth += {"{": 1, "}": -1}.get(src[i], 0)
            i += 1
        out[f"P{m.group(1)}"] = src[m.end():i - 1]
    return out


_TRIVIAL_RETURN = re.compile(r"^\s*(return\s*(NULL|nullptr|0|-1|false|true|\{\s*\}|\w+\s*\(\s*\)|head|root|"
                             r"generals|battles|\w+)?\s*;\s*)?$", re.S)


def is_missing(body: str | None) -> bool:
    """Empty body, or only a trivial return / declaration of the result ("left empty" per the exam rules)."""
    if body is None:
        return True
    stmts = [s.strip() for s in body.split(";") if s.strip()]
    if not stmts:
        return True
    if len(stmts) == 1 and _TRIVIAL_RETURN.match(stmts[0] + ";"):
        return True
    if len(stmts) == 2 and re.match(r"^[\w<>:\*\s&]+\s+\w+(\s*=\s*[^;]+)?$", stmts[0]) and stmts[1].startswith("return"):
        return True
    return False


# P1 sized by a constant (rulebook: "kích thước mảng cứng"): an array of records / dates with a literal length
HARDCODE_SIZE = re.compile(r"new\s+(General|Battle|Date)\s*\[\s*\d+\s*\]|\b(General|Battle)\s+\w+\s*\[\s*\d+\s*\]"
                           r"|\bn\s*=\s*\d{2,}\s*;")
HARDCODE_FILE = re.compile(r"\"[^\"]*(\.csv|filename)[^\"]*\"", re.I)


@dataclass
class ExecResult:
    sample_id: str
    kind: str | None
    compiles: bool
    all_commented: bool
    harness_ok: bool = True               # multi: the harness compiled with the submission
    statuses: dict = field(default_factory=dict)   # case id -> status
    groups: dict = field(default_factory=dict)     # case id -> group (single) / pid (multi)
    states: dict = field(default_factory=dict)     # multi: P1..P4 -> ok/partial/fail/crash/timeout/missing
    hardcode_size: bool = False
    hardcode_file: bool = False
    uses_stoi: bool = False
    p1_variant_fail: bool = False          # multi: P1 right on the exam CSV, wrong on another file

    def to_json(self) -> dict:
        return self.__dict__


def _multi_status(actual: str, expected, rc: int | None, timeout: bool) -> str:
    if timeout:
        return "timeout"
    if rc:
        return "crash"
    a = " ".join(actual.split())
    if isinstance(expected, list):
        return "pass" if a in expected else "fail"
    return "pass" if a == " ".join(expected.split()) else "fail"


def _problem_states(statuses: dict, missing: dict) -> tuple[dict, bool]:
    states, p1_variant_fail = {}, False
    for pid in ("P1", "P2", "P3", "P4"):
        st = [v for k, v in statuses.items() if k.startswith(pid)]
        if missing.get(pid):
            states[pid] = "missing"
        elif not st:
            states[pid] = "missing"
        elif all(s == "pass" for s in st):
            states[pid] = "ok"
        elif "timeout" in st:
            states[pid] = "timeout"
        elif any(s == "pass" for s in st):
            states[pid] = "partial"
        elif "crash" in st:
            states[pid] = "crash"
        else:
            states[pid] = "fail"
    if statuses.get("P1A") == "pass" and states["P1"] != "ok":
        p1_variant_fail = True
    return states, p1_variant_fail


class Oracle:
    """Runs submissions with a Task 2 compiler (src/task2/compile.py) and caches the results on disk."""

    def __init__(self, compiler, cache_dir="outputs/task2/_exec_cache"):
        self.compiler = compiler
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self._harness, self._cases = {}, {}

    def _key(self, code: str, tests: list[str]) -> str:
        blob = json.dumps([self.compiler.compiler_id, code, tests, RUN_TIMEOUT])
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    def _jobs(self, sample, kind: str):
        if kind in ("armstrong", "dedup", "login"):
            tests = single_tests(kind)
            return sample.code, [t[1] for t in tests], tests
        present = tuple(sorted(function_bodies(sample.code)))
        if (kind, present) not in self._harness:
            self._harness[kind, present] = harness(kind, present)
        if kind not in self._cases:
            self._cases[kind] = multi_cases(kind)
        code = PRELUDE + sample.code.lstrip("\ufeff") + "\n" + self._harness[kind, present]
        return code, [case_stdin(c) for c in self._cases[kind]], self._cases[kind]

    def run(self, samples, exams: dict) -> dict[str, ExecResult]:
        results, todo = {}, []
        for s in samples:
            kind = exam_kind(exams[s.exam_id])
            commented = strip_comments(s.code) == ALL_COMMENTED
            r = ExecResult(s.sample_id, kind, compiles=not has_compile_error(s.compile_log), all_commented=commented)
            results[s.sample_id] = r
            if kind is None or not r.compiles or commented:
                continue
            code, stdin, tests = self._jobs(s, kind)
            key = self._key(code, stdin)
            todo.append((s, kind, code, stdin, tests, key))
        fresh = [t for t in todo if not (self.cache / f"{t[5]}.json").exists()]
        if fresh:
            print(f"[exec] running {len(fresh)} submissions ({sum(len(t[3]) for t in fresh)} runs)", flush=True)
            for i in range(0, len(fresh), 40):
                chunk = fresh[i:i + 40]
                outs = self.compiler.run([(t[2], "single_problem", t[3]) for t in chunk])
                for t, (log, rc, runs) in zip(chunk, outs):
                    row = {"log": log[-2000:], "rc": rc, "runs": runs}
                    (self.cache / f"{t[5]}.json").write_text(json.dumps(row), encoding="utf-8")
        for s, kind, code, stdin, tests, key in todo:
            row = json.loads((self.cache / f"{key}.json").read_text(encoding="utf-8"))
            self._fill(results[s.sample_id], s, kind, tests, row)
        return results

    def _fill(self, r: ExecResult, s, kind: str, tests, row: dict) -> None:
        runs = row.get("runs")
        bodies = function_bodies(s.code) if kind not in ("armstrong", "dedup", "login") else {}
        src = strip_comments(s.code)
        r.uses_stoi = bool(re.search(r"\bsto(i|f|d|l|ll)\s*\(|\batoi\s*\(|\batof\s*\(", src))
        p1 = bodies.get("P1", "")
        r.hardcode_size = bool(HARDCODE_SIZE.search(p1)) if bodies else False
        r.hardcode_file = bool(HARDCODE_FILE.search(p1)) if bodies else False
        if runs is None:  # the harness (or the program) did not build: unknown, not the student's fault here
            r.harness_ok = False
            return
        if kind in ("armstrong", "dedup", "login"):
            for k, ((group, _, expected), run) in enumerate(zip(tests, runs)):
                if run.get("timeout"):
                    st = "timeout"
                elif run.get("returncode"):
                    st = "runtime_error"
                else:
                    st = compare_output(run.get("actual", ""), expected)
                r.statuses[f"t{k:02d}"], r.groups[f"t{k:02d}"] = st, group
            return
        for c, run in zip(tests, runs):
            r.statuses[c["id"]] = _multi_status(run.get("actual", ""), c["expected"], run.get("returncode"),
                                                run.get("timeout"))
            r.groups[c["id"]] = c["pid"]
        missing = {pid: is_missing(bodies.get(pid)) for pid in ("P1", "P2", "P3", "P4")}
        r.states, r.p1_variant_fail = _problem_states(r.statuses, missing)


def write_results(results: dict[str, ExecResult], path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in results.values():
            f.write(json.dumps(r.to_json(), ensure_ascii=False) + "\n")


def env_compiler(ccfg: dict):
    from src.task2.compile import make_compiler
    return make_compiler(ccfg.get("backend", "auto"), ccfg.get("image", "gcc:13.3.0"),
                         os.path.join(ccfg.get("workdir", "outputs/task2/_compile_work") + "_exec"))
