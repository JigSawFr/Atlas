"""tools/changes.py: what a run changed, the light files. Fictional games only."""
import datetime
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import changes  # noqa: E402
import schemas  # noqa: E402

A, B, C = "0100000000010000", "0100000000020000", "0100000000030000"
TODAY = datetime.date(2026, 11, 2)


def put(base, name, body):
    path = os.path.join(base, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f)


class Changes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.before = {
            "platforms/switch/games.json": {"schema": 1, "games": {A: {}, B: {}}},
            "platforms/switch/upcoming.json": {"schema": 1, "games": {C: [20261102, "Quiet Pond"]}},
            "platforms/switch/popular.json": {"schema": 1, "games": {A: [50, 10, 0], B: [40, 0, 0]}},
        }
        put(self.d, "platforms/switch/games.json", {"schema": 1, "generated": "2026-11-02", "games": {A: {}, B: {}, C: {}}})
        put(self.d, "platforms/switch/popular.json", {"schema": 1, "games": {A: [55, 210, 0], B: [40, 5, 0]}})

    def tearDown(self):
        self.tmp.cleanup()

    def test_changes(self):
        got = changes.changes(self.d, TODAY, previous=lambda p: self.before.get(p, {}))["switch"]
        self.assertEqual(got["new"], [C])
        self.assertEqual(got["out_today"], [C])
        self.assertEqual(got["trends"], [[A, 10, 210]])
        self.assertEqual(sorted(got), ["new", "out_today", "trends"])
        body = {"schema": 1, "generated": "2026-11-02", "platforms": {"switch": got}}
        self.assertEqual(schemas.errors(body, schemas.KINDS["changes"]), [])

    def test_other_schema(self):
        # The last run's files of a later schema read as none: no game said new, no trend moved.
        later = {p: {**b, "schema": 2} for p, b in self.before.items()}
        got = changes.changes(self.d, TODAY, previous=lambda p: later.get(p, {}))["switch"]
        self.assertNotIn("new", got)
        self.assertNotIn("trends", got)

    def test_lite(self):
        put(self.d, "platforms/steam/games.json", {"schema": 1, "generated": "2026-11-02", "games": {
            "900010": {"name": "Amber Lantern", "qid": "Q900001", "release": 20231114, "reviews": [1200, 91],
                       "tags": [19], "developers": [["clan:1", "A studio"]]}}})
        with mock.patch.object(changes, "LITE_FROM", 10):
            self.assertEqual(changes.lite(self.d), ["steam", "switch"])
        with open(os.path.join(self.d, "platforms/steam/games.lite.json")) as f:
            light = json.load(f)
        self.assertEqual(light["games"]["900010"], {"name": "Amber Lantern", "qid": "Q900001", "release": 20231114,
                                                    "reviews": [1200, 91]})


if __name__ == "__main__":
    unittest.main()
