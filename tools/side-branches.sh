#!/bin/bash
# The files of the branches beside `data` (tools/branches.conf) put in <dir>,
# at their own paths: what each source answered (`sources`, several hundred
# MB, since 2026-11-10) and the PC stores' files and links.json
# (`data-stores`, since 2026-11-13), kept apart because jsDelivr serves no
# branch over 50 MB: the `data` branch, without them, is served whole. The
# tools read <dir> as before. A branch not there yet (a new repository, or
# the run before the first one that publishes it): nothing done for it, <dir>
# is left as it is.
#
# Usage: tools/side-branches.sh <dir>   (from the repository's root)
set -eu
dir=$1
while read -r branch paths; do
  case $branch in ''|'#'*) continue;; esac
  if git ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
    git fetch --quiet --depth 1 origin "$branch:refs/remotes/origin/$branch"
    git archive "origin/$branch" | tar -x -C "$dir"
  fi
done < tools/branches.conf
