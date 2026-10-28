"""tools/build.py's parts that need no network: the critics' scores read,
the reviews kept, the months, the scores and trends, the upcoming games."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402


def binding(**values):
    return {k: {"value": v} for k, v in values.items()}


class Build(unittest.TestCase):
    def test_base_id(self):
        self.assertEqual(build.base_id(" 0100b0c013912000 "), "0100B0C013912000")
        for other in ("0100B0C013912800", "0100B0C013913000"[:-1], "", None, "zzzz"):
            self.assertIsNone(build.base_id(other))

    def test_score_of(self):
        self.assertEqual(build.score_of("84%"), 84)
        self.assertEqual(build.score_of("8.5/10"), 85)
        self.assertEqual(build.score_of("80 / 100"), 80)
        for bad in ("84", "A+", "11/10", "5/0", "", None):
            self.assertIsNone(build.score_of(bad))

    def test_reviews(self):
        rows = [binding(tid="01000B3012F3A000", score="84%", count="31"),
                binding(tid="01000B3012F3A000", score="80/100", count="30"),
                binding(tid="01008DF00B78E000", score="7/10"),
                binding(tid="01008DF00B78E800", score="90%", count="9"),
                binding(tid="0100000000010000", score="great", count="50")]
        self.assertEqual(build.reviews(rows), {"01000B3012F3A000": (31, 84.0), "01008DF00B78E000": (0, 70.0)})

    def test_games(self):
        rows = [binding(tid="0100000000010000", links="10", article="https://en.wikipedia.org/wiki/A%27s_game"),
                binding(tid="0100000000010000", links="10", article="https://en.wikipedia.org/wiki/A%27s_game", score="84%"),
                binding(tid="0100000000010000", links="12"),
                binding(tid="0100000000020000", links="3"),
                binding(tid="0100000000020800", links="50")]
        self.assertEqual(build.games(rows), {"0100000000010000": (12, "A's_game"), "0100000000020000": (3, None)})

    def test_months(self):
        starts, end = build.months(datetime.date(2026, 1, 15))
        self.assertEqual(starts, [datetime.date(2025, 10, 1), datetime.date(2025, 11, 1), datetime.date(2025, 12, 1)])
        self.assertEqual(end, datetime.date(2025, 12, 31))

    def test_popular(self):
        known = {"0100000000010000": (60, "Big"), "0100000000020000": (6, "Small"), "0100000000030000": (0, None)}
        critics = {"0100000000010000": (100, 92.4)}
        # No views: sitelinks and reviews, no trend.
        table = build.popular(known, critics, {})
        self.assertEqual(table["0100000000010000"], [100, 0, 92])
        self.assertLess(table["0100000000020000"][0], 50)
        self.assertNotIn("0100000000030000", table)
        # Views: the trend of a page read enough, none of one read too little.
        read = {"Big": [1000, 1000, 1500], "Small": [10, 10, 40]}
        table = build.popular(known, critics, read)
        self.assertEqual(table["0100000000010000"][1], 50)
        self.assertEqual(table["0100000000020000"][1], 0)

    def test_upcoming(self):
        today = datetime.date(2026, 10, 28)
        titles = {
            "1": {"id": "0100000000010000", "name": "Soon", "releaseDate": 20261204},
            "2": {"id": "0100000000020000", "name": "Out", "releaseDate": 20261028},
            "3": {"id": "0100000000030000", "name": "Far", "releaseDate": 20281204},
            "4": {"id": "0100000000040000", "name": "Demo", "releaseDate": 20261204, "isDemo": True},
            "5": {"id": None, "name": "No id", "releaseDate": 20261204},
            "6": {"id": "0100000000060000", "name": "", "releaseDate": 20261204},
            "7": {"id": "0100000000070000", "name": "Bad", "releaseDate": "soon"},
        }
        self.assertEqual(build.upcoming(titles, today), {"0100000000010000": [20261204, "Soon"]})


if __name__ == "__main__":
    unittest.main()
