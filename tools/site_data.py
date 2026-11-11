"""What the website's explorer reads (site/README.md), made from a copy of
the data branch: the published files stay as they are under data/, and x/
holds them cut for a phone, one platform a folder:

- x/<platform>/lists.json: the lists the explorer opens on (the best known,
  the trending, the coming soon), each game with its name;
- x/<platform>/days.json: for each day of the year (MMDD) the best known games released that day in an earlier
  year, for the first page's "On this day"; lists.json also holds the games out in the last RECENT_DAYS days;
- g/<platform>/<id>/index.html: for each platform's SHARE_LIST best known games a page that gives a link preview
  (title, Steam's header) and opens the game's sheet, for the share button;
- x/<platform>/names.json: every game with a name, for the search (an edition is found by its name and opens its game);
- x/<platform>/facets.json: for each facet (genres, modes, series,
  developers, publishers, themes, perspectives, tags, year) its values with
  the number of named games that have them, for the explorer's menus;
- x/<platform>/browse/<page>.json: every named game, best known first, PAGE
  of them a page, as [id, name, score, trend, critics, year] rows and, for
  each facet, the rows of the page that have each value (the value's number
  in facets.json, then the row numbers as the gap from the one before), so
  the explorer filters in the browser and fetches the next page only when it
  needs more;
- x/<platform>/g/<shard>.json: each game's sheet (what every file says of
  it, its ids on the other platforms), the games spread over shards by
  shard() so a sheet costs one small file.

Python's standard library only. Usage: see tools/build_site.py.
"""
import datetime
import html
import json
import os
import re
from bisect import bisect_left

from common import SCHEMA
from taxonomy import KINDS, clean_title, game_title, company_key, company_merges, drop_note, split_company, find, fold, tidy_label, with_parents
import common
from editions import by_name as editions_by_name
import extracts
import tech
import trends
import wdfacts

LIST = 200              # games a list holds
RECENT_DAYS = 60        # days back the "just out" list reaches (the page shows the last week or two of them)
RECENT_LIST = 40        # games it holds
DAY_LIST = 4            # games a day of the year holds in days.json
SHARE_LIST = 60         # best known games a platform has a page of their own for, so a shared link has a preview (explore.js SHARE_LIST)
SHARE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
PAGE = 5000             # games a page of the browse index holds
FACETS = ("genres", "themes", "modes", "perspectives", "styles", "moods", "gameplay", "content", "access",
          "series", "developers", "publishers", "tags")
FACET_VALUES = 300      # values a facet keeps (the most common), year aside
FACET_MIN = 2           # games a value needs to be worth a filter
UNIFIED_SIMILAR = 12    # games a unified sheet lists as alike
# Whose name a unified sheet takes when the platforms disagree and none is more common.
PRIORITY = ("steam", "switch", "gog", "xbox", "ps5", "ps4", "3ds")
SHARD_BYTES = 160_000   # about what a shard of sheets weighs, at most on average
# Each store's page of a game, by the platform's id in links.json.
STORES = {
    "switch": None,
    "steam": "https://store.steampowered.com/app/{}/",
    "ps": "https://store.playstation.com/concept/{}",
    "xbox": "https://www.xbox.com/games/store/-/{}",
    "gog": "https://www.gog.com/game/{}",
    "epic": "https://store.epicgames.com/p/{}",
}


def shard(game_id: str, shards: int) -> int:
    """The shard a game's sheet is in; explore.js computes the same."""
    h = 0
    for c in game_id:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return h % shards


def read(path, schema=SCHEMA):
    """A data file, None when there is none (or it is of another schema than `schema`)."""
    try:
        with open(path, encoding="utf-8") as f:
            body = json.load(f)
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) and body.get("schema") == schema else None


def platforms(data_dir: str) -> list:
    """The platforms the data has: each folder of platforms/ with a popular.json (of our schema)."""
    out = []
    base = os.path.join(data_dir, "platforms")
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if read(os.path.join(base, name, "popular.json")) is not None:
            out.append(name)
    return out


def reverse_links(links: dict) -> dict:
    """{platform: {id: (qid, {platform: [ids]})}} from links.json."""
    out = {}
    for qid, ids in ((links or {}).get("games") or {}).items():
        for platform, values in ids.items():
            for v in values:
                out.setdefault(platform, {})[str(v)] = (qid, ids)
    return out


# The kinds of traits, in the order a sheet lists them; the notions' kinds are the ones the taxonomy fills.
TRAIT_KINDS = ("genres", "themes", "modes", "perspectives", "styles", "moods", "gameplay", "content", "access",
               "series", "developers", "publishers", "tags", "keywords")
NOTIONS = ("genres", "themes", "modes", "perspectives", "tags")     # whose words the taxonomy may name
COMPANIES = ("developers", "publishers")                              # whose names are one by company_key


def tidy(kind: str, name: str) -> str:
    """A trait's name as a sheet shows it: cleaned, and a company's without the note in brackets at its end."""
    name = clean_title(name)
    return clean_title(drop_note(name)) if kind in COMPANIES else name


def same(kind: str, name: str) -> str:
    """What makes two spellings of a trait one: a company's name without its legal words, else the name folded."""
    return company_key(name) if kind in COMPANIES else fold(name)


def raw_traits(game: dict, tags: dict) -> dict:
    """A game's traits as {kind: [names]}, as its sources wrote them: Wikidata's, IGDB's or Steam's."""
    out = {}
    for kind in ("series", "developers", "publishers", "genres", "modes", "themes", "keywords", "perspectives"):
        names = [t[1] for t in game.get(kind) or [] if isinstance(t, list) and len(t) > 1 and t[1]]
        if kind in COMPANIES:
            names = [part for name in names for part in split_company(name)]      # "A / B" is two companies
        if names:
            out[kind] = names
    if game.get("tags"):
        out["tags"] = [tags.get(str(t), "") for t in game["tags"] if tags.get(str(t))]
    return out


def tally(games: dict, tags: dict, seen: dict = None) -> dict:
    """{(is a company, same name): {spelling: games}} of the traits the taxonomy does not name, added to `seen`."""
    seen = {} if seen is None else seen
    for game in games.values():
        if isinstance(game, dict):
            for kind, names in raw_traits(game, tags).items():
                for name in names:
                    name = tidy(kind, name)
                    if kind not in NOTIONS:
                        count = seen.setdefault((kind in COMPANIES, same(kind, name)), {})
                        count[name] = count.get(name, 0) + 1
                    elif not find(name):
                        name = tidy_label(name)
                        count = seen.setdefault((False, fold(name)), {})
                        count[name] = count.get(name, 0) + 1
    return seen


def spelled_of(seen: dict) -> dict:
    """{(is a company, same name): the spelling most games use} from tally(): "SEGA" and "Sega" are one
    developer, and a company with descriptors added to a name the data has ("Konami Digital Entertainment")
    is written as that name ("Konami")."""
    spelled = {k: min(c, key=lambda n: (-c[n], n)) for k, c in seen.items()}
    uses = {k[1]: sum(c.values()) for k, c in seen.items() if k[0]}
    for key, base in company_merges(uses).items():
        spelled[(True, key)] = spelled[(True, base)]
    return spelled


def spellings(games: dict, tags: dict) -> dict:
    """spelled_of(tally()) for one set of games."""
    return spelled_of(tally(games, tags))


def trait_names(game: dict, tags: dict, spelled: dict = None) -> dict:
    """A game's traits as {kind: [values]}: what the taxonomy names is its key under the notion's
    kind (a Steam tag "Singleplayer" and Wikidata's "single-player video game" both give the mode
    "single"), the rest the name in the spelling most games use."""
    spelled = spelled or {}
    out = {}
    for kind, names in raw_traits(game, tags).items():
        for name in names:
            name = tidy(kind, name)
            found = find(name) if kind in NOTIONS else None
            if kind in NOTIONS and not found:
                name = tidy_label(name)
            where, value = (KINDS[found[0]], found[1]) if found else (kind, spelled.get((kind in COMPANIES, same(kind, name)), name))
            if value not in out.setdefault(where, []):
                out[where].append(value)
    return {k: out[k] for k in TRAIT_KINDS if out.get(k)}


def year_of(game: dict) -> int:
    """The year of a game's release (yyyymmdd), 0 when it has none."""
    release = game.get("release")
    return release // 10000 if isinstance(release, int) and release >= 10_000_000 else 0


# A list's row may end with the name of a picture for its tile, a letter and a name (explore.js `tile()`):
# "s<app>" Steam's header of the same game (by links.json or the game's own Steam app), "i<id>" IGDB's cover,
# and in the lists only (their names are long: some 70 characters, a page of the browse index would double)
# "g<name>" GOG's own landscape cover. Steam's own rows need none: their id is the app.
LONG_PICTURES = {"gog": "g"}


def by_release(scores: dict, games: dict, editions: dict, generated) -> tuple:
    """The games out in the RECENT_DAYS before `generated`, best known first, and for each day of the year (MMDD)
    the best known ones released that day in an earlier year: ([(id, release)], {MMDD: [(id, release)]})."""
    try:
        today = datetime.date.fromisoformat(generated)
    except (TypeError, ValueError):
        return [], {}
    now = today.year * 10000 + today.month * 100 + today.day
    back = today - datetime.timedelta(days=RECENT_DAYS)
    start = back.year * 10000 + back.month * 100 + back.day
    recent, days = [], {}
    for gid, score in scores.items():
        game = games.get(gid)
        release = game.get("release") if isinstance(game, dict) else None
        if gid in editions or not isinstance(release, int) or release < 10_000_000 or not score[0]:
            continue
        if start <= release <= now:
            recent.append((-score[0], gid, release))
        if release // 10000 < today.year:
            days.setdefault(f"{release % 10000:04d}", []).append((-score[0], gid, release))
    recent.sort()
    return ([(g, r) for _, g, r in recent],
            {day: [(g, r) for _, g, r in sorted(rows)[:DAY_LIST]] for day, rows in sorted(days.items())})


def share_page(platform: str, gid: str, name: str) -> str:
    """The page a shared link opens on: the name and a picture for the preview of chat apps and social sites, then
    the game's sheet in the explorer (g/<platform>/<id>/index.html, three folders under the site's root)."""
    target = f"../../../explore/#{platform}/game/{gid}"
    title = html.escape(f"{name} · Atlas")
    image = (f'<meta property="og:image" content="https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{gid}/header.jpg">'
             if platform == "steam" and gid.isdigit() else "")
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="referrer" content="no-referrer"><meta name="robots" content="noindex">'
            f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'none\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>{title}</title><meta property="og:type" content="website"><meta property="og:site_name" content="Atlas">'
            f'<meta property="og:title" content="{title}"><meta property="og:description" content="Scores, traits and alike games.">{image}'
            f'<meta http-equiv="refresh" content="0; url={target}"></head>\n<body><p><a href="{target}">{title}</a></p></body></html>\n')


def picture(platform: str, gid: str, game, link, store: dict, long_ok: bool) -> str:
    """The name of a tile's picture for a row, or ""."""
    if platform == "steam":
        return ""
    img = (store or {}).get("img") or {}
    if long_ok and platform in LONG_PICTURES and img.get("h"):
        return LONG_PICTURES[platform] + img["h"]
    app = None
    if link:
        app = next(iter(link[1].get("steam") or ()), None)
    if not app and isinstance(game, dict) and isinstance(game.get("steam"), dict):
        app = game["steam"].get("app")
    if app and str(app).isdigit():
        return f"s{app}"
    if isinstance(game, dict) and game.get("igdb_cover"):
        return f"i{game['igdb_cover']}"
    return ""


def atlas_score(score: list, game) -> int:
    """The Atlas score of a game on one platform, 0 when no signal backs it: the same weights as `atlasScore()` of
    explore.js, which pools a game's platforms (the list scores a platform's own).
      critics 35 %  the critics' score, store 30 %  the stores' good reviews pulled toward 70 as if 40 more were read,
      players 15 %  IGDB's players' rating (20 ratings or more) pulled toward 70 as if 30 more were read,
      reach 20 %  the square root of the renown back on 100; the weights are worked out over the signals there are,
      and one of the three quality signals at least is needed."""
    game = game if isinstance(game, dict) else {}
    parts = []                                                  # [value, weight]
    if len(score) > 2 and score[2]:
        parts.append((score[2], 0.35))
    n = total = 0
    for r in (game.get("reviews"), game.get("rating")):
        if r and r[0]:
            n += r[0]
            total += r[0] * r[1]
    if n:
        parts.append(((total + 40 * 70) / (n + 40), 0.3 * (n / (n + 100))))
    rating = game.get("igdb_rating")
    if rating and rating[1] >= 20:
        parts.append(((rating[1] * rating[0] + 30 * 70) / (rating[1] + 30), 0.15 * (rating[1] / (rating[1] + 30))))
    if not parts:
        return 0
    if score and score[0] > 0:
        parts.append((100 * (score[0] / 100) ** 0.5, 0.2))
    weights = sum(w for _, w in parts)
    return int(sum(v * w for v, w in parts) / weights + 0.5)


def browse(best: list, games: dict, names: dict, tags: dict, spelled: dict = None, pic=None) -> tuple:
    """The browse index of the named games in `best` ([(id, [score, trend, critics])],
    best first): (facets, pages), a row being [id, name, score, trend, critics, year, Atlas score, picture], and the facets as {facet: [[value, count]]} and
    each page as {"games": rows, "facets": {facet: [[value number, row gaps]]}}."""
    rows, found = [], {k: {} for k in (*FACETS, "year")}
    for gid, score in [b for b in best if names.get(b[0])]:
        game = games.get(gid)
        year = 0
        if isinstance(game, dict):
            year = year_of(game)
            traits = trait_names(game, tags, spelled)
            for kind in FACETS:
                values = traits.get(kind, ())
                if kind == "genres":
                    values = with_parents(values)      # a platformer is in the action games too
                for value in dict.fromkeys(values):
                    found[kind].setdefault(value, []).append(len(rows))
            if year:
                found["year"].setdefault(str(year), []).append(len(rows))
        row = [gid, names[gid], *(list(score) + [0, 0, 0])[:3], year, atlas_score(list(score), game)]
        ref = pic(gid, False) if pic else ""
        rows.append(row + [ref] if ref else row)
    kept = {}
    for kind, values in found.items():
        chosen = [(v, at) for v, at in values.items() if len(at) >= FACET_MIN]
        chosen.sort(key=(lambda x: -int(x[0])) if kind == "year" else (lambda x: (-len(x[1]), x[0])))
        if kind != "year":
            chosen = chosen[:FACET_VALUES]
        if chosen:
            kept[kind] = chosen
    facets = {kind: [[v, len(at)] for v, at in chosen] for kind, chosen in kept.items()}
    pages = []
    for start in range(0, len(rows), PAGE):
        page = {"games": rows[start:start + PAGE], "facets": {}}
        for kind, chosen in kept.items():
            out = []
            for number, (_, at) in enumerate(chosen):
                here = [r - start for r in at[bisect_left(at, start):bisect_left(at, start + PAGE)]]
                if here:
                    out.append([number, [here[0]] + [b - a for a, b in zip(here, here[1:])]])
            if out:
                page["facets"][kind] = out
        pages.append(page)
    return facets, pages


# What two alike games have in common, for the card of the one under the other: at most SHARED notions, the rarest
# first (a platformer and a farm sim are alike by "farm" before "indie"), as "<letter>:<key>" (taxonomy.KINDS' letters).
SHARED = 3
SHARED_KINDS = ("genres", "themes", "gameplay", "styles", "moods", "content")
LETTER = {kind: letter for letter, kind in KINDS.items()}


def shared_traits(a: dict, b: dict, rarity: dict) -> list:
    """The notions the traits `a` and `b` ({kind: [values]}) have in common, the rarest first (`rarity`: {(kind,
    value): games with it}, a value missing from it counting as the rarest), as "<letter>:<key>"."""
    found = []
    for kind in SHARED_KINDS:
        for value in (a.get(kind) or ()):
            if value in (b.get(kind) or ()):
                found.append((rarity.get((kind, value), 0), SHARED_KINDS.index(kind), f"{LETTER[kind]}:{value}"))
    return [x[2] for x in sorted(found)[:SHARED]]


def similar_row(o: str, name: str, score: int, pic: str, shared: list) -> list:
    """A sheet's alike game: [id, name, similarity, picture name, shared notions], the empty tail left out."""
    row = [o, name, score, pic, shared]
    while row[3:] and not row[-1]:
        row.pop()
    return row


STAT_TOP = 12           # genres, studios and publishers a platform's figures name
STAT_LIST = 10          # games in its best rated and hidden gems
STAT_YEAR_LIST = 3     # the best known games the timeline shows for a year
STAT_YEARS = 30         # years of releases it counts, the latest


def edition_map(names: dict, games: dict, known: dict) -> dict:
    """{edition's id: the game's id}: the editions a source lists, and those the names give."""
    def keys(gid):
        game = games.get(gid)
        found = set()
        for kind in ("developers", "publishers"):
            for c in (game.get(kind) or []) if isinstance(game, dict) else []:
                found.add(str(c[0] if isinstance(c, (list, tuple)) and c else c).casefold())
        return found
    companies = {g: keys(g) for g in names}
    order = {g: (games.get(g) or {}).get("release") or 99999999 if isinstance(games.get(g), dict) else 99999999 for g in names}
    out = editions_by_name(names, companies, order)
    out.update(known)
    return out


def alike(gid: str, pairs: list, editions: dict) -> list:
    """A game's alike list with each edition replaced by its game, the game itself (and its own editions) out, once each."""
    mine = editions.get(gid, gid)
    seen = {}
    for o, s in pairs:
        o = editions.get(o, o)
        if o != gid and o != mine:
            seen[o] = max(s, seen.get(o, s))
    return list(seen.items())


FAMILY = 12
SERIES_MAX = 30          # a "series" of more games than this is a publisher's or a store's label, not a series


def families(sheets: dict, pic) -> dict:
    """The games of a series, oldest first: {id: [series, [[id, name, release, picture], ...]]} for each game whose
    first series has another named game (and no more than SERIES_MAX). The first FAMILY of them, the game itself in
    place of the last when it is further on."""
    series = {}
    for gid, sheet in sheets.items():
        found = (sheet.get("traits") or {}).get("series")
        if found and sheet.get("name"):
            series.setdefault(found[0], []).append(gid)
    out = {}
    for name, ids in series.items():
        if not 2 <= len(ids) <= SERIES_MAX:
            continue
        ids.sort(key=lambda g: (sheets[g].get("release") or 99999999, sheets[g]["name"], g))
        rows = {}

        def row(g):
            if g not in rows:
                rows[g] = [g, sheets[g]["name"], sheets[g].get("release") or 0]
                if pic(g):
                    rows[g].append(pic(g))
            return rows[g]
        shown = ids[:FAMILY]
        for gid in ids:
            out[gid] = [name, [row(g) for g in (shown if gid in shown else shown[:-1] + [gid])]]
    return out


def mean(values: list):
    return round(sum(values) / len(values), 1) if values else None


def median(values: list):
    if not values:
        return None
    v = sorted(values)
    m = len(v) // 2
    return v[m] if len(v) % 2 else round((v[m - 1] + v[m]) / 2, 1)


def quantiles(values: list) -> list:
    """The 101 cut points of `values` (0 %, 1 % … 100 %): where a game stands among its platform's, on its sheet."""
    v = sorted(values)
    return [v[min(len(v) - 1, round(i * (len(v) - 1) / 100))] for i in range(101)] if v else []


def stats(platform: str, best: list, games: dict, names: dict, tags: dict, spelled: dict, pic, generated) -> dict:
    """A platform's figures, condensed at the build so the page reads one small file: how many named games,
    the critics' and renown's averages and spread, the releases by year, the most common genres, studios and
    publishers with their critics' average, the best rated and the hidden gems (critics high, renown low).
    `best` is [(id, [renown, trend, critics])], best known first; the named games only count."""
    rows = [(gid, list(sc) + [0, 0, 0]) for gid, sc in best if names.get(gid)]
    critics = [sc[2] for _, sc in rows if sc[2]]
    renown = [sc[0] for _, sc in rows]
    hist = [0] * 10
    for c in critics:
        hist[min(9, max(0, int(c) // 10))] += 1
    years, groups, per_year = {}, {"genres": {}, "developers": {}, "publishers": {}, "modes": {}}, {}
    for gid, sc in rows:
        game = games.get(gid)
        if not isinstance(game, dict):
            continue
        year = year_of(game)
        if year:
            years.setdefault(year, []).append(sc[2])
            per_year.setdefault(year, []).append((-sc[0], gid))
        traits = trait_names(game, tags, spelled)
        for kind, found in groups.items():
            for value in dict.fromkeys(traits.get(kind, ())):
                found.setdefault(value, []).append(sc)
    latest = sorted(years)[-STAT_YEARS:]

    def top(kind, need=1):
        found = [(v, scs) for v, scs in groups[kind].items() if len([x for x in scs if x[2]]) >= need]
        found.sort(key=lambda x: (-len(x[1]), x[0]))
        return [[v, len(scs), mean([x[2] for x in scs if x[2]]), mean([x[0] for x in scs])] for v, scs in found[:STAT_TOP]]

    rated = [(gid, sc) for gid, sc in rows if sc[2]]
    # A score from a handful of critics is noise among the unknown: the best rated are the best known quarter's
    # (renown at or above its third quartile), the hidden gems those with 85 or more known less than most and more
    # than the least known quarter (renown between its first quartile and its median).
    known = sorted(sc[0] for _, sc in rated)
    q = (lambda f: known[min(len(known) - 1, int(len(known) * f))]) if known else (lambda f: 0)
    best_rated = sorted([(g, sc) for g, sc in rated if sc[0] >= q(0.75)], key=lambda x: (-x[1][2], -x[1][0], x[0]))[:STAT_LIST]
    gems = sorted([(g, sc) for g, sc in rated if sc[2] >= 85 and q(0.25) <= sc[0] < q(0.5)],
                  key=lambda x: (-x[1][2], x[1][0], x[0]))[:STAT_LIST]

    def named(items):
        return [[g, names[g], sc[2], sc[0], *([pic(g, False)] if pic(g, False) else [])] for g, sc in items]

    return {
        "platform": platform, "generated": generated, "games": len(rows),
        "critics": {"n": len(critics), "mean": mean(critics), "median": median(critics), "hist": hist},
        "renown": {"mean": mean(renown), "median": median(renown), "q": quantiles(renown)},
        "years": [[y, len(years[y]), mean([c for c in years[y] if c])] for y in latest],
        # each of those years' best known games, for the timeline: {year: [[id, name, renown, picture], ...]}
        "by_year": {str(y): [[g, names[g], -r, *([pic(g, False)] if pic(g, False) else [])] for r, g in sorted(per_year[y])[:STAT_YEAR_LIST]] for y in latest},
        "genres": top("genres"), "developers": top("developers", 3), "publishers": top("publishers", 3),
        "modes": [[v, len(scs)] for v, scs in sorted(groups["modes"].items(), key=lambda x: (-len(x[1]), x[0]))[:6]],
        "best": named(best_rated), "gems": named(gems),
    }


REACH_KEPT = 6      # languages of a game's reach on its sheet


def reach_of(body: dict) -> dict:
    """{game: [[language, percent], …]} from a platform's reach.json: where the game is read on Wikipedia, its
    REACH_KEPT first languages by share, the ones nobody reads it in left out; {} for a file of another shape."""
    languages, out = body.get("languages"), {}
    if not isinstance(languages, list) or not isinstance(body.get("games"), dict):
        return out
    for gid, shares in body["games"].items():
        if isinstance(shares, list) and len(shares) == len(languages) and all(isinstance(x, int) for x in shares):
            found = sorted(((x, lang) for lang, x in zip(languages, shares) if x > 0 and isinstance(lang, str)), key=lambda r: (-r[0], r[1]))
            if found:
                out[gid] = [[lang, x] for x, lang in found[:REACH_KEPT]]
    return out


def overall(everyone: dict) -> dict:
    """The figures of all the games of all the platforms, each game once, for a sheet of a game on several platforms
    (its standing among the platforms' games, not one's): {game: [[renown, trend, critics], …]}, a game's renown
    being its best across its platforms (as its sheet's) and its critics' score their mean."""
    renown = [max(sc[0] for sc in scs) for scs in everyone.values()]
    critics = [mean([sc[2] for sc in scs if sc[2]]) for scs in everyone.values() if any(sc[2] for sc in scs)]
    return {"games": len(renown), "critics": {"n": len(critics), "mean": mean(critics), "median": median(critics)},
            "renown": {"mean": mean(renown), "median": median(renown), "q": quantiles(renown)}}


def unify(entries: dict, similar_of: dict) -> dict:
    """One sheet for a game on several platforms: {platform: (id, sheet)} merged. Its name is the
    one most platforms give; each platform keeps its own figures (release, renown, reviews, ratings),
    the traits are the union (most platforms first), the games alike are one list."""
    order = sorted(entries, key=lambda p: (PRIORITY.index(p) if p in PRIORITY else len(PRIORITY), p))
    out = {"platforms": []}
    count = {}
    for p in order:
        name = entries[p][1].get("name")
        if name:
            count[name] = count.get(name, 0) + 1
    if count:
        # Spellings that differ by case only are one name: its mixed case form wins over a shouting one.
        def weight(n):
            return (sum(c for m, c in count.items() if m.casefold() == n.casefold()), n != n.upper() and n != n.lower(), count[n])
        out["name"] = max(count, key=lambda n: (weight(n), -min(i for i, p in enumerate(order) if entries[p][1].get("name") == n)))
    for p in order:
        if entries[p][1].get("wd"):
            out["wd"] = entries[p][1]["wd"]          # the game's, the same on every platform
            break
    traits = {}
    for p in order:
        gid, sheet = entries[p]
        entry = {"p": p, "id": gid}
        for k in ("name", "release", "upcoming", "popular", "reviews", "rating", "igdb_rating", "igdb_cover", "igdb_art", "views", "reach", "steam", "gamepass", "tech", "editions", "edition_of", "slug"):
            if k in sheet:
                entry[k] = sheet[k]
        out["platforms"].append(entry)
        for kind, values in (sheet.get("traits") or {}).items():
            for v in values:
                found = traits.setdefault(kind, {})
                seen = found.setdefault(same(kind, v), [0, len(found), v])     # "SEGA" and "Sega Corporation": the first one's
                seen[0] += 1
    merged = {kind: [seen[2] for seen in sorted(found.values(), key=lambda x: (-x[0], x[1]))] for kind, found in traits.items()}
    ordered = {k: merged[k] for k in TRAIT_KINDS if merged.get(k)}
    if ordered:
        out["traits"] = ordered
    alike = {}
    for p in order:
        for ref in similar_of.get(p, ()):
            key = (ref[0], ref[1])
            if key not in alike or ref[3] > alike[key][3]:
                alike[key] = ref
    if alike:
        out["similar"] = sorted(alike.values(), key=lambda r: (-r[3], r[2], r[1]))[:UNIFIED_SIMILAR]
    for p in order:
        if entries[p][1].get("family"):
            name, rows = entries[p][1]["family"]
            out["family"] = [name, [[p, *row] for row in rows]]      # the games of its series, each on the platform that named it
            break
    links = {}
    for p in order:
        for other, ids in (entries[p][1].get("links") or {}).items():
            if other not in entries:
                for i in ids:
                    if i not in links.setdefault(other, []):
                        links[other].append(i)
    if links:
        out["links"] = links
    return out


def platform_files(data_dir: str, platform: str) -> dict:
    base = os.path.join(data_dir, "platforms", platform)
    return {k: read(os.path.join(base, f"{k}.json")) or {} for k in ("popular", "games", "upcoming", "similar", "editions", "names")}


def names_of(files: dict) -> dict:
    names = {gid: n for gid, n in (files["names"].get("games") or {}).items() if isinstance(n, str) and n}
    for gid, row in (files["upcoming"].get("games") or {}).items():
        if len(row) > 1 and row[1]:
            names[gid] = row[1]
    for gid, game in (files["games"].get("games") or {}).items():
        if isinstance(game, dict) and game.get("name"):
            names[gid] = game["name"]
    cleaned = {gid: game_title(n) for gid, n in names.items()}
    return {gid: n for gid, n in cleaned.items() if n}


def sharded(base: str, folder: str, entries: dict) -> int:
    """Writes entries over base/folder/<i>.json by shard(), SHARD_BYTES each
    on average; returns how many shards."""
    os.makedirs(os.path.join(base, folder), exist_ok=True)
    size = sum(len(json.dumps(s, separators=(",", ":"))) + len(g) + 4 for g, s in entries.items())
    shards = 1
    while size / shards > SHARD_BYTES:
        shards *= 2
    parts = [{} for _ in range(shards)]
    for gid, entry in entries.items():
        parts[shard(gid, shards)][gid] = entry
    for i, part in enumerate(parts):
        write(os.path.join(base, folder, f"{i}.json"), part)
    return shards


def build(data_dir: str, out_dir: str) -> dict:
    """Writes x/ into out_dir; returns {platform: summary} for the pages."""
    links = reverse_links(read(os.path.join(data_dir, "links.json")))
    summary = {}
    plats = platforms(data_dir)
    # The games on several of the platforms the data has (by Wikidata item): each has one sheet for all.
    where = {}
    for platform in plats:
        for qid, _ in (links.get(platform) or {}).values():
            where.setdefault(qid, set()).add(platform)
    multi = {q for q, ps in where.items() if len(ps) > 1}
    kept, similar_refs = {}, {}
    wd = wdfacts.facts(common.reader(data_dir))      # what Wikidata says of a game: its site, ratings, team, engine, trailers
    for qid, texts in (common.reader(data_dir)("wikipedia/extracts.json").get("items") or {}).items():
        about = {l: t for l, t in texts.items() if l in extracts.LANGS and isinstance(t, str) and t} if isinstance(texts, dict) else {}
        if about and wdfacts.QID.match(str(qid)):
            wd.setdefault(qid, {})["about"] = about            # Wikipedia's first lines (tools/extracts.py)
    curves = trends.curves(common.reader(data_dir))  # the best known games' Wikipedia views a week
    seen = {}      # the names of studios and publishers of every platform, so a company is written one way on all
    for platform in plats:
        found = read(os.path.join(data_dir, "platforms", platform, "games.json")) or {}
        tally(found.get("games") or {}, found.get("tags") or {}, seen)
    spelled = spelled_of(seen)
    every_platform = []     # each platform's headline figures, side by side (x/stats.json)
    everyone = {}           # each game once, its scores on every platform it is on (x/all/stats.json)
    for platform in plats:
        files = platform_files(data_dir, platform)
        scores = files["popular"].get("games") or {}
        games = files["games"].get("games") or {}
        tags = files["games"].get("tags") or {}
        names = names_of(files)
        upcoming = files["upcoming"].get("games") or {}
        similar = files["similar"].get("games") or {}
        reach = reach_of(read(os.path.join(data_dir, "platforms", platform, "reach.json")) or {})
        # A game's other editions are one game with it, not games of their own: titledb's (the Switch) and the ones the
        # names give (a name plus edition words, a company in common).
        editions = edition_map(names, games, files["editions"].get("games") or {})
        base = os.path.join(out_dir, "x", platform)
        os.makedirs(base, exist_ok=True)

        stores = tech.read(data_dir, platform)       # what the stores' own sources say: runs on, languages, ages, pictures
        own_links = links.get(platform) or {}

        def pic(gid, long_ok=True):
            return picture(platform, gid, games.get(gid), own_links.get(gid), stores.get(gid), long_ok)

        def with_pic(row, gid, long_ok=True):
            ref = pic(gid, long_ok)
            return row + [ref] if ref else row

        # Not in the lists nor the browse view (nor the figures): they are on their game's sheet.
        best = sorted(((g, s) for g, s in scores.items() if g not in editions), key=lambda kv: (-kv[1][0], kv[0]))
        trending = sorted(((g, s) for g, s in scores.items() if s[1] > 0 and g not in editions), key=lambda kv: (-kv[1][1], -kv[1][0], kv[0]))
        soon = sorted(((g, r) for g, r in upcoming.items() if g not in editions), key=lambda kv: (kv[1][0], kv[0]))
        recent, days = by_release(scores, games, editions, files["popular"].get("generated"))
        lists = {
            "platform": platform,
            "generated": files["popular"].get("generated"),
            "popular": [with_pic([g, names.get(g, ""), *(list(s) + [0, 0, 0])[:3]], g) for g, s in best[:LIST]],
            "trending": [with_pic([g, names.get(g, ""), *(list(s) + [0, 0, 0])[:3]], g) for g, s in trending[:LIST]],
            "upcoming": [with_pic([g, names.get(g, ""), r[0], r[2] if len(r) > 2 else 0], g) for g, r in soon[:LIST]],
            "recent": [with_pic([g, names[g], r, scores[g][0]], g) for g, r in recent if names.get(g)][:RECENT_LIST],
        }
        for gid, _ in best[:SHARE_LIST]:
            if names.get(gid) and SHARE_ID.match(gid):
                folder = os.path.join(out_dir, "g", platform, gid)
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
                    f.write(share_page(platform, gid, names[gid]))
        write(os.path.join(base, "days.json"), {"platform": platform, "days": {
            day: [with_pic([g, names[g], r, scores[g][0]], g) for g, r in rows if names.get(g)] for day, rows in days.items()}})
        write(os.path.join(base, "names.json"),
              # (an edition is found by its name, and opens its game)
              sorted(([editions.get(g, g), n, (scores.get(editions.get(g, g)) or [0])[0]] for g, n in names.items()), key=lambda x: (-x[2], x[1])))

        facets, pages = browse(best, games, names, tags, spelled, pic)
        rarity = {(kind, v): n for kind, values in facets.items() for v, n in values}
        generated = files["popular"].get("generated")
        figures = stats(platform, best, games, names, tags, spelled, pic, generated)
        write(os.path.join(base, "stats.json"), figures)
        for gid, sc in best:
            if names.get(gid):
                link = (links.get(platform) or {}).get(gid)
                everyone.setdefault(link[0] if link else f"{platform}:{gid}", []).append(list(sc) + [0, 0, 0])
        every_platform.append([platform, figures["games"], figures["critics"]["n"], figures["critics"]["mean"],
                               figures["renown"]["mean"], median([y for y, n, _ in figures["years"] for _ in range(n)])])
        os.makedirs(os.path.join(base, "browse"), exist_ok=True)
        for n, page in enumerate(pages):
            write(os.path.join(base, "browse", f"{n}.json"), {"page": n, **page})
        write(os.path.join(base, "facets.json"),
              {"platform": platform, "generated": generated, "page": PAGE, "pages": len(pages),
               "games": sum(len(p["games"]) for p in pages), "facets": facets})

        sheets = {}
        every = set(scores) | set(games) | set(upcoming) | set(similar)
        of_edition = {}
        for e, g in editions.items():
            of_edition.setdefault(g, []).append(e)
        for gid in every:
            sheet = {}
            if names.get(gid):
                sheet["name"] = names[gid]
            if gid in scores:
                sheet["popular"] = scores[gid]
            game = games.get(gid)
            if isinstance(game, dict):
                traits = trait_names(game, tags, spelled)
                if traits:
                    sheet["traits"] = traits
                for k in ("release", "reviews", "rating", "gamepass", "qid", "slug", "igdb_rating", "igdb_cover", "igdb_art"):
                    if game.get(k):
                        sheet[k] = game[k]
                if isinstance(game.get("steam"), dict):
                    sheet["steam"] = game["steam"]
            if gid in curves.get(platform, ()):
                sheet["views"] = curves[platform][gid]
            if gid in reach:
                sheet["reach"] = reach[gid]
            if gid in stores:
                sheet["tech"] = stores[gid]
            if gid in upcoming:
                sheet["upcoming"] = upcoming[gid][0]
            if gid in similar:
                mine = sheet.get("traits") or {}
                sheet["similar"] = [similar_row(o, names.get(o, ""), s, pic(o, False),
                                                shared_traits(mine, trait_names(games.get(o), tags, spelled) if isinstance(games.get(o), dict) else {}, rarity))
                                    for o, s in alike(gid, similar[gid], editions)]
            if gid in editions:
                sheet["edition_of"] = [editions[gid], names.get(editions[gid], "")]
            if gid in of_edition:
                sheet["editions"] = [[e, names.get(e, "")] for e in sorted(of_edition[gid])]
            link = (links.get(platform) or {}).get(gid)
            if link:
                sheet["qid"] = sheet.get("qid") or link[0]
                sheet["links"] = {p: ids for p, ids in link[1].items() if p != platform or ids != [gid]}
            if sheet.get("qid") in wd:
                sheet["wd"] = wd[sheet["qid"]]
            if sheet.get("qid") in multi and gid not in editions:
                sheet["unified"] = True
                kept.setdefault(sheet["qid"], {})[platform] = (gid, sheet)
                refs = []
                for o, name, score, *ref in sheet.get("similar", ()):
                    target = (links.get(platform) or {}).get(o)
                    if target and target[0] in multi:
                        if target[0] != sheet["qid"]:
                            # A sheet of all its platforms has no app id to draw Steam's picture from: it is named.
                            named = (ref[0] if ref else "") or (f"s{o}" if platform == "steam" else "")
                            tail = similar_row("", name, score, named, ref[1] if len(ref) > 1 else [])[3:]
                            refs.append(["u", target[0], name, score, *tail])
                    else:
                        refs.append([platform, o, name, score, *ref])
                similar_refs.setdefault(sheet["qid"], {})[platform] = refs
            sheets[gid] = sheet
        for gid, family in families({g: x for g, x in sheets.items() if g not in editions}, lambda g: pic(g, False)).items():
            sheets[gid]["family"] = family
        shards = sharded(base, "g", sheets)
        lists["shards"] = shards
        lists["games"] = len(sheets)
        lists["named"] = len(names)
        write(os.path.join(base, "lists.json"), lists)
        summary[platform] = {"games": len(sheets), "named": len(names), "popular": len(scores),
                             "upcoming": len(upcoming), "similar": len(similar), "browse": sum(len(p["games"]) for p in pages), "pages": len(pages),
                             "shards": shards, "generated": files["popular"].get("generated")}
    # [platform, named games, games with a critics' score, critics' average, renown's average, median year of the last years]
    write(os.path.join(out_dir, "x", "stats.json"), {"platforms": sorted(every_platform, key=lambda r: -r[1])})
    os.makedirs(os.path.join(out_dir, "x", "all"), exist_ok=True)
    write(os.path.join(out_dir, "x", "all", "stats.json"), overall(everyone))
    one = {q: unify(entries, similar_refs.get(q, {})) for q, entries in kept.items()}
    os.makedirs(os.path.join(out_dir, "x", "u"), exist_ok=True)
    write(os.path.join(out_dir, "x", "u", "meta.json"),
          {"shards": sharded(os.path.join(out_dir, "x"), "u", {q: dict(u, qid=q) for q, u in one.items()}), "games": len(one)})
    return summary


def write(path: str, body) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, separators=(",", ":"))
