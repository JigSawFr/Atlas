"""tools/trends.py without the network: the pages of each language, the
views a day, a trend, the scores kept."""
import contextlib
import datetime
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402
import common  # noqa: E402
import trends  # noqa: E402

A, B, C = "0100000000010000", "0100000000020000", "0100000000030000"


def row(tid, url):
    return {"tid": {"value": tid}, "article": {"value": url}}


def flat(tid, url):
    """A row as the sources keep it (tools/collect.py: {variable: value})."""
    return {"tid": tid, "article": url}


class Trends(unittest.TestCase):
    def test_pages(self):
        rows = [row(A, "https://en.wikipedia.org/wiki/Lantern_Tale"), row(A, "https://fr.wikipedia.org/wiki/Lantern_Tale_%28jeu%29"),
                row(A, "https://en.wikipedia.org/wiki/Lantern_Tale"), row(B, "https://xx.wikipedia.org/wiki/Quiet_Pond"),
                row("0100000000010800", "https://en.wikipedia.org/wiki/Update")]
        self.assertEqual(trends.pages(rows, build.base_id), {A: [("en", "Lantern_Tale"), ("fr", "Lantern_Tale_(jeu)")]})
        self.assertIn('"0100000000010000"', trends.pages_query([A]))
        self.assertIn("<https://ja.wikipedia.org/>", trends.pages_query([A]))

    def test_steam_pages(self):
        rows = [row("400", "https://en.wikipedia.org/wiki/Portal_Like"), row("x1", "https://en.wikipedia.org/wiki/Not_An_App")]
        self.assertEqual(trends.pages(rows, trends.app_id), {"400": [("en", "Portal_Like")]})
        query = trends.pages_query(["400"], "P1733")
        self.assertIn("wdt:P1733 ?tid", query)
        self.assertIn('"400"', query)
        self.assertEqual([p[0] for p in trends.PLATFORMS], [build.SWITCH, "steam"])

    def test_top(self):
        popular = {"games": {A: [10, 0, 0], B: [90, 0, 0], C: "not a row"}}
        self.assertEqual(trends.top(popular), [B, A])
        self.assertEqual(trends.top({}), [])

    def test_page_read_once(self):
        asked = []

        def daily(lang, title, start, end, fetch):
            asked.append(title)
            return [1] * trends.DAYS
        start, end = trends.window(datetime.date(2026, 10, 30))
        by_game = {f"switch:{A}": [("en", "Lantern Tale")], "steam:400": [("en", "Lantern Tale"), ("fr", "Lantern")]}
        with mock.patch.object(trends, "daily", daily):
            pages = trends.fetch_daily(by_game, start, end, None, sleep=lambda s: None)
        self.assertEqual(asked, ["Lantern Tale", "Lantern"])
        self.assertEqual(set(pages), {"en:Lantern Tale", "fr:Lantern"})

    def test_steam_updated(self):
        got = trends.updated({"schema": 1, "platform": "steam", "games": {"400": [80, 3, 70]}}, {"400": 25},
                             datetime.date(2026, 10, 30), "steam")
        self.assertEqual((got["platform"], got["games"]), ("steam", {"400": [80, 25, 70]}))

    def test_batches(self):
        asked = []

        def sparql(query):
            asked.append(query)
            return [row(t, f"https://en.wikipedia.org/wiki/{t}") for t in query.split('"')[1::2] if t.startswith("0100")]

        tids = [f"01000000{n:05X}000" for n in range(1, 201)]
        got = trends.all_pages(tids, sparql, sleep=lambda s: None)
        self.assertEqual(len(asked), 3)                    # 200 games, 80 a query
        self.assertTrue(all(len(q) < 6000 for q in asked))
        self.assertEqual(len(got), 200)

    def test_trend(self):
        self.assertEqual(trends.trend([100] * 28 + [200] * 7), 100)     # twice a week of before
        self.assertEqual(trends.trend([100] * 28 + [50] * 7), -50)
        self.assertEqual(trends.trend([10] * 35), 0)                      # too little read
        self.assertEqual(trends.trend([0] * 28 + [500] * 7), 0)           # nothing before

    def test_read(self):
        start, end = trends.window(datetime.date(2026, 10, 29))
        self.assertEqual((start, end), (datetime.date(2026, 9, 24), datetime.date(2026, 10, 28)))

        def fetch(url):
            # Every page: 100 views a day, then 300 the last week; B's French page refused.
            if "fr.wikipedia" in url:
                raise urllib.error.HTTPError(url, 429, "busy", {}, None)
            items = []
            for i in range(35):
                day = start + datetime.timedelta(days=i)
                items.append({"timestamp": day.strftime("%Y%m%d") + "00", "views": 300 if i >= 28 else 100})
            return {"items": items}

        got = trends.read_trends({A: [("en", "A")], B: [("en", "B"), ("fr", "B")]}, start, end, fetch, sleep=lambda s: None)
        self.assertEqual(got, {A: 200, B: 200})

    def test_updated(self):
        popular = {"schema": 1, "month": "2026-09", "games": {A: [90, 5, 80], B: [50, -3, 0], C: [10, 0, 0]}}
        got = trends.updated(popular, {A: 40, B: 0}, datetime.date(2026, 10, 29))
        self.assertEqual(got["games"], {A: [90, 40, 80], B: [50, 0, 0], C: [10, 0, 0]})
        self.assertEqual((got["trends"], got["month"]), ("2026-10-29", "2026-09"))

    def test_updated_keeps_what_it_does_not_know(self):
        popular = {"schema": 1, "games": {A: [90, 5, 80, "more"], B: [50], C: "not a row"}}
        got = trends.updated(popular, {A: 40, B: 10, C: 10}, datetime.date(2026, 10, 29))
        self.assertEqual(got["games"], {A: [90, 40, 80, "more"], B: [50], C: "not a row"})


class Main(unittest.TestCase):
    """The daily run with no last popular.json it can read: nothing to redo, said, no error."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "out")
        self.last = os.path.join(self.tmp.name, "last")
        os.makedirs(os.path.join(self.last, "platforms", build.SWITCH))

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self):
        def no_network(*args, **kwargs):
            raise AssertionError("nothing to measure: no request")
        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["trends.py", self.out, self.last, os.path.join(self.tmp.name, "sources")]), \
                mock.patch.object(common, "sparql", no_network), mock.patch.object(common, "fetch", no_network), \
                contextlib.redirect_stderr(err):
            trends.main()
        # Nothing made (the run's time alone is kept, in .runtimes/).
        self.assertFalse(os.path.exists(os.path.join(self.out, "platforms")))
        self.assertIn("nothing to redo", err.getvalue())

    def put(self, body):
        path = os.path.join(self.last, "platforms", build.SWITCH, "popular.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f)
        return path

    def test_no_file(self):
        self.run_main()

    def test_later_schema(self):
        body = {"schema": common.SCHEMA + 1, "games": {A: {"score": 90}}}
        path = self.put(body)
        self.run_main()
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), body)                # left as it was

    def test_no_schema(self):
        self.put({"games": {A: [90, 5, 80]}})
        self.run_main()

    def test_no_rows(self):
        self.put({"schema": common.SCHEMA, "games": {A: [90]}})
        self.run_main()


class Consolidate(unittest.TestCase):
    """Both platforms' trends from one day's sources; a platform without its
    last popular.json is left alone."""

    def test_switch_and_steam(self):
        today = datetime.date(2026, 10, 30)
        views = [100] * 28 + [300] * 7
        sources = {
            "wikidata/switch-pages.json": {"rows": [flat(A, "https://en.wikipedia.org/wiki/Lantern_Tale")]},
            "wikidata/steam-pages.json": {"rows": [flat("400", "https://en.wikipedia.org/wiki/Lantern_Tale"),
                                                   flat("500", "https://fr.wikipedia.org/wiki/Quiet_Pond")]},
            "wikipedia/daily.json": {"generated": today.isoformat(),
                                     "pages": {"en:Lantern_Tale": views, "fr:Quiet_Pond": [10] * 35}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            last, out = os.path.join(tmp, "last"), os.path.join(tmp, "out")
            for platform, games in (("switch", {A: [90, 5, 80]}), ("steam", {"400": [80, 1, 0], "500": [70, 9, 0]})):
                os.makedirs(os.path.join(last, "platforms", platform))
                with open(os.path.join(last, "platforms", platform, "popular.json"), "w", encoding="utf-8") as f:
                    json.dump({"schema": common.SCHEMA, "platform": platform, "games": games}, f)
            with contextlib.redirect_stderr(io.StringIO()):
                trends.consolidate(lambda name: sources.get(name, {}), out, last, today)
            with open(os.path.join(out, "platforms", "steam", "popular.json"), encoding="utf-8") as f:
                got = json.load(f)
            self.assertEqual(got["games"], {"400": [80, 200, 0], "500": [70, 0, 0]})
            self.assertEqual((got["platform"], got["trends"]), ("steam", "2026-10-30"))
            with open(os.path.join(out, "platforms", "switch", "popular.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["games"], {A: [90, 200, 80]})


class NetworkErrors(unittest.TestCase):
    """A page not reached (network, timeout, an answer not JSON) is left out
    and the others read, as a page refused; after a few, no more."""

    def test_daily(self):
        by_game = {"A": [("en", "Lantern Tale"), ("fr", "Lantern Tale")], "B": [("en", "Quiet Pond")],
                   "C": [("ja", "Echo")], "D": [("en", "Moss Road")]}
        wrong = {"fr": urllib.error.URLError("Name or service not known"), "ja": TimeoutError("timed out")}

        def daily(lang, title, start, end, fetch):
            if lang in wrong:
                raise wrong[lang]
            if title == "Quiet Pond":
                raise ValueError("not JSON")
            return [len(title)] * trends.DAYS
        start, end = trends.window(datetime.date(2026, 10, 30))
        with mock.patch.object(trends, "daily", daily):
            pages = trends.fetch_daily(by_game, start, end, None, sleep=lambda s: None)
            self.assertEqual(sorted(pages), ["en:Lantern Tale", "en:Moss Road"])
            wrong["en"] = ConnectionResetError("reset")
            self.assertEqual(trends.fetch_daily(by_game, start, end, None, sleep=lambda s: None), {})

    def test_monthly(self):
        import build
        starts, end = build.months(datetime.date(2026, 10, 30))

        def views(article, starts_, end_):
            if article == "Echo":
                raise urllib.error.URLError("Temporary failure in name resolution")
            return [1, 2, 3]
        with mock.patch.object(build, "views", views), mock.patch.object(build.time, "sleep"):
            self.assertEqual(sorted(build.fetch_views(["Lantern Tale", "Echo", "Moss Road"], starts, end)),
                             ["Lantern Tale", "Moss Road"])


if __name__ == "__main__":
    unittest.main()
