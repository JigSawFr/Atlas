#!/usr/bin/env python3
"""The data files' JSON Schemas (draft 2020-12), published under schemas/
on the data branch, a schema a file at the same path
(schemas/platforms/switch/popular.schema.json for
platforms/switch/popular.json), and every file checked against its own
before it is published.

The check is this module's, plain Python, for the part of JSON Schema the
schemas use: type, const, enum, required, properties, additionalProperties,
propertyNames, items, prefixItems, minItems, maxItems, minimum, maximum,
pattern, anyOf and $ref to $defs.

Usage:
  tools/schemas.py check <data-dir>     every file checked, the wrong ones said (exit 1)
  tools/schemas.py publish <data-dir>   the same; a wrong file put back as it was on the
                                        branch (or removed when new), said in the run's
                                        alerts; then schemas/ written again
"""
import json
import os
import re
import subprocess
import sys

import common

DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
DAY = {"type": "integer", "minimum": 0, "maximum": 99991231}
HEAD = {"schema": {"const": common.SCHEMA}, "generated": DATE, "source": {"type": "string"}, "platform": {"type": "string"},
        "license": {"type": "string"}, "part": {"type": "integer"}, "parts": {"type": "integer"}}
TRAIT = {"type": "array", "prefixItems": [{"type": "string"}, {"type": "string"}], "minItems": 2, "maxItems": 2}
TRAITS = {"type": "array", "items": {"anyOf": [TRAIT, {"type": "integer"}]}}
MONEY = {"type": "number", "minimum": 0}


def file_schema(title, games, required=("schema", "generated", "games"), extra=None, key="games"):
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": title, "type": "object",
            "required": list(required), "properties": {**HEAD, **(extra or {}), key: {"type": "object",
                                                                                     "additionalProperties": games}}}


KINDS = {
    "popular": file_schema("A platform's games' renown: [score 0..100, trend -100..999, critics 0..100]", {
        "type": "array", "minItems": 3, "maxItems": 3, "prefixItems": [
            {"type": "integer", "minimum": 0, "maximum": 100}, {"type": "integer", "minimum": -100, "maximum": 999},
            {"type": "integer", "minimum": 0, "maximum": 100}]},
        extra={"month": {"type": "string"}, "views": {"type": "boolean"}, "trends": DATE}),
    "games": file_schema("A platform's games: name, Wikidata item, release, reviews, traits", {
        "type": "object", "properties": {
            "name": {"type": "string"}, "qid": {"type": "string", "pattern": r"^Q\d+$"}, "release": DAY,
            "slug": {"type": "string"}, "pack": {"type": "boolean"}, "coming_soon": {"type": "boolean"},
            "reviews": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
            "rating": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
            "igdb_rating": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
            "gamepass": {"type": "array", "items": {"enum": ["console", "pc"]}},
            "platforms": {"type": "array", "items": TRAIT},
            "series": TRAITS, "developers": TRAITS, "publishers": TRAITS, "genres": TRAITS, "modes": TRAITS,
            "tags": TRAITS, "themes": TRAITS, "keywords": TRAITS, "perspectives": TRAITS,
            "steam": {"type": "object", "required": ["app"], "properties": {
                "app": {"type": "integer"}, "positive": {"type": "integer", "minimum": 0},
                "negative": {"type": "integer", "minimum": 0}, "owners": {"type": "integer", "minimum": 0},
                "ccu": {"type": "integer", "minimum": 0}}}}},
        extra={"tags": {"type": "object", "additionalProperties": {"type": "string"}}}),
    "similar": file_schema("Each game's most alike: [[id, 1..100]]", {
        "type": "array", "items": {"type": "array", "minItems": 2, "maxItems": 2, "prefixItems": [
            {"type": "string"}, {"type": "integer", "minimum": 1, "maximum": 100}]}}),
    "upcoming": file_schema("The games still to come: [YYYYMMDD, name] (or with IGDB's hypes)", {
        "type": "array", "minItems": 2, "maxItems": 3, "prefixItems": [DAY, {"type": "string"}, {"type": "integer"}]}),
    "editions": file_schema("An edition's game: {edition id: game id}", {"type": "string"}),
    "names": file_schema("Every game's name: {id: name}", {"type": "string"}),
    "gamepass": file_schema("The Game Pass's games: {id: [console, pc]}", {
        "type": "array", "items": {"enum": ["console", "pc"]}}),
    "prices": file_schema("A country's prices: [regular, sale, until, lowest, lowest_day(, lowest_30)]", {
        "type": "array", "minItems": 5, "maxItems": 6, "prefixItems": [MONEY, MONEY, DAY, MONEY, DAY, MONEY]},
        required=("schema", "generated", "country", "games"),
        extra={"country": {"type": "string", "pattern": "^[A-Z]{2}$"}, "currency": {"type": "string"}, "since": DATE}),
    "links": file_schema("Each game's ids on every platform, by Wikidata item", {
        "type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}}),
    "platforms": file_schema("The platforms' registry", {
        "type": "object", "required": ["name", "kind"], "properties": {
            "name": {"type": "string"}, "qid": {"type": "string", "pattern": r"^Q\d+$"}, "igdb": {"type": "string"},
            "aurore": {"type": "string"}, "kind": {"enum": ["store", "console", "retro"]}}}, key="platforms",
        required=("schema", "generated", "platforms")),
    "index": {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Every file", "type": "object",
              "required": ["schema", "files"], "properties": {"schema": {"const": common.SCHEMA}, "files": {
                  "type": "object", "additionalProperties": {"type": "object", "required": ["bytes", "sha256"],
                                                             "properties": {"generated": {"type": "string"},
                                                                            "bytes": {"type": "integer"},
                                                                            "source": {"type": "string"},
                                                                            "license": {"type": "string"},
                                                                            "attribution": {"type": "string"},
                                                                            "sha256": {"type": "string",
                                                                                       "pattern": "^[0-9a-f]{16}$"}}}}}},
    "report": {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "How the data is", "type": "object",
               "required": ["schema", "generated", "sources", "platforms"],
               "properties": {"schema": {"const": common.SCHEMA}, "generated": DATE, "run": {"enum": ["build", "daily"]},
                              "source": {"type": "string"},
                              "sources": {"type": "object", "additionalProperties": {
                                  "type": "object", "required": ["files", "records", "generated"]}},
                              "platforms": {"type": "object", "additionalProperties": {
                                  "type": "object", "required": ["games", "linked", "priced", "reviewed"],
                                  "properties": {"linked": {"type": "number", "minimum": 0, "maximum": 1},
                                                 "priced": {"type": "number", "minimum": 0, "maximum": 1},
                                                 "reviewed": {"type": "number", "minimum": 0, "maximum": 1}}}},
                              "steps": {"type": "object", "additionalProperties": {"type": "number"}}}},
    "source": {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "A source's answers, as collected",
               "type": "object", "required": ["schema", "generated", "source", "license"],
               "properties": {**HEAD, "schema": {"const": common.SOURCE_SCHEMA}, "source_id": {"type": "string"},
                              "rows": {"type": "array", "items": {"type": "object",
                                                                  "additionalProperties": {"type": "string"}}},
                              "games": {"type": "object"}, "items": {}, "pages": {"type": "object"}}},
}


def kind_of(path):
    """The kind of a data file, by its path on the branch (None: not a data file)."""
    if path.startswith("sources/"):
        return "source"
    if path in ("links.json", "platforms.json", "index.json", "report.json"):
        return path[:-5]
    m = re.match(r"^platforms/[a-z0-9-]+/(prices/[A-Z]{2}|popular|games|similar|upcoming|editions|names|gamepass)\.json$",
                 path)
    if m:
        return "prices" if m.group(1).startswith("prices/") else m.group(1)
    return None


def schema_path(path):
    """schemas/<path without .json>.schema.json, or for a source cut in parts its whole file's."""
    path = re.sub(r"/\d+\.json$", ".json", path) if path.startswith("sources/") else path
    return "schemas/" + path[:-len(".json")] + ".schema.json"


def errors(value, schema, root=None, where="$"):
    """What is wrong with `value` against `schema`, as messages (none: right)."""
    root = root or schema
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return errors(value, root["$defs"][name], root, where)
    out = []
    kind = schema.get("type")
    if kind:
        kinds = kind if isinstance(kind, list) else [kind]
        ok = any(_is(value, k) for k in kinds)
        if not ok:
            return [f"{where}: not {'/'.join(kinds)}"]
    if "const" in schema and value != schema["const"]:
        out.append(f"{where}: not {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{where}: {value!r} not one of {schema['enum']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{where}: {value} below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{where}: {value} above {schema['maximum']}")
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        out.append(f"{where}: {value[:40]!r} not {schema['pattern']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            out.append(f"{where}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(f"{where}: more than {schema['maxItems']} items")
        first = schema.get("prefixItems") or []
        for i, item in enumerate(value):
            sub = first[i] if i < len(first) else schema.get("items")
            if sub is not None:
                out += errors(item, sub, root, f"{where}[{i}]")
                if len(out) > 20:
                    return out
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                out.append(f"{where}: no {name}")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        names = schema.get("propertyNames")
        for name, item in value.items():
            if names is not None:
                out += errors(name, names, root, f"{where}.<{name}>")
            if name in props:
                out += errors(item, props[name], root, f"{where}.{name}")
            elif extra is False:
                out.append(f"{where}: {name} not expected")
            elif isinstance(extra, dict):
                out += errors(item, extra, root, f"{where}.{name}")
            if len(out) > 20:
                return out
    if "anyOf" in schema and not any(not errors(value, s, root, where) for s in schema["anyOf"]):
        out.append(f"{where}: none of anyOf")
    return out


def _is(value, kind):
    return {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
            "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
            "null": lambda v: v is None,
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)}[kind](value)


def data_files(directory):
    """The branch's data files, as paths relative to it, schemas/ left out."""
    out = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (root == directory and d == "schemas"))
        for f in sorted(files):
            if f.endswith(".json"):
                out.append(os.path.relpath(os.path.join(root, f), directory).replace(os.sep, "/"))
    return out


def check(directory):
    """{path: [messages]} of the wrong files."""
    wrong = {}
    for path in data_files(directory):
        kind = kind_of(path)
        if not kind:
            continue
        try:
            with open(os.path.join(directory, path), encoding="utf-8") as f:
                body = json.load(f)
        except (OSError, ValueError) as e:
            wrong[path] = [f"not JSON: {e}"]
            continue
        found = errors(body, KINDS[kind])
        if found:
            wrong[path] = found
    return wrong


def write(directory):
    """schemas/ written again: a schema at each data file's path."""
    for path in data_files(directory):
        kind = kind_of(path)
        if not kind:
            continue
        target = os.path.join(directory, schema_path(path))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump({**KINDS[kind], "$id": f"https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/{schema_path(path)}"},
                      f, ensure_ascii=False, indent=1)
            f.write("\n")


def put_back(directory, path):
    """A wrong file as the branch had it (git), or removed when it is new."""
    if subprocess.run(["git", "-C", directory, "checkout", "HEAD", "--", path], capture_output=True).returncode:
        os.remove(os.path.join(directory, path))


def main():
    what, directory = sys.argv[1], sys.argv[2]
    wrong = check(directory)
    for path, found in wrong.items():
        print(f"::error::{path}: " + "; ".join(found[:5]), file=sys.stderr)
    if what == "check":
        sys.exit(1 if wrong else 0)
    for path in wrong:
        put_back(directory, path)
        if os.environ.get("ALERTS"):
            with open(os.environ["ALERTS"], "a", encoding="utf-8") as f:
                f.write(f"`{path}` did not match its schema ({wrong[path][0]}): the last run's was kept.\n")
    write(directory)
    print(f"schemas: {len(wrong)} wrong files put back" if wrong else "schemas: every file right", file=sys.stderr)


if __name__ == "__main__":
    main()
