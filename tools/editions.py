"""A game's other editions (a Deluxe, a Complete Edition, a Game of the Year,
the game with a DLC pack): one game to a player, not two to suggest, as
titledb lists them under one publisher and a name that differs only by its
edition words.

editions.json: {"schema": 1, "games": {"<edition's title id>": "<the game's title id>", ...}}

The game is the edition out first; a game with no other edition is not
listed. Words that make another game (Remastered, Special, Enhanced, a
second title after "+") are not edition words: those stay apart.
"""
import collections
import re

from taxonomy import company_key

EDITION = re.compile(r"""\s*(?:[-:–—(]\s*)?(?:the\s+)?(?:digital\s+)?
  (?:deluxe|complete|definitive|ultimate|gold|premium|collector'?s|game\s+of\s+the\s+year|goty|anniversary|season\s+pass|expanded|standard)
  (?:\s+(?:edition|bundle|pack|version))?\)?\s*$""", re.I | re.X)
# A platform in brackets after the name ("Grand Theft Auto V (Xbox Series X|S)"): the same game on its machine.
PLATFORM_TAG = re.compile(r"\s*[(\[]\s*(?:xbox\b|playstation\s*[45]|ps\s*[45]\b|pc\b|windows\b|nintendo switch|switch\b|steam\b)[^)\]]*[)\]]\s*$", re.I)
PLUS_DLC = re.compile(r"\s*\+\s*[^+]*\b(?:dlc|pack|expansion|season pass|add-?ons?)\b.*$", re.I)


def core(name):
    """A name without its edition words, folded for comparing."""
    n = re.sub(r"[™®©]", "", name or "").strip()
    n = PLUS_DLC.sub("", n)
    n = PLATFORM_TAG.sub("", n)
    for _ in range(2):
        n = EDITION.sub("", n).strip(" -:–—")
    n = re.sub(r"\s+(?:edition|bundle)$", "", n, flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", n.lower()).strip()


def editions(titles, base_id):
    """{edition's title id: the game's title id} from titledb's entries."""
    groups = collections.defaultdict(list)
    for entry in titles.values():
        tid = base_id(entry.get("id"))
        name = entry.get("name")
        if not tid or not name or entry.get("isDemo") in (True, "True"):
            continue
        key = (core(name), company_key(str(entry.get("publisher") or "")))
        if not key[0]:
            continue
        try:
            date = int(entry.get("releaseDate") or 99999999)
        except (TypeError, ValueError):
            date = 99999999
        groups[key].append((date, tid))
    out = {}
    for members in groups.values():
        members = sorted(set(members))
        tids = []
        for _, tid in members:
            if tid not in tids:
                tids.append(tid)
        for tid in tids[1:]:
            out[tid] = tids[0]
    return dict(sorted(out.items()))


def apart(similar, of):
    """similar.json's lists without a game's own editions (the same game
    is not a game like it)."""
    def game(tid):
        return of.get(tid, tid)
    out = {}
    for tid, row in similar.items():
        kept = [pair for pair in row if game(pair[0]) != game(tid)]
        if kept:
            out[tid] = kept
    return out


def by_name(names: dict, companies: dict, order: dict) -> dict:
    """{edition's id: the game's id} for any platform, from the names alone: a game whose name is another's plus edition
    words ("X - Gold Edition" next to "X"), put out by a company the two share (a developer or a publisher). The game is
    the one with no edition word in its name: a game that has none is never an edition (two "Resident Evil 4" from
    different years are two games), and an edition with no such game to belong to stays apart. When several games
    qualify, the one out first (`order`: id -> sortable) is it.
    companies: id -> set of company keys; order: id -> release (yyyymmdd, large when unknown)."""
    groups = collections.defaultdict(list)
    for gid, name in names.items():
        key = core(name)
        if key:
            groups[key].append(gid)
    plain_of = lambda name: re.sub(r"[^a-z0-9]+", " ", re.sub(r"[™®©]", "", name or "").lower()).strip()
    out = {}
    for key, ids in groups.items():
        if len(ids) < 2:
            continue
        plain = [g for g in ids if plain_of(names[g]) == key]
        for gid in ids:
            if plain_of(names[gid]) == key:
                continue
            mine = companies.get(gid) or set()
            found = [g for g in plain if mine & (companies.get(g) or set())]
            if found:
                out[gid] = min(found, key=lambda g: (order.get(g, 99999999), g))
    return out
