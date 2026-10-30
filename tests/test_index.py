"""tools/index.py: each data file listed with its day, size and hash, the
index itself left out, nothing that changes when the files do not."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import index  # noqa: E402


class Sizes(unittest.TestCase):
    """A file that more than doubles or falls under half its size is said, still published."""

    def test_grow_and_shrink(self):
        before = {"a.json": {"bytes": 100_000}, "b.json": {"bytes": 100_000}, "c.json": {"bytes": 100_000},
                  "d.json": {"bytes": 100_000}}
        now = {"a.json": {"bytes": 201_000}, "b.json": {"bytes": 49_000}, "c.json": {"bytes": 190_000},
               "d.json": {"bytes": 60_000}}
        lines = index.sizes(before, now)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("`a.json` weighs 0.20 MB against 0.10 MB last time (+101 %)"))
        self.assertTrue(lines[1].startswith("`b.json` weighs 0.05 MB against 0.10 MB last time (-51 %)"))

    def test_left_out(self):
        # Small files, the run's own, the history, a file new or gone: not weighed.
        before = {"small.json": {"bytes": 1000}, "changes.json": {"bytes": 100_000}, "report.json": {"bytes": 60_000},
                  "history/steam/2026-11.json": {"bytes": 100_000}, "gone.json": {"bytes": 100_000}}
        now = {"small.json": {"bytes": 40_000}, "changes.json": {"bytes": 900_000}, "report.json": {"bytes": 1},
               "history/steam/2026-11.json": {"bytes": 900_000}, "new.json": {"bytes": 900_000}}
        self.assertEqual(index.sizes(before, now), [])

    def test_parts_weighed_together(self):
        # A source cut again in more parts: its whole file is weighed, not each part.
        before = {"sources/steam-store/apps/1.json": {"bytes": 14_000_000}, "sources/steam-store/apps/2.json": {"bytes": 1_000_000}}
        now = {f"sources/steam-store/apps/{i}.json": {"bytes": 5_000_000} for i in (1, 2, 3)}
        self.assertEqual(index.sizes(before, now), [])
        now = {"sources/steam-store/apps/1.json": {"bytes": 5_000_000}}
        self.assertIn("`sources/steam-store/apps.json`", index.sizes(before, now)[0])

    def test_main_alerts(self):
        # The last run's index.json is read before it is replaced; the line goes to ALERTS.
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "index.json"), "w") as f:
                json.dump({"schema": 1, "files": {"popular.json": {"bytes": 200_000}}}, f)
            with open(os.path.join(d, "popular.json"), "w") as f:
                f.write('{"schema":1,"games":{}}' + " " * 60_000)
            alerts = os.path.join(d, "alerts.md")
            old = (sys.argv, os.environ.get("ALERTS"))
            sys.argv, os.environ["ALERTS"] = ["index.py", d], alerts
            try:
                index.main()
            finally:
                sys.argv = old[0]
                if old[1] is None:
                    del os.environ["ALERTS"]
                else:
                    os.environ["ALERTS"] = old[1]
            with open(alerts) as f:
                self.assertIn("`popular.json` weighs 0.06 MB against 0.20 MB", f.read())
            with open(os.path.join(d, "index.json")) as f:
                self.assertIn("popular.json", json.load(f)["files"])


class Index(unittest.TestCase):
    def test_index(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "prices"))
            os.makedirs(os.path.join(d, ".git"))
            for path, body in (("popular.json", '{"schema":1,"generated":"2026-10-29","games":{}}'),
                               ("prices/FR.json", '{"schema":1,"generated":"2026-10-30","games":{}}'),
                               ("index.json", "{}"), ("notes.txt", "x"), (".git/x.json", "{}")):
                with open(os.path.join(d, path), "w") as f:
                    f.write(body)
            got = index.index(d)
            self.assertEqual(sorted(got["files"]), ["popular.json", "prices/FR.json"])
            self.assertEqual(got["files"]["prices/FR.json"]["generated"], "2026-10-30")
            self.assertEqual(got["files"]["popular.json"]["bytes"], 48)
            self.assertEqual(len(got["files"]["popular.json"]["sha256"]), 16)
            # The same files, the same index.
            self.assertEqual(json.dumps(index.index(d)), json.dumps(got))


if __name__ == "__main__":
    unittest.main()
