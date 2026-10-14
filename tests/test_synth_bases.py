import unittest

from src.synth.bases import (
    PERSONAS,
    LLMGenerator,
    persona_prompt,
    reference_generator,
    repair,
    repair_prompt,
    strip_code_fence,
)
from src.synth.problems import Problem

PROBLEM = Problem(
    exam_id="SYN-X",
    exam_type="single_problem",
    statement="Đọc n, in True nếu n là số hoàn hảo.",
    reference="int main(){ return 0; }",
)


class TestReference(unittest.TestCase):
    def test_returns_reference(self):
        self.assertEqual(reference_generator(PROBLEM, 3), [PROBLEM.reference])


class TestPrompts(unittest.TestCase):
    def test_persona_prompt_has_statement_and_persona(self):
        text = persona_prompt(PROBLEM, "exam_style", style_profile_text="Sinh viên hay dùng bits/stdc++.h.")
        self.assertIn("số hoàn hảo", text)
        self.assertIn("thi cử", text)
        self.assertIn("```cpp", text)
        self.assertNotIn(PROBLEM.reference, text)

    def test_repair_prompt_has_code(self):
        text = repair_prompt("int x;", PROBLEM)
        self.assertIn("int x;", text)
        self.assertIn("NHỎ NHẤT", text)

    def test_strip_code_fence(self):
        self.assertEqual(strip_code_fence("```cpp\nint main(){}\n```"), "int main(){}")
        self.assertEqual(strip_code_fence("int main(){}"), "int main(){}")


class TestLLMGenerator(unittest.TestCase):
    def test_generates_k_with_personas(self):
        calls = []

        def complete(prompt):
            calls.append(prompt)
            return "```cpp\nint main(){ return 0; }\n```"

        gen = LLMGenerator(complete, personas=["exam_style", "all_in_main"])
        out = gen(PROBLEM, 2)
        self.assertEqual(len(out), 2)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all("main" in c for c in out))

    def test_validate_filters_and_stops_at_k(self):
        def complete(prompt):
            return "```cpp\nint main(){ return 0; }\n```"

        gen = LLMGenerator(complete, personas=list(PERSONAS), validate=lambda code: False)
        self.assertEqual(gen(PROBLEM, 3), [])

    def test_repair_strips_fence(self):
        self.assertEqual(repair("int x;", PROBLEM, lambda _: "```cpp\nint main(){}\n```"), "int main(){}")


if __name__ == "__main__":
    unittest.main()
