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

EDITION = re.compile(r"""\s*(?:[-:–—(]\s*)?(?:the\s+)?(?:digital\s+)?
  (?:deluxe|complete|definitive|ultimate|gold|premium|collector'?s|game\s+of\s+the\s+year|goty|anniversary|season\s+pass|expanded|standard)
  (?:\s+(?:edition|bundle|pack|version))?\)?\s*$""", re.I | re.X)
PLUS_DLC = re.compile(r"\s*\+\s*[^+]*\b(?:dlc|pack|expansion|season pass|add-?ons?)\b.*$", re.I)


def core(name):
    """A name without its edition words, folded for comparing."""
    n = re.sub(r"[™®©]", "", name or "").strip()
    n = PLUS_DLC.sub("", n)
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
        key = (core(name), str(entry.get("publisher") or "").lower())
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
