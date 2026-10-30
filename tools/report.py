#!/usr/bin/env python3
"""report.json: how the data is, run after run, for whoever reads it (and
the website's health table): for each source, its files, records, size and
the day it last answered; for each platform, its games, how many of them
links.json ties to another platform, how many have reviews or a rating,
and the day its files were made; and how long each step of the run took.
Its schema is its own (common.REPORT_SCHEMA): 2 since `priced` and
`countries` went (2026-10-30).

{"schema": 2, "generated": "YYYY-MM-DD", "run": "build"|"daily",
 "sources": {"steam-store": {"files": 16, "records": 131000, "bytes": 41000000, "generated": "YYYY-MM-DD"}, …},
 "platforms": {"switch": {"games": 2600, "names": 37000, "popular": 2500, "linked": 0.71,
                          "reviewed": 0.42, "generated": "YYYY-MM-DD"}, …},
 "steps": {"collect steam-store weekly": 512.3, "switch": 41.0, …}}

Usage: tools/report.py <data-dir> <run> [runtimes-dir…]   (writes <data-dir>/report.json;
runtimes-dir: where the run's steps left their .runtimes/)
"""
import datetime
import json
import os
import sys

import common


def read(path, schema=common.SCHEMA):
    """A file's body, {} when there is none, or it is of another schema
    (counted as none: its fields may mean something else)."""
    try:
        with open(path, encoding="utf-8") as f:
            body = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(body, dict) or (schema is not None and body.get("schema") != schema):
        return {}
    return body


def sources(directory):
    out = {}
    base = os.path.join(directory, common.SOURCES)
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        entry = {"files": 0, "records": 0, "bytes": 0, "generated": ""}
        for root, _, files in os.walk(os.path.join(base, name)):
            for f in files:
                if not f.endswith(".json"):
                    continue
                path = os.path.join(root, f)
                body = read(path, common.SOURCE_SCHEMA)
                key = common.records_key(body)
                entry["files"] += 1
                entry["bytes"] += os.path.getsize(path)
                entry["records"] += len(body[key]) if key and hasattr(body[key], "__len__") else 0
                entry["generated"] = max(entry["generated"], body.get("generated") or "")
        out[name] = entry
    return out


def platforms(directory):
    links = (read(os.path.join(directory, "links.json")).get("games") or {})
    linked_ids = {}
    for ids in links.values():
        if len(ids) > 1:
            for platform, values in ids.items():
                linked_ids.setdefault(platform, set()).update(str(v) for v in values)
    out = {}
    base = os.path.join(directory, "platforms")
    for pid in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        folder = os.path.join(base, pid)
        games = read(os.path.join(folder, "games.json")).get("games") or {}
        popular = read(os.path.join(folder, "popular.json"))
        names = read(os.path.join(folder, "names.json")).get("games") or {}
        ids = set(games) | set(popular.get("games") or {})
        share = lambda part: round(len(part & ids) / len(ids), 3) if ids else 0   # noqa: E731
        reviewed = {g for g, e in games.items() if isinstance(e, dict)
                    and any(k in e for k in ("reviews", "rating", "steam", "igdb_rating"))}
        # A platform's games by Wikidata item (the old machines'): linked when links.json has the item.
        linked = linked_ids.get(pid, set()) | {g for g in ids if g.startswith("Q") and g in links}
        out[pid] = {"games": len(games), "names": len(names) or sum(1 for e in games.values()
                                                                    if isinstance(e, dict) and e.get("name")),
                    "popular": len(popular.get("games") or {}), "linked": share(linked),
                    "reviewed": share(reviewed),
                    "generated": max(popular.get("generated") or "", read(os.path.join(folder, "games.json")).get(
                        "generated") or "")}
    return out


def steps(directories):
    out = {}
    for directory in directories:
        folder = os.path.join(directory, ".runtimes")
        for f in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            body = read(os.path.join(folder, f), schema=None)
            if isinstance(body.get("seconds"), (int, float)):
                out[f[:-5]] = round(body["seconds"], 1)
    return out


def report(directory, run, runtimes):
    return {"schema": common.REPORT_SCHEMA, "generated": datetime.date.today().isoformat(), "run": run,
            "source": "Atlas (its own files: sources/, platforms/, links.json)",
            "sources": sources(directory), "platforms": platforms(directory), "steps": steps(runtimes)}


def main():
    directory, run = sys.argv[1], sys.argv[2]
    body = report(directory, run, sys.argv[3:])
    with open(os.path.join(directory, "report.json"), "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"report: {len(body['sources'])} sources, {len(body['platforms'])} platforms", file=sys.stderr)


if __name__ == "__main__":
    main()
