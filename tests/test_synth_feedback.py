import random
import unittest

from src.synth.compliance import check
from src.synth.feedback import (
    DEFECT_TEXT,
    FEEDBACK_LEVELS,
    feedback_for,
    feedback_is_compliant,
    multi_feedback,
    praise,
    render,
)


class TestGeneratedFeedbackIsCompliant(unittest.TestCase):
    def test_every_defect_every_level(self):
        for did in DEFECT_TEXT:
            for level in FEEDBACK_LEVELS:
                with self.subTest(defect=did, level=level):
                    text = feedback_for([did], level, rng=random.Random(0))
                    self.assertTrue(feedback_is_compliant(text, level),
                                    f"{did} @ {level}: {check(text, level).violations} :: {text!r}")

    def test_every_defect_in_multi_context(self):
        for did in DEFECT_TEXT:
            for level in ("Level 2 - Chẩn đoán", "Level 3 - Gợi ý sửa", "Level 4 - Lời giải mẫu"):
                text = feedback_for([did], level, problem="P3", rng=random.Random(0))
                self.assertTrue(feedback_is_compliant(text, level), f"{did} @ {level}: {text!r}")

    def test_render_fragments(self):
        for level in ("Level 1 - Gợi ý nhẹ", "Level 2 - Chẩn đoán", "Level 3 - Gợi ý sửa", "Level 4 - Lời giải mẫu"):
            text = render(level, cause="vòng lặp không dừng", fix="cập nhật biến điều khiển",
                          code="cur = cur->next;", rng=random.Random(1))
            self.assertTrue(feedback_is_compliant(text, level), f"{level}: {text!r}")


class TestPraiseAndMulti(unittest.TestCase):
    def test_praise_is_compliant_everywhere(self):
        for level in FEEDBACK_LEVELS:
            self.assertTrue(feedback_is_compliant(praise(level, random.Random(0)), level))

    def test_empty_defects_is_praise(self):
        from src.synth.feedback import _PRAISE
        text = feedback_for([], "Level 1 - Gợi ý nhẹ", rng=random.Random(0))
        self.assertIn(text, _PRAISE)
        self.assertTrue(feedback_is_compliant(text, "Level 1 - Gợi ý nhẹ"))

    def test_multi_level1_hides_specifics(self):
        per = [("P1", [], "ok"), ("P2", [], "ok"), ("P3", ["D04"], "crash"), ("P4", ["D12"], "missing")]
        text = multi_feedback(per, "Level 1 - Gợi ý nhẹ", rng=random.Random(0))
        self.assertNotIn("P3", text)
        self.assertTrue(feedback_is_compliant(text, "Level 1 - Gợi ý nhẹ"))

    def test_multi_level2_lists_problems(self):
        per = [("P1", [], "ok"), ("P2", [], "ok"), ("P3", ["D04"], "crash"), ("P4", ["D12"], "missing")]
        text = multi_feedback(per, "Level 2 - Chẩn đoán", rng=random.Random(0))
        self.assertTrue(text.startswith("P1 đúng; P2 đúng; P3 "))
        self.assertIn("P4 không làm", text)
        self.assertTrue(feedback_is_compliant(text, "Level 2 - Chẩn đoán"))


class TestRephrase(unittest.TestCase):
    def test_rephrase_accepted_only_when_keywords_survive(self):
        good = feedback_for(["D04"], "Level 2 - Chẩn đoán", rng=random.Random(0),
                            rephrase=lambda _: "Vòng lặp không dừng ở câu P3.")
        self.assertIn("Vòng lặp", good)
        fallback = feedback_for(["D04"], "Level 2 - Chẩn đoán", rng=random.Random(0),
                                rephrase=lambda _: "Em xem lại nhé.")
        self.assertNotEqual(fallback, "Em xem lại nhé.")


if __name__ == "__main__":
    unittest.main()
