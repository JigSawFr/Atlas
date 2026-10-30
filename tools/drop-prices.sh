#!/bin/bash
# One time: Atlas no longer reads prices (2026-10-30). The next run, daily or
# build, removes from the data branch's worktree what only the prices made:
# each platform's prices/, history/, and the sources asked for them alone
# (the eShop's, Steam's and the Microsoft Store's prices, GOG's catalog of
# every country but the US). tools/publish.sh then commits their removal and
# asks jsDelivr again for each path gone; tools/schemas.py writes schemas/
# again without theirs. Nothing there: nothing done.
#
# Goes, with its step in daily.yml and build.yml, once a run has published
# the branch without them (plans/atlas/suivi.md).
#
# Usage: tools/drop-prices.sh <data-dir>
set -eu
dir=$1
rm -rf "$dir"/history "$dir"/platforms/*/prices "$dir"/sources/eshop \
  "$dir"/sources/steam-store/prices "$dir"/sources/msstore/prices
if [ -d "$dir/sources/gog/catalog" ]; then
  find "$dir/sources/gog/catalog" -mindepth 1 -maxdepth 1 ! -name US.json ! -name US -exec rm -rf {} +
fi
