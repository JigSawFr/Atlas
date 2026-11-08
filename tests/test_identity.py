"""tools/identity.py: a game's ids on every store from several sources, a conflict never settled silently."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import identity  # noqa: E402


class StoreIds(unittest.TestCase):
    def test_platform_of_a_source_name(self):
        self.assertEqual(identity.platform_of("Steam"), "steam")
        self.assertEqual(identity.platform_of("GOG"), "gog")
        self.assertEqual(identity.platform_of("Epic Games Store"), "epic")
        self.assertEqual(identity.platform_of("Microsoft"), "xbox")
        self.assertIsNone(identity.platform_of("Twitch"))

    def test_store_id(self):
        self.assertEqual(identity.store_id("steam", "900010", ""), "900010")
        self.assertIsNone(identity.store_id("steam", "app/900010", ""))
        self.assertEqual(identity.store_id("gog", "1207658", "https://www.gog.com/en/game/amber_lantern"), "amber_lantern")
        self.assertEqual(identity.store_id("epic", "abc", "https://store.epicgames.com/en-US/p/amber-lantern"), "amber-lantern")
        self.assertEqual(identity.store_id("xbox", "", "https://www.xbox.com/en-US/games/store/amber-lantern/9zzzzzzzzzz1"), "9ZZZZZZZZZZ1")
        self.assertIsNone(identity.store_id("gog", "1207658", ""))      # a number is not GOG's slug
        self.assertIsNone(identity.store_id("xbox", "", "https://www.xbox.com/games"))

    def test_igdb_groups_drop_an_id_two_games_claim(self):
        items = [[1, "steam", "10"], [1, "gog", "g1"], [2, "steam", "10"], [2, "epic", "e2"], [3, "bad", "x"], ["x", "steam", "1"]]
        self.assertEqual(identity.igdb_groups(items), {1: {"gog": ["g1"]}, 2: {"epic": ["e2"]}})


class Combine(unittest.TestCase):
    def test_an_igdb_group_joins_the_item_that_owns_one_of_its_ids(self):
        games, report = identity.combine({"Q1": {"steam": ["10"]}}, {7: {"steam": ["10"], "gog": ["g1"]}}, {})
        self.assertEqual(games, {"Q1": {"steam": ["10"], "gog": ["g1"]}})
        self.assertEqual(report["joined"], 1)

    def test_a_group_Wikidata_does_not_know_gets_its_igdb_key(self):
        games, _ = identity.combine({}, {7: {"steam": ["10"], "gog": ["g1"]}, 8: {"steam": ["11"]}}, {})
        self.assertEqual(games, {"igdb:7": {"steam": ["10"], "gog": ["g1"]}})      # one id alone ties nothing

    def test_the_item_igdb_names_takes_its_ids(self):
        games, _ = identity.combine({"Q1": {"switch": ["0100A1B2C3D4E000"]}}, {7: {"steam": ["10"], "gog": ["g1"]}}, {"Q1": 7})
        self.assertEqual(games, {"Q1": {"switch": ["0100A1B2C3D4E000"], "steam": ["10"], "gog": ["g1"]}})

    def test_a_group_between_two_items_is_a_conflict_and_changes_nothing(self):
        wd = {"Q1": {"steam": ["10"]}, "Q2": {"gog": ["g1"]}}
        games, report = identity.combine(wd, {7: {"steam": ["10"], "gog": ["g1"]}}, {})
        self.assertEqual(games, wd)
        self.assertEqual(report["conflicts"], [[7, ["Q1", "Q2"]]])

    def test_igdb_naming_one_item_while_its_ids_are_another_is_a_conflict(self):
        wd = {"Q1": {"switch": ["0100A1B2C3D4E000"]}, "Q2": {"steam": ["10"]}}
        games, report = identity.combine(wd, {7: {"steam": ["10"], "gog": ["g1"]}}, {"Q1": 7})
        self.assertEqual(games, wd)
        self.assertEqual(report["conflicts"], [[7, ["Q1", "Q2"]]])

    def test_nothing_from_igdb_changes_nothing(self):
        wd = {"Q1": {"steam": ["10"]}}
        self.assertEqual(identity.combine(wd, {}, {})[0], wd)

    def test_ids_are_sorted_and_not_doubled(self):
        games, _ = identity.combine({"Q1": {"steam": ["10"]}}, {7: {"steam": ["10", "09"], "gog": ["g1"]}}, {})
        self.assertEqual(games["Q1"]["steam"], ["09", "10"])


class Qids(unittest.TestCase):
    def test_qid_to_igdb(self):
        rows = [{"tid": {"value": "http://www.wikidata.org/entity/Q1"}, "slug": {"value": "amber-lantern"}}]
        items = [{"slug": "amber-lantern", "id": 7}, {"slug": "other", "id": 8}, {"slug": "bad"}]
        self.assertEqual(identity.qid_to_igdb(rows, items), {"Q1": 7})


if __name__ == "__main__":
    unittest.main()


class FakeClient:
    def __init__(self):
        self.asked = []

    def query(self, endpoint, text):
        self.asked.append(endpoint)
        if endpoint == "external_game_sources":
            return [{"id": 1, "name": "Steam"}, {"id": 5, "name": "GOG"}, {"id": 9, "name": "Twitch"}]
        after = int(text.split("id > ")[1].split(" ")[0])
        rows = [{"id": 10, "game": 7, "uid": "10", "url": "", "external_game_source": 1},
                {"id": 11, "game": 7, "uid": "1", "url": "https://www.gog.com/game/amber_lantern", "external_game_source": 5},
                {"id": 12, "game": 8, "uid": "x", "url": "", "external_game_source": 1}]
        return [r for r in rows if r["id"] > after]


class Collected(unittest.TestCase):
    def test_read_external(self):
        import igdb
        client = FakeClient()
        self.assertEqual(igdb.read_external(client, identity.platform_of, identity.store_id),
                         [[7, "steam", "10"], [7, "gog", "amber_lantern"]])
        self.assertEqual(client.asked[0], "external_game_sources")

    def test_links_with_igdb(self):
        import links
        src = lambda name: {"igdb/external.json": {"items": [[7, "steam", "10"], [7, "gog", "g1"], [8, "steam", "11"], [8, "epic", "e8"]]}}.get(name, {})   # noqa: E731
        games = links.with_igdb({"Q5": {"steam": ["10"]}, "Q2": {"xbox": ["9ZZZZZZZZZZ1"]}}, src)
        self.assertEqual(list(games), ["Q2", "Q5", "igdb:8"])
        self.assertEqual(games["Q5"], {"steam": ["10"], "gog": ["g1"]})
        self.assertEqual(games["igdb:8"], {"steam": ["11"], "epic": ["e8"]})

    def test_links_without_igdb(self):
        import links
        games = {"Q5": {"steam": ["10"]}, "Q2": {"xbox": ["9ZZZZZZZZZZ1"]}}
        self.assertEqual(links.with_igdb(games, lambda name: {}), {"Q2": games["Q2"], "Q5": games["Q5"]})

    def test_a_newer_schema_of_the_source_counts_as_none(self):
        import common
        import tempfile, json
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "sources", "igdb"))
            with open(os.path.join(d, "sources", "igdb", "external.json"), "w") as f:
                json.dump({"schema": common.SOURCE_SCHEMA + 1, "items": [[7, "steam", "10"], [7, "gog", "g1"]]}, f)
            self.assertEqual(common.reader(d)("igdb/external.json"), {})
