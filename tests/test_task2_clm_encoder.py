import tempfile
import unittest

import numpy as np

from src.task2.clm.encoder import CachedEncoder
from tests._task2 import FakeEncoder


class TestCachedEncoder(unittest.TestCase):
    def test_cache_hits_and_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = FakeEncoder(dim=8)
            enc = CachedEncoder(base, tmp)
            a = enc.embed(["x", "y", "x"])
            self.assertEqual(a.shape, (3, 8))
            np.testing.assert_allclose(a[0], a[2])
            self.assertEqual(enc.n_computed, 2)
            b = CachedEncoder(FakeEncoder(dim=8), tmp).embed(["y", "x"])
            np.testing.assert_allclose(b, a[[1, 0]])
            self.assertEqual(enc.encoder_id, "fake-encoder")
            self.assertEqual(CachedEncoder(base, tmp).embed([]).shape[0], 0)


if __name__ == "__main__":
    unittest.main()
