#!/bin/bash
# The `sources` branch's files put in <dir>/sources: what each source answered
# (tools/collect.py), kept on a branch of its own since 2026-11-10 because it
# weighs several hundred MB and jsDelivr serves no branch over 50 MB: the
# `data` branch, without it, is served whole. The tools read <dir>/sources as
# before. No `sources` branch yet (a new repository, or the run before the
# first one that publishes it): nothing done, <dir> is left as it is.
#
# Usage: tools/sources-branch.sh <dir>   (from the repository's root)
set -eu
dir=$1
if git ls-remote --exit-code --heads origin sources >/dev/null 2>&1; then
  git fetch --quiet --depth 1 origin sources:refs/remotes/origin/sources
  git archive origin/sources sources | tar -x -C "$dir"
fi
