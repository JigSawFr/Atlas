import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import taxonomy  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class Words(unittest.TestCase):
    def test_fold(self):
        self.assertEqual(taxonomy.fold("Shoot 'em Up"), "shoot em up")
        self.assertEqual(taxonomy.fold("Role-playing (RPG)"), "role playing rpg")
        self.assertEqual(taxonomy.fold("Éducatif"), "educatif")

    def test_the_sources_words_of_one_notion(self):
        for word in ("RPG", "Role-playing (RPG)", "role-playing video game", "Role playing", "CRPG"):
            self.assertEqual(taxonomy.find(word), ("g", "rpg"), word)
        for word in ("Single player", "Singleplayer", "single-player video game"):
            self.assertEqual(taxonomy.find(word), ("m", "single"), word)
        self.assertEqual(taxonomy.find("JRPG"), ("g", "jrpg"))
        self.assertEqual(taxonomy.find("Action & adventure"), ("g", "action_adventure"))
        self.assertEqual(taxonomy.find("Bird view / Isometric"), ("p", "isometric"))
        self.assertEqual(taxonomy.find("Hack and slash/Beat 'em up"), ("g", "beat_em_up"))

    def test_a_word_in_another_kind(self):
        self.assertEqual(taxonomy.find("Action"), ("g", "action"))         # IGDB's theme
        self.assertEqual(taxonomy.find("Horror"), ("g", "horror"))
        self.assertEqual(taxonomy.find("Co-op"), ("m", "coop"))             # Steam's tag
        self.assertEqual(taxonomy.find("First-Person"), ("p", "first"))

    def test_what_stays_as_it_is(self):
        for word in ("Great Soundtrack", "Nintendo", "", "Quiz/Trivia", "Christmas video game"):
            self.assertIsNone(taxonomy.find(word), word)

    def test_what_the_players_tags_say(self):
        for word, found in (("Pixel Graphics", ("y", "pixel_art")), ("Hand-drawn", ("y", "hand_drawn")), ("Cozy", ("o", "cozy")),
                            ("Atmospheric", ("o", "atmospheric")), ("Story Rich", ("h", "story_rich")), ("Perma Death", ("h", "permadeath")),
                            ("Violent", ("c", "violence")), ("Sexual Content", ("c", "mature")), ("Indie", ("a", "indie")),
                            ("Free to Play", ("a", "free_to_play")), ("Early Access", ("a", "early_access")),
                            ("Souls-like", ("g", "action_rpg")), ("Tower Defense", ("g", "tower_defense")),
                            ("Farming Sim", ("g", "life_sim")), ("World War II", ("t", "ww2")), ("Twin Stick Shooter", ("g", "shooter"))):
            self.assertEqual(taxonomy.find(word), found, word)

    def test_a_genre_is_in_the_larger_ones(self):
        self.assertEqual(taxonomy.with_parents(["platformer", "jrpg"]), ["platformer", "action", "jrpg", "rpg"])
        self.assertEqual(taxonomy.with_parents(["tactics"]), ["tactics", "strategy", "rpg"])
        self.assertEqual(taxonomy.with_parents(["puzzle", "puzzle"]), ["puzzle"])
        for child, parents in taxonomy.PARENTS.items():
            self.assertIn(("g", child), [(c[0], c[1]) for c in taxonomy.CONCEPTS], child)
            for parent in parents:
                self.assertIn(("g", parent), [(c[0], c[1]) for c in taxonomy.CONCEPTS], parent)
                self.assertNotIn(child, taxonomy.PARENTS.get(parent, ()))             # no loop

    def test_no_word_is_two_notions(self):
        # Building the table raises on a word two notions share; it is built on import.
        self.assertGreater(len(taxonomy.ALIASES), len(taxonomy.CONCEPTS))
        keys = [(c[0], c[1]) for c in taxonomy.CONCEPTS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_a_word_with_game_after_it(self):
        self.assertEqual(taxonomy.find("horse racing video game"), ("g", "racing"))
        self.assertEqual(taxonomy.find("Extreme sports"), ("g", "sports"))
        self.assertIsNone(taxonomy.find("Game"))

    def test_one_company_many_spellings(self):
        for name in ("Nintendo", "NINTENDO", "Nintendo Co., Ltd.", "The Nintendo Company", "nintendo co ltd"):
            self.assertEqual(taxonomy.company_key(name), "nintendo", name)
        self.assertEqual(taxonomy.company_key("Square Enix Co., Ltd."), "square enix")
        self.assertEqual(taxonomy.company_key("Avalanche Software"), "avalanche software")          # a name, not a legal form
        self.assertNotEqual(taxonomy.company_key("Avalanche Software"), taxonomy.company_key("Avalanche Studios"))
        self.assertNotEqual(taxonomy.company_key("Atari Games"), taxonomy.company_key("Atari, Inc."))
        self.assertNotEqual(taxonomy.company_key("Sega"), taxonomy.company_key("Sega Sammy"))
        self.assertEqual(taxonomy.company_key("Inc"), "inc")                                       # never nothing
        self.assertEqual(taxonomy.company_key("The"), "the")

    def test_one_company_its_branches_and_notes(self):
        for name in ("Atlus", "ATLUS USA", "Atlus Co., Ltd", "Atlus (Japan)"):
            self.assertEqual(taxonomy.company_key(name), "atlus", name)
        for name in ("Nintendo of America", "Nintendo of Europe GmbH", "Nintendo (UK)"):
            self.assertEqual(taxonomy.company_key(name), "nintendo", name)
        for name in ("Ubisoft", "UBISOFT", "Ubisoft Entertainment", "Ubisoft Entertainment SA"):
            self.assertEqual(taxonomy.company_key(name), "ubisoft", name)
        for name in ("Konami", "KONAMI", "Konami Digital Entertainment Co., Ltd."):
            self.assertEqual(taxonomy.company_key(name), "konami", name)
        self.assertEqual(taxonomy.company_key("Feral Interactive (Linux)"), taxonomy.company_key("Feral Interactive (Mac)"))
        self.assertEqual(taxonomy.company_key("Image &amp; Form Games"), taxonomy.company_key("Image & Form Games"))
        self.assertEqual(taxonomy.company_key("USA"), "usa")                                       # never nothing

    def test_a_company_in_another_script_is_its_own(self):
        keys = {taxonomy.company_key(n) for n in ("橘子班", "乌鸦大仙", "Новый Диск", "カプコン")}
        self.assertEqual(len(keys), 4)                                                              # none is ""
        self.assertEqual(taxonomy.company_key("株式会社 カプコン"), taxonomy.company_key("カプコン"))
        self.assertEqual(taxonomy.company_key("方块游戏(CubeGame)"), taxonomy.company_key("方块游戏"))
        self.assertEqual(taxonomy.company_key("Ｌｅｍｏｎ Ｂａｌｍ"), "lemon balm")                     # full-width letters
        self.assertEqual(taxonomy.company_key("Bjørn Games"), "bjørn games")

    def test_titles(self):
        self.assertEqual(taxonomy.clean_title("Draknek &amp; Friends"), "Draknek & Friends")
        self.assertEqual(taxonomy.clean_title("The Legend of Zelda™: Breath of the Wild"), "The Legend of Zelda: Breath of the Wild")
        self.assertEqual(taxonomy.clean_title("  Super   Mario®  Odyssey – "), "Super Mario Odyssey")
        self.assertEqual(taxonomy.clean_title("Café"), "Café")                         # composed form
        self.assertEqual(taxonomy.clean_title("Café"), "Café")
        self.assertEqual(taxonomy.clean_title("A B​C"), "A B C")
        self.assertEqual(taxonomy.clean_title("™"), "")


    def test_labels_no_notion_names(self):
        self.assertEqual(taxonomy.tidy_label("social deduction video game"), "Social deduction")
        self.assertEqual(taxonomy.tidy_label("art game"), "Art game")
        self.assertEqual(taxonomy.tidy_label("Hidden Object"), "Hidden Object")
        self.assertEqual(taxonomy.tidy_label("video game"), "Video game")
        self.assertEqual(taxonomy.tidy_label("indie\u2122"), "Indie")


class Assets(unittest.TestCase):
    def test_every_notion_has_its_icon_and_its_name(self):
        english = json.load(open(os.path.join(ROOT, "site", "i18n", "en-US.json"), encoding="utf-8"))
        for letter, key, icon, _ in taxonomy.CONCEPTS:
            self.assertIn(letter, taxonomy.KINDS)
            self.assertTrue(os.path.exists(os.path.join(ROOT, "site", "icons", f"{icon}.svg")), icon)
            self.assertIn(f"x_{letter}_{key}", english)
        for icon in taxonomy.KIND_ICONS.values():
            self.assertTrue(os.path.exists(os.path.join(ROOT, "site", "icons", f"{icon}.svg")), icon)

    def test_every_name_of_a_notion_is_a_notion(self):
        english = json.load(open(os.path.join(ROOT, "site", "i18n", "en-US.json"), encoding="utf-8"))
        notions = {f"x_{c[0]}_{c[1]}" for c in taxonomy.CONCEPTS}
        named = {k for k in english if k[:2] == "x_" and k[2:3] in tuple(taxonomy.KINDS) and k[3:4] == "_"}
        self.assertEqual(named, notions)


if __name__ == "__main__":
    unittest.main()
