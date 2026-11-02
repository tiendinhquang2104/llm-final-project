"""E2: suites generated from the statement (src/task2/test_gen.py) with a scripted stand-in for the LLM, the
execution oracle on them (needs a compiler) and the teacher-rule mapping.

The two exams here are made up for the tests (digit sum; a list of items read from a CSV): no competition exam,
statement or reference solution is used.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from src.task2.exec_oracle import ExecResult, Oracle, function_bodies, hardcode_file, hardcode_size, is_missing
from src.task2.exec_rules import RuleLabels, combine, rule_labels
from src.task2.test_gen import (SuiteBuilder, arg_params, extract_code, file_variants, prototypes, stub,
                                struct_names)

SINGLE = {"exam_id": "T-SUM", "exam_type": "single_problem", "problems": [
    {"pid": "P1", "io_mode": "stdin/stdout", "constraints": "1 <= n <= 10^9"}],
    "statement": "Read a positive integer n and print the sum of its digits.\n\n**Example:**\n\n"
                 "| Input | Output |\n|---|---|\n| 123 | 6 |\n| 9 | 9 |\n"}

SUM_OK = "#include <iostream>\nint main(){long long n,s=0;std::cin>>n;while(n){s+=n%10;n/=10;}std::cout<<s;}\n"
SUM_OK2 = ("#include <iostream>\n#include <string>\nint main(){std::string t;std::cin>>t;int s=0;"
           "for(char c:t)s+=c-'0';std::cout<<s<<\"\\n\";}\n")
SUM_BAD = "#include <iostream>\nint main(){long long n;std::cin>>n;std::cout<<n%10+n/10;}\n"   # passes neither example
SUM_GEN = ("#include <iostream>\nint main(){long long v[]={1,10,1000000000,999999999,5};"
           "for(int i=0;i<30;i++){if(i<5)std::cout<<v[i];else std::cout<<(i*7919LL)%1000000000+1;"
           "std::cout<<\"\\n=====\\n\";}}\n")

STRUCTS = "struct Item {\n    string name;\n    int qty;\n};\nstruct Node {\n    Item item;\n    Node* next;\n};\n"
MULTI = {"exam_id": "T-ITEMS", "exam_type": "multi_problem", "data_file": "items.csv",
         "grading_policy": "If P1 is wrong, P2-P3 are not graded.",
         "statement": "Given the structures\n```cpp\n" + STRUCTS + "```\nP1 reads all items of the file. P2 builds a "
                      "linked list in file order. P3 removes every item whose name is the given one.",
         "problems": [{"pid": "P1", "prototype": "Item* prob1(string filename, int& n);",
                       "is_prerequisite_for": ["P2", "P3"]},
                      {"pid": "P2", "prototype": "Node* prob2(Item* items, int n);"},
                      {"pid": "P3", "prototype": "void prob3(Node*& head, string name);"}]}
CSV = "Name,Qty\npen,3\nbook,1\npen,7\ncup,2\nbox,5\nink,4\n"

ITEMS_OK = """#include <fstream>
#include <sstream>
#include <string>
using namespace std;
""" + STRUCTS + """
Item* prob1(string filename, int& n) {
    ifstream f(filename); string line; n = 0;
    getline(f, line);
    string rows[1000];
    while (getline(f, line)) if (!line.empty()) rows[n++] = line;
    Item* a = new Item[n];
    for (int i = 0; i < n; i++) {
        stringstream ss(rows[i]); string q;
        getline(ss, a[i].name, ','); getline(ss, q, ','); a[i].qty = stoi(q);
    }
    return a;
}
Node* prob2(Item* items, int n) {
    Node* head = NULL; Node* tail = NULL;
    for (int i = 0; i < n; i++) {
        Node* p = new Node{items[i], NULL};
        if (!head) head = p; else tail->next = p;
        tail = p;
    }
    return head;
}
void prob3(Node*& head, string name) {
    while (head && head->item.name == name) head = head->next;
    for (Node* p = head; p && p->next;) {
        if (p->next->item.name == name) p->next = p->next->next; else p = p->next;
    }
}
"""
ITEMS_FIXED20 = ITEMS_OK.replace("Item* a = new Item[n];", "n = 6; Item* a = new Item[6];")
ITEMS_P3_EMPTY = ITEMS_OK[:ITEMS_OK.index("void prob3")] + "void prob3(Node*& head, string name) {\n}\n"
ITEMS_P3_LOOP = ITEMS_OK.replace("else p = p->next;", "")
DRIVER = """```cpp
void drv_print(Node* h) { for (; h; h = h->next) cout << h->item.name << " " << h->item.qty << "\\n"; }
int main() {
    string pid, file, arg; getline(cin, pid); getline(cin, file);
    int n = 0; Item* a = prob1(file, n);
    if (pid == "P1") { cout << n << "\\n"; for (int i = 0; i < n; i++) cout << a[i].name << " " << a[i].qty << "\\n"; return 0; }
    Node* h = prob2(a, n);
    if (pid == "P3") { getline(cin, arg); prob3(h, arg); }
    drv_print(h);
    return 0;
}
```"""


class FakeLLM:
    """Answers by prompt kind, as the local model would (code in a ```cpp block)."""
    model, revision = "fake", None

    def generate(self, requests, gen):
        tag = requests[0]["sample"].sample_id
        n = gen.get("n", 1)
        if tag.endswith(":ref") and tag.startswith("T-SUM"):
            answers = [SUM_OK, SUM_OK2, SUM_BAD, "int main( {"]
        elif tag.endswith(":gen"):
            answers = [SUM_GEN, "not code"]
        elif tag.endswith(":ref"):
            answers = [ITEMS_OK, ITEMS_OK.replace("rows[n++] = line", "rows[n++] = line;"), "struct X {"]
        elif tag.endswith(":driver"):
            answers = [DRIVER, "int main() { return 0; }"]
        elif tag.endswith(":args"):
            answers = ['{"P3": [["pen"], ["zzz"]]}']
        else:  # repair: give up
            answers = ["struct X {"]
        return [[f"```cpp\n{a}\n```" if not a.startswith("```") and not a.startswith("{") else a
                 for a in (answers * n)[:n]]]


def _compiler():
    from src.task2.exec_oracle import env_compiler
    if shutil.which("g++") and Path("/proc").exists():
        return env_compiler({"backend": "native"})
    if shutil.which("docker") and subprocess.run(["docker", "info"], capture_output=True).returncode == 0:
        return env_compiler({"backend": "docker"})
    return None


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    comp = _compiler()
    if comp is None:
        pytest.skip("needs g++ (Linux) or a running Docker")
    d = tmp_path_factory.mktemp("tg")
    (d / "items.csv").write_text(CSV, encoding="utf-8")
    b = SuiteBuilder(FakeLLM(), comp, d / "cache", k=4)
    return comp, b.build(SINGLE), b.build(MULTI, d)


def _sample(sid, exam, code):
    return NS(sample_id=sid, exam_id=exam["exam_id"], code=code, compile_log="")


def test_single_suite_majority_of_references_that_pass_the_examples(built):
    _, single, _ = built
    assert single.stats["refs_kept"] == 2                      # wrong one and non-compiling one dropped
    by_in = {t["stdin"].strip(): t["expected"].strip() for t in single.tests}
    assert by_in["123"] == "6" and by_in["999999999"] == "81" and by_in["1000000000"] == "1"
    assert {t["group"] for t in single.tests} == {"example", "edge", "normal"}


def test_multi_suite_and_oracle_states(built, tmp_path):
    comp, _, multi = built
    assert multi.pids == ["P1", "P2", "P3"] and multi.prereq == {"P1": ["P2", "P3"]}
    assert [t["id"] for t in multi.tests if t["pid"] == "P1"] == ["P1A", "P1B", "P1C"]
    exams = {"T-ITEMS": MULTI}
    samples = [_sample("ok", MULTI, ITEMS_OK), _sample("fixed", MULTI, ITEMS_FIXED20),
               _sample("empty", MULTI, ITEMS_P3_EMPTY), _sample("loop", MULTI, ITEMS_P3_LOOP),
               _sample("nomain", MULTI, ITEMS_OK + "\nint main() { return 0; }\n")]
    res = Oracle(comp, cache_dir=tmp_path).run(samples, exams, {"T-ITEMS": multi})
    assert res["ok"].states == {"P1": "ok", "P2": "ok", "P3": "ok"} and rule_labels(res["ok"]).labels == []
    assert res["nomain"].states["P1"] == "ok"                  # the student's own main is renamed
    assert res["fixed"].p1_variant_fail and res["fixed"].hardcode_size
    assert rule_labels(res["fixed"]).labels == ["Lỗi hard-code"]
    assert res["empty"].states["P3"] == "missing" and rule_labels(res["empty"]).labels == []
    assert res["loop"].states["P3"] == "timeout"
    assert rule_labels(res["loop"]).labels == ["Lỗi logic", "Lỗi vòng lặp"]


def test_single_oracle_statuses(built, tmp_path):
    comp, single, _ = built
    res = Oracle(comp, cache_dir=tmp_path).run(
        [_sample("ok", SINGLE, SUM_OK2), _sample("bad", SINGLE, SUM_BAD)], {"T-SUM": SINGLE}, {"T-SUM": single})
    assert rule_labels(res["ok"]).labels == [] and rule_labels(res["ok"]).sure
    bad = rule_labels(res["bad"])
    assert bad.labels == ["Lỗi logic"] and not bad.sure


def test_exam_parsing_helpers():
    assert struct_names(MULTI["statement"]) == ["Item", "Node"]
    protos = prototypes(MULTI)
    assert list(protos) == ["P1", "P2", "P3"]
    assert [arg_params(p) for p in protos.values()] == [["string filename"], [], ["string name"]]
    assert stub(protos["P3"]).endswith("{}") and stub(protos["P2"]).endswith("{ return {}; }")
    v = file_variants("items.csv", CSV)
    assert list(v) == ["items.csv", "items_short.csv", "items_long.csv"]
    assert [len(t.strip().split("\n")) - 1 for t in v.values()] == [6, 2, 10]
    assert extract_code("text\n```cpp\nint main(){}\n```\nmore") == "int main(){}"


def test_function_bodies_and_static_checks():
    protos = prototypes(MULTI)
    code = ("Item* prob1(string f, int& n) {\n  // todo\n}\nNode* prob2(Item* g, int n) { return NULL; }\n"
            "void prob3(Node*& h, string s) { while (h) h = h->next; }\n")
    b = function_bodies(code, protos)
    assert set(b) == {"P1", "P2", "P3"}
    assert is_missing(b["P1"]) and is_missing(b["P2"]) and not is_missing(b["P3"]) and is_missing(None)
    assert hardcode_size("Item* a = new Item[20];", ["Item"]) and not hardcode_size("new Item[n];", ["Item"])
    assert hardcode_file('ifstream f("items.csv");', "items.csv") and not hardcode_file("ifstream f(filename);", None)


def _res(**kw):
    base = dict(sample_id="x", kind="single_problem", compiles=True, all_commented=False)
    return ExecResult(**{**base, **kw})


def test_rules_single_and_multi():
    assert rule_labels(_res(compiles=False)).labels == ["Lỗi biên dịch"]
    assert rule_labels(_res(compiles=False), '#include "items.csv"\n').labels == ["Lỗi biên dịch", "Lỗi hard-code"]
    assert rule_labels(_res(all_commented=True)).labels == ["Lỗi style"]
    assert rule_labels(_res(statuses={"t0": "pass", "t1": "prompt_then_pass"})).labels == []
    assert rule_labels(_res(statuses={"t0": "whitespace", "t1": "pass"})).labels == ["Lỗi nhập/xuất"]
    assert rule_labels(_res(statuses={"t0": "timeout", "t1": "fail"})).labels == ["Lỗi logic", "Lỗi vòng lặp"]
    wrong = rule_labels(_res(statuses={"t0": "fail", "t1": "pass"}))
    assert wrong.labels == ["Lỗi logic"] and not wrong.sure
    multi = dict(kind="multi_problem", statuses={"P1A": "pass"}, prereq={"P1": ["P2", "P3", "P4"]})
    st = {"P1": "fail", "P2": "ok", "P3": "ok", "P4": "ok"}
    assert rule_labels(_res(**multi, states=st, hardcode_size=True)).labels == ["Lỗi hard-code"]
    assert rule_labels(_res(**multi, states={**st, "P1": "crash"}, uses_stoi=True)).labels == ["Lỗi hàm"]
    assert rule_labels(_res(**multi, states={**st, "P1": "ok", "P2": "fail", "P4": "partial"})).labels == ["Lỗi thuật toán"]
    assert rule_labels(_res(**multi, states={**st, "P1": "ok", "P4": "partial"})).labels == ["Lỗi logic"]
    assert rule_labels(_res(**multi, states={"P1": "ok", "P2": "ok", "P3": "missing", "P4": "missing"})).labels == []
    assert rule_labels(_res(kind=None)) is None and rule_labels(_res(harness_ok=False)) is None


def test_combine_adds_model_causes_only_when_unsure():
    sure = RuleLabels([], True, "all pass")
    unsure = RuleLabels(["Lỗi logic"], False, "wrong values")
    model = ["Lỗi hàm", "Lỗi style", "Lỗi vòng lặp", "Lỗi thuật toán"]
    assert combine(sure, model) == []
    assert combine(unsure, model) == ["Lỗi logic", "Lỗi hàm", "Lỗi vòng lặp"]
    assert combine(unsure, None) == ["Lỗi logic"]
    assert combine(None, ["Lỗi style"]) == ["Lỗi style"] and combine(None, None) == ["Lỗi logic"]


def test_suite_nobody_passes_on_the_prerequisite_is_not_trusted():
    from src.task2.exec_oracle import distrust_suites
    pre = {"P1": ["P2"]}
    samples = [NS(sample_id=f"s{i}", exam_id="E") for i in range(6)] + [NS(sample_id="t0", exam_id="F")]
    res = {f"s{i}": _res(kind="multi_problem", states={"P1": "fail", "P2": "ok"}, prereq=pre) for i in range(6)}
    res["t0"] = _res(kind="multi_problem", states={"P1": "fail", "P2": "ok"}, prereq=pre)
    assert distrust_suites(res, samples) == ["E"]          # F has too few runs to judge
    assert rule_labels(res["s0"]) is None and rule_labels(res["t0"]).labels == ["Lỗi logic"]
    res["s5"].kind, res["s5"].states = "multi_problem", {"P1": "ok", "P2": "ok"}
    for i in range(5):
        res[f"s{i}"].kind = "multi_problem"
    assert distrust_suites(res, samples) == []


def test_probe_suite_judges_record_counts_and_crashes_only(built, tmp_path):
    comp, _, multi = built
    probe = multi.as_probe()
    assert [t.get("rows") for t in probe.tests if t["pid"] == "P1"] == [6, 2, 10]
    assert all(t["expected"] is None for t in probe.tests) and not multi.probe
    crash = ITEMS_OK.replace("while (head && head->item.name == name) head = head->next;",
                             "Node* z = NULL; z->next = head;")
    samples = [_sample("ok", MULTI, ITEMS_OK), _sample("fixed", MULTI, ITEMS_FIXED20),
               _sample("loop", MULTI, ITEMS_P3_LOOP), _sample("crash", MULTI, crash)]
    res = Oracle(comp, cache_dir=tmp_path).run(samples, {"T-ITEMS": MULTI}, {"T-ITEMS": probe})
    assert res["ok"].probe and res["ok"].states == {"P1": "ok", "P2": "ran", "P3": "ran"}
    assert rule_labels(res["ok"]) is None                       # nothing wrong seen, nothing known right
    assert rule_labels(res["fixed"]).labels == ["Lỗi hard-code"]
    assert rule_labels(res["loop"]).labels == ["Lỗi logic", "Lỗi vòng lặp"]
    assert res["crash"].states["P3"] == "crash" and rule_labels(res["crash"]).labels == ["Lỗi logic"]


def test_memory_fault_on_every_run_adds_the_array_label():
    multi = dict(kind="multi_problem", prereq={"P1": ["P2"]}, states={"P1": "crash", "P2": "crash"})
    rl = rule_labels(_res(**multi, all_segfault=True))
    assert rl.labels == ["Lỗi logic", "Lỗi mảng/chuỗi"] and not rl.sure
    assert rule_labels(_res(**multi)).labels == ["Lỗi logic"]
    single = rule_labels(_res(statuses={"t0": "runtime_error"}, all_segfault=True))
    assert single.labels == ["Lỗi logic", "Lỗi mảng/chuỗi"]
