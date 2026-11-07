import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import site_data  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def put(base, path, body):
    path = os.path.join(base, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f)


def sample(base):
    """A data branch of made-up games: two Switch games, three Steam ones."""
    put(base, "platforms/switch/popular.json", {"schema": 1, "generated": "2026-11-02",
                                      "games": {"0100A1B2C3D4E000": [80, 12, 90], "0100F0F0F0F0F000": [20, 0, 0]}})
    put(base, "platforms/switch/games.json", {"schema": 1, "games": {"0100A1B2C3D4E000": {
        "series": [["Q900100", "Amber Saga"]], "developers": [["Q900200", "Tiny Owl"]], "steam": {"app": 900010, "owners": 5000}}}})
    put(base, "platforms/switch/upcoming.json", {"schema": 1, "games": {"0100C0C0C0C0C000": [20261204, "Frost Harbor"]}})
    put(base, "platforms/switch/similar.json", {"schema": 1, "games": {"0100A1B2C3D4E000": [["0100C0C0C0C0C000", 55]]}})
    put(base, "platforms/switch/editions.json", {"schema": 1, "games": {"0100F0F0F0F0F000": "0100A1B2C3D4E000"}})
    put(base, "platforms/steam/popular.json", {"schema": 1, "generated": "2026-11-02",
                                     "games": {"900010": [70, 5, 0], "900020": [40, -3, 0], "900030": [10, 0, 0]}})
    put(base, "platforms/steam/games.json", {"schema": 1, "tags": {"19": "Action"},
                                   "games": {"900010": {"name": "Amber Lantern", "qid": "Q900001", "tags": [19]},
                                             "900020": {"name": "Moss & Märchen"}}})
    put(base, "links.json", {"schema": 1, "games": {"Q900001": {"switch": ["0100A1B2C3D4E000"], "steam": ["900010"],
                                                                "gog": ["amber_lantern"]}}})
    put(base, "index.json", {"schema": 1, "files": {"platforms/switch/popular.json": {"generated": "2026-11-02", "bytes": 120, "sha256": "0" * 16},
                                                    "platforms/switch/games.json": {"generated": "2026-11-02", "bytes": 90, "sha256": "1" * 16}}})


class SiteData(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = os.path.join(self.tmp.name, "data")
        self.out = os.path.join(self.tmp.name, "out")
        sample(self.data)
        self.summary = site_data.build(self.data, self.out)

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, path):
        with open(os.path.join(self.out, path), encoding="utf-8") as f:
            return json.load(f)

    def sheet(self, platform, gid):
        lists = self.read(f"x/{platform}/lists.json")
        return self.read(f"x/{platform}/g/{site_data.shard(gid, lists['shards'])}.json")[gid]

    def test_platforms_and_lists(self):
        self.assertEqual(sorted(self.summary), ["steam", "switch"])
        lists = self.read("x/steam/lists.json")
        self.assertEqual([g[0] for g in lists["popular"]], ["900010", "900020", "900030"])
        self.assertEqual([g[0] for g in lists["trending"]], ["900010"])
        self.assertEqual(lists["popular"][0][1], "Amber Lantern")
        self.assertEqual(self.read("x/switch/lists.json")["upcoming"][0][:3], ["0100C0C0C0C0C000", "Frost Harbor", 20261204])

    def test_sheet(self):
        s = self.sheet("switch", "0100A1B2C3D4E000")
        self.assertEqual(s["popular"], [80, 12, 90])
        self.assertEqual(s["traits"]["series"], ["Amber Saga"])
        self.assertEqual(s["similar"], [["0100C0C0C0C0C000", "Frost Harbor", 55]])
        self.assertEqual(s["editions"], [["0100F0F0F0F0F000", ""]])
        self.assertEqual(s["links"]["steam"], ["900010"])
        self.assertEqual(s["qid"], "Q900001")
        self.assertEqual(self.sheet("switch", "0100F0F0F0F0F000")["edition_of"], ["0100A1B2C3D4E000", ""])
        self.assertEqual(self.sheet("steam", "900010")["traits"], {"genres": ["action"]})    # the tag "Action" is the genre

    def unified(self, qid):
        meta = self.read("x/u/meta.json")
        return self.read(f"x/u/{site_data.shard(qid, meta['shards'])}.json")[qid]

    def test_unified_sheet(self):
        u = self.unified("Q900001")
        self.assertEqual(u["qid"], "Q900001")
        self.assertEqual(u["name"], "Amber Lantern")
        self.assertEqual([e["p"] for e in u["platforms"]], ["steam", "switch"])
        self.assertEqual(u["platforms"][0]["popular"], [70, 5, 0])
        self.assertEqual(u["platforms"][1]["popular"], [80, 12, 90])
        self.assertEqual(u["platforms"][1]["steam"]["app"], 900010)
        self.assertEqual(u["traits"], {"genres": ["action"], "series": ["Amber Saga"], "developers": ["Tiny Owl"]})
        self.assertEqual(u["similar"], [["switch", "0100C0C0C0C0C000", "Frost Harbor", 55]])
        self.assertEqual(u["links"], {"gog": ["amber_lantern"]})        # the stores the data has no platform for
        self.assertTrue(self.sheet("switch", "0100A1B2C3D4E000")["unified"])
        self.assertTrue(self.sheet("steam", "900010")["unified"])
        self.assertNotIn("unified", self.sheet("steam", "900020"))      # one platform, no unified sheet
        self.assertEqual(self.read("x/u/meta.json")["games"], 1)

    def test_the_stores_sources_give_the_sheet_its_technical_part(self):
        put(self.data, "sources/steam-store/apps.json", {"schema": 1, "games": {
            "900010": {"appid": 900010, "platforms": {"windows": True, "steam_deck_compat_category": 2}, "languages": [[0, 1], [2, 0]]},
            "900020": {"appid": 900020, "name": "says nothing"}}})
        site_data.build(self.data, self.out)
        self.assertEqual(self.sheet("steam", "900010")["tech"], {"os": ["windows"], "deck": 2, "langs": ["en", "fr"], "voices": ["en"]})
        self.assertNotIn("tech", self.sheet("steam", "900020"))
        self.assertNotIn("tech", self.sheet("switch", "0100A1B2C3D4E000"))
        steam = [e for e in self.unified("Q900001")["platforms"] if e["p"] == "steam"][0]
        self.assertEqual(steam["tech"]["deck"], 2)                      # the sheet of all its platforms keeps each one's

    def test_a_company_is_one_whatever_its_legal_form(self):
        put(self.data, "platforms/steam/games.json", {"schema": 1, "games": {
            "900010": {"name": "A", "developers": [["Q1", "Sega Corporation"]], "publishers": [["Q2", "Sega"]]},
            "900020": {"name": "B", "developers": [["Q1", "SEGA"]], "publishers": [["Q2", "Sega Co., Ltd."]]},
            "900030": {"name": "C", "developers": [["Q1", "Sega"]], "publishers": [["Q2", "Sega"]]}}})
        site_data.build(self.data, self.out)
        facets = self.facets("steam")["facets"]
        self.assertEqual(facets["developers"], [["Sega", 3]])        # the spelling most games use
        self.assertEqual(facets["publishers"], [["Sega", 3]])
        self.assertEqual(self.sheet("steam", "900010")["traits"]["developers"], ["Sega"])

    def test_wikidata_facts_reach_the_sheets(self):
        put(self.data, "sources/wikidata/facts-website.json", {"schema": 1, "rows": [{"qid": "Q900001", "v": "https://example.org/amber"}]})
        put(self.data, "sources/wikidata/facts-age.json", {"schema": 1, "rows": [{"qid": "Q900001", "p": "P908", "label": "PEGI 7"}]})
        site_data.build(self.data, self.out)
        want = {"web": "https://example.org/amber", "age": [["PEGI", "7"]]}
        self.assertEqual(self.sheet("steam", "900010")["wd"], want)
        self.assertEqual(self.sheet("switch", "0100A1B2C3D4E000")["wd"], want)
        self.assertEqual(self.unified("Q900001")["wd"], want)                      # once, for the game
        self.assertNotIn("wd", self.unified("Q900001")["platforms"][0])
        self.assertNotIn("wd", self.sheet("steam", "900020"))

    def test_unify_spellings_and_order(self):
        steam = ("1", {"name": "Amber", "traits": {"developers": ["INNERSLOTH"], "genres": ["action", "puzzle"]}})
        switch = ("2", {"name": "Amber", "traits": {"developers": ["Innersloth", "Tiny Owl"], "genres": ["puzzle"]},
                        "links": {"steam": ["1"], "gog": ["amber"]}})
        u = site_data.unify({"switch": switch, "steam": steam}, {})
        self.assertEqual([e["p"] for e in u["platforms"]], ["steam", "switch"])        # steam first
        self.assertEqual(u["traits"]["developers"], ["INNERSLOTH", "Tiny Owl"])        # one spelling, the first platform's
        self.assertEqual(u["traits"]["genres"], ["puzzle", "action"])                   # on both platforms first
        self.assertEqual(u["links"], {"gog": ["amber"]})

    def facets(self, platform):
        return self.read(f"x/{platform}/facets.json")

    def page(self, platform, n=0):
        return self.read(f"x/{platform}/browse/{n}.json")

    def rows_of(self, platform, kind, value, n=0):
        """The rows of page n that have a facet value, the gaps added up."""
        number = [v for v, _ in self.facets(platform)["facets"][kind]].index(value)
        for found, gaps in self.page(platform, n)["facets"].get(kind, []):
            if found == number:
                at, last = [], 0
                for gap in gaps:
                    last += gap
                    at.append(last)
                return at
        return []

    def steam_games(self):
        put(self.data, "platforms/steam/games.json", {"schema": 1, "tags": {"19": "Action", "21": "Rare", "22": "Great Soundtrack", "23": "Singleplayer"}, "games": {
            "900010": {"name": "Amber Lantern™", "tags": [19, 21, 22, 23], "release": 20240115, "genres": [["Q1", "Puzzle"], ["Q1", "Puzzle"]],
                       "developers": [["Q5", "SEGA"]], "something_new": {"a": 1}},
            "900020": {"name": "Moss & Märchen", "tags": [19, 22], "release": 20240820, "developers": [["Q6", "Sega"]]},
            "900030": {"name": "Old Stone", "tags": [19, 22, 23], "release": 19991231, "developers": [["Q6", "Sega"]]}}})

    def test_browse(self):
        self.steam_games()
        summary = site_data.build(self.data, self.out)
        page = self.page("steam")
        self.assertEqual([r[:2] for r in page["games"]], [["900010", "Amber Lantern"], ["900020", "Moss & Märchen"], ["900030", "Old Stone"]])
        self.assertEqual(page["games"][0], ["900010", "Amber Lantern", 70, 5, 0, 2024])      # no trademark sign
        facets = self.facets("steam")
        self.assertEqual((facets["pages"], facets["games"]), (1, 3))
        self.assertEqual(facets["facets"]["genres"], [["action", 3]])                        # the tag is the genre; "puzzle" has one game
        self.assertEqual(facets["facets"]["modes"], [["single", 2]])                         # "Singleplayer" is the mode
        self.assertEqual(facets["facets"]["tags"], [["Great Soundtrack", 3]])                # "Rare" has one game only
        self.assertEqual(facets["facets"]["developers"], [["Sega", 3]])                      # "SEGA" is "Sega"
        self.assertEqual(facets["facets"]["year"], [["2024", 2]])                            # 1999 has one game
        self.assertEqual(self.rows_of("steam", "genres", "action"), [0, 1, 2])
        self.assertEqual(self.rows_of("steam", "modes", "single"), [0, 2])
        self.assertEqual(self.rows_of("steam", "year", "2024"), [0, 1])
        self.assertEqual((summary["steam"]["browse"], summary["steam"]["pages"]), (3, 1))

    def test_the_tags_the_taxonomy_names_and_a_genre_in_its_parents(self):
        put(self.data, "platforms/steam/games.json", {"schema": 1, "tags": {"1": "Pixel Graphics", "2": "Cozy", "3": "Indie", "4": "Violent"}, "games": {
            "900010": {"name": "A", "tags": [1, 2, 3], "genres": [["Q1", "platform game"]]},
            "900020": {"name": "B", "tags": [1, 3, 4], "genres": [["Q1", "platform game"], ["Q2", "role-playing video game"]]}}})
        site_data.build(self.data, self.out)
        facets = self.facets("steam")["facets"]
        self.assertEqual(facets["styles"], [["pixel_art", 2]])
        self.assertEqual(facets["access"], [["indie", 2]])
        self.assertNotIn("tags", facets)                                          # none left that no notion names
        genres = dict(facets["genres"])
        self.assertEqual((genres["platformer"], genres["action"]), (2, 2))        # a platformer is an action game too
        self.assertNotIn("rpg", genres)                                           # one game only
        self.assertEqual(self.sheet("steam", "900020")["traits"]["genres"], ["platformer", "rpg"])     # the sheet says what it is
        self.assertEqual(self.sheet("steam", "900010")["traits"]["moods"], ["cozy"])

    def test_sheet_normalized(self):
        self.steam_games()
        site_data.build(self.data, self.out)
        sheet = self.sheet("steam", "900010")
        self.assertEqual(sheet["name"], "Amber Lantern")
        self.assertEqual(sheet["traits"], {"genres": ["puzzle", "action"], "modes": ["single"],
                                           "developers": ["Sega"], "tags": ["Rare", "Great Soundtrack"]})

    def test_browse_pages(self):
        self.steam_games()
        site_data.PAGE = 2
        try:
            site_data.build(self.data, self.out)
        finally:
            site_data.PAGE = 5000
        facets = self.facets("steam")
        self.assertEqual((facets["pages"], facets["page"], facets["games"]), (2, 2, 3))
        self.assertEqual([len(self.page("steam", n)["games"]) for n in (0, 1)], [2, 1])
        self.assertEqual(self.rows_of("steam", "genres", "action", 0), [0, 1])
        self.assertEqual(self.rows_of("steam", "genres", "action", 1), [0])                  # numbered in its page
        self.assertEqual(self.rows_of("steam", "year", "2024", 1), [])
        self.assertEqual(self.page("steam", 1)["games"][0][1], "Old Stone")
        import check_site
        from pathlib import Path
        site = Path(self.out)
        self.assertEqual(check_site.browse_errors(site / "x" / "steam", site), [])

    def test_browse_without_traits(self):
        self.assertEqual(self.facets("switch")["facets"], {})
        self.assertEqual((self.facets("switch")["pages"], self.facets("switch")["games"]), (0, 0))   # no Switch game of the sample has a name
        self.assertEqual(os.listdir(os.path.join(self.out, "x", "switch", "browse")), [])

    def test_browse_check(self):
        import check_site
        from pathlib import Path
        self.steam_games()
        site_data.build(self.data, self.out)
        site = Path(self.out)
        folder = site / "x" / "steam"
        self.assertEqual(check_site.browse_errors(folder, site), [])
        page = self.page("steam")
        page["facets"]["genres"] = [[0, [1, 9]], [7, [0]]]
        put(self.out, "x/steam/browse/0.json", page)
        errors = check_site.browse_errors(folder, site)
        self.assertEqual(len([e for e in errors if "points at nothing" in e]), 2)
        self.assertTrue(any("adds up" in e for e in errors))
        os.remove(folder / "browse" / "0.json")
        self.assertTrue(any("0.json" in e for e in check_site.browse_errors(folder, site)))
        self.assertEqual(len(check_site.browse_errors(site / "x" / "gog", site)), 1)

    def test_no_prices(self):
        # A prices/ folder or a history/ left on the data branch (until the one-time cleanup) is not read.
        put(self.data, "platforms/switch/prices/FR.json", {"schema": 1, "country": "FR", "currency": "EUR",
                                                           "games": {"0100A1B2C3D4E000": [39.99, 19.99, 0, 19.99, 0]}})
        put(self.data, "history/switch/2026-10.json", {"schema": 1, "games": {"0100A1B2C3D4E000": {"FR": [[20261020, 39.99, 0]]}}})
        site_data.build(self.data, self.out)
        lists = self.read("x/switch/lists.json")
        self.assertNotIn("countries", lists)
        self.assertNotIn("history_shards", lists)
        self.assertNotIn("prices", self.sheet("switch", "0100A1B2C3D4E000"))
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, "x", "switch"))), ["browse", "facets.json", "g", "lists.json", "names.json"])

    def test_names(self):
        names = self.read("x/steam/names.json")
        self.assertEqual([n[1] for n in names], ["Amber Lantern", "Moss & Märchen"])

    def test_another_schema(self):
        # A file of a later schema, or with none, reads as no file: its platform is left out.
        put(self.data, "platforms/gog/popular.json", {"schema": site_data.SCHEMA + 1, "games": {"900040": [60, 0, 0]}})
        put(self.data, "platforms/xbox/popular.json", {"games": {"9N0000000001": [60, 0, 0]}})
        self.assertIsNone(site_data.read(os.path.join(self.data, "platforms", "gog", "popular.json")))
        self.assertIsNone(site_data.read(os.path.join(self.data, "platforms", "xbox", "popular.json")))
        self.assertEqual(site_data.read(os.path.join(self.data, "index.json"))["schema"], site_data.SCHEMA)
        self.assertEqual(site_data.platforms(self.data), ["steam", "switch"])

    def test_shard_matches_explorer(self):
        # explore.js: h = imul(h, 31) + code, unsigned 32 bits.
        self.assertEqual(site_data.shard("620", 256), (((ord("6") * 31 + ord("2")) * 31 + ord("0")) % 2 ** 32) % 256)
        self.assertLess(site_data.shard("0100A1B2C3D4E000", 64), 64)


class Build(unittest.TestCase):
    def test_build_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "data")
            sample(data)
            out = os.path.join(tmp, "site")
            subprocess.run([sys.executable, os.path.join(ROOT, "tools/build_site.py"), out, data], check=True,
                           capture_output=True)
            subprocess.run([sys.executable, os.path.join(ROOT, "tools/check_site.py"), out], check=True,
                           capture_output=True)
            with open(os.path.join(out, "fr/explore/index.html"), encoding="utf-8") as f:
                page = f.read()
            self.assertIn('<html lang="fr"', page)
            self.assertNotIn('"_country"', page)
            self.assertNotIn('data-view="deals"', page)
            # The one site the page's pictures come from besides its own: wsrv.nl (the notice says so, boreale.dev's privacy).
            self.assertIn("img-src 'self' data: https://wsrv.nl;", page)
            self.assertNotIn("img-src *", page)
            # The icons: one symbol for each notion of the taxonomy and each kind of facet, and the names in the page's language.
            self.assertIn('<symbol id="i-g-rpg" viewBox="0 0 24 24">', page)
            self.assertIn('<symbol id="i-k-developers" viewBox="0 0 24 24">', page)
            self.assertIn('"x_g_rpg":"Jeu de rôle"', page)
            # The header's menu of Boréale's sites: Atlas leads home, the others carry their UTM tags.
            self.assertIn('<a href="../../fr/" aria-current="true"><img src="../../assets/marks/atlas.svg"', page)
            self.assertIn('href="https://lantern.boreale.dev/fr/?utm_source=atlas&amp;utm_medium=nav" '
                          'referrerpolicy="strict-origin"', page)
            self.assertIn('<p class="sites-title">Données et protocoles ouverts</p>', page)
            self.assertTrue(os.path.isfile(os.path.join(out, "data/platforms/switch/games.json")))
            with open(os.path.join(out, "CNAME"), encoding="utf-8") as f:
                self.assertEqual(f.read().strip(), "atlas.boreale.dev")

    def test_status_page(self):
        # The data's status (status/): each source's and platform's state against the report's day.
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "data")
            sample(data)
            put(data, "report.json", {"schema": 2, "generated": "2026-11-02", "run": "build", "sources": {
                "wikipedia": {"files": 2, "records": 2000, "bytes": 9000, "generated": "2026-11-02"},
                "wikidata": {"files": 30, "records": 900, "bytes": 5000, "generated": "2026-10-28"},
                "steamspy": {"files": 1, "records": 500, "bytes": 3000, "generated": "2026-10-28"},
                "igdb": {"files": 0, "records": 0, "bytes": 0, "generated": ""}},
                "platforms": {"switch": {"games": 2, "linked": 0.5, "reviewed": 0.5, "generated": "2026-11-02"},
                              "nes": {"games": 7, "linked": 0.25, "reviewed": 0, "generated": "2026-11-02"}}})
            out = os.path.join(tmp, "site")
            subprocess.run([sys.executable, os.path.join(ROOT, "tools/build_site.py"), out, data], check=True,
                           capture_output=True)
            subprocess.run([sys.executable, os.path.join(ROOT, "tools/check_site.py"), out], check=True,
                           capture_output=True)
            with open(os.path.join(out, "status/index.html"), encoding="utf-8") as f:
                page = f.read()
            row = lambda name: page.split(f"<code>{name}</code>", 1)[1].split("</tr>", 1)[0]  # noqa: E731
            self.assertIn('class="state ok"', row("wikipedia"))
            self.assertIn('class="state late"', row("wikidata"))      # daily, 5 days behind the report
            self.assertIn('class="state ok"', row("steamspy"))        # weekly, 5 days is in time
            self.assertIn('class="state missing"', row("igdb"))
            self.assertIn("weekly build", page)
            self.assertIn("<td class=\"num\">50%</td>", page)
            self.assertIn("The old machines (1)", page)
            self.assertNotIn("With prices", page)
            self.assertIn('href="../data/report.json"', page)
            with open(os.path.join(out, "fr/status/index.html"), encoding="utf-8") as f:
                self.assertIn("50\u202f%", f.read())
            # A report of another schema (1: with `priced`; a later one) reads as none: the page says so.
            for other in (1, 3):
                put(data, "report.json", {"schema": other, "generated": "2026-11-02", "run": "build", "sources": {},
                                          "platforms": {"switch": {"games": 2, "linked": 0.5, "priced": 1, "reviewed": 0.5}}})
                subprocess.run([sys.executable, os.path.join(ROOT, "tools/build_site.py"), out, data], check=True,
                               capture_output=True)
                with open(os.path.join(out, "status/index.html"), encoding="utf-8") as f:
                    page = f.read()
                self.assertIn('class="note empty"', page)
                self.assertNotIn("<code>wikipedia</code>", page)

    def test_build_without_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "site")
            subprocess.run([sys.executable, os.path.join(ROOT, "tools/build_site.py"), out], check=True, capture_output=True)
            subprocess.run([sys.executable, os.path.join(ROOT, "tools/check_site.py"), out], check=True, capture_output=True)
            with open(os.path.join(out, "status/index.html"), encoding="utf-8") as f:
                self.assertIn("No report yet", f.read())


if __name__ == "__main__":
    unittest.main()


class Size(unittest.TestCase):
    """The site's size against what GitHub Pages takes (1 GB)."""

    def test_size(self):
        import check_site
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "x", "steam"))
            for name, n in (("index.html", 100), ("x/steam/lists.json", 250)):
                with open(os.path.join(tmp, name), "wb") as f:
                    f.write(b"a" * n)
            from pathlib import Path
            self.assertEqual(check_site.size(Path(tmp)), 350)
        self.assertLess(check_site.SIZE_WARN, check_site.SIZE_MAX)
        self.assertLess(check_site.SIZE_MAX, 1000 ** 3)
