"""tools/platforms.py, and the files of each old machine (tools/retro.py) and
the Switch games' names (tools/build.py), from sources. Fictional games only."""
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402
import platforms  # noqa: E402
import retro  # noqa: E402

A, B = "0100000000010000", "0100000000020000"


class Registry(unittest.TestCase):
    def test_ids(self):
        got = platforms.registry(datetime.date(2026, 10, 30))["platforms"]
        self.assertEqual(len(got), len(platforms.STORES) + len(platforms.RETRO))
        self.assertEqual(got["switch"]["aurore"], "switch")
        self.assertEqual(got["3ds"]["aurore"], "3ds")
        self.assertEqual(got["psv"]["aurore"], "psv")
        self.assertEqual(got["nes"]["kind"], "retro")
        self.assertNotIn("aurore", got["steam"])
        for pid in got:
            self.assertRegex(pid, r"^[a-z0-9-]+$")
        qids = [r[2] for r in platforms.RETRO]
        self.assertEqual(sorted(qids), sorted(retro.PLATFORMS))   # every machine retro.py asks has its folder
        self.assertEqual(platforms.path("nes", "games.json"), "platforms/nes/games.json")


def row(game, machine, name, links=10):
    return {"tid": f"http://www.wikidata.org/entity/{game}", "platform": f"http://www.wikidata.org/entity/{machine}",
            "platformName": "", "links": str(links), "name": name}


class Machines(unittest.TestCase):
    def test_a_folder_each(self):
        rows = [row("Q900001", "Q172742", "Lantern Tale", 30), row("Q900001", "Q183259", "Lantern Tale", 30),
                row("Q900002", "Q172742", "Quiet Pond", 5)]
        src = {"wikidata/retro.json": {"rows": rows}}
        with tempfile.TemporaryDirectory() as out:
            retro.consolidate(lambda n: src.get(n, {}), out, None, datetime.date(2026, 10, 30))
            with open(os.path.join(out, "platforms/nes/games.json")) as f:
                nes = json.load(f)
            with open(os.path.join(out, "platforms/snes/popular.json")) as f:
                snes = json.load(f)
            self.assertEqual(sorted(nes["games"]), ["Q900001", "Q900002"])
            self.assertEqual(nes["platform"], "nes")
            self.assertEqual(list(snes["games"]), ["Q900001"])
            self.assertFalse(os.path.exists(os.path.join(out, "platforms/gba")))


class Names(unittest.TestCase):
    def test_names(self):
        src = {"titledb/US.json": {"games": {"1": {"id": A, "name": "Lantern Tale"}, "2": {"id": B, "isDemo": True,
                                                                                     "name": "Quiet Pond Demo"}}},
               "titledb/GB.json": {"games": {"3": {"id": A, "name": "Lantern Tale (UK)"}, "4": {"id": B, "name": "Quiet Pond"}}}}
        self.assertEqual(build.names_of(lambda n: src.get(n, {})), {A: "Lantern Tale", B: "Quiet Pond"})


if __name__ == "__main__":
    unittest.main()
