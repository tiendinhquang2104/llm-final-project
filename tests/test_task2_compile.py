import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.task2 import compile as comp
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


LOG_HEADER = ("In file included from /tmp/tmpx/student.cpp:1:\n"
              "/usr/local/include/c++/13.3.0/bits/stl_algo.h:12:5: error: no matching function\n")


class TestHardening(unittest.TestCase):
    def test_header_errors_count_linker_do_not(self):
        self.assertTrue(comp.has_compile_error(LOG_HEADER))
        self.assertTrue(comp.has_compile_error("/usr/include/x.h:3:1: fatal error: y.h: No such file\n"))
        self.assertFalse(comp.has_compile_error(LOG_LINK))
        self.assertFalse(comp.has_compile_error("/usr/include/x.h:3:1: warning: foo\n"))

    def test_native_refused_on_darwin(self):
        with mock.patch.object(comp.platform, "system", return_value="Darwin"), \
                mock.patch.object(comp.shutil, "which", return_value=None), \
                mock.patch.object(comp.subprocess, "run", side_effect=OSError("no docker")), \
                mock.patch.object(comp, "NativeCompiler") as native:
            self.assertIsNone(comp.make_compiler("native"))
            self.assertIsNone(comp.make_compiler("auto"))
            native.assert_not_called()

    def test_native_env_and_decoding(self):
        seen = {}

        def fake_run(args, **kw):
            if "--version" in args:
                return mock.Mock(stdout="g++ 13", stderr="")
            seen.update(kw)
            return mock.Mock(stdout=b"", stderr=b"x\xff", returncode=1)
        with mock.patch.object(comp.subprocess, "run", side_effect=fake_run):
            c = comp.NativeCompiler()
            out = c.run([("int main(){}", "single_problem")])
        self.assertEqual(seen["env"]["LC_ALL"], "C")
        self.assertNotIn("text", seen)
        self.assertEqual(out[0][1], 1)
        self.assertIn("x", out[0][0])

    def test_cache_atomic_and_skips_timeouts(self):
        class TC:
            compiler_id = "t"

            def run(self, jobs):
                return [("compile timeout", 124) if "slow" in c else ("ok", 0) for c, _ in jobs]
        with tempfile.TemporaryDirectory() as tmp:
            cache = CompileCache(TC(), tmp)
            logs = cache.logs([s("A", "slow"), s("B", "fine")])
            self.assertEqual(logs, {"A": "compile timeout", "B": "ok"})
            files = list(Path(tmp).iterdir())
            self.assertEqual(len(files), 1)  # only the non-timeout result is cached, no stray temp files
            self.assertEqual(json.loads(files[0].read_text())["returncode"], 0)
            self.assertEqual(cache.logs([s("A", "slow")]), {"A": "compile timeout"})


class TestAttach(unittest.TestCase):
    def test_attach_compiles_all_lists_in_one_batch_and_clears_organizer_signals(self):
        fake = FakeCompiler()
        a, b = s("A", "ok"), s("B", "bad")
        a.test_report = [{"x": 1}]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(comp, "make_compiler", return_value=fake):
            (la, lb), cid = comp.attach_compile_logs({"cache_dir": "c", "workdir": "w"}, [[a], [b]], root=tmp)
        self.assertEqual(cid, "fake:g++ 13.3.0")
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual((la[0].compile_log, lb[0].compile_log), ("single_problem", "ERR single_problem"))
        self.assertIsNone(la[0].test_report)

    def test_disabled_or_missing_compiler_gives_none_logs(self):
        with mock.patch.object(comp, "make_compiler") as mk:
            (out,), cid = comp.attach_compile_logs({}, [[s("A", "ok")]], enabled=False)
            self.assertEqual((out[0].compile_log, cid), (None, None))
            (out,), cid = comp.attach_compile_logs({"enabled": False}, [[s("A", "ok")]])
            self.assertEqual((out[0].compile_log, cid), (None, None))
            mk.assert_not_called()
        with mock.patch.object(comp, "make_compiler", return_value=None):
            (out,), cid = comp.attach_compile_logs({}, [[s("A", "ok")]])
            self.assertEqual((out[0].compile_log, cid), (None, None))
