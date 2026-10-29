#!/usr/bin/env python3
"""Builds PlayInsights' data files, by Nintendo Switch title id, from open
sources that need no key:

- data/popular.json: how well known each game is (a score from 0 to 100),
  whether it is read more lately (a trend, in percent) and what the critics
  gave it (0 to 100, 0 when unknown);
- data/upcoming.json: the games whose release date is still to come, with
  their name and date (and how many follow them on IGDB, when known);
- data/games.json: each game's traits (series, developers, publishers,
  genres, modes) and, for one also sold on Steam, its Steam audience;
- data/editions.json: a game's other editions (a Deluxe, a Complete
  Edition…), each with the game it is one of (tools/editions.py);
- data/similar.json: the games most like each one, by their traits
  (tools/features.py), and for the others by what the eShop says of them
  (tools/text.py).

The sources:

- Wikidata: the games with a Switch title id (P11072), how many Wikipedias
  have a page on each (sitelinks), their English page, and their critics'
  scores (P444) with the number of reviews behind each (P7887);
- Wikimedia's pageviews: how often each English page was read in each of the
  last three whole months, for the best known games (VIEWED);
- blawar/titledb's US eShop list: the release dates, for upcoming.json;
- SteamSpy: the reviews, owners and players of the games also on Steam
  (Wikidata's Steam id), a request a second within a time budget, the rest
  kept from the last run (`previous`);
- IGDB, only when IGDB_CLIENT_ID and IGDB_CLIENT_SECRET are set (the
  repository's secrets): more traits, a popularity and the hype of the games
  Wikidata links to it (tools/igdb.py).

A game's score weighs its sitelinks, its number of critics' reviews, its
views of the last month and its Steam reviews, each on a log scale against
the most of all, and its popularity on IGDB. When
Wikimedia turns too many view requests away (fewer than half read), every
game is scored without views and none has a trend: no mixing of scales.

Usage: tools/build.py [out-dir] [previous-dir]   (default: out/; previous-dir:
the last run's files, whose Steam figures are kept for the games not asked)
"""
import datetime
import json
import math
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import editions
import features
import igdb
import text

AGENT = "PlayInsights/1.0 (https://github.com/JigSawFr/PlayInsights)"
SPARQL = "https://query.wikidata.org/sparql"
# One query (Wikidata's service may allow one a minute): each game with a
# Switch title id, its sitelinks and English page, and each of its critics'
# scores with the number of reviews behind it (a row each).
QUERY = """
SELECT ?tid ?links ?article ?score ?count WHERE {
  ?game wdt:P11072 ?tid; wikibase:sitelinks ?links.
  OPTIONAL { ?article schema:about ?game; schema:isPartOf <https://en.wikipedia.org/>. }
  OPTIONAL { ?game p:P444 ?statement. ?statement ps:P444 ?score. OPTIONAL { ?statement pq:P7887 ?count } }
}
"""
VIEWS = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
         "{article}/monthly/{start}/{end}")
TITLEDB = "https://raw.githubusercontent.com/blawar/titledb/master/US.en.json"
TID = re.compile(r"^0100[0-9A-F]{9}000$")
TRENDING_VIEWS = 500   # last month's views below which the trend says nothing
VIEWED = 400           # the games whose views are asked, the most sitelinks first
PAUSE = 0.25           # seconds between two of them
UPCOMING_DAYS = 365    # how far ahead upcoming.json looks
MAX_WAIT = 1800        # seconds a rate-limited service is waited for, at most
GUARD_KEEP = 0.7       # a file with fewer games than this share of the last run's is not published
GUARD_FLOOR = 50       # games the last run's file had at least, for that to count


def fetch(url, tries=4, patient=True, timeout=120):
    """`url`'s JSON answer; None for a 404. A 429 waits as long as the
    service says (`patient`) or is raised at once."""
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == tries - 1 or (e.code == 429 and not patient):
                raise
            if e.code == 429:
                wait = max(int(e.headers.get("Retry-After", "60") or 60), 60) + 5
                if wait > MAX_WAIT:
                    raise
                print(f"{url.split('?')[0]}: rate-limited, again in {wait} s", file=sys.stderr)
                time.sleep(wait)
                continue
        except (urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                raise
        time.sleep(2 ** attempt)
    return None


def sparql(query):
    body = fetch(SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"}))
    return body["results"]["bindings"]


def base_id(value):
    """A base game's title id, upper case, or None."""
    tid = (value or "").strip().upper()
    return tid if TID.match(tid) else None


def games(bindings):
    """{title id: (sitelinks, English article or None)}, the most sitelinks of an item's ids."""
    out = {}
    for b in bindings:
        tid = base_id(b["tid"]["value"])
        if not tid:
            continue
        links = int(b["links"]["value"])
        article = urllib.parse.unquote(b["article"]["value"].rsplit("/wiki/", 1)[-1]) if "article" in b else None
        old = out.get(tid)
        if not old or links > old[0] or (links == old[0] and article and not old[1]):
            out[tid] = (links, article or (old[1] if old else None))
    return out


def score_of(text):
    """A critics' score as Wikidata writes it ("84%", "8.5/10", "80/100") on 0..100, or None."""
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(%|/\s*([0-9]+(?:\.[0-9]+)?))?\s*$", text or "")
    if not m:
        return None
    value = float(m.group(1))
    if m.group(2) == "%":
        top = 100.0
    elif m.group(3):
        top = float(m.group(3))
    else:
        return None
    if top <= 0 or value < 0 or value > top:
        return None
    return value * 100.0 / top


def count_of(text):
    """A number of reviews; 0 for Wikidata's "unknown value" (a blank node's
    address) or anything else that is not a number."""
    try:
        return max(0, int(float(text)))
    except (TypeError, ValueError, OverflowError):
        return 0


def reviews(bindings):
    """{title id: (reviews, critics' score)}: the most reviews any of its
    scores counts, and the score that counts the most reviews."""
    out = {}
    for b in bindings:
        tid = base_id(b["tid"]["value"])
        score = score_of(b["score"]["value"]) if "score" in b else None
        if not tid or score is None:
            continue
        count = count_of(b["count"]["value"]) if "count" in b else 0
        old = out.get(tid, (0, 0.0))
        if count > old[0] or (old[1] == 0 and count == old[0]):
            out[tid] = (count, score)
    return out


def months(today):
    """The first days of the last three whole months, oldest first, and the end of the last."""
    first = today.replace(day=1)
    starts = []
    for _ in range(3):
        first = (first - datetime.timedelta(days=1)).replace(day=1)
        starts.insert(0, first)
    return starts, today.replace(day=1) - datetime.timedelta(days=1)


def views(article, starts, end):
    """The article's views in each of `starts`' months (0 for none)."""
    url = VIEWS.format(article=urllib.parse.quote(article.replace(" ", "_"), safe=""),
                       start=starts[0].strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    body = fetch(url, tries=2, patient=False, timeout=30)
    counts = {item["timestamp"][:6]: item["views"] for item in (body or {}).get("items", [])}
    return [counts.get(s.strftime("%Y%m"), 0) for s in starts]


def read_views(known, starts, end):
    """{article: [views a month]} for the best known games; {} when Wikimedia turned too many away."""
    best = sorted(((links, a) for links, a in known.values() if a), reverse=True)[:VIEWED]
    read, refused = {}, 0
    for _, article in best:
        if article in read:
            continue
        try:
            read[article] = views(article, starts, end)
        except urllib.error.HTTPError as e:
            refused += 1
            if refused >= 3:
                print(f"views: refused ({e.code}) after {len(read)}", file=sys.stderr)
                break
            time.sleep(30)
            continue
        time.sleep(PAUSE)
    if len(read) < len(best) // 2:
        print(f"views: {len(read)} of {len(best)} read, too few: none used", file=sys.stderr)
        return {}
    print(f"views: {len(read)} of {len(best)} read", file=sys.stderr)
    return read


def scale(value, most):
    return math.log1p(value) / math.log1p(most) if most > 0 else 0.0


def popular(known, critics, read, steam=None, igdb_popularity=None):
    """{title id: [score, trend, critics' score]}, the games scored above 0."""
    steam = steam or {}
    igdb_popularity = igdb_popularity or {}
    most_steam = max((s["positive"] + s["negative"] for s in steam.values()), default=0)
    most_links = max((links for links, _ in known.values()), default=1)
    most_reviews = max((n for n, _ in critics.values()), default=1)
    most_views = max([c[-1] for c in read.values()] + [1])
    table = {}
    for tid, (links, article) in sorted(known.items()):
        reviewed, critic = critics.get(tid, (0, 0.0))
        counts = read.get(article) if article else None
        if read:
            # Views read: they weigh most; a game whose page was not read
            # (not among the best known) has none.
            last = counts[-1] if counts else 0
            score = 0.3 * scale(links, most_links) + 0.2 * scale(reviewed, most_reviews) + 0.5 * scale(last, most_views)
        else:
            score = 0.6 * scale(links, most_links) + 0.4 * scale(reviewed, most_reviews)
        # Its Steam audience, for a game also sold there: a lift, never a cost.
        score = max(score, 0.75 * score + 0.25 * features.steam_scale(steam, tid, most_steam))
        # Its popularity on IGDB, the same way.
        score = max(score, 0.75 * score + 0.25 * igdb_popularity.get(tid, 0.0))
        trend = 0
        if counts:
            before = (counts[0] + counts[1]) / 2
            if counts[-1] >= TRENDING_VIEWS and before > 0:
                trend = max(-100, min(999, round((counts[-1] - before) * 100 / before)))
        if round(score * 100) > 0:
            table[tid] = [round(score * 100), trend, round(critic)]
    return table


def upcoming(titles, today, days=UPCOMING_DAYS, hypes=None):
    """{title id: [YYYYMMDD, name]} of titledb's base games out after `today`
    and within `days`, [YYYYMMDD, name, hypes] for one IGDB says is followed."""
    hypes = hypes or {}
    first = int(today.strftime("%Y%m%d"))
    last = int((today + datetime.timedelta(days=days)).strftime("%Y%m%d"))
    out = {}
    for entry in titles.values():
        tid = base_id(entry.get("id"))
        try:
            date = int(entry.get("releaseDate") or 0)
        except (TypeError, ValueError):
            continue
        name = (entry.get("name") or "").strip()
        if tid and name and first < date <= last and not entry.get("isDemo"):
            out[tid] = [date, name[:200]] + ([hypes[tid]] if hypes.get(tid) else [])
    return dict(sorted(out.items()))


def write(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"{path}: {len(payload['games'])} games", file=sys.stderr)


def count_in(path):
    """How many games a data file has, None when there is no such file (or not one of ours)."""
    try:
        with open(path, encoding="utf-8") as f:
            games_of = json.load(f).get("games")
        return len(games_of) if isinstance(games_of, dict) else None
    except (OSError, ValueError, AttributeError):
        return None


def publish(out_dir, name, payload, previous_dir, report):
    """`payload` written as out_dir/name, unless it has lost too many games
    against the last run's (a source down, not the world changed): then the
    last run's file is kept, and said. Each file's line goes in `report`."""
    path = os.path.join(out_dir, name)
    now = len(payload["games"])
    before = count_in(os.path.join(previous_dir, name)) if previous_dir else None
    kept = before is not None and before >= GUARD_FLOOR and now < before * GUARD_KEEP
    if kept:
        shutil.copyfile(os.path.join(previous_dir, name), path)
        print(f"::warning::{name}: {now} games against {before} last time, last run's file kept", file=sys.stderr)
        # For the run's alert (tools/alert.sh), when the workflow asks for one.
        if os.environ.get("ALERTS"):
            with open(os.environ["ALERTS"], "a", encoding="utf-8") as f:
                f.write(f"`{name}` came out with {now} games against {before} last time: the last run's file was kept.\n")
    else:
        write(path, payload)
    report.append((name, before, now, kept))
    return not kept


def summary(report, path=None):
    """The run's files against the last run's, as a Markdown table (for the workflow's summary)."""
    lines = ["| File | Last run | This run | Published |", "|---|---:|---:|---|"]
    for name, before, now, kept in report:
        change = "" if not before else f" ({(now - before) * 100 / before:+.0f} %)"
        lines.append(f"| `{name}` | {before if before is not None else '–'} | {now}{change} | "
                     f"{'no: last run kept' if kept else 'yes'} |")
    text = "\n".join(lines) + "\n"
    path = path or os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("### The data files\n\n" + text)
    return text


def previous_games(directory):
    """The last run's games.json's games, {} when there is none."""
    try:
        with open(os.path.join(directory, "games.json"), encoding="utf-8") as f:
            body = json.load(f)
        return body.get("games", {}) if body.get("schema") == 1 else {}
    except (OSError, ValueError, AttributeError):
        return {}


def read_igdb():
    """IGDB's traits, popularity and hypes; none without the keys, or when IGDB fails (the run goes on)."""
    nothing = {"traits": {}, "popularity": {}, "hypes": {}}
    client_id, secret = os.environ.get("IGDB_CLIENT_ID"), os.environ.get("IGDB_CLIENT_SECRET")
    if not client_id or not secret:
        print("igdb: no keys, left out", file=sys.stderr)
        return nothing
    try:
        by_slug = igdb.slugs(sparql(igdb.SLUG_QUERY), base_id)
        return igdb.read(igdb.Client(client_id, secret, AGENT), by_slug)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        print(f"igdb: {e}, left out", file=sys.stderr)
        return nothing


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "out"
    previous_dir = sys.argv[2] if len(sys.argv) > 2 else None
    before = previous_games(previous_dir) if previous_dir else {}
    report = []
    os.makedirs(out_dir, exist_ok=True)
    today = datetime.date.today()
    starts, end = months(today)

    rows = sparql(QUERY)
    known = games(rows)
    print(f"{len(known)} games with a Switch title id", file=sys.stderr)
    critics = reviews(rows)
    print(f"{len(critics)} with critics' scores", file=sys.stderr)
    read = read_views(known, starts, end)

    # The traits and the Steam audience, then the games alike.
    game_traits = features.traits(features.query_traits(sparql), base_id)
    found = read_igdb()
    for tid, kinds in found["traits"].items():
        game_traits.setdefault(tid, {}).update(kinds)
    apps = features.steam_ids(sparql(features.STEAM_QUERY), base_id)
    steam = features.read_steam(apps, {t: g["steam"] for t, g in before.items() if "steam" in g},
                                lambda url: fetch(url, tries=2, patient=False, timeout=30))
    table = {}
    for tid in sorted(set(game_traits) | set(steam)):
        entry = dict(game_traits.get(tid, {}))
        if tid in steam:
            entry["steam"] = steam[tid]
        table[tid] = entry
    publish(out_dir, "games.json", {
        "schema": 1, "generated": today.isoformat(),
        "source": "Wikidata (P179, P178, P123, P136, P404, P1733), SteamSpy" + (" and IGDB" if found["traits"] else ""),
        "games": table}, previous_dir, report)
    # The games alike: by their traits, then by what the eShop says of them
    # (titledb's names, descriptions, categories and publishers) for the
    # many games Wikidata knows nothing of.
    titles = fetch(TITLEDB, timeout=600) or {}
    by_text = text.similar(titles, base_id)
    # A game's other editions: one game, not one like it.
    of = editions.editions(titles, base_id)
    publish(out_dir, "similar.json", {
        "schema": 1, "generated": today.isoformat(),
        "source": "games.json's traits" + (" and titledb's descriptions" if by_text else ""),
        "games": editions.apart(text.merged(features.similar(game_traits), by_text), of)}, previous_dir, report)
    if of:
        publish(out_dir, "editions.json", {
            "schema": 1, "generated": today.isoformat(), "source": "blawar/titledb (US.en.json)",
            "games": of}, previous_dir, report)

    publish(out_dir, "popular.json", {
        "schema": 1, "generated": today.isoformat(), "month": starts[-1].strftime("%Y-%m"),
        "views": bool(read),
        "source": "Wikidata (P11072, sitelinks, P444 with P7887), Wikimedia pageviews (en.wikipedia), SteamSpy"
                  + (" and IGDB" if found["popularity"] else ""),
        "games": popular(known, critics, read, steam, found["popularity"])}, previous_dir, report)

    publish(out_dir, "upcoming.json", {
        "schema": 1, "generated": today.isoformat(),
        "source": "blawar/titledb (US.en.json)" + (" and IGDB" if found["hypes"] else ""),
        "games": upcoming(titles, today, hypes=found["hypes"])}, previous_dir, report)

    print(summary(report), file=sys.stderr)


if __name__ == "__main__":
    main()
