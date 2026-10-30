"""tools/build.py's parts that need no network: the critics' scores read,
the reviews kept, the months, the scores and trends, the upcoming games."""
import datetime
import json
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
                binding(tid="0100000000010000", score="great", count="50"),
                # An unknown number of reviews: Wikidata gives a blank node.
                binding(tid="0100000000020000", score="75%",
                        count="http://www.wikidata.org/.well-known/genid/06bbd14e8fb318f31861d45c712357df")]
        self.assertEqual(build.reviews(rows), {"01000B3012F3A000": (31, 84.0), "01008DF00B78E000": (0, 70.0),
                                               "0100000000020000": (0, 75.0)})
        self.assertEqual([build.count_of(v) for v in ("12", "3.0", "-4", "inf", "nan", "", None)], [12, 3, 0, 0, 0, 0, 0])

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


class PreviousGames(unittest.TestCase):
    """The last run's games.json, read for its Steam audience."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "platforms", build.SWITCH))

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, body):
        with open(os.path.join(self.tmp.name, "platforms", build.SWITCH, "games.json"), "w", encoding="utf-8") as f:
            json.dump(body, f)

    def test_previous_games(self):
        self.assertEqual(build.previous_games(self.tmp.name), {})                  # none
        games = {"0100A1B2C3D4E000": {"steam": {"app": 900010}}}
        self.put({"schema": build.SCHEMA, "games": games})
        self.assertEqual(build.previous_games(self.tmp.name), games)
        self.put({"schema": build.SCHEMA + 1, "games": games})                    # a later schema
        self.assertEqual(build.previous_games(self.tmp.name), {})
        self.put({"games": games})                                                  # none said
        self.assertEqual(build.previous_games(self.tmp.name), {})


class Guard(unittest.TestCase):
    """A file that lost too many games is not published: the last run's is kept."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "out")
        self.last = os.path.join(self.tmp.name, "last")
        os.makedirs(self.out)
        os.makedirs(self.last)
        build.write(os.path.join(self.last, "popular.json"), {"schema": 1, "games": {f"{i:016X}": [1, 0, 0] for i in range(100)}})
        # The workflows set ALERTS for the run: these made-up files must not write to it.
        from unittest import mock
        self.env = mock.patch.dict(os.environ, {"ALERTS": os.path.join(self.tmp.name, "test-alerts.md")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def payload(self, n):
        return {"schema": 1, "games": {f"{i:016X}": [2, 0, 0] for i in range(n)}}

    def test_kept(self):
        report = []
        self.assertFalse(build.publish(self.out, "popular.json", self.payload(40), self.last, report))
        self.assertEqual(build.count_in(os.path.join(self.out, "popular.json")), 100)
        self.assertEqual(report, [("popular.json", 100, 40, True)])
        self.assertIn("no: last run kept", build.summary(report, path=os.path.join(self.tmp.name, "summary.md")))

    def test_alert(self):
        alerts = os.path.join(self.tmp.name, "alerts.md")
        from unittest import mock
        with mock.patch.dict(os.environ, {"ALERTS": alerts}):
            build.publish(self.out, "popular.json", self.payload(40), self.last, [])
            build.publish(self.out, "popular.json", self.payload(95), self.last, [])
        with open(alerts, encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["`popular.json` came out with 40 games against 100 last time: the last run's file was kept."])

    def test_published(self):
        report = []
        self.assertTrue(build.publish(self.out, "popular.json", self.payload(90), self.last, report))
        self.assertEqual(build.count_in(os.path.join(self.out, "popular.json")), 90)
        # No last run, or a small one: published whatever its size.
        self.assertTrue(build.publish(self.out, "games.json", self.payload(1), self.last, report))
        self.assertTrue(build.publish(self.out, "upcoming.json", self.payload(1), None, report))
        self.assertIn("| `popular.json` | 100 | 90 (-10 %) | yes |", build.summary(report, path=os.path.join(self.tmp.name, "s.md")))
