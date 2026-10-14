import unittest

from src.synth.mutators import apply, applicable, comment_all

CODE = """#include <iostream>
using namespace std;
bool isArm(int n) {
    int sum = 0;
    int tmp = n;
    while (tmp > 0) {
        int d = tmp % 10;
        sum += d * d * d;
        tmp = tmp / 10;
    }
    return sum == n;
}
int main() {
    int n;
    cin >> n;
    cout << "True";
    return 0;
}
"""

LOOP = """int main() {
    int sum = 0;
    for (int i = 0; i < 5; i++) {
        sum += i;
    }
    cout << sum;
    return 0;
}
"""


class TestMutators(unittest.TestCase):
    def test_comment_all(self):
        out = comment_all(CODE, {})
        self.assertTrue(all(line.startswith("// ") for line in out.splitlines()))

    def test_empty_file(self):
        from src.synth.mutators import empty_file
        self.assertEqual(empty_file(CODE, {}), "")
        out = apply("D00", CODE, {})
        self.assertTrue(all(line.startswith("// ") for line in out.splitlines()))

    def test_missing_semicolon_changes_syntax(self):
        out = apply("D01", CODE, {})
        self.assertIsNotNone(out)
        self.assertNotEqual(out, CODE)
        self.assertLess(out.count(";"), CODE.count(";"))

    def test_undeclared_variable_removes_declaration(self):
        out = apply("D02", CODE, {})
        self.assertIsNotNone(out)
        self.assertNotIn("int sum = 0;", out)

    def test_remove_loop_increment(self):
        out = apply("D04", LOOP, {})
        self.assertIsNotNone(out)
        self.assertNotIn("i++", out)
        self.assertIn("sum += i", out)

    def test_empty_function_body(self):
        out = apply("D05", CODE, {"function": "isArm"})
        self.assertIsNotNone(out)
        self.assertNotIn("sum += d * d * d;", out)

    def test_extra_output_char(self):
        out = apply("D07", CODE, {})
        self.assertIn('cout << " "', out)

    def test_wrong_token(self):
        out = apply("D19", 'cout << "True";', {})
        self.assertIsNotNone(out)
        self.assertIn("TRUE", out)
        self.assertIsNone(apply("D19", "int main(){ return 0; }", {}))

    def test_include_data_file(self):
        out = apply("D03", "int x;", {"data_file": "generals.csv"})
        self.assertTrue(out.startswith('#include "generals.csv"'))

    def test_garbage_style_renames_and_adds_dead_code(self):
        out = apply("D23", CODE, {})
        self.assertIn("TODO", out)
        self.assertNotEqual(out, CODE)

    def test_context_required(self):
        self.assertFalse(applicable("D03", "int x;", {}))
        self.assertTrue(applicable("D03", "int x;", {"data_file": "a.csv"}))

    def test_array_string_bug(self):
        out = apply("D20", "int t = s[i];", {})
        self.assertEqual(out, "int t = s[i + 1];")
        self.assertEqual(apply("D20", "int d = c - '0';", {}), "int d = c + '0';")
        self.assertIsNone(apply("D20", "int x = 0;", {}))

    def test_wrong_function_call(self):
        out = apply("D21", "return isPerfect(n);", {})
        self.assertEqual(out, "return isPerfect(n + 1);")
        self.assertIsNone(apply("D21", "int main() { return 0; }", {}))

    def test_loop_label_mutators_registered(self):
        for defect in ("D06", "D08", "D16a", "D16b", "D17", "D18", "D20", "D21"):
            self.assertIn(defect, __import__("src.synth.mutators", fromlist=["MUTATORS"]).MUTATORS)

    def test_unknown_defect(self):
        with self.assertRaises(KeyError):
            apply("D99", CODE, {})


if __name__ == "__main__":
    unittest.main()
