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

Usage: tools/trends.py <out-dir> <previous-dir> <sources-dir>   (switch/popular.json from
previous-dir, the pages and their views from the sources tools/collect.py keeps)
"""
import datetime
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
    return trends_of(by_game, lambda lang, title: daily(lang, title, start, end, fetch), sleep)


def trends_of(by_game, views_of, sleep=time.sleep):
    """read_trends with each page's views from `views_of(lang, title)`, which
    raises an HTTPError for a page Wikimedia refused."""
    out, asked, refused = {}, 0, 0
    for tid, langs in by_game.items():
        total = None
        for lang, title in langs:
            asked += 1
            try:
                views = views_of(lang, title)
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


def fetch_daily(by_game, start, end, fetch, sleep=time.sleep):
    """{"lang:title": [views a day]} of the games' pages, asked in turn
    (read_trends' order); after five refusals from Wikimedia, no more."""
    out, refused = {}, 0
    for tid, langs in by_game.items():
        for lang, title in langs:
            try:
                out[f"{lang}:{title}"] = daily(lang, title, start, end, fetch)
            except urllib.error.HTTPError as e:
                refused += 1
                if refused >= 5:
                    print(f"trends: refused ({e.code}) after {len(out)} pages", file=sys.stderr)
                    return out
                sleep(30)
                continue
            sleep(PAUSE)
    return out


def from_pages(by_game, pages):
    """read_trends from the pages' views collected (sources/wikipedia/daily.json):
    a page not read counts as refused."""
    def views_of(lang, title):
        key = f"{lang}:{title}"
        if key not in pages:
            raise urllib.error.HTTPError(key, 429, "not read", {}, None)
        return pages[key]
    return trends_of(by_game, views_of, sleep=lambda s: None)


def rows(popular):
    """popular.json's games whose row is [score, trend, ...], the others left out."""
    games = popular.get("games")
    return {tid: row for tid, row in (games.items() if isinstance(games, dict) else ())
            if isinstance(row, list) and len(row) >= 3 and isinstance(row[0], (int, float))}


def updated(popular, trends, today):
    """popular.json with the trends measured put in, the others' kept (and
    a row not of the shape known, as it is)."""
    known = rows(popular)
    games = {tid: [row[0], trends.get(tid, row[1]), *row[2:]] if tid in known else row
             for tid, row in popular["games"].items()}
    return {**popular, "platform": build.SWITCH, "trends": today.isoformat(), "games": games}


def consolidate(src, out_dir, previous_dir, today):
    """switch/popular.json with today's trends, from the sources collected."""
    # None, or one of another schema: the weekly build makes the next one.
    popular = common.previous_file(previous_dir, f"platforms/{build.SWITCH}/popular.json")
    if not rows(popular):
        print(f"trends: no platforms/{build.SWITCH}/popular.json of schema {common.SCHEMA} in {previous_dir}, nothing to redo",
              file=sys.stderr)
        return
    by_game = pages(common.bindings(src("wikidata/switch-pages.json").get("rows") or []), build.base_id)
    collected = common.collected_today(src, "wikipedia/daily.json", today)
    if not by_game or not collected:
        print("trends: no pages or views collected today, nothing changes", file=sys.stderr)
        return
    trends = from_pages(by_game, collected.get("pages") or {})
    if trends is None:
        return
    report = []
    common.publish(out_dir, f"platforms/{build.SWITCH}/popular.json", updated(popular, trends, today), previous_dir, report)
    print(common.summary(report), file=sys.stderr)


def main():
    out_dir, previous_dir, sources_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    common.timed(out_dir, "trends", lambda: consolidate(common.reader(sources_dir, previous_dir), out_dir, previous_dir,
                                                         datetime.date.today()))


if __name__ == "__main__":
    main()
