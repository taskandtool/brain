---
description: "How to keep the company brain current after the first build: which sources are worth syncing, how to add a new source kind, what to schedule and what to leave case by case, and how re-ingest stays controlled. Use when the owner asks to keep something in sync, connect a new source, or when raw material needs refreshing."
---

# Brain: keeping it current

The first build is a batch: crawl the site, pull in the documents, ingest in
passes. After that, the brain should move only when the business does, in
small, controlled deltas. This skill is how to think about that.

## The principles

- **Delta, never sweep.** Every refresh goes through `raw/` and the manifest:
  `brain_status.py status` says exactly which raw files are new or changed, and
  you ingest only those (the `brain-distill` skill). A refresh that changes
  nothing costs nothing.
- **One unit at a time.** A re-crawl is one unit; a new document is one; a
  week of call transcripts is one per call. Log each.
- **Superseding, not overwriting.** When a refresh changes a fact, the old one
  is marked superseded with a pointer, per `brain/SCHEMA.md`.
- **Copies elsewhere follow on their own.** Folders the owner mirrored into
  other apps refresh at the end of every turn in which they changed; call
  `refresh_mirrors()` (tools.taskandtool) when it has to be immediate.
- **The owner sets the cadence.** Ask how often something really changes. Most
  small businesses: the site a few times a year, prices and hours occasionally,
  calls and documents whenever they happen. Don't invent a daily job.
- **Tools that need no AI can be scheduled; ingest happens in conversation.**
  The crawler runs fine as a scheduled job (Jobs, via the platform: it needs no
  AI key). What it changes in `raw/` is ingested the next time you're in chat —
  the Stop hook makes sure it isn't missed.

## Sources worth syncing, and how

| Source | How it reaches raw/ | Typical cadence |
|---|---|---|
| The owner's website | `tt-crawl site` re-crawl (idempotent; changed pages show as *changed*), then `tt-crawl docs` for linked documents | monthly, or when they say they changed the site |
| Documents (PDF, docx, sheets) | the owner uploads; convert with markitdown into `raw/docs/YYYY-MM-DD-name.md` | as they arrive |
| Calls and meetings | pasted or uploaded transcripts → `raw/transcripts/YYYY-MM-DD-name.md` | as they happen |
| Things the owner tells you in chat | `raw/transcripts/YYYY-MM-DD-chat.md` (their words, dated), then cite it | immediately |
| Other people's sites (competitors, suppliers, directories) | `tt-crawl site <url> --out raw/external/<host>` or the `browse` skill; **external, never the owner's facts** | on request |
| Reviews (Google, Yelp, etc.) | usually blocked for automated visitors from here; the owner pastes or exports | on request |
| YouTube and video | not automatic today: YouTube blocks most datacenter addresses. The owner can paste transcripts; a YouTube connection (API) or a proxy is a platform-level addition, not a workaround to attempt here | when the platform adds it |
| Email newsletters, social posts, CRM notes, Google Drive, Notion | through a connection the platform provides (Connections in Settings) once available; until then the owner pastes or exports | case by case |

Anything not on this list: ask what it is, where it lives, how it changes, and
who should see it. Then give it a raw subfolder, date-prefixed filenames, a
source page, and a cadence — the same shape as everything else.

## Adding a new source kind (the checklist)

1. Where in `raw/` it lives (a new subfolder if it's a new kind; add it to
   `brain/SCHEMA.md`'s layout).
2. How it's converted to markdown (markitdown for documents, the crawler for
   sites, plain text for transcripts). Keep the original bytes if they matter.
3. Whether it's the owner's own material or external. External goes under
   `raw/external/` and never into `public/` as the owner's facts.
4. Its source page in `brain/sources/`.
5. Its cadence, and whether a scheduled job (no AI) can do the pulling.

## Scheduling a re-crawl

If the owner wants the site refreshed on a cadence, schedule the crawler as a
job (from the app dir; see the platform's jobs tooling). Point it at the same
`raw/web` so pages update in place and the manifest reports changes:

```bash
tt-crawl site https://theirsite.com --out raw/web
```

Then the next conversation ingests the delta. Tell the owner that's how it
works, so a changed price on the site shows up in the brain after the next
chat, not silently at 3 a.m.
