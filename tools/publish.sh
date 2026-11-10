#!/bin/bash
# The data branch's files as they are in <data-dir>, published: index.json
# made again (tools/index.py, of every file, the sources' too), sources/ to
# the `sources` branch and the rest to `data`, each replaced by one commit with
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
# sources/ goes to the `sources` branch (several hundred MB: jsDelivr serves
# no branch over 50 MB, and `data` without it is served whole). First, so
# that `data` never loses a file the other branch does not have yet.
if [ -d sources ]; then
  index=$(mktemp -u)
  GIT_INDEX_FILE=$index git add -A -- sources
  tree=$(GIT_INDEX_FILE=$index git write-tree)
  rm -f "$index"
  last=$(git rev-parse -q --verify 'refs/remotes/origin/sources^{tree}' || true)
  if [ "$tree" != "$last" ]; then
    commit=$(git commit-tree "$tree" -m "$message")
    git push --force origin "$commit:refs/heads/sources"
    git update-ref refs/remotes/origin/sources "$commit"
  fi
fi
git rm -r -q --cached --ignore-unmatch sources
git add -A -- . ':(exclude)sources'
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
