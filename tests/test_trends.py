"""tools/trends.py without the network: the pages of each language, the
views a day, a trend, the scores kept."""
import contextlib
import datetime
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build  # noqa: E402
import common  # noqa: E402
import trends  # noqa: E402

A, B, C = "0100000000010000", "0100000000020000", "0100000000030000"


def row(tid, url):
    return {"tid": {"value": tid}, "article": {"value": url}}


class Trends(unittest.TestCase):
    def test_pages(self):
        rows = [row(A, "https://en.wikipedia.org/wiki/Lantern_Tale"), row(A, "https://fr.wikipedia.org/wiki/Lantern_Tale_%28jeu%29"),
                row(A, "https://en.wikipedia.org/wiki/Lantern_Tale"), row(B, "https://xx.wikipedia.org/wiki/Quiet_Pond"),
                row("0100000000010800", "https://en.wikipedia.org/wiki/Update")]
        self.assertEqual(trends.pages(rows, build.base_id), {A: [("en", "Lantern_Tale"), ("fr", "Lantern_Tale_(jeu)")]})
        self.assertIn('"0100000000010000"', trends.pages_query([A]))
        self.assertIn("<https://ja.wikipedia.org/>", trends.pages_query([A]))

    def test_batches(self):
        asked = []

        def sparql(query):
            asked.append(query)
            return [row(t, f"https://en.wikipedia.org/wiki/{t}") for t in query.split('"')[1::2] if t.startswith("0100")]

        tids = [f"01000000{n:05X}000" for n in range(1, 201)]
        got = trends.all_pages(tids, sparql, sleep=lambda s: None)
        self.assertEqual(len(asked), 3)                    # 200 games, 80 a query
        self.assertTrue(all(len(q) < 6000 for q in asked))
        self.assertEqual(len(got), 200)

    def test_trend(self):
        self.assertEqual(trends.trend([100] * 28 + [200] * 7), 100)     # twice a week of before
        self.assertEqual(trends.trend([100] * 28 + [50] * 7), -50)
        self.assertEqual(trends.trend([10] * 35), 0)                      # too little read
        self.assertEqual(trends.trend([0] * 28 + [500] * 7), 0)           # nothing before

    def test_read(self):
        start, end = trends.window(datetime.date(2026, 10, 29))
        self.assertEqual((start, end), (datetime.date(2026, 9, 24), datetime.date(2026, 10, 28)))

        def fetch(url):
            # Every page: 100 views a day, then 300 the last week; B's French page refused.
            if "fr.wikipedia" in url:
                raise urllib.error.HTTPError(url, 429, "busy", {}, None)
            items = []
            for i in range(35):
                day = start + datetime.timedelta(days=i)
                items.append({"timestamp": day.strftime("%Y%m%d") + "00", "views": 300 if i >= 28 else 100})
            return {"items": items}

        got = trends.read_trends({A: [("en", "A")], B: [("en", "B"), ("fr", "B")]}, start, end, fetch, sleep=lambda s: None)
        self.assertEqual(got, {A: 200, B: 200})

    def test_updated(self):
        popular = {"schema": 1, "month": "2026-09", "games": {A: [90, 5, 80], B: [50, -3, 0], C: [10, 0, 0]}}
        got = trends.updated(popular, {A: 40, B: 0}, datetime.date(2026, 10, 29))
        self.assertEqual(got["games"], {A: [90, 40, 80], B: [50, 0, 0], C: [10, 0, 0]})
        self.assertEqual((got["trends"], got["month"]), ("2026-10-29", "2026-09"))

    def test_updated_keeps_what_it_does_not_know(self):
        popular = {"schema": 1, "games": {A: [90, 5, 80, "more"], B: [50], C: "not a row"}}
        got = trends.updated(popular, {A: 40, B: 10, C: 10}, datetime.date(2026, 10, 29))
        self.assertEqual(got["games"], {A: [90, 40, 80, "more"], B: [50], C: "not a row"})


class Main(unittest.TestCase):
    """The daily run with no last popular.json it can read: nothing to redo, said, no error."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "out")
        self.last = os.path.join(self.tmp.name, "last")
        os.makedirs(os.path.join(self.last, "platforms", build.SWITCH))

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self):
        def no_network(*args, **kwargs):
            raise AssertionError("nothing to measure: no request")
        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["trends.py", self.out, self.last, os.path.join(self.tmp.name, "sources")]), \
                mock.patch.object(common, "sparql", no_network), mock.patch.object(common, "fetch", no_network), \
                contextlib.redirect_stderr(err):
            trends.main()
        self.assertFalse(os.path.exists(self.out))
        self.assertIn("nothing to redo", err.getvalue())

    def put(self, body):
        path = os.path.join(self.last, "platforms", build.SWITCH, "popular.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f)
        return path

    def test_no_file(self):
        self.run_main()

    def test_later_schema(self):
        body = {"schema": common.SCHEMA + 1, "games": {A: {"score": 90}}}
        path = self.put(body)
        self.run_main()
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), body)                # left as it was

    def test_no_schema(self):
        self.put({"games": {A: [90, 5, 80]}})
        self.run_main()

    def test_no_rows(self):
        self.put({"schema": common.SCHEMA, "games": {A: [90]}})
        self.run_main()


if __name__ == "__main__":
    unittest.main()
