# Scheduled jobs

Read after the first distill, or when the owner wants something kept
current. List what is there first, and add only what is missing:

```bash
python3 ~/tools/taskandtool.py list-jobs
```

## The weekly lint (after the first distill)

The brain stays true only if someone checks it. Each week a new chat runs
the `brain-lint` skill:

```bash
python3 ~/tools/taskandtool.py schedule-job weekly-brain-lint --when "0 6 * * 1" --team-only --prompt "Weekly brain lint: run the brain-lint skill. If brain/.lint-off exists, or nothing in raw/, brain/, brand/ or public/ changed since the last lint entry in brain/log.md, say so in one line and stop."
```

Tell the owner what it is for, and that the app's Jobs tab is where they
see or remove it.

## Re-crawling the site

Only when the owner wants it. Ask how often the site really changes; for
most small businesses that is a few times a year, so never a daily job. The
crawler needs no AI, so it runs as a command job; what it changes in `raw/`
waits for the next chat, where `brain_status.py status` finds it. Use the
first crawl's `pages` command, with `python3 -m ttcrawl` in place of `tt-crawl`:

```bash
python3 ~/tools/taskandtool.py schedule-job monthly-site-recrawl --when "0 4 1 * *" --team-only --command "python3 -m ttcrawl pages https://theirsite.com --images brand --styles --screenshots --screenshot-pages 5 && python3 -m ttcrawl docs"
```

Tell the owner a changed price on the site shows up in the brain after the
next chat, not silently overnight.
