#!/usr/bin/env python3
"""The brain as a website: Quartz over brain/, brand/, public/, legal/ and
raw/, with search, backlinks, a graph, and every citation a link to its
source. Standard library only; runs from any directory.

    python3 scripts/viewer.py install          # Quartz and its plugins, once
    python3 scripts/viewer.py dev [--port N]   # serve it, rebuilt on every change
    python3 scripts/viewer.py build            # the static site in dist/
    python3 scripts/viewer.py check [--all]    # links that point nowhere, citations that are not links

`install` puts Quartz outside the app (QUARTZ_DIR, default
~/.local/share/company-brain/quartz-<tag>) and prints "already installed"
when it is. `dev` is the web service's command: it installs if needed, then
serves on $PORT (3000). `build` writes dist/, leaves out any file Cloudflare
will not take, and ends with what `check` found. `check` reads brain/,
brand/, public/ and legal/ and exits 1 while anything needs fixing, naming
the link to write instead.

The viewer's look is viewer/quartz.config.yaml (colours, fonts, panels);
its plugins are pinned in viewer/quartz.lock.json.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from urllib.parse import unquote

from cli import Misuse, Parser, fail

# the app root: this file is <root>/scripts/viewer.py
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CMD = "python3 scripts/viewer.py"
VIEWER = os.path.join(ROOT, "viewer")
QUARTZ_TAG = "v5.0.0"
QUARTZ_REPO = "https://github.com/jackyzha0/quartz.git"
QUARTZ_DIR = os.environ.get("QUARTZ_DIR") or os.path.expanduser(
    f"~/.local/share/company-brain/quartz-{QUARTZ_TAG}")
# Quartz's content folders sit beside its clone, not in it: the build skips
# whatever the nearest git repository ignores, and Quartz's own .gitignore
# lists public/. One for the dev server, one for builds, so a deploy never
# rearranges what the running dev server watches.
DEV_CONTENT = os.path.join(os.path.dirname(QUARTZ_DIR), "content")
BUILD_CONTENT = os.path.join(os.path.dirname(QUARTZ_DIR), "content-build")
FOLDERS = ("brain", "brand", "public", "legal", "raw")
NOTE_FOLDERS = ("brain", "brand", "public", "legal")
DEFAULT_TITLE = "Company Brain"
MAX_ASSET = 25 * 1024 * 1024      # Cloudflare's limit on one static file
MAX_FILES = 20_000                # and on the files in one deploy
MAX_LISTED = 15
# What the viewer never serves, as Quartz globs (its config's ignorePatterns):
# the crawler's data and cache, and anything a browser would run as a page
# or script on the viewer's own address. Raw SVGs too, since one opened
# directly runs its script; brand/ keeps the owner's logos.
LEFT_OUT = ["**/*.json", "**/*.jsonl", "**/_cache/**", "**/*.html", "**/*.htm",
            "**/*.xhtml", "**/*.xml", "**/*.js", "**/*.mjs", "raw/**/*.svg"]


class Failed(Exception):
    """A step that did not work: the message, its detail lines, the Try: line."""

    def __init__(self, msg, lines=(), try_cmd=None):
        super().__init__(msg)
        self.lines, self.try_cmd = list(lines), try_cmd


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


# ---------------------------------------------------------------- install

def node_major():
    try:
        out = subprocess.run(["node", "-p", "process.versions.node"], capture_output=True, text=True)
        return int(out.stdout.split(".")[0])
    except (OSError, ValueError):
        return None


def run(args, cwd, what, try_cmd=f"{CMD} install"):
    """Run a command quietly; on failure raise with the end of its output.
    Quartz and its plugins depend on two packages fetched from GitHub at
    pinned commits, which npm 12 refuses unless allowed."""
    env = {**os.environ, "npm_config_allow_git": "all"}
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)
    except FileNotFoundError:
        raise Failed(f"{what} failed: {args[0]} is not installed", [], try_cmd)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()[-12:]
        raise Failed(f"{what} failed", tail, try_cmd)
    return r.stdout


def lock_text():
    """Our pinned plugins plus the local safe-text plugin, as Quartz's lock."""
    with open(os.path.join(VIEWER, "quartz.lock.json")) as f:
        lock = json.load(f)
    path = os.path.join(VIEWER, "safe-text")
    lock["plugins"]["safe-text"] = {"source": path, "resolved": path, "commit": "local"}
    return json.dumps(lock, indent=2) + "\n"


def business_name():
    """public/business.md's `name:`, once it is filled in."""
    try:
        with open(os.path.join(ROOT, "public", "business.md")) as f:
            text = f.read()
    except OSError:
        return None
    front = text.split("---", 2)[1] if text.startswith("---") else ""
    m = re.search(r"""^name:\s*(?:"([^"]*)"|'([^']*)'|([^#\n]*?))\s*(?:#.*)?$""", front, re.M)
    name = next((g for g in m.groups() if g is not None), "").strip() if m else ""
    return name if name and name != "to fill" else None


def config_text():
    """viewer/quartz.config.yaml with the local plugin's path filled in, and
    the business's name as the title while the title is the default."""
    with open(os.path.join(VIEWER, "quartz.config.yaml")) as f:
        text = f.read()
    text = text.replace("@SAFE_TEXT@", os.path.join(VIEWER, "safe-text"))
    text = text.replace('"@LEFT_OUT@"', json.dumps(LEFT_OUT))
    name = business_name()
    if name:
        text = re.sub(rf"^(\s*pageTitle:)\s*{DEFAULT_TITLE}\s*$",
                      lambda m: f"{m.group(1)} {json.dumps(name)}", text, flags=re.M)
    return text


def write_if_changed(path, text):
    try:
        with open(path) as f:
            if f.read() == text:
                return
    except OSError:
        pass
    with open(path, "w") as f:
        f.write(text)


def install():
    """Quartz at QUARTZ_TAG, its npm packages and the pinned plugins.
    Returns True when something was installed, False when all was there."""
    major = node_major()
    if major is None or major < 22:
        found = f"Node {major}" if major else "no Node"
        raise Failed(f"Quartz needs Node 22 or newer; found {found}", [],
                     "nvm install 22 && nvm alias default 22")
    did = False
    if not os.path.isdir(os.path.join(QUARTZ_DIR, ".git")):
        os.makedirs(os.path.dirname(QUARTZ_DIR), exist_ok=True)
        shutil.rmtree(QUARTZ_DIR, ignore_errors=True)
        run(["git", "-c", "advice.detachedHead=false", "clone", "--quiet", "--depth", "1",
             "--branch", QUARTZ_TAG, QUARTZ_REPO, QUARTZ_DIR], ROOT, f"cloning Quartz {QUARTZ_TAG}")
        did = True
    # Written only after `npm ci` succeeds, so a half-finished install is redone.
    packages = os.path.join(QUARTZ_DIR, "node_modules", ".company-brain-installed")
    if not os.path.exists(packages):
        run(["npm", "ci", "--no-audit", "--no-fund", "--loglevel=error"], QUARTZ_DIR,
            "installing Quartz's packages")
        open(packages, "w").close()
        did = True
    lock = lock_text()
    write_if_changed(os.path.join(QUARTZ_DIR, "quartz.lock.json"), lock)
    write_if_changed(os.path.join(QUARTZ_DIR, "quartz.config.yaml"), config_text())
    stamp = os.path.join(QUARTZ_DIR, ".quartz", "company-brain.stamp")
    want = hashlib.sha256(lock.encode()).hexdigest()
    try:
        with open(stamp) as f:
            have = f.read().strip()
    except OSError:
        have = None
    # The local plugin is a link to this app; one left by another app's
    # folder (a removed checkout) points nowhere, and Quartz stops on it.
    link = os.path.join(QUARTZ_DIR, ".quartz", "plugins", "safe-text")
    if os.path.islink(link) and os.path.realpath(link) != os.path.realpath(os.path.join(VIEWER, "safe-text")):
        os.unlink(link)
        have = None
    if have != want:
        run(["npx", "quartz", "plugin", "install"], QUARTZ_DIR, "installing Quartz's plugins")
        with open(stamp, "w") as f:
            f.write(want + "\n")
        did = True
    return did


def plugin_count():
    with open(os.path.join(VIEWER, "quartz.lock.json")) as f:
        return len(json.load(f)["plugins"]) + 1


# ---------------------------------------------------------------- staging

def home_page():
    """The home page: the way in. Every row exists from the first start
    (stage makes the folders), so the dev server never shows a stale one."""
    title = business_name() or DEFAULT_TITLE
    return "\n".join([
        "---", f"title: {json.dumps(title)}", "---", "",
        "- [Overview](brain/overview.md): the business on one page",
        "- [Notes](brain/): everything the brain knows, cited",
        "- [Brand](brand/): look, voice, logo and photos",
        "- [Published facts](public/): details, services, hours, team and reviews",
        "- [Raw material](raw/): the site as crawled, documents and transcripts",
    ]) + "\n"


def stage(content):
    """`content` as links to the app's folders, plus the home page. Each
    folder is made if missing, so one that fills later is watched."""
    os.makedirs(content, exist_ok=True)
    for name in os.listdir(content):
        path = os.path.join(content, name)
        if os.path.islink(path) or not os.path.isdir(path):
            os.unlink(path)
        else:
            shutil.rmtree(path)
    for folder in FOLDERS:
        source = os.path.join(ROOT, folder)
        os.makedirs(source, exist_ok=True)
        os.symlink(source, os.path.join(content, folder))
    with open(os.path.join(content, "index.md"), "w") as f:
        f.write(home_page())
    write_if_changed(os.path.join(QUARTZ_DIR, "quartz.config.yaml"), config_text())


# ---------------------------------------------------------------- build

def prune(dist):
    """Remove what Cloudflare will not take; returns (files kept, dropped)."""
    kept, dropped = 0, []
    for dirpath, _dirs, names in os.walk(dist):
        for name in names:
            path = os.path.join(dirpath, name)
            size = os.path.getsize(path)
            if size > MAX_ASSET:
                os.unlink(path)
                dropped.append((os.path.relpath(path, dist), size))
            else:
                kept += 1
    return kept, sorted(dropped)


def build():
    install()
    stage(BUILD_CONTENT)
    dist = os.path.join(ROOT, "dist")
    run(["npx", "quartz", "build", "-d", BUILD_CONTENT, "-o", dist], QUARTZ_DIR, "the Quartz build",
        f"{CMD} check, then fix the note the build output names")
    kept, dropped = prune(dist)
    pages = sum(1 for _d, _s, names in os.walk(dist) for n in names if n.endswith(".html"))
    return pages, kept, dropped


# ---------------------------------------------------------------- check

LINK = re.compile(r"!?\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*<?([^)\s>]*)>?(?:\s+[\"'][^)]*[\"'])?\s*\)")
BARE = re.compile(r"(?<![\w/.%-])raw/[\w./%~+-]*\w")
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def body_lines(text):
    """(line number, text) for each line outside the frontmatter and code."""
    lines = text.split("\n")
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    fenced = False
    for i in range(start, len(lines)):
        line = lines[i]
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not fenced:
            yield i + 1, re.sub(r"`[^`]*`", "", line)


def check_file(path):
    """Findings for one note: (line, what is wrong, what to write)."""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    here = os.path.dirname(path)
    out = []
    for n, line in body_lines(text):
        for m in LINK.finditer(line):
            target = m.group(2)
            if not target or target.startswith("#") or SCHEME.match(target):
                continue
            if target.startswith("/"):
                out.append((n, f"{target} starts at /", "a path relative to this note"))
                continue
            dest = os.path.normpath(os.path.join(here, unquote(re.split(r"[#?]", target)[0])))
            if not dest.startswith(ROOT + os.sep) or not os.path.exists(dest):
                out.append((n, f"{target} points nowhere", None))
            elif left_out(rel(dest)):
                out.append((n, f"{target} is a file the viewer leaves out", None))
        for m in BARE.finditer(LINK.sub("", line)):
            cited = m.group(0)
            link = os.path.relpath(os.path.join(ROOT, cited), here).replace(os.sep, "/")
            name = os.path.splitext(os.path.basename(cited))[0] or cited
            out.append((n, f"{cited} is a path, not a link", f"[{name}]({link})"))
    return out


def left_out(path):
    """Whether an app-relative path matches LEFT_OUT."""
    return any(fnmatch.fnmatch(path, g.replace("**/", "*/").replace("/**", "/*"))
               for g in LEFT_OUT)


def check():
    findings = []
    for folder in NOTE_FOLDERS:
        for dirpath, dirs, names in os.walk(os.path.join(ROOT, folder)):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for name in sorted(names):
                if name.endswith(".md"):
                    path = os.path.join(dirpath, name)
                    findings += [(rel(path), *f) for f in check_file(path)]
    return findings


def check_report(findings, show_all=False):
    if not findings:
        return ["viewer check: every link in brain/, brand/, public/ and legal/ resolves, "
                "and every citation is a link"]
    broken = sum(1 for f in findings if "is a path" not in f[2])
    bare = len(findings) - broken
    parts = ([f"{broken} link(s) point nowhere"] if broken else []) + \
            ([f"{bare} citation(s) are bare paths"] if bare else [])
    lines = ["viewer check: " + " and ".join(parts) + " in brain/, brand/, public/ and legal/"]
    shown = findings if show_all else findings[:MAX_LISTED]
    for path, n, what, write in shown:
        lines.append(f"  {path}:{n}  {what}" + (f"; write {write}" if write else ""))
    if len(findings) > len(shown):
        lines.append(f"  {len(findings) - len(shown)} more: {CMD} check --all")
    return lines


# ---------------------------------------------------------------- main

def free_port():
    """A port nothing holds. Quartz's dev server also opens a live-reload
    socket (3001 unless told), and dies when that port is taken; through the
    dev address the socket is never reached, so any free port will do."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def size_mb(n):
    return f"{n / (1024 * 1024):.0f} MiB"


def main(argv):
    ap = Parser(prog="viewer.py", description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="{install,dev,build,check}")
    sub.add_parser("install", help="Quartz and its plugins, outside the app; safe to re-run")
    dv = sub.add_parser("dev", help="serve the viewer, rebuilt on every change (the web service)")
    dv.add_argument("--port", type=int, help="default: $PORT, else 3000")
    sub.add_parser("build", help="the static site in dist/, ready to deploy")
    ck = sub.add_parser("check", help="links that point nowhere and citations that are not links")
    ck.add_argument("--all", action="store_true", help="list every finding")
    try:
        args = ap.parse_args(argv)
    except Misuse as e:
        cmd = argv[0] if argv and argv[0] in ("install", "dev", "build", "check") else None
        fail("viewer" + (f" {cmd}" if cmd else ""), str(e),
             [] if cmd else ["Commands: install, dev, build, check"],
             f"{CMD} {cmd + ' ' if cmd else ''}--help")
        return 2

    try:
        if args.cmd == "install":
            did = install()
            where = QUARTZ_DIR.replace(os.path.expanduser("~"), "~", 1)
            if did:
                print(f"viewer install: Quartz {QUARTZ_TAG} and its {plugin_count()} plugins in {where}")
            else:
                print(f"viewer install: Quartz {QUARTZ_TAG} already installed in {where}, left alone")
            print(f"\nNext: {CMD} build")
            return 0

        if args.cmd == "dev":
            port = args.port or os.environ.get("PORT") or "3000"
            if not str(port).isdigit():
                fail("viewer dev", f"PORT is {port!r}, not a number", [], f"PORT=3000 {CMD} dev")
                return 2
            install()
            stage(DEV_CONTENT)
            print(f"viewer dev: serving brain/, brand/, public/, legal/ and raw/ on port {port}, "
                  "rebuilt on every change", flush=True)
            os.chdir(QUARTZ_DIR)
            try:
                os.execvp("npx", ["npx", "quartz", "build", "--serve", "--port", str(port),
                                  "--wsPort", str(free_port()), "-d", DEV_CONTENT])
            except FileNotFoundError:
                raise Failed("npx is not installed", [], "node --version")

        if args.cmd == "build":
            pages, kept, dropped = build()
            lines = [f"viewer build: {pages} pages and {kept - pages} other files in dist/"]
            for path, size in dropped:
                lines.append(f"  left out, over Cloudflare's 25 MiB a file: {path} ({size_mb(size)})")
            if kept > MAX_FILES:
                lines.append(f"  {kept} files: Cloudflare may refuse a deploy of more than {MAX_FILES:,}")
            findings = check()
            if findings:
                lines.append("  " + check_report(findings)[0])
                lines.append(f"\nNext: {CMD} check")
            else:
                lines.append("\nNext: python3 ~/tools/taskandtool.py status (dev shows the same pages)")
            print("\n".join(lines))
            return 0

        findings = check()
        print("\n".join(check_report(findings, args.all)))
        if findings:
            print(f"\nNext: fix them, then {CMD} check")
        return 1 if findings else 0
    except Failed as e:
        fail(f"viewer {args.cmd}", str(e), e.lines, e.try_cmd)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
