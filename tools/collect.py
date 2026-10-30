#!/usr/bin/env python3
"""Each source asked once, its answers kept as they are (only what Atlas
uses, normalized) in sources/<source>/, keyed by the source's own ids; the
platforms' files are then made from these (each platform's tool), without
asking anything more. A source's file has its own guard: one that has lost
too many records against the last run's is not published, the last run's
is kept and said (common.publish_source).

- wikidata: the queries' rows, {variable: value}, a file a query:
  - weekly: switch (P11072, sitelinks, English page, critics), switch-<kind>
    (series, developers, publishers, genres, modes), switch-steam (P1733),
    switch-igdb (P5794), others-igdb (P5794 of every other platform's
    games), steam (P1733), gog (P2725), xbox (P5885), links
    (every store's ids), retro (P400) and retro-<kind>, playstation (the
    PS4's and PS5's games, P400), playstation-<kind> (their series,
    developers, publishers, genres, modes) and playstation-dates (P577), 3ds
    (the 3DS's games' Japanese labels, English aliases, dates and GameTDB
    codes, for tools/n3ds.py's match);
  - daily: switch-pages (the best known Switch games' pages in LANGS).
- titledb (weekly): blawar/titledb's US, GB and JP lists, by titledb's key.
- steam-store (weekly): apps.json (GetItems, by app id), tags.json,
  most-played.json.
- steamspy (weekly): apps.json, its owners and players by app id.
- gog (weekly): catalog/US.json, the catalog's products by product id in its
  trending order.
- msstore (weekly): products.json and gamepass.json.
- igdb (weekly, with its keys): games.json and popularity.json, IGDB's records
  of the Switch's games; others.json, of every other platform's games
  Wikidata links to IGDB (tools/igdb.py).
- nlib-ctr (weekly): Nlib API's 3DS lists of title ids (categories.json)
  and its base games' names, regions and product codes (titles.json, each
  asked once: tools/n3ds.py).
- wikipedia: weekly monthly.json (the best known games' English pages'
  views a month), daily daily.json (their pages' views a day, LANGS).

Usage: tools/collect.py <source> weekly|daily <out-dir> <previous-dir> [fresh-dir…]
  (fresh-dir: this run's collected sources a source needs, e.g. wikidata's)
"""
import datetime
import os
import sys
import time
import urllib.error
import zlib

import build
import common
import features
import gog
import igdb
import links
import n3ds
import playstation
import retro
import steam
import trends
import xbox

TITLEDB_REGIONS = ("US.en.json", "GB.en.json", "JP.ja.json")
TITLEDB = "https://raw.githubusercontent.com/blawar/titledb/master/{file}"
TITLEDB_FIELDS = ("id", "name", "releaseDate", "isDemo", "publisher", "category", "intro", "description")
# The other regions' lists give the names the US one lacks: no need of their texts.
TITLEDB_SHORT = ("id", "name", "releaseDate", "isDemo")


def payload(name, today, source, licence, **records):
    return {"source_id": name, "generated": today.isoformat(), "source": source,
            "license": licence, **records, "schema": common.SOURCE_SCHEMA}


def wikidata_weekly():
    """[(file, rows)] of the weekly queries, in the order they are asked."""
    out = [("switch", lambda: common.sparql(build.QUERY))]
    for kind, (prop, _) in features.KINDS.items():
        out.append((f"switch-{kind}", lambda prop=prop: common.sparql(features.TRAIT_QUERY.format(prop=prop))))
    out += [("switch-steam", lambda: common.sparql(features.STEAM_QUERY)),
            ("switch-igdb", lambda: common.sparql(igdb.SLUG_QUERY)),
            ("others-igdb", lambda: common.sparql(igdb.others_query(retro.PLATFORMS + playstation.ITEMS))),
            ("steam", steam.wikidata_rows), ("gog", gog.wikidata_rows), ("xbox", xbox.wikidata_rows),
            ("links", links.rows), ("retro", lambda: retro.query(retro.GAMES))]
    for kind in retro.KINDS:
        out.append((f"retro-{kind}", lambda kind=kind: retro.query(
            retro.TRAITS.replace("{prop}", features.KINDS[kind][0]))))
    out.append(("playstation", lambda: common.sparql(playstation.GAMES)))
    for kind in playstation.KINDS:
        out.append((f"playstation-{kind}", lambda kind=kind: common.sparql(playstation.query(kind))))
    out.append(("playstation-dates", lambda: common.sparql(playstation.DATES)))
    out.append(("3ds", lambda: common.sparql(n3ds.EXTRA)))
    return out


def collect_wikidata(what, out_dir, previous_dir, fresh, today, report):
    if what == "weekly":
        asked = wikidata_weekly()
    else:
        # Each platform's best known games' pages (tools/trends.py's PLATFORMS).
        def pages(platform, prop):
            best = trends.top(common.previous_file(previous_dir, f"platforms/{platform}/popular.json"))
            rows = []
            for i in range(0, len(best), trends.BATCH):
                if i:
                    time.sleep(5)
                rows += common.sparql(trends.pages_query(best[i:i + trends.BATCH], prop))
            return rows
        asked = [(f"{platform}-pages", lambda platform=platform, prop=prop: pages(platform, prop))
                 for platform, prop, _ in trends.PLATFORMS]
    for i, (name, ask) in enumerate(asked):
        if i:
            time.sleep(5)   # Wikidata's service may allow one query a minute: spaced
        try:
            rows = common.rows_of(ask())
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            print(f"wikidata: {name}: {e}, the last run's kept", file=sys.stderr)
            continue
        print(f"wikidata: {name}: {len(rows)} rows", file=sys.stderr)
        common.publish_source(out_dir, f"{common.SOURCES}/wikidata/{name}.json",
                              payload("wikidata", today, "Wikidata", "CC0-1.0", rows=rows), previous_dir, report)


def collect_titledb(what, out_dir, previous_dir, fresh, today, report):
    for file in TITLEDB_REGIONS:
        titles = common.fetch(TITLEDB.format(file=file), timeout=600) or {}
        fields = TITLEDB_FIELDS if file.startswith("US.") else TITLEDB_SHORT
        games = {}
        for key, entry in titles.items():
            if isinstance(entry, dict):
                games[key] = {f: entry[f] for f in fields if entry.get(f) is not None}
        region = file.split(".")[0]
        common.publish_source(out_dir, f"{common.SOURCES}/titledb/{region}.json", payload(
            "titledb", today, f"blawar/titledb ({file})", "as published by blawar/titledb", file=file, games=games),
            previous_dir, report)


STEAM_ITEM = {"basic_info": ("franchises", "developers", "publishers"),
              "reviews": ("summary_filtered",), "release": ("steam_release_date", "original_steam_release_date",
                                                            "is_coming_soon")}


def steam_item(item):
    """What Atlas keeps of a GetItems item (steam.entry's and features.reviews_of's fields)."""
    out = {k: item[k] for k in ("appid", "success", "type", "name", "is_free", "tagids") if k in item}
    for k, fields in STEAM_ITEM.items():
        part = item.get(k)
        if isinstance(part, dict):
            out[k] = {f: part[f] for f in fields if f in part}
    return out


def collect_steam_store(what, out_dir, previous_dir, fresh, today, report):
    fetch = lambda url: common.fetch(url, tries=3, patient=False, timeout=60)   # noqa: E731
    store = "Steam's store (api.steampowered.com)"
    terms = "Steam's terms of use (Valve)"
    rows = common.bindings(common.source(f"{common.SOURCES}/wikidata/steam.json", *fresh).get("rows") or [])
    switch_rows = common.bindings(common.source(f"{common.SOURCES}/wikidata/switch-steam.json", *fresh).get("rows") or [])
    known = build.games(rows, ident=steam.app_id)
    played = steam.most_played(fetch(steam.MOST_PLAYED))
    tags = steam.tag_names(fetch(steam.TAGS))
    switch_apps = {str(app) for app in features.steam_ids(switch_rows, build.base_id).values()}
    items = steam.read_items(set(known) | set(played) | switch_apps, fetch)
    base = f"{common.SOURCES}/steam-store"
    common.publish_source(out_dir, f"{base}/apps.json", payload(
        "steam-store", today, store + ": IStoreBrowseService/GetItems", terms,
        games={app: steam_item(item) for app, item in items.items()}), previous_dir, report)
    common.publish_source(out_dir, f"{base}/tags.json", payload(
        "steam-store", today, store + ": IStoreService/GetTagList", terms,
        items={str(k): v for k, v in tags.items()}), previous_dir, report)
    common.publish_source(out_dir, f"{base}/most-played.json", payload(
        "steam-store", today, store + ": ISteamChartsService/GetMostPlayedGames", terms, items=played),
        previous_dir, report)


def collect_steamspy(what, out_dir, previous_dir, fresh, today, report):
    rows = common.bindings(common.source(f"{common.SOURCES}/wikidata/switch-steam.json", *fresh).get("rows") or [])
    apps = features.steam_ids(rows, build.base_id)
    before = build.previous_games(previous_dir) if previous_dir else {}
    answers = {}

    def fetch(url):
        body = common.fetch(url, tries=2, patient=False, timeout=30)
        if isinstance(body, dict):
            app = url.rsplit("=", 1)[-1]
            answers[app] = {k: body[k] for k in ("positive", "negative", "owners", "ccu") if k in body}
        return body
    features.read_steam(apps, {t: g["steam"] for t, g in before.items() if "steam" in g}, fetch)
    common.publish_source(out_dir, f"{common.SOURCES}/steamspy/apps.json", payload(
        "steamspy", today, "SteamSpy (steamspy.com)", "SteamSpy's terms of use", games=answers),
        previous_dir, report)


GOG_FIELDS = ("id", "title", "slug", "releaseDate", "productType", "reviewsCount", "reviewsRating",
              "developers", "publishers", "genres", "tags")


def collect_gog(what, out_dir, previous_dir, fresh, today, report):
    fetch = lambda url: common.fetch(url, tries=3, patient=False, timeout=60)   # noqa: E731
    found = gog.read_catalog(fetch)
    games = {str(p["id"]): {f: p[f] for f in GOG_FIELDS if f in p} for p, _ in found}
    common.publish_source(out_dir, f"{common.SOURCES}/gog/catalog/US.json", payload(
        "gog", today, "GOG's catalog (catalog.gog.com), in its trending order", "GOG's terms of use",
        country="US", games=games), previous_dir, report)


def ms_product(p):
    """What Atlas keeps of the store's product (xbox.entry's fields)."""
    local = (p.get("LocalizedProperties") or [{}])[0]
    market = (p.get("MarketProperties") or [{}])[0]
    return {"ProductId": p.get("ProductId"), "ProductKind": p.get("ProductKind"),
            "LocalizedProperties": [{k: local[k] for k in ("ProductTitle", "DeveloperName", "PublisherName")
                                     if k in local}],
            "MarketProperties": [{k: market[k] for k in ("OriginalReleaseDate", "UsageData") if k in market}],
            "Properties": {"Categories": (p.get("Properties") or {}).get("Categories") or []}}


def collect_msstore(what, out_dir, previous_dir, fresh, today, report):
    fetch = lambda url: common.fetch(url, tries=3, patient=False, timeout=120)   # noqa: E731
    store = "Microsoft Store's catalog (displaycatalog.mp.microsoft.com)"
    terms = "Microsoft's terms of use"
    base = f"{common.SOURCES}/msstore"
    rows = common.bindings(common.source(f"{common.SOURCES}/wikidata/xbox.json", *fresh).get("rows") or [])
    known = build.games(rows, ident=xbox.big_id)
    gamepass = xbox.read_gamepass(fetch)
    found = xbox.read_products(set(known) | set(gamepass), "US", fetch)
    common.publish_source(out_dir, f"{base}/gamepass.json", payload(
        "msstore", today, "Game Pass's lists (catalog.gamepass.com: console, PC)", terms, games=gamepass),
        previous_dir, report)
    common.publish_source(out_dir, f"{base}/products.json", payload(
        "msstore", today, store, terms, country="US",
        games={pid: ms_product(p) for pid, p in found.items()}), previous_dir, report)


def collect_igdb(what, out_dir, previous_dir, fresh, today, report, client=None):
    client_id, secret = os.environ.get("IGDB_CLIENT_ID"), os.environ.get("IGDB_CLIENT_SECRET")
    if client is None and (not client_id or not secret):
        print("igdb: no keys, nothing asked", file=sys.stderr)
        return
    rows = common.bindings(common.source(f"{common.SOURCES}/wikidata/switch-igdb.json", *fresh).get("rows") or [])
    by_slug = igdb.slugs(rows, build.base_id)
    client = client or igdb.Client(client_id, secret, common.AGENT)
    records = igdb.read_records(client, sorted(by_slug))
    ids, _, _ = igdb.read_games(records, by_slug)
    found = []
    games = sorted(ids)
    step = igdb.BATCH // len(igdb.POPULARITY)
    for i in range(0, len(games), step):
        found += client.query("popularity_primitives", igdb.popularity_query(games[i:i + step]))
    terms = "IGDB's API terms (data from IGDB.com)"
    common.publish_source(out_dir, f"{common.SOURCES}/igdb/games.json", payload(
        "igdb", today, "IGDB (api.igdb.com: games)", terms, items=records), previous_dir, report)
    common.publish_source(out_dir, f"{common.SOURCES}/igdb/popularity.json", payload(
        "igdb", today, "IGDB (api.igdb.com: popularity_primitives)", terms, items=found), previous_dir, report)
    # Every other platform's games Wikidata links to IGDB: the new ones, and a
    # quarter of the known ones again (each every four weeks), the rest kept.
    rows = common.bindings(common.source(f"{common.SOURCES}/wikidata/others-igdb.json", *fresh).get("rows") or [])
    wanted = igdb.slugs(rows, retro.qid)
    kept = {r["slug"]: r for r in common.source(f"{common.SOURCES}/igdb/others.json", previous_dir).get("items") or []
            if isinstance(r, dict) and r.get("slug") in wanted}
    week = today.isocalendar()[1]
    asked = [n for n in sorted(wanted) if n not in kept or zlib.crc32(n.encode()) % igdb.REFRESH == week % igdb.REFRESH]
    got = {r["slug"]: r for r in igdb.read_records(client, asked, igdb.others_games_query)
           if isinstance(r, dict) and r.get("slug")}
    others = [got.get(n) or kept[n] for n in sorted(wanted) if n in got or n in kept]
    print(f"igdb: the other platforms' {len(wanted)} games, {len(asked)} asked, {len(others)} found", file=sys.stderr)
    common.publish_source(out_dir, f"{common.SOURCES}/igdb/others.json", payload(
        "igdb", today, "IGDB (api.igdb.com: games)", terms, items=others), previous_dir, report)


def monthly_wanted(fresh, previous_dir):
    """The English pages whose monthly views a platform's popular.json
    weighs: each platform's best known (build.read_views's choice), in turn."""
    import retro as retro_
    src = lambda name: common.source(f"{common.SOURCES}/{name}", *fresh, previous_dir)   # noqa: E731
    wanted = []
    for known in (build.views_known(src), steam.views_known(src), gog.views_known(src), xbox.views_known(src),
                  retro_.views_known(src), playstation.views_known(src)):
        for article in build.best_articles(known):
            if article not in wanted:
                wanted.append(article)
    return wanted


def collect_wikipedia(what, out_dir, previous_dir, fresh, today, report):
    licence = "CC0-1.0 (Wikimedia pageviews)"
    if what == "weekly":
        starts, end = build.months(today)
        read = build.fetch_views(monthly_wanted(fresh, previous_dir), starts, end)
        common.publish_source(out_dir, f"{common.SOURCES}/wikipedia/monthly.json", payload(
            "wikipedia", today, "Wikimedia pageviews (en.wikipedia, monthly)", licence,
            months=[s.strftime("%Y-%m") for s in starts], pages=read), previous_dir, report)
        return
    by_game = {}
    for platform, _, base_id in trends.PLATFORMS:
        rows = common.bindings(common.source(f"{common.SOURCES}/wikidata/{platform}-pages.json", *fresh).get("rows") or [])
        for game, langs in trends.pages(rows, base_id).items():
            by_game[f"{platform}:{game}"] = langs   # a page read once for both platforms' games
    start, end = trends.window(today)
    read = trends.fetch_daily(by_game, start, end, lambda url: common.fetch(url, tries=2, patient=False, timeout=30))
    common.publish_source(out_dir, f"{common.SOURCES}/wikipedia/daily.json", payload(
        "wikipedia", today, "Wikimedia pageviews (" + ", ".join(f"{l}.wikipedia" for l in trends.LANGS) + ", daily)",
        licence, start=start.isoformat(), end=end.isoformat(), pages=read), previous_dir, report)


def collect_nlib_ctr(what, out_dir, previous_dir, fresh, today, report):
    n3ds.collect(out_dir, previous_dir, fresh, today, report)


COLLECTORS = {"nlib-ctr": collect_nlib_ctr, "wikidata": collect_wikidata, "titledb": collect_titledb,
              "steam-store": collect_steam_store, "steamspy": collect_steamspy, "gog": collect_gog,
              "msstore": collect_msstore, "igdb": collect_igdb, "wikipedia": collect_wikipedia}


def main():
    source, what, out_dir, previous_dir = sys.argv[1:5]
    fresh = sys.argv[5:]
    if source not in COLLECTORS:
        sys.exit(f"collect: no source {source!r}")
    report = []
    common.timed(out_dir, f"collect {source} {what}",
                 lambda: COLLECTORS[source](what, out_dir, previous_dir, fresh, datetime.date.today(), report))
    print(common.summary(report), file=sys.stderr)


if __name__ == "__main__":
    main()
