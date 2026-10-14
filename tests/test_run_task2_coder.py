import unittest
from scripts.run_task2_coder import robust_parse_labels


class TestCoderRunner(unittest.TestCase):
    def test_robust_parse_labels(self):
        # Valid JSON
        text = '{"rationale": "Code sai", "taxonomy_error": ["Lỗi logic", "Lỗi mảng/chuỗi"]}'
        self.assertEqual(robust_parse_labels(text), ["Lỗi logic", "Lỗi mảng/chuỗi"])

        # Markdown wrapped JSON
        text_md = '```json\n{"taxonomy_error": ["Lỗi edge case"]}\n```'
        self.assertEqual(robust_parse_labels(text_md), ["Lỗi edge case"])

        # Empty array
        text_empty = '{"taxonomy_error": []}'
        self.assertEqual(robust_parse_labels(text_empty), [])

        # Fallback text
        text_fallback = "Bài này mắc Lỗi biên dịch và Lỗi vòng lặp."
        res = robust_parse_labels(text_fallback)
        self.assertIn("Lỗi biên dịch", res)
        self.assertIn("Lỗi vòng lặp", res)
