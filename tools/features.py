"""What tools/build.py adds beyond popularity: each game's traits (its series,
developers, publishers, genres and modes, from Wikidata; its themes, keywords
and player perspectives, from IGDB when the keys are there), its Steam
audience (from SteamSpy, for the games also sold on Steam), and, from the
traits, the games most like each one (similar.json).

The similarity of two games weighs the traits they share, each by how rare
it is (its inverse document frequency) and by its kind (WEIGHT: a series
counts most, a mode or a perspective least), over the square root of what each has:
a cosine over weighted sets. Two games sharing only a mode are not similar.
"""
import math
import sys
import time
import urllib.error

# What each trait is, its Wikidata property, and how much sharing one counts.
KINDS = {
    "series": ("P179", 4.0),
    "developers": ("P178", 2.0),
    "genres": ("P136", 1.0),
    "publishers": ("P123", 0.5),
    "modes": ("P404", 0.5),
}
# IGDB's (tools/igdb.py), when the repository has its keys.
IGDB_WEIGHT = {"themes": 1.0, "keywords": 1.0, "perspectives": 0.5}
WEIGHT = {**{kind: w for kind, (_, w) in KINDS.items()}, **IGDB_WEIGHT}
WEAK = {"modes", "publishers", "perspectives"}   # not enough alone to make two games alike
SIMILAR = 12                     # the games kept as like each one
MAX_TRAITS = 12                  # of a kind, a game's first ones
STEAMSPY = "https://steamspy.com/api.php?request=appdetails&appid={}"
STEAM_PAUSE = 1.05               # SteamSpy allows a request a second
STEAM_BUDGET = 2700              # seconds spent on SteamSpy a run, at most

TRAIT_QUERY = """
SELECT ?tid ?value ?valueLabel WHERE {{
  ?game wdt:P11072 ?tid; wdt:{prop} ?value.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""
STEAM_QUERY = """
SELECT ?tid ?steam WHERE { ?game wdt:P11072 ?tid; wdt:P1733 ?steam. }
"""


def qid(uri):
    """Q123 of a Wikidata entity's address, or None."""
    tail = (uri or "").rsplit("/", 1)[-1]
    return tail if tail[:1] == "Q" and tail[1:].isdigit() else None


def traits(rows_by_kind, base_id):
    """{title id: {kind: [[qid, label], ...]}} from each kind's query rows, in
    the order Wikidata gives them, each value once, MAX_TRAITS at most."""
    out = {}
    for kind, rows in rows_by_kind.items():
        for b in rows:
            tid = base_id(b["tid"]["value"])
            value = qid(b["value"]["value"])
            if not tid or not value:
                continue
            label = b.get("valueLabel", {}).get("value", "")
            # No English label: Wikidata gives the id itself.
            if not label or label == value:
                label = ""
            have = out.setdefault(tid, {}).setdefault(kind, [])
            if len(have) < MAX_TRAITS and all(v[0] != value for v in have):
                have.append([value, label[:120]])
    return out


def steam_ids(rows, base_id):
    """{title id: Steam app id} (the smallest, for a game with several)."""
    out = {}
    for b in rows:
        tid = base_id(b["tid"]["value"])
        app = b["steam"]["value"].strip()
        if tid and app.isdigit():
            out[tid] = min(out.get(tid, int(app)), int(app))
    return out


def owners_low(text):
    """The lower bound of SteamSpy's owners range ("2,000,000 .. 5,000,000")."""
    head = (text or "").split("..")[0].replace(",", "").strip()
    return int(head) if head.isdigit() else 0


def steam_of(body):
    """What a SteamSpy answer says of a game, or None when it says nothing."""
    if not isinstance(body, dict):
        return None
    positive, negative = body.get("positive"), body.get("negative")
    if not isinstance(positive, int) or not isinstance(negative, int) or positive + negative == 0:
        return None
    ccu = body.get("ccu") if isinstance(body.get("ccu"), int) else 0
    return {"positive": positive, "negative": negative, "owners": owners_low(body.get("owners")), "ccu": ccu}


def read_steam(apps, previous, fetch, budget=STEAM_BUDGET, now=time.monotonic, sleep=time.sleep):
    """{title id: SteamSpy's figures}: asked for each game, the ones not known
    from `previous` first, until `budget` seconds are spent; the rest keep
    what `previous` (the last run's games.json) said of them."""
    out = {}
    known = {tid for tid in apps if tid in previous and previous[tid].get("app") == apps[tid]}
    order = sorted(apps, key=lambda tid: (tid in known, tid))
    start = now()
    asked = 0
    for tid in order:
        if now() - start > budget:
            break
        try:
            got = steam_of(fetch(STEAMSPY.format(apps[tid])))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"steam: {apps[tid]}: {e}", file=sys.stderr)
            got = None
        asked += 1
        if got:
            got["app"] = apps[tid]
            out[tid] = got
        sleep(STEAM_PAUSE)
    for tid in apps:
        if tid not in out and tid in known:
            out[tid] = previous[tid]
    print(f"steam: {asked} of {len(apps)} asked, {len(out)} known", file=sys.stderr)
    return out


def similar(game_traits, keep=SIMILAR):
    """{title id: [[title id, 1..100], ...]}: each game's most similar, the most first."""
    # Each trait's weight: its kind's, times how rare it is.
    counts = {}
    for kinds in game_traits.values():
        for kind, values in kinds.items():
            for value, _ in values:
                counts[(kind, value)] = counts.get((kind, value), 0) + 1
    total = max(len(game_traits), 1)
    weight = {key: WEIGHT[key[0]] * math.log(1 + total / n) for key, n in counts.items() if key[0] in WEIGHT}
    vectors = {}
    for tid, kinds in game_traits.items():
        keys = {(kind, value) for kind, values in kinds.items() for value, _ in values if (kind, value) in weight}
        if keys:
            vectors[tid] = (keys, math.sqrt(sum(weight[k] ** 2 for k in keys)))
    # Who has each trait, to compare a game only with those sharing one.
    holders = {}
    for tid, (keys, _) in vectors.items():
        for k in keys:
            holders.setdefault(k, []).append(tid)
    out = {}
    for tid, (keys, norm) in vectors.items():
        scores = {}
        strong = {}
        for k in keys:
            for other in holders[k]:
                if other == tid:
                    continue
                scores[other] = scores.get(other, 0.0) + weight[k] ** 2
                if k[0] not in WEAK:
                    strong[other] = True
        ranked = []
        for other, dot in scores.items():
            if not strong.get(other):
                continue
            cosine = dot / (norm * vectors[other][1])
            if round(cosine * 100) > 0:
                ranked.append((-cosine, other))
        ranked.sort()
        if ranked:
            out[tid] = [[other, round(-c * 100)] for c, other in ranked[:keep]]
    return dict(sorted(out.items()))


def query_traits(sparql, pause=5):
    """Each kind's rows, one query each (Wikidata's service may allow one a minute: waited for)."""
    rows = {}
    for kind, (prop, _) in KINDS.items():
        rows[kind] = sparql(TRAIT_QUERY.format(prop=prop))
        print(f"{kind}: {len(rows[kind])} rows", file=sys.stderr)
        time.sleep(pause)
    return rows


def steam_scale(steam, tid, most):
    """A game's Steam audience on 0..1 (its reviews, on a log scale against the most), 0 when unknown."""
    s = steam.get(tid)
    if not s or most <= 0:
        return 0.0
    return math.log1p(s["positive"] + s["negative"]) / math.log1p(most)
