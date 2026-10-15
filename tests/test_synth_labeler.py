import unittest

from src.synth.labeler import (
    Label,
    MultiSignals,
    SingleSignals,
    label,
    label_multi,
    label_single,
    round_half_down,
    split_multi_total,
)


class TestRoundHalfDown(unittest.TestCase):
    def test_rulebook_examples(self):
        self.assertEqual(round_half_down(8.75), 9)  # S104
        self.assertEqual(round_half_down(9.5), 9)  # S102
        self.assertEqual(round_half_down(2.5), 2)
        self.assertEqual(round_half_down(3.75), 4)
        self.assertEqual(round_half_down(7.0), 7)


class TestSingle(unittest.TestCase):
    def test_first_match_wins(self):
        cases = [
            ("S0", SingleSignals(has_code=False), (0, 0, 0, 0, 0, 0)),
            ("S1", SingleSignals(compiles=False), (0, 0, 0, 0, 0, 1)),
            ("S2", SingleSignals(terminates=False), (1, 0, 0, 0, 0, 1)),
            ("S3", SingleSignals(token_exact=False, token_normalized=False, normal_pass_ratio=0.0), (1, 0, 0, 0, 1, 1)),
            ("S7", SingleSignals(examples_only_pass=True, normal_pass_ratio=0.2), (1, 1, 1, 0, 0, 1)),
            ("S8", SingleSignals(perf_ok=False, edge_groups_failed=2, normal_pass_ratio=0.5), (1, 1, 2, 0, 0, 1)),
            ("S9", SingleSignals(token_exact=False, token_normalized=False, normal_pass_ratio=0.5), (1, 0, 2, 1, 1, 1)),
            ("S4", SingleSignals(normal_pass_ratio=0.5), (1, 1, 2, 1, 1, 1)),
            ("S10", SingleSignals(edge_groups_failed=2), (1, 1, 4, 0, 1, 1)),
            ("S11", SingleSignals(edge_groups_failed=1), (1, 1, 4, 1, 1, 1)),
            ("S12", SingleSignals(style_very_bad=True), (1, 1, 4, 2, 1, 0)),
            ("S5", SingleSignals(token_exact=False), (1, 0, 4, 2, 1, 1)),
            ("S6", SingleSignals(), (1, 1, 4, 2, 1, 1)),
        ]
        for rule_id, signals, dims in cases:
            with self.subTest(rule_id=rule_id):
                out = label_single(signals)
                self.assertEqual(out.rule_id, rule_id)
                self.assertEqual(tuple(out.rubric.values()), dims)

    def test_total_is_sum_of_dims(self):
        for rule_id, signals, _ in [
            ("S1", SingleSignals(compiles=False), None),
            ("S4", SingleSignals(normal_pass_ratio=0.3), None),
            ("S10", SingleSignals(edge_groups_failed=3), None),
        ]:
            out = label_single(signals)
            self.assertEqual(out.total, sum(out.rubric.values()))

    def test_s4_kind_refines_taxonomy(self):
        self.assertEqual(label_single(SingleSignals(normal_pass_ratio=0.5, taxonomy_hint=("algorithm",))).taxonomy,
                         ["Lỗi thuật toán"])
        self.assertEqual(label_single(SingleSignals(normal_pass_ratio=0.5)).taxonomy, ["Lỗi logic"])


class TestMulti(unittest.TestCase):
    def test_rulebook_worked_examples(self):
        cases = [
            ("M0", MultiSignals(has_code=False), 0),
            ("M1", MultiSignals(compiles=False), 0),
            ("M2", MultiSignals(infinite_loop_any=True), 2),
            ("M3", MultiSignals(p1_ok=False), 1),
        ]
        for rule_id, signals, total in cases:
            with self.subTest(rule_id=rule_id):
                self.assertEqual(label_multi(signals).total, total)

    def test_m4_documented_samples(self):
        s115 = label_multi(MultiSignals(problem_states=("ok", "ok", "ok", "ok")))
        self.assertEqual((s115.rule_id, s115.total, tuple(s115.rubric.values())), ("M4", 10, (1, 1, 4, 2, 1, 1)))

        s104 = label_multi(MultiSignals(problem_states=("ok", "ok", "partial", "ok")))
        self.assertEqual((s104.total, tuple(s104.rubric.values())), (9, (1, 1, 3, 2, 1, 1)))

        s102 = label_multi(MultiSignals(problem_states=("ok", "ok", "ok", "edge")))
        self.assertEqual((s102.total, tuple(s102.rubric.values())), (9, (1, 1, 4, 1, 1, 1)))

        s101 = label_multi(MultiSignals(problem_states=("ok", "ok", "missing", "edge")))
        self.assertEqual((s101.total, tuple(s101.rubric.values())), (7, (1, 1, 2, 1, 1, 1)))

    def test_m4_types_have_edge_taxonomy(self):
        self.assertIn("Lỗi edge case", label_multi(MultiSignals(problem_states=("ok", "ok", "ok", "edge"))).taxonomy)
        self.assertIn("Lỗi logic", label_multi(MultiSignals(problem_states=("ok", "ok", "partial", "ok"))).taxonomy)

    def test_split_keeps_g1(self):
        for total in range(0, 11):
            rubric = split_multi_total(total, ("ok", "ok", "missing", "edge"))
            self.assertEqual(sum(rubric), total)


class TestDispatch(unittest.TestCase):
    def test_label_dispatches_and_type_checks(self):
        self.assertEqual(label("single_problem", SingleSignals()).rule_id, "S6")
        self.assertEqual(label("multi_problem", MultiSignals()).rule_id, "M4")
        with self.assertRaises(TypeError):
            label("single_problem", MultiSignals())
        with self.assertRaises(ValueError):
            label("unknown", SingleSignals())

    def test_label_rejects_inconsistent_rubric(self):
        with self.assertRaises(ValueError):
            Label("x", {"compilable": 1}, 1, [])


if __name__ == "__main__":
    unittest.main()
