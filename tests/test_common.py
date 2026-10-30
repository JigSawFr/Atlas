"""tools/common.py's parts that need no network: a file published in a
folder of its own (a platform's), with its guard, and the last run's file read."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import common  # noqa: E402


class Common(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "out")
        self.last = os.path.join(self.tmp.name, "last")
        # The workflows set ALERTS for the run: these made-up files must not write to it.
        self.alerts = os.path.join(self.tmp.name, "test-alerts.md")
        self.env = mock.patch.dict(os.environ, {"ALERTS": self.alerts})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def payload(self, n):
        return {"schema": common.SCHEMA, "games": {str(900000 + i): [1, 0, 0] for i in range(n)}}

    def test_publish_in_a_folder(self):
        report = []
        self.assertTrue(common.publish(self.out, "steam/upcoming.json", self.payload(80), None, report))
        self.assertEqual(common.count_in(os.path.join(self.out, "steam", "upcoming.json")), 80)
        self.assertEqual(report, [("steam/upcoming.json", None, 80, False)])

    def test_guard_in_a_folder(self):
        common.publish(self.last, "steam/popular.json", self.payload(100), None, [])
        self.assertFalse(common.publish(self.out, "steam/popular.json", self.payload(10), self.last, []))
        self.assertEqual(common.count_in(os.path.join(self.out, "steam", "popular.json")), 100)

    def test_previous_file(self):
        common.publish(self.last, "steam/upcoming.json", self.payload(3), None, [])
        self.assertEqual(len(common.previous_file(self.last, "steam/upcoming.json")["games"]), 3)
        self.assertEqual(common.previous_file(self.last, "gog/upcoming.json"), {})
        self.assertEqual(common.previous_file(self.tmp.name, "nothing.json"), {})

    def put(self, name, body):
        path = os.path.join(self.last, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f)
        return path

    def test_another_schema(self):
        # A file of a later schema, or with none, is no last run's file.
        games = self.payload(100)["games"]
        for name, body in (("next.json", {"schema": common.SCHEMA + 1, "games": games}), ("none.json", {"games": games})):
            path = self.put(name, body)
            self.assertEqual(common.previous_file(self.last, name), {})
            self.assertIsNone(common.count_in(path))
        self.assertEqual(common.count_in(self.put("ours.json", {"schema": common.SCHEMA, "games": games})), 100)
        self.assertIsNone(common.count_in(self.put("list.json", [1, 2])))

    def test_guard_against_another_schema(self):
        # Not counted: this run's file is published, whatever its size, and the other left as it was.
        path = self.put("steam/popular.json", {"schema": common.SCHEMA + 1, "games": self.payload(100)["games"]})
        report = []
        self.assertTrue(common.publish(self.out, "steam/popular.json", self.payload(10), self.last, report))
        self.assertEqual(report, [("steam/popular.json", None, 10, False)])
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["schema"], common.SCHEMA + 1)


class RunsAlerts(unittest.TestCase):
    """The tests run in the workflows' jobs, whose ALERTS is the run's own:
    the guard's made-up "kept" lines must not reach it (a false alert)."""

    def test_tests_leave_the_runs_alerts_alone(self):
        import test_build
        with tempfile.TemporaryDirectory() as tmp:
            run = os.path.join(tmp, "run-alerts.md")
            with mock.patch.dict(os.environ, {"ALERTS": run}):
                suite = unittest.TestSuite()
                loader = unittest.TestLoader()
                suite.addTests(loader.loadTestsFromTestCase(test_build.Guard))
                suite.addTests(loader.loadTestsFromTestCase(Common))
                result = unittest.TextTestRunner(stream=open(os.devnull, "w")).run(suite)
            self.assertTrue(result.wasSuccessful())
            self.assertFalse(os.path.exists(run))


if __name__ == "__main__":
    unittest.main()
