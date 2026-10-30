#!/usr/bin/env python3
"""The games of the consoles, handhelds and computers no store Atlas reads
sells any more (the NES to the Xbox 360, the Game Boy to the Vita, the
arcade, the Commodore 64…), by Wikidata item (QID), in retro/, every Monday
(build.yml), from Wikidata alone:

- retro/popular.json: [score, trend, critics] as switch/popular.json, the
  game's renown on Wikipedia (its sitelinks, its English page's views for
  the best known); critics 0 (not asked);
- retro/games.json: each game's name, platforms ([QID, name]) and traits
  (series, developers, publishers, genres);
- retro/similar.json: the games most like each one, by their traits.

Usage: tools/retro.py <out-dir> [previous-dir]   (writes out-dir/retro/)
"""
import datetime
import re
import sys
import time
import urllib.error
import urllib.parse

import build
import common
import features

RETRO = "retro"
# The platforms, by Wikidata item.
PLATFORMS = ("Q172742 Q135321 Q183259 Q184839 Q182172 Q8079 Q56942 Q186437 Q203992 Q188642 Q170323 Q203597 "
             "Q10677 Q10680 Q10683 Q170325 Q188808 Q209868 Q10676 Q1047516 Q200912 Q184198 Q751719 Q132020 "
             "Q48263 Q206261 Q1057377 Q1054350 Q229429 Q1046862 Q1023103 Q192851 Q99775 Q23882 Q100047 "
             "Q478829 Q627302 Q853547 Q47604 Q3017175").split()
PREFIXES = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX bd: <http://www.bigdata.com/rdf#>
"""
GAMES = PREFIXES + """SELECT ?tid ?platform ?platformName ?links ?article ?name ?nameMul WHERE {
  VALUES ?platform { %s }
  ?tid wdt:P400 ?platform; wdt:P31 wd:Q7889; wikibase:sitelinks ?links.
  OPTIONAL { ?article schema:about ?tid; schema:isPartOf <https://en.wikipedia.org/>. }
  OPTIONAL { ?tid rdfs:label ?name. FILTER(LANG(?name) = "en") }
  OPTIONAL { ?tid rdfs:label ?nameMul. FILTER(LANG(?nameMul) = "mul") }
  OPTIONAL { ?platform rdfs:label ?platformName. FILTER(LANG(?platformName) = "mul") }
}""" % " ".join(f"wd:{p}" for p in PLATFORMS)
TRAITS = PREFIXES + """SELECT ?tid ?value ?valueLabel WHERE {
  VALUES ?platform { %s }
  ?tid wdt:P400 ?platform; wdt:P31 wd:Q7889; wdt:{prop} ?value.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul". }
}""".replace("%s", " ".join(f"wd:{p}" for p in PLATFORMS))
KINDS = ("series", "developers", "publishers", "genres")
QID = re.compile(r"^Q[0-9]+$")


def qid(value):
    """Q123 of a Wikidata entity's address, or None."""
    tail = (value or "").rsplit("/", 1)[-1]
    return tail if QID.match(tail) else None


def games_of(rows):
    """{QID: {"name": …, "platforms": [[QID, name]]}} from GAMES' rows."""
    out = {}
    for b in rows:
        game, platform = qid(b["tid"]["value"]), qid(b["platform"]["value"])
        if not game or not platform:
            continue
        g = out.setdefault(game, {"name": "", "platforms": []})
        if not g["name"]:
            # The English label, else the one for every language (Wikidata's "mul").
            g["name"] = (b.get("name") or b.get("nameMul") or {}).get("value", "")[:200]
        if all(p != platform for p, _ in g["platforms"]):
            g["platforms"].append([platform, b.get("platformName", {}).get("value", "")[:120]])
    return out


def query(text):
    return common.sparql(text)


def main():
    out_dir = sys.argv[1]
    previous_dir = sys.argv[2] if len(sys.argv) > 2 else None
    today = datetime.date.today()
    report = []
    rows = query(GAMES)
    known = build.games(rows, ident=qid)
    games = games_of(rows)
    print(f"retro: {len(games)} games", file=sys.stderr)
    by_kind = {}
    for kind in KINDS:
        try:
            by_kind[kind] = query(TRAITS.replace("{prop}", features.KINDS[kind][0]))
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            print(f"retro: {kind}: {e}, left out", file=sys.stderr)
            by_kind[kind] = []
        print(f"retro: {kind}: {len(by_kind[kind])} rows", file=sys.stderr)
        time.sleep(5)
    traits = features.traits(by_kind, qid)
    for game, kinds in traits.items():
        if game in games:
            games[game].update(kinds)
    starts, end = build.months(today)
    read = build.read_views(known, starts, end)

    def payload(source, entries, **extra):
        return {"platform": RETRO, "generated": today.isoformat(), **extra, "schema": common.SCHEMA, "source": source,
                "games": entries}
    by_id = lambda d: dict(sorted(d.items(), key=lambda kv: int(kv[0][1:])))   # noqa: E731
    common.publish(out_dir, f"{RETRO}/games.json", payload(
        "Wikidata (P400, P179, P178, P123, P136)", by_id(games)), previous_dir, report)
    common.publish(out_dir, f"{RETRO}/popular.json", payload(
        "Wikidata (P400, sitelinks), Wikimedia pageviews (en.wikipedia)", by_id(build.popular(known, {}, read)),
        month=starts[-1].strftime("%Y-%m"), views=bool(read)), previous_dir, report)
    common.publish(out_dir, f"{RETRO}/similar.json", payload(
        "retro/games.json's traits", by_id(features.similar(
            {g: {k: games[g][k] for k in KINDS if k in games[g]} for g in games}, max_shared=300))),
        previous_dir, report)
    print(common.summary(report), file=sys.stderr)


if __name__ == "__main__":
    main()
