"""tools/features.py without the network: the traits read from Wikidata's
rows, SteamSpy's answers, the time budget, the games alike."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402
import features  # noqa: E402


def row(tid, value, label=None):
    b = {"tid": {"value": tid}, "value": {"value": "http://www.wikidata.org/entity/" + value}}
    if label is not None:
        b["valueLabel"] = {"value": label}
    return b


A, B, C, D = "0100000000010000", "0100000000020000", "0100000000030000", "0100000000040000"


class Features(unittest.TestCase):
    def test_traits(self):
        rows = {"series": [row(A, "Q1", "Saga"), row(A, "Q1", "Saga"), row(B, "Q1", "Saga")],
                "genres": [row(A, "Q9", "Q9"), row("0100000000010800", "Q2", "Update"), row(C, "notanid", "x")]}
        got = features.traits(rows, build.base_id)
        self.assertEqual(got[A], {"series": [["Q1", "Saga"]], "genres": [["Q9", ""]]})
        self.assertEqual(got[B], {"series": [["Q1", "Saga"]]})
        self.assertNotIn(C, got)

    def test_steam(self):
        rows = [{"tid": {"value": A}, "steam": {"value": "504230"}}, {"tid": {"value": A}, "steam": {"value": "400"}},
                {"tid": {"value": B}, "steam": {"value": "x1"}}]
        self.assertEqual(features.steam_ids(rows, build.base_id), {A: 400})
        self.assertEqual(features.owners_low("2,000,000 .. 5,000,000"), 2000000)
        self.assertEqual(features.owners_low(None), 0)
        self.assertEqual(features.steam_of({"positive": 10, "negative": 2, "owners": "0 .. 20,000", "ccu": 3}),
                         {"positive": 10, "negative": 2, "owners": 0, "ccu": 3})
        for nothing in ({}, {"positive": 0, "negative": 0}, {"positive": "1", "negative": 0}, [], None):
            self.assertIsNone(features.steam_of(nothing))

    def test_read_steam(self):
        clock = [0.0]
        asked = []

        def fetch(url):
            asked.append(url)
            return {"positive": 5, "negative": 1, "owners": "1,000 .. 2,000", "ccu": 0}

        def sleep(s):
            clock[0] += s

        apps = {A: 1, B: 2, C: 3}
        previous = {A: {"app": 1, "positive": 9, "negative": 9, "owners": 0, "ccu": 0},
                    C: {"app": 99, "positive": 1, "negative": 1, "owners": 0, "ccu": 0}}
        # Room for two: the games not known before go first; A keeps what was known.
        got = features.read_steam(apps, previous, fetch, budget=1.5, now=lambda: clock[0], sleep=sleep)
        self.assertEqual(asked, [features.STEAMSPY.format(2), features.STEAMSPY.format(3)])
        self.assertEqual(got[A]["positive"], 9)
        self.assertEqual(got[B]["app"], 2)
        # C's earlier figures were another app's: replaced.
        self.assertEqual(got[C], {"positive": 5, "negative": 1, "owners": 1000, "ccu": 0, "app": 3})

    def test_similar(self):
        t = lambda *pairs: [[v, ""] for v in pairs]  # noqa: E731
        game_traits = {
            A: {"series": t("Q1"), "genres": t("Q10", "Q11"), "modes": t("Q50")},
            B: {"series": t("Q1"), "genres": t("Q10"), "modes": t("Q50")},
            C: {"genres": t("Q11"), "modes": t("Q50")},
            D: {"modes": t("Q50")},
        }
        got = features.similar(game_traits)
        # A's series mate first, then the one sharing a genre; never D (a mode alone).
        self.assertEqual([o for o, _ in got[A]], [B, C])
        self.assertTrue(got[A][0][1] > got[A][1][1] > 0)
        self.assertNotIn(D, got)
        self.assertTrue(all(1 <= s <= 100 for row_ in got.values() for _, s in row_))


class SteamReviews(unittest.TestCase):
    def test_reviews_of(self):
        item = {"reviews": {"summary_filtered": {"review_count": 1200, "percent_positive": 91}}}
        self.assertEqual(features.reviews_of(item), (1092, 108))
        for none in (None, {}, {"reviews": {"summary_filtered": {"review_count": 0, "percent_positive": 0}}}):
            self.assertIsNone(features.reviews_of(none))

    def test_with_reviews(self):
        apps = {A: 900010, B: 900011, C: 900012}
        spied = {A: {"app": 900010, "positive": 10, "negative": 2, "owners": 50000, "ccu": 7}}
        got = features.with_reviews(spied, {A: (1092, 108), B: (5, 1)}, apps)
        self.assertEqual(got, {A: {"app": 900010, "positive": 1092, "negative": 108, "owners": 50000, "ccu": 7},
                               B: {"app": 900011, "positive": 5, "negative": 1, "owners": 0, "ccu": 0}})


if __name__ == "__main__":
    unittest.main()
