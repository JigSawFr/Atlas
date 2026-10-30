#!/usr/bin/env python3
"""What a run changed, once its files are in the data branch's worktree
(before they are committed: the branch's last commit is the last run's):

- changes.json, by platform: the new games, the games out today, and the
  trends that moved the most;
- platforms/<id>/games.lite.json for a games.json larger than LITE_FROM:
  each game's name, Wikidata item, release and reviews (or rating) alone.

Usage: tools/changes.py <data-dir>   (a git worktree of the data branch, the run's files in it)
"""
import datetime
import json
import os
import subprocess
import sys

import common

KEEP = 200            # of each kind of change, a platform's first ones
TREND_MOVE = 100      # points a trend moved by, at least, to be said
LITE_FROM = 1_000_000  # bytes of a games.json above which a light one is made too


def ours(body):
    """body when it is a file of our schema, else {} (one of another schema reads as none)."""
    return body if isinstance(body, dict) and body.get("schema") == common.SCHEMA else {}


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return ours(json.load(f))
    except (OSError, ValueError):
        return {}


def other_schema(path):
    """True when `path` holds a file of another schema: never written over."""
    try:
        with open(path, encoding="utf-8") as f:
            body = json.load(f)
    except (OSError, ValueError):
        return False
    return isinstance(body, dict) and "schema" in body and body["schema"] != common.SCHEMA


def last(directory, path):
    """The file as the branch's last commit has it (the last run's), {} when it had none."""
    got = subprocess.run(["git", "-C", directory, "show", f"HEAD:{path}"], capture_output=True)
    if got.returncode:
        return {}
    try:
        return ours(json.loads(got.stdout))
    except ValueError:
        return {}


def platform_ids(directory):
    base = os.path.join(directory, "platforms")
    return sorted(os.listdir(base)) if os.path.isdir(base) else []


def changes(directory, today, previous=None):
    """{platform: {kind: [...]}}."""
    asked = previous or (lambda path: last(directory, path))
    previous = lambda path: ours(asked(path))   # noqa: E731
    day = int(today.strftime("%Y%m%d"))
    out = {}
    for pid in platform_ids(directory):
        base = f"platforms/{pid}"
        mine = {}
        now = read(os.path.join(directory, base, "games.json")).get("games") or {}
        before = previous(f"{base}/games.json").get("games") or {}
        if before:
            mine["new"] = sorted(g for g in now if g not in before)[:KEEP]
        coming = previous(f"{base}/upcoming.json").get("games") or {}
        mine["out_today"] = sorted(g for g, row in coming.items() if row and row[0] == day)[:KEEP]
        popular = read(os.path.join(directory, base, "popular.json")).get("games") or {}
        was = previous(f"{base}/popular.json").get("games") or {}
        moved = [(g, was[g][1], row[1]) for g, row in popular.items() if g in was and abs(row[1] - was[g][1]) >= TREND_MOVE]
        mine["trends"] = [[g, a, b] for g, a, b in sorted(moved, key=lambda m: -abs(m[2] - m[1]))[:KEEP]]
        out[pid] = {k: v for k, v in mine.items() if v}
    return out


def lite(directory):
    """games.lite.json beside each games.json larger than LITE_FROM."""
    written = []
    for pid in platform_ids(directory):
        path = os.path.join(directory, "platforms", pid, "games.json")
        if not os.path.exists(path) or os.path.getsize(path) <= LITE_FROM:
            continue
        body = read(path)
        target = os.path.join(directory, "platforms", pid, "games.lite.json")
        if not body or other_schema(target):
            continue
        light = {}
        for g, e in (body.get("games") or {}).items():
            if isinstance(e, dict):
                light[g] = {k: e[k] for k in ("name", "qid", "release", "reviews", "rating") if k in e}
        common._dump(target, {
            "schema": common.SCHEMA, "platform": pid, "generated": body.get("generated"),
            "source": f"platforms/{pid}/games.json (name, Wikidata item, release, reviews or rating)", "games": light})
        written.append(pid)
    return written


def main():
    directory = sys.argv[1]
    today = datetime.date.today()
    found = changes(directory, today)
    common._dump(os.path.join(directory, "changes.json"), {
        "schema": common.SCHEMA, "generated": today.isoformat(), "source": "Atlas (the run's files against the last run's)",
        "platforms": found})
    print(f"changes: {sum(len(v) for v in found.values())} kinds of change; "
          f"lite: {', '.join(lite(directory)) or 'none'}", file=sys.stderr)


if __name__ == "__main__":
    main()
