import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import wdfacts  # noqa: E402


def src_of(files):
    return lambda name: {"rows": files[name]} if name in files else {}


class Queries(unittest.TestCase):
    def test_a_query_for_each_group(self):
        names = [n for n, _ in wdfacts.queries()]
        self.assertEqual(names, list(wdfacts.GROUPS) + ["facts-wiki"])
        self.assertEqual(len(names), 7)

    def test_labels_only_where_the_value_is_an_item(self):
        with_labels = wdfacts.query(("P908",), True)
        self.assertIn("rdfs:label", with_labels)
        self.assertIn("SELECT ?qid ?p ?label", with_labels)
        plain = wdfacts.query(("P856",), False)
        self.assertNotIn("rdfs:label", plain)
        self.assertIn("SELECT ?qid ?p ?v", plain)
        self.assertIn("wdt:P400", plain)               # a game with a platform


class Ratings(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(wdfacts.age("P908", "PEGI 12"), ["PEGI", "12"])
        self.assertEqual(wdfacts.age("P914", "USK 6"), ["USK", "6"])
        self.assertEqual(wdfacts.age("P852", "Everyone 10+"), ["ESRB", "E10+"])
        self.assertEqual(wdfacts.age("P852", "Mature 17+"), ["ESRB", "M"])
        self.assertEqual(wdfacts.age("P853", "B (Ages 12 and up)"), ["CERO", "B"])
        self.assertEqual(wdfacts.age("P853", "Z (Ages 18 and up only)"), ["CERO", "Z"])

    def test_what_is_none(self):
        for prop, label in (("P908", "PEGI 99"), ("P908", "Q14915515"), ("P852", "Pending"), ("P853", "Ages 12"), ("P1", "PEGI 12"), ("P908", None)):
            self.assertIsNone(wdfacts.age(prop, label), (prop, label))


class Facts(unittest.TestCase):
    FILES = {
        "wikidata/facts-website.json": [{"qid": "Q1", "v": "https://example.org/a"}, {"qid": "Q1", "v": "https://example.org/b"},
                                        {"qid": "Q2", "v": "javascript:alert(1)"}, {"qid": "Q3", "v": "http://example.org/with space"},
                                        {"qid": "not a qid", "v": "https://example.org/x"}],
        "wikidata/facts-pcgw.json": [{"qid": "Q1", "v": "Amber_Lantern"}, {"qid": "Q2", "v": "bad/id"}],
        "wikidata/facts-wiki.json": [{"qid": "Q1", "p": "wiki", "lang": "fr", "v": "Lanterne_d%27ambre"},
                                     {"qid": "Q1", "p": "wiki", "lang": "en", "v": "Amber_Lantern"},
                                     {"qid": "Q1", "p": "wiki", "lang": "xx", "v": "Other"},
                                     {"qid": "Q1", "p": "wiki", "lang": "de", "v": "with space"}],
        "wikidata/facts-youtube.json": [{"qid": "Q1", "v": f"abcdefghij{i}"} for i in range(5)] + [{"qid": "Q1", "v": "short"}],
        "wikidata/facts-age.json": [{"qid": "Q1", "p": "P908", "label": "PEGI 16"}, {"qid": "Q1", "p": "P908", "label": "PEGI 12"},
                                    {"qid": "Q1", "p": "P852", "label": "Teen"}, {"qid": "Q1", "p": "P853", "label": "C (Ages 15 and up)"},
                                    {"qid": "Q1", "p": "P914", "label": "USK 12"}, {"qid": "Q2", "p": "P908", "label": "PEGI 99"}],
        "wikidata/facts-people.json": [{"qid": "Q1", "p": "P57", "label": "Ann"}, {"qid": "Q1", "p": "P57", "label": "Bo"},
                                       {"qid": "Q1", "p": "P57", "label": "Cy"}, {"qid": "Q1", "p": "P57", "label": "Di"},
                                       {"qid": "Q1", "p": "P86", "label": "Eve"}, {"qid": "Q1", "p": "P58", "label": "Q99999"},
                                       {"qid": "Q1", "p": "P1", "label": "Nobody"}],
        "wikidata/facts-engine.json": [{"qid": "Q1", "p": "P408", "label": "Unity"}, {"qid": "Q1", "p": "P408", "label": "Unity"},
                                       {"qid": "Q1", "p": "P408", "label": "Godot"}, {"qid": "Q1", "p": "P408", "label": "Source"}],
    }

    def test_facts(self):
        got = wdfacts.facts(src_of(self.FILES))
        self.assertEqual(got["Q1"]["web"], "https://example.org/a")          # the first, in a fixed order
        self.assertEqual(got["Q1"]["pcgw"], "Amber_Lantern")
        self.assertEqual(got["Q1"]["wiki"], {"en": "Amber_Lantern", "fr": "Lanterne_d%27ambre"})   # the site's languages, a clean address
        self.assertIn("schema:about", wdfacts.wiki_query())
        self.assertIn("facts-wiki", [n for n, _ in wdfacts.queries()])
        self.assertEqual(len(got["Q1"]["yt"]), wdfacts.VIDEOS)                # 11 characters, three at most
        self.assertEqual(got["Q1"]["age"], [["ESRB", "T"], ["CERO", "C"], ["PEGI", "12"], ["USK", "12"]])    # one for a system, by property
        self.assertEqual(got["Q1"]["team"], {"director": ["Ann", "Bo", "Cy"], "composer": ["Eve"]})
        self.assertEqual(got["Q1"]["engine"], ["Godot", "Source"])      # two at most, in the label order
        self.assertNotIn("Q2", got)                                           # nothing it says is kept
        self.assertNotIn("Q3", got)

    def test_without_the_files(self):
        self.assertEqual(wdfacts.facts(lambda name: {}), {})

    def test_the_rows_order_does_not_decide(self):
        files = {k: list(reversed(v)) for k, v in self.FILES.items()}
        self.assertEqual(wdfacts.facts(src_of(files)), wdfacts.facts(src_of(self.FILES)))


if __name__ == "__main__":
    unittest.main()
