import json
import tempfile
import unittest
from pathlib import Path

from src.task2.augment_api import (SCHEMA, build_messages, generate_mutants, load_mutants, parse_code,
                                    plan_jobs)
from src.task2.data import load_task2
from tests._task2 import FakeBackend, make_dataset


class TestAugmentApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ds = load_task2(make_dataset(Path(self.tmp.name) / "g", [
            ("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", []), ("B1", "EXB", ["Lỗi hàm"])]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_skips_samples_that_already_have_label(self):
        jobs = plan_jobs(self.ds.samples, ["Lỗi logic", "Lỗi hàm"], per_label=5)
        pairs = [(s.sample_id, lab) for s, lab in jobs]
        self.assertNotIn(("A1", "Lỗi logic"), pairs)
        self.assertNotIn(("B1", "Lỗi hàm"), pairs)
        self.assertIn(("A2", "Lỗi logic"), pairs)
        self.assertEqual(len(plan_jobs(self.ds.samples, ["Lỗi logic"], per_label=1)), 1)

    def test_messages_and_parse(self):
        s = self.ds.by_id()["A2"]
        text = "\n".join(m["content"] for m in build_messages(self.ds.exams["EXA"], s, "Lỗi edge case"))
        self.assertIn("Lỗi edge case", text)
        self.assertIn(s.code.strip()[:20], text)
        self.assertNotIn("feedback", text.lower())
        self.assertEqual(parse_code('{"code": "int x;"}', "int y;"), "int x;")
        self.assertIsNone(parse_code('{"code": "int y;"}', "int y;"))  # unchanged
        self.assertIsNone(parse_code("rác", "int y;"))
        self.assertEqual(SCHEMA["required"], ["code"])

    def test_generate_and_load_roundtrip(self):
        jobs = plan_jobs(self.ds.samples, ["Lỗi edge case"], per_label=2)
        backend = FakeBackend([json.dumps({"code": "int changed1;"}), "rác"])
        recs = generate_mutants(self.ds, jobs, backend, {"n": 1})
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["source_id"], jobs[0][0].sample_id)
        self.assertIn("Lỗi edge case", recs[0]["labels"])
        self.assertTrue(recs[0]["sample_id"].startswith(jobs[0][0].sample_id + "~api-"))
        self.assertEqual(backend.calls[0]["schema_name"], "task2_mutant")
        path = Path(self.tmp.name) / "m.json"
        path.write_text(json.dumps(recs, ensure_ascii=False), encoding="utf-8")
        loaded = load_mutants(path)
        self.assertEqual(loaded[0].code, "int changed1;")
        self.assertTrue(loaded[0].has_gold)


if __name__ == "__main__":
    unittest.main()
