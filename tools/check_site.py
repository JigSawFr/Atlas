#!/usr/bin/env python3
"""Checks Atlas's built website (tools/build_site.py) and its sources.

    python3 tools/check_site.py <site-dir>

- every catalog of site/i18n/ has the same keys as en.json, none empty, with
  the same {placeholders} and <em> as English's;
- no {{key}} left in a page;
- every link and image to the site leads to a file, and every #anchor to an id;
- nothing the Content-Security-Policy blocks: no inline script (but the
  schema.org data, which runs nothing), no <style>, no style="" attribute,
  nothing loaded from another site;
- no referrer: every page says `<meta name="referrer" content="no-referrer">`
  and every link to another site has rel="noreferrer", so a store or a
  source never learns a visitor came from Atlas (the explorer's store links
  too, built in site/assets/explore.js);
- the explorer's texts (its application/json data) read as JSON, and with a
  data copy built in, each platform's x/<platform>/lists.json and shards.
"""
import json
import re
import sys
import xml.etree.ElementTree as ElementTree
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.problems, self.data = set(), [], [], []
        self.in_data = False
        self.no_referrer = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if "style" in a:
            self.problems.append(f"style attribute on <{tag}>")
        if tag == "style":
            self.problems.append("<style> element")
        if tag == "meta" and a.get("name") == "referrer" and a.get("content") == "no-referrer":
            self.no_referrer = True
        if tag == "a" and urlparse(a.get("href") or "").scheme in ("http", "https") \
                and "noreferrer" not in (a.get("rel") or "").split():
            self.problems.append(f"link to {a['href']} without rel=\"noreferrer\"")
        if tag == "script":
            if a.get("type") == "application/json":
                self.in_data = True
                return
            if not a.get("src"):
                self.problems.append("inline <script>")
            self.links.append(("src", a.get("src") or ""))
        for name in ("href", "src"):
            if name in a and not (tag == "script" and name == "src"):
                self.links.append((name, a[name]))

    def handle_data(self, data):
        if self.in_data:
            self.data.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_data = False


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    site = Path(sys.argv[1])
    errors = []

    catalogs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "site/i18n").glob("*.json"))}
    reference = set(catalogs["en"])
    for lang, catalog in catalogs.items():
        for key in sorted(reference - set(catalog)):
            errors.append(f"i18n/{lang}.json: no {key}")
        for key in sorted(set(catalog) - reference):
            errors.append(f"i18n/{lang}.json: {key} is not in en.json")
        for key, text in catalog.items():
            if not str(text).strip():
                errors.append(f"i18n/{lang}.json: {key} is empty")
            if key in catalogs["en"]:
                english = catalogs["en"][key]
                if sorted(re.findall(r"\{[a-z]+\}", english)) != sorted(re.findall(r"\{[a-z]+\}", text)):
                    errors.append(f"i18n/{lang}.json: {key}'s placeholders differ from English's")
                if ("<em>" in english) != ("<em>" in text):
                    errors.append(f"i18n/{lang}.json: {key}'s <em> differs from English's")

    pages = sorted(site.rglob("*.html"))
    if not pages:
        errors.append(f"no page in {site}")
    for path in pages:
        name = path.relative_to(site)
        html = path.read_text(encoding="utf-8")
        if "{{" in html:
            errors.append(f"{name}: a {{{{key}}}} is left")
        parsed = Page()
        parsed.feed(html)
        errors += [f"{name}: {p}" for p in parsed.problems]
        if not parsed.no_referrer:
            errors.append(f"{name}: no <meta name=\"referrer\" content=\"no-referrer\">")
        try:
            json.loads("".join(parsed.data) or "{}")
        except ValueError as error:
            errors.append(f"{name}: its data is not JSON ({error})")
        for attr, link in parsed.links:
            url = urlparse(link)
            if url.scheme in ("http", "https", "mailto"):
                if attr == "src":
                    errors.append(f"{name}: loads {link} from another site")
                continue
            if name.name == "404.html" and url.path.startswith("/"):
                target = site / url.path.lstrip("/")  # served from the site's root
            else:
                target = (path.parent / url.path).resolve() if url.path else path
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                errors.append(f"{name}: {link} leads nowhere")
                continue
            if url.fragment and target == path and url.fragment not in parsed.ids:
                errors.append(f"{name}: #{url.fragment} is not on the page")

    try:
        ElementTree.parse(site / "sitemap.xml")
    except (OSError, ElementTree.ParseError) as error:
        errors.append(f"sitemap.xml: {error}")
    for lists in sorted(site.glob("x/*/lists.json")):
        body = json.loads(lists.read_text(encoding="utf-8"))
        shards = sorted(int(p.stem) for p in (lists.parent / "g").glob("*.json"))
        if shards != list(range(body.get("shards", 0))):
            errors.append(f"{lists.parent.relative_to(site)}: {len(shards)} shards, not {body.get('shards')}")

    for e in errors:
        print(f"check_site: {e}")
    if errors:
        sys.exit(1)
    print(f"check_site: {len(pages)} pages, {len(catalogs)} catalogs, nothing wrong")


if __name__ == "__main__":
    main()
