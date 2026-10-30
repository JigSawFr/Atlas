"""tools/steam_prices.py's parts that need no network: GetItems' price read,
the lowest prices kept, a country read."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import steam_prices  # noqa: E402


def item(app, final, original=None, end=None, lowest=None, free=False):
    option = {"final_price_in_cents": str(final)}
    if original:
        option["original_price_in_cents"] = str(original)
        option["discount_pct"] = round(100 - final * 100 / original)
    if end:
        option["active_discounts"] = [{"discount_end_date": end}]
    if lowest:
        option["lowest_recent_price_in_cents"] = str(lowest)
    return {"appid": app, "success": 1, "is_free": free, "best_purchase_option": option}


class SteamPrices(unittest.TestCase):
    def test_row_of(self):
        self.assertEqual(steam_prices.row_of(item(900010, 1999)), [19.99, 0, 0, 0])
        self.assertEqual(steam_prices.row_of(item(900011, 2999, 3999, 1793728800, 2999)), [39.99, 29.99, 20261103, 29.99])   # 2026-11-03 01:00 UTC
        self.assertIsNone(steam_prices.row_of(item(900012, 0, free=True)))
        self.assertIsNone(steam_prices.row_of({"appid": 900013, "success": 1}))
        self.assertIsNone(steam_prices.row_of({"appid": 900014, "success": 2}))

    def test_with_lowest(self):
        rows = {"900010": [19.99, 9.99, 20261102, 14.99], "900011": [39.99, 0, 0, 0]}
        last = {"900010": [19.99, 0, 0, 7.99, 20261001, 0], "900011": [39.99, 0, 0, 39.99, 20261029, 0]}
        self.assertEqual(steam_prices.with_lowest(rows, last, "2026-10-30"), {
            "900010": [19.99, 9.99, 20261102, 7.99, 20261001, 14.99],
            "900011": [39.99, 0, 0, 39.99, 20261030, 0]})

    def test_read_country(self):
        def fetch(url):
            self.assertIn("%22country_code%22%3A%22JP%22", url)
            return {"response": {"store_items": [item(900010, 280000), item(900011, 0, free=True)]}}
        got = steam_prices.read_country("JP", ["900011", "900010"], fetch, workers=1, pause=0)
        self.assertEqual(got, {"900010": [2800.0, 0, 0, 0]})


    def test_refused_then_answered(self):
        import urllib.error
        calls = []

        def fetch(url):
            calls.append(url)
            if len(calls) == 1:
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
            return {"response": {"store_items": [item(900010, 999)]}}
        got = steam_prices.read_country("FR", ["900010"], fetch, workers=1, pause=0)
        self.assertEqual((got, len(calls)), ({"900010": [9.99, 0, 0, 0]}, 2))


if __name__ == "__main__":
    unittest.main()
