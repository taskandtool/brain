# Company Brain

**A knowledge base of your business that your AI agent builds, checks and
keeps up to date.** You get notes on your prices, policies and how-tos. Your
team can search them and open the page or document behind each fact.

[![Deploy on Task & Tool](https://taskandtool.com/images/deploy-button.svg)](https://taskandtool.com/accounts/register?starter_app=brain)

![The map of Northline Gardens' Company Brain beside its Prices note](https://taskandtool.com/images/starter-apps/brain.webp)

It's made to run on Task & Tool. Each app there has a computer for your AI
agent. The agent reads your website, documents and call transcripts on that
computer and writes what it finds as short notes. It follows the skills and
scripts in this repo. The notes are plain Markdown files. Your team reads
them as a website built with Quartz.

## Get started

Click the button above, or pick Company Brain when you create an app on
[Task & Tool](https://taskandtool.com/starter-apps/brain). Then ask in the
chat: "Read my website into the brain" and paste your website's address.

See it in use on the [Company Brain
page](https://taskandtool.com/starter-apps/brain).

## Features

### Start from your website and its documents

The agent opens each page in a real browser. You get the text of every page.
It reads up to 1,000 pages and tells you if your site has more. It also
fetches the price lists, brochures and menus your pages link to. If your
site is on WordPress, the agent can import every page and post from
WordPress with the date you published it.

### You can add documents, transcripts and facts in chat

The agent converts a PDF, Word, PowerPoint or Excel file you attach in the
chat to text. Paste your notes, or attach a call or meeting transcript. The
agent turns speaker labels and timestamps into readable paragraphs. When you
say "remember that we're closed Mondays now", the agent records what you
said and the date before it writes the note. With a Google connection, it
can also read your Google listing and reviews.

### Every fact is linked to its source

The agent writes a fact only when it can cite a source file. Each note is
one screen long and about one topic: a service, a policy, a person, a
procedure. If two sources have different values, the agent keeps both, marks
the conflict and asks you which is right. When a newer source has a
different fact, the agent marks the old note out of date and links it to the
newer note or source. When a fact comes from another business's site, the
agent puts that business's name in the note's title.

<img src="https://taskandtool.com/images/marketing/northline-gardens-brain-prices.webp" width="360" alt="Northline Gardens' Prices note: lawn care from $45 a visit and hedge trimming from $120. Each price has a link to its source">

### The agent checks the notes every week

After the first notes are written, the agent schedules a check for Mondays.
If nothing changed since the last one, it says so in one line and stops.
Otherwise it runs these checks:

| Check | What the agent looks for |
|---|---|
| Citations | Five facts picked at random, checked against their sources |
| Contradictions | Two notes, or a note and a newer source, with different hours, prices, phone numbers or policies |
| Stale facts | Facts with a newer value in a later source. The agent marks them out of date. |
| Outside facts | Anything from another site or general knowledge written up as yours |
| Gaps | Notes with no links to them, and topics in many notes that have no note of their own |
| Links | Broken links and sources written as bare paths |
| Wrong folder | Internal procedures in `public/`, or a public fact kept in `brain/sops/` |
| Duplicates | Two notes about one thing, and notes that are only a copy of a source |
| Wording | Machine-sounding phrases |

Where a newer source has the answer, the agent fixes the note. Otherwise it
asks you. It puts all its questions in one message. You can see or remove
the job on the app's Jobs tab.

### A private site for your team

The agent serves the notes as a website at the app's team address. Your team
can search the notes, browse by folder, follow backlinks and see a graph of
the links between notes. You can click a citation to open the source page or
document. At the top of a note you see its type, its status and when it was
last updated.

When you ask, the agent publishes the site to production on your own domain.
If you make it public, anyone can read all the notes. That includes your
procedures and the raw sources. The agent can also match the site's colors
and fonts to your brand.

![A search for deposit and the Deposits note. The $50 deposit for a spring planting date is refundable up to 48 hours before the visit](https://taskandtool.com/images/marketing/northline-gardens-brain-search.webp)

### Your brand and business facts

The agent fills two folders. `brand/` has your look, voice, audience, logo
and best photos. `public/` has your business details, services, prices,
hours, FAQs, team, policies and reviews. The Website, Marketing, CRM and
Lander Starter Apps have the same `brand` skill and the same two folders.

### Ask questions about your business

Ask a question in the chat. The agent answers from the notes and names the
one it used. When the agent needs several notes for an answer, it saves the
answer as a new note. You can also ask what's in the brain so far and what's
missing.

### Rereading your site on a schedule

Tell the agent you want the brain kept current with your site. It asks how
often you change your site and schedules a crawl to match. For most small
businesses that is a few times a year. The crawl is a plain command without
AI. In the next chat, the agent finds what changed and updates the notes.

## Why run it on Task & Tool

Task & Tool is the easiest place to run it: the agent, the crawler and the
viewer are set up when you create the app. Each app has:

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

Ask the agent for any change in the chat. The rules for the notes are in
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

- Run `npm run dev` to install Quartz (first time only) and serve the notes
  on localhost:3000. You see changes as soon as a note is saved.
- Run `npm run build` to build the site into `dist/`.
- Run `npm run deploy` on Task & Tool to build the site and publish it to
  production.
- Run `python3 scripts/viewer.py check` to see broken links and bare
  citations. You get the link to write for each one.
- Run `python3 scripts/brain_status.py status` to list the sources not yet
  in notes.
- Run `python3 scripts/brain_status.py mark <path>` to record the ones that
  are.
- Run the tests with `python3 tests/test_brain_status.py`, `python3
  tests/test_viewer.py`, `python3 tests/test_words.py` and `node --test
  tests/*.test.mjs`.

## Third-party tools it installs

- [`tt-crawl`](https://github.com/taskandtool/crawler), our crawler (MIT),
  installed from its main branch. Its browser is headless Chrome from
  Google's Chrome for Testing. Obscura is its fallback browser. We install
  [markitdown](https://github.com/microsoft/markitdown) (MIT) with it for
  documents.
- [Quartz](https://github.com/jackyzha0/quartz) (MIT), the viewer, pinned to
  v5.0.0. Its community plugins are pinned by commit in
  `viewer/quartz.lock.json`.

Nothing is vendored. We install the crawler and its browsers in
`.taskandtool/after-setup.sh`. You install Quartz the first time you run
`npm run dev`.

## Contributing

Pull requests are welcome. There are no credentials in the repo. We scan our
own pushes for secrets.

## License

MIT. See `LICENSE`.
