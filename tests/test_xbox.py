"""tools/xbox.py's parts that need no network: the store's products read, a
game's entry, its price, the Game Pass, the scores."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import xbox  # noqa: E402

A, B, C = "9ZZZZZZZZZZ1", "9ZZZZZZZZZZ2", "9ZZZZZZZZZZ3"


def product(pid, title, list_price=29.99, msrp=29.99, kind="Game", ratings=463):
    return {"ProductId": pid, "ProductKind": kind,
            "LocalizedProperties": [{"ProductTitle": title, "DeveloperName": "Lantern Works", "PublisherName": "Tiny Owl"}],
            "MarketProperties": [{"OriginalReleaseDate": "2020-10-23T00:00:00.0000000Z",
                                  "UsageData": [{"AggregateTimeSpan": "7Days", "AverageRating": 4.5, "RatingCount": 2},
                                                {"AggregateTimeSpan": "AllTime", "AverageRating": 4.2, "RatingCount": ratings}]}],
            "Properties": {"Categories": ["Action & adventure", "Platformer"]},
            "DisplaySkuAvailabilities": [{"Availabilities": [
                {"Actions": ["Details", "License"], "OrderManagementData": {"Price": {"ListPrice": 0.0, "MSRP": 0.0}}},
                {"Actions": ["Details", "Purchase"], "OrderManagementData": {"Price": {"ListPrice": list_price, "MSRP": msrp}}}]}]}


class Xbox(unittest.TestCase):
    def test_big_id(self):
        self.assertEqual(xbox.big_id(" 9zzzzzzzzzz1 "), A)
        self.assertIsNone(xbox.big_id("9ZZZ"))

    def test_price_of(self):
        self.assertEqual(xbox.price_of(product(A, "A")), [29.99, 0, 0])
        self.assertEqual(xbox.price_of(product(B, "B", 14.99, 29.99)), [29.99, 14.99, 0])
        self.assertIsNone(xbox.price_of(product(C, "C", 0.0, 0.0)))
        self.assertIsNone(xbox.price_of({"ProductId": C}))

    def test_entry(self):
        self.assertEqual(xbox.entry(product(A, "Amber Lantern"), "Q900001", ["pc", "console"]), {
            "name": "Amber Lantern", "qid": "Q900001", "release": 20201023, "rating": [463, 84],
            "gamepass": ["console", "pc"], "developers": [["name:lantern works", "Lantern Works"]],
            "publishers": [["name:tiny owl", "Tiny Owl"]],
            "genres": [["genre:action & adventure", "Action & adventure"], ["genre:platformer", "Platformer"]]})

    def test_read_products(self):
        def fetch(url):
            self.assertIn("market=JP", url)
            return {"Products": [product(A, "A"), {"ProductId": "bad"}]}
        got = xbox.read_products([A, B], "JP", fetch, workers=1, pause=0)
        self.assertEqual(list(got), [A])

    def test_read_gamepass(self):
        lists = {"f6f1f99f": [{"siglId": "f6f1f99f"}, {"id": A}, {"id": B}], "fdd9e2a7": [{"siglId": "fdd9e2a7"}, {"id": A}]}
        got = xbox.read_gamepass(lambda url: lists[url.split("id=")[1][:8]])
        self.assertEqual(got, {A: ["console", "pc"], B: ["console"]})

    def test_popular(self):
        games = {A: {"rating": [10000, 90]}, B: {"rating": [3, 60]}, C: {"gamepass": ["pc"]}}
        table = xbox.popular({}, {}, {}, games)
        self.assertGreater(table[A][0], table[B][0])
        self.assertIn(C, table)   # in the Game Pass, without ratings


if __name__ == "__main__":
    unittest.main()
