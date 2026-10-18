import sys
import types
import unittest
from types import SimpleNamespace
from unittest import mock

import torch  # noqa: F401 - loaded before patch.dict(sys.modules) so restoring it never evicts torch

from src.llm.local_backend import OOM_MARK, VLLMChatBackend, make_local_backend


class FakeTok:
    def apply_chat_template(self, messages, add_generation_prompt=True, tokenize=True):
        return list(range(len(messages[-1]["content"])))  # one token per character


class FakeLLM:
    calls = []

    def __init__(self, **kw):
        self.kw = kw

    def get_tokenizer(self):
        return FakeTok()

    def generate(self, prompts, params, use_tqdm=False):
        FakeLLM.calls.append((prompts, params))
        return [SimpleNamespace(outputs=[SimpleNamespace(text=f"ans{len(p['prompt_token_ids'])}-{k}",
                                                         token_ids=[0] * 3) for k in range(sp.n)])
                for p, sp in zip(prompts, params)]


def fake_vllm():
    mod = types.ModuleType("vllm")
    mod.__version__ = "0.0-test"
    mod.LLM = FakeLLM
    mod.SamplingParams = lambda **kw: SimpleNamespace(**kw)
    return mod


def req(sid, content):
    return {"sample": SimpleNamespace(sample_id=sid), "messages": [{"role": "user", "content": content}]}


class TestVLLMBackend(unittest.TestCase):
    def setUp(self):
        FakeLLM.calls = []
        patcher = mock.patch.dict(sys.modules, {"vllm": fake_vllm()})
        patcher.start()
        self.addCleanup(patcher.stop)
        with mock.patch("src.llm.local_backend._hub_revision", return_value="abc"):
            self.be = make_local_backend("vllm", {"vllm": {"model": "m", "max_model_len": 20,
                                                           "tensor_parallel_size": 2}})

    def test_one_batched_call_in_request_order(self):
        out = self.be.generate([req("A", "xxxx"), req("B", "yy")], {"temperature": 0.0, "max_new_tokens": 8})
        self.assertEqual(out, [["ans4-0"], ["ans2-0"]])
        self.assertEqual(len(FakeLLM.calls), 1)                       # all samples in one generate call
        params = FakeLLM.calls[0][1]
        self.assertEqual([p.max_tokens for p in params], [8, 8])
        self.assertFalse(hasattr(params[0], "seed"))                  # greedy: no sampling seed
        self.assertEqual(self.be.usage, {"requests": 2, "prompt_tokens": 6, "output_tokens": 6})
        self.assertEqual(self.be.checkpoint_every, 64)
        self.assertEqual(self.be.revision, "abc")

    def test_sampling_n_and_per_sample_seed(self):
        gen = {"temperature": 0.7, "top_p": 0.95, "n": 3, "max_new_tokens": 8}
        out = self.be.generate([req("A", "xx")], gen)
        self.assertEqual(out, [["ans2-0", "ans2-1", "ans2-2"]])
        p = FakeLLM.calls[0][1][0]
        self.assertEqual((p.n, p.top_p), (3, 0.95))
        self.be.generate([req("A", "xx")], gen)
        self.assertEqual(FakeLLM.calls[1][1][0].seed, p.seed)          # stable across calls / cache chunks

    def test_long_prompt_is_capped_or_skipped(self):
        out = self.be.generate([req("A", "x" * 15), req("B", "x" * 25)], {"temperature": 0.0, "max_new_tokens": 8})
        self.assertEqual(FakeLLM.calls[0][1][0].max_tokens, 5)         # 20 - 15 left for the answer
        self.assertEqual(len(FakeLLM.calls[0][0]), 1)                 # B never reaches vLLM
        self.assertTrue(out[1][0].startswith(OOM_MARK))               # unparseable -> retried / rerun later

    def test_greedy_n_gt_1_rejected(self):
        with self.assertRaises(ValueError):
            self.be.generate([req("A", "x")], {"temperature": 0.0, "n": 2})

    def test_is_a_vllm_backend(self):
        self.assertIsInstance(self.be, VLLMChatBackend)
        self.assertEqual(self.be.llm.kw["tensor_parallel_size"], 2)


if __name__ == "__main__":
    unittest.main()
