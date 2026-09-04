---
description: "The brain's periodic health pass: audit citations, find contradictions, superseded claims, orphans, missing pages, dead links, schema drift and external-fact leakage in brain/; fix what is safe, flag the rest to the owner, publish. Runs weekly by a platform reminder, or on demand."
---

# Brain: lint

Ingest keeps the brain growing; lint keeps it true. Run it when the weekly
reminder arrives in chat, or whenever the owner asks. If the owner has said
they don't want the weekly pass, create the empty file `brain/.lint-off` and
say so; the reminder then does nothing.

## First, is there anything to do?

- Read `brain/SCHEMA.md`; it defines what "correct" means here.
- `python3 .claude/skills/brain-distill/brain_status.py status` — un-ingested
  raw files mean ingest first (the `brain-distill` skill), then lint.
- Read the last lint entry in `brain/log.md`. If nothing in `raw/` or `brain/`
  changed since, say so in one line and stop. Don't re-lint a brain that
  hasn't moved; it costs the owner tokens for nothing.

## The checks

Read `index.md`, `overview.md`, then every current note. Look for:

1. **Citation audit (the hallucination check).** Pick five facts at random
   from different notes and trace each to its cited `raw/` file: is the fact
   actually there, as stated? A fact with no citation, a citation that doesn't
   contain it, or a number that drifted is the top finding. Fix from raw or
   remove the fact, and say which in the log.
2. **Contradictions** — two current notes (or a note and a newer raw source)
   that disagree: hours, prices, phone numbers, policies. Newer raw wins when
   the date is clear; otherwise mark both and ask the owner.
3. **Stale claims** — facts a newer source superseded. Mark the old
   `status: superseded` with `superseded_by`; never just delete.
4. **Leakage** — anything from `raw/external/` or general knowledge presented
   as the owner's own fact, especially in `public/`. Move or relabel it.
5. **Orphans** — notes nothing links to, or missing from `index.md`. Link them
   in or fold them into a better home.
6. **Missing pages** — concepts referenced across notes with no note of their
   own (a service everyone mentions with no page). Create it from raw.
7. **Dead links** — relative links to notes or raw files that no longer exist.
8. **Wrong folder** — internal procedure in `public/`, a public fact buried in
   `sops/`. Move it; the folders are what other apps subscribe to.
9. **Schema drift** — notes missing frontmatter, oversized notes that should
   split, duplicates by meaning, source units with no `sources/` page, an
   `overview.md` that no longer matches the notes. Fix to the schema.
10. **Prune** — notes that only restate a raw page. Merge and remove the
    redundant note (update links and the index). **Never delete anything in
    `raw/`.**

## Then

- Append a lint entry to `brain/log.md`: what was checked (including which
  five facts were audited), what changed, what needs the owner.
- Tell the owner the short version. Ask the questions that only they can
  answer, one message, grouped.
- Refresh any mirrors of the brain's folders:

```bash
cd ~ && python3 -c "from tools.taskandtool import refresh_mirrors; print(refresh_mirrors())"
```
