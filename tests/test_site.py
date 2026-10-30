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
    put(base, "switch/popular.json", {"schema": 1, "generated": "2026-11-02",
                                      "games": {"0100A1B2C3D4E000": [80, 12, 90], "0100F0F0F0F0F000": [20, 0, 0]}})
    put(base, "switch/games.json", {"schema": 1, "games": {"0100A1B2C3D4E000": {
        "series": [["Q900100", "Amber Saga"]], "developers": [["Q900200", "Tiny Owl"]], "steam": {"app": 900010, "owners": 5000}}}})
    put(base, "switch/upcoming.json", {"schema": 1, "games": {"0100C0C0C0C0C000": [20261204, "Frost Harbor"]}})
    put(base, "switch/similar.json", {"schema": 1, "games": {"0100A1B2C3D4E000": [["0100C0C0C0C0C000", 55]]}})
    put(base, "switch/editions.json", {"schema": 1, "games": {"0100F0F0F0F0F000": "0100A1B2C3D4E000"}})
    put(base, "switch/prices/FR.json", {"schema": 1, "country": "FR", "currency": "EUR", "generated": "2026-11-02",
                                        "games": {"0100A1B2C3D4E000": [39.99, 19.99, 20261110, 19.99, 20261102],
                                                  "0100F0F0F0F0F000": [1.99, 0.99, 20261110, 0.99, 20261102]}})
    put(base, "steam/popular.json", {"schema": 1, "generated": "2026-11-02",
                                     "games": {"900010": [70, 5, 0], "900020": [40, -3, 0], "900030": [10, 0, 0]}})
    put(base, "steam/games.json", {"schema": 1, "tags": {"19": "Action"},
                                   "games": {"900010": {"name": "Amber Lantern", "qid": "Q900001", "tags": [19]},
                                             "900020": {"name": "Moss & Märchen"}}})
    put(base, "links.json", {"schema": 1, "games": {"Q900001": {"switch": ["0100A1B2C3D4E000"], "steam": ["900010"],
                                                                "gog": ["amber_lantern"]}}})
    put(base, "index.json", {"schema": 1, "files": {"switch/popular.json": {"generated": "2026-11-02", "bytes": 120, "sha256": "0" * 16},
                                                    "switch/prices/FR.json": {"generated": "2026-11-02", "bytes": 90, "sha256": "1" * 16}}})


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

    def test_deals_floor(self):
        deals = self.read("x/switch/deals/FR.json")
        # The 1,99 € game is under the floor (5 €): left out.
        self.assertEqual([g[0] for g in deals["games"]], ["0100A1B2C3D4E000"])
        self.assertEqual(deals["games"][0][8], 50)
        self.assertEqual(deals["floor"], 5)

    def test_sheet(self):
        s = self.sheet("switch", "0100A1B2C3D4E000")
        self.assertEqual(s["popular"], [80, 12, 90])
        self.assertEqual(s["traits"]["series"], ["Amber Saga"])
        self.assertEqual(s["similar"], [["0100C0C0C0C0C000", "Frost Harbor", 55]])
        self.assertEqual(s["editions"], [["0100F0F0F0F0F000", ""]])
        self.assertEqual(s["prices"]["FR"][-1], "EUR")
        self.assertEqual(s["links"]["steam"], ["900010"])
        self.assertEqual(s["qid"], "Q900001")
        self.assertEqual(self.sheet("switch", "0100F0F0F0F0F000")["edition_of"], ["0100A1B2C3D4E000", ""])
        self.assertEqual(self.sheet("steam", "900010")["traits"]["tags"], ["Action"])

    def test_names(self):
        names = self.read("x/steam/names.json")
        self.assertEqual([n[1] for n in names], ["Amber Lantern", "Moss & Märchen"])

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
            self.assertIn('"_country":"FR"', page)
            self.assertTrue(os.path.isfile(os.path.join(out, "data/switch/prices/FR.json")))
            with open(os.path.join(out, "CNAME"), encoding="utf-8") as f:
                self.assertEqual(f.read().strip(), "atlas.boreale.dev")

    def test_build_without_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "site")
            subprocess.run([sys.executable, os.path.join(ROOT, "tools/build_site.py"), out], check=True, capture_output=True)
            subprocess.run([sys.executable, os.path.join(ROOT, "tools/check_site.py"), out], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()


class Referrer(unittest.TestCase):
    """Links out: a third party gets no referrer, Boréale and JigSawFr's GitHub the origin."""

    def problems(self, html):
        import check_site
        page = check_site.Page()
        page.feed(html)
        return page.problems, page.no_referrer

    def test_own(self):
        import check_site
        for href in ("https://boreale.dev/", "https://atlas.boreale.dev/fr/", "https://github.com/JigSawFr/Atlas",
                     "https://github.com/jigsawfr/atlas/releases"):
            self.assertTrue(check_site.own(href), href)
        for href in ("https://store.example.com/app/1", "https://github.com/someone/else", "https://boreale.dev.example.com/",
                     "https://notboreale.dev/"):
            self.assertFalse(check_site.own(href), href)

    def test_links(self):
        ok = ('<meta name="referrer" content="no-referrer">'
              '<a href="https://store.example.com/app/1" rel="noreferrer noopener">store</a>'
              '<a href="https://github.com/JigSawFr/Atlas" referrerpolicy="strict-origin">GitHub</a>')
        self.assertEqual(self.problems(ok), ([], True))
        problems, meta = self.problems('<a href="https://store.example.com/app/1">store</a>'
                                       '<a href="https://boreale.dev/" rel="noreferrer">Boréale</a>')
        self.assertFalse(meta)
        self.assertEqual(len(problems), 2)
