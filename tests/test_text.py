"""tools/text.py without the network: games alike by their words, demos
left out, and the traits' likeness merged with the words'."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402
import text  # noqa: E402


def entry(tid, name, description, category=("Puzzle",), publisher="Lanternworks", demo=False):
    return {"id": tid, "name": name, "description": description, "category": list(category),
            "publisher": publisher, "isDemo": demo}


# Made-up games: three of haunted manors, two of kart races, one alone.
TITLES = {
    "a": entry("0100000000010000", "Hollow Manor", "Explore a haunted manor full of ghosts and creaking doors. Survive the night.", ("Horror", "Adventure")),
    "b": entry("0100000000020000", "Manor of Whispers", "A haunted manor, ghosts in every hall: survive until dawn.", ("Horror", "Adventure")),
    "c": entry("0100000000030000", "Ghost Lantern", "Ghosts haunt the old manor; light your lantern and survive.", ("Horror",)),
    "d": entry("0100000000040000", "Turbo Drift Kart", "Drift your kart around tracks, boost past rivals and win the cup.", ("Racing",), "Copperline"),
    "e": entry("0100000000050000", "Kart Cup Rally", "Win the cup: drift, boost and race your kart on every track.", ("Racing",), "Copperline"),
    "f": entry("0100000000060000", "Quiet Pond", "Fold paper boats on a quiet pond.", ("Relaxing",), "Pondworks"),
    "g": entry("0100000000070000", "Hollow Manor Demo", "Explore a haunted manor full of ghosts.", ("Horror",), demo=True),
    "h": entry("0100000000010800", "Hollow Manor Update", "An update.", ("Horror",)),
}


class Text(unittest.TestCase):
    def test_words(self):
        self.assertEqual(text.words_of("The Ghosts' manors, and the fun!"), ["ghost", "manor"])

    def test_similar(self):
        old = text.FLOOR
        text.FLOOR = 1   # few games: their scores are low
        try:
            got = text.similar(TITLES, build.base_id)
        finally:
            text.FLOOR = old
        ids = {k: [o for o, _ in v] for k, v in got.items()}
        # The haunted manors together, the karts together.
        self.assertEqual(set(ids["0100000000010000"][:2]), {"0100000000020000", "0100000000030000"})
        self.assertEqual(ids["0100000000040000"][0], "0100000000050000")
        # Demos and updates are not games of their own.
        self.assertNotIn("0100000000070000", got)
        self.assertNotIn("0100000000070000", sum(ids.values(), []))
        self.assertNotIn("0100000000010800", got)
        for row in got.values():
            self.assertTrue(all(1 <= s <= 100 for _, s in row))

    def test_merged(self):
        traits = {"A": [["B", 90], ["C", 40]]}
        words = {"A": [["C", 70], ["D", 50]], "E": [["A", 30]]}
        got = text.merged(traits, words)
        # The traits' likeness first; a word's counts four fifths.
        self.assertEqual(got["A"], [["B", 90], ["C", 56], ["D", 40]])
        self.assertEqual(got["E"], [["A", 24]])


if __name__ == "__main__":
    unittest.main()
