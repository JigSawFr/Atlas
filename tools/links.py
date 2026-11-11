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
none of is left out. The 3DS's games are by their family (tools/n3ds.py),
the PS4's and PS5's by their Wikidata item (ps4, ps5: tools/playstation.py's
folders), for the games tied to another platform.

When sources/igdb/external.json exists (IGDB's keys), tools/identity.py adds the ids IGDB gives a
game on Steam, GOG, Epic and the Microsoft Store, and the games only IGDB knows, by "igdb:<id>"
instead of a Wikidata item; an id two games claim is left out.

One query to Wikidata's query service a run; when it turns the run away,
QLever's copy of Wikidata (qlever.dev) is asked the same.

platforms/switch/also.json is cut from it: each Switch game sold on another store, by its title id,
with its ids there ({"0100A1B2C3D4E000": {"steam": ["900010"], "xbox": ["9ZZZZZZZZZZ1"]}}), some
kilobytes where links.json is megabytes.

Usage: tools/links.py <out-dir> <previous-dir> <sources-dir>   (writes out-dir/links.json and
platforms/switch/also.json,
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
# The platforms platforms/switch/also.json names a Switch game's other stores by.
ALSO = ("steam", "ps", "xbox", "gog", "epic")
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


def also(games):
    """{Switch title id: {platform: [ids]}} for the Switch games sold on another store (ALSO), cut
    from links.json's games so a reader that knows a game by its title id (PlayShelf) need not read
    all of them."""
    out = {}
    for found in games.values():
        others = {p: found[p] for p in ALSO if found.get(p)}
        if others:
            for title_id in found.get("switch") or ():
                out[title_id] = others
    return dict(sorted(out.items()))


def rows():
    """The query's rows, from Wikidata's service, else QLever's."""
    try:
        return common.sparql(QUERY)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        print(f"links: Wikidata's service: {e}; QLever asked", file=sys.stderr)
        body = common.fetch(QLEVER + "?" + urllib.parse.urlencode({"query": QUERY}), tries=3, timeout=300,
                            headers={"Accept": "application/sparql-results+json"})
        return body["results"]["bindings"]


def with_igdb(games, src):
    """`games` with the ids IGDB's store pages add (tools/identity.py), then the items by number,
    the games of IGDB alone ("igdb:<id>") after them. Nothing changes without sources/igdb/external.json."""
    import identity
    groups = identity.igdb_groups(src("igdb/external.json").get("items"))
    named = {}
    if groups:
        by_switch = {t: q for q, ids in games.items() for t in ids.get("switch", [])}
        rows = [{"tid": {"value": by_switch[b["tid"]["value"].upper()]}, "slug": b["slug"]}
                for b in common.bindings(src("wikidata/switch-igdb.json").get("rows") or [])
                if b["tid"]["value"].upper() in by_switch]
        named = identity.qid_to_igdb(rows, src("igdb/games.json").get("items"))
        named.update(identity.qid_to_igdb(common.bindings(src("wikidata/others-igdb.json").get("rows") or []),
                                          src("igdb/others.json").get("items")))
    games, found = identity.combine(games, groups, named)
    if groups:
        print(f"links: IGDB's store pages: {found['joined']} games given ids, {found['new']} games of its own, "
              f"{len(found['conflicts'])} left out (an id of two games)", file=sys.stderr)
    return dict(sorted(games.items(), key=lambda kv: (0, int(kv[0][1:])) if kv[0][1:].isdigit() else (1, kv[0])))


def main():
    out_dir, previous_dir, sources_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    src = common.reader(sources_dir, previous_dir)
    games = links(common.bindings(src("wikidata/links.json").get("rows") or []))
    # The 3DS's games Wikidata knows by their name (it has no 3DS title id): their family.
    import n3ds
    for qid, found in n3ds.built(src)[1].items():
        games.setdefault(qid, {})[n3ds.N3DS] = found
    # The PS4's and PS5's games, by their Wikidata item: tied to the ones it has
    # ids of elsewhere, or to each other when a game is on both.
    import playstation
    for qid, machines in playstation.machines_by_game(src).items():
        if qid in games or len(machines) > 1:
            for pid in machines:
                games.setdefault(qid, {})[pid] = [qid]
    games = with_igdb(games, src)
    report = []
    common.publish(out_dir, "links.json", {
        "schema": common.SCHEMA, "generated": datetime.date.today().isoformat(),
        "source": "Wikidata (" + ", ".join(PROPERTIES) + ")", "games": games}, previous_dir, report)
    common.publish(out_dir, "platforms/switch/also.json", {
        "schema": common.SCHEMA, "platform": "switch", "generated": datetime.date.today().isoformat(),
        "source": "links.json (Wikidata: " + ", ".join(p for p in PROPERTIES if PROPERTIES[p] in ALSO) + ")",
        "games": also(games)}, previous_dir, report)
    platforms.write_registry(out_dir)
    print(common.summary(report), file=sys.stderr)


if __name__ == "__main__":
    main()
