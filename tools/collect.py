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
    switch-igdb (P5794), steam (P1733), gog (P2725), xbox (P5885), links
    (every store's ids), retro (P400) and retro-<kind>;
  - daily: switch-pages (the best known Switch games' pages in LANGS).
- titledb (daily): blawar/titledb's US, GB and JP lists, by titledb's key.
- eshop (daily): prices/<country>.json, the eShop's answer by eShop id.
- steam-store: weekly apps.json (GetItems, by app id), tags.json,
  most-played.json; daily prices/<country>.json.
- steamspy (weekly): apps.json, its owners and players by app id.
- gog: catalog/<country>.json, the catalog's products by product id in its
  trending order (weekly: US; daily: every country).
- msstore: weekly products.json and gamepass.json; daily
  prices/<country>.json ([list price, MSRP] by product id).
- igdb (weekly, with its keys): games.json and popularity.json, IGDB's records.
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

import build
import common
import features
import gog
import igdb
import links
import prices
import retro
import steam
import steam_prices
import trends
import xbox

TITLEDB_REGIONS = ("US.en.json", "GB.en.json", "JP.ja.json")
TITLEDB_FIELDS = ("id", "nsuId", "name", "releaseDate", "isDemo", "publisher", "category", "intro", "description")
# The other regions' lists give the eShop's ids there (prices.eshop_ids): no need of their texts.
TITLEDB_SHORT = ("id", "nsuId", "name", "releaseDate", "isDemo")


def payload(name, today, source, licence, **records):
    return {"schema": 1, "source_id": name, "generated": today.isoformat(), "source": source,
            "license": licence, **records}


def wikidata_weekly():
    """[(file, rows)] of the weekly queries, in the order they are asked."""
    out = [("switch", lambda: common.sparql(build.QUERY))]
    for kind, (prop, _) in features.KINDS.items():
        out.append((f"switch-{kind}", lambda prop=prop: common.sparql(features.TRAIT_QUERY.format(prop=prop))))
    out += [("switch-steam", lambda: common.sparql(features.STEAM_QUERY)),
            ("switch-igdb", lambda: common.sparql(igdb.SLUG_QUERY)),
            ("steam", steam.wikidata_rows), ("gog", gog.wikidata_rows), ("xbox", xbox.wikidata_rows),
            ("links", links.rows), ("retro", lambda: retro.query(retro.GAMES))]
    for kind in retro.KINDS:
        out.append((f"retro-{kind}", lambda kind=kind: retro.query(
            retro.TRAITS.replace("{prop}", features.KINDS[kind][0]))))
    return out


def collect_wikidata(what, out_dir, previous_dir, fresh, today, report):
    if what == "weekly":
        asked = wikidata_weekly()
    else:
        popular = common.previous_file(previous_dir, f"platforms/{build.SWITCH}/popular.json").get("games") or {}
        top = [tid for tid, _ in sorted(popular.items(), key=lambda kv: -kv[1][0])[:trends.TOP]]

        def pages():
            rows = []
            for i in range(0, len(top), trends.BATCH):
                if i:
                    time.sleep(5)
                rows += common.sparql(trends.pages_query(top[i:i + trends.BATCH]))
            return rows
        asked = [("switch-pages", pages)]
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
        titles = common.fetch(prices.TITLEDB.format(file=file), timeout=600) or {}
        fields = TITLEDB_FIELDS if file.startswith("US.") else TITLEDB_SHORT
        games = {}
        for key, entry in titles.items():
            if isinstance(entry, dict):
                games[key] = {f: entry[f] for f in fields if entry.get(f) is not None}
        region = file.split(".")[0]
        common.publish_source(out_dir, f"{common.SOURCES}/titledb/{region}.json", payload(
            "titledb", today, f"blawar/titledb ({file})", "as published by blawar/titledb", file=file, games=games),
            previous_dir, report)


def read_eshop(country, nsus, fetch, workers=prices.WORKERS, pause=prices.PAUSE):
    """{eShop id: {status, regular, discount, until, currency}} of the eShop's
    answers for `nsus`, in the order they came (prices.read_country's)."""
    import concurrent.futures
    numbers = sorted(nsus)
    batches = [numbers[i:i + prices.BATCH] for i in range(0, len(numbers), prices.BATCH)]

    def ask(batch):
        time.sleep(pause)
        try:
            body = fetch(prices.PRICE.format(country=country, ids=",".join(map(str, batch))))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"eshop: {country}: {e}", file=sys.stderr)
            return []
        rows = []
        for p in (body or {}).get("prices", []):
            if p.get("title_id") is None:
                continue
            discount = p.get("discount_price")
            rows.append((str(p["title_id"]), {
                "status": p.get("sales_status"), "regular": prices.amount(p.get("regular_price")),
                "currency": (p.get("regular_price") or {}).get("currency"),
                "discount": prices.amount(discount) if discount else None,
                "until": prices.day_of(discount.get("end_datetime")) if discount else 0}))
        return rows

    out = {}
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for rows in pool.map(ask, batches):
            for nsu, row in rows:
                out.setdefault(nsu, row)
    return out


def collect_eshop(what, out_dir, previous_dir, fresh, today, report):
    fetch = lambda url: common.fetch(url, tries=3, patient=False, timeout=60)   # noqa: E731
    for file, countries in prices.REGIONS.items():
        region = file.split(".")[0]
        titles = common.source(f"{common.SOURCES}/titledb/{region}.json", *fresh, previous_dir).get("games") or {}
        ids = prices.eshop_ids(titles, build.base_id)
        print(f"eshop: {file}: {len(ids)} games with an eShop id", file=sys.stderr)
        for country in countries:
            common.publish_source(out_dir, f"{common.SOURCES}/eshop/prices/{country}.json", payload(
                "eshop", today, "Nintendo eShop's prices (api.ec.nintendo.com)", "Nintendo's terms of use",
                country=country, region=file, games=read_eshop(country, ids, fetch)), previous_dir, report)


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
    if "best_purchase_option" in item:
        option = item["best_purchase_option"] or {}
        out["best_purchase_option"] = {f: option[f] for f in (
            "final_price_in_cents", "original_price_in_cents", "active_discounts", "lowest_recent_price_in_cents")
            if f in option}
    return out


def collect_steam_store(what, out_dir, previous_dir, fresh, today, report):
    fetch = lambda url: common.fetch(url, tries=3, patient=False, timeout=60)   # noqa: E731
    store = "Steam's store (api.steampowered.com)"
    terms = "Steam's terms of use (Valve)"
    if what == "weekly":
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
        return
    games = common.previous_file(previous_dir, f"platforms/{steam.STEAM}/games.json").get("games") or {}
    if not games:
        print("steam-store prices: no steam/games.json in the last run's files, nothing to ask", file=sys.stderr)
        return
    for country in steam_prices.COUNTRIES:
        items = steam_prices.read_items(country, games, fetch)
        common.publish_source(out_dir, f"{common.SOURCES}/steam-store/prices/{country}.json", payload(
            "steam-store", today, store + ": IStoreBrowseService/GetItems", terms, country=country,
            games={app: steam_item(item) for app, item in items.items()}), previous_dir, report)


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
              "developers", "publishers", "genres", "tags", "price")


def collect_gog(what, out_dir, previous_dir, fresh, today, report):
    fetch = lambda url: common.fetch(url, tries=3, patient=False, timeout=60)   # noqa: E731
    for country in (["US"] if what == "weekly" else list(gog.COUNTRIES)):
        found = gog.read_catalog(country, fetch)
        games = {str(p["id"]): {f: p[f] for f in GOG_FIELDS if f in p} for p, _ in found}
        common.publish_source(out_dir, f"{common.SOURCES}/gog/catalog/{country}.json", payload(
            "gog", today, "GOG's catalog (catalog.gog.com), in its trending order", "GOG's terms of use",
            country=country, currency=gog.COUNTRIES[country], games=games), previous_dir, report)


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
    if what == "weekly":
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
        return
    games = common.previous_file(previous_dir, f"platforms/{xbox.XBOX}/games.json").get("games") or {}
    if not games:
        print("msstore prices: no xbox/games.json in the last run's files, nothing to ask", file=sys.stderr)
        return
    for country, currency in xbox.COUNTRIES.items():
        found = xbox.read_products(games, country, fetch, template="browse")
        rows = {}
        for pid, product in found.items():
            got = xbox.purchase(product)
            rows[pid] = list(got) if got else None
        common.publish_source(out_dir, f"{base}/prices/{country}.json", payload(
            "msstore", today, store, terms, country=country, currency=currency, games=rows), previous_dir, report)


def collect_igdb(what, out_dir, previous_dir, fresh, today, report):
    client_id, secret = os.environ.get("IGDB_CLIENT_ID"), os.environ.get("IGDB_CLIENT_SECRET")
    if not client_id or not secret:
        print("igdb: no keys, nothing asked", file=sys.stderr)
        return
    rows = common.bindings(common.source(f"{common.SOURCES}/wikidata/switch-igdb.json", *fresh).get("rows") or [])
    by_slug = igdb.slugs(rows, build.base_id)
    client = igdb.Client(client_id, secret, common.AGENT)
    records = []
    names = sorted(by_slug)
    for i in range(0, len(names), igdb.BATCH):
        records += client.query("games", igdb.games_query(names[i:i + igdb.BATCH]))
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


def monthly_wanted(fresh, previous_dir):
    """The English pages whose monthly views a platform's popular.json
    weighs: each platform's best known (build.read_views's choice), in turn."""
    import retro as retro_
    src = lambda name: common.source(f"{common.SOURCES}/{name}", *fresh, previous_dir)   # noqa: E731
    wanted = []
    for known in (build.views_known(src), steam.views_known(src), gog.views_known(src), xbox.views_known(src),
                  retro_.views_known(src)):
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
    rows = common.bindings(common.source(f"{common.SOURCES}/wikidata/switch-pages.json", *fresh).get("rows") or [])
    by_game = trends.pages(rows, build.base_id)
    start, end = trends.window(today)
    read = trends.fetch_daily(by_game, start, end, lambda url: common.fetch(url, tries=2, patient=False, timeout=30))
    common.publish_source(out_dir, f"{common.SOURCES}/wikipedia/daily.json", payload(
        "wikipedia", today, "Wikimedia pageviews (" + ", ".join(f"{l}.wikipedia" for l in trends.LANGS) + ", daily)",
        licence, start=start.isoformat(), end=end.isoformat(), pages=read), previous_dir, report)


COLLECTORS = {"wikidata": collect_wikidata, "titledb": collect_titledb, "eshop": collect_eshop,
              "steam-store": collect_steam_store, "steamspy": collect_steamspy, "gog": collect_gog,
              "msstore": collect_msstore, "igdb": collect_igdb, "wikipedia": collect_wikipedia}


def main():
    name, what, out_dir, previous_dir = sys.argv[1:5]
    fresh = sys.argv[5:]
    report = []
    common.timed(out_dir, f"collect {name} {what}",
                 lambda: COLLECTORS[name](what, out_dir, previous_dir, fresh, datetime.date.today(), report))
    print(common.summary(report), file=sys.stderr)


if __name__ == "__main__":
    main()
