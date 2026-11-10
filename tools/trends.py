#!/usr/bin/env python3
"""Each popular game's trend, every day, on the Switch and on Steam
(PLATFORMS): how much more (or less) it was read on the Wikipedias of
PlayShelf's languages (LANGS) in the last seven days than in a week of the
four before. It goes into the platform's popular.json's `trend`, the weekly
build's scores kept (tools/build.py, tools/steam.py), with the day it was
measured (`trends`).

Each platform's best known games (TOP, by score) are measured: Wikidata
gives their pages in each language (by the platform's id: the Switch's title
id, Steam's app id), Wikimedia their views a day. A game read fewer than
MIN_VIEWS times in the week has no trend; one whose views could not be read
keeps the trend it had. When Wikimedia turns too many away, nothing changes.
The same views also give `platforms/<platform>/reach.json`: for each game read MIN_VIEWS times in the
days collected, the share of its views in each of LANGS (percent, in LANGS' order).

Usage: tools/trends.py <out-dir> <previous-dir> <sources-dir>   (each platform's popular.json from
previous-dir, the pages and their views from the sources tools/collect.py keeps)
"""
import datetime
import sys
import time
import urllib.error
import urllib.parse
import zlib

import build
import common
import steam

# The Wikipedias of the site's languages (site/i18n: the 15 locales, PlayShelf's too, are these 11 languages; the first 8
# keep their place, reach.json's rows being in this order).
LANGS = ("en", "fr", "de", "es", "it", "ja", "nl", "pt", "ko", "ru", "zh")
TOP = 400            # the best known games measured
MIN_VIEWS = 300      # views in the last seven days below which a trend says nothing
DAYS = 91            # 13 weeks: the last seven days, the four weeks before for the trend, and the curve of the sheet
WEEKS = 13           # weeks of the curve
MIN_CURVE = 100      # views in all the weeks below which a curve says nothing
PAUSE = 0.1          # seconds between two requests
MISSES = 5           # pages in a row not read after which the day's collection stops
# A page read little is asked less often (each request is a day of Wikimedia's patience): up to this many views in
# the last 28 days, once in so many days (each page on a day of its own); a page above the last limit, every day. Between
# two readings the page's last days are the week's mean before (carried()), which a page this small does not move.
CADENCE = ((300, 7), (1000, 3))
MAX_AGE = 8          # days since the last run above which nothing is carried: all the pages are asked
WAIT_MIN, WAIT_MAX = 30, 120   # seconds waited after a page not read (Wikimedia's Retry-After within them)
WAIT_BUDGET = 600    # seconds a day's collection may wait for Wikimedia, at most
BATCH = 80           # games a Wikidata query asks for: more makes too long an address (414)
DAILY = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{lang}.wikipedia/all-access/user/"
         "{article}/daily/{start}/{end}")
PAGES = """
SELECT ?tid ?article WHERE {{
  VALUES ?tid {{ {tids} }}
  ?game wdt:{prop} ?tid.
  ?article schema:about ?game; schema:isPartOf ?wiki.
  FILTER(?wiki IN ({wikis}))
}}
"""


def app_id(value):
    """A Steam app id as Wikidata gives it (P1733), or None."""
    value = (value or "").strip()
    return value if value.isdigit() else None


# The platforms measured: (id, the Wikidata property of a game's id there, that id from Wikidata's value).
PLATFORMS = ((build.SWITCH, "P11072", build.base_id), (steam.STEAM, "P1733", app_id))


def all_pages(tids, sparql, sleep=time.sleep, prop="P11072", base_id=build.base_id):
    """{game id: [(language, page title)]} for `tids`, asked of Wikidata BATCH at a time."""
    out = {}
    for i in range(0, len(tids), BATCH):
        if i:
            sleep(5)
        out.update(pages(sparql(pages_query(tids[i:i + BATCH], prop)), base_id))
    return out


def pages_query(tids, prop="P11072"):
    wikis = ", ".join(f"<https://{lang}.wikipedia.org/>" for lang in LANGS)
    return PAGES.format(tids=" ".join(f'"{t}"' for t in tids), wikis=wikis, prop=prop)


def top(popular):
    """popular.json's TOP best known games, by score."""
    return [tid for tid, _ in sorted(rows(popular).items(), key=lambda kv: -kv[1][0])[:TOP]]


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


def cadence(days):
    """Days between two readings of a page, from its last 28 days (the page's last series)."""
    views = sum(days[-28:])
    return next((every for limit, every in CADENCE if views <= limit), 1)


def carried(days, shift, length):
    """A page's last series moved forward `shift` days (the last reading was that many days ago): the days it
    still has, the new ones the mean of its last week; None when it cannot be (another length, too old)."""
    if not (isinstance(days, list) and len(days) == length and 0 <= shift < length and all(isinstance(d, int) for d in days)):
        return None
    mean = round(sum(days[-7:]) / 7)
    return days[shift:] + [mean] * shift


def due(key, every, today):
    """Whether a page asked every `every` days is asked today: on a day of its own, so the readings are spread."""
    return every <= 1 or (zlib.crc32(key.encode()) + today.toordinal()) % every == 0


def reuse(by_game, previous, today, everything=False):
    """{"lang:title": series} of the pages not asked today: the last run's, moved to today's window, for a page
    read little and not due; the others (new, hot, due, or whose last series cannot be moved) are asked.
    With `everything`, the due pages too (the stand-in for one that could not be asked). `previous` is the last
    daily.json ({"end": day, "pages": {...}})."""
    pages = (previous or {}).get("pages")
    try:
        last = datetime.date.fromisoformat(previous["end"])
    except (KeyError, TypeError, ValueError):
        return {}
    if not isinstance(pages, dict):
        return {}
    shift = (today - datetime.timedelta(days=1) - last).days
    out = {}
    if shift > MAX_AGE:
        return out
    for langs in by_game.values():
        for lang, title in langs:
            key = f"{lang}:{title}"
            days = pages.get(key)
            if key in out or not isinstance(days, list) or (not everything and due(key, cadence(days), today)):
                continue
            moved = carried(days, shift, DAYS)
            if moved is not None:
                out[key] = moved
    return out


def daily(lang, title, start, end, fetch):
    """The page's views on each day from start to end (0 for a day without)."""
    url = DAILY.format(lang=lang, article=urllib.parse.quote(title.replace(" ", "_"), safe=""),
                       start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    body = fetch(url)
    counts = {item["timestamp"][:8]: item["views"] for item in (body or {}).get("items", [])}
    days = (end - start).days + 1
    return [counts.get((start + datetime.timedelta(days=i)).strftime("%Y%m%d"), 0) for i in range(days)]


def weekly(days):
    """Views a week, the oldest first, over the whole weeks of `days` (the last day ends the last week),
    WEEKS at most."""
    n = min(len(days) // 7, WEEKS)
    return [sum(days[len(days) - 7 * (n - i):len(days) - 7 * (n - i - 1)]) for i in range(n)]


def curves(src):
    """{platform: {game id: [views a week]}} of the best known games, from the pages' views collected
    (sources/wikipedia/daily.json); a game read less than MIN_CURVE times in all, or on fewer than 4 weeks, has none."""
    pages_read = (src("wikipedia/daily.json").get("pages")) or {}
    out = {}
    for platform, _, base_id in PLATFORMS:
        by_game = pages(common.bindings(src(f"wikidata/{platform}-pages.json").get("rows") or []), base_id)
        found = out.setdefault(platform, {})
        for tid, langs in by_game.items():
            total = None
            for lang, title in langs:
                days = pages_read.get(f"{lang}:{title}")
                if isinstance(days, list) and days and all(isinstance(d, int) for d in days):
                    total = days if total is None else [a + b for a, b in zip(total, days)]
            weeks = weekly(total) if total else []
            if len(weeks) >= 4 and sum(weeks) >= MIN_CURVE:
                found[tid] = weeks
    return out


def reach_of(by_game, pages_read):
    """{game id: [share of its views in each of LANGS, in percent]} over the days collected, for the games
    read MIN_VIEWS times or more in all: where a game is read (a game much read in Japanese, in French…)."""
    out = {}
    for tid, pages_of in by_game.items():
        totals = dict.fromkeys(LANGS, 0)
        for lang, title in pages_of:
            days = pages_read.get(f"{lang}:{title}")
            if lang in totals and isinstance(days, list) and all(isinstance(d, int) for d in days):
                totals[lang] += sum(days)
        total = sum(totals.values())
        if total >= MIN_VIEWS:
            out[tid] = [round(totals[lang] * 100 / total) for lang in LANGS]
    return out


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


def fetch_daily(by_game, start, end, fetch, sleep=time.sleep, skip=()):
    """{"lang:title": [views a day]} of the games' pages, asked in turn
    (read_trends' order). A page refused for too many requests (429) is
    asked again once, after as long as Wikimedia says (Retry-After, within
    WAIT_MIN and WAIT_MAX), while the run has waited less than WAIT_BUDGET;
    a page not read is left out, and after MISSES in a row, no more: the
    ones read so far kept. The pages in `skip` (reuse()'s) are not asked."""
    out, missed, waited = {}, 0, 0
    for tid, langs in by_game.items():
        for lang, title in langs:
            if f"{lang}:{title}" in out or f"{lang}:{title}" in skip:   # the same game on two platforms: its page read once
                continue
            for again in (False, True):
                try:
                    out[f"{lang}:{title}"] = daily(lang, title, start, end, fetch)
                    missed = 0
                    break
                except common.NOT_READ as e:
                    print(f"trends: {lang}:{title}: {common.why(e)}", file=sys.stderr)
                    wait = retry_after(e)
                    if not again and getattr(e, "code", None) == 429 and waited + wait <= WAIT_BUDGET:
                        waited += wait
                        sleep(wait)
                        continue
                    missed += 1
                    if missed >= MISSES:
                        print(f"trends: {missed} pages in a row not read, stopped after {len(out)} pages "
                              f"({waited} s waited)", file=sys.stderr)
                        return out
                    sleep(wait)
                    break
            sleep(PAUSE)
    print(f"trends: {len(out)} pages read ({waited} s waited for Wikimedia)", file=sys.stderr)
    return out


def retry_after(error):
    """The seconds Wikimedia asks to wait (Retry-After), within WAIT_MIN and WAIT_MAX."""
    return build.wait_of(error, WAIT_MIN, WAIT_MAX)


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


def updated(popular, trends, today, platform=build.SWITCH):
    """popular.json with the trends measured put in, the others' kept (and
    a row not of the shape known, as it is)."""
    known = rows(popular)
    games = {tid: [row[0], trends.get(tid, row[1]), *row[2:]] if tid in known else row
             for tid, row in popular["games"].items()}
    return {**popular, "platform": platform, "trends": today.isoformat(), "games": games}


def consolidate(src, out_dir, previous_dir, today):
    """Each platform's popular.json with today's trends, from the sources collected."""
    report = []
    for platform, _, base_id in PLATFORMS:
        name = f"platforms/{platform}/popular.json"
        # None, or one of another schema: the weekly build makes the next one.
        popular = common.previous_file(previous_dir, name)
        if not rows(popular):
            print(f"trends: no {name} of schema {common.SCHEMA} in {previous_dir}, nothing to redo", file=sys.stderr)
            continue
        by_game = pages(common.bindings(src(f"wikidata/{platform}-pages.json").get("rows") or []), base_id)
        collected = common.collected_today(src, "wikipedia/daily.json", today)
        if not by_game or not collected:
            print(f"trends: {platform}: no pages or views collected today, nothing changes", file=sys.stderr)
            continue
        reach = reach_of(by_game, collected.get("pages") or {})
        if reach:
            common.publish(out_dir, f"platforms/{platform}/reach.json", {
                "schema": common.SCHEMA, "platform": platform, "generated": today.isoformat(),
                "source": "Wikimedia pageviews, Wikidata (the games' pages)", "languages": list(LANGS), "games": reach},
                previous_dir, report)
        trends = from_pages(by_game, collected.get("pages") or {})
        if trends is None:
            continue
        common.publish(out_dir, name, updated(popular, trends, today, platform), previous_dir, report)
    if report:
        print(common.summary(report), file=sys.stderr)


def main():
    out_dir, previous_dir, sources_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    common.timed(out_dir, "trends", lambda: consolidate(common.reader(sources_dir, previous_dir), out_dir, previous_dir,
                                                         datetime.date.today()))


if __name__ == "__main__":
    main()
