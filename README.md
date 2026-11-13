# Company Brain

**A knowledge base of your business that your AI agent builds, checks and
keeps current by chat.** You get notes on your prices, policies and how-tos.
Your team can search them and open the page or document behind each fact.

[![Deploy on Task & Tool](https://taskandtool.com/images/deploy-button.svg)](https://taskandtool.com/accounts/register?starter_app=brain)

![The map of Northline Gardens' Company Brain with Prices lit, and the Prices note](https://taskandtool.com/images/starter-apps/brain.webp)

It's made to run on Task & Tool. There, each app has its own computer for
your AI agent. The agent reads your website, documents and call transcripts
on that computer and writes what it finds as short notes. It follows the
skills and scripts in this repo. The notes are plain Markdown files. Your
team reads them as a website built with Quartz.

## Get started

Click the button above, or pick Company Brain when you create an app on
[Task & Tool](https://taskandtool.com/starter-apps/brain). Then ask in the
chat: "Read my website into the brain" and paste your website's address.

See it in use on the [Company Brain page](https://taskandtool.com/starter-apps/brain).

## Features

### Start from your website and its documents

The agent opens each page in a real browser and keeps its words as they are.
It reads up to 1,000 pages and tells you if your site has more. It also
fetches the price lists, brochures and menus your pages link to. If your
site runs on WordPress, the agent can import every page and post through the
site's API. It imports them with their dates.

### You can add documents, transcripts and facts in chat

The agent converts a PDF, Word, PowerPoint or Excel file you attach in the
chat to text. Paste your notes, or attach a call or meeting transcript. The
agent turns speaker labels and timestamps into readable paragraphs. When you
say "remember that we're closed Mondays now", the agent saves your words
with the date before it writes the note. The agent can also read your Google
listing and reviews through a Google connection.

### Each fact has a source you can open

The agent writes a fact only when it can cite a source file. A note fits on
one screen and covers one topic: a service, a policy, a person, a procedure.
If two sources disagree, the agent keeps both values, marks the conflict and
asks you which is right. When a newer source changes a fact, the agent marks
the old note out of date and links it to the new one. The agent marks facts
it took from other sites as theirs.

<img src="https://taskandtool.com/images/marketing/northline-gardens-brain-prices.webp" width="360" alt="Northline Gardens' Prices note: lawn care from $45 a visit and hedge trimming from $120. Each price links to its source">

### The agent checks the notes every week

After the first notes are written, the agent schedules a check for Mondays.
If nothing changed since the last one, it says so in one line and stops.
Otherwise it runs these checks:

| Check | What the agent looks for |
|---|---|
| Citations | Whether five facts picked at random say what their sources say |
| Contradictions | Two notes, or a note and a newer source, that disagree on hours, prices, phone numbers or policies |
| Stale facts | Facts a newer source replaced. The agent marks them superseded. |
| Outside facts | Anything from another site or general knowledge written up as yours |
| Gaps | Notes nothing links to, and topics many notes mention that have no note |
| Links | Links that point nowhere and sources written as bare paths |
| Wrong folder | Internal procedures in `public/`, or a public fact kept in `brain/sops/` |
| Duplicates | Two notes about one thing, and notes that only repeat a source |
| Wording | Phrases that read as machine-written |

Where a newer source has the answer, the agent fixes the note. Otherwise it
asks you. It puts all its questions in one message. You can see or remove
the job on the app's Jobs tab.

### Your team gets a private site to search

The agent serves the notes as a website at the app's team address. Your team
can search the notes, browse by folder, follow backlinks and see a graph of
how notes link. You can click a citation to open the page or document the
fact came from. At the top of a note you see its type, its status and when
it was last updated.

When you ask, the agent publishes the site to production on your own domain.
If you make it public, anyone can read all the notes, including your
procedures and the raw sources. The agent can also match the site's colors
and fonts to your brand.

![A search for deposit opens the Deposits note: a $50 deposit holds a spring planting date, refunded up to 48 hours before the visit](https://taskandtool.com/images/marketing/northline-gardens-brain-search.webp)

### Your brand and facts in the folders your other apps use

The agent fills two folders. `brand/` has your look, voice, audience, logo
and best photos. `public/` has your business details, services, prices,
hours, FAQs, team, policies and reviews. The Website, Marketing, CRM and
Lander Starter Apps use the same `brand` skill and the same two folders.

### Ask questions about your business

Ask a question in the chat. The agent answers from the notes and names the
one it used. When an answer takes several notes to put together, the agent
saves it as a new note. You can also ask what's in the brain so far and
what's missing.

### Keep the brain current with your site

Tell the agent you want the brain kept current with your site. It asks how
often your site changes and schedules a crawl to match. For most small
businesses that is a few times a year. The crawl runs as a command without
AI. In the next chat, the agent finds what changed and updates the notes.

## Why run it on Task & Tool

Task & Tool is the easiest place to run it: the agent, the crawler and the
viewer are set up when you create the app. Each app gets:

- A computer for the agent
- A dev address your team can open to read the notes as the agent writes
  them
- Publishing on your own domain with a free SSL certificate. Only your team
  sees production until you make it public.
- Connections to Google and any service with an API. We keep their keys out
  of this repo.
- Scheduled jobs for the weekly check and the site recrawl
- Sign-in for your team

## Make it your own

Ask the agent for any change in the chat. The rules the notes follow are in
`brain/SCHEMA.md`. You can ask the agent to change them. To start from your
own copy, fork this repo, change what you like, and start a new app from
your fork on Task & Tool. You can also copy its skills from
`.claude/skills/` into another repo.

## What's in the repo

```
brain/SCHEMA.md   the rules the notes follow: layout, citing, conflicts
raw/              your sources: site pages, documents, transcripts
brand/ public/    your brand and published facts
scripts/          brain_status.py and viewer.py (see Commands)
viewer/           the site's colors, fonts and plugins
tests/            the tests for the scripts, plugins and wording
.claude/skills/   five skills: brain, brain-lint, brand, writing and tropes
AGENTS.md         what the agent reads first
.taskandtool/     setup for an install on Task & Tool
starter-app.json  what the app needs and its chat suggestions
```

What the agent writes in `brain/`, `raw/`, `brand/` and `public/` is not
committed. Only `brain/SCHEMA.md` and the folders' `_index.md` pages are.

## Commands

The agent runs these on the app's computer. With Python 3, Node 22 or later
and git, you can run the viewer on your own computer too.

- `npm run dev` installs Quartz the first time, then serves the notes on
  localhost:3000 and rebuilds on every change.
- `npm run build` builds the site into `dist/`.
- `npm run deploy` builds the site and publishes it to production. It works
  only on Task & Tool.
- `python3 scripts/viewer.py check` lists broken links and bare citations.
  For each one it prints the link to write.
- `python3 scripts/brain_status.py status` lists the sources not yet in
  notes.
- `python3 scripts/brain_status.py mark <path>` records the ones that are.
- `python3 tests/test_brain_status.py`, `python3 tests/test_viewer.py`,
  `python3 tests/test_words.py` and `node --test tests/*.test.mjs` run the
  tests.

## Third-party tools it installs

- [`tt-crawl`](https://github.com/taskandtool/crawler), our crawler (MIT),
  installed from its main branch. It drives headless Chrome from Google's
  Chrome for Testing. Obscura is its fallback browser. It installs
  [markitdown](https://github.com/microsoft/markitdown) (MIT) to read
  documents.
- [Quartz](https://github.com/jackyzha0/quartz) (MIT), the viewer, pinned to
  v5.0.0. Its community plugins are pinned by commit in
  `viewer/quartz.lock.json`.

Nothing is vendored. `.taskandtool/after-setup.sh` installs the crawler and
its browsers. `npm run dev` installs Quartz the first time it runs.

## Contributing

Pull requests are welcome. The repo holds no credentials. We scan our own
pushes for secrets.

## License

MIT. See `LICENSE`.
