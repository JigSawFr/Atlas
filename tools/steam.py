#!/usr/bin/env python3
"""Steam's files, by Steam app id, in steam/ (made every Monday, build.yml):

- steam/popular.json: how well known each game is, [score, trend, critics],
  as switch/popular.json, its Steam reviews weighing half;
- steam/games.json: the GAMES_KEPT best known games' name, release day,
  Steam reviews, Wikidata item and traits (its franchise as series,
  developers, publishers, and its players' tags by id, their names in the
  file's `tags`);
- steam/upcoming.json: the games still to come, [YYYYMMDD, name];
- steam/similar.json: the games most like each one, by their traits.

The games are those Wikidata gives a Steam app id (P1733, some 128,000
items), and Steam's most played of last week; Steam's store
(IStoreBrowseService/GetItems, no key, 200 apps a request) says which are
games and gives their name, reviews, release, franchise, developers,
publishers and tags. A game's renown on Wikipedia (sitelinks, critics, the
views of the best known) is weighed as the Switch's (tools/build.py).

Usage: tools/steam.py <out-dir> <previous-dir> <sources-dir>   (writes out-dir/steam/, from
the sources tools/collect.py keeps: wikidata, steam-store, wikipedia)
"""
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse

import build
import common
import features

STEAM = "steam"
QUERY = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
SELECT ?tid ?item ?links ?article ?score ?count WHERE {
  ?item wdt:P1733 ?tid; wikibase:sitelinks ?links.
  OPTIONAL { ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }
  OPTIONAL { ?item p:P444 ?statement. ?statement ps:P444 ?score. OPTIONAL { ?statement pq:P7887 ?count } }
}
"""
QLEVER = "https://qlever.dev/api/wikidata"
ITEMS = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1/?input_json={}"
TAGS = "https://api.steampowered.com/IStoreService/GetTagList/v1/?language=english"
MOST_PLAYED = "https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/"
BATCH = 200            # apps a GetItems request (300 is too long an address)
PAUSE = 0.3            # seconds between two
GAME = 0               # GetItems' type of a game (not a DLC, a tool, a video…)
TAGS_KEPT = 10         # a game's first tags, by weight
GAMES_KEPT = 40000     # the best known games in games.json (all 120,000 would be some 50 MB)
SIMILAR_GAMES = 30000  # the best known games compared for similar.json
MAX_SHARED = 300       # games a trait may be shared by, at most, to make two candidates
UPCOMING_DAYS = 365


def app_id(value):
    """A Steam app id, as a string of digits, or None."""
    v = (value or "").strip()
    return v if v.isdigit() and 0 < len(v) <= 10 and int(v) > 0 else None


def wikidata_rows():
    """QUERY's rows, from Wikidata's service, else QLever's copy."""
    try:
        return common.sparql(QUERY)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        print(f"steam: Wikidata's service: {e}; QLever asked", file=sys.stderr)
        body = common.fetch(QLEVER + "?" + urllib.parse.urlencode({"query": QUERY}), tries=3, timeout=300,
                            headers={"Accept": "application/sparql-results+json"})
        return body["results"]["bindings"]


def items_of(rows):
    """{app id: Wikidata item}, the first item of an app."""
    out = {}
    for b in rows:
        app = app_id(b["tid"]["value"])
        if app and app not in out:
            out[app] = b["item"]["value"].rsplit("/", 1)[-1]
    return out


def request(apps, country="US"):
    """GetItems' address for `apps` (at most BATCH)."""
    data = {"include_reviews": True, "include_release": True, "include_basic_info": True,
            "include_tag_count": TAGS_KEPT}
    body = {"ids": [{"appid": int(a)} for a in apps],
            "context": {"language": "english", "country_code": country}, "data_request": data}
    return ITEMS.format(urllib.parse.quote(json.dumps(body, separators=(",", ":"))))


def read_items(apps, fetch, country="US", sleep=time.sleep):
    """{app id: GetItems' item} of the apps it knows; a request that fails is left out."""
    apps = sorted(apps, key=int)
    out, failed = {}, 0
    for i in range(0, len(apps), BATCH):
        try:
            body = fetch(request(apps[i:i + BATCH], country))
        except (urllib.error.URLError, OSError, ValueError) as e:
            failed += 1
            print(f"steam: GetItems {i}: {e}", file=sys.stderr)
            continue
        for item in ((body or {}).get("response") or {}).get("store_items") or []:
            if item.get("success") == 1 and item.get("appid"):
                out[str(item["appid"])] = item
        sleep(PAUSE)
    print(f"steam: {len(out)} of {len(apps)} apps known to the store ({failed} requests failed)", file=sys.stderr)
    return out


def day_of(stamp):
    """YYYYMMDD of a Unix time, 0 when there is none."""
    try:
        return int(datetime.datetime.fromtimestamp(int(stamp), datetime.timezone.utc).strftime("%Y%m%d")) if stamp else 0
    except (TypeError, ValueError, OverflowError, OSError):
        return 0


def tag_names(body):
    return {t["tagid"]: t["name"] for t in ((body or {}).get("response") or {}).get("tags", [])
            if isinstance(t, dict) and "tagid" in t and t.get("name")}


def creators(people):
    """[[id, name]] of GetItems' developers or publishers, each once."""
    out = []
    for c in people or []:
        name = (c.get("name") or "").strip()
        if not name:
            continue
        key = f"clan:{c['creator_clan_account_id']}" if c.get("creator_clan_account_id") else f"name:{name.lower()}"
        if all(k != key for k, _ in out):
            out.append([key, name[:120]])
    return out[:features.MAX_TRAITS]


def entry(item, qid=None):
    """A game's steam/games.json entry, from its GetItems item."""
    basic = item.get("basic_info") or {}
    reviews = ((item.get("reviews") or {}).get("summary_filtered") or {})
    release = item.get("release") or {}
    out = {"name": (item.get("name") or "")[:200]}
    if qid:
        out["qid"] = qid
    day = day_of(release.get("steam_release_date") or release.get("original_steam_release_date"))
    if day:
        out["release"] = day
    if release.get("is_coming_soon"):
        out["coming_soon"] = True
    if reviews.get("review_count"):
        out["reviews"] = [int(reviews["review_count"]), int(reviews.get("percent_positive") or 0)]
    series = [[f"franchise:{f['name'].lower()}", f["name"][:120]] for f in basic.get("franchises") or [] if f.get("name")]
    traits = {"series": series, "developers": creators(basic.get("developers")),
              "publishers": creators(basic.get("publishers")),
              "tags": [t for t in (item.get("tagids") or [])[:TAGS_KEPT] if isinstance(t, int)]}
    out.update({k: v for k, v in traits.items() if v})
    return out


def popular(known, critics, read, games, played):
    """{app id: [score, trend, critics]}: a game's renown on Wikipedia (as
    the Switch's) and its Steam reviews, half each; Steam's most played of
    last week lifted by their rank."""
    wiki = build.popular(known, critics, read)
    most = max((g["reviews"][0] for g in games.values() if "reviews" in g), default=0)
    table = {}
    for app, g in games.items():
        w = wiki.get(app, [0, 0, 0])
        score = 0.5 * w[0] / 100 + 0.5 * common.scale(g["reviews"][0] if "reviews" in g else 0, most)
        if app in played:
            score = max(score, 0.75 * score + 0.25 * (1 - (played[app] - 1) / 100))
        if round(score * 100) > 0:
            table[app] = [round(score * 100), w[1], w[2]]
    return dict(sorted(table.items(), key=lambda kv: int(kv[0])))


def upcoming(games, today, days=UPCOMING_DAYS):
    """{app id: [YYYYMMDD, name]} of the games out after `today` and within `days`."""
    first = int(today.strftime("%Y%m%d"))
    last = int((today + datetime.timedelta(days=days)).strftime("%Y%m%d"))
    return {app: [g["release"], g["name"]] for app, g in sorted(games.items(), key=lambda kv: int(kv[0]))
            if g.get("name") and first < g.get("release", 0) <= last}


def most_played(body):
    """{app id: rank} of Steam's most played of last week."""
    return {str(r["appid"]): int(r["rank"]) for r in ((body or {}).get("response") or {}).get("ranks", [])
            if r.get("appid") and r.get("rank")}


def similar(games, popular_table, count=SIMILAR_GAMES):
    """The best known games' most similar, by their traits."""
    best = sorted(popular_table, key=lambda app: -popular_table[app][0])[:count]
    traits = {}
    for app in best:
        if app in games:
            g = games[app]
            traits[app] = {k: g[k] for k in ("series", "developers", "publishers") if k in g}
            if g.get("tags"):
                traits[app]["tags"] = [[f"tag:{t}", ""] for t in g["tags"]]
    return features.similar(traits, max_shared=MAX_SHARED)


def store_games(src, known, played):
    """{app id: games.json entry} of the apps Wikidata or the most played name
    that the store says are games (sources/steam-store/apps.json)."""
    rows = common.bindings(src("wikidata/steam.json").get("rows") or [])
    qids = items_of(rows)
    found = src("steam-store/apps.json").get("games") or {}
    return {app: entry(item, qids.get(app)) for app, item in found.items()
            if (app in known or app in played) and item.get("type") == GAME}


def views_known(src):
    """{app id: (sitelinks, English page)} of the games whose views count."""
    known = build.games(common.bindings(src("wikidata/steam.json").get("rows") or []), ident=app_id)
    played = src("steam-store/most-played.json").get("items") or {}
    return {app: known[app] for app in store_games(src, known, played) if app in known}


def consolidate(src, out_dir, previous_dir, today):
    """steam/'s weekly files from the sources collected (tools/collect.py)."""
    report = []
    rows = common.bindings(src("wikidata/steam.json").get("rows") or [])
    known = build.games(rows, ident=app_id)
    critics = build.reviews(rows, ident=app_id)
    print(f"steam: {len(known)} apps in Wikidata, {len(critics)} with critics' scores", file=sys.stderr)
    played = src("steam-store/most-played.json").get("items") or {}
    tags = {int(k): v for k, v in (src("steam-store/tags.json").get("items") or {}).items()}
    games = store_games(src, known, played)
    print(f"steam: {len(games)} games", file=sys.stderr)
    starts, end = build.months(today)
    read = build.views_from({app: known[app] for app in games if app in known},
                            src("wikipedia/monthly.json").get("pages") or {})
    table = popular(known, critics, read, games, played)

    def payload(source, entries, **extra):
        return {"schema": 1, "platform": STEAM, "generated": today.isoformat(), **extra,
                "source": source, "games": entries}

    kept = set(sorted(table, key=lambda app: -table[app][0])[:GAMES_KEPT]) | set(upcoming(games, today))
    used = {t for app in kept for t in games[app].get("tags", [])}
    common.publish(out_dir, f"{STEAM}/games.json", payload(
        "Steam's store (GetItems, GetTagList), Wikidata (P1733)",
        {app: games[app] for app in sorted(kept, key=int)},
        tags={str(t): tags[t] for t in sorted(used) if t in tags}), previous_dir, report)
    common.publish(out_dir, f"{STEAM}/popular.json", payload(
        "Wikidata (P1733, sitelinks, P444 with P7887), Wikimedia pageviews (en.wikipedia), Steam's reviews "
        "and most played", table, month=starts[-1].strftime("%Y-%m"), views=bool(read)), previous_dir, report)
    common.publish(out_dir, f"{STEAM}/upcoming.json", payload(
        "Steam's store (GetItems)", upcoming(games, today)), previous_dir, report)
    common.publish(out_dir, f"{STEAM}/similar.json", payload(
        "steam/games.json's traits", similar(games, table)), previous_dir, report)
    print(common.summary(report), file=sys.stderr)


def main():
    out_dir, previous_dir, sources_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    consolidate(common.reader(sources_dir, previous_dir), out_dir, previous_dir, datetime.date.today())


if __name__ == "__main__":
    main()
