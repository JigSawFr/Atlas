import email.message
import io
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import common  # noqa: E402


class Clock:
    """A clock that only moves when something sleeps or is made to take time."""

    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def refusal(code, retry=None):
    headers = email.message.Message()
    if retry is not None:
        headers["Retry-After"] = str(retry)
    return urllib.error.HTTPError("https://example.org/x", code, "refused", headers, io.BytesIO(b""))


class Answer:
    def __init__(self, body=b'{"ok": true}'):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class PacerTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()

    def pacer(self, interval, share=0.0):
        return common.Pacer(interval, share, clock=self.clock.time, sleep=self.clock.sleep)

    def test_two_requests_are_an_interval_apart(self):
        p = self.pacer(5)
        p.wait()                                       # the first goes at once
        self.assertEqual(self.clock.slept, [])
        self.clock.now += 1                            # it took a second
        p.wait()
        self.assertEqual(self.clock.slept, [4])        # the second waits for the rest of the 5
        self.assertEqual(p.waited, 4)

    def test_no_wait_when_the_interval_has_passed(self):
        p = self.pacer(1)
        p.wait()
        self.clock.now += 3
        p.wait()
        self.assertEqual(self.clock.slept, [])

    def test_a_service_that_counts_time_gets_the_time_back(self):
        p = self.pacer(5, share=1.0)
        p.wait()
        started = self.clock.now
        self.clock.now += 22                           # a query that took 22 seconds
        p.done(started)
        p.wait()
        self.assertEqual(self.clock.slept, [22])       # as long again: half the clock is its own
        self.clock.now += 2                            # a quick one
        p.done(self.clock.now - 2)
        p.wait()
        self.assertEqual(self.clock.slept, [22, 3])    # the interval is the least

    def test_a_service_that_does_not_count_is_not_slowed_by_a_slow_answer(self):
        p = self.pacer(0.4, share=0.0)
        p.wait()
        started = self.clock.now
        self.clock.now += 30
        p.done(started)
        p.wait()
        self.assertEqual(self.clock.slept, [])


class Manners(unittest.TestCase):
    def test_hosts_with_manners(self):
        common.PACERS.clear()
        wikidata = common.pacer_for("https://query.wikidata.org/sparql?query=x")
        self.assertIs(wikidata, common.pacer_for("https://query.wikidata.org/other"))     # one for the host, shared
        self.assertEqual((wikidata.interval, wikidata.share), (5.0, 1.0))
        self.assertEqual(common.pacer_for("https://api.steampowered.com/IStoreBrowseService/GetItems/v1/").interval, 0.4)
        self.assertEqual(common.pacer_for("https://wikimedia.org/api/rest_v1/x").interval, 0.1)
        self.assertEqual(common.pacer_for("https://wikimedia.org/api/rest_v1/x"), common.pacer_for("https://wikimedia.org/api/rest_v1/y"))
        self.assertIsNone(common.pacer_for("https://example.org/x"))
        self.assertIsNone(common.pacer_for("https://notquery.wikidata.org.example.org/x"))

    def test_retry_after(self):
        self.assertEqual(common.retry_after(refusal(503, 120), 5), 120)
        self.assertEqual(common.retry_after(refusal(503), 5), 5)
        self.assertEqual(common.retry_after(refusal(503, "Wed, 21 Oct 2026 07:28:00 GMT"), 5), 5)    # a date: not read, the default
        self.assertEqual(common.retry_after(refusal(503, "-3"), 5), 0)


class Fetch(unittest.TestCase):
    def setUp(self):
        common.PACERS.clear()
        common.WAITED.clear()
        self.slept = []
        patches = [mock.patch.object(common.time, "sleep", self.slept.append),
                   mock.patch.object(common.random, "uniform", lambda a, b: 0.5)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_with(self, answers, **kwargs):
        calls = iter(answers)

        def urlopen(request, timeout=0):
            a = next(calls)
            if isinstance(a, Exception):
                raise a
            return a
        with mock.patch.object(common.urllib.request, "urlopen", urlopen):
            return common.fetch("https://example.org/x", **kwargs)

    def test_a_503_waits_what_it_says(self):
        self.assertEqual(self.run_with([refusal(503, 30), Answer()]), {"ok": True})
        self.assertEqual(self.slept, [30.5])                        # what it said, and a little jitter

    def test_a_503_without_a_word_waits_a_growing_while(self):
        self.assertEqual(self.run_with([refusal(503), refusal(502), Answer()]), {"ok": True})
        self.assertEqual(self.slept, [5.5, 10.5])

    def test_a_429_waits_a_minute_at_least(self):
        self.assertEqual(self.run_with([refusal(429, 10), Answer()]), {"ok": True})
        self.assertEqual(self.slept, [65])
        self.slept.clear()
        self.assertEqual(self.run_with([refusal(429, 100), Answer()]), {"ok": True})
        self.assertEqual(self.slept, [105])

    def test_a_429_is_raised_when_not_patient(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.run_with([refusal(429, 10)], patient=False)
        self.assertEqual(self.slept, [])

    def test_a_wait_longer_than_the_most_is_raised(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.run_with([refusal(429, common.MAX_WAIT + 100), Answer()])
        self.assertEqual(self.slept, [])

    def test_a_host_that_keeps_refusing_stops_costing_time(self):
        common.WAITED["example.org"] = common.WAIT_BUDGET - 30         # the run has waited nearly all it may for it
        with self.assertRaises(urllib.error.HTTPError):
            self.run_with([refusal(429, 10), Answer()])                 # 65 s more would pass the budget
        self.assertEqual(self.slept, [])
        self.assertEqual(self.run_with([refusal(503, 5), Answer()]), {"ok": True})   # a short wait still fits
        self.assertEqual(self.slept, [5.5])

    def test_the_waits_add_up_for_a_host(self):
        self.run_with([refusal(503, 30), refusal(503, 40), Answer()])
        self.assertEqual(common.WAITED["example.org"], 71.0)

    def test_a_404_is_none_and_another_error_is_raised(self):
        self.assertIsNone(self.run_with([refusal(404)]))
        with self.assertRaises(urllib.error.HTTPError):
            self.run_with([refusal(403), refusal(403), refusal(403), refusal(403)])

    def test_a_host_with_manners_is_paced(self):
        fake = mock.Mock()
        with mock.patch.object(common, "pacer_for", lambda url: fake):
            self.assertEqual(self.run_with([Answer()]), {"ok": True})
        self.assertEqual(fake.wait.call_count, 1)
        self.assertEqual(fake.done.call_count, 1)


if __name__ == "__main__":
    unittest.main()
