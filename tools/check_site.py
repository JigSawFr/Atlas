#!/usr/bin/env python3
"""Checks Atlas's built website (tools/build_site.py) and its sources.

    python3 tools/check_site.py <site-dir>

- what every one of Boréale's sites passes (library/boreale-site,
  boreale_site.check): the page chrome (one header with the menu of Boréale's
  sites, the nav, the pill before GitHub, the footer, chrome.css and
  chrome.js), no {{key}} left, links and #anchors that lead
  somewhere, no referrer and the UTM tags of links to our other sites (the
  explorer's store links too, built in site/assets/explore.js, carry
  rel="noreferrer"), nothing the Content-Security-Policy blocks, Umami's
  tracker, no e-mail address, the explorer's texts (its application/json
  data) read as JSON;
- the catalogs of site/i18n/ and boreale-site's: the same keys as en-US.json,
  none empty, the same {placeholders} and <em> as English's, no common text
  repeated here;
- sitemap.xml reads; with a data copy built in, each platform's
  x/<platform>/lists.json and its sheets' shards, and x/<platform>/facets.json and its
  browse pages (every page there, every facet adding up);
- its size: GitHub Pages takes a site of 1 GB at most; past SIZE_WARN a
  warning in the run (time to cut data/ or x/), past SIZE_MAX an error.
"""
import json
import os
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "library" / "boreale-site"))
import boreale_site as boreale  # noqa: E402
from boreale_site import check  # noqa: E402

SIZE_WARN = 500 * 1000 ** 2   # bytes: half of what Pages takes
SIZE_MAX = 900 * 1000 ** 2    # bytes: a margin below Pages' 1 GB


def size(site: Path) -> int:
    """The site's bytes, every file counted."""
    return sum(p.stat().st_size for p in site.rglob("*") if p.is_file())


def browse_errors(folder: Path, site: Path) -> list:
    """What is wrong with a platform's browse index (x/<platform>/): no facets.json,
    a page missing, or a facet pointing at a value or a row that is not there, or
    adding up to another count than facets.json's."""
    name = folder.relative_to(site)
    try:
        facets = json.loads((folder / "facets.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"{name}/facets.json: {error}"]
    pages, errors, totals = facets.get("pages", 0), [], {}
    games = 0
    for n in range(pages):
        try:
            page = json.loads((folder / "browse" / f"{n}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            errors.append(f"{name}/browse/{n}.json: {error}")
            continue
        rows = len(page.get("games") or [])
        games += rows
        for kind, found in (page.get("facets") or {}).items():
            known = (facets.get("facets") or {}).get(kind) or []
            for number, gaps in found:
                last = -1
                for i, gap in enumerate(gaps):
                    last = gap if i == 0 else last + gap
                    if i and gap < 1:
                        errors.append(f"{name}/browse/{n}.json: facet {kind} repeats a row")
                if not 0 <= number < len(known) or last >= rows:
                    errors.append(f"{name}/browse/{n}.json: facet {kind}/{number} points at nothing")
                else:
                    totals[kind, number] = totals.get((kind, number), 0) + len(gaps)
    if games != facets.get("games"):
        errors.append(f"{name}: {games} games in the pages, not {facets.get('games')}")
    for kind, values in (facets.get("facets") or {}).items():
        for number, (value, count) in enumerate(values):
            if totals.get((kind, number), 0) != count:
                errors.append(f"{name}: facet {kind}/{value} adds up to {totals.get((kind, number), 0)}, not {count}")
    return errors


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    site = Path(sys.argv[1])
    errors = boreale.check_catalogs(ROOT / "site" / "i18n")
    found, pages = check.pages(site, boreale.Site("atlas", os.environ.get("SITE_URL")), skip=("assets", "data", "x"), chrome=True)
    errors += found

    try:
        ElementTree.parse(site / "sitemap.xml")
    except (OSError, ElementTree.ParseError) as error:
        errors.append(f"sitemap.xml: {error}")
    for lists in sorted(site.glob("x/*/lists.json")):
        body = json.loads(lists.read_text(encoding="utf-8"))
        shards = sorted(int(p.stem) for p in (lists.parent / "g").glob("*.json"))
        if shards != list(range(body.get("shards", 0))):
            errors.append(f"{lists.parent.relative_to(site)}: {len(shards)} shards, not {body.get('shards')}")
        errors += browse_errors(lists.parent, site)

    total = size(site)
    if total > SIZE_MAX:
        errors.append(f"{total / 1e6:.0f} MB, more than {SIZE_MAX / 1e6:.0f} MB (GitHub Pages takes 1 GB at most)")
    elif total > SIZE_WARN:
        print(f"::warning::check_site: {total / 1e6:.0f} MB, past {SIZE_WARN / 1e6:.0f} MB: GitHub Pages takes 1 GB at most")

    for e in errors:
        print(f"check_site: {e}")
    if errors:
        sys.exit(1)
    print(f"check_site: {pages} pages, {len(boreale.CODES)} catalogs, {total / 1e6:.1f} MB, nothing wrong")


if __name__ == "__main__":
    main()
