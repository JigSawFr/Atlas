"""tools/migrate.py: the Switch's files moved from the data branch's root into
switch/, read there by the next run as the last run's."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import common  # noqa: E402
import migrate  # noqa: E402

A = "0100000000010000"


class Migrate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, games):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"schema": 1, "games": games}, f)

    def test_root_files_move(self):
        for name in ("popular.json", "games.json", "similar.json", "upcoming.json", "editions.json"):
            self.put(name, {A: [1, 0, 0]})
        self.put("prices/FR.json", {A: [9.99, 0, 0, 4.99, 20261001]})
        self.put("index.json", {})
        moved = migrate.migrate(self.dir)
        self.assertEqual(len(moved), 6)
        self.assertEqual(sorted(os.listdir(self.dir)), ["index.json", "switch"])
        # The next run's guard and lowest prices read them there.
        self.assertEqual(common.count_in(os.path.join(self.dir, "switch", "popular.json")), 1)
        last = common.previous_file(self.dir, "switch/prices/FR.json")
        self.assertEqual(last["games"][A][3:], [4.99, 20261001])

    def test_switch_folder_wins(self):
        self.put("popular.json", {A: [1, 0, 0]})
        self.put("switch/popular.json", {A: [2, 0, 0], "0100000000020000": [1, 0, 0]})
        self.assertEqual(migrate.migrate(self.dir), [])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "popular.json")))
        self.assertEqual(common.count_in(os.path.join(self.dir, "switch", "popular.json")), 2)

    def test_again_does_nothing(self):
        self.put("prices/JP.json", {})
        migrate.migrate(self.dir)
        self.assertEqual(migrate.migrate(self.dir), [])
        self.assertTrue(os.path.exists(os.path.join(self.dir, "switch", "prices", "JP.json")))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "prices")))


if __name__ == "__main__":
    unittest.main()
