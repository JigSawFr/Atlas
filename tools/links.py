#!/usr/bin/env python3
"""links.json: each game Wikidata knows on a store, by its Wikidata item
(QID), with its ids on every platform, so a reader can go from a game on one
platform to the same game on another ("also on Steam"), and Atlas
can weigh a game's renown (Wikipedia) once for all its platforms.

{"schema": 1, "generated": "YYYY-MM-DD", "source": "Wikidata",
 "games": {"Q900001": {"switch": ["0100A1B2C3D4E000"], "steam": ["900010"],
                       "ps": ["10900001"], "ps_product": ["EP0001-PPSA00001_00-AMBERLANTERN0000"],
                       "xbox": ["9ZZZZZZZZZZ1"], "gog": ["amber_lantern"], "epic": ["amber-lantern"]}}}

Each platform's ids as its store writes them: a Switch base game's title id
(upper case), a Steam app id, a PlayStation Store concept id (ps) and its
products (ps_product: North America, Europe, Japan), a Microsoft Store
product id (upper case), a GOG page's slug, an Epic Games Store page's slug.
A game may have several of a platform (editions, regions); a platform it has
none of is left out.

One query to Wikidata's query service a run; when it turns the run away,
QLever's copy of Wikidata (qlever.dev) is asked the same.

Usage: tools/links.py <out-dir> <previous-dir> <sources-dir>   (writes out-dir/links.json,
from sources/wikidata/links.json, tools/collect.py's)
"""
import datetime
import re
import sys
import urllib.error
import urllib.parse

import common
import platforms

QLEVER = "https://qlever.dev/api/wikidata"
# The platform each property's ids are of.
PROPERTIES = {
    "P11072": "switch", "P1733": "steam", "P12332": "ps",
    "P5944": "ps_product", "P5971": "ps_product", "P5999": "ps_product",
    "P5885": "xbox", "P2725": "gog", "P6278": "epic",
}
PLATFORMS = ("switch", "steam", "ps", "ps_product", "xbox", "gog", "epic")
QUERY = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT ?item ?prop ?v WHERE {
  VALUES ?prop { %s }
  ?item ?prop ?v.
}
""" % " ".join(f"wdt:{p}" for p in PROPERTIES)
SWITCH = re.compile(r"^0100[0-9A-F]{9}000$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
PS_PRODUCT = re.compile(r"^[A-Z]{2}[0-9]{4}-[A-Z]{4}[0-9]{5}_00-[0-9A-Z]{16}$")
XBOX = re.compile(r"^[0-9A-Z]{12}$")


def normal(platform, value):
    """An id as its platform writes it, or None when it is not one."""
    v = (value or "").strip()
    if platform == "switch":
        v = v.upper()
        return v if SWITCH.match(v) else None
    if platform in ("steam", "ps"):
        return v if v.isdigit() and len(v) <= 12 else None
    if platform == "ps_product":
        v = v.upper()
        return v if PS_PRODUCT.match(v) else None
    if platform == "xbox":
        v = v.upper()
        return v if XBOX.match(v) else None
    if platform == "gog":
        v = v.lower()
        v = v[len("game/"):] if v.startswith("game/") else v
        return v if SLUG.match(v) else None
    if platform == "epic":
        v = v.lower().strip("/")
        return v if SLUG.match(v) else None
    return None


def links(rows):
    """{QID: {platform: [ids]}} from the query's rows, each platform's ids sorted."""
    out = {}
    for b in rows:
        item = b["item"]["value"].rsplit("/", 1)[-1]
        platform = PROPERTIES.get(b["prop"]["value"].rsplit("/", 1)[-1])
        if not re.match(r"^Q[0-9]+$", item) or not platform:
            continue
        value = normal(platform, b["v"]["value"])
        if value:
            ids = out.setdefault(item, {}).setdefault(platform, [])
            if value not in ids:
                ids.append(value)
    for game in out.values():
        for platform in game:
            game[platform].sort()
    return {q: {p: out[q][p] for p in PLATFORMS if p in out[q]} for q in sorted(out, key=lambda q: int(q[1:]))}


def rows():
    """The query's rows, from Wikidata's service, else QLever's."""
    try:
        return common.sparql(QUERY)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        print(f"links: Wikidata's service: {e}; QLever asked", file=sys.stderr)
        body = common.fetch(QLEVER + "?" + urllib.parse.urlencode({"query": QUERY}), tries=3, timeout=300,
                            headers={"Accept": "application/sparql-results+json"})
        return body["results"]["bindings"]


def main():
    out_dir, previous_dir, sources_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    src = common.reader(sources_dir, previous_dir)
    games = links(common.bindings(src("wikidata/links.json").get("rows") or []))
    report = []
    common.publish(out_dir, "links.json", {
        "schema": common.SCHEMA, "generated": datetime.date.today().isoformat(),
        "source": "Wikidata (" + ", ".join(PROPERTIES) + ")", "games": games}, previous_dir, report)
    platforms.write_registry(out_dir)
    print(common.summary(report), file=sys.stderr)


if __name__ == "__main__":
    main()
