#!/usr/bin/env python3
"""Crawl a website into a clean markdown corpus for the company brain.

Runs on the sprite (the AI drives it). Starting from one URL it discovers
every same-site page (the sitemap first, then every link on every page),
renders each one in the Obscura headless browser so JavaScript-built pages
and menus count, extracts the *content* as markdown with trafilatura, strips
the header/footer/nav lines that repeat across the site, pulls the content
images locally (deduped), drops duplicate pages, and writes everything under
the brain's raw/ layer:

    raw/web/<slug>.md        one file per page, images rewritten to relative paths
    raw/web/images/<hash>.<ext>
    raw/web/_common.md       the site-wide lines removed from every page (kept once)
    raw/web/_manifest.json   what was fetched, skipped, deduped, and the limit

    python3 brain_scrape.py <start_url> [--out raw/web] [--max-pages 100]
                            [--max-images 200] [--delay 0.5] [--static]
                            [--keep-boilerplate] [--ignore-robots] [--no-sitemap]

The page limit is deliberate and visible: the summary says how many pages
were found versus read, so the owner can be told and the limit raised.

Dependencies (installed by the brain kit's setup.sh, NOT base — base stays
stdlib+requests): trafilatura (Apache-2.0) and the Obscura binary. Without
Obscura (or with --static) pages are fetched as plain HTML.
"""
import argparse
import hashlib
import ipaddress
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib import robotparser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request

# trafilatura is imported lazily inside main() — the pure helpers below need no
# dependency, so they (and their tests) run on stdlib alone.

# ── Safety rails ──────────────────────────────────────────────────────────
MAX_IMAGE_BYTES = 15 * 1024 * 1024          # skip anything larger
IMAGE_CONTENT_TYPES = ("image/",)           # Content-Type allowlist
MIN_MARKDOWN_CHARS = 200                     # below this = thin/JS-rendered
USER_AGENT = "TaskAndTool-BrainScraper/1.0 (+https://taskandtool.com)"
RENDER_TIMEOUT_S = 60                        # hard cap on one browser render
OBSCURA_CANDIDATES = ("/usr/local/bin/obscura", os.path.expanduser("~/.local/bin/obscura"))
DEFAULT_MAX_PAGES = 100
MAX_SITEMAPS = 10
SKIP_EXTENSIONS = (".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4",
                   ".mp3", ".css", ".js", ".ico", ".xml", ".json", ".doc", ".docx", ".xls", ".xlsx")
TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref")


def is_public_host(host):
    # SSRF guard: the AI drives fetches from inside our infra, so refuse
    # anything that resolves to a private / loopback / link-local address.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return False
    return True


def same_site(url, root_host):
    return (urlsplit(url).hostname or "") == root_host


def normalize_url(url):
    """One canonical form per page: no fragment, no tracking params, no
    trailing slash on paths, so the same page isn't crawled twice."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return None
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(TRACKING_PARAMS)]
    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit((parts.scheme, (parts.hostname or "").lower(), path,
                       urlencode(query), ""))


def crawlable(url):
    path = urlsplit(url).path.lower()
    return not path.endswith(SKIP_EXTENSIONS)


class LinkParser(HTMLParser):
    """Collect <a href> links from HTML, to drive the same-site crawl."""

    def __init__(self, base_url):
        super().__init__()
        self.base = base_url
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(urljoin(self.base, a["href"].split("#")[0]))


def parse_sitemap(xml):
    """<loc> URLs from a sitemap or sitemap index (pure)."""
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)


# Images are pulled from the CONTENT markdown, not every <img> on the page —
# so we fetch only what the extracted content actually references (no nav
# icons/logos). MD_IMAGE_RE finds the URLs; MD_IMAGE_SUB rewrites them in place
# — matching the whole `![alt](url)` token (two groups: prefix, url) so we
# never over-replace a bare URL that appears inside another image or a link.
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
MD_IMAGE_SUB = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)")
SIZE_SUFFIX_RE = re.compile(r"(-\d{2,4}x\d{2,4}|@\dx|_\d{2,4}x\d{2,4}|-scaled)(?=\.[a-z0-9]{2,5}$)", re.I)


def image_key(url):
    """The identity of an image across its size/format variants: WordPress
    `-300x200` and `-scaled` suffixes, `@2x`, and query strings are dropped so
    one picture served five ways is fetched once."""
    parts = urlsplit(url)
    path = SIZE_SUFFIX_RE.sub("", parts.path)
    return (parts.hostname or "").lower() + path.lower()


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    """Re-run the SSRF check on every redirect hop — a public image URL must
    not 302 into a private/internal address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = urlsplit(newurl).hostname
        if not host or not is_public_host(host):
            raise urllib.error.URLError("redirect to non-public host blocked")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_GuardedRedirect())


def find_obscura(env=os.environ, which=shutil.which, exists=os.path.isfile):
    """The Obscura binary if installed: $OBSCURA_BIN, then PATH, then the two
    places setup.sh installs to. None means "no browser"."""
    explicit = env.get("OBSCURA_BIN")
    if explicit:
        return explicit if exists(explicit) else None
    found = which("obscura")
    if found:
        return found
    for cand in OBSCURA_CANDIDATES:
        if exists(cand):
            return cand
    return None


def render_html(url, binary, runner=subprocess.run, timeout=RENDER_TIMEOUT_S):
    """Fetch `url` through Obscura and return the rendered HTML, or None when
    the render fails, times out, or comes back empty. Obscura refuses private
    and internal addresses itself (no --allow-private-network here), so the
    SSRF rail holds on this path too."""
    cmd = [binary, "fetch", url, "--dump", "html", "--quiet", "--timeout", "30"]
    try:
        proc = runner(cmd, capture_output=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.decode("utf-8", "replace") if isinstance(proc.stdout, bytes) else (proc.stdout or "")
    return out if out.strip() else None


def rewrite_images(md, local_map):
    """Rewrite each `![alt](url)` whose url is in local_map to the local path,
    touching only the url inside an image tag (never a link, never a bare
    substring elsewhere)."""
    return MD_IMAGE_SUB.sub(
        lambda m: m.group(1) + local_map.get(m.group(2), m.group(2)), md
    )


def slugify(url):
    path = urlsplit(url).path.strip("/") or "index"
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    return (slug or "index")[:80]


def fetch_text(url, cap=2_000_000):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with _opener.open(req, timeout=30) as resp:
        return resp.read(cap).decode("utf-8", "replace")


def fetch_bytes(url, cap):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with _opener.open(req, timeout=30) as resp:
        ctype = resp.headers.get("Content-Type", "")
        if not ctype.startswith(IMAGE_CONTENT_TYPES):
            return None, ctype
        data = resp.read(cap + 1)
        if len(data) > cap:
            return None, ctype
        return data, ctype


def ext_for(url, ctype):
    for cand in (os.path.splitext(urlsplit(url).path)[1].lstrip("."), ctype.split("/")[-1]):
        if cand and re.fullmatch(r"[a-z0-9]{2,5}", cand.lower()):
            return cand.lower().replace("jpeg", "jpg")
    return "img"


def shingles(text, k=8):
    words = re.findall(r"\w+", text.lower())
    return {" ".join(words[i:i + k]) for i in range(max(len(words) - k + 1, 1))}


def near_duplicate(text, kept_shingle_sets, threshold=0.9):
    # Simple Jaccard at a single business's corpus scale (tens–hundreds of
    # pages). datasketch/MinHash-LSH is the escalation if a corpus gets large.
    s = shingles(text)
    for other in kept_shingle_sets:
        inter = len(s & other)
        union = len(s | other) or 1
        if inter / union >= threshold:
            return True, s
    return False, s


# ── Site-wide boilerplate ─────────────────────────────────────────────────

def _norm_line(line):
    return re.sub(r"\s+", " ", line.strip()).lower()


def boilerplate_threshold(n_pages):
    """A line is site furniture when it appears on at least this many pages:
    a third of the site, never fewer than 3 pages (so small sites still get
    their menu stripped, and a phrase two pages happen to share does not)."""
    return max(3, math.ceil(n_pages / 3))


def strip_common_lines(pages, threshold=None):
    """Remove the lines that repeat across the site — header menus, footer
    addresses, cookie notices, the logo image — from every page. Returns
    (cleaned_pages, common_lines) where common_lines keeps each removed line
    once, in first-seen order, so site-wide facts (the phone number in the
    footer) are not lost, just moved to one place. Pure. Needs ≥ 4 pages to
    have any opinion."""
    if len(pages) < 4:
        return list(pages), []
    threshold = threshold or boilerplate_threshold(len(pages))
    counts = {}
    first_seen = {}
    for md in pages:
        seen_here = set()
        for line in md.splitlines():
            key = _norm_line(line)
            if not key or key in seen_here or re.fullmatch(r"[-*_= ]+", key):
                continue
            seen_here.add(key)
            counts[key] = counts.get(key, 0) + 1
            first_seen.setdefault(key, line.strip())
    common = {k for k, c in counts.items() if c >= threshold}
    cleaned = []
    for md in pages:
        kept = [line for line in md.splitlines() if _norm_line(line) not in common]
        text = "\n".join(kept)
        text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
        cleaned.append(text)
    common_lines = [first_seen[k] for k in sorted(common, key=lambda k: list(first_seen).index(k))]
    return cleaned, common_lines


# ── The crawl ─────────────────────────────────────────────────────────────

def load_robots(start_url, ignore):
    rp = robotparser.RobotFileParser()
    if ignore:
        rp.parse(["User-agent: *", "Allow: /"])
        return rp, []
    parts = urlsplit(start_url)
    try:
        text = fetch_text(f"{parts.scheme}://{parts.netloc}/robots.txt", cap=200_000)
        rp.parse(text.splitlines())
        sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", text)
    except Exception:
        rp.parse(["User-agent: *", "Allow: /"])
        sitemaps = []
    return rp, sitemaps


def sitemap_urls(start_url, extra_sitemaps, root_host):
    """Every same-site page URL the site's sitemaps list (index files are
    followed, capped)."""
    parts = urlsplit(start_url)
    todo = [f"{parts.scheme}://{parts.netloc}/sitemap.xml"] + list(extra_sitemaps)
    seen, found = set(), []
    while todo and len(seen) < MAX_SITEMAPS:
        sm = todo.pop(0)
        if sm in seen or not same_site(sm, root_host):
            continue
        seen.add(sm)
        try:
            xml = fetch_text(sm)
        except Exception:
            continue
        for loc in parse_sitemap(xml):
            if loc.lower().endswith(".xml") and "sitemap" in loc.lower():
                todo.append(loc)
            elif same_site(loc, root_host):
                found.append(loc)
    return found


def main():
    import trafilatura

    ap = argparse.ArgumentParser()
    ap.add_argument("start_url")
    ap.add_argument("--out", default="raw/web")
    ap.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                    help=f"pages to read (default {DEFAULT_MAX_PAGES}; the summary says how many were found)")
    ap.add_argument("--max-images", type=int, default=200)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--static", "--no-render", action="store_true", dest="static",
                    help="plain HTML fetches only, never the browser")
    ap.add_argument("--keep-boilerplate", action="store_true",
                    help="keep the header/footer lines that repeat across pages")
    ap.add_argument("--ignore-robots", action="store_true")
    ap.add_argument("--no-sitemap", action="store_true")
    args = ap.parse_args()

    start = normalize_url(args.start_url)
    root_host = urlsplit(start or "").hostname or ""
    if not start or not root_host or not is_public_host(root_host):
        sys.stderr.write("refusing: start host is missing or not a public address\n")
        sys.exit(2)

    obscura = None if args.static else find_obscura()
    robots, robots_sitemaps = load_robots(start, args.ignore_robots)
    img_dir = os.path.join(args.out, "images")
    os.makedirs(img_dir, exist_ok=True)

    queue = [start]
    if not args.no_sitemap:
        for u in sitemap_urls(start, robots_sitemaps, root_host):
            n = normalize_url(u)
            if n and n not in queue:
                queue.append(n)
    discovered = set(queue)
    seen = set()
    kept = []                       # [{url, md, rendered}]
    kept_hashes, kept_shingles = set(), []
    manifest = {"start": start, "pages": [], "skipped": [], "images": 0,
                "renderer": obscura, "limit": args.max_pages, "limit_reached": False}

    def enqueue(links):
        for l in links:
            n = normalize_url(l)
            if n and same_site(n, root_host) and n not in discovered and crawlable(n):
                discovered.add(n)
                queue.append(n)

    while queue:
        if len(kept) >= args.max_pages:
            manifest["limit_reached"] = True
            break
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        if not robots.can_fetch(USER_AGENT, url):
            manifest["skipped"].append({"url": url, "reason": "robots"})
            continue

        html, rendered = None, False
        if obscura:
            html = render_html(url, obscura)
            rendered = html is not None
        if html is None:
            html = trafilatura.fetch_url(url)
        if not html:
            manifest["skipped"].append({"url": url, "reason": "fetch_failed"})
            continue

        parser = LinkParser(url)
        parser.feed(html)
        enqueue(parser.links)

        md = trafilatura.extract(html, output_format="markdown", include_links=True,
                                 include_images=True, favor_recall=True) or ""
        if len(md) < MIN_MARKDOWN_CHARS:
            manifest["skipped"].append({"url": url, "reason": "thin"})
            continue
        digest = hashlib.sha256(re.sub(r"\s+", " ", md).strip().encode()).hexdigest()
        if digest in kept_hashes:
            manifest["skipped"].append({"url": url, "reason": "exact_duplicate"})
            continue
        dup, sset = near_duplicate(md, kept_shingles)
        if dup:
            manifest["skipped"].append({"url": url, "reason": "near_duplicate"})
            continue
        kept_hashes.add(digest)
        kept_shingles.append(sset)
        kept.append({"url": url, "md": md, "rendered": rendered})
        time.sleep(args.delay)

    # Site furniture: strip what repeats across pages, keep it once.
    common_lines = []
    if not args.keep_boilerplate:
        cleaned, common_lines = strip_common_lines([p["md"] for p in kept])
        for page, md in zip(kept, cleaned):
            page["md"] = md
    if common_lines:
        with open(os.path.join(args.out, "_common.md"), "w") as f:
            f.write("<!-- lines that repeated across the site (header, footer, menus); "
                    "removed from every page and kept here once -->\n\n")
            f.write("\n".join(common_lines) + "\n")

    # Images: only what the CLEANED content references (so the header logo is
    # gone), one fetch per picture across its size variants, one file per
    # distinct byte content.
    image_hashes, key_to_local = {}, {}
    for page in kept:
        local_map = {}
        for raw_ref in dict.fromkeys(MD_IMAGE_RE.findall(page["md"])):
            img_url = urljoin(page["url"], raw_ref)
            key = image_key(img_url)
            if key in key_to_local:
                local_map[raw_ref] = key_to_local[key]
                continue
            if manifest["images"] >= args.max_images:
                break
            host = urlsplit(img_url).hostname
            if not host or not is_public_host(host):
                continue
            try:
                data, ctype = fetch_bytes(img_url, MAX_IMAGE_BYTES)
            except Exception:
                continue
            if not data:
                continue
            ihash = hashlib.sha256(data).hexdigest()[:16]
            if ihash not in image_hashes:
                fname = f"{ihash}.{ext_for(img_url, ctype)}"
                with open(os.path.join(img_dir, fname), "wb") as f:
                    f.write(data)
                image_hashes[ihash] = fname
                manifest["images"] += 1
            key_to_local[key] = f"images/{image_hashes[ihash]}"
            local_map[raw_ref] = key_to_local[key]
        page["md"] = rewrite_images(page["md"], local_map)

    # Write pages. A page that was all furniture is not worth a file.
    used = set()
    for page in kept:
        if len(page["md"].strip()) < MIN_MARKDOWN_CHARS // 2:
            manifest["skipped"].append({"url": page["url"], "reason": "boilerplate_only"})
            continue
        slug = slugify(page["url"])
        fname, n = f"{slug}.md", 1
        while fname in used or os.path.exists(os.path.join(args.out, fname)):
            fname = f"{slug}-{n}.md"
            n += 1
        used.add(fname)
        with open(os.path.join(args.out, fname), "w") as f:
            f.write(f"<!-- source: {page['url']} -->\n\n{page['md']}")
        manifest["pages"].append({"url": page["url"], "file": fname,
                                  "chars": len(page["md"]), "rendered": page["rendered"]})

    manifest["discovered"] = len(discovered)
    manifest["unread"] = len([u for u in queue if u not in seen])
    manifest["common_lines"] = len(common_lines)
    with open(os.path.join(args.out, "_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(json.dumps({"pages": len(manifest["pages"]),
                      "discovered": manifest["discovered"],
                      "unread": manifest["unread"],
                      "limit": args.max_pages,
                      "limit_reached": manifest["limit_reached"],
                      "skipped": len(manifest["skipped"]),
                      "images": manifest["images"],
                      "rendered": sum(1 for p in manifest["pages"] if p["rendered"]),
                      "common_lines": len(common_lines),
                      "renderer": obscura}))


if __name__ == "__main__":
    main()
