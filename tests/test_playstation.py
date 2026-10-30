"""tools/playstation.py: the PS4's and PS5's files from Wikidata's rows
(fictional games), and links.json's ps4 and ps5."""
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import common  # noqa: E402
import playstation  # noqa: E402
import schemas  # noqa: E402

E = "http://www.wikidata.org/entity/"
PS4, PS5 = "Q5014725", "Q63184502"
TODAY = datetime.date(2026, 10, 30)


def game(qid, machine, name, links=10, article=None):
    b = {"tid": E + qid, "platform": E + machine, "links": str(links), "name": name}
    if article:
        b["article"] = f"https://en.wikipedia.org/wiki/{article}"
    return b


def date(qid, value, precision=11, on=None):
    b = {"tid": E + qid, "date": value, "precision": str(precision)}
    if on:
        b["on"] = E + on
    return b


def trait(qid, prop, value, label):
    return {"tid": E + qid, "prop": "http://www.wikidata.org/prop/direct/" + prop, "value": E + value,
            "valueLabel": label}


def link(qid, prop, value):
    return {"item": E + qid, "prop": "http://www.wikidata.org/prop/direct/" + prop, "v": value}


SOURCES = {
    "wikidata/playstation.json": {"rows": [
        game("Q900001", PS4, "Lantern Tale", 40, "Lantern_Tale"), game("Q900001", PS5, "Lantern Tale", 40, "Lantern_Tale"),
        game("Q900002", PS4, "Quiet Pond", 5), game("Q900003", PS5, "Ember Vale", 20, "Ember_Vale")]},
    "wikidata/playstation-traits.json": {"rows": [
        trait("Q900001", "P179", "Q910001", "Lantern saga"), trait("Q900003", "P179", "Q910001", "Lantern saga"),
        trait("Q900001", "P136", "Q910002", "puzzle"), trait("Q900003", "P404", "Q910003", "single-player"),
        trait("Q900002", "P31", "Q7889", "video game")]},
    "wikidata/playstation-dates.json": {"rows": [
        date("Q900001", "2019-03-14T00:00:00Z"), date("Q900001", "2020-11-12T00:00:00Z", on=PS5),
        date("Q900001", "2018-01-01T00:00:00Z", precision=9),              # a year: not a day
        date("Q900002", "2017-06-02T00:00:00Z", on="Q19610114"),            # the Switch's, not the PS4's
        date("Q900003", "2027-02-20T00:00:00Z")]},
    "wikidata/links.json": {"rows": [
        link("Q900001", "P12332", "10900001"), link("Q900001", "P5944", "UP0001-CUSA00001_00-LANTERNTALE00000"),
        link("Q900001", "P5971", "EP0001-PPSA00001_00-LANTERNTALE00000"), link("Q900001", "P1733", "900010"),
        link("Q900003", "P11072", "0100000000030000")]},
    "wikipedia/monthly.json": {"pages": {"Lantern_Tale": [900, 1000, 3000], "Ember_Vale": [10, 10, 20]}},
}
src = lambda name: SOURCES.get(name, {})   # noqa: E731


class Machines(unittest.TestCase):
    def test_games(self):
        got = playstation.machines_of(src)
        self.assertEqual(sorted(got["ps4"]), ["Q900001", "Q900002"])
        self.assertEqual(sorted(got["ps5"]), ["Q900001", "Q900003"])
        lantern = got["ps4"]["Q900001"]
        self.assertEqual(lantern["name"], "Lantern Tale")
        self.assertEqual(lantern["release"], 20190314)
        self.assertEqual(got["ps5"]["Q900001"]["release"], 20190314)   # the earliest day said for every machine
        self.assertEqual(lantern["ps"], ["10900001"])
        self.assertEqual(lantern["ps_product"], ["UP0001-CUSA00001_00-LANTERNTALE00000"])   # CUSA: the PS4's
        self.assertEqual(got["ps5"]["Q900001"]["ps_product"], ["EP0001-PPSA00001_00-LANTERNTALE00000"])
        self.assertEqual(lantern["series"], [["Q910001", "Lantern saga"]])
        self.assertEqual(lantern["genres"], [["Q910002", "puzzle"]])
        self.assertNotIn("release", got["ps4"]["Q900002"])   # only another machine's date
        self.assertEqual(got["ps4"]["Q900002"], {"name": "Quiet Pond"})   # P31 is no trait

    def test_releases(self):
        rows = common.bindings(SOURCES["wikidata/playstation-dates.json"]["rows"])
        self.assertEqual(playstation.releases(rows, PS5), {"Q900001": 20190314, "Q900003": 20270220})
        self.assertEqual(playstation.releases([{"tid": {"value": E + "Q1"}, "date": {"value": "nonsense"},
                                                "precision": {"value": "x"}}], PS4), {})

    def test_upcoming(self):
        games = {"Q1": {"name": "Soon", "release": 20270101}, "Q2": {"name": "Out", "release": 20261030},
                 "Q3": {"name": "Far", "release": 20290101}, "Q4": {"name": "Unknown"}}
        self.assertEqual(playstation.upcoming(games, TODAY), {"Q1": [20270101, "Soon"]})

    def test_files(self):
        with tempfile.TemporaryDirectory() as out:
            playstation.consolidate(src, out, None, TODAY)
            def read(p):
                with open(os.path.join(out, "platforms", p)) as f:
                    return json.load(f)
            ps5 = {k: read(f"ps5/{k}.json") for k in ("games", "popular", "similar", "upcoming")}
            for name, body in ps5.items():
                self.assertEqual(body["platform"], "ps5")
                self.assertEqual(body["schema"], common.SCHEMA)
                self.assertEqual(schemas.errors(body, schemas.KINDS[name]), [], name)
            self.assertEqual(ps5["upcoming"]["games"], {"Q900003": [20270220, "Ember Vale"]})
            self.assertGreater(ps5["popular"]["games"]["Q900001"][0], ps5["popular"]["games"]["Q900003"][0])
            self.assertEqual(ps5["similar"]["games"]["Q900001"][0][0], "Q900003")   # the same series
            self.assertNotIn("PlayStation Store", ps5["games"]["source"])   # Wikidata's ids, nothing of the store
            self.assertEqual(read("ps4/upcoming.json")["games"], {})

    def test_by_game(self):
        self.assertEqual(playstation.machines_by_game(src), {"Q900001": ["ps4", "ps5"], "Q900002": ["ps4"],
                                                              "Q900003": ["ps5"]})


class Links(unittest.TestCase):
    def test_ps4_ps5(self):
        import links
        with tempfile.TemporaryDirectory() as sources, tempfile.TemporaryDirectory() as out:
            for name, body in SOURCES.items():
                path = os.path.join(sources, common.SOURCES, name)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    json.dump({"schema": common.SOURCE_SCHEMA, **body}, f)
            argv = sys.argv
            sys.argv = ["links.py", out, os.path.join(out, "none"), sources]
            try:
                links.main()
            finally:
                sys.argv = argv
            with open(os.path.join(out, "links.json")) as f:
                games = json.load(f)["games"]
        self.assertEqual(games["Q900001"]["ps4"], ["Q900001"])
        self.assertEqual(games["Q900001"]["ps5"], ["Q900001"])
        self.assertEqual(games["Q900003"]["ps5"], ["Q900003"])   # tied to its Switch title id
        self.assertNotIn("Q900002", games)                         # on the PS4 alone, tied to nothing


if __name__ == "__main__":
    unittest.main()
