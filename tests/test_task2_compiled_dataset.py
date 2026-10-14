import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.task2.compile import attach_compile_logs
from src.task2.compiled_dataset import build_compiled_dataset
from src.task2.data import load_task2
from tests._task2 import make_dataset

SAMPLES = [("s1", "EXA", None), ("s2", "EXB", None)]


class FakeCompiler:
    compiler_id = "fake:g++"

    def __init__(self):
        self.calls = []

    def run(self, jobs):
        self.calls.append(list(jobs))
        return [("E log" if "bad" in c else "", 0) for c, _ in jobs]


def _src(tmp: Path) -> Path:
    root = make_dataset(tmp / "public_test_release", SAMPLES)
    (root / "label_space.json").write_bytes(b'{"a": 1}\r\n')
    (root / "data_files").mkdir()
    (root / "data_files" / "x.csv").write_bytes(b"1,2\r\n")
    rows = json.loads((root / "task2_error_taxonomy.json").read_text(encoding="utf-8"))["samples"]
    for name in ("task1_grading.json", "task3_feedback.json"):
        (root / name).write_bytes(json.dumps({"task": name, "samples": rows}, indent=2, ensure_ascii=False)
                                  .replace("\n", "\r\n").encode("utf-8"))
    return root


class TestBuild(unittest.TestCase):
    def test_only_compile_log_changes(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            src = _src(t)
            out = t / "out"
            build_compiled_dataset(src, out, {"s1": "", "s2": "x.cpp:1:1: error: boom\n"})
            dst = out / "public_test_release"
            for name in ("exams.json", "label_space.json", "data_files/x.csv", "submissions/EXA/s1.cpp"):
                self.assertEqual((src / name).read_bytes(), (dst / name).read_bytes(), name)
            for name in ("task1_grading.json", "task2_error_taxonomy.json", "task3_feedback.json"):
                a = json.loads((src / name).read_text(encoding="utf-8"))
                b = json.loads((dst / name).read_text(encoding="utf-8"))
                self.assertEqual(b["samples"][0]["input"]["compile_log"], "")
                self.assertEqual(b["samples"][1]["input"]["compile_log"], "x.cpp:1:1: error: boom\n")
                for sa, sb in zip(a["samples"], b["samples"]):
                    sb["input"]["compile_log"] = sa["input"]["compile_log"]
                self.assertEqual(a, b)
            raw = (dst / "task1_grading.json").read_bytes()
            self.assertIn(b"\r\n", raw)
            names = zipfile.ZipFile(out / "public_test_release.zip").namelist()
            self.assertTrue(all(n.startswith("public_test_release/") for n in names))
            self.assertIn("public_test_release/exams.json", names)
            ds = load_task2(dst, keep_empty_compile_log=True)
            self.assertEqual([s.compile_log for s in ds.samples], ["", "x.cpp:1:1: error: boom\n"])

    def test_no_zip(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            build_compiled_dataset(_src(t), t / "out", {"s1": "", "s2": ""}, make_zip=False)
            self.assertFalse((t / "out" / "public_test_release.zip").exists())

    def test_missing_log_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            with self.assertRaises(KeyError):
                build_compiled_dataset(_src(t), t / "out", {"s1": ""})
            self.assertFalse((t / "out" / "public_test_release").exists())


class TestKeepEmpty(unittest.TestCase):
    def test_default_maps_empty_to_none(self):
        with tempfile.TemporaryDirectory() as t:
            root = make_dataset(Path(t) / "d", SAMPLES)
            self.assertIsNone(load_task2(root).samples[0].compile_log)
            self.assertEqual(load_task2(root, keep_empty_compile_log=True).samples[0].compile_log, "")


class TestDatasetSource(unittest.TestCase):
    def test_only_none_logs_are_compiled(self):
        with tempfile.TemporaryDirectory() as t:
            root = make_dataset(Path(t) / "d", SAMPLES)
            a, b = load_task2(root, keep_empty_compile_log=True).samples
            b.compile_log = "kept"
            from dataclasses import replace
            m = replace(a, sample_id="m1", code="bad code", compile_log=None)
            comp = FakeCompiler()
            from unittest import mock
            with mock.patch("src.task2.compile.make_compiler", return_value=comp):
                (la, lm), cid = attach_compile_logs({"cache_dir": str(Path(t) / "c")}, [[a, b], [m]],
                                                    source="dataset", root=Path(t))
            self.assertEqual([s.compile_log for s in la], ["", "kept"])
            self.assertEqual(lm[0].compile_log, "E log")
            self.assertEqual(len(comp.calls), 1)
            self.assertEqual([c for c, _ in comp.calls[0]], ["bad code"])
            self.assertEqual(cid, "fake:g++")

    def test_no_compiler_gives_none_for_missing(self):
        with tempfile.TemporaryDirectory() as t:
            root = make_dataset(Path(t) / "d", SAMPLES)
            a, b = load_task2(root, keep_empty_compile_log=True).samples
            from dataclasses import replace
            m = replace(a, sample_id="m1", compile_log=None)
            from unittest import mock
            with mock.patch("src.task2.compile.make_compiler", return_value=None):
                (la, lm), cid = attach_compile_logs({}, [[a], [m]], source="dataset", root=Path(t))
            self.assertEqual(la[0].compile_log, "")
            self.assertIsNone(lm[0].compile_log)
            self.assertEqual(cid, "dataset")

    def test_all_present_needs_no_compiler(self):
        with tempfile.TemporaryDirectory() as t:
            root = make_dataset(Path(t) / "d", SAMPLES)
            a, _ = load_task2(root, keep_empty_compile_log=True).samples
            from unittest import mock
            with mock.patch("src.task2.compile.make_compiler") as mk:
                (la,), cid = attach_compile_logs({}, [[a]], source="dataset", root=Path(t))
            mk.assert_not_called()
            self.assertEqual(la[0].compile_log, "")
            self.assertEqual(cid, "dataset")

    def test_no_compile_flag_forces_none(self):
        with tempfile.TemporaryDirectory() as t:
            root = make_dataset(Path(t) / "d", SAMPLES)
            a, _ = load_task2(root, keep_empty_compile_log=True).samples
            (la,), cid = attach_compile_logs({}, [[a]], enabled=False, source="dataset", root=Path(t))
            self.assertIsNone(la[0].compile_log)
            self.assertIsNone(cid)


if __name__ == "__main__":
    unittest.main()
