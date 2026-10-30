#!/usr/bin/env python3
"""The data branch as it was before each platform had its folder: the
Switch's files at its root (popular.json, games.json, similar.json,
upcoming.json, editions.json, prices/<country>.json) moved into switch/,
so a run reads them there as the last run's (the guard's counts, the
lowest prices, the trends' scores). A file already in switch/ wins, and
the root's copy goes. Run on a branch already moved, it does nothing.

Usage: tools/migrate.py <data-dir>   (the data branch's worktree, before a run)
"""
import os
import shutil
import sys

SWITCH = "switch"
ROOT_FILES = ("popular.json", "games.json", "similar.json", "upcoming.json", "editions.json")


def legacy(directory):
    """The Switch's files still at the root, as paths relative to it."""
    found = [n for n in ROOT_FILES if os.path.isfile(os.path.join(directory, n))]
    prices = os.path.join(directory, "prices")
    if os.path.isdir(prices):
        found += sorted(f"prices/{n}" for n in os.listdir(prices) if n.endswith(".json"))
    return found


def migrate(directory):
    """Moves the root's Switch files into switch/; the moved paths."""
    moved = []
    for name in legacy(directory):
        old = os.path.join(directory, name)
        new = os.path.join(directory, SWITCH, name)
        if os.path.exists(new):
            os.remove(old)
        else:
            os.makedirs(os.path.dirname(new), exist_ok=True)
            shutil.move(old, new)
            moved.append(name)
    prices = os.path.join(directory, "prices")
    if os.path.isdir(prices) and not os.listdir(prices):
        os.rmdir(prices)
    return moved


def main():
    moved = migrate(sys.argv[1])
    print(f"migrate: {len(moved)} files moved into {SWITCH}/" if moved else "migrate: nothing to move", file=sys.stderr)


if __name__ == "__main__":
    main()
