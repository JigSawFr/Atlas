#!/bin/bash
# The data branch's files as they are in <data-dir>, published: index.json
# made again (tools/index.py), the whole branch replaced by one commit with
# no history (the files' past is not needed: each run reads only the last
# one, and a history of daily prices would grow the repository by hundreds
# of MB a year), pushed, and jsDelivr asked again for the files that
# changed. Nothing changed: nothing pushed.
#
# Usage: tools/publish.sh <data-dir> <message>   (from the repository's root)
set -eu
dir=$1; message=$2
here=$(pwd)
python3 tools/index.py "$dir"
cd "$dir"
git add -A
if git diff --cached --quiet; then
  echo "nothing changed"
  exit 0
fi
changed=$(git diff --cached --name-only)
commit=$(git commit-tree "$(git write-tree)" -m "$message")
git push --force origin "$commit:refs/heads/data"
# jsDelivr keeps a branch's files up to 12 hours: asked again now.
for f in $changed; do
  curl -fsS "https://purge.jsdelivr.net/gh/${GITHUB_REPOSITORY}@data/$f" >/dev/null || true
done
cd "$here"
