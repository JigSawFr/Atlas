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
import schemas  # noqa: E402
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
        self.assertEqual((start, end), (datetime.date(2026, 7, 30), datetime.date(2026, 10, 28)))

        def fetch(url):
            # Every page: 100 views a day, then 300 the last week; B's French page refused.
            if "fr.wikipedia" in url:
                raise urllib.error.HTTPError(url, 429, "busy", {}, None)
            items = []
            for i in range(trends.DAYS):
                day = start + datetime.timedelta(days=i)
                items.append({"timestamp": day.strftime("%Y%m%d") + "00", "views": 300 if i >= trends.DAYS - 7 else 100})
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

    def test_daily_waits_as_asked(self):
        # Wikimedia refuses (429, Retry-After: 45) every other request: each page asked again after 45 s.
        calls, slept = [], []

        def daily(lang, title, start, end, fetch):
            calls.append(title)
            if len(calls) % 2:
                raise urllib.error.HTTPError(title, 429, "busy", {"Retry-After": "45"}, None)
            return [1] * trends.DAYS
        by_game = {str(n): [("en", f"Page {n}")] for n in range(8)}
        start, end = trends.window(datetime.date(2026, 10, 30))
        with mock.patch.object(trends, "daily", daily), contextlib.redirect_stderr(io.StringIO()):
            pages = trends.fetch_daily(by_game, start, end, None, sleep=slept.append)
        self.assertEqual(len(pages), 8)                  # none lost, though a refusal a page
        self.assertEqual(slept.count(45), 8)
        self.assertEqual(trends.retry_after(urllib.error.HTTPError("u", 429, "", {"Retry-After": "900"}, None)),
                         trends.WAIT_MAX)
        self.assertEqual(trends.retry_after(TimeoutError()), trends.WAIT_MIN)

    def test_daily_wait_budget(self):
        # Always refused: asked again while the budget lasts, then five in a row: stopped.
        slept = []

        def daily(lang, title, start, end, fetch):
            raise urllib.error.HTTPError(title, 429, "busy", {"Retry-After": "120"}, None)
        by_game = {str(n): [("en", f"Page {n}")] for n in range(50)}
        start, end = trends.window(datetime.date(2026, 10, 30))
        with mock.patch.object(trends, "daily", daily), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(trends.fetch_daily(by_game, start, end, None, sleep=slept.append), {})
        self.assertLessEqual(sum(slept), trends.WAIT_BUDGET + trends.MISSES * trends.WAIT_MAX)

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


class Reach(unittest.TestCase):
    def test_reach_of(self):
        by_game = {A: [("en", "Lantern_Tale"), ("ja", "Lantern")], "0100000000002000": [("en", "Quiet_Pond")],
                   "0100000000003000": [("fr", "Missing"), ("zz", "Odd")]}
        pages = {"en:Lantern_Tale": [10] * 10, "ja:Lantern": [30] * 10, "en:Quiet_Pond": [1] * 10, "zz:Odd": [999] * 10}
        got = trends.reach_of(by_game, pages)
        self.assertEqual(got, {A: [25, 0, 0, 0, 0, 75, 0, 0, 0, 0, 0]})     # LANGS order: en fr de es it ja nl pt ko ru zh
        self.assertEqual(trends.reach_of(by_game, {}), {})

    def test_standing_in_each_language(self):
        by_game = {"g1": [("en", "A"), ("fr", "A_fr")], "g2": [("en", "B"), ("ja", "B_ja")], "g3": [("fr", "C")], "g4": [("en", "Rare")]}
        pages = {"en:A": [100] * 4, "fr:A_fr": [50] * 4, "en:B": [20] * 4, "ja:B_ja": [200] * 4, "fr:C": [100] * 4, "en:Rare": [1] * 4}
        totals = trends.totals_of(by_game, pages)
        self.assertEqual(sorted(totals), ["g1", "g2", "g3"])              # g4 read under MIN_VIEWS: out
        st = trends.standing_of(totals)
        i = {lang: n for n, lang in enumerate(trends.LANGS)}
        rank = lambda lang: [st["ranks"][g][i[lang]] for g in ("g1", "g2", "g3")]   # noqa: E731
        self.assertEqual(rank("en"), [1, 2, 0])                           # English: g1 400, g2 80; g3 none
        self.assertEqual(rank("fr"), [2, 0, 1])                           # French: g3 400, g1 200
        self.assertEqual(rank("ja"), [0, 1, 0])
        self.assertEqual((st["counts"][i["en"]], st["counts"][i["fr"]], st["counts"][i["ja"]], st["counts"][i["de"]]), (2, 2, 1, 0))
        self.assertEqual(st["base"][i["ja"]], round(800 * 100 / 1880, 1))   # Japanese: 800 of the 1,880 views (600 + 880 + 400)
        self.assertEqual(round(sum(st["base"])), 100)
        self.assertEqual(trends.standing_of({}), {"base": [0] * len(trends.LANGS), "counts": [0] * len(trends.LANGS), "ranks": {}})

    def test_published_with_the_trends(self):
        today = datetime.date(2026, 10, 30)
        sources = {"wikidata/switch-pages.json": {"rows": [flat(A, "https://en.wikipedia.org/wiki/Lantern_Tale")]},
                   "wikipedia/daily.json": {"generated": today.isoformat(), "pages": {"en:Lantern_Tale": [100] * 35}}}
        with tempfile.TemporaryDirectory() as tmp:
            last, out = os.path.join(tmp, "last"), os.path.join(tmp, "out")
            os.makedirs(os.path.join(last, "platforms", "switch"))
            with open(os.path.join(last, "platforms", "switch", "popular.json"), "w", encoding="utf-8") as f:
                json.dump({"schema": common.SCHEMA, "platform": "switch", "games": {A: [90, 5, 80]}}, f)
            with contextlib.redirect_stderr(io.StringIO()):
                trends.consolidate(lambda name: sources.get(name, {}), out, last, today)
            with open(os.path.join(out, "platforms", "switch", "reach.json"), encoding="utf-8") as f:
                got = json.load(f)
            self.assertEqual(got["games"], {A: [100] + [0] * (len(trends.LANGS) - 1)})
            self.assertEqual((got["languages"], got["schema"]), (list(trends.LANGS), common.SCHEMA))
            self.assertEqual(got["ranks"][A][0], 1)                                  # the one game: first in English
            self.assertEqual((len(got["base"]), len(got["counts"])), (len(trends.LANGS), len(trends.LANGS)))
            self.assertEqual(schemas.errors(got, schemas.KINDS["reach"]), [])
            self.assertEqual(schemas.kind_of("platforms/switch/reach.json"), "reach")


class Cadence(unittest.TestCase):
    """The pages read little are asked once in a few days (2026-11-10), the last run's series kept in between."""
    TODAY = datetime.date(2026, 11, 10)

    def test_cadence_by_views(self):
        self.assertEqual(trends.cadence([0] * 91), 7)
        self.assertEqual(trends.cadence([10] * 91), 7)         # 280 in the last 28 days
        self.assertEqual(trends.cadence([20] * 91), 3)         # 560
        self.assertEqual(trends.cadence([100] * 91), 1)        # 2,800: every day
        self.assertEqual(trends.cadence([100] * 63 + [0] * 28), 7)    # only the last 28 days count

    def test_carried_series(self):
        days = list(range(1, 92))
        moved = trends.carried(days, 3, 91)
        self.assertEqual(len(moved), 91)
        self.assertEqual(moved[:88], days[3:])                  # the days it still has
        self.assertEqual(moved[88:], [round(sum(days[-7:]) / 7)] * 3)    # the new ones: the last week's mean
        self.assertEqual(trends.carried(days, 0, 91), days)
        self.assertIsNone(trends.carried(days, 91, 91))         # too old
        self.assertIsNone(trends.carried(days, -1, 91))
        self.assertIsNone(trends.carried(days[:50], 1, 91))     # another length
        self.assertIsNone(trends.carried(None, 1, 91))

    def test_each_page_is_due_once_in_its_period(self):
        for every in (3, 7):
            days = [datetime.date(2026, 11, 1) + datetime.timedelta(days=i) for i in range(every * 4)]
            for key in ("en:Lantern_Tale", "fr:Quiet_Pond", "ja:Echo"):
                self.assertEqual(sum(trends.due(key, every, d) for d in days), 4)       # once in each period
        self.assertTrue(all(trends.due("en:X", 1, self.TODAY + datetime.timedelta(days=i)) for i in range(5)))
        # Not the same day for all the pages: the load is spread.
        keys = [f"en:Page_{i}" for i in range(60)]
        self.assertGreater(len({trends.due(k, 7, self.TODAY) for k in keys}), 1)
        self.assertLess(sum(trends.due(k, 7, self.TODAY) for k in keys), 30)

    def previous(self, **pages):
        return {"end": "2026-11-08", "pages": pages}        # the last run was yesterday's, whose window ended 2026-11-08

    def test_reuse_keeps_what_is_not_due(self):
        keys = [f"en:Cold_{i}" for i in range(40)]
        by_game = {f"g{i}": [("en", f"Cold_{i}")] for i in range(40)}
        previous = self.previous(**{k: [5] * 91 for k in keys})
        kept = trends.reuse(by_game, previous, self.TODAY)
        self.assertTrue(0 < len(kept) < 40)                                     # most are kept, the due ones asked
        self.assertTrue(all(k not in kept or trends.due(k, 7, self.TODAY) is False for k in keys))
        self.assertTrue(all(v == [5] * 91 for v in kept.values()))               # one day on: a flat series stays flat
        self.assertEqual(set(trends.reuse(by_game, previous, self.TODAY, everything=True)), set(keys))

    def test_reuse_asks_the_new_hot_and_stale(self):
        today = self.TODAY
        by_game = {"a": [("en", "Hot")], "b": [("en", "New")], "c": [("fr", "Short")], "d": [("de", "Old")]}
        previous = self.previous(**{"en:Hot": [100] * 91, "fr:Short": [1] * 50, "de:Old": [1] * 91})
        previous["end"] = "2026-10-01"                                           # a last run long ago: nothing can be moved
        self.assertEqual(trends.reuse(by_game, previous, today), {})
        previous["end"] = "2026-11-08"
        got = trends.reuse(by_game, previous, today, everything=True)
        self.assertNotIn("en:New", got)                                          # never read
        self.assertNotIn("fr:Short", got)                                        # another length
        self.assertIn("de:Old", got)
        self.assertNotIn("en:Hot", trends.reuse(by_game, previous, today))        # a page read much is asked every day
        for bad in (None, {}, {"end": "no", "pages": {}}, {"end": "2026-11-08", "pages": []}):
            self.assertEqual(trends.reuse(by_game, bad, today), {})

    def test_fetch_daily_does_not_ask_the_kept(self):
        asked = []

        def daily(lang, title, start_, end_, fetch):
            asked.append(f"{lang}:{title}")
            return [1] * trends.DAYS
        by_game = {A: [("en", "One"), ("fr", "Two")]}
        start, end = trends.window(self.TODAY)
        with mock.patch.object(trends, "daily", daily), contextlib.redirect_stderr(io.StringIO()):
            got = trends.fetch_daily(by_game, start, end, None, sleep=lambda s: None, skip={"fr:Two"})
        self.assertEqual((asked, list(got)), (["en:One"], ["en:One"]))


class SiteLanguages(unittest.TestCase):
    def test_every_language_of_the_site_is_read(self):
        """The site's locales (site/i18n, PlayShelf's too) all have their language's Wikipedia in LANGS."""
        names = [n[:-5] for n in os.listdir(os.path.join(os.path.dirname(__file__), "..", "site", "i18n")) if n.endswith(".json")]
        self.assertEqual(len(names), 15)
        self.assertEqual({n.split("-")[0] for n in names} - set(trends.LANGS), set())
        self.assertEqual(trends.LANGS[:8], ("en", "fr", "de", "es", "it", "ja", "nl", "pt"))   # reach.json's first columns


class Curves(unittest.TestCase):
    def test_weekly(self):
        days = list(range(1, 92))
        weeks = trends.weekly(days)
        self.assertEqual(len(weeks), 13)
        self.assertEqual(weeks[-1], sum(days[-7:]))                 # the last day ends the last week
        self.assertEqual(weeks[0], sum(days[0:7]))
        self.assertEqual(trends.weekly([1] * 15), [7, 7])           # whole weeks only
        self.assertEqual(trends.weekly([1] * 3), [])

    def test_curves(self):
        rows = [{"tid": "0100000000001000", "article": "https://en.wikipedia.org/wiki/Lantern_Tale"},
                {"tid": "0100000000001000", "article": "https://fr.wikipedia.org/wiki/Lanterne"},
                {"tid": "0100000000002000", "article": "https://en.wikipedia.org/wiki/Quiet_Pond"}]
        files = {"wikidata/switch-pages.json": {"rows": rows},
                 "wikipedia/daily.json": {"pages": {"en:Lantern_Tale": [10] * 91, "fr:Lanterne": [5] * 91, "en:Quiet_Pond": [0] * 91}}}
        got = trends.curves(lambda name: files.get(name, {}))
        self.assertEqual(got["switch"]["0100000000001000"], [105] * 13)     # the pages of all languages added up
        self.assertNotIn("0100000000002000", got["switch"])                 # nobody read it: no curve
        self.assertEqual(got["steam"], {})
        self.assertEqual(trends.curves(lambda name: {}), {"switch": {}, "steam": {}})


if __name__ == "__main__":
    unittest.main()
