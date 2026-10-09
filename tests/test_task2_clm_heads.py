import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from src.task2.clm.heads import Head, LinearProbe, NoulModel, TrainConfig, load_heads, predict_noul, train_noul
from tests._task2 import make_fake_heads


class TestLoad(unittest.TestCase):
    def test_pt_and_safetensors_dir_match(self):
        from safetensors.torch import save_file

        with tempfile.TemporaryDirectory() as tmp:
            pt = make_fake_heads(Path(tmp) / "h.pt")
            a = load_heads(pt)
            self.assertEqual(a["cfg"]["hidden"], 16)
            d = Path(tmp) / "heads"
            d.mkdir()
            ck = torch.load(pt, weights_only=True)
            flat = {f"{n}.{k}": v for n in ("state_head", "action_head") for k, v in ck[n].items()}
            flat["logit_scale"] = ck["logit_scale"].reshape(1)
            save_file(flat, str(d / "CLM_v0.1-8B.safetensors"))
            (d / "config.json").write_text(json.dumps({"cfg": ck["cfg"], "projection_dim": 4, "hidden_size": 16}))
            b = load_heads(d)
            x = torch.randn(3, 16)
            torch.testing.assert_close(a["state"](x), b["state"](x))
            self.assertAlmostEqual(a["logit_scale"], b["logit_scale"], places=5)


class TestTrain(unittest.TestCase):
    def test_loss_decreases_and_predict_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = NoulModel.from_checkpoint(make_fake_heads(Path(tmp) / "h.pt"))
            rng = np.random.default_rng(0)
            S = rng.standard_normal((40, 10, 16)).astype(np.float32)
            C = rng.standard_normal((10, 2, 16)).astype(np.float32)
            Y = (S[:, :, 0] > 0).astype(np.float32)
            hist = train_noul(model, S, C, Y, TrainConfig(epochs=30, lr=1e-2, batch_size=64))
            self.assertLess(hist["loss"][-1], hist["loss"][0])
            P = predict_noul(model, S, C)
            self.assertEqual(P.shape, (40, 10))
            self.assertTrue(((P >= 0) & (P <= 1)).all())

    def test_eval_fn_keeps_best(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = NoulModel.from_checkpoint(make_fake_heads(Path(tmp) / "h.pt"))
            S = np.random.default_rng(1).standard_normal((4, 10, 16)).astype(np.float32)
            C = np.random.default_rng(2).standard_normal((10, 2, 16)).astype(np.float32)
            scores = iter([0.1, 0.9, 0.2])
            hist = train_noul(model, S, C, np.zeros((4, 10), np.float32), TrainConfig(epochs=3, lr=1e-2),
                              eval_fn=lambda m: next(scores))
            self.assertEqual(hist["best_epoch"], 1)


class TestProbe(unittest.TestCase):
    def test_fit_predict(self):
        rng = np.random.default_rng(0)
        X = rng.standard_normal((60, 16)).astype(np.float32)
        Y = np.zeros((60, 10), np.float32)
        Y[:, 0] = X[:, 0] > 0
        P = LinearProbe().fit(X, Y).predict_proba(X)
        self.assertEqual(P.shape, (60, 10))
        self.assertGreater(((P[:, 0] >= 0.5) == (Y[:, 0] == 1)).mean(), 0.8)
        self.assertTrue((P[:, 1] == 0).all())  # no positive example -> constant 0


if __name__ == "__main__":
    unittest.main()
