"""tools/igdb.py without the network: the games found by their slug, their
traits and hype, their popularity ranked, and what build.py makes of them."""
import datetime
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402
import collect  # noqa: E402
import common  # noqa: E402
import features  # noqa: E402
import igdb  # noqa: E402

A, B, C = "0100000000010000", "0100000000020000", "0100000000030000"


def slug_row(tid, slug):
    return {"tid": {"value": tid}, "slug": {"value": slug}}


class Stub:
    """A client answering each endpoint from a list, the queries kept."""

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def query(self, endpoint, text):
        self.asked.append((endpoint, text))
        return self.answers.get(endpoint, [])


class Igdb(unittest.TestCase):
    def test_slugs(self):
        rows = [slug_row(A, "Lantern-Tale"), slug_row(B, "lantern-tale"), slug_row(A, "lantern-tale"),
                slug_row(C, "bad slug"), slug_row("0100000000010800", "an-update")]
        self.assertEqual(igdb.slugs(rows, build.base_id), {"lantern-tale": [A, B]})

    def test_queries(self):
        self.assertIn('where slug = ("a","b")', igdb.games_query(["a", "b"]))
        self.assertIn("themes.name", igdb.games_query(["a"]))
        q = igdb.popularity_query([7, 8])
        self.assertIn("where game_id = (7,8) & popularity_type = (1,2,3,4)", q)

    def test_read_games(self):
        records = [
            {"id": 7, "slug": "lantern-tale", "hypes": 40, "themes": [{"id": 1, "name": "Fantasy"}],
             "keywords": [{"id": k, "name": f"k{k}"} for k in range(20)], "player_perspectives": [{"id": 2}]},
            {"id": 8, "slug": "unknown"},
            {"slug": "lantern-tale"},
        ]
        ids, traits, hypes = igdb.read_games(records, {"lantern-tale": [A, B]})
        self.assertEqual(ids, {7: [A, B]})
        self.assertEqual(traits[A]["themes"], [["1", "Fantasy"]])
        self.assertEqual(len(traits[A]["keywords"]), igdb.MAX_TRAITS)
        self.assertEqual(traits[B]["perspectives"], [["2", ""]])
        self.assertEqual(hypes, {A: 40, B: 40})

    def test_ratings(self):
        records = [{"id": 7, "slug": "lantern-tale", "rating": 82.6, "rating_count": 1240},
                   {"id": 8, "slug": "quiet-pond", "rating": 70.0, "rating_count": 0},
                   {"id": 9, "slug": "kart-cup", "rating": "x", "rating_count": 3}]
        got = igdb.read_ratings(records, {"lantern-tale": [A, B], "quiet-pond": [C], "kart-cup": [C]})
        self.assertEqual(got, {A: [83, 1240], B: [83, 1240]})
        self.assertIn("rating_count", igdb.games_query(["a"]))

    def test_popularity(self):
        ids = {7: [A], 8: [B], 9: [C]}
        records = [
            {"game_id": 7, "popularity_type": 1, "value": 0.9}, {"game_id": 8, "popularity_type": 1, "value": 0.1},
            {"game_id": 7, "popularity_type": 2, "value": 0.2}, {"game_id": 8, "popularity_type": 2, "value": 0.5},
            {"game_id": 9, "popularity_type": 6, "value": 99}, {"game_id": 10, "popularity_type": 1, "value": 1},
            {"game_id": 9, "popularity_type": 3, "value": "x"},
        ]
        got = igdb.read_popularity(records, ids)
        self.assertEqual(got, {A: 0.75, B: 0.75})

    def test_read(self):
        stub = Stub({"games": [{"id": 7, "slug": "lantern-tale", "themes": [{"id": 1, "name": "Fantasy"}]}],
                     "popularity_primitives": [{"game_id": 7, "popularity_type": 1, "value": 0.5}]})
        with mock.patch.object(igdb.time, "sleep"):
            got = igdb.read(stub, {"lantern-tale": [A]})
        self.assertEqual(got["popularity"], {A: 1.0})
        self.assertEqual(got["traits"][A]["themes"], [["1", "Fantasy"]])
        self.assertEqual([e for e, _ in stub.asked], ["games", "popularity_primitives"])

    def test_without_keys(self):
        # Nothing collected from IGDB (no keys): nothing from it.
        self.assertEqual(build.igdb_found(lambda name: {}), {"traits": {}, "popularity": {}, "hypes": {}, "ratings": {}})

    def test_build_uses_it(self):
        known = {A: (10, None), B: (10, None)}
        table = build.popular(known, {}, {}, {}, {A: 1.0})
        self.assertGreater(table[A][0], table[B][0])
        titles = {"x": {"id": A, "releaseDate": 20261201, "name": "Lantern Tale"},
                  "y": {"id": B, "releaseDate": 20261202, "name": "Quiet Pond"}}
        got = build.upcoming(titles, datetime.date(2026, 11, 1), hypes={A: 12})
        self.assertEqual(got, {A: [20261201, "Lantern Tale", 12], B: [20261202, "Quiet Pond"]})

    def test_similar_weighs_them(self):
        # A shared theme makes two games alike; a shared perspective alone does not.
        traits = {A: {"themes": [["1", "Fantasy"]]}, B: {"themes": [["1", "Fantasy"]]},
                  C: {"perspectives": [["2", "Side view"]]}, "0100000000040000": {"perspectives": [["2", "Side view"]]}}
        got = features.similar(traits)
        self.assertEqual(got[A][0][0], B)
        self.assertNotIn(C, got)



# IGDB's answers for two fictional games, as its API gives them.
LANTERN = {"id": 9001, "slug": "lantern-tale", "rating": 81.6, "rating_count": 40,
           "genres": [{"id": 12, "name": "Role-playing (RPG)"}, {"id": 31, "name": "Adventure"}],
           "collections": [{"id": 77, "name": "Lantern"}], "franchises": [{"id": 5, "name": "Lantern Saga"}],
           "game_modes": [{"id": 1, "name": "Single player"}],
           "involved_companies": [{"id": 1, "company": {"id": 300, "name": "Amber Works"}, "developer": True,
                                   "publisher": False},
                                  {"id": 2, "company": {"id": 301, "name": "Reed Games"}, "developer": False,
                                   "publisher": True}]}
POND = {"id": 9002, "slug": "quiet-pond", "rating": 55, "rating_count": 0, "genres": [{"id": 13}],
        "involved_companies": [{"id": 3, "company": {"id": 302}, "developer": True}]}


def qid_row(qid, slug):
    """A row of sources/wikidata/others-igdb.json, as kept ({variable: value})."""
    return {"tid": f"http://www.wikidata.org/entity/{qid}", "slug": slug}


class SlugStub(Stub):
    """A client answering each games query with the records of the slugs it names."""

    def __init__(self, records):
        super().__init__({})
        self.records = records

    def query(self, endpoint, text):
        self.asked.append((endpoint, text))
        if endpoint != "games":
            return []
        wanted = json.loads("[" + text.split("where slug = (")[1].split(")")[0] + "]")
        return [r for r in self.records if r["slug"] in wanted]


class Others(unittest.TestCase):
    def test_query(self):
        text = igdb.others_query(["Q203597", "Q5014725"])
        self.assertIn("VALUES ?platform { wd:Q203597 wd:Q5014725 }", text)
        self.assertIn("wdt:P5794", text)
        fields = igdb.others_games_query(["lantern-tale"])
        self.assertIn('where slug = ("lantern-tale")', fields)
        self.assertIn("involved_companies.company.name", fields)

    def test_read_others(self):
        got = igdb.read_others([LANTERN, POND, {"slug": "unknown"}], {"lantern-tale": ["Q1", "Q2"], "quiet-pond": ["Q3"]})
        self.assertEqual(got["Q1"], {
            "series": [["igdb:collection:77", "Lantern"], ["igdb:franchise:5", "Lantern Saga"]],
            "developers": [["igdb:company:300", "Amber Works"]], "publishers": [["igdb:company:301", "Reed Games"]],
            "genres": [["igdb:genre:12", "Role-playing (RPG)"], ["igdb:genre:31", "Adventure"]],
            "modes": [["igdb:mode:1", "Single player"]], "igdb_rating": [82, 40]})
        self.assertEqual(got["Q2"], got["Q1"])
        self.assertNotIn("Q3", got)   # nothing named, no one rated it: nothing

    def test_complete(self):
        found = igdb.read_others([LANTERN], {"lantern-tale": ["Q1"]})
        games = {"Q1": {"name": "Lantern Tale", "genres": [["Q900", "fantasy video game"]]},   # by its key
                 "CTR-LNT": {"name": "Lantern Tale", "qid": "Q1"},                              # by its "qid"
                 "CTR-QPD": {"name": "Quiet Pond"}}
        self.assertEqual(igdb.complete(games, found), 2)
        self.assertEqual(games["Q1"]["genres"], [["Q900", "fantasy video game"]])   # Wikidata's kept
        self.assertEqual(games["Q1"]["developers"], [["igdb:company:300", "Amber Works"]])
        self.assertEqual(games["CTR-LNT"]["igdb_rating"], [82, 40])
        self.assertEqual(games["CTR-QPD"], {"name": "Quiet Pond"})
        self.assertEqual(igdb.complete(games, {}), 0)

    def test_others_of_sources(self):
        sources = {"wikidata/others-igdb.json": {"rows": [qid_row("Q1", "lantern-tale")]},
                   "igdb/others.json": {"items": [LANTERN]}}
        self.assertEqual(igdb.others(lambda name: sources.get(name, {}))["Q1"]["igdb_rating"], [82, 40])
        self.assertEqual(igdb.others(lambda name: {}), {})   # no keys, nothing collected: nothing

    def write(self, root, name, body):
        path = os.path.join(root, common.SOURCES, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"schema": common.SOURCE_SCHEMA, **body}, f)

    def test_collect(self):
        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as last, \
                tempfile.TemporaryDirectory() as fresh, mock.patch.dict(os.environ, {}, clear=True):
            self.write(fresh, "wikidata/switch-igdb.json", {"rows": []})
            self.write(fresh, "wikidata/others-igdb.json", {"rows": [qid_row("Q1", "lantern-tale"),
                                                                     qid_row("Q3", "quiet-pond")]})
            old = dict(POND, rating=10, rating_count=3)
            self.write(last, "igdb/others.json", {"items": [old, {"slug": "gone-game"}]})
            stub = SlugStub([LANTERN, POND])
            day = datetime.date(2026, 11, 2)
            week = day.isocalendar()[1]
            with mock.patch.object(collect.zlib, "crc32", lambda b: week + 1):   # quiet-pond not due again
                collect.collect_igdb("weekly", out, last, [fresh], day, [], client=stub)
            with open(os.path.join(out, common.SOURCES, "igdb/others.json")) as f:
                items = json.load(f)["items"]
        self.assertEqual(items, [LANTERN, old])   # the new one asked, the known one kept, the gone one dropped
        others = [t for e, t in stub.asked if e == "games" and "involved_companies" in t]
        self.assertEqual(len(others), 1)
        self.assertIn('"lantern-tale"', others[0])
        self.assertNotIn("quiet-pond", others[0])

    def test_collect_without_keys(self):
        with tempfile.TemporaryDirectory() as out, mock.patch.dict(os.environ, {}, clear=True):
            collect.collect_igdb("weekly", out, out, [], datetime.date(2026, 11, 2), [])
            self.assertEqual(os.listdir(out), [])   # nothing asked, nothing written, no error

if __name__ == "__main__":
    unittest.main()
