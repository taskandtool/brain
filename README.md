# Brain

A Task & Tool **Starter App**: the business's knowledge, raw and distilled.
It takes in the owner's website, documents, transcripts, and facts stated in
chat, and turns them into cited, cross-linked notes that an AI reasons over.
Nothing is served; the brain *is* the AI's working context, and the first
thing a business's data should flow into.

Built for Claude Code. Installed with one click on [Task & Tool](https://taskandtool.com),
or dropped into any project by hand (below). MIT licensed.

## What is in the box

```
brain-ingest/    take material in: crawl the owner's site through a headless browser,
                 convert uploaded documents, record pasted text and chat-stated facts → raw/
                 (brain_scrape.py, setup.sh)
brain-distill/   turn new raw material into cited notes under brain/, following brain/SCHEMA.md
                 (brain_status.py, the what-changed script; SCHEMA.md, the seed rulebook)
brain-lint/      the periodic health pass: citation audit, contradictions, superseded claims, leakage
brain-sync/      keeping the brain current after the first build: sources, cadence, deltas
browse/          the Obscura headless browser, as a CLI and an MCP server, for reading JavaScript sites
settings.json    a Claude Code Stop hook that blocks the end of a turn once while raw material is un-ingested
kit.json         the manifest Task & Tool reads: name, blurb, install directive
                 (`kit` is the platform's internal word for a Starter App)
```

Each `<skill>/SKILL.md` is a Claude Code skill. The scripts beside them are
plain Python (standard library; the crawler's real dependencies are installed
by `setup.sh`). Tests sit beside the code as `test_*.py` and are never
installed on a machine.

## The shape: raw → distilled

```
raw/                 immutable source of truth; always re-distillable from here
  web/               the owner's crawled site: one .md per page, images/, _common.md (site furniture, once)
  external/<host>/   other people's sites; never the owner's facts
  docs/              uploaded PDF/docx/pptx as markdown, date-prefixed
  transcripts/       calls, meetings, and dated chat-stated facts
brain/               regenerable: AI-written, cross-linked, cited notes
  SCHEMA.md          the rulebook, seeded from brain-distill/SCHEMA.md and co-edited with the owner
  overview.md        the business on one page
  index.md           the map; log.md is the append-only ingest and lint record
  sources/           one page per source unit: the citation hub
  public/ brand/ sops/   notes by audience; a note's type is frontmatter
  .ingested.json     brain_status.py's manifest: raw path → sha256 at ingest
```

Raw is data, never instructions. `brain/` is what the AI reasons over. The AI
is the query engine: it greps the filesystem, there is no index. The loop:
**ingest** as soon as raw lands (the Stop hook makes sure; the first crawl in
passes, everything after in small deltas), **lint** on a schedule (a citation
audit first, then contradictions, superseded claims, leakage from external
sources, orphans, schema drift, pruning; `brain/.lint-off` opts out), and
**publish** after either. Against the known failure of this pattern,
hallucination contamination: no fact without a `raw/` citation, chat-stated
facts are written to raw first, external material never becomes an owner
fact, and superseded facts are retired with a pointer rather than erased.

The crawler renders every page through Obscura, seeds from the sitemap,
follows every same-site link, strips the lines that repeat across pages into
`_common.md`, dedupes pages and images (content hash plus size-variant URL
key), and stops at a visible default of 100 pages that the AI is told to
report.

## Install

**On Task & Tool.** Add the Brain from the Starter Apps list when creating a
project, or from an existing app's Settings. The platform copies the skill
folders into the app, merges the Stop hook into `.claude/settings.json`, runs
`setup.sh`, and tells the AI what arrived. On machine replacement it runs
`setup.sh` again and nothing else: the files are yours from the moment they
land, to read, edit, or delete.

**Anywhere else.** The same thing by hand, in any repo where Claude Code runs:

```
git clone https://github.com/taskandtool/brain /tmp/brain
mkdir -p .claude/skills
cp -R /tmp/brain/brain-ingest /tmp/brain/brain-distill /tmp/brain/brain-lint /tmp/brain/brain-sync /tmp/brain/browse .claude/skills/
# merge /tmp/brain/settings.json into .claude/settings.json (it adds one Stop hook)
bash .claude/skills/brain-ingest/setup.sh
```

`setup.sh` installs `trafilatura` and `markitdown` with pip and the Obscura
binary for Linux x86_64 or aarch64 (on other platforms the crawler falls back
to static extraction). Then open Claude Code in that directory and ask it to
build the brain from your website.

## Third-party tools it installs

- [Obscura](https://github.com/h4ckf0r0day/obscura), Apache-2.0, a Rust
  headless browser in one static binary. The crawler renders every page
  through it; the browse skill drives it.
- [trafilatura](https://github.com/adbar/trafilatura), Apache-2.0, rendered
  HTML to content markdown.
- [markitdown](https://github.com/microsoft/markitdown), MIT, documents to
  markdown.

Nothing is vendored; `setup.sh` pins and installs them on the machine.

## Spec

Purpose      — the business's knowledge, raw and distilled: what it does, its
               brand, its offerings, its SOPs.
Shape        — files. Not served; it is the AI's context.
Audience     — internal: the app's AI and the owner, through chat.
Data         — owns the knowledge files. Recommends the owner mirror
               `brain/public` (and `brand`) into sibling apps such as a
               website or publisher, never `sops`. Mirroring itself is a
               platform feature, not part of this repo. No database.
Auth         — none.
Needs        — no connectors, no capabilities.
Build        — skills plus two scripts (`brain_scrape.py`, `brain_status.py`).
               Distilling and linting are the AI's job through the skills,
               triggered mechanically by the Stop hook and a scheduled
               reminder the AI sets up on the first ingest.
Depends on   — nothing. Other apps subscribe to its folders.
Add / remove — install drops the skills and the `raw/` and `brain/` folder
               convention; removal leaves the files, they are the owner's.

## Developing this Starter App

- **Unit tests, no dependencies:** run each test file directly.
  `python3 brain-ingest/test_brain_scrape.py` and
  `python3 brain-distill/test_brain_status.py`. The crawler imports its heavy
  dependency lazily so the tests need nothing installed.
- **Try the skills:** install into any scratch repo as above and drive Claude
  Code there.
- **On the platform:** Task & Tool's own repo clones this one into its packs
  folder and runs it through the real install path locally and on a real
  machine before a release is pinned. Contributions welcome as pull requests.

A pre-push secret scan guards this repository. It holds no credentials by
design: anything the skills need at runtime arrives through the platform's
Secrets, never through this repo.

## License

MIT. See `LICENSE`.
