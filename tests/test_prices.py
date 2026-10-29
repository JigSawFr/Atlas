"""tools/prices.py without the network: eShop ids, an answer read, a
country's games in batches."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402
import prices  # noqa: E402

A, B, C = "0100000000010000", "0100000000020000", "0100000000030000"


def price(nsu, regular, sale=None, end="2026-11-01T06:59:59Z", status="onsale"):
    p = {"title_id": nsu, "sales_status": status}
    if regular is not None:
        p["regular_price"] = {"amount": f"{regular} €", "currency": "EUR", "raw_value": str(regular)}
    if sale is not None:
        p["discount_price"] = {"amount": f"{sale} €", "currency": "EUR", "raw_value": str(sale), "end_datetime": end}
    return p


class Prices(unittest.TestCase):
    def test_eshop_ids(self):
        titles = {"1": {"id": A, "nsuId": "70010000000001"}, "2": {"id": B, "nsuId": 70010000000002, "isDemo": "True"},
                  "3": {"id": "0100000000010800", "nsuId": "70010000000003"}, "4": {"id": C, "nsuId": None}}
        self.assertEqual(prices.eshop_ids(titles, build.base_id), {70010000000001: A})

    def test_read_answer(self):
        ids = {1: A, 2: B, 3: C, 4: "0100000000040000"}
        body = {"prices": [price(1, 19.99, 13.99), price(2, 39.99), price(3, 9.99, status="sales_termination"),
                           price(4, 9.99, 12.0), price(5, 1.0), price(1, None)]}
        got, currency = prices.read_answer(body, ids)
        self.assertEqual(currency, "EUR")
        self.assertEqual(dict(got), {A: [19.99, 13.99, 20261101], B: [39.99, 0, 0], "0100000000040000": [9.99, 0, 0]})
        self.assertEqual(prices.day_of("bad"), 0)

    def test_read_country(self):
        ids = {n: f"01000000000{n:02d}000" for n in range(1, 121)}
        asked = []

        def fetch(url):
            asked.append(url)
            numbers = [int(x) for x in url.split("ids=")[1].split(",")]
            return {"prices": [price(n, 5.0, 2.5 if n % 10 == 0 else None) for n in numbers]}

        with mock.patch.object(prices.time, "sleep"):
            games, currency = prices.read_country("FR", ids, fetch, workers=2)
        self.assertEqual(len(asked), 3)            # 120 games, 50 a request
        self.assertTrue(all("country=FR" in u for u in asked))
        self.assertEqual(len(games), 120)
        self.assertEqual(sum(1 for r in games.values() if r[1]), 12)
        self.assertEqual(currency, "EUR")


if __name__ == "__main__":
    unittest.main()
