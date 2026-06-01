import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from retrieval import shadow_search  # noqa: E402


class ShadowSearchTokenTests(unittest.TestCase):
    def test_matches_short_slavic_inflection_variants_by_stem(self):
        self.assertTrue(shadow_search._matches_term("нарвы", "нарву"))
        self.assertTrue(shadow_search._matches_term("эстонии", "эстонию"))

    def test_does_not_match_unrelated_long_prefix_words(self):
        self.assertFalse(shadow_search._matches_term("протесты", "против"))


if __name__ == "__main__":
    unittest.main()
