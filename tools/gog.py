#!/usr/bin/env python3
"""GOG's files, by GOG product id, in gog/:

- every Monday (build.yml), `tools/gog.py catalog`:
  - gog/popular.json: [score, trend, critics], as switch/popular.json: half
    the game's renown on Wikipedia (by the Wikidata item that gives its GOG
    page, P2725), half its GOG reviews, its rank in GOG's "trending" order
    a lift;
  - gog/games.json: each game's name, slug, release, reviews, Wikidata item
    and traits (developers, publishers, genres, tags);
  - gog/upcoming.json: the games still to come, [YYYYMMDD, name];
  - gog/similar.json: the games most like each one, by their traits;
- every day (daily.yml), `tools/gog.py prices`: gog/prices/<country>.json,
  [regular, sale, until, lowest, lowest_day] as switch/prices/ (GOG gives no
  sale's last day: `until` is 0).

GOG's catalog (catalog.gog.com, no key) gives every game and pack, 100 a
page, with its price in a country's currency; some 85 pages a country.

Usage: tools/gog.py catalog|prices <out-dir> [previous-dir]
"""
import concurrent.futures
import datetime
import sys
import time
import urllib.error
import urllib.parse

import build
import common
import features

GOG = "gog"
CATALOG = ("https://catalog.gog.com/v1/catalog?limit=100&page={page}&countryCode={country}&currencyCode={currency}"
           "&locale=en-US&order=desc:trending&productType=in:game,pack")
# GOG sells in Japan in US dollars.
COUNTRIES = {"US": "USD", "CA": "CAD", "MX": "MXN", "BR": "BRL", "GB": "GBP", "FR": "EUR", "DE": "EUR",
             "ES": "EUR", "IT": "EUR", "NL": "EUR", "PT": "EUR", "AU": "AUD", "JP": "USD"}
QUERY = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
SELECT ?tid ?item ?links ?article ?score ?count WHERE {
  ?item wdt:P2725 ?tid; wikibase:sitelinks ?links.
  OPTIONAL { ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }
  OPTIONAL { ?item p:P444 ?statement. ?statement ps:P444 ?score. OPTIONAL { ?statement pq:P7887 ?count } }
}
"""
QLEVER = "https://qlever.dev/api/wikidata"
WORKERS = 4
PAUSE = 0.3
MAX_PAGES = 200        # a bound, should GOG's page count go wrong
TAGS_KEPT = 10
UPCOMING_DAYS = 365


def read_catalog(country, fetch, workers=WORKERS, pause=PAUSE):
    """GOG's products in `country`, in its trending order: [(product, rank)]."""
    currency = COUNTRIES[country]
    first = fetch(CATALOG.format(page=1, country=country, currency=currency)) or {}
    pages = min(int(first.get("pages") or 0), MAX_PAGES)

    def ask(page):
        time.sleep(pause)
        try:
            return (fetch(CATALOG.format(page=page, country=country, currency=currency)) or {}).get("products") or []
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"gog: {country} page {page}: {e}", file=sys.stderr)
            return []

    found = list(first.get("products") or [])
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for products in pool.map(ask, range(2, pages + 1)):
            found.extend(products)
    out, seen = [], set()
    for product in found:
        pid = str(product.get("id") or "")
        if pid.isdigit() and pid not in seen:
            seen.add(pid)
            out.append((product, len(out) + 1))
    print(f"gog: {country}: {len(out)} products, {pages} pages", file=sys.stderr)
    return out


def money(value):
    try:
        v = float((value or {}).get("amount"))
    except (TypeError, ValueError):
        return None
    return round(v, 2) if v >= 0 else None


def price_of(product):
    """[regular, sale, until] of a product, or None when it is free or has no price."""
    price = product.get("price") or {}
    final, base = money(price.get("finalMoney")), money(price.get("baseMoney"))
    if not final:
        return None
    if base and base > final:
        return [base, final, 0]
    return [final, 0, 0]


def day_of(text):
    """YYYYMMDD of GOG's "2023.09.26", 0 when there is none."""
    digits = (text or "").replace(".", "").replace("-", "")[:8]
    return int(digits) if len(digits) == 8 and digits.isdigit() else 0


def entry(product, qid=None):
    """A game's gog/games.json entry."""
    out = {"name": (product.get("title") or "")[:200], "slug": product.get("slug") or ""}
    if qid:
        out["qid"] = qid
    day = day_of(product.get("releaseDate"))
    if day:
        out["release"] = day
    if product.get("productType") == "pack":
        out["pack"] = True
    if product.get("reviewsCount"):
        # GOG's rating is out of 50 (4.3 stars: 43).
        out["reviews"] = [int(product["reviewsCount"]), round(int(product.get("reviewsRating") or 0) * 2)]

    def named(kind, names):
        return [[f"{kind}:{n.lower()}", n[:120]] for n in names if n][:features.MAX_TRAITS]
    traits = {"developers": named("name", product.get("developers") or []),
              "publishers": named("name", product.get("publishers") or []),
              "genres": [[f"genre:{g['slug']}", g.get("name", "")] for g in product.get("genres") or [] if g.get("slug")],
              "tags": [[f"tag:{t['slug']}", t.get("name", "")] for t in (product.get("tags") or [])[:TAGS_KEPT]
                       if t.get("slug")]}
    out.update({k: v for k, v in traits.items() if v})
    return out


def popular(known, critics, read, games, ranks):
    """{product id: [score, trend, critics]}: half the renown on Wikipedia,
    half GOG's reviews; GOG's 100 first in its trending order lifted by rank."""
    wiki = build.popular(known, critics, read)
    most = max((g["reviews"][0] for g in games.values() if "reviews" in g), default=0)
    table = {}
    for pid, g in games.items():
        w = wiki.get(g.get("slug"), [0, 0, 0])
        score = 0.5 * w[0] / 100 + 0.5 * common.scale(g["reviews"][0] if "reviews" in g else 0, most)
        rank = ranks.get(pid, 999)
        if rank <= 100:
            score = max(score, 0.75 * score + 0.25 * (1 - (rank - 1) / 100))
        if round(score * 100) > 0:
            table[pid] = [round(score * 100), w[1], w[2]]
    return dict(sorted(table.items(), key=lambda kv: int(kv[0])))


def slug_of(value):
    """A GOG page's slug from Wikidata's P2725 ("game/amber_lantern")."""
    v = (value or "").strip().lower()
    v = v[len("game/"):] if v.startswith("game/") else v
    return v or None


def wikidata_rows():
    try:
        return common.sparql(QUERY)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        print(f"gog: Wikidata's service: {e}; QLever asked", file=sys.stderr)
        body = common.fetch(QLEVER + "?" + urllib.parse.urlencode({"query": QUERY}), tries=3, timeout=300,
                            headers={"Accept": "application/sparql-results+json"})
        return body["results"]["bindings"]


def catalog(out_dir, previous_dir, fetch, today):
    report = []
    found = read_catalog("US", fetch)
    rows = wikidata_rows()
    known = build.games(rows, ident=slug_of)
    critics = build.reviews(rows, ident=slug_of)
    qids = {}
    for b in rows:
        slug = slug_of(b["tid"]["value"])
        if slug and slug not in qids:
            qids[slug] = b["item"]["value"].rsplit("/", 1)[-1]
    games = {str(p["id"]): entry(p, qids.get((p.get("slug") or "").lower())) for p, _ in found}
    ranks = {str(p["id"]): rank for p, rank in found}
    starts, end = build.months(today)
    slugs = {g["slug"] for g in games.values()}
    read = build.read_views({s: known[s] for s in known if s in slugs}, starts, end)
    table = popular({s: known[s] for s in known if s in slugs}, critics, read, games, ranks)
    first = int(today.strftime("%Y%m%d"))
    last = int((today + datetime.timedelta(days=UPCOMING_DAYS)).strftime("%Y%m%d"))
    coming = {pid: [g["release"], g["name"]] for pid, g in sorted(games.items(), key=lambda kv: int(kv[0]))
              if first < g.get("release", 0) <= last}
    traits = {pid: {k: g[k] for k in ("developers", "publishers", "genres", "tags") if k in g} for pid, g in games.items()}

    def payload(source, entries, **extra):
        return {"platform": GOG, "generated": today.isoformat(), **extra, "schema": common.SCHEMA, "source": source,
                "games": entries}
    by_id = lambda d: dict(sorted(d.items(), key=lambda kv: int(kv[0])))   # noqa: E731
    common.publish(out_dir, f"{GOG}/games.json", payload("GOG's catalog, Wikidata (P2725)", by_id(games)),
                   previous_dir, report)
    common.publish(out_dir, f"{GOG}/popular.json", payload(
        "Wikidata (P2725, sitelinks, P444 with P7887), Wikimedia pageviews (en.wikipedia), GOG's reviews and trending",
        table, month=starts[-1].strftime("%Y-%m"), views=bool(read)), previous_dir, report)
    common.publish(out_dir, f"{GOG}/upcoming.json", payload("GOG's catalog", coming), previous_dir, report)
    common.publish(out_dir, f"{GOG}/similar.json", payload(
        "gog/games.json's traits", features.similar(traits, max_shared=300)), previous_dir, report)
    print(common.summary(report), file=sys.stderr)


def prices(out_dir, previous_dir, fetch, today):
    report = []
    for country, currency in COUNTRIES.items():
        rows = {}
        for product, _ in read_catalog(country, fetch):
            row = price_of(product)
            if row:
                rows[str(product["id"])] = row
        name = f"{GOG}/prices/{country}.json"
        last = common.previous_file(previous_dir, name) if previous_dir else {}
        common.publish(out_dir, name, {
            "schema": common.SCHEMA, "platform": GOG, "generated": today.isoformat(), "country": country, "currency": currency,
            "since": last.get("since") or last.get("generated") or today.isoformat(), "source": "GOG's catalog",
            "games": common.with_lowest(dict(sorted(rows.items(), key=lambda kv: int(kv[0]))),
                                        last.get("games") or {}, today.isoformat())}, previous_dir, report)
    print(common.summary(report), file=sys.stderr)


def main():
    what, out_dir = sys.argv[1], sys.argv[2]
    previous_dir = sys.argv[3] if len(sys.argv) > 3 else None
    fetch = lambda url: common.fetch(url, tries=3, patient=False, timeout=60)   # noqa: E731
    {"catalog": catalog, "prices": prices}[what](out_dir, previous_dir, fetch, datetime.date.today())


if __name__ == "__main__":
    main()
