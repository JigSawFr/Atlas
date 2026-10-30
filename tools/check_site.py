#!/usr/bin/env python3
"""Checks Atlas's built website (tools/build_site.py) and its sources.

    python3 tools/check_site.py <site-dir>

- every catalog of site/i18n/ has the same keys as en.json, none empty, with
  the same {placeholders} and <em> as English's;
- no {{key}} left in a page;
- every link and image to the site leads to a file, and every #anchor to an id;
- nothing the Content-Security-Policy blocks: no inline script (but the
  schema.org data, which runs nothing), no <style>, no style="" attribute,
  nothing loaded from another site; the one address a page may send to is
  Umami's (connect-src), whose tracker (assets/umami.js, the site's own copy)
  every page carries;
- no referrer: every page says `<meta name="referrer" content="no-referrer">`
  and every link to another site has rel="noreferrer", so a store or a
  source never learns a visitor came from Atlas (the explorer's store links
  too, built in site/assets/explore.js); but a link to boreale.dev, its
  subdomains or github.com/JigSawFr keeps the site's origin
  (referrerpolicy="strict-origin", no noreferrer), so GitHub's Traffic
  page still shows where visits come from;
- the explorer's texts (its application/json data) read as JSON, and with a
  data copy built in, each platform's x/<platform>/lists.json and shards;
- its size: GitHub Pages takes a site of 1 GB at most; past SIZE_WARN a
  warning in the run (time to cut data/ or x/), past SIZE_MAX an error.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ElementTree
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

ROOT = Path(__file__).resolve().parent.parent
SIZE_WARN = 500 * 1000 ** 2   # bytes: half of what Pages takes
SIZE_MAX = 900 * 1000 ** 2    # bytes: a margin below Pages' 1 GB



# No real e-mail address on the site, ours or anyone's: contact goes through
# the repository's issues, a security flaw through a private advisory.
EMAIL = re.compile(r"[\w.+-]+@(?:[\w-]+\.)+[a-z]{2,}", re.IGNORECASE)
RESERVED = re.compile(r"@(?:[\w-]+\.)*(?:example\.(?:org|com|net)|[\w-]+\.example)$", re.IGNORECASE)


def emails(text: str) -> list:
    return [f"an e-mail address ({m.group(0)}), contact goes through GitHub"
            for m in EMAIL.finditer(text) if not RESERVED.search(m.group(0))]


def size(site: Path) -> int:
    """The site's bytes, every file counted."""
    return sum(p.stat().st_size for p in site.rglob("*") if p.is_file())


def own(href: str) -> bool:
    """A link to Boréale's sites or to JigSawFr's GitHub: it keeps the origin."""
    url = urlparse(href)
    host = url.hostname or ""
    if host == "boreale.dev" or host.endswith(".boreale.dev"):
        return True
    return host == "github.com" and url.path.lower().startswith("/jigsawfr/")


# Atlas's own address (build_site.py's SITE_URL): its links to itself carry no UTM tags.
SITE_HOST = (urlparse(os.environ.get("SITE_URL", "https://atlas.boreale.dev/")).hostname or "").lower()

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
        if tag == "a" and urlparse(a.get("href") or "").scheme in ("http", "https"):
            rel = (a.get("rel") or "").split()
            if own(a["href"]):
                if "noreferrer" in rel or a.get("referrerpolicy") != "strict-origin":
                    self.problems.append(f"link to {a['href']} without referrerpolicy=\"strict-origin\" (or with noreferrer)")
            elif "noreferrer" not in rel:
                self.problems.append(f"link to {a['href']} without rel=\"noreferrer\"")
            # UTM tags (workbench's "Mesure d'audience"): a link to another of
            # our sites says it comes from Atlas (utm_source=atlas, a
            # utm_medium); one to Atlas itself or to anyone else carries none.
            u = urlparse(a["href"])
            host = (u.hostname or "").lower()
            query = dict(parse_qsl(u.query))
            if u.scheme == "https" and (host == "boreale.dev" or host.endswith(".boreale.dev")) and host != SITE_HOST:
                if query.get("utm_source") != "atlas" or not query.get("utm_medium"):
                    self.problems.append(f"link to {a['href']} without utm_source=atlas and a utm_medium")
            elif any(k.startswith("utm_") for k in query):
                self.problems.append(f"link to {a['href']} with utm_ parameters: only a link to another of our sites has them")
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
        errors += [f"{name}: {p}" for p in parsed.problems + emails(html)]
        if not any(attr == "src" and link.endswith("assets/umami.js") for attr, link in parsed.links):
            errors.append(f"{name}: no Umami tracker (assets/umami.js)")
        csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', html)
        if not csp or "connect-src 'self' https://gateway.umami.is;" not in csp.group(1):
            errors.append(f"{name}: its policy's connect-src is not 'self' and Umami's alone")
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

    total = size(site)
    if total > SIZE_MAX:
        errors.append(f"{total / 1e6:.0f} MB, more than {SIZE_MAX / 1e6:.0f} MB (GitHub Pages takes 1 GB at most)")
    elif total > SIZE_WARN:
        print(f"::warning::check_site: {total / 1e6:.0f} MB, past {SIZE_WARN / 1e6:.0f} MB: GitHub Pages takes 1 GB at most")

    for e in errors:
        print(f"check_site: {e}")
    if errors:
        sys.exit(1)
    print(f"check_site: {len(pages)} pages, {len(catalogs)} catalogs, {total / 1e6:.1f} MB, nothing wrong")


if __name__ == "__main__":
    main()
