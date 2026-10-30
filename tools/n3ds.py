#!/usr/bin/env python3
"""The Nintendo 3DS's files, in platforms/3ds/, every Monday, a game a
family (one game across its regions, as a serial: "CTR-AKD" for the
"CTR-N-AKDJ", "CTR-N-AKDE"… of its cards and downloads):

- games.json: each family's name (its American or European one first), its
  regions, its base games' title ids by region, its updates', add-ons' and
  demos' title ids, its publisher, its first day on the eShop, and, for
  the ones Wikidata knows (Wikidata's 3DS games, P400 = Q203597, matched by
  their English name), its Wikidata item and traits (series, developers,
  publishers, genres);
- popular.json: [score, trend, critics] as platforms/switch/popular.json,
  from Wikidata and Wikipedia (sitelinks, the English page's views) for the
  games Wikidata knows; critics 0;
- similar.json: the games most like each one, by their traits.

No prices: the 3DS's eShop closed in March 2023. No pictures nor texts.

The source is Nlib API's 3DS (api.nlib.cc/ctr/, no key): its lists of
title ids by category (base games, updates, add-ons, demos), then each base
game's name, publisher, region, product code and first day, a request a
title (some 4,400), asked once and kept (sources/nlib-ctr/titles.json):
a run asks only the titles it does not know yet, at most MAX_NEW, two at a
time, paced (PAUSE). Wikidata has no 3DS title id: an item is matched to a
family by its English name, only when exactly one of each has that name.

Usage: tools/n3ds.py <out-dir> <previous-dir> <sources-dir>
"""
import concurrent.futures
import datetime
import re
import sys
import time
import unicodedata
import urllib.error

import build
import common
import features
import platforms

N3DS = "3ds"
ITEM = "Q203597"          # Nintendo 3DS, in Wikidata
API = "https://api.nlib.cc/ctr/"
CATEGORIES = ("base", "updates", "dlc", "digital-demos")
FIELDS = "name,formal_name,publisher,region,product_code,release_date_on_eshop"
AGENT = {"User-Agent": "Atlas/1.0 (+https://atlas.boreale.dev)"}
WORKERS = 2               # requests at once
PAUSE = 0.25              # seconds a worker waits between two
MAX_NEW = 5000            # titles asked a run, at most (the first run: all of them)
TID = re.compile(r"^0004[0-9A-F]{12}$")
CODE = re.compile(r"^(CTR|KTR)-[A-Z]-([0-9A-Z]{3})([A-Z])$")
ENGLISH = ("US", "GB", "EU", "AU", "CA")


def fetch(url):
    return common.fetch(url, tries=3, patient=False, timeout=60, headers=AGENT)


def collect(out_dir, previous_dir, fresh, today, report, fetch=fetch, workers=WORKERS, pause=PAUSE):
    """sources/nlib-ctr/categories.json and titles.json (the new titles asked, the known ones kept)."""
    lists = {}
    for category in CATEGORIES:
        body = fetch(API + f"category/{category}") or {}
        lists[category] = sorted({t.upper() for t in body.get("titles") or [] if TID.match(t.upper())})
    known = common.source(f"{common.SOURCES}/nlib-ctr/titles.json", previous_dir).get("games") or {}
    asked = [t for t in lists["base"] if t not in known][:MAX_NEW]

    def ask(tid):
        time.sleep(pause)
        try:
            body = fetch(API + f"{tid}?fields={FIELDS}&related=0")
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"nlib-ctr: {tid}: {e}", file=sys.stderr)
            return tid, None
        return tid, {k: v for k, v in (body or {}).items() if k in FIELDS.split(",") and v not in (None, "")}

    titles = {t: known[t] for t in lists["base"] if t in known}
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for tid, got in pool.map(ask, asked):
            if got:
                titles[tid] = got
    print(f"nlib-ctr: {len(lists['base'])} base titles, {len(asked)} asked, {len(titles)} known", file=sys.stderr)
    payload = {"schema": 1, "source_id": "nlib-ctr", "generated": today.isoformat(),
               "source": "Nlib API (api.nlib.cc/ctr/)", "license": "as published by Nlib API (no terms stated)"}
    common.publish_source(out_dir, f"{common.SOURCES}/nlib-ctr/categories.json", {**payload, "items": lists},
                          previous_dir, report)
    common.publish_source(out_dir, f"{common.SOURCES}/nlib-ctr/titles.json",
                          {**payload, "games": dict(sorted(titles.items()))}, previous_dir, report)


def family_of(code):
    """("CTR-AKD", region letter) of a product code ("CTR-N-AKDE"), or (None, None)."""
    m = CODE.match((code or "").strip().upper())
    return (f"{m.group(1)}-{m.group(2)}", m.group(3)) if m else (None, None)


def families(titles, lists):
    """{family: entry}: the base titles grouped by their product code's serial,
    each with its updates', add-ons' and demos' title ids (the same unique id)."""
    by_unique = {}
    for kind, category in (("updates", "updates"), ("dlc", "dlc"), ("demos", "digital-demos")):
        for tid in lists.get(category) or []:
            by_unique.setdefault(tid[8:14], {}).setdefault(kind, []).append(tid)
    out = {}
    for tid, t in sorted(titles.items()):
        family, _ = family_of(t.get("product_code"))
        if not family:
            continue
        f = out.setdefault(family, {"names": {}, "tids": {}, "publisher": "", "release": 0})
        region = (t.get("region") or "").upper() or "?"
        f["tids"].setdefault(region, []).append(tid)
        if t.get("name"):
            f["names"].setdefault(region, t["name"])
        f["publisher"] = f["publisher"] or (t.get("publisher") or "")
        day = int((t.get("release_date_on_eshop") or "0").replace("-", "")[:8] or 0)
        if day and (not f["release"] or day < f["release"]):
            f["release"] = day
        for kind, tids in by_unique.get(tid[8:14], {}).items():
            have = f.setdefault(kind, [])
            have += [x for x in tids if x not in have]
    return out


def name_of(f):
    for region in ENGLISH:
        if f["names"].get(region):
            return f["names"][region]
    return next(iter(f["names"].values()), "")


def normal(name):
    """A name compared: lower case, no marks (™, ®, accents), letters and digits only."""
    text = unicodedata.normalize("NFKD", (name or "").replace("™", "").replace("®", "").replace("©", ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def matches(games, retro_games):
    """{QID: family} of Wikidata's 3DS games whose English name is one family's
    name in an English region, only where each side has that name once."""
    by_name = {}
    for family, f in games.items():
        for name in {normal(n) for r, n in f["names"].items() if r in ENGLISH and n}:
            by_name.setdefault(name, set()).add(family)
    items = {}
    for qid, g in retro_games.items():
        if any(p == ITEM for p, _ in g.get("platforms") or []) and g.get("name"):
            items.setdefault(normal(g["name"]), []).append(qid)
    out = {}
    for name, qids in items.items():
        found = by_name.get(name)
        if name and len(qids) == 1 and found and len(found) == 1:
            out[qids[0]] = next(iter(found))
    return out


def built(src):
    """(games.json's games, {QID: family}) from the sources collected."""
    import retro   # its Wikidata rows (P400) hold the 3DS's games
    titles = src("nlib-ctr/titles.json").get("games") or {}
    lists = src("nlib-ctr/categories.json").get("items") or {}
    found = families(titles, lists)
    rows = common.bindings(src("wikidata/retro.json").get("rows") or [])
    wiki = retro.games_of(rows)
    traits = features.traits({kind: common.bindings(src(f"wikidata/retro-{kind}.json").get("rows") or [])
                              for kind in retro.KINDS}, retro.qid)
    matched = matches(found, wiki)
    by_family = {f: q for q, f in matched.items()}
    games = {}
    for family, f in sorted(found.items()):
        entry = {"name": name_of(f)[:200], "regions": sorted(f["tids"]), "tids": {r: sorted(t) for r, t in f["tids"].items()}}
        for kind in ("updates", "dlc", "demos"):
            if f.get(kind):
                entry[kind] = sorted(f[kind])
        if f["publisher"]:
            entry["publisher"] = f["publisher"][:120]
        if f["release"]:
            entry["release"] = f["release"]
        qid = by_family.get(family)
        if qid:
            entry["qid"] = qid
            entry.update({k: v for k, v in traits.get(qid, {}).items() if k in retro.KINDS})
        games[family] = entry
    return games, matched


def consolidate(src, out_dir, previous_dir, today):
    report = []
    games, matched = built(src)
    print(f"3ds: {len(games)} games, {len(matched)} matched to Wikidata", file=sys.stderr)
    import retro
    rows = common.bindings(src("wikidata/retro.json").get("rows") or [])
    known_q = build.games(rows, ident=retro.qid)
    known = {matched[q]: known_q[q] for q in matched if q in known_q}
    read = build.views_from(known_q, src("wikipedia/monthly.json").get("pages") or {})
    starts, _ = build.months(today)

    def payload(source, entries, **extra):
        return {"schema": 1, "platform": N3DS, "generated": today.isoformat(), **extra, "source": source,
                "games": entries}
    common.publish(out_dir, platforms.path(N3DS, "games.json"), payload(
        "Nlib API (api.nlib.cc/ctr/), Wikidata (P400, P179, P178, P123, P136)", games), previous_dir, report)
    common.publish(out_dir, platforms.path(N3DS, "popular.json"), payload(
        "Wikidata (P400, sitelinks), Wikimedia pageviews (en.wikipedia)", dict(sorted(
            build.popular(known, {}, read).items())), month=starts[-1].strftime("%Y-%m"), views=bool(read)),
        previous_dir, report)
    common.publish(out_dir, platforms.path(N3DS, "similar.json"), payload(
        "platforms/3ds/games.json's traits", features.similar(
            {g: {k: e[k] for k in retro.KINDS if k in e} for g, e in games.items()}, max_shared=300)),
        previous_dir, report)
    print(common.summary(report), file=sys.stderr)


def main():
    out_dir, previous_dir, sources_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    consolidate(common.reader(sources_dir, previous_dir), out_dir, previous_dir, datetime.date.today())


if __name__ == "__main__":
    main()
