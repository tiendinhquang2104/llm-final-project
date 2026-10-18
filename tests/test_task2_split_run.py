import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.task2 import compile as comp
from src.task2.compile import CompileCache, attach_compile_logs, compare_output, run_report
from src.task2.data import Task2Dataset, Task2Sample
from src.task2.examples import input_lines, statement_examples
from src.task2.pipeline import Task2ApiPipeline
from src.task2.prompts_cot import HIDDEN, build_cot_messages, compact_compile_log, numbered_code
from src.task2.split import function_defs, merge_parts, prerequisites, split_submission, statement_for
from tests._task2 import FakeBackend

STATEMENT_2LINES = """## Exercise
**Input:**

The input is read from the console with:

    - The first line contains $n$.
    - The second line contains $n$ integers.

**Output:**

    - The count.

**Example:**

| Input | Output |
|---|---|
| 3 | 2 |
| 1 1 2 | 1 2 |
| 1 | 1 |
| 7 | 7 |
"""

STATEMENT_PROSE = """**Input:** một số nguyên `n` duy nhất.

| Input | Output |
|---|---|
| `1634` | `True` |
| `123` | `False` |
"""

PROBLEMS = [{"pid": "P1", "prototype": "int prob1(string filename);", "is_prerequisite_for": ["P2", "P3"]},
            {"pid": "P2", "prototype": "int prob2(int n);"},
            {"pid": "P3", "prototype": "void prob3(int& n);"}]
MULTI_STATEMENT = ("Shared structs.\n\n**Problem 1 (1 điểm).** Read the file.\n\n**Problem 2 (4 điểm).** Use Problem 1."
                   "\n\n**Problem 3 (5 điểm).** Change n.\n")
MULTI_EXAM = {"exam_id": "EXM", "exam_type": "multi_problem", "language": "cpp11", "statement": MULTI_STATEMENT,
              "problems": PROBLEMS}

CODE = """#include <iostream>
using namespace std;
struct A { int f() { return 1; } };
int helper(int x) {
    return x + 1;
}
int unused() { return 0; }
int prob1(string filename) {
    return 0;
}
int prob2(int n)
{
    // calls a helper
    return helper(n) + prob1("x");
}
void prob3(int& n) { n = 3; }
"""


class TestExamples(unittest.TestCase):
    def test_bullet_lines_group_table_rows(self):
        exam = {"exam_type": "single_problem", "statement": STATEMENT_2LINES,
                "problems": [{"pid": "P1", "io_mode": "stdin/stdout"}]}
        self.assertEqual(input_lines(STATEMENT_2LINES), 2)
        self.assertEqual(statement_examples(exam), [{"input": "3\n1 1 2\n", "expected": "2\n1 2"},
                                                    {"input": "1\n7\n", "expected": "1\n7"}])

    def test_prose_input_one_row_per_example_and_backticks(self):
        exam = {"exam_type": "single_problem", "statement": STATEMENT_PROSE, "problems": []}
        self.assertEqual(statement_examples(exam), [{"input": "1634\n", "expected": "True"},
                                                    {"input": "123\n", "expected": "False"}])

    def test_no_examples_for_multi_problem_or_no_table(self):
        self.assertEqual(statement_examples({"exam_type": "multi_problem", "statement": STATEMENT_PROSE}), [])
        self.assertEqual(statement_examples({"exam_type": "single_problem", "statement": "no table"}), [])


class TestCompare(unittest.TestCase):
    def test_statuses(self):
        self.assertEqual(compare_output("True\n", "True"), "pass")
        self.assertEqual(compare_output("1 5 3 \n2 \n\n", "1 5 3\n2"), "pass")  # trailing spaces / lines ignored
        self.assertEqual(compare_output("Nhap n: True", "True"), "prompt_then_pass")
        self.assertEqual(compare_output("6 1 5 3", "6\n1 5 3"), "whitespace")
        self.assertEqual(compare_output("TRUE", "True"), "case")
        self.assertEqual(compare_output("False", "True"), "fail")
        self.assertEqual(compare_output("", "True"), "fail")

    def test_run_report(self):
        ex = [{"input": "1\n", "expected": "True"}] * 3
        runs = [{"actual": "True", "returncode": 0, "timeout": False},
                {"actual": "", "returncode": 124, "timeout": True},
                {"actual": "Tr", "returncode": 139, "timeout": False}]
        self.assertEqual([r["status"] for r in run_report(ex, runs)], ["pass", "timeout", "runtime_error"])
        self.assertEqual([r["passed"] for r in run_report(ex, runs)], [True, False, False])
        self.assertIsNone(run_report(ex, None))   # did not compile
        self.assertIsNone(run_report([], []))


class FakeRunCompiler:
    compiler_id = "fake:g++"

    def __init__(self):
        self.calls = []

    def run(self, jobs):
        self.calls.append(list(jobs))
        out = []
        for job in jobs:
            if len(job) == 2:
                out.append(("", 0))
            elif "bad" in job[0]:
                out.append(("student.cpp:1:1: error: x", 1, None))
            else:
                out.append(("", 0, [{"actual": "True" if "ok" in job[0] else "TRUE", "returncode": 0, "timeout": False}
                                    for _ in job[2]]))
        return out


def smp(sid, code, exam="EX2", exam_type="single_problem"):
    return Task2Sample(sid, exam, exam_type, "cpp11", f"{sid}.cpp", code, None, None, [])


class TestRunHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.exams = {"EX2": {"exam_type": "single_problem", "statement": STATEMENT_PROSE,
                              "problems": [{"pid": "P1", "io_mode": "stdin/stdout"}]},
                      "EXM": MULTI_EXAM}

    def tearDown(self):
        self.tmp.cleanup()

    def test_cache_key_unchanged_without_examples(self):
        cache = CompileCache(FakeRunCompiler(), self.tmp.name)
        old = __import__("hashlib").sha256(json.dumps(
            ["fake:g++", comp.compile_args("single_problem"), "code"]).encode()).hexdigest()[:32]
        self.assertEqual(cache._key("code", "single_problem"), old)
        self.assertNotEqual(cache._key("code", "single_problem", ["1\n"]), old)

    def test_attach_runs_examples_and_caches(self):
        fake = FakeRunCompiler()
        cfg = {"cache_dir": self.tmp.name, "run_examples": True}
        lists = [[smp("ok1", "ok"), smp("up", "up"), smp("bad", "bad"), smp("m", "int prob1(){}", "EXM", "multi_problem")]]
        orig = comp.make_compiler
        comp.make_compiler = lambda *a, **k: fake
        try:
            (out,), cid = attach_compile_logs(cfg, lists, exams=self.exams)
            (again,), _ = attach_compile_logs(cfg, lists, exams=self.exams)
        finally:
            comp.make_compiler = orig
        by = {s.sample_id: s for s in out}
        self.assertEqual([r["status"] for r in by["ok1"].test_report], ["pass", "fail"])  # expected True / False
        self.assertEqual([r["status"] for r in by["up"].test_report], ["case", "fail"])
        self.assertIsNone(by["bad"].test_report)          # did not compile: not run
        self.assertIsNone(by["m"].test_report)            # multi_problem: compile only
        self.assertEqual(len(fake.calls[0][0]), 3)        # (code, exam_type, inputs)
        self.assertEqual(len(fake.calls), 1)              # second call fully cached
        self.assertEqual(by["up"].test_report, {s.sample_id: s for s in again}["up"].test_report)

    def test_run_examples_off_clears_test_report(self):
        fake = FakeRunCompiler()
        orig = comp.make_compiler
        comp.make_compiler = lambda *a, **k: fake
        try:
            (out,), _ = attach_compile_logs({"cache_dir": self.tmp.name},
                                            [[Task2Sample("x", "EX2", "single_problem", "cpp11", "x.cpp", "ok", None,
                                                          [{"input": "1", "passed": True}], [])]], exams=self.exams)
        finally:
            comp.make_compiler = orig
        self.assertIsNone(out[0].test_report)

    @unittest.skipUnless(shutil.which("g++"), "needs a C++ compiler")
    def test_native_runs_with_timeout_and_crash(self):
        progs = {"echo": '#include <iostream>\nint main(){std::string s; std::cin>>s; std::cout<<s;}',
                 "loop": "int main(){ volatile int x=0; while(true){x++;} }",
                 "crash": "#include <cstdlib>\nint main(){ abort(); }",
                 "bad": "int main(){ x; }"}
        nc = comp.NativeCompiler("g++")
        orig = comp.RUN_TIMEOUT
        comp.RUN_TIMEOUT = 1
        try:
            res = nc.run([(c, "single_problem", ["hi\n"]) for c in progs.values()])
        finally:
            comp.RUN_TIMEOUT = orig
        got = dict(zip(progs, res))
        self.assertEqual(got["echo"][2][0]["actual"], "hi")
        self.assertTrue(got["loop"][2][0]["timeout"])
        self.assertNotEqual(got["crash"][2][0]["returncode"], 0)
        self.assertIsNone(got["bad"][2])


class TestSplit(unittest.TestCase):
    def test_function_defs_top_level_only(self):
        names = [d.name for d in function_defs(CODE)]
        self.assertEqual(names, ["helper", "unused", "prob1", "prob2", "prob3"])  # A::f is inside the struct
        p2 = [d for d in function_defs(CODE) if d.name == "prob2"][0]
        self.assertEqual((p2.start, p2.end), (11, 15))
        self.assertEqual(p2.calls, {"helper", "prob1"})

    def test_parts_hide_other_questions_and_unused_helpers(self):
        parts = {p.pid: p for p in split_submission(CODE, PROBLEMS)}
        p2 = parts["P2"]
        self.assertIn(4, p2.lines)            # helper, called by prob2
        self.assertNotIn(7, p2.lines)         # unused()
        self.assertNotIn(8, p2.lines)         # prob1: another question, even though prob2 calls it
        self.assertIn(3, p2.lines)            # struct outside functions stays
        self.assertEqual(p2.own, set(range(11, 16)))
        self.assertEqual(p2.code.split("\n")[7], HIDDEN)
        self.assertNotIn("calls a helper", p2.code)  # comment-free code
        self.assertEqual(len(p2.code.split("\n")), len(CODE.split("\n")))  # line numbers kept

    def test_missing_question_and_unsplittable(self):
        code = CODE.replace("void prob3(int& n) { n = 3; }", "")
        p3 = {p.pid: p for p in split_submission(code, PROBLEMS)}["P3"]
        self.assertFalse(p3.found)
        self.assertIn(7, p3.lines)            # unused() stays visible: the attempt may be there
        self.assertNotIn(9, p3.lines)
        self.assertIsNone(split_submission("// int prob1(){}", PROBLEMS))
        self.assertIsNone(split_submission("int main(){}", PROBLEMS))
        self.assertIsNone(split_submission(CODE, [{"pid": "P1"}]))

    def test_statement_for_drops_later_questions(self):
        self.assertNotIn("Problem 2", statement_for(MULTI_STATEMENT, PROBLEMS, "P1"))
        self.assertIn("Shared structs", statement_for(MULTI_STATEMENT, PROBLEMS, "P1"))
        s2 = statement_for(MULTI_STATEMENT, PROBLEMS, "P2")
        self.assertIn("Problem 1", s2)
        self.assertNotIn("Problem 3", s2)
        self.assertEqual(statement_for(MULTI_STATEMENT, PROBLEMS, "P3"), MULTI_STATEMENT)
        self.assertEqual(statement_for("no headings", PROBLEMS, "P1"), "no headings")

    def test_merge_follows_prerequisites(self):
        self.assertEqual(prerequisites(PROBLEMS), {"P1": set(), "P2": {"P1"}, "P3": {"P1"}})
        labs, graded = merge_parts(PROBLEMS, {"P1": ["Lỗi hard-code"], "P2": ["Lỗi logic"], "P3": []})
        self.assertEqual((labs, graded), (["Lỗi hard-code"], ["P1"]))
        labs, graded = merge_parts(PROBLEMS, {"P1": [], "P2": ["Lỗi logic"], "P3": ["Lỗi hàm", "Lỗi logic"]})
        self.assertEqual((labs, graded), (["Lỗi logic", "Lỗi hàm"], ["P1", "P2", "P3"]))
        labs, graded = merge_parts(PROBLEMS, {"P1": [], "P2": ["Lỗi logic"], "P3": []}, {"P1"})
        self.assertEqual((labs, graded), ([], ["P1"]))   # compiler error inside P1's own lines
        chain = [{"pid": "P1", "is_prerequisite_for": ["P2"]}, {"pid": "P2", "is_prerequisite_for": ["P3"]},
                 {"pid": "P3"}]
        self.assertEqual(merge_parts(chain, {"P1": [], "P2": ["Lỗi logic"], "P3": ["Lỗi hàm"]}),
                         (["Lỗi logic"], ["P1", "P2"]))


class TestPartPrompt(unittest.TestCase):
    def test_numbered_code_collapses_hidden_runs(self):
        code = "\n".join(["a", HIDDEN, "", HIDDEN, "b", "", "c"])
        self.assertEqual(numbered_code(code, hidden="// H").splitlines(),
                         ["   1| a", "    | // H", "   5| b", "   6| ", "   7| c"])

    def test_compile_log_keeps_visible_lines(self):
        log = ("student.cpp:3:1: error: a\n    3 | x\n      | ^\nstudent.cpp:9:2: error: b\n    9 | y\n")
        self.assertIn("error: a", compact_compile_log(log, 800, "en", {3}))
        self.assertNotIn("error: b", compact_compile_log(log, 800, "en", {3}))
        self.assertIn("2 errors are in other", compact_compile_log(log, 800, "en", {5}))

    def test_part_prompt_and_run_report(self):
        cfg = {"lang": "vi", "strip_comments": True, "drop_blank_lines": True, "max_compile_log_chars": 800,
               "use_aux_signals": True}
        sample = smp("m", CODE, "EXM", "multi_problem")
        part = split_submission(CODE, PROBLEMS)[1]
        text = build_cot_messages(MULTI_EXAM, sample, cfg, (), part)[1]["content"]
        self.assertIn("## CÂU CẦN CHẤM: P2", text)
        self.assertIn("đã ẩn", text)
        self.assertNotIn("Problem 3", text)
        self.assertNotIn("n = 3", text)
        report = run_report([{"input": "1\n", "expected": "True"}], [{"actual": "TRUE", "returncode": 0,
                                                                    "timeout": False}])
        single = Task2Sample("s", "EX2", "single_problem", "cpp11", "s.cpp", "int main(){}", "", report, [])
        exam = {"exam_id": "EX2", "exam_type": "single_problem", "statement": STATEMENT_PROSE, "problems": []}
        text = build_cot_messages(exam, single, {**cfg, "lang": "en"})[1]["content"]
        self.assertIn("0/1 examples match", text)
        self.assertIn("WRONG only in letter case", text)


def cot(*labels):
    return "1. ...\nCONCLUSION: " + json.dumps({"taxonomy_error": list(labels)}, ensure_ascii=False)


class TestSplitPipeline(unittest.TestCase):
    def setUp(self):
        self.ds = Task2Dataset(Path("."), {"EXM": MULTI_EXAM}, [smp("m", CODE, "EXM", "multi_problem")])
        self.cfg = {"name": "t", "prompt": {"style": "cot", "lang": "en", "split_problems": True,
                                            "compile_rule": True, "strip_comments": True},
                    "generation": {"temperature": 0.0, "n": 1}, "retry_on_parse_fail": 1}

    def run_pipe(self, texts, log=""):
        self.ds.samples[0].compile_log = log
        be = FakeBackend(texts)
        pipe = Task2ApiPipeline(self.ds, be, self.cfg)
        rec = pipe.infer(self.ds.samples)[0]
        return be, rec, pipe.postprocess(rec)

    def test_one_request_per_question_merged_by_prerequisite(self):
        be, rec, out = self.run_pipe([cot(), cot("Lỗi logic"), cot("Lỗi hàm")])
        self.assertEqual([c["pid"] for c in be.calls], ["P1", "P2", "P3"])
        self.assertEqual([p["pid"] for p in rec["parts"]], ["P1", "P2", "P3"])
        self.assertTrue(rec["outputs"][1].startswith("### P2\n"))
        self.assertEqual(out["labels"], ["Lỗi logic", "Lỗi hàm"])
        self.assertTrue(out["parse_ok"])
        _, _, out = self.run_pipe([cot("Lỗi hard-code"), cot("Lỗi logic"), cot("Lỗi hàm")])
        self.assertEqual(out["labels"], ["Lỗi hard-code"])     # P1 wrong: P2, P3 not graded
        self.assertEqual([p["graded"] for p in out["parts"]], [True, False, False])
        self.assertLess(out["probs"]["Lỗi logic"], 0.5)

    def test_compile_rule_and_compile_error_inside_prerequisite(self):
        log = "student.cpp:9:5: error: oops\n"            # inside prob1 (lines 8-10)
        _, _, out = self.run_pipe([cot("Lỗi biên dịch"), cot("Lỗi logic"), cot()], log)
        self.assertEqual(out["labels"], ["Lỗi biên dịch"])
        self.assertTrue(out["parts"][0]["compile_error_here"])
        _, _, out = self.run_pipe([cot(), cot("Lỗi logic", "Lỗi biên dịch"), cot()], "")
        self.assertEqual(out["labels"], ["Lỗi logic"])         # the rule removes the model's compile vote

    def test_retry_only_the_unparsed_question(self):
        be, rec, out = self.run_pipe([cot(), "no conclusion", cot(), cot("Lỗi logic")])
        self.assertEqual(len(be.calls), 4)
        self.assertEqual(be.calls[3]["pid"], "P2")
        self.assertEqual(out["labels"], ["Lỗi logic"])

    def test_not_split_without_flag(self):
        self.cfg["prompt"]["split_problems"] = False
        be, rec, _ = self.run_pipe([cot()])
        self.assertEqual(len(be.calls), 1)
        self.assertNotIn("parts", rec)


if __name__ == "__main__":
    unittest.main()
