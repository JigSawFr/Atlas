"""Games alike by what the eShop says of them, for the games Wikidata knows
nothing of (most of the eShop's small games): each game's words (its name,
intro and description), its categories and its publisher, weighed by how
rare they are (tf-idf), compared as a cosine.

To stay quick over twenty thousand games in plain Python, a game keeps only
its TERMS weightiest words, and a word shared by more than MAX_SHARED games
says too little to compare by: what is left is compared through an index
of who has each word.
"""
import math
import re

TERMS = 24            # a game's weightiest words kept
MAX_SHARED = 250      # games a word may be shared by, at most, to count
KEEP = 10             # the games kept as like each one, by its words
FLOOR = 25            # a likeness by words below this (1..100) is not kept
WORD = re.compile(r"[a-z][a-z'-]{2,}")
STOP = set("""
the and for you your with from that this are can will all its into out new more one two who what when where which
their them they have has his her our not but get just also over than then very even each every any some much many
most other such only own same both few how why way make made use play game games player players switch nintendo
mode modes world time take takes taking set sets let lets like need needs including include includes feature
features available now online up off about after before again against while through during under above below
featuring experience enjoy fun friends friend new full first last best great well together way ways able every
""".split())


def words_of(text):
    out = []
    for w in WORD.findall((text or "").lower()):
        w = w.strip("'-")
        if len(w) < 3 or w in STOP:
            continue
        if w.endswith("s") and not w.endswith("ss") and len(w) > 4:
            w = w[:-1]
        out.append(w)
    return out


def terms_of(entry):
    """A titledb entry's terms and how many times each: its name's words count
    three times, its categories and publisher are terms of their own."""
    counts = {}

    def add(term, n=1.0):
        counts[term] = counts.get(term, 0.0) + n

    for w in words_of(entry.get("name")):
        add(w, 3)
    for w in words_of(entry.get("intro")):
        add(w, 1.5)
    for w in words_of(entry.get("description")):
        add(w)
    for c in entry.get("category") or []:
        if isinstance(c, str) and c:
            add("category:" + c.lower(), 3)
    publisher = entry.get("publisher")
    if isinstance(publisher, str) and publisher and publisher != "None":
        add("publisher:" + publisher.lower(), 2)
    return counts


def similar(titles, base_id, keep=KEEP):
    """{title id: [[title id, 1..100], ...]} from titledb's entries, the most alike first."""
    docs = {}
    for entry in titles.values():
        tid = base_id(entry.get("id"))
        if not tid or tid in docs or entry.get("isDemo") in (True, "True"):
            continue
        counts = terms_of(entry)
        if counts:
            docs[tid] = counts
    n = max(len(docs), 1)
    df = {}
    for counts in docs.values():
        for t in counts:
            df[t] = df.get(t, 0) + 1
    vectors = {}
    for tid, counts in docs.items():
        weighted = []
        for t, c in counts.items():
            if df[t] < 2 or df[t] > MAX_SHARED:
                continue
            weighted.append(((1 + math.log(c)) * math.log(n / df[t]), t))
        weighted.sort(reverse=True)
        top = weighted[:TERMS]
        norm = math.sqrt(sum(w * w for w, _ in top))
        if norm > 0:
            vectors[tid] = {t: w / norm for w, t in top}
    holders = {}
    for tid, vec in vectors.items():
        for t, w in vec.items():
            holders.setdefault(t, []).append((tid, w))
    out = {}
    for tid, vec in vectors.items():
        scores = {}
        for t, w in vec.items():
            for other, w2 in holders[t]:
                if other != tid:
                    scores[other] = scores.get(other, 0.0) + w * w2
        best = sorted(((s, o) for o, s in scores.items() if round(s * 100) >= FLOOR), reverse=True)[:keep]
        if best:
            out[tid] = [[o, round(s * 100)] for s, o in best]
    return dict(sorted(out.items()))


def merged(by_traits, by_text, keep=12, text_share=0.8):
    """Each game's alike from its traits first, then from its words (a word
    match counts a little less than a trait match): the best of both."""
    out = {}
    for tid in set(by_traits) | set(by_text):
        best = {}
        for other, s in by_traits.get(tid, []):
            best[other] = max(best.get(other, 0), s)
        for other, s in by_text.get(tid, []):
            best[other] = max(best.get(other, 0), round(s * text_share))
        ranked = sorted(((s, o) for o, s in best.items() if s > 0), key=lambda x: (-x[0], x[1]))[:keep]
        if ranked:
            out[tid] = [[o, s] for s, o in ranked]
    return dict(sorted(out.items()))
