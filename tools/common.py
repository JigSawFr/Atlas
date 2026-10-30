"""What every platform's build shares: asking a service for JSON (fetch) and
Wikidata's query service (sparql), a score's log scale, and publishing a
data file (publish) with its guard: a file that has lost too many games
against the last run's (a source down, not the world changed) is not
published, the last run's is kept and said. Also the lowest price a game
has had, day after day, weighed against the last run's file (with_lowest).
"""
import json
import math
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

AGENT = "Atlas/1.0 (https://github.com/JigSawFr/Atlas)"
SPARQL = "https://query.wikidata.org/sparql"
MAX_WAIT = 1800        # seconds a rate-limited service is waited for, at most
GUARD_KEEP = 0.7       # a file with fewer games than this share of the last run's is not published
GUARD_FLOOR = 50       # games the last run's file had at least, for that to count
# The data files' schema (README): a new field keeps it, a field changing
# meaning moves it up. A file of another schema is read as no file at all.
SCHEMA = 1
# The sources' files' schema: a new field keeps it, a field changing
# meaning moves it up; one of another schema is read as no file.
SOURCE_SCHEMA = 1
SOURCES = "sources"    # each source's answers, as collected (tools/collect.py)
SHARD_BYTES = 15_000_000   # a source file larger than this is cut in parts (jsDelivr serves 20 MB at most)


def fetch(url, tries=4, patient=True, timeout=120, data=None, headers=None):
    """`url`'s JSON answer; None for a 404. A 429 waits as long as the
    service says (`patient`) or is raised at once. `data` (bytes) makes it
    a POST."""
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, data=data, headers={
                "User-Agent": AGENT, "Accept": "application/json", **(headers or {})})
            with urllib.request.urlopen(request, timeout=timeout) as r:
                # Wikidata's labels may hold control characters, which strict JSON refuses.
                return json.loads(r.read(), strict=False)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == tries - 1 or (e.code == 429 and not patient):
                raise
            if e.code == 429:
                wait = max(int(e.headers.get("Retry-After", "60") or 60), 60) + 5
                if wait > MAX_WAIT:
                    raise
                print(f"{url.split('?')[0]}: rate-limited, again in {wait} s", file=sys.stderr)
                time.sleep(wait)
                continue
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == tries - 1:
                raise
        time.sleep(2 ** attempt)
    return None


def sparql(query):
    body = fetch(SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"}))
    return body["results"]["bindings"]


def scale(value, most):
    return math.log1p(value) / math.log1p(most) if most > 0 else 0.0


def write(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"{path}: {len(payload['games'])} games", file=sys.stderr)


def count_in(path):
    """How many games a data file has, None when there is no such file (or
    not one of ours, or of another schema)."""
    try:
        with open(path, encoding="utf-8") as f:
            body = json.load(f)
        if body.get("schema") != SCHEMA:
            return None
        games_of = body.get("games")
        return len(games_of) if isinstance(games_of, dict) else None
    except (OSError, ValueError, AttributeError):
        return None


def publish(out_dir, name, payload, previous_dir, report):
    """`payload` written as out_dir/name (name may be in a folder:
    steam/popular.json), unless it has lost too many games against the last
    run's (a source down, not the world changed): then the last run's file
    is kept, and said. Each file's line goes in `report`."""
    path = os.path.join(out_dir, name)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    now = len(payload["games"])
    before = count_in(os.path.join(previous_dir, name)) if previous_dir else None
    kept = before is not None and before >= GUARD_FLOOR and now < before * GUARD_KEEP
    if kept:
        shutil.copyfile(os.path.join(previous_dir, name), path)
        print(f"::warning::{name}: {now} games against {before} last time, last run's file kept", file=sys.stderr)
        # For the run's alert (tools/alert.sh), when the workflow asks for one.
        if os.environ.get("ALERTS"):
            with open(os.environ["ALERTS"], "a", encoding="utf-8") as f:
                f.write(f"`{name}` came out with {now} games against {before} last time: the last run's file was kept.\n")
    else:
        write(path, payload)
    report.append((name, before, now, kept))
    return not kept


def summary(report, path=None):
    """The run's files against the last run's, as a Markdown table (for the workflow's summary)."""
    lines = ["| File | Last run | This run | Published |", "|---|---:|---:|---|"]
    for name, before, now, kept in report:
        change = "" if not before else f" ({(now - before) * 100 / before:+.0f} %)"
        lines.append(f"| `{name}` | {before if before is not None else '–'} | {now}{change} | "
                     f"{'no: last run kept' if kept else 'yes'} |")
    text = "\n".join(lines) + "\n"
    path = path or os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("### The data files\n\n" + text)
    return text


def with_lowest(games, previous, today):
    """Each game's [regular, sale, until] row with its lowest price so far
    and that price's last day, from the last run's rows (`previous`, {} on a
    first run): [regular, sale, until, lowest, lowest_day]."""
    day = int(today.replace("-", ""))
    out = {}
    for tid, row in games.items():
        regular, sale, until = row[:3]
        now = sale or regular
        lowest, lowest_day = now, day
        last = previous.get(tid)
        if isinstance(last, list) and len(last) >= 5 and isinstance(last[3], (int, float)) and isinstance(last[4], int):
            if last[3] < now:
                lowest, lowest_day = last[3], last[4]
        out[tid] = [regular, sale, until, lowest, lowest_day]
    return out


def previous_file(previous_dir, name):
    """The last run's file `name` (in previous_dir), {} when there is none
    (or it is of another schema)."""
    try:
        with open(os.path.join(previous_dir, name), encoding="utf-8") as f:
            body = json.load(f)
        return body if body.get("schema") == SCHEMA else {}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def records_key(payload):
    """The key of a data file's records: "games" for a platform's, else a source's own."""
    for key in ("games", "rows", "pages", "items"):
        if key in payload:
            return key
    return None


def _parts(payload, key):
    """`payload` cut in parts of about SHARD_BYTES, each with every other field."""
    records = payload[key]
    items = list(records.items()) if isinstance(records, dict) else list(records)
    size = len(json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode())
    count = max(1, -(-size // SHARD_BYTES))
    if count == 1:
        return [payload]
    step = -(-len(items) // count)
    chunks = [items[i:i + step] for i in range(0, len(items), step)]
    out = []
    for n, chunk in enumerate(chunks, 1):
        part = {k: v for k, v in payload.items() if k != key}
        part.update({"part": n, "parts": len(chunks), key: dict(chunk) if isinstance(records, dict) else chunk})
        out.append(part)
    return out


def read_records(directory, name):
    """The source file `name` (sources/<source>/<file>.json) in `directory`,
    its parts put together when it was cut (sources/<source>/<file>/1.json…);
    None when there is none, or it is of another schema (README)."""
    whole = _read_records(directory, name)
    return whole if isinstance(whole, dict) and whole.get("schema") == SOURCE_SCHEMA else None


def _read_records(directory, name):
    path = os.path.join(directory, name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        pass
    folder = path[:-len(".json")]
    try:
        names = sorted((n for n in os.listdir(folder) if n.endswith(".json") and n[:-5].isdigit()),
                       key=lambda n: int(n[:-5]))
    except OSError:
        return None
    whole = None
    for n in names:
        try:
            with open(os.path.join(folder, n), encoding="utf-8") as f:
                part = json.load(f)
        except (OSError, ValueError):
            return None
        try:
            key = records_key(part)
            if whole is None:
                whole = {k: v for k, v in part.items() if k not in ("part", "parts")}
            elif isinstance(part[key], dict):
                whole[key].update(part[key])
            else:
                whole[key].extend(part[key])
        except (AttributeError, KeyError, TypeError):
            return None   # not one of ours
    return whole


def source(name, *directories):
    """A source file from the first of `directories` that has it (this run's
    collected files, then the last run's), {} when none does."""
    for directory in directories:
        if directory:
            found = read_records(directory, name)
            if found is not None:
                return found
    return {}


def publish_source(out_dir, name, payload, previous_dir, report):
    """A source's file written as out_dir/name, cut in parts when too large
    (read_records puts them together), unless it has lost too many records
    against the last run's: then the last run's is kept, and said."""
    key = records_key(payload)
    now = len(payload[key])
    last = read_records(previous_dir, name) if previous_dir else None
    before = len(last[records_key(last)]) if last and records_key(last) else None
    kept = before is not None and before >= GUARD_FLOOR and now < before * GUARD_KEEP
    if kept:
        payload = last
        print(f"::warning::{name}: {now} records against {before} last time, last run's kept", file=sys.stderr)
        if os.environ.get("ALERTS"):
            with open(os.environ["ALERTS"], "a", encoding="utf-8") as f:
                f.write(f"`{name}` came out with {now} records against {before} last time: the last run's was kept.\n")
    parts = _parts(payload, key)
    path = os.path.join(out_dir, name)
    if len(parts) == 1:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        _dump(path, parts[0])
    else:
        folder = path[:-len(".json")]
        os.makedirs(folder, exist_ok=True)
        for part in parts:
            _dump(os.path.join(folder, f"{part['part']}.json"), part)
    print(f"{name}: {now} records" + (f", {len(parts)} parts" if len(parts) > 1 else ""), file=sys.stderr)
    report.append((name, before, now, kept))
    return not kept


def _dump(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def rows_of(bindings):
    """A query's rows as a source keeps them: {variable: value}."""
    return [{k: v["value"] for k, v in b.items() if isinstance(v, dict) and "value" in v} for b in bindings]


def bindings(rows):
    """A source's rows back as the query's answer gave them (rows_of's reverse)."""
    return [{k: {"value": v} for k, v in r.items()} for r in rows]


def reader(*directories):
    """src(name): sources/<name> from the first of `directories` that has it."""
    return lambda name: source(f"{SOURCES}/{name}", *directories)


def collected_today(src, name, today):
    """A source file collected today, {} when it is an older run's (a
    collection that failed today: nothing made from the last run's)."""
    found = src(name)
    day = today if isinstance(today, str) else today.isoformat()
    return found if found.get("generated") == day else {}
