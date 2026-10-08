import unittest

from src.task1.scorer import parse_output

GOOD = ('{"rationale": "ok", "problems": [{"pid": "P1", "status": "wrong"}, {"pid": "2", "status": "correct"}], '
        '"rubric": {"compilable": 1, "io_format": 1, "logic": 2, "edge_case": 1, "complexity": 1, "code_quality": 1}}')


class TestParsing(unittest.TestCase):
    def test_plain_json(self):
        p = parse_output(GOOD)
        self.assertTrue(p.ok)
        self.assertEqual(p.rubric["logic"], 2)
        self.assertEqual(p.problems, {"P1": "wrong", "P2": "correct"})

    def test_think_and_fence(self):
        p = parse_output("<think>let me think {not json}</think>\nHere:\n```json\n" + GOOD + "\n```")
        self.assertTrue(p.ok)
        self.assertEqual(p.problems["P1"], "wrong")

    def test_flat_rubric_and_trailing_comma(self):
        p = parse_output('{"compilable":1,"io_format":0,"logic":3,"edge_case":2,"complexity":1,"code_quality":1,}')
        self.assertTrue(p.ok)
        self.assertEqual(p.rubric["io_format"], 0)

    def test_score_objects(self):
        p = parse_output('{"rubric": {"compilable": {"score": 1}, "io_format": {"score": 1}, "logic": {"score": "3"},'
                         ' "edge_case": {"score": 2}, "complexity": {"score": 1}, "code_quality": {"score": 0}}}')
        self.assertTrue(p.ok)
        self.assertEqual(p.rubric["logic"], 3)

    def test_regex_fallback(self):
        p = parse_output("compilable: 1, io_format: 1, logic: 4, edge_case: 2, complexity: 1, code_quality: 1 (cut")
        self.assertTrue(p.ok and p.partial)

    def test_garbage(self):
        self.assertFalse(parse_output("I cannot grade this.").ok)
        self.assertFalse(parse_output("").ok)

    def test_braces_inside_strings(self):
        p = parse_output(GOOD.replace('"ok"', '"code has { and } inside"'))
        self.assertTrue(p.ok)


if __name__ == "__main__":
    unittest.main()
