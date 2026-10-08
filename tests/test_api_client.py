"""GeminiBackend tests with a patched HTTP layer (no network)."""
import io
import json
import unittest
import urllib.error
from unittest import mock

from src.llm.api_client import GeminiBackend, QuotaExhausted, default_thinking

ANSWER = {"rationale": "x", "problems": [{"pid": "P1", "status": "correct"}],
          "rubric": {"compilable": 1, "io_format": 1, "logic": 4, "edge_case": 2, "complexity": 1, "code_quality": 1}}
MSGS = [{"role": "system", "content": "sys"}, {"role": "user", "content": "grade"},
        {"role": "assistant", "content": "bad"}, {"role": "user", "content": "retry"}]


def fake_response(payload, label=""):
    return {"modelVersion": "gemini-test-001",
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20, "thoughtsTokenCount": 5},
            "candidates": [{"finishReason": "STOP", "content": {"parts": [
                {"text": "thinking...", "thought": True}, {"text": json.dumps(ANSWER)}]}}]}


def backend(**kw):
    return GeminiBackend(api_key="test-key", rpm=0, **kw)


def http_error(code, body):
    return urllib.error.HTTPError("u", code, "err", {}, io.BytesIO(body.encode()))


class TestGeminiBackend(unittest.TestCase):
    def test_requires_key(self):
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            with self.assertRaises(RuntimeError):
                GeminiBackend(api_key="PASTE_YOUR_GEMINI_API_KEY")

    def test_payload_mapping(self):
        b = backend()
        p = b.build_payload(MSGS, {"temperature": 0.0, "max_new_tokens": 512}, seed=7)
        self.assertEqual(p["systemInstruction"]["parts"][0]["text"], "sys")
        self.assertEqual([c["role"] for c in p["contents"]], ["user", "model", "user"])
        g = p["generationConfig"]
        self.assertEqual((g["temperature"], g["maxOutputTokens"], g["seed"]), (0.0, 512, 7))
        self.assertEqual(g["thinkingConfig"], {"thinkingLevel": "low"})
        self.assertEqual(g["responseMimeType"], "application/json")
        self.assertNotIn("topP", g)
        on = b.build_payload(MSGS, {"enable_thinking": True, "temperature": 0.6, "top_k": 20}, seed=1)["generationConfig"]
        self.assertEqual(on["thinkingConfig"], {"thinkingLevel": "high"})
        self.assertEqual(on["topK"], 20)

    def test_generate_skips_thought_parts_and_counts_usage(self):
        b = backend()
        with mock.patch.object(b, "_post", side_effect=fake_response):
            out = b.generate([{"messages": MSGS}, {"messages": MSGS}], {"n": 2, "temperature": 0.7})
        self.assertEqual([len(o) for o in out], [2, 2])
        self.assertEqual(json.loads(out[0][0]), ANSWER)
        info = b.info()
        self.assertEqual(info["usage"]["requests"], 4)
        self.assertEqual(info["usage"]["thinking_tokens"], 20)
        self.assertEqual(info["served_models"], ["gemini-test-001"])
        self.assertNotIn("test-key", json.dumps(info))

    def test_request_cap(self):
        b = backend(max_requests_per_run=1)
        b._wait_turn()
        with self.assertRaises(QuotaExhausted):
            b._wait_turn()

    def test_daily_quota_stops_immediately(self):
        b = backend()
        err = http_error(429, '{"error": {"details": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}}')
        with mock.patch("urllib.request.urlopen", side_effect=err) as m:
            with self.assertRaises(QuotaExhausted):
                b.generate([{"messages": MSGS}], {})
        self.assertEqual(m.call_count, 1)

    def test_rate_limit_retries_with_server_delay(self):
        b = backend()
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = json.dumps(fake_response(None)).encode()
        err = http_error(429, '{"error": {"details": [{"retryDelay": "0s"}]}}')
        with mock.patch("urllib.request.urlopen", side_effect=[err, ok]), mock.patch("time.sleep") as sleep:
            out = b.generate([{"messages": MSGS}], {})
        self.assertEqual(json.loads(out[0][0]), ANSWER)
        sleep.assert_called_with(1.0)  # retryDelay 0s + 1s margin

    def test_other_failure_returns_empty_text(self):
        b = backend(max_retries=1)
        with mock.patch("urllib.request.urlopen", side_effect=http_error(400, "bad request")):
            out = b.generate([{"messages": MSGS}], {})
        self.assertEqual(out, [[""]])
        self.assertEqual(b.info()["usage"]["failed_requests"], 1)


    def test_default_thinking_by_model_family(self):
        self.assertEqual(default_thinking("gemma-4-26b-a4b-it")[0], {"thinkingLevel": "minimal"})
        self.assertEqual(default_thinking("gemini-2.5-flash")[0], {"thinkingBudget": 0})
        self.assertEqual(default_thinking("gemini-3.8-flash")[0], {"thinkingLevel": "low"})
        self.assertEqual(default_thinking("gemma-3-27b-it"), ({}, {}))
        b = GeminiBackend(api_key="k", model="gemma-3-27b-it", rpm=0)
        self.assertNotIn("thinkingConfig", b.build_payload(MSGS, {}, 1)["generationConfig"])

    def test_unsupported_features_are_dropped_and_resent(self):
        b = backend(model="gemma-4-26b-a4b-it")
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = json.dumps(fake_response(None)).encode()
        errs = [http_error(400, '{"error": {"message": "JSON mode is not enabled for models/gemma"}}'),
                http_error(400, '{"error": {"message": "Developer instruction is not enabled for models/gemma"}}'),
                ok]
        sent = []

        def fake_urlopen(req, timeout=None):
            sent.append(json.loads(req.data))
            r = errs.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            out = b.generate([{"messages": MSGS}], {})
        self.assertEqual(json.loads(out[0][0]), ANSWER)
        self.assertIn("responseMimeType", sent[0]["generationConfig"])
        self.assertNotIn("responseMimeType", sent[1]["generationConfig"])
        self.assertNotIn("systemInstruction", sent[2])
        self.assertTrue(sent[2]["contents"][0]["parts"][0]["text"].startswith("sys"))
        self.assertEqual((b.json_mode, b.no_system), (False, True))


    def test_tpm_throttle_waits_for_window(self):
        b = backend(tpm=10000)
        with mock.patch("time.monotonic", return_value=1000.0), mock.patch("time.sleep") as sleep:
            b._wait_turn(6000)
            b._wait_turn(6000)  # 12000 > 10000 within 60s -> must wait until the first one leaves the window
        sleep.assert_called_once_with(60.0)

    def test_quota_kind(self):
        self.assertEqual(GeminiBackend._quota_kind('"quotaId": "GenerateContentInputTokensPerModelPerMinute-FreeTier"'),
                         "token/phút")
        self.assertEqual(GeminiBackend._quota_kind('"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"'),
                         "request/phút")


if __name__ == "__main__":
    unittest.main()
