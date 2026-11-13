#!/bin/bash
# The data branch's files as they are in <data-dir>, published: index.json
# made again (tools/index.py, of every file, whatever its branch), what
# tools/branches.conf names to its own branch (sources/ to `sources`, the PC
# stores' files and links.json to `data-stores`) and the rest to `data`, each replaced by one commit with
# no history (the files' past is not needed: each run reads only the last
# one, and a history of daily files would grow the repository by hundreds
# of MB a year), pushed, and jsDelivr asked again for the files that
# changed. Nothing changed: nothing pushed.
#
# Usage: tools/publish.sh <data-dir> <message>   (from the repository's root)
set -eu
dir=$1; message=$2
here=$(pwd)
python3 tools/index.py "$dir"
cd "$dir"
# What tools/branches.conf names goes to its own branch (jsDelivr serves no
# branch over 50 MB, and `data` without them is served whole). First, so that
# `data` never loses a file the other branch does not have yet.
apart=()
while read -r branch paths; do
  case $branch in ''|'#'*) continue;; esac
  # shellcheck disable=SC2086  # the paths, one word each
  for p in $paths; do apart+=("$p"); done
  present=()
  for p in $paths; do
    if [ -e "$p" ]; then present+=("$p"); fi
  done
  [ ${#present[@]} -gt 0 ] || continue
  index=$(mktemp -u)
  GIT_INDEX_FILE=$index git add -A -- "${present[@]}"
  tree=$(GIT_INDEX_FILE=$index git write-tree)
  rm -f "$index"
  last=$(git rev-parse -q --verify "refs/remotes/origin/$branch^{tree}" || true)
  [ "$tree" != "$last" ] || continue
  if [ -n "$last" ]; then moved=$(git diff --name-only --no-renames "$last" "$tree"); else moved=$(git ls-tree -r --name-only "$tree"); fi
  commit=$(git commit-tree "$tree" -m "$message")
  git push --force origin "$commit:refs/heads/$branch"
  git update-ref "refs/remotes/origin/$branch" "$commit"
  # A branch jsDelivr serves: its files that changed asked again, as below.
  case $branch in data*)
    if [ -n "${GITHUB_REPOSITORY:-}" ]; then
      for f in $moved; do
        curl -fsS -m 20 "https://purge.jsdelivr.net/gh/${GITHUB_REPOSITORY}@$branch/$f" >/dev/null || true
      done
    fi;;
  esac
done < "$here/tools/branches.conf"
excluded=()
for p in "${apart[@]}"; do excluded+=(":(exclude)$p"); done
git rm -r -q --cached --ignore-unmatch -- "${apart[@]}"
git add -A -- . "${excluded[@]}"
if git diff --cached --quiet; then
  echo "nothing changed"
  exit 0
fi
# Without renames: a moved file's old path is asked again too (it goes).
changed=$(git diff --cached --name-only --no-renames)
commit=$(git commit-tree "$(git write-tree)" -m "$message")
git push --force origin "$commit:refs/heads/data"
# jsDelivr keeps a branch's files up to 12 hours: asked again now.
if [ -n "${GITHUB_REPOSITORY:-}" ]; then
  for f in $changed; do
    curl -fsS -m 20 "https://purge.jsdelivr.net/gh/${GITHUB_REPOSITORY}@data/$f" >/dev/null || true
  done
fi
cd "$here"
