import unittest

from src.synth.taxonomy import DEFECTS, LABEL_SPACE, defect_for_rule, defect_taxonomy, taxonomy_for


class TestDefectRegistry(unittest.TestCase):
    def test_all_labels_are_in_space(self):
        for d in DEFECTS.values():
            for label in (*d.primary, *d.secondary):
                self.assertIn(label, LABEL_SPACE)

    def test_rulebook_defects_present(self):
        expected = {"D00", "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09",
                    "D10", "D11", "D12", "D13", "D14", "D14b", "D14c", "D14d", "D15", "D15s", "D16a", "D16b", "D17", "D18",
                    "D19", "D20", "D21", "D22", "D23"}
        self.assertEqual(set(DEFECTS), expected)


class TestTaxonomy(unittest.TestCase):
    def test_primary_only(self):
        self.assertEqual(defect_taxonomy("D17"), ["Lỗi hard-code"])
        self.assertEqual(defect_taxonomy("D16a"), ["Lỗi edge case"])
        self.assertEqual(defect_taxonomy("D05"), ["Lỗi logic"])

    def test_secondary_only_when_confirmed(self):
        self.assertEqual(defect_taxonomy("D01"), ["Lỗi biên dịch"])
        self.assertEqual(defect_taxonomy("D01", ("Lỗi vòng lặp",)), ["Lỗi biên dịch", "Lỗi vòng lặp"])

    def test_stacked_defects_are_deduped_and_ordered(self):
        out = taxonomy_for(["D22", "D08"], extra=("Lỗi logic",))
        # D08 corrupts the formula/operator -> "Lỗi thuật toán" (rulebook T2.1: sai công thức)
        self.assertEqual(out, ["Lỗi logic", "Lỗi thuật toán", "Lỗi style"])

    def test_matches_real_sample_shape(self):
        self.assertEqual(taxonomy_for(["D03"]), ["Lỗi biên dịch", "Lỗi hard-code"])
        self.assertEqual(taxonomy_for(["D16a"]), ["Lỗi edge case"])

    def test_reverse_lookup(self):
        self.assertEqual(defect_for_rule("S12", "single_problem"), "D23")
        self.assertEqual(defect_for_rule("M2", "multi_problem"), "D04")
        with self.assertRaises(KeyError):
            defect_for_rule("Z9", "single_problem")

    def test_unknown_defect(self):
        with self.assertRaises(KeyError):
            defect_taxonomy("D99")


if __name__ == "__main__":
    unittest.main()
