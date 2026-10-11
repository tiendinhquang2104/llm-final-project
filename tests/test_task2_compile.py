import tempfile
import unittest
from pathlib import Path

from src.task2.compile import CompileCache, compile_args, has_compile_error, with_compile_logs
from src.task2.data import Task2Sample

LOG_ERR = ("/tmp/tmpab12cd34/student.cpp: In function 'int main()':\n"
           "/tmp/tmpab12cd34/student.cpp:5:3: error: 'x' was not declared in this scope\n")
LOG_FATAL = '/tmp/tmpq/student.cpp:5:10: fatal error: data.csv: No such file or directory\n'
LOG_LINK = ("/usr/bin/ld: Scrt1.o: in function `_start':\n(.text+0x1b): undefined reference to `main'\n"
            "collect2: error: ld returned 1 exit status\n")
LOG_WARN = "/tmp/tmpz/student.cpp:10:1: warning: no return statement [-Wreturn-type]\n"


class FakeCompiler:
    compiler_id = "fake:g++ 13.3.0"

    def __init__(self):
        self.calls = []

    def run(self, jobs):
        self.calls.append(list(jobs))
        return [(("ERR " if "bad" in code else "") + exam_type, 1 if "bad" in code else 0) for code, exam_type in jobs]


def s(sid, code, exam_type="single_problem"):
    return Task2Sample(sid, "EXA", exam_type, "cpp11", f"{sid}.cpp", code, "organizer log", None, [])


class TestCompile(unittest.TestCase):
    def test_args_follow_exam_notes(self):
        self.assertEqual(compile_args("multi_problem"), ["g++", "-std=c++11", "-fsyntax-only", "student.cpp"])
        self.assertEqual(compile_args("single_problem"), ["g++", "-std=c++11", "student.cpp", "-o", "student"])

    def test_has_compile_error(self):
        self.assertTrue(has_compile_error(LOG_ERR))
        self.assertTrue(has_compile_error(LOG_FATAL))
        self.assertFalse(has_compile_error(LOG_LINK))
        self.assertFalse(has_compile_error(LOG_WARN))
        self.assertFalse(has_compile_error(None))
        self.assertFalse(has_compile_error(""))

    def test_cache_batches_and_reuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeCompiler()
            samples = [s("A", "ok"), s("B", "bad", "multi_problem"), s("C", "ok")]
            logs = CompileCache(fake, tmp).logs(samples)
            self.assertEqual(logs, {"A": "single_problem", "B": "ERR multi_problem", "C": "single_problem"})
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(len(fake.calls[0]), 2)  # A and C share code+type -> compiled once
            fake2 = FakeCompiler()
            self.assertEqual(CompileCache(fake2, tmp).logs(samples), logs)
            self.assertEqual(fake2.calls, [])

    def test_with_compile_logs_replaces_every_sample(self):
        out = with_compile_logs([s("A", "x"), s("B", "y")], {"A": "log A"})
        self.assertEqual([o.compile_log for o in out], ["log A", None])  # organizer log never kept
