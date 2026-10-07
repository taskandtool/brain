#!/usr/bin/env python3
"""What changed in raw/ since the brain last distilled it, and marking what
has been distilled. Standard library only; runs from any directory.

    python3 scripts/brain_status.py status [<path> …] [--all] [--json]
    python3 scripts/brain_status.py mark <path> [<path> …]
    python3 scripts/brain_status.py mark --all

`status` prints a summary, then the pending source units (a site folder, a
document) as paths; exit 1 while anything is pending, 0 when nothing is.
With paths (a section of a site: raw/site/<host>/pages/services-*.md), it
counts and lists only the files under them.
`mark` records every raw file at or under each path as distilled; a path
that is gone from raw/ is recorded as removed.

State: brain/.ingested.json maps each raw file path to the sha256 of its
content when it was marked. Pictures, screenshots and the crawler's own
_index/ and _cache/ are never pending.
"""
import argparse
import hashlib
import json
import os
import sys

from cli import Misuse, Parser, fail

# the app root: this file is <root>/scripts/brain_status.py
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CMD = "python3 scripts/brain_status.py"
# Pictures are looked at, not distilled one file at a time (visual-identity.md
# reads them through _index/media.json and the screenshots), and a crawl's
# own ledger and cache (_index/, _cache/) are the crawler's, not sources.
SKIP_DIRS = {"images", "shots", "videos", "__pycache__"}
MAX_LISTED = 15


def manifest_path():
    return os.path.join(ROOT, "brain", ".ingested.json")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def raw_files():
    """{"raw/…": sha256} for every raw file that is distill work."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "raw")):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith((".", "_"))]
        for name in filenames:
            if name.startswith((".", "_")):        # _sites.json, _latest.json, dotfiles
                continue
            full = os.path.join(dirpath, name)
            out[os.path.relpath(full, ROOT).replace(os.sep, "/")] = sha(full)
    return out


def load_manifest():
    try:
        with open(manifest_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_manifest(data):
    path = manifest_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(dict(sorted(data.items())), f, indent=1)


def unit_of(path):
    """The source unit a raw file belongs to (the brain keeps one source page
    per unit), as the path to mark it by: each of the owner's sites
    (raw/site/<host>) and each external site is one folder, and so is each
    social profile with its posts (raw/social/<platform>/<handle>); every
    document, transcript, listing, or other file is its own."""
    parts = path.split("/")
    if len(parts) >= 4 and parts[0] == "raw" and parts[1] in ("site", "external"):
        return "/".join(parts[:3])
    if len(parts) >= 5 and parts[0] == "raw" and parts[1] == "social":
        return "/".join(parts[:4])
    return path


def diff(current, ingested):
    """Pure: {new, changed, removed} sorted lists, plus `units`: per source
    unit, how many files are new/changed (what a distill pass is about)."""
    new = sorted(p for p in current if p not in ingested)
    changed = sorted(p for p in current if p in ingested and ingested[p] != current[p])
    removed = sorted(p for p in ingested if p not in current)
    units = {}
    for kind, paths in (("new", new), ("changed", changed)):
        for p in paths:
            u = units.setdefault(unit_of(p), {"new": 0, "changed": 0})
            u[kind] += 1
    return {"new": new, "changed": changed, "removed": removed, "units": units}


def under(path, prefixes):
    return any(path == x or path.startswith(x.rstrip("/") + "/") for x in prefixes)


def status(prefixes=None):
    """The diff, or only the files under `prefixes` ("raw/…") when given."""
    current = raw_files()
    # A file marked before it was skipped (a 0.1.3 screenshot) is still on
    # disk: not removed, just no longer distill work.
    ingested = {p: h for p, h in load_manifest().items()
                if p in current or not os.path.exists(os.path.join(ROOT, p))}
    if prefixes is not None:
        current = {p: h for p, h in current.items() if under(p, prefixes)}
        ingested = {p: h for p, h in ingested.items() if under(p, prefixes)}
    return diff(current, ingested)


def summarize(d, show_all=False, scope=None):
    """The status report: a summary line, then the pending units (or, with
    show_all or a scope, every pending file), capped at MAX_LISTED."""
    pending = d["new"] + d["changed"]
    where = f" under {', '.join(scope)}" if scope else ""
    if not pending and not d["removed"]:
        return f"brain_status status: nothing pending{where}" + ("" if scope else "; every raw file is distilled")
    parts = []
    if d["new"]:
        parts.append(f"{len(d['new'])} new")
    if d["changed"]:
        parts.append(f"{len(d['changed'])} changed")
    head = "brain_status status: "
    if parts:
        head += ", ".join(parts) + f" raw file(s){where} not yet distilled into brain/"
    if d["removed"]:
        head += ("; " if parts else "") + f"{len(d['removed'])} raw file(s){where} removed since they were distilled"
    lines = [head]
    if show_all or scope:
        rows = [f"new      {p}" for p in d["new"]] + [f"changed  {p}" for p in d["changed"]] + \
               [f"removed  {p}" for p in d["removed"]]
    else:
        rows = [f"{u}  ({v['new']} new, {v['changed']} changed)" for u, v in sorted(d["units"].items())]
        gone = {}
        for p in d["removed"]:
            gone[unit_of(p)] = gone.get(unit_of(p), 0) + 1
        rows += [f"{u}  ({n} removed)" for u, n in sorted(gone.items())]
    shown = rows if show_all else rows[:MAX_LISTED]
    lines += ["  " + r for r in shown]
    if len(rows) > len(shown):
        lines.append(f"  {len(rows) - len(shown)} more: " + " ".join([CMD, "status", *(scope or []), "--all"]))
    if pending:
        lines.append(f"\nNext: distill each unit (the brain skill), then {CMD} mark <path>")
    else:
        lines.append(f"\nNext: retire what the brain cites from them (the brain skill), then {CMD} mark <path>")
    return "\n".join(lines)


def resolve(arg):
    """A path argument (relative to the working directory or the app root,
    or absolute) as an app-relative "raw/…" prefix, or None outside raw/.
    It may be gone from disk: a removed file is marked by its old path."""
    cands = [os.path.abspath(arg), os.path.abspath(os.path.join(ROOT, arg))]
    rels = [os.path.relpath(c, ROOT).replace(os.sep, "/") for c in cands]
    inside = [(c, r) for c, r in zip(cands, rels) if r == "raw" or r.startswith("raw/")]
    for c, r in inside:
        if os.path.exists(c):
            return r
    return inside[-1][1] if inside else None


def mark(paths=None):
    """Record the raw files at or under `paths` (every raw file when None) as
    distilled, and forget the files there that are gone from raw/. Returns
    (marked, unchanged, removed) counts; raises ValueError naming a path
    that holds no raw files, present or removed."""
    current = raw_files()
    manifest = load_manifest()
    gone = [p for p in manifest if p not in current and not os.path.exists(os.path.join(ROOT, p))]
    if paths is None:
        chosen, forget = list(current), gone
    else:
        chosen, forget = [], []
        for arg in paths:
            prefix = resolve(arg)
            hits = [p for p in current if prefix and under(p, [prefix])]
            lost = [p for p in gone if prefix and under(p, [prefix])]
            if not hits and not lost:
                raise ValueError(arg)
            chosen += hits
            forget += lost
    # a file marked before it was skipped (a picture) is dropped quietly
    ingested = {p: h for p, h in manifest.items() if p in current or (p in gone and p not in forget)}
    marked = unchanged = 0
    for p in set(chosen):
        if ingested.get(p) == current[p]:
            unchanged += 1
        else:
            ingested[p] = current[p]
            marked += 1
    save_manifest(ingested)
    return marked, unchanged, len(set(forget))


def main(argv):
    as_json = "--json" in argv
    ap = Parser(prog="brain_status.py", description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="{status,mark}")
    st = sub.add_parser("status", help="what in raw/ is not yet distilled (exit 1 while anything is)")
    st.add_argument("paths", nargs="*", help="only the files at or under these (a section of a site)")
    st.add_argument("--all", action="store_true", help="list every pending file, not the units")
    st.add_argument("--json", action="store_true", help="the full diff as JSON (for a live check)")
    mk = sub.add_parser("mark", help="record raw files as distilled")
    mk.add_argument("paths", nargs="*", help="files or folders under raw/; every file under a folder is marked")
    mk.add_argument("--all", action="store_true", help="mark every raw file")
    try:
        args = ap.parse_args(argv)
    except Misuse as e:
        cmd = argv[0] if argv and argv[0] in ("status", "mark") else None
        fail("brain_status" + (f" {cmd}" if cmd else ""), str(e), [] if cmd else ["Commands: status, mark"],
             f"{CMD} {cmd + ' ' if cmd else ''}--help", as_json)
        return 2

    if args.cmd == "status":
        scope = None
        if args.paths:
            scope = [resolve(a) for a in args.paths]
            known = list(raw_files()) + list(load_manifest())
            for arg, prefix in zip(args.paths, scope):
                if not prefix or not any(under(p, [prefix]) for p in known):
                    fail("brain_status status", f"no raw files at or under {arg}",
                         ["Paths are files or folders under raw/."], f"{CMD} status", as_json)
                    return 2
        d = status(scope)
        print(json.dumps(d) if args.json else summarize(d, args.all, scope))
        return 1 if d["new"] or d["changed"] or d["removed"] else 0

    if args.all == bool(args.paths):
        fail("brain_status mark", "give the paths you distilled, or --all, not both or neither",
             try_cmd=f"{CMD} mark raw/site/<host>")
        return 2
    try:
        marked, unchanged, removed = mark(None if args.all else args.paths)
    except ValueError as e:
        fail("brain_status mark", f"no raw files at or under {e}, on disk or removed; nothing was marked",
             ["Paths are files or folders under raw/ (pictures and _index/ are never pending)."],
             f"{CMD} status")
        return 2
    what = "every raw file" if args.all else ", ".join(args.paths)
    print(f"brain_status mark: {marked} raw file(s) marked distilled ({what})"
          + (f"; {removed} removed from raw/ recorded as removed" if removed else "")
          + (f"; {unchanged} already marked, left alone" if unchanged else ""))
    print(f"\nNext: {CMD} status")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
