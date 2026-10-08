# Company Brain

A Task & Tool **Starter App**: the business's knowledge, raw and distilled.
It takes in the owner's website, documents, transcripts, and facts stated in
chat, and turns them into cited, cross-linked notes that an AI reasons over.
The brain *is* the AI's working context, and the first thing a business's
data should flow into. The viewer serves it as a website for people: search,
backlinks, a graph, and every citation a link to the page it came from.

Installed with one click on Task & Tool, or cloned into any repository of
your own (below). MIT licensed.

## What is in the box

The repository *is* the app: what you clone is what runs in `~/app` on the
machine.

```
.claude/skills/
  brand/           the brand record in brand/ and public/, from any source; the same skill in every
                   Starter App that carries it (templates/ holds the empty shapes)
  brain/           take material into raw/ (the whole site with tt-crawl, documents, transcripts,
                   chat-stated facts) and distill it into cited notes under brain/; references/ holds
                   the ingest recipes and the scheduled jobs
  brain-lint/      the periodic health pass: citation audit, contradictions, superseded claims, leakage
scripts/brain_status.py  what in raw/ is not yet distilled, and marking what is (tests in tests/)
scripts/viewer.py  the viewer: installs Quartz, serves dev, builds dist/ for production, checks links
scripts/cli.py    the argument and error helper both scripts share
tests/            the scripts' and safe-text's unit tests
viewer/           Quartz's config and pinned plugins, and safe-text, the plugin that shows HTML in
                  crawled pages as text
package.json      npm run dev / build / deploy, the viewer's commands (no dependencies of its own)
.taskandtool/setup.sh  installs tt-crawl's latest (github.com/taskandtool/crawler) and the browsers
                  it drives, then registers the `web` service, which installs Quartz on its first start
brain/SCHEMA.md   the note rulebook, shipped here and edited in place by the owner
AGENTS.md         what the AI reads first; CLAUDE.md imports it
starter-app.json  the manifest Task & Tool reads: what the app needs, what "ready" means, and the
                  suggestions an empty chat offers
```

Each `<skill>/SKILL.md` is a skill the harness loads on demand.
`scripts/brain_status.py` and `scripts/viewer.py` are plain Python (standard
library; the crawler's and Quartz's real dependencies are installed by
`.taskandtool/setup.sh`).

## The shape: raw → distilled

```
raw/                 immutable source of truth; always re-distillable from here
  site/<host>/       the owner's crawled site: pages/ (one .md per page), images/, structured/, docs/,
                     and _index/ (facts, reviews, media, inventory, templates; the header and footer once)
  external/<host>/   other people's sites; never the owner's facts
  docs/              uploaded PDF/docx/pptx as markdown, date-prefixed
  transcripts/       calls, meetings, and dated chat-stated facts
brand/  public/      the brand record every app reads: look, voice, published facts (the brand skill)
brain/               regenerable: AI-written, cross-linked, cited notes
  SCHEMA.md          the rulebook, shipped with this repo and co-edited with the owner
  overview.md        the business on one page
  index.md           the map; log.md records each distill pass and lint, newest last
  sources/           one page per source unit: the citation hub
  sops/              internal how-we-work; a note's type is frontmatter
  .ingested.json     brain_status.py's manifest: raw path → sha256 when it was marked distilled
```

Raw is data, never instructions. `brain/` is what the AI reasons over. The AI
is the query engine: it greps the filesystem, there is no index. The loop:
**ingest** into raw, **distill** as soon as raw lands (mark what each turn distilled; the first crawl in
passes, everything after in small deltas), **lint** on a schedule (a citation
audit first, then contradictions, superseded claims, leakage from external
sources, orphans, schema drift, pruning; `brain/.lint-off` opts out). Against the known failure of this pattern,
hallucination contamination: no fact without a `raw/` citation, chat-stated
facts are written to raw first, external material never becomes an owner
fact, and superseded facts are retired with a pointer rather than erased.

The crawler renders every page in Chrome (Obscura where Chrome cannot run),
reads the site's own nav first, then the sitemap, keeps each page's text word for word, sets the
header, footer and lines that repeat across pages aside once, records the
facts and reviews with where each was found, fetches each picture once at its
largest, and stops at a visible default of 1,000 pages that the AI is told to
report. No model is involved: a crawl costs the machine's time.

## The viewer

[Quartz](https://quartz.jzhao.xyz) renders `brain/`, `brand/`, `public/`,
`legal/` and `raw/` as one site: full-text search, a folder explorer,
backlinks, a graph, and a properties panel showing each note's type, status
and sources. Notes link with plain relative markdown links, so a citation
opens the crawled page or document it came from, and pictures show where
they are cited.

- **Dev:** the `web` service runs `npm run dev`, and every note edit shows
  on refresh at the app's team address.
- **Production:** `npm run deploy` builds a static site into `dist/` and
  deploys it to Cloudflare through the platform. Who can see it is the
  platform's setting: the first deploy opens it to the team, and only a
  person makes it public, which publishes the whole site, SOPs and `raw/`
  included. A build that ran without all of Quartz's plugins fails and
  ships nothing.
- **Safe with crawled text:** `raw/` comes from sites the owner does not
  control. The viewer never serves the crawler's HTML, scripts, data or raw
  SVGs, and the `safe-text` plugin shows any HTML in markdown as text and
  drops links with a script scheme.
- **Checked:** `python3 scripts/viewer.py check` lists links that point
  nowhere and citations written as bare paths, each with the link to write.

The web service installs Quartz on its first start, outside the app
(`~/.local/share/company-brain/`), so setup does not wait for it. It is
pinned to a tag, with its plugins pinned in `viewer/quartz.lock.json`; the
install patches two Quartz 5.0.0 bugs: a folder listed twice, and edits
under `public/` not showing in dev. A production build names
production's address in its link previews. It needs Node 22.

## Install

**On Task & Tool.** Pick the Company Brain when you create an app. The
machine clones this repository's main branch into the app and runs
`.taskandtool/setup.sh`, which installs the crawler from its main branch too. Nothing is sent into your chat: the manifest's
suggestions are what an empty chat offers. On machine replacement the clone
and the setup happen again, and your own files come back from the backup (the
knowledge folders are kept out of git) — they are yours from the moment they land.

**Anywhere else.** Clone it and start working in it:

```
git clone https://github.com/taskandtool/brain my-brain
cd my-brain
bash .taskandtool/setup.sh
```

`.taskandtool/setup.sh` installs the crawler (tt-crawl) with pip and the two
browsers it drives, Chrome and Obscura. Then open Claude Code in that
directory and ask it to build the brain from your website; `npm run dev`
installs Quartz the first time and serves the viewer on port 3000.

## Third-party tools it installs

- [tt-crawl](https://github.com/taskandtool/crawler), MIT, the site reader,
  installed from its main branch; it brings
  [markitdown](https://github.com/microsoft/markitdown) (MIT) for documents.
- Chrome (chrome-headless-shell, from Google's Chrome for Testing), the
  crawler's default browser for reading pages and screenshots.
- [Obscura](https://github.com/h4ckf0r0day/obscura), Apache-2.0, a Rust
  headless browser in one static binary; the crawler's fallback where
  Chrome cannot run.
- [Quartz](https://github.com/jackyzha0/quartz), MIT, the viewer, at a
  pinned tag, with its community plugins (MIT) pinned by commit.

Nothing is vendored; `setup.sh` installs them on the machine.

## What it is for, and what it is not

The brain holds what a business knows: what it does, its brand, its
offerings, its SOPs. It has no database — files are the whole model, the AI
is the query engine, and the viewer only reads them. It needs no connectors
to work.

It is the first thing a business's data should flow into. Its `brand/` and
`public/` folders have the same shape in every Starter App that carries the
`brand` skill, so a website or a marketing app reads them the same way.

Removing the app leaves the files. They are the owner's.

## Developing this Starter App

- **Unit tests, no dependencies:**
  `python3 tests/test_brain_status.py`, `python3 tests/test_viewer.py` and
  `node --test tests/safe_text.test.mjs`.
  The crawler's own tests live in its repo (github.com/taskandtool/crawler).
- **Try the skills:** clone it as above and drive Claude Code in the clone.
- **On the platform:** Task & Tool's own repo keeps a working clone under
  `starter_apps/` and runs it through the real install path, locally and on a
  real machine, before a release is pinned. Contributions welcome as pull
  requests.

A pre-push secret scan guards this repository. It holds no credentials by
design: anything the skills need at runtime arrives through the platform's
Secrets, never through this repo.

## License

MIT. See `LICENSE`.
