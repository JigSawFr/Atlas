"""Ties one game's ids on every store together from more than one source, so a game Wikidata
does not know, or knows by a few of its ids, is still one game.

- IGDB's external_games (tools/igdb.py, sources/igdb/external.json) give the ids a game has on
  Steam, GOG, Epic and the Microsoft Store. They are read here: platform_of(), store_id(), igdb_groups().
- combine() adds those groups to links.py's Wikidata items. A group joins the item that owns
  one of its ids, or the one Wikidata says is the same IGDB game (qid_to_igdb()). A group
  between two items, or an id two IGDB games claim, is never settled: it is left out and
  listed in the report. A group no item owns, with ids on two platforms or more, is a game of
  its own, "igdb:<IGDB id>".

What is not here yet: a link by the game's name and year (the games tied only by it would be
marked as inferred); see plans/atlas/identite-jeux.md.
"""
import re

import links

# IGDB's names for the sources whose ids Atlas has, as external_game_sources lists them.
SOURCES = {"steam": "steam", "gog": "gog", "epic games store": "epic", "epic games": "epic", "epic": "epic",
           "microsoft": "xbox", "microsoft store": "xbox", "xbox": "xbox"}
ORDER = links.PLATFORMS
_GOG = re.compile(r"gog\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?game/([a-z0-9_.-]+)", re.I)
_EPIC = re.compile(r"epicgames\.com/(?:[a-z]{2}(?:-[a-zA-Z]{2})?/)?p/([a-z0-9_.-]+)", re.I)
_XBOX = re.compile(r"(?:xbox|microsoft)\.com/.*/([0-9A-Za-z]{12})(?:[/?#]|$)")


def platform_of(source_name):
    """Atlas's platform of an IGDB external game source, or None."""
    return SOURCES.get(str(source_name or "").strip().casefold())


def store_id(platform, uid, url):
    """An external game's id as its platform writes it (links.normal), or None. Steam's is the uid;
    GOG's, Epic's and the Microsoft Store's ids are in the page's address (the uid is a number)."""
    uid, url = str(uid or "").strip(), str(url or "")
    if platform == "steam":
        return links.normal("steam", uid)
    found = {"gog": _GOG, "epic": _EPIC, "xbox": _XBOX}.get(platform)
    m = found.search(url) if found else None
    return links.normal(platform, m.group(1)) if m else None


def igdb_groups(items):
    """{IGDB game id: {platform: [ids]}} from [[game id, platform, id], ...]; a store id two
    games claim is claimed by none."""
    claims = {}
    for row in items or []:
        if not (isinstance(row, (list, tuple)) and len(row) == 3 and isinstance(row[0], int)
                and row[1] in ORDER and isinstance(row[2], str) and row[2]):
            continue
        claims.setdefault((row[1], row[2]), set()).add(row[0])
    out = {}
    for (platform, value), games in sorted(claims.items()):
        if len(games) == 1:
            out.setdefault(next(iter(games)), {}).setdefault(platform, []).append(value)
    return out


def qid_to_igdb(rows, items):
    """{QID: IGDB game id} from Wikidata's rows (?tid the item's address, ?slug IGDB's) and IGDB's
    games ({"slug", "id"}), the item and the game being the one of that slug."""
    ids = {str(i["slug"]).lower(): i["id"] for i in items or []
           if isinstance(i, dict) and isinstance(i.get("id"), int) and i.get("slug")}
    out = {}
    for b in rows:
        qid = (b["tid"]["value"] or "").rsplit("/", 1)[-1]
        game = ids.get(b["slug"]["value"].strip().lower())
        if re.match(r"^Q[0-9]+$", qid) and game:
            out[qid] = game
    return out


def _ordered(ids):
    known = [p for p in ORDER if p in ids]
    return {p: sorted(set(ids[p])) for p in known + [p for p in ids if p not in ORDER]}


def combine(wikidata, groups, named):
    """(games, report): `wikidata` {QID: {platform: [ids]}} with the IGDB groups' ids added.
    `named` is {QID: IGDB game id}. The report: joined (items given ids), new (games of IGDB
    alone), conflicts ([[IGDB id, [QIDs]], ...])."""
    owner = {}
    for qid, ids in wikidata.items():
        for platform, values in ids.items():
            for v in values:
                owner.setdefault((platform, v), set()).add(qid)
    named_by = {}
    for qid, game in named.items():
        named_by.setdefault(game, set()).add(qid)
    games = {q: {p: list(v) for p, v in ids.items()} for q, ids in wikidata.items()}
    extra, report = {}, {"joined": 0, "new": 0, "conflicts": []}
    for game in sorted(groups):
        ids = groups[game]
        found = set(named_by.get(game, ()))
        for platform, values in ids.items():
            for v in values:
                found |= owner.get((platform, v), set())
        if len(found) > 1:
            report["conflicts"].append([game, sorted(found, key=lambda q: int(q[1:]))])
        elif found:
            target = games.setdefault(next(iter(found)), {})     # an item Wikidata gave no store id to
            added = False
            for platform, values in ids.items():
                have = target.setdefault(platform, [])
                new = [v for v in values if v not in have]
                have += new
                added = added or bool(new)
            report["joined"] += added
        elif len(ids) > 1:
            extra[f"igdb:{game}"] = ids
            report["new"] += 1
    out = {q: _ordered(ids) for q, ids in games.items()}
    out.update({k: _ordered(v) for k, v in sorted(extra.items(), key=lambda kv: int(kv[0][5:]))})
    return out, report
