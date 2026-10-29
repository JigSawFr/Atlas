#!/usr/bin/env python3
"""Each game's price in the eShop of a few countries, and its sale when it
has one: data/prices/<country>.json, made every day (daily.yml).

The eShop's price service (api.ec.nintendo.com/v1/price) answers by the
eShop's own ids, which differ from one region to the next: titledb's list of
each region gives them with each game's title id (REGIONS). It is asked 50
games at a time, a few requests at once.

prices/<country>.json:
  {"schema": 1, "generated": "YYYY-MM-DD", "country": "FR", "currency": "EUR",
   "since": "YYYY-MM-DD",
   "games": {"<title id>": [regular, sale, until, lowest, lowest_day], ...}}

`regular` and `sale` are prices in the country's currency (sale 0: not on
sale), `until` the sale's last day, YYYYMMDD (0: none). `lowest` is the
lowest price the game has had since `since`, the day these files began,
and `lowest_day` (YYYYMMDD) the last day it had it: each day's price is
weighed against the last run's file. A game no longer sold, or not in that
eShop, is left out.

Usage: tools/prices.py [out-dir] [previous-dir]   (writes out-dir/prices/)
"""
import concurrent.futures
import datetime
import json
import os
import sys
import time
import urllib.error

import build

PRICE = "https://api.ec.nintendo.com/v1/price?country={country}&lang=en&ids={ids}"
TITLEDB = "https://raw.githubusercontent.com/blawar/titledb/master/{file}"
# titledb's list of a region, and the countries whose eShop uses its ids.
REGIONS = {
    "US.en.json": ["US", "CA", "MX", "BR"],
    "GB.en.json": ["GB", "FR", "DE", "ES", "IT", "NL", "PT", "AU"],
    "JP.ja.json": ["JP"],
}
BATCH = 50          # games a request
WORKERS = 4         # requests at once
PAUSE = 0.2         # seconds a worker waits between two


def eshop_ids(titles, base_id):
    """{eShop id: title id} of a region's base games (no demo)."""
    out = {}
    for entry in titles.values():
        tid = base_id(entry.get("id"))
        nsu = str(entry.get("nsuId") or "").strip()
        if tid and nsu.isdigit() and entry.get("isDemo") not in (True, "True"):
            out[int(nsu)] = tid
    return out


def amount(price):
    """A price's value, a number, or None."""
    try:
        value = float((price or {}).get("raw_value"))
    except (TypeError, ValueError):
        return None
    return round(value, 2) if value >= 0 else None


def day_of(stamp):
    """YYYYMMDD of an ISO time (2026-11-01T06:59:59Z), 0 when there is none."""
    try:
        return int(datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).strftime("%Y%m%d"))
    except ValueError:
        return 0


def read_answer(body, ids):
    """[(title id, [regular, sale, until])] and the currency, from a price answer."""
    out, currency = [], None
    for p in (body or {}).get("prices", []):
        tid = ids.get(p.get("title_id"))
        if not tid or p.get("sales_status") != "onsale":
            continue
        regular = amount(p.get("regular_price"))
        if regular is None:
            continue
        currency = currency or (p.get("regular_price") or {}).get("currency")
        sale, until = 0, 0
        discount = p.get("discount_price")
        if discount and amount(discount) is not None and amount(discount) < regular:
            sale, until = amount(discount), day_of(discount.get("end_datetime"))
        out.append((tid, [regular, sale, until]))
    return out, currency


def read_country(country, ids, fetch, workers=WORKERS, pause=PAUSE):
    """{title id: [regular, sale, until]} and the currency of `country`'s eShop."""
    numbers = sorted(ids)
    batches = [numbers[i:i + BATCH] for i in range(0, len(numbers), BATCH)]

    def ask(batch):
        time.sleep(pause)
        try:
            return read_answer(fetch(PRICE.format(country=country, ids=",".join(map(str, batch)))), ids)
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"prices: {country}: {e}", file=sys.stderr)
            return [], None

    games, currency = {}, None
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for found, cur in pool.map(ask, batches):
            currency = currency or cur
            for tid, row in found:
                games.setdefault(tid, row)
    return dict(sorted(games.items())), currency


def with_lowest(games, previous, today):
    """Each game's row with its lowest price so far and that price's last
    day, from the last run's rows (`previous`, {} on a first run)."""
    day = int(today.replace("-", ""))
    out = {}
    for tid, row in games.items():
        regular, sale, until = row[:3]
        now = sale or regular
        lowest, lowest_day = now, day
        last = previous.get(tid)
        if isinstance(last, list) and len(last) >= 5 and isinstance(last[3], (int, float)) and isinstance(last[4], int):
            if last[3] < now:
                lowest, lowest_day = last[3], last[4]
        out[tid] = [regular, sale, until, lowest, lowest_day]
    return out


def previous_file(previous_dir, country):
    """The last run's file of `country`, {} when there is none."""
    try:
        with open(os.path.join(previous_dir, f"{country}.json"), encoding="utf-8") as f:
            body = json.load(f)
        return body if body.get("schema") == 1 else {}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "out"
    previous_dir = os.path.join(sys.argv[2], "prices") if len(sys.argv) > 2 else None
    os.makedirs(os.path.join(out_dir, "prices"), exist_ok=True)
    today = datetime.date.today().isoformat()
    fetch = lambda url: build.fetch(url, tries=3, patient=False, timeout=60)   # noqa: E731
    report = []
    for file, countries in REGIONS.items():
        titles = build.fetch(TITLEDB.format(file=file), timeout=600) or {}
        ids = eshop_ids(titles, build.base_id)
        print(f"{file}: {len(ids)} games with an eShop id", file=sys.stderr)
        for country in countries:
            started = time.monotonic()
            games, currency = read_country(country, ids, fetch)
            print(f"{country}: {len(games)} games, {sum(1 for r in games.values() if r[1])} on sale, "
                  f"{time.monotonic() - started:.0f} s", file=sys.stderr)
            last = previous_file(previous_dir, country) if previous_dir else {}
            build.publish(os.path.join(out_dir, "prices"), f"{country}.json", {
                "schema": 1, "generated": today, "country": country, "currency": currency or "",
                "since": last.get("since") or last.get("generated") or today,
                "source": f"Nintendo eShop's prices, by titledb's {file} eShop ids",
                "games": with_lowest(games, last.get("games") or {}, today)}, previous_dir, report)
    print(build.summary(report), file=sys.stderr)


if __name__ == "__main__":
    main()
