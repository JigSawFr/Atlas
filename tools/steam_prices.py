#!/usr/bin/env python3
"""Each Steam game's price and sale in a few countries' stores, every day
(daily.yml): steam/prices/<country>.json, the games of the last run's
steam/games.json (the best known 40,000 and the upcoming ones).

steam/prices/<country>.json:
  {"schema": 1, "platform": "steam", "generated": "YYYY-MM-DD", "country": "FR", "currency": "EUR",
   "since": "YYYY-MM-DD",
   "games": {"<app id>": [regular, sale, until, lowest, lowest_day, lowest_30], ...}}

The first five as switch/prices/: the price, the sale price (0: not on
sale), the sale's last day (YYYYMMDD, 0: none), the lowest price since
`since` and the last day it had it. `lowest_30` is Steam's own: the lowest
price of the last 30 days, as the store shows it in Europe (0 when it says
none). A free game, or one not sold in the country, is left out.

Steam's store (IStoreBrowseService/GetItems, no key) answers 200 apps a
request; a few requests at once.

Usage: tools/steam_prices.py <out-dir> <previous-dir> <sources-dir>   (writes out-dir/steam/prices/,
from sources/steam-store/prices/, tools/collect.py's)
"""
import concurrent.futures
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse

import common
import steam

COUNTRIES = {"US": "USD", "CA": "CAD", "MX": "MXN", "BR": "BRL", "GB": "GBP", "FR": "EUR", "DE": "EUR",
             "ES": "EUR", "IT": "EUR", "NL": "EUR", "PT": "EUR", "AU": "AUD", "JP": "JPY"}
WORKERS = 3         # requests at once
PAUSE = 0.3         # seconds a worker waits between two
REFUSED_WAIT = 20   # seconds a worker waits when the store says too many (429), then asks again
REFUSED_TRIES = 4


def request(apps, country):
    body = {"ids": [{"appid": int(a)} for a in apps],
            "context": {"language": "english", "country_code": country}, "data_request": {}}
    return steam.ITEMS.format(urllib.parse.quote(json.dumps(body, separators=(",", ":"))))


def cents(value):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    return round(v / 100, 2) if v >= 0 else None


def row_of(item):
    """[regular, sale, until, lowest_30] of a GetItems item, or None (free, not sold)."""
    if item.get("success") != 1 or item.get("is_free"):
        return None
    option = item.get("best_purchase_option") or {}
    final = cents(option.get("final_price_in_cents"))
    if not final:
        return None
    original = cents(option.get("original_price_in_cents"))
    regular, sale, until = final, 0, 0
    if original and original > final:
        regular, sale = original, final
        ends = [d.get("discount_end_date") for d in option.get("active_discounts") or [] if d.get("discount_end_date")]
        until = steam.day_of(min(ends)) if ends else 0
    lowest_30 = cents(option.get("lowest_recent_price_in_cents")) or 0
    return [regular, sale, until, lowest_30]


def read_items(country, apps, fetch, workers=WORKERS, pause=PAUSE):
    """{app id: GetItems' item} of `country`'s store for `apps`, in the order they came."""
    apps = sorted(apps, key=int)
    batches = [apps[i:i + steam.BATCH] for i in range(0, len(apps), steam.BATCH)]

    def ask(batch):
        time.sleep(pause)
        for attempt in range(REFUSED_TRIES):
            try:
                body = fetch(request(batch, country))
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == REFUSED_TRIES - 1:
                    print(f"steam prices: {country}: {e}", file=sys.stderr)
                    return []
                time.sleep(REFUSED_WAIT * pause / PAUSE if pause else 0)
            except (urllib.error.URLError, OSError, ValueError) as e:
                print(f"steam prices: {country}: {e}", file=sys.stderr)
                return []
        return [(str(item["appid"]), item) for item in ((body or {}).get("response") or {}).get("store_items") or []
                if item.get("appid")]

    out = {}
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for found in pool.map(ask, batches):
            out.update(found)
    return out


def rows_of(items):
    """{app id: [regular, sale, until, lowest_30]} of the items sold."""
    out = {}
    for app, item in items.items():
        row = row_of(item)
        if row:
            out[app] = row
    return dict(sorted(out.items(), key=lambda kv: int(kv[0])))


def read_country(country, apps, fetch, workers=WORKERS, pause=PAUSE):
    """{app id: [regular, sale, until, lowest_30]} of `country`'s store."""
    return rows_of(read_items(country, apps, fetch, workers, pause))


def with_lowest(rows, previous, today):
    """Each row with the lowest price so far and its day (common.with_lowest), then Steam's 30 days' lowest."""
    kept = common.with_lowest({app: r[:3] for app, r in rows.items()}, previous, today)
    return {app: kept[app] + [rows[app][3]] for app in rows}


def consolidate(src, out_dir, previous_dir, today):
    """steam/prices/<country>.json from the store's answers collected today."""
    report = []
    for country, currency in COUNTRIES.items():
        collected = common.collected_today(src, f"steam-store/prices/{country}.json", today)
        if not collected:
            print(f"steam prices: {country}: nothing collected today", file=sys.stderr)
            continue
        rows = rows_of(collected.get("games") or {})
        print(f"{country}: {len(rows)} games, {sum(1 for r in rows.values() if r[1])} on sale", file=sys.stderr)
        name = f"{steam.STEAM}/prices/{country}.json"
        last = common.previous_file(previous_dir, name)
        common.publish(out_dir, name, {
            "schema": common.SCHEMA, "platform": steam.STEAM, "generated": today, "country": country, "currency": currency,
            "since": last.get("since") or last.get("generated") or today,
            "source": "Steam's store (IStoreBrowseService/GetItems)",
            "games": with_lowest(rows, last.get("games") or {}, today)}, previous_dir, report)
    print(common.summary(report), file=sys.stderr)


def main():
    out_dir, previous_dir, sources_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    consolidate(common.reader(sources_dir, previous_dir), out_dir, previous_dir, datetime.date.today().isoformat())


if __name__ == "__main__":
    main()
