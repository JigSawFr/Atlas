#!/usr/bin/env python3
"""The Nintendo 3DS's files, in platforms/3ds/, every Monday, a game a
family (one game across its regions, as a serial: "CTR-AKD" for the
"CTR-N-AKDJ", "CTR-N-AKDE"… of its cards and downloads):

- games.json: each family's name (its American or European one first), its
  regions, its base games' title ids by region, its updates', add-ons' and
  demos' title ids, its publisher, its first day on the eShop, and, for
  the ones Wikidata knows (Wikidata's 3DS games, P400 = Q203597, matched by
  matches()), its Wikidata item and traits (series, developers,
  publishers, genres);
- popular.json: [score, trend, critics] as platforms/switch/popular.json,
  from Wikidata and Wikipedia (sitelinks, the English page's views) for the
  games Wikidata knows; critics 0;
- similar.json: the games most like each one, by their traits.

No pictures nor texts.

The source is Nlib API's 3DS (api.nlib.cc/ctr/, no key): its lists of
title ids by category (base games, updates, add-ons, demos), then each base
game's name, publisher, region, product code and first day, a request a
title (some 4,400), asked once and kept (sources/nlib-ctr/titles.json):
a run asks only the titles it does not know yet, at most MAX_NEW, two at a
time, paced (PAUSE). Wikidata has no 3DS title id: an item is matched to its
families by its GameTDB code (P8087), else its names (sources/wikidata/
3ds.json adds its Japanese label, English aliases and dates), see matches().

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
import igdb
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
    payload = {"schema": common.SOURCE_SCHEMA, "source_id": "nlib-ctr", "generated": today.isoformat(),
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


ROMAN = {"ii": "2", "iii": "3", "iv": "4", "vi": "6", "vii": "7", "viii": "8", "ix": "9", "xi": "11",
         "xii": "12", "xiii": "13"}   # not i, v nor x: letters as often as numbers ("Pokémon X")
TAILS = (("for", "nintendo", "3ds"), ("nintendo", "3ds"), ("3ds",))
SUBTITLE = re.compile(r"\s*:\s*|\s+[-–—]\s*|\s*[(\[]")   # not a new line: a long name's, as often
TAGS = re.compile(r"<[^>]*>")
NOT_A_NAME = {"inc", "co", "ltd", "llc", "corp", "corporation", "company", "limited", "gmbh", "sa", "kk", "the",
              "of", "and", "games", "game", "entertainment", "interactive", "studio", "studios", "software",
              "digital", "publishing", "media", "america", "europe", "usa", "japan", "nintendo"}
EXTRA = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?tid ?ja ?alias ?date ?tdb WHERE {
  ?tid wdt:P400 wd:%s; wdt:P31 wd:Q7889.
  { ?tid rdfs:label ?ja. FILTER(LANG(?ja) = "ja") }
  UNION { ?tid skos:altLabel ?alias. FILTER(LANG(?alias) = "en") }
  UNION { ?tid wdt:P577 ?date. }
  UNION { ?tid wdt:P8087 ?tdb. FILTER(STRSTARTS(?tdb, "3DS/")) }
}""" % ITEM
TDB = re.compile(r"^3DS/([0-9A-Z]{3})[A-Z]$")


def tokens(name):
    """A name's words compared: lower case, no marks (™, ®, accents on Latin
    letters), no HTML tag, "&" as "and", Roman numerals from II as figures."""
    text = TAGS.sub(" ", (name or "").replace("™", "").replace("®", "").replace("©", ""))
    text = text.replace("&", " and ").replace("'", "").replace("’", "")
    kept = []
    for c in unicodedata.normalize("NFKD", text):
        if unicodedata.combining(c) and kept and ord(kept[-1]) < 0x370:
            continue   # an accent on a Latin letter; a Japanese voicing mark stays
        kept.append(c)
    words = [ROMAN.get(w, w) for w in re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", "".join(kept)).lower())]
    return words


def key(name):
    """A name as compared: its words run together, without a leading "the" nor a
    trailing "for Nintendo 3DS" ("" for a name with no letter nor figure)."""
    words = tokens(name)
    if words[:1] == ["the"] and len(words) > 1:
        words = words[1:]
    for tail in TAILS:
        if len(words) > len(tail) and tuple(words[-len(tail):]) == tail:
            words = words[:-len(tail)]
            break
    return "".join(words)


def main_key(name):
    """The key of a name's title before its subtitle (": …", " - …", " -…-",
    brackets), or ""."""
    parts = SUBTITLE.split(name or "", maxsplit=1)
    head = key(parts[0]) if len(parts) == 2 and parts[1].strip() else ""
    return head if len(head) >= 4 else ""


def company(names):
    """The words that tell a publisher apart ("Bandai Namco Games" → bandai, namco)."""
    return {w for n in names for w in tokens(n) if w not in NOT_A_NAME and len(w) > 1}


def extras(rows):
    """{QID: {"names": [...], "years": {...}, "serials": {...}}} from EXTRA's rows."""
    import retro
    out = {}
    for b in rows:
        game = retro.qid(b["tid"]["value"])
        if not game:
            continue
        e = out.setdefault(game, {"names": [], "years": set(), "serials": set()})
        for field in ("ja", "alias"):
            if b.get(field, {}).get("value"):
                e["names"].append(b[field]["value"][:200])
        year = b.get("date", {}).get("value", "")[:4]
        if year.isdigit():
            e["years"].add(int(year))
        m = TDB.match(b.get("tdb", {}).get("value", "").strip().upper())
        if m:
            e["serials"].add(m.group(1))
    return out


def evidence(item, fam):
    """How much a game and a family agree besides their name: its release
    year within a year of the family's first day (+1), a publisher's name in
    common (+1)."""
    score = 0
    if fam["year"] and any(abs(y - fam["year"]) <= 1 for y in item["years"]):
        score += 1
    if item["pubs"] & fam["pubs"]:
        score += 1
    return score


def matches(games, retro_games, extra=None):
    """{QID: [family, ...]}: Wikidata's 3DS games matched to families, each
    family to one game, a game to one family a region at most.

    1. GameTDB's code (P8087, "3DS/AMKE"): its serial is the family's
       (CTR-AMK or KTR-AMK), when it points to one family only.
    2. The name (any region's, against the English, the "mul", the Japanese
       label and the English aliases), compared by key(): when one game
       has it, the families that have it; when several games do, the pair
       that agrees best on year and publisher, if it is the only one that good.
    3. The family's title before its subtitle ("Lantern Tale: Moon Tide")
       as the game's name ("Lantern Tale"), when no other game nor family
       has it and year or publisher agrees.
    Anything else is left without a match rather than matched wrong."""
    extra = extra or {}
    items = {}
    for qid, g in retro_games.items():
        if not any(p == ITEM for p, _ in g.get("platforms") or []):
            continue
        e = extra.get(qid, {})
        names = [n for n in [g.get("name")] + list(e.get("names") or []) if n]
        items[qid] = {"own": key(g.get("name")), "keys": {key(n) for n in names} - {""}, "mains": {main_key(n) for n in names} - {""},
                      "years": set(e.get("years") or ()), "serials": set(e.get("serials") or ()),
                      "pubs": company(v[1] for v in g.get("publishers") or [])}
    fams = {}
    for family, f in games.items():
        names = [n for n in f["names"].values() if n]
        fams[family] = {"keys": {key(n) for n in names} - {""}, "mains": {main_key(n) for n in names} - {""},
                        "year": (f.get("release") or 0) // 10000, "pubs": company([f.get("publisher") or ""])}
    out, taken = {}, set()

    def accept(pairs):
        """The pairs where the family has no other candidate, and the game
        none either, or only families of other regions (one game sold under
        a serial a region: "CTR-AMK" in America, "CTR-AMJ" in Japan)."""
        by_f = {}
        for q, fam in pairs:
            by_f.setdefault(fam, set()).add(q)
        # Two games for a family (Wikidata has some twice, its Japanese and its
        # English item): the one with the family's own name, if only one has it.
        for fam, qs in by_f.items():
            own = [q for q in qs if key(name_of(games[fam])) in items[q]["keys"]]
            if len(qs) > 1 and len(own) == 1:
                by_f[fam] = set(own)
        by_q = {}
        for fam, qs in by_f.items():
            for q in qs:
                by_q.setdefault(q, set()).add(fam)
        def apart(found):
            regions = [r for fam in found for r in games[fam]["names"]]
            return len(regions) == len(set(regions))
        for q, found in sorted(by_q.items()):
            if not all(len(by_f[fam]) == 1 for fam in found):
                continue
            had = set(out.get(q, ()))   # from a surer step: kept
            found = found - had
            if not apart(found):
                # Two of a region: only the ones named as the game is (its English label).
                found = {fam for fam in found if key(name_of(games[fam])) == items[q]["own"]}
                if not apart(found):
                    continue
            found = {fam for fam in found if apart(had | {fam})}
            if found:
                out[q] = sorted(had | found)
                taken.update(found)

    # 1. GameTDB's codes.
    by_serial = {}
    for family in fams:
        by_serial.setdefault(family.split("-", 1)[1], set()).add(family)
    accept({(q, next(iter(by_serial[s]))) for q, i in items.items() for s in i["serials"]
            if len(by_serial.get(s, ())) == 1})

    # 2. The whole name.
    def index(of, fields, skip):
        found = {}
        for ident, entry in of.items():
            if ident in skip:
                continue
            for field in fields:
                for k in entry[field]:
                    found.setdefault(k, set()).add(ident)
        return found
    q_keys, f_keys = index(items, ("keys",), ()), index(fams, ("keys",), taken)
    pairs = set()
    for k, qs in q_keys.items():
        fs = f_keys.get(k)
        if not fs:
            continue
        regions = [r for fam in fs for r in games[fam]["names"]]
        if len(qs) == 1 and len(regions) == len(set(regions)):
            pairs.update((next(iter(qs)), fam) for fam in fs)
            continue
        scored = {(q, fam): evidence(items[q], fams[fam]) for q in qs for fam in fs}
        best = max(scored.values())
        top = [p for p, s in scored.items() if s == best]
        if best >= 1 and len(top) == 1:
            pairs.add(top[0])
    accept(pairs)

    # 3. The title before the subtitle, unique among every game and family.
    q_all, f_all = index(items, ("keys", "mains"), ()), index(fams, ("keys", "mains"), ())   # unique among all
    pairs = set()
    for k, qs in q_all.items():
        fs = f_all.get(k)
        if not fs or len(qs) != 1 or len(fs) != 1:
            continue
        q, fam = next(iter(qs)), next(iter(fs))
        if fam in taken:
            continue
        # The family's subtitle only: Wikidata's own name is the shorter one ("Dr. Mario:
        # Miracle Cure" is not the "Dr. Mario" of 1990).
        if k in fams[fam]["mains"] and k in items[q]["keys"] and evidence(items[q], fams[fam]) >= 1:
            pairs.add((q, fam))
    accept(pairs)
    return out


def built(src):
    """(games.json's games, {QID: [family, ...]}) from the sources collected."""
    import retro   # its Wikidata rows (P400) hold the 3DS's games
    titles = src("nlib-ctr/titles.json").get("games") or {}
    lists = src("nlib-ctr/categories.json").get("items") or {}
    found = families(titles, lists)
    rows = common.bindings(src("wikidata/retro.json").get("rows") or [])
    wiki = retro.games_of(rows)
    traits = features.traits({kind: common.bindings(src(f"wikidata/retro-{kind}.json").get("rows") or [])
                              for kind in retro.KINDS}, retro.qid)
    for qid, kinds in traits.items():
        if qid in wiki and kinds.get("publishers"):
            wiki[qid]["publishers"] = kinds["publishers"]
    matched = matches(found, wiki, extras(common.bindings(src("wikidata/3ds.json").get("rows") or [])))
    by_family = {f: q for q, fs in matched.items() for f in fs}
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
    print(f"3ds: IGDB's traits or rating for {igdb.complete(games, igdb.others(src))} games", file=sys.stderr)
    return games, matched


def consolidate(src, out_dir, previous_dir, today):
    report = []
    games, matched = built(src)
    print(f"3ds: {len(games)} games, {sum(map(len, matched.values()))} matched to {len(matched)} of Wikidata's",
          file=sys.stderr)
    import retro
    rows = common.bindings(src("wikidata/retro.json").get("rows") or [])
    known_q = build.games(rows, ident=retro.qid)
    known = {f: known_q[q] for q, fs in matched.items() if q in known_q for f in fs}
    read = build.views_from(known_q, src("wikipedia/monthly.json").get("pages") or {})
    starts, _ = build.months(today)

    def payload(source, entries, **extra):
        return {"schema": common.SCHEMA, "platform": N3DS, "generated": today.isoformat(), **extra, "source": source,
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
