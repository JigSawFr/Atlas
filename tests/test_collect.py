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


class RicherSources(unittest.TestCase):
    """What the sheets show beyond the names and the figures (2026-11-07): where a game runs, how the
    Steam Deck takes it, the languages, the age ratings, the capabilities, and the pictures' names (the
    pictures themselves are not kept). Each source's answer is cut to those, and what it is not asked for stays out."""

    def test_steam_item(self):
        item = {"appid": 900001, "success": 1, "type": 0, "name": "Lantern Tale",
                "platforms": {"windows": True, "mac": True, "steamos_linux": False, "vr_support": {}, "steam_deck_compat_category": 3,
                              "steam_os_compat_category": 2},
                "categories": {"supported_player_categoryids": [2, 1], "feature_categoryids": [22], "controller_categoryids": [28],
                               "something_new": [1]},
                "assets": {"asset_url_format": "steam/apps/900001/${FILENAME}?t=1", "header": "ab12/header.jpg",
                           "small_capsule": "cd34/capsule_231x87.jpg", "hero_capsule": "ef56/hero_capsule.jpg"},
                "screenshots": {"all_ages_screenshots": [{"filename": f"steam/apps/900001/ss_{i}.jpg?t=1", "ordinal": i} for i in range(9)]},
                "supported_languages": [{"elanguage": 0, "supported": True, "full_audio": True},
                                        {"elanguage": 2, "supported": True, "full_audio": False},
                                        {"elanguage": 5, "supported": False}],
                "trailers": {"highlights": [{"trailer_name": "x"}]}}
        kept = collect.steam_item(item)
        self.assertEqual(kept["platforms"], {"windows": True, "mac": True, "steamos_linux": False, "steam_deck_compat_category": 3})
        self.assertEqual(kept["categories"], {"supported_player_categoryids": [2, 1], "feature_categoryids": [22], "controller_categoryids": [28]})
        self.assertEqual(kept["assets"], {"header": "ab12/header.jpg", "small_capsule": "cd34/capsule_231x87.jpg"})
        self.assertEqual(kept["screenshots"], [f"ss_{i}.jpg" for i in range(collect.SHOTS)])    # the first ones, by name
        self.assertEqual(kept["languages"], [[0, 1], [2, 0]])                                    # the supported ones
        self.assertNotIn("trailers", kept)
        self.assertNotIn("supported_languages", kept)

    def test_steam_item_without_them(self):
        kept = collect.steam_item({"appid": 1, "success": 1, "name": "Old", "screenshots": {}, "supported_languages": []})
        self.assertEqual(kept, {"appid": 1, "success": 1, "name": "Old"})

    def test_steam_asks_for_them(self):
        import steam
        request = steam.request(["620"])
        for flag in ("include_platforms", "include_assets", "include_screenshots", "include_supported_languages"):
            self.assertIn(flag, request)
        self.assertLess(len(steam.request([str(i) for i in range(steam.BATCH)])), 8000)    # an address the API takes

    def test_gog_product(self):
        host = collect.GOG_IMAGES
        product = {"id": "1", "title": "Quiet Pond", "operatingSystems": ["windows", "linux"],
                   "features": [{"name": "Single-player", "slug": "single"}, {"name": "Cloud saves", "slug": "cloud_saves"}],
                   "ratings": [{"name": "pegiRating", "ageRating": "16"}, {"name": "esrbRating", "ageRating": 17}, {"name": "x"}],
                   "coverHorizontal": host + "aa.png", "coverVertical": host + "bb.jpg", "logo": host + "cc.png",
                   "screenshots": [host + f"{i}_{{formatter}}.jpg" for i in range(9)],
                   "price": {"finalMoney": {"amount": "3.99"}}}
        kept = collect.gog_product(product)
        self.assertEqual(kept["operatingSystems"], ["windows", "linux"])
        self.assertEqual(kept["features"], ["single", "cloud_saves"])
        self.assertEqual(kept["ratings"], [["pegiRating", "16"], ["esrbRating", "17"]])
        self.assertEqual(kept["pictures"], {"cover": "aa.png", "poster": "bb.jpg", "screenshots": [str(i) for i in range(collect.SHOTS)]})
        self.assertNotIn("price", kept)
        self.assertNotIn("logo", kept)
        self.assertEqual(collect.gog_product({"id": "2", "coverHorizontal": "https://elsewhere.example.org/x.png"}), {"id": "2"})

    def test_ms_product(self):
        host = collect.MS_IMAGES
        product = {"ProductId": "9ABC", "ProductKind": "Game",
                   "LocalizedProperties": [{"ProductTitle": "Quiet Pond", "ProductDescription": "long text", "Images": [
                       {"ImagePurpose": "Logo", "Uri": host + "logo"}, {"ImagePurpose": "BoxArt", "Uri": host + "box"},
                       {"ImagePurpose": "BoxArt", "Uri": host + "box2"}, {"ImagePurpose": "Poster", "Uri": host + "poster"}] +
                       [{"ImagePurpose": "Screenshot", "Uri": host + f"s{i}"} for i in range(9)] +
                       [{"ImagePurpose": "Screenshot", "Uri": "https://elsewhere.example.org/x"}]}],
                   "MarketProperties": [{"OriginalReleaseDate": "2020-01-01", "MinimumUserAge": 12,
                                         "ContentRatings": [{"RatingSystem": "PEGI", "RatingId": "PEGI:16", "RatingDescriptors": ["PEGI:Vio"]},
                                                            {"RatingSystem": "ESRB"}]}],
                   "Properties": {"Categories": ["Action & adventure"], "Attributes": [
                       {"Name": "XblOnlineCoop", "Minimum": 2, "Maximum": 8}, {"Name": "SinglePlayer", "Maximum": None},
                       {"Name": "XblPresence", "Maximum": None}]},
                   "DisplaySkuAvailabilities": [{"Sku": {"Properties": {"Packages": [
                       {"PlatformDependencies": [{"PlatformName": "Windows.Xbox"}, {"PlatformName": "Windows.Desktop"}]},
                       {"PlatformDependencies": [{"PlatformName": "Windows.Xbox"}]}]}}}]}
        kept = collect.ms_product(product)
        self.assertEqual(kept["MarketProperties"][0]["ContentRatings"], [{"RatingSystem": "PEGI", "RatingId": "PEGI:16"}])
        self.assertEqual(kept["Properties"]["Attributes"], [{"Name": "XblOnlineCoop", "Maximum": 8}, {"Name": "SinglePlayer"}])
        self.assertEqual(kept["Properties"]["Platforms"], ["Windows.Desktop", "Windows.Xbox"])
        images = kept["LocalizedProperties"][0]["Images"]
        self.assertEqual(images[:2], [["BoxArt", "box"], ["Poster", "poster"]])                  # one of each, no logo
        self.assertEqual([i[1] for i in images if i[0] == "Screenshot"], [f"s{i}" for i in range(collect.SHOTS)])
        self.assertNotIn("ProductDescription", kept["LocalizedProperties"][0])
        self.assertEqual(collect.ms_product({"ProductId": "9X"})["Properties"], {"Categories": []})


class NoPrices(unittest.TestCase):
    """Atlas keeps no price nor sale (2026-10-30): the stores' answers are
    kept without theirs and nothing is asked for them every day."""

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


if __name__ == "__main__":
    unittest.main()
