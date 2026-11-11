#!/usr/bin/env python3
"""The PlayStation 4's and PlayStation 5's files, in platforms/ps4/ and
platforms/ps5/, every Monday, a game by Wikidata item (QID), from Wikidata
and Wikipedia alone (Wikidata's games of the machine: P400 = Q5014725, the
PS4; Q63184502, the PS5):

- games.json: each game's name, its first day on the machine (release,
  YYYYMMDD: the publication date, P577, said to the day: the one Wikidata
  gives for this machine, else the game's first one for every machine if
  the machine was out by then), its PlayStation Store ids as Wikidata
  gives them (ps: concept ids, P12332; ps_product: the products of the
  machine, P5944, P5971, P5999, CUSA… for the PS4, PPSA… for the PS5), and
  its traits (series, developers, publishers, genres, modes);
- popular.json: [score, trend, critics] as platforms/switch/popular.json,
  the game's renown on Wikipedia (its sitelinks, its English page's views
  for the 400 best known of both machines), weighed among the machine's
  games; critics 0;
- similar.json: the machine's games most like each one, by their traits;
- upcoming.json: the games whose first day is still to come, within a
  year, [YYYYMMDD, name].

No store's figures: nothing is asked of the PlayStation Store
nor of playstation.com, whose terms forbid collecting their data. The
store ids are Wikidata's (CC0), kept as plain identifiers; links.json ties
a game to its other platforms (Steam, Switch…) by its Wikidata item.

Usage: tools/playstation.py <out-dir> <previous-dir> <sources-dir>   (from
the sources tools/collect.py keeps: wikidata/playstation.json,
playstation-<kind>.json, playstation-dates.json,
wikidata/links.json, wikipedia/monthly.json)
"""
import datetime
import re
import sys

import build
import common
import features
import igdb
import links
import platforms
import retro

# The machines, by their folder: (Wikidata item, the prefix of its store products).
MACHINES = {"ps4": ("Q5014725", "CUSA"), "ps5": ("Q63184502", "PPSA")}
ITEMS = [item for item, _ in MACHINES.values()]
# The day each machine came out (its first sales anywhere): a date before is not the machine's.
LAUNCH = {"Q5014725": 20131115, "Q63184502": 20201112}
KINDS = tuple(features.KINDS)   # series, developers, genres, publishers, modes
GAMES = retro.games_query(ITEMS)
# A query a kind (one for all of them runs past the query service's minute).
TRAITS = retro.TRAITS_QUERY.replace("%s", retro.values(ITEMS))
DATES = retro.PREFIXES + """PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
SELECT DISTINCT ?tid ?date ?precision ?on WHERE {
  VALUES ?platform { %s }
  ?tid wdt:P400 ?platform; wdt:P31 wd:Q7889; p:P577 ?st.
  ?st psv:P577 ?v; wikibase:rank ?rank.
  FILTER(?rank != wikibase:DeprecatedRank)
  ?v wikibase:timeValue ?date; wikibase:timePrecision ?precision.
  OPTIONAL { ?st pq:P400 ?on. }
}""" % retro.values(ITEMS)
DAY_PRECISION = 11   # Wikidata's precision of a date said to the day
DATE = re.compile(r"^\+?(\d{4})-(\d{2})-(\d{2})T")


def query(kind):
    """TRAITS for one kind (features.KINDS': series, developers…)."""
    return TRAITS.replace("{prop}", features.KINDS[kind][0])


def traits_of(src):
    """{QID: {kind: [[QID, name]]}} from each kind's rows (wikidata/playstation-<kind>.json)."""
    return features.traits({kind: common.bindings(src(f"wikidata/playstation-{kind}.json").get("rows") or [])
                            for kind in KINDS}, retro.qid)


def releases(rows, item):
    """{QID: YYYYMMDD}: each game's date on the machine `item`, said to the day. The earliest of the statements
    that name this machine (the P400 qualifier) when there is one; else the earliest of the statements that name none
    (Wikidata's dates of the game, for every machine) that the machine existed for (LAUNCH): one before is the game's
    and not the machine's, and a game with no other has none. (The earliest of both used to be taken: a game's
    first date, from a phone or a computer, beat the PlayStation's own, and half of the PS5's games came out in
    the 2010s.)"""
    named, anywhere = {}, {}
    launch = LAUNCH.get(item, 0)
    for b in rows:
        game = retro.qid(b["tid"]["value"])
        on = retro.qid(b["on"]["value"]) if "on" in b else None
        m = DATE.match(b.get("date", {}).get("value", ""))
        try:
            precise = int(b.get("precision", {}).get("value", "0")) >= DAY_PRECISION
        except ValueError:
            precise = False
        if not game or not m or not precise or (on and on != item):
            continue
        day = int("".join(m.groups()))
        if day % 10000 and (on or day >= launch):       # a date for no machine, from before this one existed, is the game's
            kept = named if on else anywhere
            if game not in kept or day < kept[game]:
                kept[game] = day
    out = dict(anywhere)
    out.update(named)
    return out


def store_ids(ids, prefix):
    """The game's PlayStation Store ids for the machine: concepts (any), products of its prefix."""
    out = {}
    if ids.get("ps"):
        out["ps"] = ids["ps"]
    products = [p for p in ids.get("ps_product") or [] if p[7:11] == prefix]
    if products:
        out["ps_product"] = products
    return out


def upcoming(games, today, days=build.UPCOMING_DAYS):
    """{QID: [YYYYMMDD, name]} of the games out after `today` and within `days`."""
    first = int(today.strftime("%Y%m%d"))
    last = int((today + datetime.timedelta(days=days)).strftime("%Y%m%d"))
    return {g: [e["release"], e.get("name", "")] for g, e in games.items() if first < e.get("release", 0) <= last}


def machines_of(src):
    """{folder: {QID: games.json's entry}} from the sources collected."""
    rows = common.bindings(src("wikidata/playstation.json").get("rows") or [])
    found = retro.games_of(rows)
    traits = traits_of(src)
    dates = common.bindings(src("wikidata/playstation-dates.json").get("rows") or [])
    ids = links.links(common.bindings(src("wikidata/links.json").get("rows") or []))
    others = igdb.others(src)
    out = {}
    for pid, (item, prefix) in MACHINES.items():
        days = releases(dates, item)
        mine = {}
        for game, g in found.items():
            if all(p != item for p, _ in g["platforms"]):
                continue
            entry = {"name": g["name"]} if g["name"] else {}
            if game in days:
                entry["release"] = days[game]
            entry.update(store_ids(ids.get(game) or {}, prefix))
            entry.update({k: v for k, v in traits.get(game, {}).items() if k in KINDS})
            mine[game] = entry
        print(f"{pid}: IGDB's traits or rating for {igdb.complete(mine, others)} games", file=sys.stderr)
        out[pid] = mine
    return out


def machines_by_game(src):
    """{QID: [folder]}: the machines each game of Wikidata's is on (MACHINES' order)."""
    found = retro.games_of(common.bindings(src("wikidata/playstation.json").get("rows") or []))
    return {game: [pid for pid, (item, _) in MACHINES.items() if any(p == item for p, _ in g["platforms"])]
            for game, g in found.items()}


def views_known(src):
    return build.games(common.bindings(src("wikidata/playstation.json").get("rows") or []), ident=retro.qid)


def consolidate(src, out_dir, previous_dir, today):
    """platforms/ps4/ and platforms/ps5/ from the sources collected (tools/collect.py)."""
    report = []
    known = views_known(src)
    read = build.views_from(known, src("wikipedia/monthly.json").get("pages") or {})
    starts, _ = build.months(today)
    by_id = lambda d: dict(sorted(d.items(), key=lambda kv: int(kv[0][1:])))   # noqa: E731
    for pid, games in machines_of(src).items():
        print(f"{pid}: {len(games)} games", file=sys.stderr)
        if not games:
            continue

        def payload(source, entries, **extra):
            return {"schema": common.SCHEMA, "platform": pid, "generated": today.isoformat(), **extra, "source": source,
                    "games": entries}
        common.publish(out_dir, platforms.path(pid, "games.json"), payload(
            "Wikidata (P400, P577, P12332, P5944, P5971, P5999, P179, P178, P123, P136, P404)", by_id(games)),
            previous_dir, report)
        common.publish(out_dir, platforms.path(pid, "popular.json"), payload(
            "Wikidata (P400, sitelinks), Wikimedia pageviews (en.wikipedia)",
            by_id(build.popular({g: known[g] for g in games if g in known}, {}, read)),
            month=starts[-1].strftime("%Y-%m"), views=bool(read)), previous_dir, report)
        common.publish(out_dir, platforms.path(pid, "similar.json"), payload(
            f"platforms/{pid}/games.json's traits", by_id(features.similar(
                {g: {k: e[k] for k in KINDS if k in e} for g, e in games.items()}, max_shared=300))),
            previous_dir, report)
        common.publish(out_dir, platforms.path(pid, "upcoming.json"), payload(
            "Wikidata (P577)", by_id(upcoming(games, today))), previous_dir, report)
    print(common.summary(report), file=sys.stderr)


def main():
    out_dir, previous_dir, sources_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    common.timed(out_dir, "playstation", lambda: consolidate(common.reader(sources_dir, previous_dir), out_dir,
                                                              previous_dir, datetime.date.today()))


if __name__ == "__main__":
    main()
