"""What the website's explorer reads (site/README.md), made from a copy of
the data branch: the published files stay as they are under data/, and x/
holds them cut for a phone, one platform a folder:

- x/<platform>/lists.json: the lists the explorer opens on (the best known,
  the trending, the coming soon), each game with its name;
- x/<platform>/names.json: every game with a name, for the search;
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
import json
import os
from bisect import bisect_left

from common import SCHEMA
from taxonomy import KINDS, clean_title, company_key, company_merges, drop_note, split_company, find, fold, tidy_label, with_parents
import common
import extracts
import tech
import trends
import wdfacts

LIST = 200              # games a list holds
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


def browse(best: list, games: dict, names: dict, tags: dict, spelled: dict = None, pic=None) -> tuple:
    """The browse index of the named games in `best` ([(id, [score, trend, critics])],
    best first): (facets, pages), the facets as {facet: [[value, count]]} and
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
        row = [gid, names[gid], *(list(score) + [0, 0, 0])[:3], year]
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
        out["name"] = max(count, key=lambda n: (count[n], -min(i for i, p in enumerate(order) if entries[p][1].get("name") == n)))
    for p in order:
        if entries[p][1].get("wd"):
            out["wd"] = entries[p][1]["wd"]          # the game's, the same on every platform
            break
    traits = {}
    for p in order:
        gid, sheet = entries[p]
        entry = {"p": p, "id": gid}
        for k in ("name", "release", "upcoming", "popular", "reviews", "rating", "igdb_rating", "igdb_cover", "igdb_art", "views", "steam", "gamepass", "tech", "editions", "edition_of"):
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
    cleaned = {gid: clean_title(n) for gid, n in names.items()}
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
    for platform in plats:
        files = platform_files(data_dir, platform)
        scores = files["popular"].get("games") or {}
        games = files["games"].get("games") or {}
        tags = files["games"].get("tags") or {}
        names = names_of(files)
        upcoming = files["upcoming"].get("games") or {}
        similar = files["similar"].get("games") or {}
        editions = files["editions"].get("games") or {}
        base = os.path.join(out_dir, "x", platform)
        os.makedirs(base, exist_ok=True)

        stores = tech.read(data_dir, platform)       # what the stores' own sources say: runs on, languages, ages, pictures
        own_links = links.get(platform) or {}

        def pic(gid, long_ok=True):
            return picture(platform, gid, games.get(gid), own_links.get(gid), stores.get(gid), long_ok)

        def with_pic(row, gid, long_ok=True):
            ref = pic(gid, long_ok)
            return row + [ref] if ref else row

        best = sorted(scores.items(), key=lambda kv: (-kv[1][0], kv[0]))
        trending = sorted(((g, s) for g, s in scores.items() if s[1] > 0), key=lambda kv: (-kv[1][1], -kv[1][0], kv[0]))
        soon = sorted(upcoming.items(), key=lambda kv: (kv[1][0], kv[0]))
        lists = {
            "platform": platform,
            "generated": files["popular"].get("generated"),
            "popular": [with_pic([g, names.get(g, ""), *(list(s) + [0, 0, 0])[:3]], g) for g, s in best[:LIST]],
            "trending": [with_pic([g, names.get(g, ""), *(list(s) + [0, 0, 0])[:3]], g) for g, s in trending[:LIST]],
            "upcoming": [with_pic([g, names.get(g, ""), r[0], r[2] if len(r) > 2 else 0], g) for g, r in soon[:LIST]],
        }
        write(os.path.join(base, "names.json"),
              sorted(([g, n, (scores.get(g) or [0])[0]] for g, n in names.items()), key=lambda x: (-x[2], x[1])))

        facets, pages = browse(best, games, names, tags, spelled, pic)
        generated = files["popular"].get("generated")
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
                for k in ("release", "reviews", "rating", "gamepass", "qid", "igdb_rating", "igdb_cover", "igdb_art"):
                    if game.get(k):
                        sheet[k] = game[k]
                if isinstance(game.get("steam"), dict):
                    sheet["steam"] = game["steam"]
            if gid in curves.get(platform, ()):
                sheet["views"] = curves[platform][gid]
            if gid in stores:
                sheet["tech"] = stores[gid]
            if gid in upcoming:
                sheet["upcoming"] = upcoming[gid][0]
            if gid in similar:
                sheet["similar"] = [with_pic([o, names.get(o, ""), s], o, False) for o, s in similar[gid]]
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
            if sheet.get("qid") in multi:
                sheet["unified"] = True
                kept.setdefault(sheet["qid"], {})[platform] = (gid, sheet)
                refs = []
                for o, name, score, *ref in sheet.get("similar", ()):
                    target = (links.get(platform) or {}).get(o)
                    if target and target[0] in multi:
                        if target[0] != sheet["qid"]:
                            refs.append(["u", target[0], name, score, *(ref or [f"s{o}"] if platform == "steam" else ref)])
                    else:
                        refs.append([platform, o, name, score, *ref])
                similar_refs.setdefault(sheet["qid"], {})[platform] = refs
            sheets[gid] = sheet
        shards = sharded(base, "g", sheets)
        lists["shards"] = shards
        lists["games"] = len(sheets)
        lists["named"] = len(names)
        write(os.path.join(base, "lists.json"), lists)
        summary[platform] = {"games": len(sheets), "named": len(names), "popular": len(scores),
                             "upcoming": len(upcoming), "similar": len(similar), "browse": sum(len(p["games"]) for p in pages), "pages": len(pages),
                             "shards": shards, "generated": files["popular"].get("generated")}
    one = {q: unify(entries, similar_refs.get(q, {})) for q, entries in kept.items()}
    os.makedirs(os.path.join(out_dir, "x", "u"), exist_ok=True)
    write(os.path.join(out_dir, "x", "u", "meta.json"),
          {"shards": sharded(os.path.join(out_dir, "x"), "u", {q: dict(u, qid=q) for q, u in one.items()}), "games": len(one)})
    return summary


def write(path: str, body) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, separators=(",", ":"))
