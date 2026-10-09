import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.llm.openai_client import OpenAIBackend
from src.task2.data import load_task2
from src.task2.labels import LABELS
from src.task2.pipeline import Task2ApiPipeline, parse_labels, vote
from src.task2.prompts import RESPONSE_SCHEMA, select_demos
from tests._task2 import FakeBackend, make_dataset

CFG = {"name": "t", "prompt": {"few_shot_k": 2, "max_code_chars": 4000, "demo_max_code_chars": 500,
                               "use_aux_signals": False},
       "generation": {"temperature": 0.0, "n": 1, "max_new_tokens": 512}, "retry_on_parse_fail": 1}


def ans(*labels):
    return json.dumps({"rationale": "r", "taxonomy_error": list(labels)}, ensure_ascii=False)


class TestParse(unittest.TestCase):
    def test_parse_labels(self):
        self.assertEqual(parse_labels(ans("lỗi logic ", " Lỗi hàm", "Lỗi lạ")), ["Lỗi logic", "Lỗi hàm"])
        self.assertEqual(parse_labels("```json\n" + ans() + "\n```"), [])
        self.assertIsNone(parse_labels("không phải JSON"))
        self.assertIsNone(parse_labels('{"taxonomy_error": "Lỗi logic"}'))

    def test_vote(self):
        p = vote([["Lỗi logic"], ["Lỗi logic", "Lỗi hàm"], []])
        self.assertAlmostEqual(p["Lỗi logic"], 2 / 3)
        self.assertAlmostEqual(p["Lỗi hàm"], 1 / 3)
        self.assertEqual(set(p), set(LABELS))


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ds = load_task2(make_dataset(Path(self.tmp.name), [
            ("A1", "EXA", ["Lỗi logic"]), ("A2", "EXA", []), ("B1", "EXB", ["Lỗi hàm", "Lỗi style"]),
            ("A3", "EXA", ["Lỗi biên dịch"])]))
        self.by = self.ds.by_id()

    def tearDown(self):
        self.tmp.cleanup()

    def test_demos_cover_labels_and_skip_self(self):
        demos = select_demos(self.ds.samples, self.by["A1"], 2)
        self.assertNotIn("A1", [d.sample_id for d in demos])
        self.assertEqual(len(demos), 2)
        self.assertEqual(demos[0].sample_id, "B1")  # covers the most new labels
        self.assertEqual(select_demos(self.ds.samples, self.by["A1"], 0), [])

    def test_prompt_content(self):
        pipe = Task2ApiPipeline(self.ds, None, CFG, [self.by["B1"], self.by["A2"]])
        req = pipe.build_request(self.by["A1"])
        text = "\n".join(m["content"] for m in req["messages"])
        for lab in LABELS:
            self.assertIn(lab, text)
        self.assertNotIn("feedback", text.lower())
        self.assertEqual(req["schema"], RESPONSE_SCHEMA)
        self.assertEqual(req["schema_name"], "task2_labels")

    def test_infer_vote_and_retry(self):
        cfg = {**CFG, "generation": {**CFG["generation"], "n": 2}}
        backend = FakeBackend([ans("Lỗi logic"), ans("Lỗi logic", "Lỗi hàm"),  # A1: n=2
                               "rác", "rác",                                    # A2: both unparseable
                               ans()])                                          # A2 retry
        pipe = Task2ApiPipeline(self.ds, backend, cfg)
        recs = pipe.infer([self.by["A1"], self.by["A2"]])
        p1, p2 = pipe.postprocess(recs[0]), pipe.postprocess(recs[1])
        self.assertEqual(p1["labels"], ["Lỗi logic", "Lỗi hàm"])  # 0.5 votes counts as positive
        self.assertAlmostEqual(p1["probs"]["Lỗi hàm"], 0.5)
        self.assertTrue(p2["parse_ok"])
        self.assertEqual(p2["labels"], [])
        self.assertEqual(len(backend.calls), 3)

    def test_fallback_empty(self):
        pipe = Task2ApiPipeline(self.ds, FakeBackend(["rác", "rác"]), CFG)
        pred = pipe.postprocess(pipe.infer([self.by["A1"]])[0])
        self.assertFalse(pred["parse_ok"])
        self.assertEqual(pred["labels"], [])


class TestOpenAISchema(unittest.TestCase):
    def test_request_schema_used(self):
        calls = []

        def create(**kw):
            calls.append(kw)
            return SimpleNamespace(id="r1", status="completed", output_text=ans("Lỗi logic"),
                                   usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                                                         input_tokens_details=SimpleNamespace(cached_tokens=0)))

        backend = OpenAIBackend(client=SimpleNamespace(responses=SimpleNamespace(create=create)), max_usd=1)
        req = {"messages": [{"role": "user", "content": "x"}], "exam": {}, "schema": RESPONSE_SCHEMA,
               "schema_name": "task2_labels"}
        backend.generate([req], {"n": 1, "max_new_tokens": 64})
        fmt = calls[0]["text"]["format"]
        self.assertEqual(fmt["schema"], RESPONSE_SCHEMA)
        self.assertEqual(fmt["name"], "task2_labels")
