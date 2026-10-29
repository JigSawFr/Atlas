#!/usr/bin/env python3
"""index.json of the data branch: each data file's path, the day it was
made (its `generated`), its size and a hash of its content, so a reader
(PlayShelf) asks for this small file every day and fetches only the files
whose hash changed.

{"schema": 1,
 "files": {"popular.json": {"generated": "YYYY-MM-DD", "bytes": 70123, "sha256": "<16 hex>"}, ...}}

Usage: tools/index.py <data-dir>   (writes <data-dir>/index.json)
"""
import hashlib
import json
import os
import sys


def entry(path):
    with open(path, "rb") as f:
        body = f.read()
    try:
        generated = json.loads(body).get("generated", "")
    except (ValueError, AttributeError):
        generated = ""
    return {"generated": generated if isinstance(generated, str) else "", "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest()[:16]}


def index(directory):
    files = {}
    for root, dirs, names in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(names):
            if name.endswith(".json") and name != "index.json":
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
