#!/usr/bin/env python3
"""index.json of the data branch: each data file's path, the day it was
made (its `generated`), its size and a hash of its content, so a reader
(PlayShelf) asks for this small file every day and fetches only the files
whose hash changed.

{"schema": 1,
 "files": {"platforms/switch/popular.json": {"generated": "YYYY-MM-DD", "bytes": 70123, "sha256": "<16 hex>",
   "source": "…", "license": "…", "attribution": "…"}, ...}}

Each file's `source` is its own (what it was made from), `license` the
terms its sources put it under, `attribution` whom to credit: a source's
file has its source's; a file Atlas made has those of every source it was
made from (LICENCES, by the names its `source` gives).

Before it writes index.json, the one there (the last run's) tells each
file's size last time: a file that came out more than twice as large, or
less than half as large (SIZE_GROW, SIZE_SHRINK), is said in the run's
alert (ALERTS, tools/alert.sh), beside the games' guard (common.publish),
which a file that keeps its games but loses or doubles its fields does not
see. It is still published: a size is a sign, not a proof. Small files
(under SIZE_FLOOR) and the run's own (changes.json, report.json) are not
weighed; a source's parts (sources/<name>/<file>/<n>.json) are weighed
together.

Usage: tools/index.py <data-dir>   (writes <data-dir>/index.json)
"""
import hashlib
import json
import os
import re
import sys

import common


# A source named in a file's `source`: its terms, and whom to credit.
LICENCES = [
    ("Wikidata", "CC0-1.0", "Wikidata"),
    ("Wikimedia", "CC0-1.0", "Wikimedia pageviews"),
    ("titledb", "as published by blawar/titledb", "blawar/titledb"),
    ("SteamSpy", "SteamSpy's terms of use", "SteamSpy"),
    ("Steam", "Steam Web API terms of use", "Data from Valve, not endorsed by it"),
    ("GOG", "GOG's terms of use", "GOG"),
    ("Microsoft", "Microsoft's terms of use", "Microsoft"),
    ("Game Pass", "Microsoft's terms of use", "Microsoft"),
    ("IGDB", "IGDB's API terms", "Data from IGDB.com"),
    ("Nlib", "as published by Nlib API (no terms stated)", "Nlib API"),
]
OWN = ("CC0-1.0", "Atlas (github.com/JigSawFr/Atlas)")   # what Atlas makes of nothing but its own files
SIZE_GROW = 2.0       # a file more than this many times last run's size is said
SIZE_SHRINK = 0.5     # and one under this share of it
SIZE_FLOOR = 50_000   # bytes, last run's or this run's, under which a file is not weighed
UNWEIGHED = re.compile(r"^(changes|report)\.json$")
PART = re.compile(r"^(sources/.+)/\d+\.json$")


def terms(body):
    """(license, attribution) of a file: its own when it says it (a source's
    file), else those of the sources its `source` names."""
    source = body.get("source") if isinstance(body.get("source"), str) else ""
    if isinstance(body.get("license"), str):
        found = [(body["license"], next((a for k, _, a in LICENCES if k in source), source))]
    else:
        found = [(lic, who) for key, lic, who in LICENCES if key in source] or [OWN]
    licences, credits = [], []
    for lic, who in found:
        if lic not in licences:
            licences.append(lic)
        if who not in credits:
            credits.append(who)
    return "; ".join(licences), "; ".join(credits)


def entry(path):
    with open(path, "rb") as f:
        body = f.read()
    try:
        parsed = json.loads(body)
        parsed = parsed if isinstance(parsed, dict) else {}
    except ValueError:
        parsed = {}
    generated = parsed.get("generated", "")
    licence, attribution = terms(parsed)
    out = {"generated": generated if isinstance(generated, str) else "", "bytes": len(body),
           "sha256": hashlib.sha256(body).hexdigest()[:16]}
    if isinstance(parsed.get("source"), str):
        out["source"] = parsed["source"]
    out.update({"license": licence, "attribution": attribution})
    return out


def index(directory):
    files = {}
    for root, dirs, names in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(names):
            if name.endswith(".json") and name != "index.json" and not root.startswith(os.path.join(directory, "schemas")):
                path = os.path.join(root, name)
                files[os.path.relpath(path, directory).replace(os.sep, "/")] = entry(path)
    # No day of its own: it changes only when a file does.
    return {"schema": common.SCHEMA, "files": dict(sorted(files.items()))}


def weights(files):
    """{file: bytes}, a source's parts summed under its file's name."""
    out = {}
    for name, f in (files or {}).items():
        if UNWEIGHED.search(name) or not isinstance(f, dict) or not isinstance(f.get("bytes"), int):
            continue
        key = PART.sub(r"\1.json", name)
        out[key] = out.get(key, 0) + f["bytes"]
    return out


def sizes(before, now):
    """The alert's lines: each file weighed in both runs whose size more
    than doubled or fell under half (`before`, `now`: index.json's files)."""
    lines = []
    last, this = weights(before), weights(now)
    for name in sorted(set(last) & set(this)):
        a, b = last[name], this[name]
        if max(a, b) < SIZE_FLOOR or not a:
            continue
        if b > a * SIZE_GROW or b < a * SIZE_SHRINK:
            lines.append(f"`{name}` weighs {b / 1e6:.2f} MB against {a / 1e6:.2f} MB last time "
                         f"({(b - a) * 100 / a:+.0f} %): published, worth a look.")
    return lines


def previous(directory):
    """The last run's index.json files ({} without one, or of another schema)."""
    try:
        with open(os.path.join(directory, "index.json"), encoding="utf-8") as f:
            body = json.load(f)
    except (OSError, ValueError):
        return {}
    return (body.get("files") or {}) if isinstance(body, dict) and body.get("schema") == common.SCHEMA else {}


def main():
    directory = sys.argv[1]
    before = previous(directory)
    body = index(directory)
    lines = sizes(before, body["files"])
    for line in lines:
        print(f"::warning::{line}", file=sys.stderr)
    if lines and os.environ.get("ALERTS"):
        with open(os.environ["ALERTS"], "a", encoding="utf-8") as f:
            f.write("".join(line + "\n" for line in lines))
    with open(os.path.join(directory, "index.json"), "w", encoding="utf-8") as f:
        json.dump(body, f, separators=(",", ":"))
        f.write("\n")


if __name__ == "__main__":
    main()
