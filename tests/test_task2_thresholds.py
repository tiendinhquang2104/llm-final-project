import unittest

import numpy as np

from src.task2.thresholds import apply_thresholds, best_threshold, tune_thresholds


class TestThresholds(unittest.TestCase):
    def test_best_threshold(self):
        p = np.array([0.9, 0.6, 0.4, 0.1])
        y = np.array([1, 1, 0, 0])
        self.assertAlmostEqual(best_threshold(p, y), 0.45)
        self.assertEqual(best_threshold(p, np.zeros(4)), 0.5)
        self.assertEqual(best_threshold(p, np.zeros(4), default=0.7), 0.7)

    def test_tune_shape(self):
        P = np.random.default_rng(0).random((8, 10))
        thr = tune_thresholds(P, P > 0.5)
        self.assertEqual(thr.shape, (10,))

    def test_apply_with_floor(self):
        P = np.array([[0.2, 0.9], [0.1, 0.8], [0.3, 0.1], [0.05, 0.2]])
        thr = np.array([0.5, 0.5])
        plain = apply_thresholds(P, thr)
        self.assertEqual(plain[:, 0].sum(), 0)
        floored = apply_thresholds(P, thr, min_rate=0.25)
        self.assertEqual(floored[:, 0].tolist(), [False, False, True, False])  # top-1 of column 0 forced
        self.assertEqual(floored[:, 1].tolist(), plain[:, 1].tolist())       # already >= 1 positive
