"""What the website's explorer reads (site/README.md), made from a copy of
the data branch: the published files stay as they are under data/, and x/
holds them cut for a phone, one platform a folder:

- x/<platform>/lists.json: the lists the explorer opens on (the best known,
  the trending, the coming soon), each game with its name, and the countries
  with prices;
- x/<platform>/deals/<country>.json: that country's sales, the best known
  first, the games under a floor price left out;
- x/<platform>/names.json: every game with a name, for the search;
- x/<platform>/g/<shard>.json: each game's sheet (what every file says of
  it, its prices in every country, its ids on the other platforms), the
  games spread over shards by shard() so a sheet costs one small file.

Python's standard library only. Usage: see tools/build_site.py.
"""
import json
import os

from common import SCHEMA

LIST = 200              # games a list holds
SHARD_BYTES = 160_000   # about what a shard of sheets weighs, at most on average
# A sale's regular price below this (in the country's currency) is left out
# of the deals: thousands of small games are always at 90 % off.
FLOOR = {"USD": 5, "CAD": 7, "MXN": 100, "BRL": 25, "GBP": 4, "EUR": 5, "AUD": 8, "JPY": 700}
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


def read(path):
    """A data file, None when there is none (or it is of another schema)."""
    try:
        with open(path, encoding="utf-8") as f:
            body = json.load(f)
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) and body.get("schema") == SCHEMA else None


def platforms(data_dir: str) -> list:
    """The platforms the data has: each folder with a popular.json (of our schema)."""
    out = []
    for name in sorted(os.listdir(data_dir)):
        if read(os.path.join(data_dir, name, "popular.json")) is not None:
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


def trait_names(game: dict, tags: dict) -> dict:
    """A game's traits as {kind: [names]}: Wikidata's or Steam's."""
    out = {}
    for kind in ("series", "developers", "publishers", "genres", "modes", "themes", "keywords", "perspectives"):
        names = [t[1] for t in game.get(kind) or [] if isinstance(t, list) and len(t) > 1 and t[1]]
        if names:
            out[kind] = names
    if game.get("tags"):
        out["tags"] = [tags.get(str(t), "") for t in game["tags"] if tags.get(str(t))]
    return out


def platform_files(data_dir: str, platform: str) -> dict:
    base = os.path.join(data_dir, platform)
    files = {k: read(os.path.join(base, f"{k}.json")) or {} for k in ("popular", "games", "upcoming", "similar", "editions")}
    prices = {}
    pdir = os.path.join(base, "prices")
    if os.path.isdir(pdir):
        for f in sorted(os.listdir(pdir)):
            body = read(os.path.join(pdir, f))
            if f.endswith(".json") and body and body.get("games"):
                prices[f[:-5]] = body
    files["prices"] = prices
    return files


def names_of(files: dict) -> dict:
    names = {}
    for gid, row in (files["upcoming"].get("games") or {}).items():
        if len(row) > 1 and row[1]:
            names[gid] = row[1]
    for gid, game in (files["games"].get("games") or {}).items():
        if isinstance(game, dict) and game.get("name"):
            names[gid] = game["name"]
    return names


def deals(prices: dict, scores: dict, names: dict) -> dict:
    """A country's sales above the floor, the best known first, then the deepest."""
    currency = prices.get("currency") or ""
    floor = FLOOR.get(currency, 0)
    rows = []
    for gid, r in prices["games"].items():
        regular, sale = r[0], r[1]
        if not sale or regular < floor or sale >= regular:
            continue
        cut = round((regular - sale) * 100 / regular)
        rows.append([gid, names.get(gid, ""), regular, sale, r[2], r[3] if len(r) > 3 else 0,
                     r[4] if len(r) > 4 else 0, r[5] if len(r) > 5 else 0, cut, (scores.get(gid) or [0])[0]])
    rows.sort(key=lambda x: (-x[9], -x[8], x[0]))
    return {"country": prices.get("country"), "currency": currency, "generated": prices.get("generated"),
            "since": prices.get("since"), "floor": floor, "count": len(rows), "games": rows[:LIST]}


def build(data_dir: str, out_dir: str) -> dict:
    """Writes x/ into out_dir; returns {platform: summary} for the pages."""
    links = reverse_links(read(os.path.join(data_dir, "links.json")))
    summary = {}
    for platform in platforms(data_dir):
        files = platform_files(data_dir, platform)
        scores = files["popular"].get("games") or {}
        games = files["games"].get("games") or {}
        tags = files["games"].get("tags") or {}
        names = names_of(files)
        upcoming = files["upcoming"].get("games") or {}
        similar = files["similar"].get("games") or {}
        editions = files["editions"].get("games") or {}
        base = os.path.join(out_dir, "x", platform)
        os.makedirs(os.path.join(base, "deals"), exist_ok=True)
        os.makedirs(os.path.join(base, "g"), exist_ok=True)

        best = sorted(scores.items(), key=lambda kv: (-kv[1][0], kv[0]))
        trending = sorted(((g, s) for g, s in scores.items() if s[1] > 0), key=lambda kv: (-kv[1][1], -kv[1][0], kv[0]))
        soon = sorted(upcoming.items(), key=lambda kv: (kv[1][0], kv[0]))
        countries = {}
        for c, body in files["prices"].items():
            d = deals(body, scores, names)
            write(os.path.join(base, "deals", f"{c}.json"), d)
            countries[c] = {"currency": d["currency"], "games": len(body["games"]), "deals": d["count"],
                            "generated": d["generated"]}
        lists = {
            "platform": platform,
            "generated": files["popular"].get("generated"),
            "popular": [[g, names.get(g, ""), *s] for g, s in best[:LIST]],
            "trending": [[g, names.get(g, ""), *s] for g, s in trending[:LIST]],
            "upcoming": [[g, r[1] if len(r) > 1 else "", r[0], r[2] if len(r) > 2 else 0] for g, r in soon[:LIST]],
            "countries": countries,
        }
        write(os.path.join(base, "names.json"),
              sorted(([g, n, (scores.get(g) or [0])[0]] for g, n in names.items()), key=lambda x: (-x[2], x[1])))

        sheets = {}
        every = set(scores) | set(games) | set(upcoming) | set(similar)
        for body in files["prices"].values():
            every |= set(body["games"])
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
                traits = trait_names(game, tags)
                if traits:
                    sheet["traits"] = traits
                for k in ("release", "reviews", "qid", "igdb_rating"):
                    if game.get(k):
                        sheet[k] = game[k]
                if isinstance(game.get("steam"), dict):
                    sheet["steam"] = game["steam"]
            if gid in upcoming:
                sheet["upcoming"] = upcoming[gid][0]
            if gid in similar:
                sheet["similar"] = [[o, names.get(o, ""), s] for o, s in similar[gid]]
            if gid in editions:
                sheet["edition_of"] = [editions[gid], names.get(editions[gid], "")]
            if gid in of_edition:
                sheet["editions"] = [[e, names.get(e, "")] for e in sorted(of_edition[gid])]
            prices = {c: [*body["games"][gid], body.get("currency") or ""] for c, body in files["prices"].items()
                      if gid in body["games"]}
            if prices:
                sheet["prices"] = prices
            link = (links.get(platform) or {}).get(gid)
            if link:
                sheet["qid"] = sheet.get("qid") or link[0]
                sheet["links"] = {p: ids for p, ids in link[1].items() if p != platform or ids != [gid]}
            sheets[gid] = sheet
        size = sum(len(json.dumps(s, separators=(",", ":"))) + len(g) + 4 for g, s in sheets.items())
        shards = 1
        while size / shards > SHARD_BYTES:
            shards *= 2
        parts = [{} for _ in range(shards)]
        for gid, sheet in sheets.items():
            parts[shard(gid, shards)][gid] = sheet
        for i, part in enumerate(parts):
            write(os.path.join(base, "g", f"{i}.json"), part)
        lists["shards"] = shards
        lists["games"] = len(sheets)
        lists["named"] = len(names)
        write(os.path.join(base, "lists.json"), lists)
        summary[platform] = {"games": len(sheets), "named": len(names), "popular": len(scores),
                             "upcoming": len(upcoming), "similar": len(similar), "countries": sorted(countries),
                             "shards": shards, "generated": files["popular"].get("generated")}
    return summary


def write(path: str, body) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, separators=(",", ":"))
