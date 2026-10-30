#!/bin/bash
# The data branch's files as they are in <data-dir>, kept as a GitHub
# release: data-YYYY-MM-DD, tagged on the commit of main that made them, with
# one archive of every file (playinsights-data-YYYY-MM-DD.tar.gz) and its
# SHA256SUMS.txt. The data branch keeps no history; these releases are its
# history, one a week, kept for good (a few MB each). Run again the same day,
# the release's files are replaced.
#
# Usage: tools/archive.sh <data-dir> <day> <out-dir>   (GH_TOKEN, GITHUB_SHA set)
set -eu
dir=$1; day=$2; out=$3
tag="data-$day"
name="playinsights-data-$day.tar.gz"
mkdir -p "$out"
# The same files give the same archive: sorted, owner and dates fixed.
tar --exclude=.git --sort=name --owner=0 --group=0 --numeric-owner \
    --mtime="$day 00:00:00Z" -C "$dir" -cf - . | gzip -n -9 > "$out/$name"
(cd "$out" && sha256sum "$name" > SHA256SUMS.txt && cat SHA256SUMS.txt)

files=$(python3 -c "import json,sys; print(len(json.load(open(sys.argv[1]))['files']))" "$dir/index.json")
notes="PlayInsights' data files as published on $day: $files files, the same as the \`data\` branch had that day (see its \`index.json\`). Their format is in the README."
if gh release view "$tag" >/dev/null 2>&1; then
  gh release upload "$tag" "$out/$name" "$out/SHA256SUMS.txt" --clobber
else
  gh release create "$tag" "$out/$name" "$out/SHA256SUMS.txt" \
    --target "$GITHUB_SHA" --title "Data of $day" --notes "$notes"
fi
