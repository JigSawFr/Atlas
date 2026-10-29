"""What tools/build.py takes from IGDB (https://www.igdb.com), when the
repository has its keys (IGDB_CLIENT_ID and IGDB_CLIENT_SECRET, a Twitch
application's): without them, nothing, and every file is made as before.

- Each game's themes, keywords and player perspectives, more traits for
  similar.json (features.WEIGHT says how much each counts).
- Its popularity on IGDB (POPULARITY: its visits there and how many players
  want to play it, play it or have played it), a lift to popular.json's
  score as Steam's audience is.
- Its hype (how many follow it before its release), for upcoming.json.

The games are found by their IGDB slug in Wikidata (P5794), which links them
to their Switch title id: no table kept by hand. IGDB answers 4 requests a
second and 500 records a request at most (PAUSE, BATCH).
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN = "https://id.twitch.tv/oauth2/token"
API = "https://api.igdb.com/v4/"
PAUSE = 0.26                # IGDB allows 4 requests a second
BATCH = 500                 # records a request, at most
POPULARITY = (1, 2, 3, 4)   # visits, want to play, playing, played
KINDS = {"themes": "themes", "keywords": "keywords", "perspectives": "player_perspectives"}
MAX_TRAITS = 12             # of a kind, a game's first ones

SLUG_QUERY = """
SELECT ?tid ?slug WHERE { ?game wdt:P11072 ?tid; wdt:P5794 ?slug. }
"""


def slugs(rows, base_id):
    """{IGDB slug: [title id, ...]} from Wikidata's rows (a game may have several ids)."""
    out = {}
    for b in rows:
        tid = base_id(b["tid"]["value"])
        slug = b["slug"]["value"].strip().lower()
        if tid and slug and all(c.isalnum() or c == "-" for c in slug):
            have = out.setdefault(slug, [])
            if tid not in have:
                have.append(tid)
    return out


def quoted(values):
    return ",".join(json.dumps(v) for v in values)


def games_query(batch):
    fields = ",".join(["slug", "hypes"] + [f"{f}.name" for f in KINDS.values()])
    return f"fields {fields}; where slug = ({quoted(batch)}); limit {BATCH};"


def popularity_query(ids):
    types = ",".join(str(t) for t in POPULARITY)
    return f"fields game_id,popularity_type,value; where game_id = ({','.join(str(i) for i in ids)}) & popularity_type = ({types}); limit {BATCH};"


def read_games(records, by_slug):
    """From IGDB's games: {IGDB id: [title id, ...]}, {title id: {kind: [[id, name], ...]}}, {title id: hypes}."""
    ids, traits, hypes = {}, {}, {}
    for g in records:
        tids = by_slug.get(g.get("slug"))
        if not tids or not isinstance(g.get("id"), int):
            continue
        ids[g["id"]] = tids
        kinds = {}
        for kind, field in KINDS.items():
            values = []
            for v in g.get(field) or []:
                if isinstance(v, dict) and isinstance(v.get("id"), int) and len(values) < MAX_TRAITS:
                    values.append([str(v["id"]), str(v.get("name") or "")[:120]])
            if values:
                kinds[kind] = values
        for tid in tids:
            if kinds:
                traits[tid] = kinds
            if isinstance(g.get("hypes"), int) and g["hypes"] > 0:
                hypes[tid] = g["hypes"]
    return ids, traits, hypes


def read_popularity(records, ids):
    """{title id: 0..1}: for each kind of popularity, the game's rank among
    the games that have one (1 the most popular), the kinds averaged."""
    values = {}   # kind: {IGDB id: value}
    for r in records:
        kind, game, value = r.get("popularity_type"), r.get("game_id"), r.get("value")
        if kind in POPULARITY and game in ids and isinstance(value, (int, float)):
            values.setdefault(kind, {})[game] = max(value, values.get(kind, {}).get(game, 0))
    ranks = {}
    for of_kind in values.values():
        ordered = sorted(of_kind, key=lambda g: of_kind[g])
        for i, game in enumerate(ordered):
            ranks.setdefault(game, []).append((i + 1) / len(ordered))
    out = {}
    for game, r in ranks.items():
        for tid in ids[game]:
            out[tid] = max(out.get(tid, 0.0), sum(r) / len(r))
    return out


class Client:
    """IGDB's API with a token, a request at a time, paced."""

    def __init__(self, client_id, secret, agent):
        self.client_id, self.agent = client_id, agent
        body = urllib.parse.urlencode({"client_id": client_id, "client_secret": secret,
                                       "grant_type": "client_credentials"}).encode()
        self.token = self.send(TOKEN, body, {})["access_token"]

    def send(self, url, body, headers, tries=4):
        for attempt in range(tries):
            try:
                request = urllib.request.Request(url, data=body, method="POST",
                                                 headers={"User-Agent": self.agent, "Accept": "application/json", **headers})
                with urllib.request.urlopen(request, timeout=60) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if attempt == tries - 1 or e.code not in (429, 500, 502, 503, 504):
                    raise
            except (urllib.error.URLError, TimeoutError):
                if attempt == tries - 1:
                    raise
            time.sleep(2 ** attempt)
        return None

    def query(self, endpoint, text):
        time.sleep(PAUSE)
        return self.send(API + endpoint, text.encode(), {"Client-ID": self.client_id,
                                                         "Authorization": "Bearer " + self.token}) or []


def read(client, by_slug):
    """{"traits": …, "popularity": …, "hypes": …} for the games Wikidata links to IGDB."""
    records = []
    names = sorted(by_slug)
    for i in range(0, len(names), BATCH):
        records += client.query("games", games_query(names[i:i + BATCH]))
    ids, traits, hypes = read_games(records, by_slug)
    found = []
    games = sorted(ids)
    step = BATCH // len(POPULARITY)   # a record for each kind of each game
    for i in range(0, len(games), step):
        found += client.query("popularity_primitives", popularity_query(games[i:i + step]))
    popularity = read_popularity(found, ids)
    print(f"igdb: {len(ids)} games found of {len(by_slug)}, {len(traits)} with traits, "
          f"{len(popularity)} with a popularity, {len(hypes)} with a hype", file=sys.stderr)
    return {"traits": traits, "popularity": popularity, "hypes": hypes}
