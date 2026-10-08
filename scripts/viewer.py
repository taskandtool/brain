#!/usr/bin/env python3
"""The brain as a website: Quartz over brain/, brand/, public/, legal/ and
raw/, with search, backlinks, a graph, and every citation a link to its
source. Standard library only; runs from any directory.

    python3 scripts/viewer.py install          # Quartz and its plugins, once
    python3 scripts/viewer.py dev              # serve it, rebuilt on every change
    python3 scripts/viewer.py build            # the static site in dist/
    python3 scripts/viewer.py check [--all]    # links that point nowhere, citations that are not links

`install` puts Quartz outside the app (QUARTZ_DIR, default
~/.local/share/company-brain/quartz-<tag>) and prints "already installed"
when it is. `dev` is the web service's command: it installs if needed, then
serves on $PORT (3000). `build` writes dist/, leaves out any file Cloudflare
will not take, and ends with what `check` found; it fails, and removes dist/,
if Quartz built without all its plugins. Who can see production is the
platform's setting, never this script's. `check` reads brain/, brand/,
public/ and legal/ and exits 1 while anything needs fixing, naming the link
to write instead.

The viewer's look is viewer/quartz.config.yaml (colours, fonts, panels);
its plugins are pinned in viewer/quartz.lock.json.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import unquote, urlparse

from cli import MAX_LISTED, ROOT, Misuse, Parser, fail

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
BRIDGE = "python3 ~/tools/taskandtool.py"
DEV_RETRY_PAUSE = 60
# What the viewer never serves: the crawler's data and cache, and anything a
# browser would run as a page or script on the viewer's own address, in any
# letter case. SVGs from raw/ too, since one opened directly runs its script;
# brand/ keeps the owner's logos.
NEVER_SERVED = ("json", "jsonl", "html", "htm", "shtml", "xhtml", "xht", "xml", "xsl",
                "xslt", "js", "mjs", "cjs", "mht", "mhtml")
NEVER_SERVED_FROM_RAW = ("svg", "svgz")


def any_case(ext):
    """`svg` as a glob that matches it in any letter case: [sS][vV][gG]."""
    return "".join(f"[{c.lower()}{c.upper()}]" if c.isalpha() else c for c in ext)


# The same list as Quartz globs, its config's ignorePatterns.
LEFT_OUT = (["**/_cache/**"] + [f"**/*.{any_case(e)}" for e in NEVER_SERVED]
            + [f"raw/**/*.{any_case(e)}" for e in NEVER_SERVED_FROM_RAW])


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


# Quartz and its plugins depend on two packages fetched from GitHub at pinned
# commits, which npm 12 refuses unless allowed.
NPM_ENV = {"npm_config_allow_git": "all"}


def run(args, cwd, what, try_cmd=f"{CMD} install"):
    """Run a command quietly; on failure raise with the end of its output.
    Returns stdout and stderr together."""
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env={**os.environ, **NPM_ENV})
    except FileNotFoundError:
        raise Failed(f"{what} failed: {args[0]} is not installed", [], try_cmd)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()[-12:]
        raise Failed(f"{what} failed", tail, try_cmd)
    return r.stdout + r.stderr


def pinned_lock():
    """viewer/quartz.lock.json: the community plugins pinned by commit."""
    with open(os.path.join(VIEWER, "quartz.lock.json")) as f:
        return json.load(f)


def lock_text():
    """Our pinned plugins plus the local safe-text plugin, as Quartz's lock."""
    lock = pinned_lock()
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


def production_host(bridge=BRIDGE):
    """Production's host name from the bridge, or None off the platform or
    before there is one: link previews need it as an absolute address."""
    try:
        r = subprocess.run(bridge_cmd(bridge, "status", "--json"),
                           capture_output=True, text=True, timeout=30)
        url = json.loads(r.stdout or "{}").get("production_url") or ""
    except (OSError, ValueError, AttributeError, subprocess.TimeoutExpired):
        return None
    return urlparse(url).hostname or None


def config_text(base_url=None):
    """viewer/quartz.config.yaml with the local plugin's path filled in, the
    business's name as the title while the title is the default, and
    `base_url` (production's host, for a build) as the address link previews
    name."""
    with open(os.path.join(VIEWER, "quartz.config.yaml")) as f:
        text = f.read()
    if base_url:
        text = re.sub(r"^(\s*baseUrl:).*$", lambda m: f"{m.group(1)} {base_url}", text, count=1, flags=re.M)
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


# Fixes to the pinned Quartz, applied at every install: (file, the text as
# shipped, what it becomes).
QUARTZ_PATCHES = [
    # Quartz 5.0.0 stores a generated folder page's rendered listing as its
    # content, then renders the listing again, so every folder showed its
    # list twice.
    ("quartz/plugins/pageTypes/dispatcher.ts",
     "      ve.tree.children = htmlAst.children\n      ve.vfile.data.htmlAst = htmlAst\n",
     "      ve.vfile.data.htmlAst = htmlAst\n"),
    # Its dev server checks each changed note against Quartz's own .gitignore,
    # which lists public/ (its build output), so edits under the brain's
    # public/ never showed in dev. Checked against the content folder, as
    # the first build already is.
    ("quartz/build.ts",
     "  const gitIgnoredMatcher = await isGitIgnored()\n",
     "  const gitIgnoredMatcher = await isGitIgnored({ cwd: argv.directory })\n"),
]


def patch_quartz():
    for name, shipped, fixed in QUARTZ_PATCHES:
        path = os.path.join(QUARTZ_DIR, name)
        with open(path) as f:
            text = f.read()
        if shipped in text:
            with open(path, "w") as f:
                f.write(text.replace(shipped, fixed, 1))
        elif fixed not in text:
            raise Failed(f"Quartz {QUARTZ_TAG} is not the code the viewer patches: {name}", [],
                         f"move {QUARTZ_DIR} aside, then {CMD} install")


class quartz_lock:
    """Quartz's folder for one command at a time: an install, a dev start's
    staging, a build. Whoever waits says so, then waits. The lock goes with
    the process, so a crash or a sleep that kills it never leaves it held."""

    def __enter__(self):
        os.makedirs(os.path.dirname(QUARTZ_DIR), exist_ok=True)
        self.file = open(QUARTZ_DIR + ".lock", "w")
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("viewer: waiting for another viewer command (the web service's first "
                  "install takes minutes)", flush=True)
            fcntl.flock(self.file, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        self.file.close()


def install():
    """Quartz at QUARTZ_TAG, its npm packages and the pinned plugins.
    Returns True when something was installed, False when all was there."""
    with quartz_lock():
        return _install()


def plugins_missing():
    """The pinned plugins not in place, safe-text included: Quartz's plugin
    install exits 0 with some failed, and a build without safe-text would
    render raw/'s HTML."""
    names = list(pinned_lock()["plugins"])
    plugins = os.path.join(QUARTZ_DIR, ".quartz", "plugins")
    missing = [n for n in names if not os.path.isfile(os.path.join(plugins, n, "package.json"))]
    link = os.path.join(plugins, "safe-text")
    if os.path.realpath(link) != os.path.realpath(os.path.join(VIEWER, "safe-text")):
        missing.append("safe-text")
    return missing


def _install():
    major = node_major()
    if major is None or major < 22:
        found = f"Node {major}" if major else "no Node"
        raise Failed(f"Quartz needs Node 22 or newer; found {found}", [],
                     "nvm install 22 && nvm alias default 22")
    did = False
    if not os.path.isdir(os.path.join(QUARTZ_DIR, ".git")):
        if os.path.exists(QUARTZ_DIR):
            # Not something this script made: say so rather than delete it.
            raise Failed(f"{QUARTZ_DIR} is there but is not a Quartz clone", [],
                         f"move it aside, then {CMD} install")
        # Cloned beside it and renamed into place, so a clone cut off by a
        # sleep or a replacement never leaves a half Quartz that looks whole.
        # Only the .partial folder, this step's own, is ever removed.
        partial = QUARTZ_DIR + ".partial"
        shutil.rmtree(partial, ignore_errors=True)
        run(["git", "-c", "advice.detachedHead=false", "clone", "--quiet", "--depth", "1",
             "--branch", QUARTZ_TAG, QUARTZ_REPO, partial], ROOT, f"cloning Quartz {QUARTZ_TAG}")
        os.rename(partial, QUARTZ_DIR)
        did = True
    # Written only after `npm ci` succeeds, so a half-finished install is redone.
    packages = os.path.join(QUARTZ_DIR, "node_modules", ".company-brain-installed")
    if not os.path.exists(packages):
        run(["npm", "ci", "--no-audit", "--no-fund", "--loglevel=error"], QUARTZ_DIR,
            "installing Quartz's packages")
        open(packages, "w").close()
        did = True
    patch_quartz()
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
    if have != want or plugins_missing():
        run(["npx", "quartz", "plugin", "install"], QUARTZ_DIR, "installing Quartz's plugins")
        missing = plugins_missing()
        if missing:
            raise Failed(f"Quartz's plugin install left out {', '.join(missing)}", [],
                         f"{CMD} install")
        with open(stamp, "w") as f:
            f.write(want + "\n")
        did = True
    return did


def plugin_count():
    return len(pinned_lock()["plugins"]) + 1          # safe-text is the one more


# ---------------------------------------------------------------- staging

def home_page():
    """The home page: the way in. Every row has a page from the first start,
    since each folder ships with a file (brain/SCHEMA.md, and a README.md in
    brand/, public/ and raw/), so neither a fresh brain nor the dev server's
    page written once at its start ever links to nothing."""
    title = business_name() or DEFAULT_TITLE
    return "\n".join([
        "---", f"title: {json.dumps(title)}", "---", "",
        "- [Notes](brain/): everything the brain knows, cited; the overview first",
        "- [Brand](brand/): look, voice, logo and photos",
        "- [Published facts](public/): details, services, hours, team and reviews",
        "- [Raw material](raw/): the site as crawled, documents and transcripts",
    ]) + "\n"


def stage(content, base_url=None):
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
    write_if_changed(os.path.join(QUARTZ_DIR, "quartz.config.yaml"), config_text(base_url))


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


# Quartz goes on building when a plugin fails to load, and says so only here.
PLUGIN_FAILED = re.compile(r"Failed to (install|load|instantiate) plugin|Could not determine category")


def build():
    """The site in dist/: (pages, files kept, files dropped, production's
    host or None)."""
    # A build is for production: its link previews name production's address.
    host = production_host()
    dist = os.path.join(ROOT, "dist")
    # Held from install to the end of the build: the config and dist/ are
    # shared with the dev server's start and with any other build.
    with quartz_lock():
        _install()
        stage(BUILD_CONTENT, host)
        out = run(["npx", "quartz", "build", "-d", BUILD_CONTENT, "-o", dist], QUARTZ_DIR,
                  "the Quartz build", f"{CMD} check, then fix the note the build output names")
    failed = [line.strip() for line in out.splitlines() if PLUGIN_FAILED.search(line)]
    if failed:
        # Without its plugins (safe-text above all) the site must not ship.
        shutil.rmtree(dist, ignore_errors=True)
        raise Failed("the Quartz build ran without all its plugins; dist/ removed", failed[:5],
                     f"{CMD} install")
    kept, dropped = prune(dist)
    pages = sum(1 for _d, _s, names in os.walk(dist) for n in names if n.endswith(".html"))
    return pages, kept, dropped, host


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
            elif rel(dest).split("/")[0] not in FOLDERS:
                out.append((n, f"{target} is outside what the viewer shows ({', '.join(FOLDERS)})", None))
            elif left_out(rel(dest)):
                out.append((n, f"{target} is a file the viewer leaves out", None))
        for m in BARE.finditer(LINK.sub("", line)):
            cited = m.group(0)
            link = os.path.relpath(os.path.join(ROOT, cited), here).replace(os.sep, "/")
            name = os.path.splitext(os.path.basename(cited))[0] or cited
            out.append((n, f"{cited} is a path, not a link", f"[{name}]({link})"))
    return out


def left_out(path):
    """Whether the viewer leaves out an app-relative path: the same rule as
    LEFT_OUT, by lowercased extension."""
    parts = path.split("/")
    ext = os.path.splitext(parts[-1])[1].lower().lstrip(".")
    return ("_cache" in parts[:-1] or ext in NEVER_SERVED
            or (parts[0] == "raw" and ext in NEVER_SERVED_FROM_RAW))


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


def build_report(pages, kept, dropped, host):
    """The build's summary lines: the first is `viewer build: …`."""
    lines = [f"viewer build: {pages} pages and {kept - pages} other files in dist/"]
    if not host:
        lines.append("  production's address is not known here, so link previews name localhost; "
                     f"{BRIDGE} status shows it once there is one")
    for path, size in dropped:
        lines.append(f"  left out, over Cloudflare's 25 MiB a file: {path} ({size_mb(size)})")
    if kept > MAX_FILES:
        lines.append(f"  {kept} files: Cloudflare may refuse a deploy of more than {MAX_FILES:,}")
    return lines


def bridge_cmd(bridge, *args):
    """The bridge command line, `~` expanded in each word."""
    return [os.path.expanduser(w) for w in shlex.split(bridge)] + list(args)


def main(argv):
    ap = Parser(prog="viewer.py", description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="{install,dev,build,check}")
    sub.add_parser("install", help="Quartz and its plugins, outside the app; safe to re-run")
    sub.add_parser("dev", help="serve the viewer on $PORT (3000), rebuilt on every change (the web service)")
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
            port = os.environ.get("PORT") or "3000"
            if not str(port).isdigit():
                fail("viewer dev", f"PORT is {port!r}, not a number", [], f"PORT=3000 {CMD} dev")
                return 2
            if not os.path.isdir(os.path.join(QUARTZ_DIR, ".quartz")):
                print(f"viewer dev: installing Quartz {QUARTZ_TAG} first; minutes on a machine", flush=True)
            try:
                # Released before the exec: the dev server must not hold it.
                with quartz_lock():
                    _install()
                    stage(DEV_CONTENT)
            except Failed as e:
                # The service manager restarts this at once; a pause keeps a
                # failing install (GitHub or npm unreachable) from looping.
                fail("viewer dev", str(e), e.lines, e.try_cmd)
                time.sleep(DEV_RETRY_PAUSE)
                return 1
            print(f"viewer dev: serving brain/, brand/, public/, legal/ and raw/ on port {port}, "
                  "rebuilt on every change", flush=True)
            os.chdir(QUARTZ_DIR)
            os.environ.update(NPM_ENV)
            try:
                os.execvp("npx", ["npx", "quartz", "build", "--serve", "--port", str(port),
                                  "--wsPort", str(free_port()), "-d", DEV_CONTENT])
            except FileNotFoundError:
                raise Failed("npx is not installed", [], "node --version")

        if args.cmd == "build":
            lines = build_report(*build())
            findings = check()
            if findings:
                lines.append("  " + check_report(findings)[0])
                lines.append(f"\nNext: {CMD} check")
            else:
                lines.append(f"\nNext: {BRIDGE} status (dev shows the same pages)")
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
