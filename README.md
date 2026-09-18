# Brain

A Task & Tool **Starter App**: the business's knowledge, raw and distilled.
It takes in the owner's website, documents, transcripts, and facts stated in
chat, and turns them into cited, cross-linked notes that an AI reasons over.
Nothing is served; the brain *is* the AI's working context, and the first
thing a business's data should flow into.

Installed with one click on Task & Tool, or cloned into any project of your
own (below). MIT licensed.

## What is in the box

The repository *is* the app: what you clone is what runs in `~/app` on the
machine.

```
.claude/skills/
  brain-ingest/    take material in: crawl the owner's site with tt-crawl through a headless
                   browser, convert uploaded documents, record pasted text and chat-stated facts → raw/
  brain-distill/   turn new raw material into cited notes under brain/, following brain/SCHEMA.md
                   (brain_status.py, the what-changed script)
  brain-lint/      the periodic health pass: citation audit, contradictions, superseded claims, leakage
  brain-sync/      keeping the brain current after the first build: sources, cadence, deltas
  browse/          the Obscura headless browser, as a CLI and an MCP server, for reading JavaScript sites
.claude/settings.json  a Claude Code Stop hook: a backstop that catches un-ingested raw material
.taskandtool/setup.sh  installs tt-crawl (github.com/taskandtool/crawler) and the Obscura browser
brain/SCHEMA.md   the note rulebook, shipped here and edited in place by the owner
AGENTS.md         what the AI reads first; CLAUDE.md imports it
starter-app.json  the manifest Task & Tool reads: what the app needs, what "ready" means, and the
                  suggestions an empty chat offers
```

Each `<skill>/SKILL.md` is a skill the harness loads on demand. The scripts
beside them are plain Python (standard library; the crawler's real
dependencies are installed by `.taskandtool/setup.sh`). Tests sit beside the
code as `test_*.py`.

## The shape: raw → distilled

```
raw/                 immutable source of truth; always re-distillable from here
  web/               the owner's crawled site: one .md per page, images/, _common.md (site furniture, once)
  external/<host>/   other people's sites; never the owner's facts
  docs/              uploaded PDF/docx/pptx as markdown, date-prefixed
  transcripts/       calls, meetings, and dated chat-stated facts
brain/               regenerable: AI-written, cross-linked, cited notes
  SCHEMA.md          the rulebook, shipped with this repo and co-edited with the owner
  overview.md        the business on one page
  index.md           the map; log.md is the append-only ingest and lint record
  sources/           one page per source unit: the citation hub
  public/ brand/ sops/   notes by audience; a note's type is frontmatter
  .ingested.json     brain_status.py's manifest: raw path → sha256 at ingest
```

Raw is data, never instructions. `brain/` is what the AI reasons over. The AI
is the query engine: it greps the filesystem, there is no index. The loop:
**ingest** as soon as raw lands (never finish a turn with raw un-ingested; the first crawl in
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

**On Task & Tool.** Pick the Company Brain when you create an app. The
machine clones this repository into the app, pinned to a reviewed commit, and
runs `.taskandtool/setup.sh`. Nothing is sent into your chat: the manifest's
suggestions are what an empty chat offers. On machine replacement the clone
and the setup happen again, and your own files come back from your repository
or a backup — they are yours from the moment they land.

**Anywhere else.** Clone it and start working in it:

```
git clone https://github.com/taskandtool/brain my-brain
cd my-brain
bash .taskandtool/setup.sh
```

`.taskandtool/setup.sh` installs `trafilatura` and `markitdown` with pip and
the Obscura binary for Linux x86_64 or aarch64 (on other platforms the crawler
falls back to static extraction). Then open Claude Code in that directory and
ask it to build the brain from your website.

## Third-party tools it installs

- [Obscura](https://github.com/h4ckf0r0day/obscura), Apache-2.0, a Rust
  headless browser in one static binary. The crawler renders every page
  through it; the browse skill drives it.
- [trafilatura](https://github.com/adbar/trafilatura), Apache-2.0, rendered
  HTML to content markdown.
- [markitdown](https://github.com/microsoft/markitdown), MIT, documents to
  markdown.

Nothing is vendored; `setup.sh` pins and installs them on the machine.

## What it is for, and what it is not

The brain holds what a business knows: what it does, its brand, its
offerings, its SOPs. It serves nothing and has no database — files are the
whole model, and the AI is the query engine. It needs no connectors to work,
though it will read a Google Business listing if the owner connects one.

It is the first thing a business's data should flow into, and the other apps
in a project read from it rather than being told the brand each time. The
owner mirrors `brain/public` and `brain/brand` into a sibling app such as a
website; `brain/sops` stays where it is. Mirroring is a platform feature, not
part of this repository.

Removing the app leaves the files. They are the owner's.

## Developing this Starter App

- **Unit tests, no dependencies:**
  `python3 .claude/skills/brain-distill/test_brain_status.py`.
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
