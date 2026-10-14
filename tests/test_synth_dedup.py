import tempfile
import unittest
from pathlib import Path

from src.synth.dedup import (
    dedupe,
    jaccard,
    max_similarity,
    normalize_tokens,
    public_test_signatures,
    signature,
)

BASE = """#include <iostream>
using namespace std;
int main() {
    int n; cin >> n;
    int s = 0;
    for (int i = 1; i <= n; i++) s += i;
    cout << s;
    return 0;
}
"""

# same code, only comments/whitespace differ
SAME = """#include <iostream>
using namespace std;

int main() { // tinh tong
    int n; cin >> n;

    int s = 0;                       /* accumulator */
    for (int i = 1; i <= n; i++) s += i;
    cout << s;
    return 0;
}
"""

# one token changed (<= becomes <)
NEAR = BASE.replace("i <= n", "i < n")
OTHER = """#include <fstream>
using namespace std;
int main(){ ifstream f("a"); int x; f >> x; cout << x * 2; return 0; }
"""


class TestMinHash(unittest.TestCase):
    def test_ignores_comments_and_whitespace(self):
        self.assertEqual(normalize_tokens(BASE), normalize_tokens(SAME))
        self.assertEqual(jaccard(signature(BASE), signature(SAME)), 1.0)

    def test_near_duplicate_is_high(self):
        self.assertGreater(max_similarity(signature(NEAR), [signature(BASE)]), 0.5)

    def test_unrelated_is_low(self):
        self.assertLess(max_similarity(signature(OTHER), [signature(BASE)]), 0.5)

    def test_empty_has_zero_similarity(self):
        self.assertEqual(max_similarity(signature(""), [signature(BASE)]), 0.0)


class TestDedupe(unittest.TestCase):
    def test_drops_duplicate_keeps_distinct(self):
        sigs = [signature(BASE), signature(SAME), signature(OTHER)]
        res = dedupe(sigs, threshold=0.9)
        self.assertEqual(res.kept, [0, 2])
        self.assertEqual(res.dropped[0][0], 1)

    def test_keep_together_preserves_group(self):
        sigs = [signature(BASE), signature(SAME)]
        res = dedupe(sigs, threshold=0.9, keep_together=[{0, 1}])
        self.assertEqual(res.kept, [0, 1])


class TestPublicCorpus(unittest.TestCase):
    def test_reads_all_cpp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "EX1").mkdir()
            (root / "EX1" / "a.cpp").write_text(BASE, encoding="utf-8")
            (root / "EX1" / "b.cpp").write_text(OTHER, encoding="utf-8")
            sigs = public_test_signatures(root)
            self.assertEqual(len(sigs), 2)
            self.assertEqual(max_similarity(signature(SAME), sigs), 1.0)


if __name__ == "__main__":
    unittest.main()
