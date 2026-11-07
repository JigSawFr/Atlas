#!/bin/bash
# The data branch's files as they are in <data-dir>, kept as a GitHub
# release: data-YYYY-MM-DD (data-YYYY-MM-DD-2… when a release still holds
# the day's tag), tagged on the commit of main that made them, with
# each file attached on its own (platforms/switch/popular.json as
# platforms-switch-popular.json: a
# release's files have no folders), all of them in one zip
# (atlas-data-YYYY-MM-DD.zip, with its folders), and a SHA256SUMS.txt. The data branch
# keeps no history; these releases are its history, one a week, kept for
# good. Run again the same day, the release is made again.
#
# Usage: tools/archive.sh <data-dir> <day> <out-dir>   (GH_TOKEN, GITHUB_SHA set)
set -eu
dir=$1; day=$2; out=$3
tag="data-$day"
rm -rf "$out"; mkdir -p "$out"
(cd "$dir" && find . -type f -not -name .git -not -path './.git/*' -printf '%P\n') | sort |
  while IFS= read -r f; do cp "$dir/$f" "$out/${f//\//-}"; done
# The same files give the same zip: sorted, dates fixed.
python3 - "$dir" "$day" "$out/atlas-data-$day.zip" <<'PY'
import os, sys, zipfile
src, day, dest = sys.argv[1:]
stamp = tuple(int(x) for x in day.split("-")) + (0, 0, 0)
names = sorted(os.path.relpath(os.path.join(r, f), src)
               for r, ds, fs in os.walk(src) for f in fs if ".git" not in os.path.join(r, f)[len(src):].split(os.sep))
with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for n in names:
        info = zipfile.ZipInfo(n.replace(os.sep, "/"), stamp)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        with open(os.path.join(src, n), "rb") as f:
            z.writestr(info, f.read(), compresslevel=9)
PY
(cd "$out" && sha256sum -- * > ../SHA256SUMS.txt && mv ../SHA256SUMS.txt . && cat SHA256SUMS.txt)

files=$(python3 -c "import json,sys; print(len(json.load(open(sys.argv[1]))['files']))" "$dir/index.json")
notes="Atlas' data files as published on $day: $files files, the same as the \`data\` branch had that day (\`platforms/switch/popular.json\` is \`platforms-switch-popular.json\` here; the zip keeps the folders). Their format is in the README."
if gh release view "$tag" >/dev/null 2>&1; then
  gh release delete "$tag" --yes --cleanup-tag
fi
# A draft left by a run that failed half way (the release made, not all its
# files sent) is of no use, and `gh release view` does not see it: deleted if
# GitHub lets us (it answered 502 on one, 2026-11-07, from the API and from
# the web page), left alone if not.
gh api --paginate "repos/$GITHUB_REPOSITORY/releases" --jq '.[] | select(.draft) | .id' |
  while IFS= read -r id; do
    gh api -X DELETE "repos/$GITHUB_REPOSITORY/releases/$id" >/dev/null ||
      echo "archive: draft $id not deleted, its tag is not reused" >&2
  done
# A tag a release still holds is not reused (two drafts on one tag cannot be
# told apart by `gh release upload`): data-YYYY-MM-DD-2, -3...
base=$tag; version=1
taken=$(gh api --paginate "repos/$GITHUB_REPOSITORY/releases" --jq '.[].tag_name')
while grep -qxF "$tag" <<<"$taken"; do
  version=$((version + 1)); tag="$base-$version"
done
title="Data of $day"
[ "$version" -eq 1 ] || title="$title, version $version"
# The tag pushed by git first, the release then made on it: the first run
# (2026-10-30) had the API refuse a release that made its own tag (403).
git push --force origin "$GITHUB_SHA:refs/tags/$tag"
# Made as a draft, the files sent one by one, then published: sending 200
# files in one `gh release create` ran into GitHub's secondary rate limit
# (403 on 2026-11-07, the release left as a draft). One file a second, and a
# file that gets the limit is sent again after a wait.
gh release create "$tag" --draft --verify-tag \
  --title "$title" --notes "$notes"
for f in "$out"/*; do
  n=0
  until gh release upload "$tag" "$f" --clobber; do
    n=$((n + 1))
    [ "$n" -lt 5 ] || { echo "archive: $f not sent after $n tries" >&2; exit 1; }
    sleep $((60 * n))
  done
  sleep 1
done
gh release edit "$tag" --draft=false --latest
