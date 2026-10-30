#!/bin/bash
# The data branch's files as they are in <data-dir>, kept as a GitHub
# release: data-YYYY-MM-DD, tagged on the commit of main that made them, with
# each file attached on its own (platforms/switch/prices/FR.json as
# platforms-switch-prices-FR.json: a
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
notes="Atlas' data files as published on $day: $files files, the same as the \`data\` branch had that day (\`platforms/switch/prices/FR.json\` is \`platforms-switch-prices-FR.json\` here; the zip keeps the folders). Their format is in the README."
if gh release view "$tag" >/dev/null 2>&1; then
  gh release delete "$tag" --yes --cleanup-tag
fi
# The tag pushed by git first, the release then made on it: the first run
# (2026-10-30) had the API refuse a release that made its own tag (403).
git push --force origin "$GITHUB_SHA:refs/tags/$tag"
gh release create "$tag" "$out"/* --verify-tag --latest \
  --title "Data of $day" --notes "$notes"
