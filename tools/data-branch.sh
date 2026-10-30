#!/bin/bash
# The data branch's last files in ./data-branch (a worktree, on branch `data`,
# a new orphan one when the repository has none yet): each job reads the last
# run's files there, and the publishing job commits into it.
#
# Usage: tools/data-branch.sh   (from the repository's root)
set -eu
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
if git ls-remote --exit-code --heads origin data >/dev/null; then
  git fetch --depth 1 origin data:refs/remotes/origin/data
  git worktree add data-branch origin/data
  git -C data-branch checkout -B data
else
  git worktree add --orphan -b data data-branch
fi
