"""tools/igdb.py without the network: the games found by their slug, their
traits and hype, their popularity ranked, and what build.py makes of them."""
import datetime
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402
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
        with mock.patch.dict(os.environ, {"IGDB_CLIENT_ID": "", "IGDB_CLIENT_SECRET": ""}):
            self.assertEqual(build.read_igdb(), {"traits": {}, "popularity": {}, "hypes": {}, "ratings": {}})

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


if __name__ == "__main__":
    unittest.main()
