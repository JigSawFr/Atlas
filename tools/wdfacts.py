"""What Wikidata says of a game that the stores do not (site/README.md): its official site, its age
ratings, who directed it, wrote it and made its music, its engine, its trailers on YouTube and its
PCGamingWiki page. One query for each property or group of properties (the service answers in
seconds that way, and a failed one costs only its own file, which the last run's replaces).

Each query gives {qid, p, label or v} for the games with a platform (P400):

    sources/wikidata/facts-age.json      P908 PEGI, P852 ESRB, P853 CERO, P914 USK (labels)
    sources/wikidata/facts-people.json   P57 director, P86 composer, P58 screenwriter (labels)
    sources/wikidata/facts-engine.json   P408 engine (labels)
    sources/wikidata/facts-website.json  P856 official website
    sources/wikidata/facts-pcgw.json     P6337 PCGamingWiki id
    sources/wikidata/facts-youtube.json  P1651 YouTube video id

facts() reduces them to {qid: {"web": url, "pcgw": id, "yt": [ids], "age": [[system, value]],
"team": {"director": [names], "composer": […], "writer": […]}, "engine": [names]}}, a key left out
when there is nothing. Python's standard library only.
"""
import re

import common

PREFIXES = """PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""
# file -> (properties, whether the value is an item whose English label is wanted)
GROUPS = {
    "facts-age": (("P908", "P852", "P853", "P914"), True),
    "facts-people": (("P57", "P86", "P58"), True),
    "facts-engine": (("P408",), True),
    "facts-website": (("P856",), False),
    "facts-pcgw": (("P6337",), False),
    "facts-youtube": (("P1651",), False),
}
TEAM = {"P57": "director", "P86": "composer", "P58": "writer"}
NAMES = 3          # people kept for each role
VIDEOS = 3
ENGINES = 2


def query(properties, labels):
    """The query of a group: {qid, p, label} (or {qid, p, v}) of the games with a platform."""
    values = " ".join(f"wdt:{p}" for p in properties)
    pick = "?label" if labels else "?v"
    label = 'OPTIONAL { ?v rdfs:label ?label . FILTER(LANG(?label) = "en") }' if labels else ""
    return PREFIXES + f"""SELECT ?qid ?p {pick} WHERE {{
  VALUES ?prop {{ {values} }}
  ?item wdt:P400 [] .
  ?item ?prop ?v .
  {label}
  BIND(STRAFTER(STR(?item), "/entity/") AS ?qid)
  BIND(STRAFTER(STR(?prop), "/prop/direct/") AS ?p)
}}"""


def queries():
    """[(file, ask)] of the group queries, for the weekly collection."""
    return [(name, lambda props=props, labels=labels: common.sparql(query(props, labels)))
            for name, (props, labels) in GROUPS.items()]


QID = re.compile(r"^Q[0-9]+$")
VIDEO = re.compile(r"^[A-Za-z0-9_-]{11}$")
PCGW = re.compile(r"^[^\s/#?&]{1,120}$")
PEGI = re.compile(r"^PEGI (3|7|12|16|18)$")
USK = re.compile(r"^USK (0|6|12|16|18)$")
CERO = re.compile(r"^([ABCDZ])\b")
ESRB = {"early childhood": "EC", "everyone": "E", "everyone 10+": "E10+", "teen": "T", "mature 17+": "M",
        "adults only 18+": "AO", "adults only": "AO"}


def age(prop: str, label: str):
    """[system, value] of a rating's English label ("PEGI 12", "Everyone 10+", "B (Ages 12 and up)",
    "USK 6"), None when it is not one the sheet shows."""
    label = (label or "").strip()
    if prop == "P908":
        m = PEGI.match(label)
        return ["PEGI", m.group(1)] if m else None
    if prop == "P914":
        m = USK.match(label)
        return ["USK", m.group(1)] if m else None
    if prop == "P852":
        v = ESRB.get(label.lower())
        return ["ESRB", v] if v else None
    if prop == "P853":
        m = CERO.match(label)
        return ["CERO", m.group(1)] if m else None
    return None


def rows(src, name):
    """The rows of a file that are of a Wikidata item, in an order that does not depend on the service's."""
    found = [r for r in (src(name).get("rows") or []) if isinstance(r, dict) and QID.match(str(r.get("qid") or ""))]
    return sorted(found, key=lambda r: (int(r["qid"][1:]), str(r.get("p") or ""), str(r.get("label") or ""), str(r.get("v") or "")))


def facts(src) -> dict:
    """{qid: facts} from the sources the queries made; `src(name)` reads sources/<name>."""
    out = {}

    def put(qid, key, value, many=0, sub=None):
        slot = out.setdefault(qid, {})
        if sub:
            slot = slot.setdefault(key, {})
            key = sub
        if many:
            if value not in slot.setdefault(key, []) and len(slot[key]) < many:
                slot[key].append(value)
        else:
            slot.setdefault(key, value)

    for r in rows(src, "wikidata/facts-website.json"):
        url = str(r.get("v") or "")
        if url.startswith(("https://", "http://")) and " " not in url and len(url) <= 300:
            put(r["qid"], "web", url)
    for r in rows(src, "wikidata/facts-pcgw.json"):
        if PCGW.match(str(r.get("v") or "")):
            put(r["qid"], "pcgw", r["v"])
    for r in rows(src, "wikidata/facts-youtube.json"):
        if VIDEO.match(str(r.get("v") or "")):
            put(r["qid"], "yt", r["v"], many=VIDEOS)
    for r in rows(src, "wikidata/facts-age.json"):
        found = age(r.get("p"), r.get("label"))
        if found and found[0] not in [a[0] for a in out.get(r["qid"], {}).get("age", [])]:
            put(r["qid"], "age", found, many=4)
    for r in rows(src, "wikidata/facts-people.json"):
        role, label = TEAM.get(r.get("p")), str(r.get("label") or "").strip()
        if role and label and not QID.match(label):
            put(r["qid"], "team", label, many=NAMES, sub=role)
    for r in rows(src, "wikidata/facts-engine.json"):
        label = str(r.get("label") or "").strip()
        if label and not QID.match(label):
            put(r["qid"], "engine", label, many=ENGINES)
    return out
