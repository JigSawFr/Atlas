"""tools/collect.py and the platforms' tools reading what it keeps: the
files made from the sources collected are the ones each tool made when it
asked the sources itself (the same answers, the same files). Fictional
games only."""
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402
import collect  # noqa: E402
import common  # noqa: E402
import features  # noqa: E402
import trends  # noqa: E402

A, B, C = "0100000000010000", "0100000000020000", "0100000000030000"


class SourceFiles(unittest.TestCase):
    def test_parts(self):
        with tempfile.TemporaryDirectory() as out, mock.patch.object(common, "SHARD_BYTES", 200):
            games = {str(n): {"name": f"Lantern Tale {n}"} for n in range(1, 41)}
            report = []
            common.publish_source(out, "sources/demo/apps.json", {"schema": 1, "games": games}, None, report)
            self.assertFalse(os.path.exists(os.path.join(out, "sources/demo/apps.json")))
            self.assertTrue(os.path.exists(os.path.join(out, "sources/demo/apps/1.json")))
            got = common.read_records(out, "sources/demo/apps.json")
            self.assertEqual(list(got["games"].items()), list(games.items()))   # order kept
            self.assertNotIn("part", got)

    def test_guard(self):
        with tempfile.TemporaryDirectory() as last, tempfile.TemporaryDirectory() as out:
            report = []
            common.publish_source(last, "sources/demo/rows.json", {"schema": 1, "rows": [{"n": i} for i in range(100)]},
                                  None, report)
            with mock.patch.dict(os.environ, {"ALERTS": ""}):
                kept = not common.publish_source(out, "sources/demo/rows.json",
                                                 {"schema": 1, "rows": [{"n": 1}]}, last, report)
            self.assertTrue(kept)
            self.assertEqual(len(common.read_records(out, "sources/demo/rows.json")["rows"]), 100)

    def test_schema(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "sources/demo"))
            for name, body in (("newer", {"schema": 2, "games": {"1": {}}}), ("none", {"games": {"1": {}}}),
                               ("odd", ["not", "ours"]),
                               ("known", {"schema": 1, "games": {"1": {"name": "Lantern Tale"}}, "later": 3})):
                with open(os.path.join(d, f"sources/demo/{name}.json"), "w") as f:
                    json.dump(body, f)
            self.assertIsNone(common.read_records(d, "sources/demo/newer.json"))   # another schema: no file
            self.assertIsNone(common.read_records(d, "sources/demo/none.json"))
            self.assertIsNone(common.read_records(d, "sources/demo/odd.json"))
            self.assertEqual(common.read_records(d, "sources/demo/known.json")["later"], 3)   # unknown field kept
        with tempfile.TemporaryDirectory() as last, tempfile.TemporaryDirectory() as out:
            os.makedirs(os.path.join(last, "sources/demo"))
            with open(os.path.join(last, "sources/demo/rows.json"), "w") as f:
                json.dump({"schema": 2, "rows": [{"n": i} for i in range(100)]}, f)
            # the last run's file is of another schema: no guard against it
            self.assertTrue(common.publish_source(out, "sources/demo/rows.json",
                                                  {"schema": 1, "rows": [{"n": 1}]}, last, []))

    def test_rows(self):
        answer = [{"tid": {"type": "literal", "value": A}, "name": {"value": "Lantern Tale", "xml:lang": "en"}}]
        rows = common.rows_of(answer)
        self.assertEqual(rows, [{"tid": A, "name": "Lantern Tale"}])
        self.assertEqual(common.bindings(rows), [{"tid": {"value": A}, "name": {"value": "Lantern Tale"}}])

    def test_reader(self):
        with tempfile.TemporaryDirectory() as fresh, tempfile.TemporaryDirectory() as last:
            for d, n in ((fresh, 1), (last, 2)):
                os.makedirs(os.path.join(d, "sources/demo"))
                with open(os.path.join(d, "sources/demo/a.json"), "w") as f:
                    json.dump({"schema": 1, "games": {"n": n}, "generated": "2026-10-30"}, f)
            with open(os.path.join(last, "sources/demo/b.json"), "w") as f:
                json.dump({"schema": 1, "games": {"n": 3}}, f)
            src = common.reader(fresh, last)
            self.assertEqual(src("demo/a.json")["games"]["n"], 1)
            self.assertEqual(src("demo/b.json")["games"]["n"], 3)
            self.assertEqual(src("demo/c.json"), {})
            self.assertEqual(common.collected_today(src, "demo/a.json", datetime.date(2026, 10, 30))["games"]["n"], 1)
            self.assertEqual(common.collected_today(src, "demo/b.json", "2026-10-30"), {})


class SameFiles(unittest.TestCase):
    def test_monthly_views(self):
        known = {f"g{n}": (n % 7, f"Page {n}" if n % 5 else None) for n in range(600)}
        known["dup"] = (6, "Page 1")
        starts, end = build.months(datetime.date(2026, 10, 30))

        def views(article, starts_, end_):
            if article == "Page 3":
                raise urllib.error.HTTPError(article, 429, "no", {}, None)
            return [1, 2, len(article)]
        with mock.patch.object(build, "views", views), mock.patch.object(build.time, "sleep"):
            asked = build.read_views(known, starts, end)
            pages = build.fetch_views(build.best_articles(known), starts, end)
        self.assertEqual(build.views_from(known, json.loads(json.dumps(pages))), asked)

    def test_monthly_views_retry_after(self):
        # A page refused for too many requests is asked again once, after Wikimedia's Retry-After.
        starts, end = build.months(datetime.date(2026, 10, 30))
        asked, waits = [], []

        def views(article, starts_, end_):
            asked.append(article)
            if article == "Busy" and asked.count("Busy") == 1:
                raise urllib.error.HTTPError(article, 429, "no", {"Retry-After": "75"}, None)
            if article == "Gone":
                raise urllib.error.HTTPError(article, 429, "no", {"Retry-After": "9999"}, None)
            return [1, 2, 3]
        with mock.patch.object(build, "views", views):
            pages = build.fetch_views(["Busy", "Gone", "Calm"], starts, end, sleep=waits.append)
        self.assertEqual(sorted(pages), ["Busy", "Calm"])
        self.assertEqual(asked, ["Busy", "Busy", "Gone", "Gone", "Calm"])
        self.assertEqual(waits[0], 75)
        self.assertIn(120, waits)   # at most two minutes

    def test_daily_views(self):
        by_game = {A: [("en", "Lantern Tale"), ("fr", "Lantern Tale")], B: [("en", "Quiet Pond")], C: [("ja", "Echo")]}
        start, end = trends.window(datetime.date(2026, 10, 30))

        def daily(lang, title, start_, end_, fetch):
            if title == "Echo":
                raise urllib.error.HTTPError(title, 429, "no", {}, None)
            return [len(title) * (i + 1) for i in range(trends.DAYS)]
        with mock.patch.object(trends, "daily", daily):
            asked = trends.read_trends(by_game, start, end, None, sleep=lambda s: None)
            pages = trends.fetch_daily(by_game, start, end, None, sleep=lambda s: None)
        self.assertEqual(trends.from_pages(by_game, json.loads(json.dumps(pages))), asked)

    def test_steamspy(self):
        apps = {A: 900010, B: 900020, C: 900030}
        previous = {C: {"app": 900030, "positive": 1, "negative": 1, "owners": 0, "ccu": 0}}
        answers = {"900010": {"positive": 90, "negative": 10, "owners": "20,000 .. 50,000", "ccu": 3}}

        def fetch(url):
            app = url.rsplit("=", 1)[-1]
            if app == "900020":
                raise urllib.error.URLError("down")
            return answers.get(app, {"positive": 0, "negative": 0})
        with mock.patch.object(features, "STEAM_PAUSE", 0):
            spied = features.read_steam(apps, previous, fetch, sleep=lambda s: None)
        store = {A: (95, 5)}
        asked = features.with_reviews(spied, store, apps)
        items = {"900010": {"reviews": {"summary_filtered": {"review_count": 100, "percent_positive": 95}}}}
        src = {"steam-store/apps.json": {"games": items}, "steamspy/apps.json": {"games": answers}}
        before = {C: {"steam": previous[C]}}
        self.assertEqual(build.steam_figures(lambda n: src.get(n, {}), apps, before), asked)


class NoPrices(unittest.TestCase):
    """Atlas keeps no price nor sale (2026-10-30): the stores' answers are
    kept without theirs, nothing is asked for them every day, and the one-time
    cleanup takes their files off the data branch."""

    def test_steam_item(self):
        item = {"appid": 900001, "success": 1, "type": 0, "name": "Lantern Tale", "is_free": False,
                "reviews": {"summary_filtered": {"review_count": 10, "percent_positive": 90}},
                "best_purchase_option": {"final_price_in_cents": 999, "original_price_in_cents": 1999,
                                         "lowest_recent_price_in_cents": 799}}
        kept = collect.steam_item(item)
        self.assertNotIn("best_purchase_option", kept)
        self.assertEqual(kept["reviews"], item["reviews"])

    def test_gog_catalog(self):
        product = {"id": 1207000001, "title": "Quiet Pond", "slug": "quiet_pond", "reviewsCount": 12, "reviewsRating": 43,
                   "price": {"finalMoney": {"amount": "3.99"}, "baseMoney": {"amount": "19.99"}}}
        asked = []

        def fetch(url):
            asked.append(url)
            return {"pages": 1, "products": [product]}
        with tempfile.TemporaryDirectory() as out, mock.patch.object(common, "fetch", lambda url, **k: fetch(url)):
            collect.collect_gog("weekly", out, None, [], datetime.date(2026, 11, 2), [])
            kept = common.read_records(out, "sources/gog/catalog/US.json")
        self.assertEqual(len(asked), 1)
        self.assertNotIn("currencyCode", asked[0])
        self.assertEqual(kept["games"]["1207000001"]["reviewsCount"], 12)
        self.assertNotIn("price", kept["games"]["1207000001"])

    def test_one_source_a_job(self):
        with self.assertRaises(SystemExit), mock.patch.object(sys, "argv", ["collect.py", "eshop", "daily", "o", "o"]):
            collect.main()
        with self.assertRaises(SystemExit), mock.patch.object(sys, "argv", ["collect.py", "steam-store:FR", "daily", "o", "o"]):
            collect.main()
        with tempfile.TemporaryDirectory() as out, \
                mock.patch.object(sys, "argv", ["collect.py", "steam-store", "weekly", out, out]), \
                mock.patch.dict(collect.COLLECTORS, {"steam-store": lambda *a, **k: None}):
            collect.main()
            self.assertEqual(os.listdir(os.path.join(out, ".runtimes")), ["collect steam-store weekly.json"])

    def test_daily_asks_no_store(self):
        with open(os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "daily.yml"), encoding="utf-8") as f:
            daily = f.read()
        asked = sorted(set(re.findall(r"tools/collect\.py (\S+) daily", daily)))
        self.assertEqual(asked, ["wikidata", "wikipedia"])
        for gone in ("prices.py", "steam_prices.py", "gog.py prices", "xbox.py prices", "steam-store"):
            self.assertNotIn(gone, daily)

    def test_cleanup(self):
        script = os.path.join(os.path.dirname(__file__), "..", "tools", "drop-prices.sh")
        with tempfile.TemporaryDirectory() as d:
            kept = ["platforms/switch/popular.json", "platforms/steam/games.json", "sources/gog/catalog/US.json",
                    "sources/steam-store/apps.json", "sources/msstore/products.json", "sources/titledb/US.json"]
            gone = ["platforms/switch/prices/FR.json", "platforms/xbox/prices/JP.json", "history/steam/2026-10.json",
                    "sources/eshop/prices/FR.json", "sources/steam-store/prices/DE.json", "sources/msstore/prices/BR.json",
                    "sources/gog/catalog/FR.json", "sources/gog/catalog/JP/1.json"]
            for name in kept + gone:
                os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)
                with open(os.path.join(d, name), "w") as f:
                    f.write("{}")
            subprocess.run(["bash", script, d], check=True)
            for name in kept:
                self.assertTrue(os.path.exists(os.path.join(d, name)), name)
            for name in gone:
                self.assertFalse(os.path.exists(os.path.join(d, name)), name)
            for folder in ("history", "sources/eshop", "platforms/switch/prices"):
                self.assertFalse(os.path.exists(os.path.join(d, folder)), folder)
            subprocess.run(["bash", script, d], check=True)   # again: nothing left to do, no error


if __name__ == "__main__":
    unittest.main()
