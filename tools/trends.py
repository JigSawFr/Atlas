#!/usr/bin/env python3
"""Each popular game's trend, every day: how much more (or less) it was read
on the Wikipedias of PlayShelf's languages (LANGS) in the last seven days
than in a week of the four before. It goes into popular.json's `trend`, the
weekly build's scores kept (tools/build.py), with the day it was measured
(`trends`).

The best known games (TOP, by score) are measured: Wikidata gives their
pages in each language, Wikimedia their views a day. A game read fewer than
MIN_VIEWS times in the week has no trend; one whose views could not be read
keeps the trend it had. When Wikimedia turns too many away, nothing changes.

Usage: tools/trends.py <out-dir> <previous-dir>   (switch/popular.json from previous-dir)
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse

import build
import common

LANGS = ("en", "fr", "de", "es", "it", "ja", "nl", "pt")
TOP = 400            # the best known games measured
MIN_VIEWS = 300      # views in the last seven days below which a trend says nothing
DAYS = 35            # the last seven days and the four weeks before
PAUSE = 0.1          # seconds between two requests
BATCH = 80           # games a Wikidata query asks for: more makes too long an address (414)
DAILY = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{lang}.wikipedia/all-access/user/"
         "{article}/daily/{start}/{end}")
PAGES = """
SELECT ?tid ?article WHERE {{
  VALUES ?tid {{ {tids} }}
  ?game wdt:P11072 ?tid.
  ?article schema:about ?game; schema:isPartOf ?wiki.
  FILTER(?wiki IN ({wikis}))
}}
"""


def all_pages(tids, sparql, sleep=time.sleep):
    """{title id: [(language, page title)]} for `tids`, asked of Wikidata BATCH at a time."""
    out = {}
    for i in range(0, len(tids), BATCH):
        if i:
            sleep(5)
        out.update(pages(sparql(pages_query(tids[i:i + BATCH])), build.base_id))
    return out


def pages_query(tids):
    wikis = ", ".join(f"<https://{lang}.wikipedia.org/>" for lang in LANGS)
    return PAGES.format(tids=" ".join(f'"{t}"' for t in tids), wikis=wikis)


def pages(rows, base_id):
    """{title id: [(language, page title)]} from Wikidata's rows."""
    out = {}
    for b in rows:
        tid = base_id(b["tid"]["value"])
        url = urllib.parse.urlparse(b["article"]["value"])
        lang = url.netloc.split(".")[0]
        if not tid or lang not in LANGS or not url.path.startswith("/wiki/"):
            continue
        title = urllib.parse.unquote(url.path[len("/wiki/"):])
        if (lang, title) not in out.setdefault(tid, []):
            out[tid].append((lang, title))
    return out


def window(today):
    """The first and last days measured: DAYS days up to yesterday (today's are not whole)."""
    end = today - datetime.timedelta(days=1)
    return end - datetime.timedelta(days=DAYS - 1), end


def daily(lang, title, start, end, fetch):
    """The page's views on each day from start to end (0 for a day without)."""
    url = DAILY.format(lang=lang, article=urllib.parse.quote(title.replace(" ", "_"), safe=""),
                       start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    body = fetch(url)
    counts = {item["timestamp"][:8]: item["views"] for item in (body or {}).get("items", [])}
    days = (end - start).days + 1
    return [counts.get((start + datetime.timedelta(days=i)).strftime("%Y%m%d"), 0) for i in range(days)]


def trend(days):
    """The last seven days against a week of the four before, in percent; 0 when too little is read."""
    last = sum(days[-7:])
    before = sum(days[-35:-7]) / 4
    if last < MIN_VIEWS or before <= 0:
        return 0
    return max(-100, min(999, round((last - before) * 100 / before)))


def read_trends(by_game, start, end, fetch, sleep=time.sleep):
    """{title id: trend} for the games whose views could be read, None when too few could."""
    out, asked, refused = {}, 0, 0
    for tid, langs in by_game.items():
        total = None
        for lang, title in langs:
            asked += 1
            try:
                views = daily(lang, title, start, end, fetch)
            except urllib.error.HTTPError as e:
                refused += 1
                if refused >= 5:
                    print(f"trends: refused ({e.code}) after {len(out)} games", file=sys.stderr)
                    return out if len(out) >= len(by_game) // 2 else None
                sleep(30)
                continue
            total = views if total is None else [a + b for a, b in zip(total, views)]
            sleep(PAUSE)
        if total is not None:
            out[tid] = trend(total)
    if len(out) < len(by_game) // 2:
        print(f"trends: {len(out)} of {len(by_game)} games read, too few: none used", file=sys.stderr)
        return None
    print(f"trends: {len(out)} of {len(by_game)} games read ({asked} pages)", file=sys.stderr)
    return out


def updated(popular, trends, today):
    """popular.json with the trends measured put in, the others' kept."""
    games = {tid: [row[0], trends.get(tid, row[1]), row[2]] for tid, row in popular["games"].items()}
    return {**popular, "trends": today.isoformat(), "games": games}


def main():
    out_dir, previous_dir = sys.argv[1], sys.argv[2]
    with open(os.path.join(previous_dir, build.SWITCH, "popular.json"), encoding="utf-8") as f:
        popular = json.load(f)
    if popular.get("schema") != 1:
        sys.exit("trends: popular.json is not of schema 1")
    today = datetime.date.today()
    top = [tid for tid, _ in sorted(popular["games"].items(), key=lambda kv: -kv[1][0])[:TOP]]
    by_game = all_pages(top, common.sparql)
    start, end = window(today)
    trends = read_trends(by_game, start, end, lambda url: common.fetch(url, tries=2, patient=False, timeout=30))
    if trends is None:
        return
    report = []
    common.publish(out_dir, f"{build.SWITCH}/popular.json", updated(popular, trends, today), previous_dir, report)
    print(common.summary(report), file=sys.stderr)


if __name__ == "__main__":
    main()
