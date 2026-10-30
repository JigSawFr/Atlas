"""Compares two runs' data files: each file the same, else how many games differ."""
import json
import os
import sys

old, new = sys.argv[1], sys.argv[2]
names = set()
for base in (old, new):
    for root, _, files in os.walk(base):
        for f in files:
            if f.endswith(".json") and "/sources" not in root:
                names.add(os.path.relpath(os.path.join(root, f), base))
same = 0
lines = []
for name in sorted(names):
    try:
        a = open(os.path.join(old, name), "rb").read()
        b = open(os.path.join(new, name), "rb").read()
    except OSError:
        lines.append(f"| `{name}` | only in {'new' if not os.path.exists(os.path.join(old, name)) else 'old'} |")
        continue
    if a == b:
        same += 1
        continue
    ja, jb = json.loads(a), json.loads(b)
    ga, gb = ja.get("games") or {}, jb.get("games") or {}
    keys = set(ga) | set(gb)
    diff = [k for k in keys if ga.get(k) != gb.get(k)]
    other = [k for k in set(ja) | set(jb) if k != "games" and ja.get(k) != jb.get(k)]
    fields = {}
    for k in diff:
        a, b = ga.get(k), gb.get(k)
        if isinstance(a, dict) and isinstance(b, dict):
            for f in set(a) | set(b):
                if a.get(f) != b.get(f):
                    fields[f] = fields.get(f, 0) + 1
        else:
            fields["(whole entry)"] = fields.get("(whole entry)", 0) + 1
    lines.append(f"| `{name}` | {len(diff)} of {len(keys)} games differ{', fields: ' + ', '.join(other) if other else ''} |"
                 + (f" e.g. {sorted(diff)[:3]}; by field: {dict(sorted(fields.items()))}" if diff else ""))
    for k in sorted(diff)[:2]:
        print(f"{name} {k}\n  old: {json.dumps(ga.get(k))[:400]}\n  new: {json.dumps(gb.get(k))[:400]}", file=sys.stderr)
print(f"{same} files the same byte for byte, {len(lines)} not\n")
if lines:
    print("| File | Difference |\n|---|---|")
    print("\n".join(lines))
