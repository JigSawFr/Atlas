"""tools/retro.py's parts that need no network: Wikidata's rows read into
games with their platforms."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import retro  # noqa: E402

E = "http://www.wikidata.org/entity/"


def row(game, platform, name=None, platform_name=None):
    b = {"tid": {"value": E + game}, "platform": {"value": E + platform}, "links": {"value": "3"}}
    if name:
        b["name"] = {"value": name}
    if platform_name:
        b["platformName"] = {"value": platform_name}
    return b


class Retro(unittest.TestCase):
    def test_qid(self):
        self.assertEqual(retro.qid(E + "Q900001"), "Q900001")
        self.assertIsNone(retro.qid(E + "L12"))

    def test_games_of(self):
        rows = [row("Q900001", "Q172742", "Amber Lantern", "Nintendo Entertainment System"),
                row("Q900001", "Q186437", None, "Game Boy"), row("Q900001", "Q172742"),
                row("Q900002", "Q206261", "Pebble Pilots"), row("L1", "Q206261")]
        rows.append({**row("Q900003", "Q206261"), "nameMul": {"value": "Tiny Owl"}})
        self.assertEqual(retro.games_of(rows), {
            "Q900001": {"name": "Amber Lantern", "platforms": [["Q172742", "Nintendo Entertainment System"],
                                                              ["Q186437", "Game Boy"]]},
            "Q900002": {"name": "Pebble Pilots", "platforms": [["Q206261", ""]]},
            "Q900003": {"name": "Tiny Owl", "platforms": [["Q206261", ""]]}})

    def test_platforms(self):
        self.assertEqual(len(retro.PLATFORMS), len(set(retro.PLATFORMS)))
        self.assertTrue(all(retro.QID.match(p) for p in retro.PLATFORMS))


if __name__ == "__main__":
    unittest.main()
