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
        for word in ("RPG", "Role-playing (RPG)", "role-playing video game", "Role playing", "JRPG"):
            self.assertEqual(taxonomy.find(word), ("g", "rpg"), word)
        for word in ("Single player", "Singleplayer", "single-player video game"):
            self.assertEqual(taxonomy.find(word), ("m", "single"), word)
        self.assertEqual(taxonomy.find("Action & adventure"), ("g", "action_adventure"))
        self.assertEqual(taxonomy.find("Bird view / Isometric"), ("p", "isometric"))
        self.assertEqual(taxonomy.find("Hack and slash/Beat 'em up"), ("g", "beat_em_up"))

    def test_a_word_in_another_kind(self):
        self.assertEqual(taxonomy.find("Action"), ("g", "action"))         # IGDB's theme
        self.assertEqual(taxonomy.find("Horror"), ("g", "horror"))
        self.assertEqual(taxonomy.find("Co-op"), ("m", "coop"))             # Steam's tag
        self.assertEqual(taxonomy.find("First-Person"), ("p", "first"))

    def test_what_stays_as_it_is(self):
        for word in ("Indie", "Pixel Graphics", "Nintendo", "", "Quiz/Trivia"):
            self.assertIsNone(taxonomy.find(word), word)

    def test_no_word_is_two_notions(self):
        # Building the table raises on a word two notions share; it is built on import.
        self.assertGreater(len(taxonomy.ALIASES), len(taxonomy.CONCEPTS))
        keys = [(c[0], c[1]) for c in taxonomy.CONCEPTS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_titles(self):
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
