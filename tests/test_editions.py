"""tools/editions.py: a game's editions found by their names, the games
that only look like editions kept apart, a game's editions out of its
similar games."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402
import editions  # noqa: E402


def entry(tid, name, date, publisher="Lanternworks"):
    return {"id": tid, "name": name, "releaseDate": date, "publisher": publisher}


A, B, C, D, E, F, G = (f"0100000000{n}0000" for n in range(10, 17))


class Editions(unittest.TestCase):
    def test_core(self):
        self.assertEqual(editions.core("Hollow Manor™ - Deluxe Edition"), "hollow manor")
        self.assertEqual(editions.core("Hollow Manor: Game of the Year Edition"), "hollow manor")
        self.assertEqual(editions.core("Hollow Manor + Haunted Wing Pack"), "hollow manor")
        self.assertEqual(editions.core("Hollow Manor Remastered"), "hollow manor remastered")
        self.assertEqual(editions.core("Fight Night Special"), "fight night special")
        self.assertEqual(editions.core("Lanterns + Embers"), "lanterns embers")

    def test_editions(self):
        titles = {
            "1": entry(A, "Hollow Manor", "20220301"),
            "2": entry(B, "Hollow Manor - Complete Edition", "20240105"),
            "3": entry(C, "Hollow Manor Deluxe", "20230610"),
            "4": entry(D, "Hollow Manor Remastered", "20250101"),
            "5": entry(E, "Hollow Manor", "20220301", publisher="Someone Else"),
            "6": entry(F, "Kart Cup", "20210101"),
            "7": {"id": G, "name": "Kart Cup Gold", "releaseDate": "20211201", "publisher": "Lanternworks", "isDemo": "True"},
        }
        self.assertEqual(editions.editions(titles, build.base_id), {B: A, C: A})

    def test_apart(self):
        similar = {A: [[B, 90], [F, 40]], B: [[A, 90]], F: [[A, 40]]}
        self.assertEqual(editions.apart(similar, {B: A}), {A: [[F, 40]], F: [[A, 40]]})


if __name__ == "__main__":
    unittest.main()
