import unittest

from src.data.loader import DIMENSIONS
from src.evaluation.metrics import mean_absolute_error, quadratic_weighted_kappa
from src.task1.evaluator import evaluate


def item(total, **dims):
    r = {d: 0 for d in DIMENSIONS}
    r.update(dims)
    return {"rubric": r, "total_score": total}


class TestQWK(unittest.TestCase):
    def test_perfect(self):
        self.assertAlmostEqual(quadratic_weighted_kappa([0, 5, 10, 7], [0, 5, 10, 7]), 1.0)

    def test_known_value(self):
        # Same value as sklearn.metrics.cohen_kappa_score(weights="quadratic") for these ratings.
        self.assertAlmostEqual(quadratic_weighted_kappa([1, 2, 3, 4, 5], [1, 2, 3, 5, 4]), 0.9, places=6)

    def test_reversed_is_negative(self):
        self.assertLess(quadratic_weighted_kappa([0, 2, 8, 10], [10, 8, 2, 0]), 0)

    def test_constant_raters(self):
        self.assertEqual(quadratic_weighted_kappa([3, 3], [3, 3]), 1.0)
        self.assertEqual(quadratic_weighted_kappa([3, 3], [4, 4]), 0.0)

    def test_clips_out_of_range(self):
        self.assertAlmostEqual(quadratic_weighted_kappa([0, 10], [-5, 15]), 1.0)


class TestEvaluate(unittest.TestCase):
    def test_mae(self):
        self.assertAlmostEqual(mean_absolute_error([1, 2, 3], [2, 2, 5]), 1.0)

    def test_evaluate_exact_and_missing(self):
        gold = {"a": item(2, compilable=1, io_format=1),
                "b": item(10, compilable=1, io_format=1, logic=4, edge_case=2, complexity=1, code_quality=1)}
        pred = {"a": item(2, compilable=1, io_format=1)}
        m = evaluate(gold, pred, {"a": "EX01", "b": "EX02"})
        self.assertEqual(m["n_missing"], 1)
        self.assertAlmostEqual(m["mae"], 5.0)
        self.assertAlmostEqual(m["exact_match"]["compilable"], 0.5)
        self.assertAlmostEqual(m["exact_total"], 0.5)
        self.assertEqual(set(m["by_group"]), {"EX01", "EX02"})


if __name__ == "__main__":
    unittest.main()
