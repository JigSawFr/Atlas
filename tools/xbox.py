#!/usr/bin/env python3
"""The Xbox and Microsoft Store's files, by Microsoft Store product id (its
"bigId", 12 characters, upper case), in xbox/:

- every Monday (build.yml), `tools/xbox.py catalog`:
  - xbox/popular.json: [score, trend, critics], as switch/popular.json:
    half the game's renown on Wikipedia (by the Wikidata item that gives its
    Microsoft Store id, P5885), half its players' ratings on the store; a
    game in the Game Pass lifted;
  - xbox/games.json: each game's name, release, players' rating, Game Pass,
    Wikidata item and traits (developers, publishers, genres);
  - xbox/gamepass.json: the games in the Game Pass, ["console", "pc"];
  - xbox/upcoming.json and xbox/similar.json;
- every day (daily.yml), `tools/xbox.py prices`: xbox/prices/<country>.json,
  [regular, sale, until, lowest, lowest_day] as switch/prices/, for the
  games of the last run's xbox/games.json (the store doesn't say when a sale
  ends in its short answer: `until` is 0).

The games are those Wikidata gives a Microsoft Store id (some 6,500) and the
Game Pass's (its public lists, console and PC); the Microsoft Store's
catalog (displaycatalog.mp.microsoft.com, no key) says which are games and
gives the rest, 200 a request.

Usage: tools/xbox.py catalog|prices <out-dir> <previous-dir> <sources-dir>
  (from the sources tools/collect.py keeps: msstore, wikidata, wikipedia)
"""
import concurrent.futures
import datetime
import re
import sys
import time
import urllib.error
import urllib.parse

import build
import common
import features

XBOX = "xbox"
PRODUCTS = ("https://displaycatalog.mp.microsoft.com/v7.0/products?bigIds={ids}&market={country}"
            "&languages=en-us&fieldsTemplate={template}")
GAMEPASS = "https://catalog.gamepass.com/sigls/v2?id={list}&language=en-us&market=US"
GAMEPASS_LISTS = {"console": "f6f1f99f-9b49-4ccd-b3bf-4d9767a77f5e", "pc": "fdd9e2a7-0fee-49f6-ad69-4354098401ff"}
COUNTRIES = {"US": "USD", "CA": "CAD", "MX": "MXN", "BR": "BRL", "GB": "GBP", "FR": "EUR", "DE": "EUR",
             "ES": "EUR", "IT": "EUR", "NL": "EUR", "PT": "EUR", "AU": "AUD", "JP": "JPY"}
QUERY = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
SELECT ?tid ?item ?links ?article ?score ?count WHERE {
  ?item wdt:P5885 ?tid; wikibase:sitelinks ?links.
  OPTIONAL { ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }
  OPTIONAL { ?item p:P444 ?statement. ?statement ps:P444 ?score. OPTIONAL { ?statement pq:P7887 ?count } }
}
"""
QLEVER = "https://qlever.dev/api/wikidata"
BIG_ID = re.compile(r"^[0-9A-Z]{12}$")
BATCH = 200
WORKERS = 3
PAUSE = 0.3
UPCOMING_DAYS = 365


def big_id(value):
    v = (value or "").strip().upper()
    return v if BIG_ID.match(v) else None


def read_products(ids, country, fetch, template="details", workers=WORKERS, pause=PAUSE):
    """{bigId: the store's product} of the ids it knows in `country`."""
    ids = sorted(ids)
    batches = [ids[i:i + BATCH] for i in range(0, len(ids), BATCH)]

    def ask(batch):
        time.sleep(pause)
        try:
            body = fetch(PRODUCTS.format(ids=",".join(batch), country=country, template=template))
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"xbox: {country}: {e}", file=sys.stderr)
            return []
        return (body or {}).get("Products") or []

    out = {}
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for products in pool.map(ask, batches):
            for p in products:
                pid = big_id(p.get("ProductId"))
                if pid:
                    out[pid] = p
    print(f"xbox: {country}: {len(out)} of {len(ids)} products known", file=sys.stderr)
    return out


def purchase(product):
    """The store's price of a product's first sku that can be bought: (list price, MSRP), or None."""
    for sku in product.get("DisplaySkuAvailabilities") or []:
        for a in sku.get("Availabilities") or []:
            if "Purchase" in (a.get("Actions") or []):
                price = ((a.get("OrderManagementData") or {}).get("Price")) or {}
                try:
                    return float(price.get("ListPrice")), float(price.get("MSRP"))
                except (TypeError, ValueError):
                    return None
    return None


def price_of(product):
    """[regular, sale, until] of a product, or None when it is free or not sold."""
    return row_of(purchase(product))


def row_of(got):
    """[regular, sale, until] of the store's (list price, MSRP), or None when free or not sold."""
    if not got or got[0] <= 0:
        return None
    sale, msrp = round(got[0], 2), round(got[1], 2)
    if msrp > sale:
        return [msrp, sale, 0]
    return [sale, 0, 0]


def rating(product):
    """[count, percent] of the store's players' ratings of all time, or None."""
    for usage in ((product.get("MarketProperties") or [{}])[0].get("UsageData")) or []:
        if usage.get("AggregateTimeSpan") == "AllTime" and usage.get("RatingCount"):
            return [int(usage["RatingCount"]), round(float(usage.get("AverageRating") or 0) * 20)]
    return None


def day_of(text):
    digits = (text or "")[:10].replace("-", "")
    return int(digits) if len(digits) == 8 and digits.isdigit() and not digits.startswith("1753") else 0


def entry(product, qid=None, gamepass=()):
    local = (product.get("LocalizedProperties") or [{}])[0]
    out = {"name": (local.get("ProductTitle") or "")[:200]}
    if qid:
        out["qid"] = qid
    day = day_of(((product.get("MarketProperties") or [{}])[0]).get("OriginalReleaseDate"))
    if day:
        out["release"] = day
    r = rating(product)
    if r:
        out["rating"] = r
    if gamepass:
        out["gamepass"] = sorted(gamepass)

    def named(kind, name):
        name = (name or "").strip()
        return [[f"{kind}:{name.lower()}", name[:120]]] if name else []
    categories = (product.get("Properties") or {}).get("Categories") or []
    traits = {"developers": named("name", local.get("DeveloperName")),
              "publishers": named("name", local.get("PublisherName")),
              "genres": [[f"genre:{c.lower()}", c] for c in categories if isinstance(c, str)][:features.MAX_TRAITS]}
    out.update({k: v for k, v in traits.items() if v})
    return out


def read_gamepass(fetch):
    """{bigId: ["console", "pc"]} of the Game Pass's public lists."""
    out = {}
    for name, sigl in GAMEPASS_LISTS.items():
        try:
            body = fetch(GAMEPASS.format(list=sigl)) or []
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"xbox: Game Pass {name}: {e}", file=sys.stderr)
            continue
        for row in body:
            pid = big_id((row or {}).get("id"))
            if pid:
                out.setdefault(pid, []).append(name)
    return out


def popular(known, critics, read, games):
    """{bigId: [score, trend, critics]}: half the renown on Wikipedia, half the
    store's ratings; a game in the Game Pass lifted."""
    wiki = build.popular(known, critics, read)
    most = max((g["rating"][0] for g in games.values() if "rating" in g), default=0)
    table = {}
    for pid, g in games.items():
        w = wiki.get(pid, [0, 0, 0])
        score = 0.5 * w[0] / 100 + 0.5 * common.scale(g["rating"][0] if "rating" in g else 0, most)
        if g.get("gamepass"):
            score = max(score, 0.75 * score + 0.25 * 0.5)
        if round(score * 100) > 0:
            table[pid] = [round(score * 100), w[1], w[2]]
    return dict(sorted(table.items()))


def wikidata_rows():
    try:
        return common.sparql(QUERY)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        print(f"xbox: Wikidata's service: {e}; QLever asked", file=sys.stderr)
        body = common.fetch(QLEVER + "?" + urllib.parse.urlencode({"query": QUERY}), tries=3, timeout=300,
                            headers={"Accept": "application/sparql-results+json"})
        return body["results"]["bindings"]


def known_of(src):
    rows = common.bindings(src("wikidata/xbox.json").get("rows") or [])
    return rows, build.games(rows, ident=big_id)


def store_games(src, rows, known):
    """{bigId: games.json entry} of the products collected that are games."""
    qids = {}
    for b in rows:
        pid = big_id(b["tid"]["value"])
        if pid and pid not in qids:
            qids[pid] = b["item"]["value"].rsplit("/", 1)[-1]
    gamepass = src("msstore/gamepass.json").get("games") or {}
    found = src("msstore/products.json").get("games") or {}
    return gamepass, {pid: entry(p, qids.get(pid), gamepass.get(pid, ())) for pid, p in found.items()
                      if p.get("ProductKind") == "Game" and (pid in known or pid in gamepass)}


def views_known(src):
    """{bigId: (sitelinks, English page)} of the games whose views count."""
    rows, known = known_of(src)
    _, games = store_games(src, rows, known)
    return {pid: known[pid] for pid in games if pid in known}


def catalog(src, out_dir, previous_dir, today):
    report = []
    rows, known = known_of(src)
    critics = build.reviews(rows, ident=big_id)
    gamepass, games = store_games(src, rows, known)
    print(f"xbox: {len(games)} games, {sum(1 for g in games.values() if 'gamepass' in g)} in the Game Pass",
          file=sys.stderr)
    starts, end = build.months(today)
    read = build.views_from({pid: known[pid] for pid in games if pid in known},
                            src("wikipedia/monthly.json").get("pages") or {})
    table = popular(known, critics, read, games)
    first = int(today.strftime("%Y%m%d"))
    last = int((today + datetime.timedelta(days=UPCOMING_DAYS)).strftime("%Y%m%d"))
    coming = {pid: [g["release"], g["name"]] for pid, g in sorted(games.items()) if first < g.get("release", 0) <= last}
    traits = {pid: {k: g[k] for k in ("developers", "publishers", "genres") if k in g} for pid, g in games.items()}

    def payload(source, entries, **extra):
        return {"schema": 1, "platform": XBOX, "generated": today.isoformat(), **extra, "source": source,
                "games": entries}
    common.publish(out_dir, f"platforms/{XBOX}/games.json", payload(
        "Microsoft Store's catalog (displaycatalog), Game Pass lists, Wikidata (P5885)", dict(sorted(games.items()))),
        previous_dir, report)
    common.publish(out_dir, f"platforms/{XBOX}/gamepass.json", payload(
        "Game Pass's lists (console, PC)", {pid: gamepass[pid] for pid in sorted(gamepass) if pid in games}),
        previous_dir, report)
    common.publish(out_dir, f"platforms/{XBOX}/popular.json", payload(
        "Wikidata (P5885, sitelinks, P444 with P7887), Wikimedia pageviews (en.wikipedia), the store's ratings, "
        "the Game Pass", table, month=starts[-1].strftime("%Y-%m"), views=bool(read)), previous_dir, report)
    common.publish(out_dir, f"platforms/{XBOX}/upcoming.json", payload("Microsoft Store's catalog", coming), previous_dir, report)
    common.publish(out_dir, f"platforms/{XBOX}/similar.json", payload(
        "xbox/games.json's traits", features.similar(traits, max_shared=300)), previous_dir, report)
    print(common.summary(report), file=sys.stderr)


def prices(src, out_dir, previous_dir, today):
    report = []
    for country, currency in COUNTRIES.items():
        rows = {}
        collected = common.collected_today(src, f"msstore/prices/{country}.json", today)
        if not collected:
            print(f"xbox prices: {country}: nothing collected today", file=sys.stderr)
            continue
        for pid, got in (collected.get("games") or {}).items():
            row = row_of(got)
            if row:
                rows[pid] = row
        name = f"platforms/{XBOX}/prices/{country}.json"
        last = common.previous_file(previous_dir, name)
        common.publish(out_dir, name, {
            "schema": 1, "platform": XBOX, "generated": today.isoformat(), "country": country, "currency": currency,
            "since": last.get("since") or last.get("generated") or today.isoformat(),
            "source": "Microsoft Store's catalog (displaycatalog)",
            "games": common.with_lowest(dict(sorted(rows.items())), last.get("games") or {}, today.isoformat())},
            previous_dir, report)
    print(common.summary(report), file=sys.stderr)


def main():
    what, out_dir, previous_dir, sources_dir = sys.argv[1:5]
    common.timed(out_dir, f"xbox {what}", lambda: {"catalog": catalog, "prices": prices}[what](
        common.reader(sources_dir, previous_dir), out_dir, previous_dir, datetime.date.today()))


if __name__ == "__main__":
    main()
