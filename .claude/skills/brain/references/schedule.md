# Scheduled jobs

Read after the first distill, or when the owner wants something kept
current. List what is there first, and add only what is missing:

```bash
python3 ~/tools/taskandtool.py list-jobs
```

## The weekly lint (after the first distill)

Each week a new chat runs the `brain-lint` skill:

```bash
python3 ~/tools/taskandtool.py schedule-job "Brain lint" --when "0 6 * * 1" --prompt "Weekly brain lint: run the brain-lint skill. If nothing in raw/, brain/, brand/ or public/ changed since the last lint entry in brain/log.md, say so in one line and stop."
```

Tell the owner what it is for, and that they can see or remove it in the
app's Jobs tab.

## Re-crawling the site

Only when the owner wants it. Ask how often the site changes. For most
small businesses that is a few times a year; don't schedule it daily. The
crawler needs no AI: schedule it as a command job. The next chat's
`brain_status.py status` lists what the crawl changed in `raw/`. Use the
first crawl's `pages` command, with `python3 -m ttcrawl` in place of `tt-crawl`:

```bash
python3 ~/tools/taskandtool.py schedule-job "Site recrawl" --when "0 4 1 * *" --command "python3 -m ttcrawl pages https://theirsite.com --images brand --styles --screenshots --screenshot-pages 5 && python3 -m ttcrawl docs"
```

Tell the owner that a price they change on the site is in the brain only after the next chat.
