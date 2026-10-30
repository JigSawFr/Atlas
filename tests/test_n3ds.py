"""tools/n3ds.py: the 3DS's families and their match to Wikidata, from fictional titles."""
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import common  # noqa: E402
import n3ds  # noqa: E402

TITLES = {
    "0004000000A10000": {"name": "ランタンの物語", "region": "JP", "product_code": "CTR-P-LNTJ", "publisher": "Amber Works",
                         "release_date_on_eshop": "2014-03-01"},
    "0004000000A10100": {"name": "Lantern Tale™", "region": "US", "product_code": "CTR-P-LNTE",
                         "release_date_on_eshop": "2014-05-02"},
    "0004000000A10200": {"name": "Lantern Tale", "region": "EU", "product_code": "CTR-P-LNTP"},
    "0004000000B20000": {"name": "Quiet Pond", "region": "US", "product_code": "KTR-N-QPDE"},
    "0004000000B30000": {"name": "Quiet Pond", "region": "EU", "product_code": "CTR-N-QPXP"},   # two "Quiet Pond": no match
    "0004000000C40000": {"name": "No code", "region": "US"},
}
LISTS = {"base": sorted(TITLES), "updates": ["0004000E00A10100"], "dlc": ["0004008C00A10100"],
         "digital-demos": ["0004000200A10001"]}


class Families(unittest.TestCase):
    def test_families(self):
        f = n3ds.families(TITLES, LISTS)
        self.assertEqual(sorted(f), ["CTR-LNT", "CTR-QPX", "KTR-QPD"])
        lantern = f["CTR-LNT"]
        self.assertEqual(lantern["tids"], {"JP": ["0004000000A10000"], "US": ["0004000000A10100"], "EU": ["0004000000A10200"]})
        self.assertEqual(lantern["release"], 20140301)
        self.assertEqual(lantern["updates"], ["0004000E00A10100"])
        self.assertEqual(n3ds.name_of(lantern), "Lantern Tale™")

    def test_matches(self):
        f = n3ds.families(TITLES, LISTS)
        wiki = {"Q900001": {"name": "Lantern Tale", "platforms": [["Q203597", "Nintendo 3DS"]]},
                "Q900002": {"name": "Quiet Pond", "platforms": [["Q203597", "Nintendo 3DS"]]},
                "Q900003": {"name": "Lantern Tale", "platforms": [["Q8079", "Wii"]]}}
        self.assertEqual(n3ds.matches(f, wiki), {"Q900001": "CTR-LNT"})

    def test_collect(self):
        asked = []

        def fetch(url):
            asked.append(url)
            if "/category/" in url:
                return {"titles": LISTS.get(url.rsplit("/", 1)[-1], [])}
            tid = url.split("/ctr/")[1].split("?")[0]
            return dict(TITLES[tid], description="not kept")
        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as last:
            os.makedirs(os.path.join(last, "sources/nlib-ctr"))
            with open(os.path.join(last, "sources/nlib-ctr/titles.json"), "w") as f:
                json.dump({"schema": common.SOURCE_SCHEMA, "games": {"0004000000A10000": TITLES["0004000000A10000"]}}, f)
            n3ds.collect(out, last, [], datetime.date(2026, 11, 2), [], fetch=fetch, workers=1, pause=0)
            with open(os.path.join(out, "sources/nlib-ctr/titles.json")) as f:
                body = json.load(f)
        titles = body["games"]
        self.assertEqual(body["schema"], common.SOURCE_SCHEMA)
        self.assertEqual(len(titles), len(TITLES))
        self.assertNotIn("description", titles["0004000000B20000"])
        self.assertEqual(sum(1 for u in asked if "/category/" not in u), len(TITLES) - 1)   # the known one not asked

    def test_known_of_another_schema(self):
        # The last run's titles of a later schema: read as none (every title asked), left as they were.
        def fetch(url):
            if "/category/" in url:
                return {"titles": LISTS.get(url.rsplit("/", 1)[-1], [])}
            return dict(TITLES[url.split("/ctr/")[1].split("?")[0]])
        asked = []
        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as last:
            path = os.path.join(last, "sources/nlib-ctr/titles.json")
            os.makedirs(os.path.dirname(path))
            later = {"schema": common.SOURCE_SCHEMA + 1, "games": {"0004000000A10000": {"name": "?"}}}
            with open(path, "w") as f:
                json.dump(later, f)
            n3ds.collect(out, last, [], datetime.date(2026, 11, 2), [],
                         fetch=lambda u: asked.append(u) or fetch(u), workers=1, pause=0)
            with open(path) as f:
                self.assertEqual(json.load(f), later)
        self.assertEqual(sum(1 for u in asked if "/category/" not in u), len(TITLES))


if __name__ == "__main__":
    unittest.main()
