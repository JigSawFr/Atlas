import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import tech  # noqa: E402


class Steam(unittest.TestCase):
    ITEM = {"appid": 900001, "platforms": {"windows": True, "mac": False, "steamos_linux": True, "steam_deck_compat_category": 3},
            "categories": {"supported_player_categoryids": [2, 27], "feature_categoryids": [22, 23, 8], "controller_categoryids": [18]},
            "assets": {"header": "ab/header.jpg", "small_capsule": "cd/capsule_231x87.jpg"},
            "screenshots": ["ss_1.jpg", "ss_2.jpg"], "languages": [[0, 1], [2, 0], [99, 1], [0, 0]]}

    def test_sheet(self):
        sheet = tech.steam(self.ITEM)
        self.assertEqual(sheet["os"], ["windows", "linux"])
        self.assertEqual(sheet["deck"], 3)
        self.assertEqual(sheet["langs"], ["en", "fr"])               # 99 is no language of ours, "en" once
        self.assertEqual(sheet["voices"], ["en"])
        self.assertEqual(sheet["feat"], ["achievements", "cloud", "controller_partial", "crossplay"])
        self.assertEqual(sheet["img"], {"h": "ab/header.jpg", "t": "cd/capsule_231x87.jpg", "s": ["ss_1.jpg", "ss_2.jpg"]})

    def test_full_controller_support_takes_the_partial(self):
        sheet = tech.steam({"categories": {"controller_categoryids": [28, 18]}})
        self.assertEqual(sheet["feat"], ["controller"])

    def test_the_deck_is_kept_when_tested(self):
        self.assertNotIn("deck", tech.steam({"platforms": {"steam_deck_compat_category": 0, "windows": True}}))
        self.assertEqual(tech.steam({"platforms": {"steam_deck_compat_category": 1}})["deck"], 1)

    def test_nothing_said_nothing_kept(self):
        self.assertEqual(tech.steam({"appid": 1, "name": "Old"}), {})


class Stores(unittest.TestCase):
    def test_gog(self):
        sheet = tech.gog({"operatingSystems": ["windows", "osx", "beos"], "features": ["single", "cloud_saves", "controller_support", "overlay"],
                          "ratings": [["pegiRating", "16"], ["brRating", "12"], ["esrbRating", "17"]],
                          "pictures": {"cover": "aa.png", "poster": "bb.jpg", "screenshots": ["s1", "s2"]}})
        self.assertEqual(sheet["os"], ["windows", "mac"])
        self.assertEqual(sheet["feat"], ["cloud", "controller"])
        self.assertEqual(sheet["age"], [["PEGI", "16"], ["ESRB", "17"]])
        self.assertEqual(sheet["img"], {"h": "aa.png", "v": "bb.jpg", "s": ["s1", "s2"]})

    def test_microsoft(self):
        sheet = tech.ms({"Properties": {"Platforms": ["Windows.Xbox", "Windows.Desktop"], "Attributes": [
                             {"Name": "XblLocalCoop", "Maximum": 4}, {"Name": "XblOnlineCoop", "Maximum": 8},
                             {"Name": "XblLocalMultiPlayer", "Maximum": 2}, {"Name": "SinglePlayer"},
                             {"Name": "XPA"}, {"Name": "Capability4k"}, {"Name": "XblCrossPlatformCoop"}]},
                         "MarketProperties": [{"ContentRatings": [{"RatingSystem": "PEGI", "RatingId": "PEGI:7"},
                                                                  {"RatingSystem": "ESRB", "RatingId": "ESRB:E10"},
                                                                  {"RatingSystem": "DJCTQ", "RatingId": "DJCTQ:10"},
                                                                  {"RatingSystem": "PEGI", "RatingId": "PEGI:3"}]}],
                         "LocalizedProperties": [{"Images": [["SuperHeroArt", "hero"], ["BoxArt", "box"], ["Poster", "poster"],
                                                              ["Screenshot", "s1"], ["Screenshot", "s2"]]}]})
        self.assertEqual(sheet["os"], ["windows", "xbox"])
        self.assertEqual(sheet["feat"], ["crossplay", "play_anywhere", "4k"])
        self.assertEqual(sheet["players"], {"local": 4, "online": 8})
        self.assertEqual(sheet["age"], [["PEGI", "7"], ["ESRB", "E10"]])        # the systems we show, once each
        self.assertEqual(sheet["img"], {"h": "hero", "v": "box", "s": ["s1", "s2"]})

    def test_one_player_is_not_a_count(self):
        self.assertNotIn("players", tech.ms({"Properties": {"Attributes": [{"Name": "XblLocalMultiPlayer", "Maximum": 1}]}}))

    def test_read(self):
        import json
        with tempfile.TemporaryDirectory() as data:
            os.makedirs(os.path.join(data, "sources", "gog", "catalog"))
            with open(os.path.join(data, "sources", "gog", "catalog", "US.json"), "w", encoding="utf-8") as f:
                json.dump({"schema": 1, "games": {"7": {"operatingSystems": ["linux"]}, "8": {"title": "Bare"}, "9": "not a game"}}, f)
            self.assertEqual(tech.read(data, "gog"), {"7": {"os": ["linux"]}})          # the games that say something
            self.assertEqual(tech.read(data, "steam"), {})                                # its source is not there
            self.assertEqual(tech.read(data, "switch"), {})                               # not a store
            with open(os.path.join(data, "sources", "gog", "catalog", "US.json"), "w", encoding="utf-8") as f:
                json.dump({"schema": 2, "games": {"7": {"operatingSystems": ["linux"]}}}, f)
            self.assertEqual(tech.read(data, "gog"), {})                                  # another schema counts as none


if __name__ == "__main__":
    unittest.main()
