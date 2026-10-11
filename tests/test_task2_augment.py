import unittest

from src.task2.augment import MUTATORS, augment, source_id
from src.task2.data import Task2Sample
from src.task2.labels import LABELS

CODE = """#include <iostream>
#include <vector>
using namespace std;
int sumDigits(int n) {
    if (n == 0) return 0;
    int s = 0;
    for (int i = 0; i < 10; i++) {
        s += n % 10;
    }
    return s + n;
}
void fill(vector<int> &v) {
    for (int i = 0; i < v.size(); i++) v[i] = i;
}
int main() {
    int n;
    cin >> n;
    if (n > 0) cout << "Tong: " << sumDigits(n) << endl;
    return 0;
}
"""

EXPECT = {
    "drop_return_semicolon": "if (n == 0) return 0\n",
    "alter_output_text": 'cout << "Ket qua: Tong: "',
    "flip_if_comparison": "if (n != 0) return 0;",
    "flip_loop_bound": "for (int i = 0; i <= 10; i++)",
    "off_by_one_size": "v.size() + 1",
    "drop_reference_param": "void fill(vector<int> v)",
    "hardcode_return": "return 1;",
    "strip_indentation": "\nint s = 0;\n",
}


def sample(sid="S1", code=CODE, labels=("Lỗi logic",)):
    return Task2Sample(sample_id=sid, exam_id="EXA", exam_type="single_problem", language="cpp11",
                       code_file=f"{sid}.cpp", code=code, compile_log="log", test_report=[{"x": 1}],
                       labels=list(labels))


class TestMutators(unittest.TestCase):
    def test_nine_mutators_valid_labels(self):
        self.assertEqual(len(MUTATORS), 9)
        self.assertEqual(len({m.name for m in MUTATORS}), 9)
        for m in MUTATORS:
            self.assertIn(m.label, LABELS)
        self.assertNotIn("Lỗi thuật toán", {m.label for m in MUTATORS})

    def test_each_mutator_changes_code(self):
        by_name = {m.name: m for m in MUTATORS}
        for name, needle in EXPECT.items():
            new = by_name[name].apply(CODE)
            self.assertIsNotNone(new, name)
            self.assertNotEqual(new, CODE, name)
            self.assertIn(needle, new, name)
        guarded = by_name["remove_edge_guard"].apply(CODE)
        self.assertNotIn("if (n == 0)", guarded)
        self.assertIn("int s = 0;", guarded)

    def test_edge_guard_with_else_branch_is_not_removed(self):
        code = ("int f(int i) {\n\tif (i == 0){\n\t\treturn 5;\n\t}else if(i == 1){\n\t\treturn 6;\n\t}\n"
                "\treturn 7;\n}\n")
        self.assertIsNone(next(m for m in MUTATORS if m.name == "remove_edge_guard").apply(code))
        ok = "int f(int i) {\n\tif (i == 0) return 5;\n\telse return 6;\n}\n"
        self.assertIsNone(next(m for m in MUTATORS if m.name == "remove_edge_guard").apply(ok))

    def test_drop_reference_keeps_type_name_separator(self):
        by_name = {m.name: m for m in MUTATORS}
        self.assertEqual(by_name["drop_reference_param"].apply("int f(int& n) {}"), "int f(int n) {}")
        self.assertEqual(by_name["drop_reference_param"].apply("int f(string &s) {}"), "int f(string s) {}")

    def test_not_applicable_returns_none(self):
        plain = "int main(){return 0;}\n"
        by_name = {m.name: m for m in MUTATORS}
        for name in ("alter_output_text", "flip_if_comparison", "flip_loop_bound", "off_by_one_size",
                     "drop_reference_param", "remove_edge_guard", "hardcode_return", "strip_indentation"):
            self.assertIsNone(by_name[name].apply(plain), name)


class TestAugment(unittest.TestCase):
    def test_labels_ids_and_aux_cleared(self):
        out = augment([sample()])
        self.assertEqual(len(out), 9)
        loop = next(m for m in out if m.sample_id == "S1~flip_loop_bound")
        self.assertEqual(loop.labels, ["Lỗi logic", "Lỗi vòng lặp"])
        self.assertIsNone(loop.compile_log)
        self.assertIsNone(loop.test_report)
        self.assertEqual(source_id(loop.sample_id), "S1")
        self.assertEqual(source_id("S1"), "S1")

    def test_cap_and_unlabelled_skipped(self):
        samples = [sample("S1"), sample("S2"), Task2Sample("P1", "EXA", "single_problem", "cpp11", "p.cpp", CODE,
                                                           None, None, None)]
        out = augment(samples, max_per_mutator=1)
        self.assertEqual(len(out), 9)
        self.assertTrue(all(source_id(m.sample_id) == "S1" for m in out))


if __name__ == "__main__":
    unittest.main()
