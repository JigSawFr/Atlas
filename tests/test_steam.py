"""tools/steam.py's parts that need no network: GetItems' answers read, a
game's entry, the scores, the upcoming games, the most played."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import steam  # noqa: E402

TAGS = {19: "Action", 21: "Adventure", 492: "Indie"}


def item(app, name, reviews=None, release=None, kind=0, tags=(19, 492), franchise=None, coming=False):
    it = {"appid": app, "id": app, "success": 1, "type": kind, "name": name, "tagids": list(tags),
          "basic_info": {"developers": [{"name": "Lantern Works", "creator_clan_account_id": 77}],
                         "publishers": [{"name": "Tiny Owl"}]},
          "release": {"steam_release_date": release} if release else {}}
    if franchise:
        it["basic_info"]["franchises"] = [{"name": franchise}]
    if reviews:
        it["reviews"] = {"summary_filtered": {"review_count": reviews[0], "percent_positive": reviews[1]}}
    if coming:
        it["release"]["is_coming_soon"] = True
    return it


class Steam(unittest.TestCase):
    def test_app_id(self):
        self.assertEqual(steam.app_id(" 900010 "), "900010")
        for bad in ("0", "12a", "", None, "12345678901"):
            self.assertIsNone(steam.app_id(bad))

    def test_entry(self):
        got = steam.entry(item(900010, "Amber Lantern", (1200, 91), 1700000000, franchise="Lantern"), "Q900001")
        self.assertEqual(got, {
            "name": "Amber Lantern", "qid": "Q900001", "release": 20231114, "reviews": [1200, 91],
            "series": [["franchise:lantern", "Lantern"]], "developers": [["clan:77", "Lantern Works"]],
            "publishers": [["name:tiny owl", "Tiny Owl"]], "tags": [19, 492]})

    def test_read_items(self):
        answers = [{"response": {"store_items": [item(900010, "Amber Lantern"), {"appid": 900011, "success": 2}]}}]
        asked = []

        def fetch(url):
            asked.append(url)
            return answers.pop(0) if answers else None
        got = steam.read_items(["900011", "900010"], fetch, sleep=lambda s: None)
        self.assertEqual(list(got), ["900010"])
        self.assertEqual(len(asked), 1)
        self.assertIn("%22appid%22%3A900010", asked[0])

    def test_popular(self):
        known = {"900010": (40, None), "900011": (2, None)}
        games = {"900010": {"name": "A", "reviews": [10000, 90]}, "900011": {"name": "B", "reviews": [10, 50]},
                 "900012": {"name": "C"}}
        table = steam.popular(known, {}, {}, games, {"900012": 1})
        self.assertGreater(table["900010"][0], table["900011"][0])
        self.assertEqual(table["900010"][0], 80)   # its Wikipedia half: 60 (no critics, no views)
        self.assertIn("900012", table)   # the most played, without reviews or Wikidata

    def test_upcoming(self):
        games = {"900010": {"name": "Soon", "release": 20261204}, "900011": {"name": "Out", "release": 20200101},
                 "900012": {"name": "Far", "release": 20301204}, "900013": {"name": "Undated"}}
        self.assertEqual(steam.upcoming(games, datetime.date(2026, 11, 2)), {"900010": [20261204, "Soon"]})

    def test_tag_names(self):
        body = {"response": {"tags": [{"tagid": t, "name": n} for t, n in TAGS.items()] + [{"tagid": 7}]}}
        self.assertEqual(steam.tag_names(body), TAGS)

    def test_most_played(self):
        body = {"response": {"ranks": [{"rank": 1, "appid": 900010}, {"rank": 2, "appid": 900011}, {"rank": 3}]}}
        self.assertEqual(steam.most_played(body), {"900010": 1, "900011": 2})

    def test_similar(self):
        games = {str(900010 + i): steam.entry(item(900010 + i, f"G{i}", franchise="Lantern" if i < 3 else None,
                                                   tags=(19,) if i < 5 else (21,))) for i in range(8)}
        table = {app: [50, 0, 0] for app in games}
        got = steam.similar(games, table)
        self.assertEqual(got["900010"][0][0], "900011")   # same franchise first
        self.assertTrue(all(other != "900010" for other, _ in got["900010"]))


if __name__ == "__main__":
    unittest.main()
