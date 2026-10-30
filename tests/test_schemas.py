"""tools/schemas.py, tools/report.py and index.json's licences: fictional games only."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import index  # noqa: E402
import report  # noqa: E402
import schemas  # noqa: E402

A, B = "0100000000010000", "0100000000020000"


def put(base, name, body):
    path = os.path.join(base, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f)


class Schemas(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(schemas.kind_of("platforms/switch/popular.json"), "popular")
        self.assertEqual(schemas.kind_of("platforms/steam/prices/FR.json"), "prices")
        self.assertEqual(schemas.kind_of("sources/titledb/US/2.json"), "source")
        self.assertEqual(schemas.kind_of("schemas/x.schema.json"), None)
        self.assertEqual(schemas.schema_path("sources/titledb/US/2.json"), "schemas/sources/titledb/US.schema.json")
        self.assertEqual(schemas.schema_path("platforms/nes/games.json"), "schemas/platforms/nes/games.schema.json")

    def test_right_and_wrong(self):
        popular = {"schema": 1, "generated": "2026-10-30", "games": {A: [77, 21, 90]}}
        self.assertEqual(schemas.errors(popular, schemas.KINDS["popular"]), [])
        popular["games"][B] = [101, 0, 0]
        self.assertTrue(schemas.errors(popular, schemas.KINDS["popular"]))
        prices = {"schema": 1, "generated": "2026-10-30", "country": "FR", "games": {A: [19.99, 9.99, 20261101, 9.99, 20261030]}}
        self.assertEqual(schemas.errors(prices, schemas.KINDS["prices"]), [])
        prices["games"][A] = [19.99, "cheap", 0, 0, 0]
        self.assertTrue(schemas.errors(prices, schemas.KINDS["prices"]))
        games = {"schema": 1, "generated": "2026-10-30", "games": {"900010": {"name": "Amber Lantern", "tags": [19, 21],
                                                                          "developers": [["clan:1", "A studio"]]}}}
        self.assertEqual(schemas.errors(games, schemas.KINDS["games"]), [])

    def test_publish_puts_back(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "platforms/switch/popular.json", {"schema": 1, "generated": "2026-10-30", "games": {A: [1, 2]}})
            put(d, "links.json", {"schema": 1, "generated": "2026-10-30", "games": {"Q900001": {"switch": [A]}}})
            wrong = schemas.check(d)
            self.assertEqual(list(wrong), ["platforms/switch/popular.json"])
            schemas.put_back(d, "platforms/switch/popular.json")   # not on a branch: removed
            self.assertFalse(os.path.exists(os.path.join(d, "platforms/switch/popular.json")))
            schemas.write(d)
            self.assertTrue(os.path.exists(os.path.join(d, "schemas/links.schema.json")))


class Report(unittest.TestCase):
    def test_report(self):
        with tempfile.TemporaryDirectory() as d:
            put(d, "links.json", {"schema": 1, "games": {"Q900001": {"switch": [A], "steam": ["900010"]}}})
            put(d, "platforms/switch/games.json", {"schema": 1, "generated": "2026-10-30",
                                                   "games": {A: {"name": "Lantern Tale", "steam": {"app": 900010}}, B: {}}})
            put(d, "platforms/switch/popular.json", {"schema": 1, "generated": "2026-10-30", "games": {A: [1, 0, 0]}})
            put(d, "platforms/switch/prices/FR.json", {"schema": 1, "games": {A: [1, 0, 0, 1, 20261030]}})
            put(d, "sources/titledb/US.json", {"schema": 1, "generated": "2026-10-30", "games": {"1": {}, "2": {}}})
            put(d, "run/.runtimes/switch.json", {"seconds": 12.34})
            got = report.report(d, "build", [os.path.join(d, "run")])
            self.assertEqual(got["platforms"]["switch"], {"games": 2, "names": 1, "popular": 1, "linked": 0.5,
                                                          "priced": 0.5, "reviewed": 0.5, "countries": 1,
                                                          "generated": "2026-10-30"})
            self.assertEqual(got["sources"]["titledb"]["records"], 2)
            self.assertEqual(got["steps"], {"switch": 12.3})
            self.assertEqual(schemas.errors(got, schemas.KINDS["report"]), [])
            # A file of a later schema counts as none, and is left as it was.
            later = {"schema": 2, "generated": "2026-11-09", "games": {A: [1, 0, 0], B: [2, 0, 0]}}
            put(d, "platforms/switch/popular.json", later)
            self.assertEqual(report.report(d, "build", [])["platforms"]["switch"]["popular"], 0)
            with open(os.path.join(d, "platforms/switch/popular.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f), later)

    def test_kinds_known(self):
        # platforms.json's kinds, the 3DS's console among them, match its schema.
        import datetime
        import platforms
        body = platforms.registry(datetime.date(2026, 10, 30))
        self.assertEqual(schemas.errors(body, schemas.KINDS["platforms"]), [])
        self.assertEqual({e["kind"] for e in body["platforms"].values()}, {"store", "console", "retro"})


class Licences(unittest.TestCase):
    def test_terms(self):
        self.assertEqual(index.terms({"source": "Wikidata (P400), Wikimedia pageviews (en.wikipedia)"}),
                         ("CC0-1.0", "Wikidata; Wikimedia pageviews"))
        self.assertEqual(index.terms({"source": "IGDB (api.igdb.com: games)", "license": "IGDB's API terms"}),
                         ("IGDB's API terms", "Data from IGDB.com"))
        self.assertEqual(index.terms({}), index.OWN)


if __name__ == "__main__":
    unittest.main()
