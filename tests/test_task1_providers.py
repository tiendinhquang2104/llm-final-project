"""Provider parity and OpenAI billing tests; all responses are local fakes."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src.data.loader import load_split, load_task1
from src.llm.api_client import GeminiBackend
from src.llm.openai_client import CostLimitReached, OpenAIBackend
from src.task1.experiment import run_experiment
from src.task1.pipeline import Task1Pipeline
from src.utils.config import load_config
from tests._data import DATA, ROOT, require_data

require_data()
DS = load_task1(DATA)
SPLIT = load_split(ROOT / "data" / "splits")
ANSWER = {"rationale": "P1 đọc file sai", "problems": [{"pid": "P1", "status": "wrong", "note": "sai"}],
          "rubric": {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2,
                     "complexity": 1, "code_quality": 1}}


class FakeResponses:
    def __init__(self, texts=None):
        self.texts = list(texts or [json.dumps(ANSWER)])
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = self.texts.pop(0)
        return SimpleNamespace(id=f"r{len(self.calls)}", status="completed", output_text=text,
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20,
                                                     input_tokens_details=SimpleNamespace(cached_tokens=10)))


def gemini_response(*_args):
    return {"usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20},
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(ANSWER)}]}}]}


class TestProviders(unittest.TestCase):
    def test_same_prompt_rule_and_cache_isolation(self):
        cfg = load_config(ROOT / "configs" / "task1" / "e3_few_shot_structured.yaml")
        cfg["data"]["sample_ids"] = ["EX01-S106"]
        pool = [DS.by_id()[sid] for sid in SPLIT["train"]]
        sample = DS.by_id()["EX01-S106"]
        fake = FakeResponses()
        openai = OpenAIBackend(client=SimpleNamespace(responses=fake), max_usd=1)
        gemini = GeminiBackend(api_key="test", model="gemma-4-26b-a4b-it", rpm=0)
        with mock.patch.object(gemini, "_post", side_effect=gemini_response):
            p_open = Task1Pipeline(DS, openai, cfg, pool)
            p_gem = Task1Pipeline(DS, gemini, cfg, pool)
            self.assertEqual(p_open.build_request(sample)["messages"], p_gem.build_request(sample)["messages"])
            self.assertTrue(set(p_open.build_request(sample)["demos"]) <= set(SPLIT["train"]))
            _, o_pred = p_open.run([sample])
            _, g_pred = p_gem.run([sample])
        self.assertEqual(o_pred[0]["rubric"], g_pred[0]["rubric"])
        self.assertEqual(o_pred[0]["total_score"], g_pred[0]["total_score"])
        self.assertEqual(o_pred[0]["total_score"], 2)
        self.assertEqual(fake.calls[0]["text"]["format"]["type"], "json_schema")
        self.assertFalse(fake.calls[0]["store"])
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(gemini, "_post", side_effect=gemini_response):
                run_experiment(cfg, DS, SPLIT, gemini, tmp, verbose=False, registry=None)
            fake.texts.append(json.dumps(ANSWER))
            run_experiment(cfg, DS, SPLIT, openai, tmp, verbose=False, registry=None)
            cache = Path(tmp) / "_cache"
            self.assertTrue(list((cache / "gemini").rglob("*.jsonl")))
            self.assertTrue(list((cache / "openai").rglob("*.jsonl")))

    def test_repair_usage_and_cost_limit(self):
        fake = FakeResponses(["bad JSON", json.dumps(ANSWER)])
        backend = OpenAIBackend(client=SimpleNamespace(responses=fake), max_usd=1)
        cfg = load_config(ROOT / "configs" / "task1" / "e2_zero_shot_structured.yaml")
        sample = DS.by_id()["EX01-S106"]
        pipe = Task1Pipeline(DS, backend, cfg)
        _, preds = pipe.run([sample])
        self.assertEqual(len(fake.calls), 2)
        self.assertTrue(preds[0]["parse_ok"])
        self.assertEqual(backend.info()["usage"]["requests"], 2)
        self.assertAlmostEqual(backend.info()["usage"]["cost_usd"], 2 * ((90 * .15 + 10 * .075 + 20 * .60) / 1_000_000))
        self.assertEqual(len(backend.ledger), 2)
        tiny = OpenAIBackend(client=SimpleNamespace(responses=FakeResponses()), max_usd=0.000001)
        with self.assertRaises(CostLimitReached):
            tiny.generate([pipe.build_request(sample)], cfg["generation"])

    def test_invalid_rubric_and_api_error_are_not_scored(self):
        invalid = {**ANSWER, "rubric": {**ANSWER["rubric"], "logic": 8}}
        fake = FakeResponses([json.dumps(invalid), json.dumps(invalid)])
        backend = OpenAIBackend(client=SimpleNamespace(responses=fake))
        cfg = load_config(ROOT / "configs" / "task1" / "e2_zero_shot_structured.yaml")
        sample = DS.by_id()["EX01-S106"]
        _, preds = Task1Pipeline(DS, backend, cfg).run([sample])
        self.assertFalse(preds[0]["parse_ok"])
        self.assertIsNone(preds[0]["total_score"])
        broken = SimpleNamespace(responses=SimpleNamespace(create=mock.Mock(side_effect=RuntimeError("offline"))))
        backend2 = OpenAIBackend(client=broken)
        self.assertEqual(backend2.generate([{"messages": [], "exam": DS.exams[sample.exam_id], "sample": sample}], {}), [[""]])
        self.assertEqual(backend2.info()["usage"]["failed_requests"], 1)
        self.assertNotIn("offline", json.dumps(backend2.ledger))

    def test_invalid_grade_excluded_from_metrics_and_cache(self):
        invalid = {**ANSWER, "rubric": {**ANSWER["rubric"], "logic": 8}}
        fake = FakeResponses([json.dumps(invalid), json.dumps(invalid), json.dumps(ANSWER)])
        backend = OpenAIBackend(client=SimpleNamespace(responses=fake))
        cfg = load_config(ROOT / "configs" / "task1" / "e2_zero_shot_structured.yaml")
        cfg["data"]["sample_ids"] = ["EX01-S106"]
        with tempfile.TemporaryDirectory() as tmp:
            first = run_experiment(cfg, DS, SPLIT, backend, tmp, verbose=False, registry=None)
            self.assertEqual((first["n_requested"], first["n_success"], first["main"]["n"]), (1, 0, 0))
            out = Path(tmp) / cfg["name"]
            self.assertEqual(json.loads((out / "predictions.json").read_text(encoding="utf-8")), [])
            self.assertIsNone(json.loads((out / "metrics.json").read_text(encoding="utf-8"))["main"]["qwk"])
            second = run_experiment(cfg, DS, SPLIT, backend, tmp, verbose=False, registry=None)
            self.assertEqual(second["n_success"], 1)
            self.assertEqual(len(fake.calls), 3)


if __name__ == "__main__":
    unittest.main()
