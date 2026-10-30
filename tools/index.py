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

Usage: tools/index.py <data-dir>   (writes <data-dir>/index.json)
"""
import hashlib
import json
import os
import sys


# A source named in a file's `source`: its terms, and whom to credit.
LICENCES = [
    ("Wikidata", "CC0-1.0", "Wikidata"),
    ("Wikimedia", "CC0-1.0", "Wikimedia pageviews"),
    ("titledb", "as published by blawar/titledb", "blawar/titledb"),
    ("eShop", "Nintendo's terms of use", "Nintendo"),
    ("SteamSpy", "SteamSpy's terms of use", "SteamSpy"),
    ("Steam", "Steam Web API terms of use", "Data from Valve, not endorsed by it"),
    ("GOG", "GOG's terms of use", "GOG"),
    ("Microsoft", "Microsoft's terms of use", "Microsoft"),
    ("Game Pass", "Microsoft's terms of use", "Microsoft"),
    ("IGDB", "IGDB's API terms", "Data from IGDB.com"),
]
OWN = ("CC0-1.0", "Atlas (github.com/JigSawFr/Atlas)")   # what Atlas makes of nothing but its own files


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
    return {"schema": 1, "files": dict(sorted(files.items()))}


def main():
    directory = sys.argv[1]
    with open(os.path.join(directory, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index(directory), f, separators=(",", ":"))
        f.write("\n")


if __name__ == "__main__":
    main()
