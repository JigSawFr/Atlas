#!/usr/bin/env python3
"""Builds Atlas' data files, by Nintendo Switch title id, from open
sources that need no key:

- switch/popular.json: how well known each game is (a score from 0 to 100),
  whether it is read more lately (a trend, in percent) and what the critics
  gave it (0 to 100, 0 when unknown);
- switch/upcoming.json: the games whose release date is still to come, with
  their name and date (and how many follow them on IGDB, when known);
- switch/games.json: each game's traits (series, developers, publishers,
  genres, modes) and, for one also sold on Steam, its Steam audience;
- switch/editions.json: a game's other editions (a Deluxe, a Complete
  Edition…), each with the game it is one of (tools/editions.py);
- switch/similar.json: the games most like each one, by their traits
  (tools/features.py), and for the others by what the eShop says of them
  (tools/text.py).

The sources:

- Wikidata: the games with a Switch title id (P11072), how many Wikipedias
  have a page on each (sitelinks), their English page, and their critics'
  scores (P444) with the number of reviews behind each (P7887);
- Wikimedia's pageviews: how often each English page was read in each of the
  last three whole months, for the best known games (VIEWED);
- blawar/titledb's US eShop list: the release dates, for upcoming.json;
- Steam's store (tools/steam.py): the reviews of the games also on Steam,
  all of them every run; SteamSpy: their owners and players
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

Every source is asked beforehand (tools/collect.py), its answers kept in
sources/; this makes the files from them, asking nothing.

Usage: tools/build.py <out-dir> <previous-dir> <sources-dir>   (writes out-dir/switch/;
previous-dir: the last run's files, whose SteamSpy figures are kept for the
games not asked; sources-dir: this run's sources, else the last run's)
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse

import common
import editions
import features
import igdb
import text
# Shared with the other tools, which read them here too.
from common import (AGENT, GUARD_FLOOR, GUARD_KEEP, MAX_WAIT, SPARQL, count_in, fetch,  # noqa: F401
                    publish, scale, sparql, summary, write)

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
SWITCH = "switch"      # the folder of the Switch's files, in the data branch






def base_id(value):
    """A base game's title id, upper case, or None."""
    tid = (value or "").strip().upper()
    return tid if TID.match(tid) else None


def games(bindings, ident=None):
    """{title id: (sitelinks, English article or None)}, the most sitelinks of
    an item's ids; `ident` reads another platform's ids (base_id: the Switch's)."""
    ident = ident or base_id
    out = {}
    for b in bindings:
        tid = ident(b["tid"]["value"])
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


def reviews(bindings, ident=None):
    """{title id: (reviews, critics' score)}: the most reviews any of its
    scores counts, and the score that counts the most reviews."""
    ident = ident or base_id
    out = {}
    for b in bindings:
        tid = ident(b["tid"]["value"])
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


def best_articles(known):
    """The English pages whose views are asked: the VIEWED best known games' (most sitelinks first)."""
    return [a for _, a in sorted(((links, a) for links, a in known.values() if a), reverse=True)[:VIEWED]]


def fetch_views(articles, starts, end):
    """{article: [views a month]} of `articles`, asked in turn; after three
    refusals from Wikimedia, no more (the ones read so far kept)."""
    read, refused = {}, 0
    for article in articles:
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
    return read


def views_from(known, pages):
    """{article: [views a month]} for the best known games of `known`, from
    the views collected (sources/wikipedia/monthly.json); {} when fewer than
    half of them could be read (no mixing of scales)."""
    best = best_articles(known)
    read = {a: pages[a] for a in best if a in pages}
    if len(read) < len(best) // 2:
        print(f"views: {len(read)} of {len(best)} read, too few: none used", file=sys.stderr)
        return {}
    print(f"views: {len(read)} of {len(best)} read", file=sys.stderr)
    return read


def read_views(known, starts, end):
    """{article: [views a month]} for the best known games; {} when Wikimedia turned too many away."""
    best = best_articles(known)
    return views_from(known, fetch_views(best, starts, end))


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










def previous_games(directory):
    """The last run's games.json's games, {} when there is none."""
    try:
        with open(os.path.join(directory, "platforms", SWITCH, "games.json"), encoding="utf-8") as f:
            body = json.load(f)
        return body.get("games", {}) if body.get("schema") == 1 else {}
    except (OSError, ValueError, AttributeError):
        return {}


def igdb_found(src):
    """IGDB's traits, popularity, hypes and ratings from its collected records; none without them."""
    rows = common.bindings(src("wikidata/switch-igdb.json").get("rows") or [])
    games_, popularity = src("igdb/games.json").get("items"), src("igdb/popularity.json").get("items")
    if not games_ or not rows:
        return {"traits": {}, "popularity": {}, "hypes": {}, "ratings": {}}
    by_slug = igdb.slugs(rows, base_id)
    ids, traits, hypes = igdb.read_games(games_, by_slug)
    return {"traits": traits, "popularity": igdb.read_popularity(popularity or [], ids), "hypes": hypes,
            "ratings": igdb.read_ratings(games_, by_slug)}


def names_of(src):
    """{title id: name} of every base game titledb knows (not a demo), the US
    list's name first, else the British one's, else the Japanese one's."""
    out = {}
    for region in ("US", "GB", "JP"):
        for entry in (src(f"titledb/{region}.json").get("games") or {}).values():
            tid = base_id(entry.get("id"))
            name = (entry.get("name") or "").strip()
            if tid and name and tid not in out and entry.get("isDemo") not in (True, "True"):
                out[tid] = name[:200]
    return out


def views_known(src):
    """{title id: (sitelinks, English page)}, the games whose views count."""
    return games(common.bindings(src("wikidata/switch.json").get("rows") or []))


def steam_figures(src, apps, before):
    """Each game's Steam figures: its store's reviews, SteamSpy's owners and
    players (as asked this run, the others' kept from `before`)."""
    items = src("steam-store/apps.json").get("games") or {}
    store_reviews = {tid: features.reviews_of(items.get(str(app))) for tid, app in apps.items()}
    spy = src("steamspy/apps.json").get("games") or {}
    previous = {t: g["steam"] for t, g in before.items() if "steam" in g}
    spied = {}
    for tid, app in apps.items():
        got = features.steam_of(spy.get(str(app)))
        if got:
            got["app"] = app
            spied[tid] = got
    for tid in apps:
        if tid not in spied and tid in previous and previous[tid].get("app") == apps[tid]:
            spied[tid] = previous[tid]
    return features.with_reviews(spied, {tid: r for tid, r in store_reviews.items() if r}, apps)


def consolidate(src, out_dir, previous_dir, today):
    """switch/'s weekly files from the sources collected (tools/collect.py)."""
    before = previous_games(previous_dir) if previous_dir else {}
    report = []
    starts, end = months(today)
    rows = common.bindings(src("wikidata/switch.json").get("rows") or [])
    known = games(rows)
    print(f"{len(known)} games with a Switch title id", file=sys.stderr)
    critics = reviews(rows)
    print(f"{len(critics)} with critics' scores", file=sys.stderr)
    read = views_from(known, src("wikipedia/monthly.json").get("pages") or {})

    # The traits and the Steam audience, then the games alike.
    game_traits = features.traits({kind: common.bindings(src(f"wikidata/switch-{kind}.json").get("rows") or [])
                                   for kind in features.KINDS}, base_id)
    found = igdb_found(src)
    for tid, kinds in found["traits"].items():
        game_traits.setdefault(tid, {}).update(kinds)
    apps = features.steam_ids(common.bindings(src("wikidata/switch-steam.json").get("rows") or []), base_id)
    steam = steam_figures(src, apps, before)
    # Every game's name (titledb's), and every game titledb knows, even with nothing else.
    names = names_of(src)
    table = {}
    for tid in sorted(set(game_traits) | set(steam) | set(found["ratings"]) | set(names)):
        entry = {"name": names[tid]} if tid in names else {}
        entry.update(game_traits.get(tid, {}))
        if tid in found["ratings"]:
            entry["igdb_rating"] = found["ratings"][tid]
        if tid in steam:
            entry["steam"] = steam[tid]
        table[tid] = entry
    publish(out_dir, f"platforms/{SWITCH}/games.json", {
        "schema": 1, "platform": SWITCH, "generated": today.isoformat(),
        "source": "blawar/titledb (names), Wikidata (P179, P178, P123, P136, P404, P1733), Steam's store, SteamSpy"
                  + (" and IGDB" if found["traits"] else ""),
        "games": table}, previous_dir, report)
    # The games alike: by their traits, then by what the eShop says of them
    # (titledb's names, descriptions, categories and publishers) for the
    # many games Wikidata knows nothing of.
    titles = src("titledb/US.json").get("games") or {}
    by_text = text.similar(titles, base_id)
    # A game's other editions: one game, not one like it.
    of = editions.editions(titles, base_id)
    publish(out_dir, f"platforms/{SWITCH}/similar.json", {
        "schema": 1, "platform": SWITCH, "generated": today.isoformat(),
        "source": "games.json's traits" + (" and titledb's descriptions" if by_text else ""),
        "games": editions.apart(text.merged(features.similar(game_traits), by_text), of)}, previous_dir, report)
    if of:
        publish(out_dir, f"platforms/{SWITCH}/editions.json", {
            "schema": 1, "platform": SWITCH, "generated": today.isoformat(), "source": "blawar/titledb (US.en.json)",
            "games": of}, previous_dir, report)

    publish(out_dir, f"platforms/{SWITCH}/popular.json", {
        "schema": 1, "platform": SWITCH, "generated": today.isoformat(), "month": starts[-1].strftime("%Y-%m"),
        "views": bool(read),
        "source": "Wikidata (P11072, sitelinks, P444 with P7887), Wikimedia pageviews (en.wikipedia), Steam's store"
                  + (" and IGDB" if found["popularity"] else ""),
        "games": popular(known, critics, read, steam, found["popularity"])}, previous_dir, report)

    publish(out_dir, f"platforms/{SWITCH}/upcoming.json", {
        "schema": 1, "platform": SWITCH, "generated": today.isoformat(),
        "source": "blawar/titledb (US.en.json)" + (" and IGDB" if found["hypes"] else ""),
        "games": upcoming(titles, today, hypes=found["hypes"])}, previous_dir, report)

    print(summary(report), file=sys.stderr)


def main():
    out_dir, previous_dir, sources_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    consolidate(common.reader(sources_dir, previous_dir), out_dir, previous_dir, datetime.date.today())


if __name__ == "__main__":
    main()
