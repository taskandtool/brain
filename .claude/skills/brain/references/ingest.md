# Taking material into raw/

Read when a site, a document, a transcript or a new kind of source arrives.
SCHEMA.md's layout says where each lands. The tools (tt-crawl, its browsers,
markitdown) were installed with the app; if one is missing, re-run
`bash ~/app/.taskandtool/setup.sh` once.

## The owner's website (the usual first step)

`tt-crawl` (`python3 -m ttcrawl` if it is not on the PATH) reads the site
in a real browser and keeps each page's own words. No model reads anything.
The whole site, with the pictures, styles and screenshots the brand skill
needs:

```bash
tt-crawl pages https://theirsite.com --images brand --styles --screenshots --screenshot-pages 5
tt-crawl docs                  # the price lists, brochures and menus the pages link to
```

It reads up to 1,000 pages (`--max-pages`); `--resume` carries on an
interrupted crawl. Each command prints what it read and wrote, then
`Next:`. For other jobs, print the recipe instead of guessing flags, for
example `tt-crawl playbook survey` for a site past 1,000 pages.
`structured/business.json` is the best seed for `public/business.md`.

What to do with what it reports:

- **The limit.** If its first line says `limit 1000 reached`, tell the
  owner ("your site has 2,400 pages; I read the first 1,000") and offer
  more, or a survey.
- **A fact with two values** in `_index/facts.json` (two phone numbers):
  ask the owner which is right; never pick.
- **WordPress** (`raw/site/_sites.json` has `"wordpress": true`):
  `tt-crawl import` adds every post and page through the site's own API,
  dated.
- **A site that refuses this machine** (a challenge page, a block on cloud
  addresses): use a web-scraping connection this app holds, as its skill
  says, or ask for one with `python3 ~/tools/taskandtool.py
  request-connection <slug> --why "<why>"`. Do neither without the
  owner's say-so: it spends their credits.

Tell the owner the result in plain words: pages read and found, pictures,
reviews, facts, documents, whether it is WordPress. A re-crawl with the
same command refreshes the folder in place, and `brain_status.py` lists
what changed.

## Uploaded documents

PDF, docx, pptx and xlsx convert with markitdown into `raw/docs/`, named
by the date the document was made if known, else today:

```bash
python3 -m markitdown their-brochure.pdf > raw/docs/2026-09-02-brochure.md
```

## Transcripts and pasted text

Write calls, meetings and video transcripts to
`raw/transcripts/YYYY-MM-DD-<name>.md`. Turn speaker labels, timestamps and
line-wrapping into readable paragraphs; from SRT or VTT keep only the text.

## Other sources

| Source | How it reaches raw/ |
|---|---|
| Someone else's site (competitor, supplier, directory) | `tt-crawl playbook competitor` gives the commands; into `raw/external/<host>/` |
| The Google listing and its reviews | the brand skill's `tt-crawl places` line, through the `google-places` connection (into `raw/places/`); more reviews or other review sites through the `dataforseo` or `apify` connection, as its skill says |
| YouTube | through a data connection (ScrapeCreators lists a channel's videos and transcripts; DataForSEO and SearchAPI fetch one video's), never directly: YouTube blocks this machine. One file per video: `raw/transcripts/YYYY-MM-DD-youtube-<video id>.md` with its title and link |
| Newsletters, social posts, CRM notes, Notion | through a connection the app holds, as its skill says; otherwise the owner pastes or exports |

A connection the app lacks: `python3 ~/tools/taskandtool.py
request-connection <slug> --why "<why>"`.

A new kind of source: ask what it is, where it lives, how it changes and
whether it is the owner's own. Then give it a raw subfolder (add it to
SCHEMA.md's layout), date-prefixed files, a source page, and a cadence.
