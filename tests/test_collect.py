"""tools/collect.py and the platforms' tools reading what it keeps: the
files made from the sources collected are the ones each tool made when it
asked the sources itself (the same answers, the same files). Fictional
games only."""
import datetime
import json
import os
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
import prices  # noqa: E402
import steam_prices  # noqa: E402
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


def price(nsu, regular, sale=None, status="onsale"):
    p = {"title_id": nsu, "sales_status": status}
    if regular is not None:
        p["regular_price"] = {"currency": "EUR", "raw_value": str(regular)}
    if sale is not None:
        p["discount_price"] = {"raw_value": str(sale), "end_datetime": "2026-11-01T06:59:59Z"}
    return p


class SameFiles(unittest.TestCase):
    def test_eshop(self):
        ids = {n: f"01000000000{n:02d}000" for n in range(1, 121)}
        ids[7] = ids[3]   # two eShop ids of one game: the first answered wins

        def fetch(url):
            numbers = [int(x) for x in url.split("ids=")[1].split(",")]
            return {"prices": [price(n, 5.0, 2.5 if n % 10 == 0 else (6.0 if n == 9 else None),
                                     "sales_termination" if n == 11 else "onsale") for n in numbers]
                    + [price(None, 1.0), price(3, None)]}

        with mock.patch.object(prices.time, "sleep"), mock.patch.object(collect.time, "sleep"):
            asked = prices.read_country("FR", ids, fetch, workers=2)
            kept = json.loads(json.dumps(collect.read_eshop("FR", ids, fetch, workers=2)))
        self.assertEqual(prices.from_answers(kept, ids), asked)

    def test_steam_prices(self):
        def fetch(url):
            apps = [a["appid"] for a in json.loads(urllib.parse.unquote(url.split("input_json=")[1]))["ids"]]
            return {"response": {"store_items": [
                {"appid": a, "success": 1, "is_free": a == 900003, "name": "x",
                 "best_purchase_option": {"final_price_in_cents": 999, "original_price_in_cents": 1999 if a % 2 else 999,
                                          "active_discounts": [{"discount_end_date": 1793491199}],
                                          "lowest_recent_price_in_cents": 799}} for a in apps]}}
        import urllib.parse  # noqa: F401
        apps = [str(900000 + n) for n in range(1, 450)]
        asked = steam_prices.read_country("FR", apps, fetch, workers=2, pause=0)
        items = steam_prices.read_items("FR", apps, fetch, workers=2, pause=0)
        kept = json.loads(json.dumps({app: collect.steam_item(item) for app, item in items.items()}))
        self.assertEqual(steam_prices.rows_of(kept), asked)

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


if __name__ == "__main__":
    unittest.main()
