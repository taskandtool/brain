#!/usr/bin/env python3
"""What changed in raw/ since the brain last ingested it. The one script the
AI and a scheduled job call — deterministic, stdlib only.

    python3 brain_status.py status            # JSON: new / changed / removed raw files
    python3 brain_status.py mark [--all|paths] # record raw files as ingested

State: brain/.ingested.json maps each raw file path to the sha256 of its
content at ingest time. `status` diffs raw/ against it. Run from the app
dir.
"""
import hashlib
import json
import os
import sys

RAW = "raw"
MANIFEST = os.path.join("brain", ".ingested.json")
# Pictures are looked at, not ingested one file at a time (visual-identity.md
# reads them through _index/media.json and the screenshots), and a crawl's
# own ledger and cache (_index/, _cache/) are the crawler's, not sources.
SKIP_DIRS = {"images", "shots", "videos", "__pycache__"}
MAX_LISTED = 15


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def raw_files(root=RAW):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith((".", "_"))]
        for name in filenames:
            if name.startswith((".", "_")):        # _sites.json, _latest.json, dotfiles
                continue
            path = os.path.join(dirpath, name).replace(os.sep, "/")
            out[path] = sha(path)
    return out


def load_manifest(path=MANIFEST):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_manifest(data, path=MANIFEST):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(dict(sorted(data.items())), f, indent=1)


def unit_of(path):
    """The source unit a raw file belongs to (the brain keeps one source page
    per unit): each of the owner's sites (raw/site/<host>) is one unit; each
    external site is one; every document, transcript, or other file is its own."""
    parts = path.split("/")
    if len(parts) >= 4 and parts[0] == RAW and parts[1] == "site":
        return "site:" + parts[2]
    if len(parts) >= 4 and parts[0] == RAW and parts[1] == "external":
        return "external:" + parts[2]
    return path


def diff(current, ingested):
    """Pure: {new, changed, removed} sorted lists, plus `units`: per source
    unit, how many files are new/changed (what an ingest pass is about)."""
    new = sorted(p for p in current if p not in ingested)
    changed = sorted(p for p in current if p in ingested and ingested[p] != current[p])
    removed = sorted(p for p in ingested if p not in current)
    units = {}
    for kind, paths in (("new", new), ("changed", changed)):
        for p in paths:
            u = units.setdefault(unit_of(p), {"new": 0, "changed": 0})
            u[kind] += 1
    return {"new": new, "changed": changed, "removed": removed, "units": units}


def status():
    current = raw_files()
    # A file ingested before it was skipped (a 0.1.3 screenshot) is still on
    # disk: not removed, just no longer ingest work.
    ingested = {p: h for p, h in load_manifest().items() if p in current or not os.path.exists(p)}
    return diff(current, ingested)


def summarize(d):
    pending = d["new"] + d["changed"]
    if not pending and not d["removed"]:
        return ""
    listed = pending[:MAX_LISTED]
    more = len(pending) - len(listed)
    parts = []
    if d["new"]:
        parts.append(f"{len(d['new'])} new")
    if d["changed"]:
        parts.append(f"{len(d['changed'])} changed")
    if d["removed"]:
        parts.append(f"{len(d['removed'])} removed")
    text = ", ".join(parts) + " raw file(s) not yet ingested into brain/"
    units = d.get("units") or {}
    if units:
        text += " — units: " + ", ".join(
            f"{u} ({v['new']} new, {v['changed']} changed)" for u, v in sorted(units.items()))
    if listed:
        text += ": " + ", ".join(listed) + (f" (+{more} more)" if more else "")
    return text


def mark(paths=None):
    current = raw_files()
    ingested = load_manifest()
    if paths is None:
        ingested = current
    else:
        for p in paths:
            p = p.replace(os.sep, "/")
            if p in current:
                ingested[p] = current[p]
        for p in list(ingested):
            if p not in current:
                del ingested[p]
    save_manifest(ingested)
    return len(ingested)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        d = status()
        print(json.dumps(d))
        s = summarize(d)
        if s:
            sys.stderr.write(s + "\n")
        return 0
    if cmd == "mark":
        rest = argv[2:]
        n = mark(None if not rest or rest == ["--all"] else rest)
        print(json.dumps({"ingested": n}))
        return 0
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
