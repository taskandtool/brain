#!/usr/bin/env python3
"""What changed in raw/ since the brain last ingested it. The one script the
AI, the Stop hook, and a scheduled job all call — deterministic, stdlib only.

    python3 brain_status.py status            # JSON: new / changed / removed raw files
    python3 brain_status.py mark [--all|paths] # record raw files as ingested
    python3 brain_status.py hook-stop         # Claude Code Stop hook (reads stdin)

State: brain/.ingested.json maps each raw file path to the sha256 of its
content at ingest time. `status` diffs raw/ against it. Run from the app
dir (the hook passes $CLAUDE_PROJECT_DIR).

The Stop hook implements Karpathy's "ingest when a source is added" without
the human having to say so: when the agent tries to end its turn while
un-ingested raw files exist, the hook blocks once and hands back the list,
so the agent integrates them first. It never blocks twice in a row
(`stop_hook_active`), so it can't loop.
"""
import hashlib
import json
import os
import sys

RAW = "raw"
MANIFEST = os.path.join("brain", ".ingested.json")
SKIP_DIRS = {"images", "__pycache__"}
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
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if name.startswith((".", "_")):        # _manifest.json, _common.md, dotfiles
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
    per unit): the owner's whole site is one unit; each external site is one;
    every document, transcript, or other file is its own."""
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == RAW and parts[1] == "web":
        return "website"
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
    return diff(raw_files(), load_manifest())


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


def hook_stop(stdin_text):
    """Claude Code Stop hook: block the turn once with the pending list.
    Returns (stdout_text, exit_code). Pure given the stdin payload and the
    status."""
    try:
        payload = json.loads(stdin_text or "{}")
    except ValueError:
        payload = {}
    if payload.get("stop_hook_active"):
        return "", 0                       # already continuing from us: never loop
    if not os.path.isdir(RAW):
        return "", 0
    d = status()
    if not d["new"] and not d["changed"]:
        return "", 0
    reason = (
        "Brain: " + summarize(d) +
        ". Ingest them now with the brain-distill skill (read them, fold the facts into "
        "brain/ notes, cross-link, update brain/index.md and brain/log.md, then run "
        "`python3 .claude/skills/brain-distill/brain_status.py mark --all` and publish). "
        "If the owner explicitly asked you not to, say so and stop."
    )
    return json.dumps({"decision": "block", "reason": reason}), 0


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
    if cmd == "hook-stop":
        project = os.environ.get("CLAUDE_PROJECT_DIR")
        if project and os.path.isdir(project):
            os.chdir(project)
        out, code = hook_stop(sys.stdin.read())
        if out:
            print(out)
        return code
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
