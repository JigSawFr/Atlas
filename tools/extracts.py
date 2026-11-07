"""The first lines of a game's Wikipedia page, for its sheet (site/README.md): what Wikipedia's summary
service gives (`/api/rest_v1/page/summary/<title>`), a few hundred characters of the page's introduction,
in English and French. The text is Wikipedia's (CC BY-SA 4.0): the sheet says so and links to the page.

    sources/wikipedia/extracts.json   {"items": {qid: {lang: text}}}

The games are asked most-translated first (a game on many Wikipedias is a known one), WEEKLY at a time, the
ones not known yet first; the extracts already known are kept (a page's first lines rarely change).
Python's standard library only.
"""
import re
import time
import urllib.parse

import common

LANGS = ("en", "fr")
WEEKLY = 2500          # games asked in a run, at most
LIMIT = 420            # characters kept
SECONDS = 900          # a run's time for the requests
SUMMARY = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
SENTENCE = re.compile(r"(?<=[.!?。])\s+(?=[A-ZÀ-ÖØ-Þ0-9«“\"'])")


def ranked(pages):
    """[qid] of the games with a page in LANGS, the most translated first; `pages`: {qid: {lang: title}}."""
    return sorted((q for q, p in pages.items() if any(l in p for l in LANGS)), key=lambda q: (-len(pages[q]), int(q[1:])))


def trim(text):
    """A summary's first sentences within LIMIT characters ('' for one too short to say anything)."""
    text = " ".join(str(text or "").split())
    if len(text) <= LIMIT:
        return text if len(text) >= 40 else ""
    out = ""
    for sentence in SENTENCE.split(text):
        if out and len(out) + len(sentence) + 1 > LIMIT:
            break
        out = f"{out} {sentence}".strip()
    return out[:LIMIT].rstrip() + ("…" if len(out) > LIMIT else "")


def read(summary):
    """The extract of a summary answer, '' when the page is not an article (disambiguation, redirect…)."""
    if not isinstance(summary, dict) or summary.get("type") != "standard":
        return ""
    return trim(summary.get("extract"))


def collect(pages, kept, fetch, clock=time.monotonic, limit=WEEKLY, seconds=SECONDS):
    """{qid: {lang: text}}: the `kept` extracts and up to `limit` more for the games of `pages`
    ({qid: {lang: title}}), those with none yet first, within `seconds`. `fetch(url)` gives the JSON or None."""
    out = {q: dict(v) for q, v in kept.items() if isinstance(v, dict)}
    order = ranked(pages)
    asked, start = 0, clock()
    for qid in [q for q in order if q not in out] + [q for q in order if q in out]:
        if asked >= limit or clock() - start > seconds:
            break
        for lang in LANGS:
            title = pages[qid].get(lang)
            if not title or lang in out.get(qid, {}):
                continue
            asked += 1
            try:
                text = read(fetch(SUMMARY.format(lang=lang, title=urllib.parse.quote(urllib.parse.unquote(title), safe="()_,'"))))
            except Exception:       # a page that does not answer is left for the next run
                continue
            if text:
                out.setdefault(qid, {})[lang] = text
    return out
