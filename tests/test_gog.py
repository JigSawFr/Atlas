"""tools/gog.py's parts that need no network: GOG's catalog read, a game's
entry, its price, the scores."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import gog  # noqa: E402


def product(pid, title, final="9.99", base="9.99", rating=43, count=120, release="2023.09.26"):
    return {"id": str(pid), "slug": title.lower().replace(" ", "_"), "title": title, "releaseDate": release,
            "productType": "game", "developers": ["Lantern Works"], "publishers": ["Tiny Owl"],
            "genres": [{"name": "Role-playing", "slug": "rpg"}], "tags": [{"name": "Cozy", "slug": "cozy"}],
            "reviewsRating": rating, "reviewsCount": count,
            "price": {"finalMoney": {"amount": final, "currency": "EUR"}, "baseMoney": {"amount": base, "currency": "EUR"}}}


class Gog(unittest.TestCase):
    def test_price_of(self):
        self.assertEqual(gog.price_of(product(1, "A")), [9.99, 0, 0])
        self.assertEqual(gog.price_of(product(2, "B", final="3.99", base="19.99")), [19.99, 3.99, 0])
        self.assertIsNone(gog.price_of(product(3, "C", final="0.00", base="0.00")))
        self.assertIsNone(gog.price_of({"id": "4"}))

    def test_entry(self):
        self.assertEqual(gog.entry(product(900010, "Amber Lantern"), "Q900001"), {
            "name": "Amber Lantern", "slug": "amber_lantern", "qid": "Q900001", "release": 20230926,
            "reviews": [120, 86], "developers": [["name:lantern works", "Lantern Works"]],
            "publishers": [["name:tiny owl", "Tiny Owl"]], "genres": [["genre:rpg", "Role-playing"]],
            "tags": [["tag:cozy", "Cozy"]]})

    def test_read_catalog(self):
        pages = {1: {"pages": 2, "products": [product(900010, "A"), product(900011, "B")]},
                 2: {"pages": 2, "products": [product(900011, "B"), product(900012, "C")]}}

        def fetch(url):
            self.assertIn("currencyCode=USD", url)   # Japan, in dollars
            return pages[int(url.split("page=")[1].split("&")[0])]
        got = gog.read_catalog("JP", fetch, workers=1, pause=0)
        self.assertEqual([(p["id"], rank) for p, rank in got], [("900010", 1), ("900011", 2), ("900012", 3)])

    def test_slug_of(self):
        self.assertEqual(gog.slug_of("game/Amber_Lantern"), "amber_lantern")
        self.assertIsNone(gog.slug_of(""))

    def test_popular(self):
        games = {"900010": {"slug": "a", "reviews": [5000, 90]}, "900011": {"slug": "b", "reviews": [5, 60]},
                 "900012": {"slug": "c"}}
        table = gog.popular({"a": (30, None)}, {}, {}, games, {"900012": 1})
        self.assertGreater(table["900010"][0], table["900011"][0])
        self.assertIn("900012", table)   # first in GOG's trending order


if __name__ == "__main__":
    unittest.main()
