#!/usr/bin/env python3
"""The data branch as it was before, moved to today's folders, so a run
reads the last run's files where it writes its own (the guard's counts, the
lowest prices and their `since`, the trends' scores):

- before each platform had its folder, the Switch's files were at its root
  (popular.json, games.json, similar.json, upcoming.json, editions.json,
  prices/<country>.json): moved into platforms/switch/;
- before platforms/, each platform's folder was at the root (switch/,
  steam/, gog/, xbox/): moved into platforms/<id>/; retro/ (all the old
  machines in one folder, now one folder each) goes.

A file already where it goes wins, and the old copy goes. Run on a branch
already moved, it does nothing.

Usage: tools/migrate.py <data-dir>   (the data branch's worktree, before a run)
"""
import os
import shutil
import sys

SWITCH = "switch"
ROOT_FILES = ("popular.json", "games.json", "similar.json", "upcoming.json", "editions.json")
FOLDERS = ("switch", "steam", "gog", "xbox")
GONE = ("retro",)
TARGET = "platforms"


def legacy(directory):
    """The Switch's files still at the root, as paths relative to it."""
    found = [n for n in ROOT_FILES if os.path.isfile(os.path.join(directory, n))]
    prices = os.path.join(directory, "prices")
    if os.path.isdir(prices):
        found += sorted(f"prices/{n}" for n in os.listdir(prices) if n.endswith(".json"))
    return found


def move(old, new, moved, name):
    if os.path.exists(new):
        os.remove(old)
    else:
        os.makedirs(os.path.dirname(new), exist_ok=True)
        shutil.move(old, new)
        moved.append(name)


def prune(folder):
    """Empty folders under `folder` removed, `folder` too when it is left empty."""
    for root, dirs, files in os.walk(folder, topdown=False):
        if not os.listdir(root):
            os.rmdir(root)


def migrate(directory):
    """Moves the old places' files to today's; the moved paths."""
    moved = []
    for name in legacy(directory):
        move(os.path.join(directory, name), os.path.join(directory, TARGET, SWITCH, name), moved, name)
    for folder in FOLDERS:
        base = os.path.join(directory, folder)
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for f in sorted(files):
                rel = os.path.relpath(os.path.join(root, f), directory)
                move(os.path.join(directory, rel), os.path.join(directory, TARGET, rel), moved, rel)
        prune(base)
    for folder in GONE:
        if os.path.isdir(os.path.join(directory, folder)):
            shutil.rmtree(os.path.join(directory, folder))
    if os.path.isdir(os.path.join(directory, "prices")):
        prune(os.path.join(directory, "prices"))
    return moved


def main():
    moved = migrate(sys.argv[1])
    print(f"migrate: {len(moved)} files moved into {TARGET}/" if moved else "migrate: nothing to move", file=sys.stderr)


if __name__ == "__main__":
    main()
