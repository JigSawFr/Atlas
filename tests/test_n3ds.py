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
    "0004000000B30000": {"name": "Quiet Pond", "region": "EU", "product_code": "CTR-N-QPXP"},   # its European serial
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
        self.assertEqual(n3ds.matches(f, wiki), {"Q900001": ["CTR-LNT"], "Q900002": ["CTR-QPX", "KTR-QPD"]})

    def test_keys(self):
        for a, b in (("Lantern Tale™", "lantern tale"), ("The Amber Road", "Amber Road"),
                     ("Star Pilot II", "Star Pilot 2"), ("Café Story®", "CAFE STORY"),
                     ("Moss & Stone", "Moss and Stone"), ("Kite's Day", "Kites Day"),
                     ("Pixel-Garden", "Pixel Garden"), ("Tide Runner for Nintendo 3DS", "Tide Runner"),
                     ("Ｆｕｌｌ Ｗｉｄｔｈ", "Full Width")):
            self.assertEqual(n3ds.key(a), n3ds.key(b), (a, b))
        for a, b in (("Star Pilot X", "Star Pilot 10"), ("Star Pilot V", "Star Pilot 5"),
                     ("ガーデン", "カーデン"), ("Lantern Tale", "Lantern Tale 2"), ("3DS", "")):
            self.assertNotEqual(n3ds.key(a), n3ds.key(b), (a, b))
        self.assertEqual(n3ds.main_key("River Guard: Moon Tide"), n3ds.key("River Guard"))
        self.assertEqual(n3ds.main_key("River Guard - Moon Tide"), n3ds.key("River Guard"))
        self.assertEqual(n3ds.main_key("Reed Song [Deluxe]"), n3ds.key("Reed Song"))
        self.assertEqual(n3ds.main_key("River Guard"), "")
        self.assertEqual(n3ds.main_key("Ox: Return"), "")   # too short a title to stand alone

    def test_tricky_pairs(self):
        def fam(name, region="US", publisher="", release=0):
            return {"names": {region: name}, "tids": {region: []}, "publisher": publisher, "release": release}

        def item(name, publishers=(), **_):
            return {"name": name, "platforms": [["Q203597", "Nintendo 3DS"]],
                    "publishers": [["Q1", p] for p in publishers]}
        games = {
            "CTR-AAA": fam("Lantern Tale™"),                                   # marks
            "CTR-AAB": fam("Star Pilot II"),                                   # Roman numerals
            "CTR-AAC": fam("River Guard: Moon Tide", publisher="Amber Works Inc.", release=20140301),
            "CTR-AAD": fam("Kite Hero: Red", release=20150101),                # two of a title: no match
            "CTR-AAE": fam("Kite Hero: Blue", release=20150101),
            "CTR-AAF": fam("Moss Valley: Return", publisher="Fern Ltd", release=20160101),
            "CTR-AAG": fam("Quiet Pond", publisher="Amber Works", release=20140101),
            "CTR-AAH": fam("Quiet Pond", publisher="Reed Games", release=20120101),   # America twice
            "CTR-AAI": fam("ランタンの森", "JP"),                                  # the Japanese label
            "CTR-AAJ": fam("Some Other Name"),                                 # GameTDB's code
            "CTR-AAK": fam("Star Pilot X"),
            "CTR-AAL": fam("Owl Post", release=20130101),                      # two games, one family
            "CTR-AAM": fam("Salt Marsh"),                                      # by its alias
            "CTR-AAN": fam("Fox Trail", "US"),                                 # one game, a serial a region
            "CTR-AAP": fam("Fox Trail", "JP"),
            "CTR-AAQ": fam("Ember Isle\n-The Lost Map-", "EU", release=20150101),   # a subtitle in dashes
            "CTR-AAS": fam("ランタン\nコレクション", "JP", publisher="Amber Works"),   # a line, not a subtitle
            "CTR-AAR": fam("Ember<br>Isle 2"),
        }
        wiki = {
            "Q1": item("Lantern Tale"), "Q2": item("Star Pilot 2"),
            "Q3": item("River Guard", ["Amber Works"]),
            "Q4": item("Kite Hero"),
            "Q5": item("Moss Valley", ["Other Studio"]),                       # no year, no publisher in common
            "Q6": item("Quiet Pond", ["Amber Works"]),
            "Q7": item("Forest of Lanterns"), "Q8": item("Codename Gull"),
            "Q9": item("Star Pilot 10"),
            "Q10": item("Owl Post"), "Q11": item("Owl Post"),
            "Q12": item("Marsh of Salt"),
            "Q13": {"name": "Star Pilot II", "platforms": [["Q8079", "Wii"]]},   # another machine's
            "Q14": item("Fox Trail"), "Q15": item("Ember Isle"), "Q16": item("Ember Isle 2"),
            "Q17": item("Lantern", ["Amber Works"]),
        }
        extra = {"Q3": {"years": {2014}}, "Q5": {"years": {2011}}, "Q6": {"years": {2014}},
                 "Q7": {"names": ["ランタンの森"]}, "Q8": {"serials": {"AAJ"}},
                 "Q10": {"years": {2013}}, "Q11": {"years": {2013}}, "Q12": {"names": ["Salt Marsh"]},
                 "Q15": {"years": {2014}}, "Q17": {"names": ["ランタン"]}}
        self.assertEqual(n3ds.matches(games, wiki, extra), {
            "Q1": ["CTR-AAA"], "Q2": ["CTR-AAB"], "Q3": ["CTR-AAC"], "Q6": ["CTR-AAG"], "Q7": ["CTR-AAI"],
            "Q8": ["CTR-AAJ"], "Q12": ["CTR-AAM"], "Q14": ["CTR-AAN", "CTR-AAP"], "Q15": ["CTR-AAQ"],
            "Q16": ["CTR-AAR"]})

    def test_codes_first(self):
        # GameTDB's code wins over a name, and a serial two families share is not used.
        games = {"CTR-AAA": {"names": {"US": "Reed Song"}, "tids": {}, "release": 0},
                 "CTR-AAB": {"names": {"US": "Reed Song Deluxe"}, "tids": {}, "release": 0},
                 "CTR-ZZZ": {"names": {"US": "Ice Hill"}, "tids": {}, "release": 0},
                 "KTR-ZZZ": {"names": {"US": "Ice Hill Plus"}, "tids": {}, "release": 0}}
        wiki = {"Q1": {"name": "Reed Song", "platforms": [["Q203597", ""]]},
                "Q2": {"name": "Ice Hill Pack", "platforms": [["Q203597", ""]]}}
        extra = {"Q1": {"serials": {"AAB"}}, "Q2": {"serials": {"ZZZ"}}}
        self.assertEqual(n3ds.matches(games, wiki, extra), {"Q1": ["CTR-AAB"]})

    def test_extras(self):
        rows = [{"tid": {"value": "http://www.wikidata.org/entity/Q5"}, "ja": {"value": "ランタン"}},
                {"tid": {"value": "http://www.wikidata.org/entity/Q5"}, "alias": {"value": "Lantern"}},
                {"tid": {"value": "http://www.wikidata.org/entity/Q5"}, "date": {"value": "2014-03-01T00:00:00Z"}},
                {"tid": {"value": "http://www.wikidata.org/entity/Q5"}, "tdb": {"value": "3DS/LNTE"}},
                {"tid": {"value": "http://www.wikidata.org/entity/Q5"}, "tdb": {"value": "Wii/RLNE01"}},
                {"tid": {"value": "not an item"}, "alias": {"value": "?"}}]
        self.assertEqual(n3ds.extras(rows), {"Q5": {"names": ["ランタン", "Lantern"], "years": {2014},
                                                    "serials": {"LNT"}}})

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
