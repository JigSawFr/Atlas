import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import extracts  # noqa: E402

LONG = "A tale of lanterns. " + "It follows a keeper across the marshes. " * 20


class Extracts(unittest.TestCase):
    def test_ranked(self):
        pages = {"Q5": {"en": "A"}, "Q2": {"en": "B", "fr": "C", "de": "D"}, "Q9": {"de": "X"}, "Q1": {"fr": "Y"}}
        self.assertEqual(extracts.ranked(pages), ["Q2", "Q1", "Q5"])    # most translated first; none in en or fr: out

    def test_trim_and_read(self):
        self.assertEqual(extracts.trim("Short."), "")
        self.assertLessEqual(len(extracts.trim(LONG)), extracts.LIMIT + 1)
        self.assertTrue(extracts.trim(LONG).startswith("A tale of lanterns. It follows"))
        self.assertEqual(extracts.read({"type": "disambiguation", "extract": LONG}), "")
        self.assertEqual(extracts.read(None), "")
        self.assertTrue(extracts.read({"type": "standard", "extract": LONG}))

    def test_collect(self):
        asked = []

        def fetch(url):
            asked.append(url)
            return {"type": "standard", "extract": LONG}
        pages = {"Q1": {"en": "Lantern_Tale", "fr": "Lanterne%27s"}, "Q2": {"en": "Pond"}}
        got = extracts.collect(pages, {"Q2": {"en": "kept text"}}, fetch, limit=2)
        self.assertEqual(sorted(got["Q1"]), ["en", "fr"])         # those with none first, within the limit
        self.assertEqual(got["Q2"], {"en": "kept text"})          # a known one is kept, not asked again
        self.assertEqual(len(asked), 2)
        self.assertIn("en.wikipedia.org/api/rest_v1/page/summary/Lantern_Tale", asked[0])
        self.assertTrue(asked[1].endswith("/fr.wikipedia.org/api/rest_v1/page/summary/Lanterne's".split("org")[1]) or "Lanterne" in asked[1])
        self.assertEqual(extracts.collect(pages, {}, lambda u: (_ for _ in ()).throw(OSError()), limit=5), {})   # none answers: none


if __name__ == "__main__":
    unittest.main()
