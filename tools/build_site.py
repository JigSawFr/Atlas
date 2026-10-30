#!/usr/bin/env python3
"""Builds Atlas's website (the PlayInsights repository's) into <out-dir> (site/README.md).

    python3 tools/build_site.py <out-dir> [<data-dir>]

<data-dir> is a copy of the data branch (git clone -b data): it is
published as it is under data/, cut for the explorer under x/
(tools/site_data.py), and its index.json gives the project page its files,
their sizes and days. Without it the pages are built with no figures.

site/template.html is the page around site/home.html (the project) and
site/explore.html (explore/: the explorer, assets/explore.js); each {{key}}
is the key's text in the language's catalog, site/i18n/<language>.json.
The fifteen languages of Boréale's sites (LANGUAGES): English at the root,
each other one in its folder (fr/, fr-ca/, de/ ... zh-hant/).

SITE_URL is the site's address (https://atlas.boreale.dev/ by default);
the links inside the site are relative, so it works at another one
(https://jigsawfr.github.io/Atlas/) too. Python's standard library only.
"""
import html
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import platforms  # noqa: E402
import site_data  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITE_URL = os.environ.get("SITE_URL", "https://atlas.boreale.dev/").rstrip("/") + "/"
# The audience, counted by Umami Cloud (site/README.md): its tracker, served from
# assets/, sends each page seen to gateway.umami.is, without cookie, and only from
# the site's own address (not a local copy). Its site in Umami is Boréale's,
# shared by its projects' sites: Umami's Hostname filter tells them apart.
UMAMI_WEBSITE = "6410ffdd-ae2e-4ddb-8e18-0a77e9fa374e"
UMAMI_DOMAIN = urlparse(SITE_URL).hostname
# Boréale's sites' languages: the catalog's code, the folder ('' for the
# root), the name in its own words, the html lang.
LANGUAGES = [
    ("en", "", "English", "en"),
    ("fr", "fr", "Français", "fr"),
    ("fr-CA", "fr-ca", "Français (Canada)", "fr-CA"),
    ("de", "de", "Deutsch", "de"),
    ("es", "es", "Español", "es"),
    ("es-419", "es-419", "Español (Latinoamérica)", "es-419"),
    ("it", "it", "Italiano", "it"),
    ("nl", "nl", "Nederlands", "nl"),
    ("pt", "pt", "Português", "pt-PT"),
    ("pt-BR", "pt-br", "Português (Brasil)", "pt-BR"),
    ("ru", "ru", "Русский", "ru"),
    ("ja", "ja", "日本語", "ja"),
    ("ko", "ko", "한국어", "ko"),
    ("zh-Hans", "zh-hans", "简体中文", "zh-Hans"),
    ("zh-Hant", "zh-hant", "繁體中文", "zh-Hant"),
]
FLAGS = {"en": "US", "fr": "FR", "fr-CA": "CA", "de": "DE", "es": "ES", "es-419": "MX", "it": "IT", "nl": "NL",
         "pt": "PT", "pt-BR": "BR", "ru": "RU", "ja": "JP", "ko": "KR", "zh-Hans": "CN", "zh-Hant": "TW"}
OG_LOCALES = {"en": "en_US", "fr": "fr_FR", "fr-CA": "fr_CA", "de": "de_DE", "es": "es_ES", "es-419": "es_LA",
              "it": "it_IT", "nl": "nl_NL", "pt": "pt_PT", "pt-BR": "pt_BR", "ru": "ru_RU", "ja": "ja_JP",
              "ko": "ko_KR", "zh-Hans": "zh_CN", "zh-Hant": "zh_TW"}
# The platforms, in their order: those the data has are live, the others coming.
PLATFORMS = [(p[0], p[1]) for p in platforms.STORES + platforms.CONSOLES] + [(p[0], p[1]) for p in platforms.RETRO]
STORE_IDS = {p[0] for p in platforms.STORES + platforms.CONSOLES}   # a button each; the old machines in a list
MACHINES = "|".join(re.escape(p[0]) for p in platforms.RETRO)
# The pages, by their path under each language's folder.
PAGES = {"": "home", "explore/": "explore", "status/": "status"}
# Boréale's sites, in the header's menu (switcher()): boreale.dev's
# reference (boreale/tools/build_site.py), then the open data and protocols,
# this one and Lantern.
SITES = [(None, [("boreale", "Boréale", "https://boreale.dev/")]),
         ("sites_homebrew", [("playguard", "PlayGuard", "https://guard.boreale.dev/"),
                             ("playshelf", "PlayShelf", "https://shelf.boreale.dev/")]),
         ("sites_libraries", [("aurore", "Aurore", "https://aurore.boreale.dev/")]),
         ("sites_open", [("atlas", "Atlas", "https://atlas.boreale.dev/"),
                         ("lantern", "Lantern", "https://lantern.boreale.dev/")])]
HERE = "atlas"
# Where a visit to another of Boréale's sites came from, for Umami (Boréale's
# audience rules): a link from this site to another *.boreale.dev site
# carries utm_source=atlas and a utm_medium telling where on the page it is
# ("nav" for the header's sites menu, "footer"). A link to this site carries none.
UTM_SOURCE = "atlas"
# A file made every day; the others every week (late past 2 and 9 days).
# The sources collected every day (in part: wikidata's pages, wikipedia's
# daily views; tools/collect.py); the others every week. The status page
# marks one late past 2 days, or 9.
DAILY_SOURCES = {"wikipedia", "wikidata"}
DAILY = re.compile(r"^platforms/(switch|steam)/popular\.json$|^sources/wikipedia/daily\.json$|^sources/wikidata/[a-z0-9]+-pages\.json$")

# Numbers and sizes as each language writes them: the thousands' and the
# decimals' marks, the units.
MARKS = {"en": (",", "."), "fr": (" ", ","), "fr-CA": (" ", ","), "de": (".", ","), "es": (".", ","),
         "es-419": (",", "."), "it": (".", ","), "nl": (".", ","), "pt": (" ", ","), "pt-BR": (".", ","),
         "ru": (" ", ","), "ja": (",", "."), "ko": (",", "."), "zh-Hans": (",", "."), "zh-Hant": (",", ".")}
UNITS = {"fr": ("ko", "Mo"), "fr-CA": ("ko", "Mo"), "ru": ("КБ", "МБ")}
_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]
_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "fr": _FR, "fr-CA": _FR,
    "de": ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."],
    "es": _ES, "es-419": _ES,
    "it": ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"],
    "nl": ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
    "pt": _PT, "pt-BR": _PT,
    "ru": ["янв.", "февр.", "мар.", "апр.", "мая", "июн.", "июл.", "авг.", "сент.", "окт.", "нояб.", "дек."],
}
DATES = {"en": "{m} {d}, {y}", "de": "{d}. {m} {y}", "ja": "{y}年{n}月{d}日", "zh-Hans": "{y}年{n}月{d}日",
         "zh-Hant": "{y}年{n}月{d}日", "ko": "{y}. {n}. {d}."}  # else "{d} {m} {y}"

KEY = re.compile(r"\{\{([a-z0-9_]+)\}\}")


def folder(language: str) -> str:
    return next(f for c, f, _, _ in LANGUAGES if c == language) + ("/" if language != "en" else "")


def fill(text: str, values: dict) -> str:
    def one(match):
        key = match.group(1)
        if key not in values:
            sys.exit(f"build_site: no text for {{{{{key}}}}}")
        return values[key]
    return KEY.sub(one, KEY.sub(one, text))


def number(n: int, language: str) -> str:
    return f"{n:,}".replace(",", MARKS[language][0])


def size(n: int, language: str) -> str:
    kb, mb = UNITS.get(language, ("kB", "MB"))
    if n < 1_000_000:
        return f"{max(1, round(n / 1000))} {kb}"
    return f"{n / 1_000_000:.1f}".replace(".", MARKS[language][1]) + f" {mb}"


def day(text: str, language: str) -> str:
    """A YYYY-MM-DD as the language writes it, short."""
    try:
        d = date.fromisoformat(text)
    except (TypeError, ValueError):
        return ""
    month = MONTHS[language][d.month - 1] if language in MONTHS else ""
    return DATES.get(language, "{d} {m} {y}").format(d=d.day, m=month, n=d.month, y=d.year)


def utm(url: str, medium: str) -> str:
    """`url` tagged for its medium, or as it is when it leads out of Boréale's
    sites or to this site itself."""
    u = urlsplit(url)
    host = (u.hostname or "").lower()
    if u.scheme != "https" or not (host == "boreale.dev" or host.endswith(".boreale.dev")):
        return url
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not k.startswith("utm_")]
    if host != (urlsplit(SITE_URL).hostname or ""):
        query += [("utm_source", UTM_SOURCE), ("utm_medium", medium)]
    return urlunsplit(u._replace(query=urlencode(query)))


def switcher(language: str, catalog: dict, root: str) -> str:
    """The header's name, a button that opens the menu of Boréale's sites
    (site.css's and site.js's "site switcher" blocks, boreale.dev's), this
    one marked and leading home. A popover: the browser closes it on Esc or
    a click elsewhere. The other sites keep the origin and carry their UTM
    tags (utm()); no versions: this build reads nothing from boreale.dev."""
    label = catalog["sites_label"]
    groups = []
    for title, sites in SITES:
        items = []
        for key, name, url in sites:
            if key == HERE:
                link = f'href="{root}{folder(language)}" aria-current="true"'
            else:
                link = f'href="{html.escape(utm(url + folder(language), "nav"))}" referrerpolicy="strict-origin"'
            soon = f'<em class="soon">{catalog["sites_soon"]}</em>' if key == "playshelf" else ""
            items.append(f'<li><a {link}>'
                         f'<img src="{root}assets/marks/{key}.svg" alt="" width="36" height="36">'
                         f'<span><strong>{name}</strong><small>{catalog[f"sites_{key}"]}</small></span>{soon}</a></li>')
        heading = f'<p class="sites-title">{catalog[title]}</p>' if title else ""
        groups.append(f'        {heading}<ul>\n          ' + "\n          ".join(items) + '\n        </ul>')
    return (f'<div class="switcher">\n'
            f'      <button class="brand switch" type="button" popovertarget="sites" aria-label="Atlas · {label}">'
            f'<img src="{root}assets/mark.svg" alt="" width="34" height="34">Atlas'
            f'<svg class="chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></button>\n'
            f'      <div id="sites" class="sites" popover aria-label="{label}">\n'
            + "\n".join(groups) + '\n      </div>\n    </div>')


def flag(language: str) -> str:
    emoji = "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in FLAGS[language])
    return f'<span class="flag" aria-hidden="true">{emoji}</span>'


def languages(language: str, catalog: dict, root: str, path: str) -> str:
    """The header's languages: a button with the page's, and their menu (a
    popover), this page in each. Choosing one keeps it (assets/lang.js)."""
    name = next(n for c, _, n, _ in LANGUAGES if c == language)
    current = ' aria-current="true"'
    options = "\n".join(
        f'        <li><a href="{root}{folder(c)}{path}" data-lang="{d or c}" lang="{hl}" hreflang="{hl}"'
        f'{current if c == language else ""}>{flag(c)}{html.escape(n)}</a></li>'
        for c, d, n, hl in LANGUAGES)
    label = catalog["language"]
    return (f'<div class="settings">\n'
            f'      <button class="lang-button" type="button" popovertarget="languages" aria-label="{label} · {html.escape(name)}">'
            f'{flag(language)}<span class="lang-name">{html.escape(name)}</span>'
            f'<span class="lang-code">{language.split("-")[0].upper()}</span>'
            f'<svg class="chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></button>\n'
            f'      <ul id="languages" class="langs" popover aria-label="{label}">\n{options}\n      </ul>\n    </div>')


def indexing(path: str) -> str:
    """The canonical address and the other languages' for search engines."""
    lines = [f'<link rel="canonical" href="{SITE_URL}{path}">']
    return "\n".join(lines)


def alternates(path_in: str) -> str:
    out = [f'<link rel="alternate" hreflang="{hl}" href="{SITE_URL}{folder(c)}{path_in}">' for c, _, _, hl in LANGUAGES]
    out.append(f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}{path_in}">')
    return "\n".join(out)


def platform_cards(language: str, catalog: dict, root: str, summary: dict) -> str:
    """A card a store, then one for every old machine together (retro)."""
    machines = [k for k, _ in PLATFORMS if k not in STORE_IDS and k in summary]
    retro = {"games": sum(summary[k]["games"] for k in machines),
             "generated": max((summary[k].get("generated") or "" for k in machines), default="")}
    cards = []
    for key, name in [(k, n) for k, n in PLATFORMS if k in STORE_IDS] + [("retro", "Retro")]:
        s = retro if key == "retro" else (summary.get(key) or {})
        live = bool(machines) if key == "retro" else key in summary
        target = machines[0] if key == "retro" and machines else key
        facts = ""
        if live:
            items = [catalog["platform_games"].replace("{n}", number(s["games"], language))]
            if s.get("generated"):
                items.append(catalog["platform_updated"].replace("{date}", day(s["generated"], language)))
            facts = '<ul class="facts">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
            more = f'<a class="more" href="{root}{folder(language)}explore/#{target}/popular">{catalog["platform_explore"]}</a>'
            state = f'<span class="state live">{catalog["platform_live"]}</span>'
        else:
            more = ""
            state = f'<span class="state">{catalog["platform_soon"]}</span>'
        cards.append(f'      <li class="platform{" soon" if not live else ""}"><div class="head"><h3>{name}</h3>{state}</div>'
                     f'<p>{catalog[f"platform_{key}_text"]}</p>{facts}{more}</li>')
    return "\n".join(cards)


def file_kind(name: str) -> str:
    if name.startswith("sources/"):
        return "source"
    base = name.rsplit("/", 1)[-1]
    return base[:-5] if base.endswith(".json") else base


def file_rows(language: str, catalog: dict, index: dict) -> str:
    """index.json's files, a source's or the old machines' kind in one row."""
    groups = {}
    for name, f in sorted(((index or {}).get("files") or {}).items()):
        # A source's files in one row (they are not copied here: sources/ stays on the data branch).
        key = re.sub(r"^(sources/[^/]+/).*$", r"\1…", name)
        # The old machines' files, one row a kind of file.
        key = re.sub(rf"^platforms/({MACHINES})/", "platforms/<machine>/", key)
        g = groups.setdefault(key, {"bytes": 0, "generated": "", "n": 0, "name": name})
        g["bytes"] += f.get("bytes", 0)
        g["generated"] = max(g["generated"], f.get("generated") or "")
        g["n"] += 1
    groups["index.json"] = {"bytes": 0, "generated": "", "n": 1, "name": "index.json"}
    rows = []
    for key, g in groups.items():
        kind = file_kind(g["name"])
        what = catalog.get(f"file_{kind}", "")
        daily = bool(DAILY.search(g["name"]))
        rhythm = catalog["files_daily"] if daily else catalog["files_weekly"]
        shown = html.escape(key) + (f' <small>×{g["n"]}</small>' if g["n"] > 1 else "")
        when = (f'<time datetime="{g["generated"]}" data-age="{2 if daily else 9}" data-late="{catalog["files_late"]}">'
                f'{day(g["generated"], language)}</time>') if g["generated"] else "—"
        rows.append(f'          <tr><td><code>{shown}</code></td><td>{what}</td><td>{rhythm}</td>'
                    f'<td class="num">{size(g["bytes"], language) if g["bytes"] else "—"}</td><td>{when}</td></tr>')
    return "\n".join(rows)


def percent(share, language: str) -> str:
    n = round((share or 0) * 100)
    return f"{n}\u202f%" if language in ("fr", "fr-CA") else (f"{n} %" if language in ("de", "ru") else f"{n}%")


def age(made: str, report: str):
    """Days between a day and the report's, None when either is missing."""
    try:
        return (date.fromisoformat(report) - date.fromisoformat(made)).days
    except (TypeError, ValueError):
        return None


def state(made: str, report: str, days: int, empty: bool, catalog: dict) -> str:
    """Up to date, late (older than its rhythm allows when the report was
    made: the run left it behind), or no data."""
    late = age(made, report)
    if empty or late is None:
        return f'<span class="state missing">{catalog["status_missing"]}</span>'
    if late > days:
        return f'<span class="state late">{catalog["status_late"]}</span>'
    return f'<span class="state ok">{catalog["status_ok"]}</span>'


def when(made: str, days: int, catalog: dict, language: str) -> str:
    """A day, marked late by site.js when older than `days` today."""
    if not made:
        return "—"
    return f'<time datetime="{made}" data-age="{days}" data-late="{catalog["files_late"]}">{day(made, language)}</time>'


def status_body(language: str, catalog: dict, root: str, report: dict, index: dict) -> str:
    """The data's status (status/), from report.json (tools/report.py) and
    index.json: the run, each source's and platform's last update and state,
    each platform's games linked and reviewed. Without a report (a
    build without data, a branch from before report.json), a note."""
    if not report:
        return (f'  <section id="status">\n    <p class="note empty">{catalog["status_none"]} '
                f'<a href="{root}{folder(language)}#files">{catalog["status_files"]}</a></p>\n  </section>')
    made = report.get("generated") or ""
    files = (index or {}).get("files") or {}
    run = catalog.get(f'status_run_{report.get("run")}', html.escape(str(report.get("run") or "—")))
    stats = [(catalog["status_generated"], when(made, 2, catalog, language)), (catalog["status_run"], run)]
    if files:
        stats += [(catalog["status_files_count"], number(len(files), language)),
                  (catalog["files_size"], size(sum(f.get("bytes", 0) for f in files.values()), language))]
    out = ['  <section id="run">', '    <dl class="stats">']
    out += [f"      <div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in stats]
    out += ['    </dl>', '  </section>', '']
    head = (f'<th scope="col">{catalog["status_state"]}</th>')
    rows = []
    for name, s in sorted((report.get("sources") or {}).items()):
        days = 2 if name in DAILY_SOURCES else 9
        rhythm = catalog["files_daily"] if days == 2 else catalog["files_weekly"]
        rows.append(f'          <tr><th scope="row"><code>{html.escape(name)}</code></th>'
                    f'<td>{state(s.get("generated") or "", made, days, not s.get("records"), catalog)}</td><td>{rhythm}</td>'
                    f'<td class="num">{number(s.get("records") or 0, language)}</td>'
                    f'<td class="num">{size(s.get("bytes") or 0, language)}</td>'
                    f'<td>{when(s.get("generated") or "", days, catalog, language)}</td></tr>')
    out += [f'  <section id="sources">', '    <div class="section-head">',
            f'      <h2>{catalog["status_sources_title"]}</h2>', f'      <p>{catalog["status_sources_lede"]}</p>', '    </div>',
            f'    <div class="table" tabindex="0" role="region" aria-label="{catalog["status_sources_title"]}">',
            '      <table class="status">',
            f'        <thead><tr><th scope="col">{catalog["status_source"]}</th>{head}<th scope="col">{catalog["files_rhythm"]}</th>'
            f'<th scope="col" class="num">{catalog["status_records"]}</th><th scope="col" class="num">{catalog["files_size"]}</th>'
            f'<th scope="col">{catalog["files_updated"]}</th></tr></thead>',
            '        <tbody>', *rows, '        </tbody>', '      </table>', '    </div>', '  </section>', '']
    names = dict(PLATFORMS)
    reported = report.get("platforms") or {}

    def table(ids, label):
        rows = []
        for pid in ids:
            p = reported[pid]
            days = 2 if DAILY.search(f"platforms/{pid}/popular.json") else 9
            rows.append(f'          <tr><th scope="row">{html.escape(names.get(pid, pid))}</th>'
                        f'<td>{state(p.get("generated") or "", made, days, not p.get("games"), catalog)}</td>'
                        f'<td class="num">{number(p.get("games") or 0, language)}</td>'
                        + "".join(f'<td class="num">{percent(p.get(k), language)}</td>' for k in ("linked", "reviewed"))
                        + f'<td>{when(p.get("generated") or "", days, catalog, language)}</td></tr>')
        return [f'    <div class="table" tabindex="0" role="region" aria-label="{label}">', '      <table class="status">',
                f'        <thead><tr><th scope="col">{catalog["status_platform"]}</th>{head}'
                f'<th scope="col" class="num">{catalog["status_games"]}</th><th scope="col" class="num">{catalog["status_linked"]}</th>'
                f'<th scope="col" class="num">{catalog["status_reviewed"]}</th>'
                f'<th scope="col">{catalog["files_updated"]}</th></tr></thead>',
                '        <tbody>', *rows, '        </tbody>', '      </table>', '    </div>']

    order = [k for k, _ in PLATFORMS]
    known = sorted(reported, key=lambda k: (order.index(k) if k in order else len(order), k))
    stores = [k for k in known if k not in names or k in STORE_IDS]
    machines = [k for k in known if k in names and k not in STORE_IDS]
    out += ['  <section id="platforms">', '    <div class="section-head">',
            f'      <h2>{catalog["status_platforms_title"]}</h2>', f'      <p>{catalog["status_platforms_lede"]}</p>', '    </div>']
    out += table(stores, catalog["status_platforms_title"])
    if machines:
        retro = catalog["status_retro"].replace("{n}", str(len(machines)))
        out += [f'    <details class="retro"><summary>{retro}</summary>', *table(machines, retro), '    </details>']
    out += [f'    <p class="note">{catalog["status_note"]} <a href="{root}data/report.json">report.json</a></p>', '  </section>']
    return "\n".join(out)


def hero(page: str, catalog: dict, root: str, language: str) -> str:
    if page == "home":
        return (f'<div class="wrap hero">\n    <span class="eyebrow">{catalog["hero_eyebrow"]}</span>\n'
                f'    <h1>{catalog["hero_title"]}</h1>\n    <p class="lede">{catalog["hero_lede"]}</p>\n'
                f'    <div class="actions"><a class="button primary" href="{root}{folder(language)}explore/">{catalog["cta_explore"]}</a>'
                f'<a class="button ghost" href="https://github.com/JigSawFr/Atlas" referrerpolicy="strict-origin">{catalog["cta_github"]}</a></div>\n  </div>')
    return (f'<div class="wrap hero small">\n    <span class="eyebrow">{catalog[f"{page}_eyebrow"]}</span>\n'
            f'    <h1>{catalog[f"{page}_title"]}</h1>\n    <p class="lede">{catalog[f"{page}_lede"]}</p>\n  </div>')


def strings(catalog: dict, language: str, summary: dict) -> str:
    """The explorer's texts and settings, as JSON in the page (data, not a script)."""
    body = {k: v for k, v in catalog.items() if k.startswith("x_")}
    body["_platforms"] = {k: summary[k]["shards"] for k in summary}
    body["_names"] = dict(PLATFORMS)
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def page_html(template: str, language: str, catalog: dict, path: str, page: str, summary: dict, index: dict,
              report: dict = None) -> str:
    depth = path.count("/") + (1 if language != "en" else 0)
    root = "../" * depth
    body = (SITE / f"{page}.html").read_text(encoding="utf-8")
    hl = next(h for c, _, _, h in LANGUAGES if c == language)
    values = dict(catalog)
    values.update({
        "lang": hl, "root": root, "home": folder(language), "site": SITE_URL, "page": page,
        "url": SITE_URL + folder(language) + path,
        "title": catalog[f"title_{page}"], "description": html.escape(catalog[f"description_{page}"], quote=True),
        "og_locale": OG_LOCALES[language],
        "first_visit": ' data-first-visit=""' if language == "en" and path == "" else "",
        "indexing": indexing(folder(language) + path) + "\n" + alternates(path),
        "languages": languages(language, catalog, root, path),
        "switcher": switcher(language, catalog, root),
        "current_project": ' aria-current="page"' if page == "home" else "",
        "current_explore": ' aria-current="page"' if page == "explore" else "",
        "current_status": ' aria-current="page"' if page == "status" else "",
        "status_body": status_body(language, catalog, root, report, index) if page == "status" else "",
        "scripts": f'<script src="{root}assets/explore.js" defer></script>' if page == "explore" else "",
        "audience": f'<script src="{root}assets/umami.js" defer data-website-id="{UMAMI_WEBSITE}" '
                    f'data-domains="{UMAMI_DOMAIN}"></script>',
        "hero": hero(page, catalog, root, language),
        "platform_cards": platform_cards(language, catalog, root, summary) if page == "home" else "",
        "file_rows": file_rows(language, catalog, index) if page == "home" else "",
        "platform_buttons": "\n".join(
            f'        <button type="button" data-platform="{k}">{n}</button>' for k, n in PLATFORMS
            if k in summary and k in STORE_IDS) if page == "explore" else "",
        "machine_hidden": "" if any(k in summary and k not in STORE_IDS for k, _ in PLATFORMS) else " hidden",
        "machine_options": "\n".join(
            f'          <option value="{k}">{html.escape(n)}</option>' for k, n in PLATFORMS
            if k in summary and k not in STORE_IDS) if page == "explore" else "",
        "strings": strings(catalog, language, summary) if page == "explore" else "",
    })
    values["body"] = fill(body, values)
    return fill(template, values)


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    out = Path(sys.argv[1])
    data = Path(sys.argv[2]) if len(sys.argv) == 3 else None
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(SITE / "assets", out / "assets")
    summary, index, report = {}, {}, {}
    if data:
        # The sources are not the explorer's: left on the data branch, the site smaller.
        shutil.copytree(data, out / "data", ignore=lambda d, names: [n for n in names if n.startswith(".git")
                                                                   or (Path(d) == data and n == "sources")])
        summary = site_data.build(str(data), str(out))
        index = site_data.read(str(data / "index.json")) or {}
        report = site_data.read(str(data / "report.json")) or {}
    catalogs = {c: json.loads((SITE / "i18n" / f"{c}.json").read_text(encoding="utf-8")) for c, _, _, _ in LANGUAGES}
    template = (SITE / "template.html").read_text(encoding="utf-8")
    urls = []
    for language, _, _, _ in LANGUAGES:
        for path, page in PAGES.items():
            target = out / folder(language) / path / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(page_html(template, language, catalogs[language], path, page, summary, index, report),
                              encoding="utf-8")
            urls.append(SITE_URL + folder(language) + path)
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{html.escape(u)}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")
    host = urlparse(SITE_URL).hostname or ""
    if host and not host.endswith("github.io"):
        (out / "CNAME").write_text(host + "\n", encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"build_site: {len(urls)} pages, {', '.join(summary) or 'no data'}, {total / 1e6:.1f} MB in {out}")


if __name__ == "__main__":
    main()
