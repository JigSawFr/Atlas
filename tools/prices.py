#!/usr/bin/env python3
"""Each game's price in the eShop of a few countries, and its sale when it
has one: switch/prices/<country>.json, made every day (daily.yml).

The eShop's price service (api.ec.nintendo.com/v1/price) answers by the
eShop's own ids, which differ from one region to the next: titledb's list of
each region gives them with each game's title id (REGIONS). It is asked 50
games at a time, a few requests at once.

switch/prices/<country>.json:
  {"schema": 1, "platform": "switch", "generated": "YYYY-MM-DD", "country": "FR", "currency": "EUR",
   "since": "YYYY-MM-DD",
   "games": {"<title id>": [regular, sale, until, lowest, lowest_day], ...}}

`regular` and `sale` are prices in the country's currency (sale 0: not on
sale), `until` the sale's last day, YYYYMMDD (0: none). `lowest` is the
lowest price the game has had since `since`, the day these files began,
and `lowest_day` (YYYYMMDD) the last day it had it: each day's price is
weighed against the last run's file. A game no longer sold, or not in that
eShop, is left out.

Usage: tools/prices.py <out-dir> <previous-dir> <sources-dir>   (writes out-dir/switch/prices/,
from the sources tools/collect.py keeps: titledb, eshop)
"""
import concurrent.futures
import datetime
import sys
import time
import urllib.error

import build
import common
from common import with_lowest  # noqa: F401  (tests read it here)

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






def from_answers(rows, ids):
    """{title id: [regular, sale, until]} and the currency, from the eShop's
    answers collected (sources/eshop/prices/<country>.json: by eShop id, in
    the order they came), as read_country reads them."""
    games, currency = {}, None
    for nsu, r in rows.items():
        tid = ids.get(int(nsu)) if nsu.isdigit() else None
        if not tid or r.get("status") != "onsale" or r.get("regular") is None:
            continue
        regular = r["regular"]
        currency = currency or r.get("currency")
        sale, until = 0, 0
        if r.get("discount") is not None and r["discount"] < regular:
            sale, until = r["discount"], r.get("until") or 0
        games.setdefault(tid, [regular, sale, until])
    return dict(sorted(games.items())), currency


def consolidate(src, out_dir, previous_dir, today):
    """switch/prices/<country>.json from the eShop's answers and titledb's ids collected."""
    report = []
    for file, countries in REGIONS.items():
        titles = src(f"titledb/{file.split('.')[0]}.json").get("games") or {}
        ids = eshop_ids(titles, build.base_id)
        print(f"{file}: {len(ids)} games with an eShop id", file=sys.stderr)
        for country in countries:
            answers = common.collected_today(src, f"eshop/prices/{country}.json", today).get("games")
            if answers is None:
                print(f"{country}: no answers collected today", file=sys.stderr)
                continue
            games, currency = from_answers(answers, ids)
            print(f"{country}: {len(games)} games, {sum(1 for r in games.values() if r[1])} on sale", file=sys.stderr)
            name = f"platforms/{build.SWITCH}/prices/{country}.json"
            last = common.previous_file(previous_dir, name) if previous_dir else {}
            common.publish(out_dir, name, {
                "schema": 1, "platform": build.SWITCH, "generated": today, "country": country, "currency": currency or "",
                "since": last.get("since") or last.get("generated") or today,
                "source": f"Nintendo eShop's prices, by titledb's {file} eShop ids",
                "games": with_lowest(games, last.get("games") or {}, today)}, previous_dir, report)
    print(common.summary(report), file=sys.stderr)


def main():
    out_dir, previous_dir, sources_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    consolidate(common.reader(sources_dir, previous_dir), out_dir, previous_dir, datetime.date.today().isoformat())


if __name__ == "__main__":
    main()
