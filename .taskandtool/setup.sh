#!/usr/bin/env bash
# Company Brain setup. Task & Tool runs this in ~/app after the repository is
# cloned onto the machine, and again whenever the machine is replaced. It is
# safe to re-run any time to update the tools:
#
#     bash ~/app/.taskandtool/setup.sh
#
# Installs: the tt-crawl site reader at its latest (github.com/taskandtool/crawler)
# and the two browsers it drives, Chrome and Obscura (the browse skill uses
# Obscura too).
# Nothing here touches the app's code.
set -euo pipefail

CRAWLER_REF="${CRAWLER_REF:-main}"
CRAWLER="git+https://github.com/taskandtool/crawler@$CRAWLER_REF"

echo "== tt-crawl $CRAWLER_REF (site reader) + python tools"
# The crawler's main, every run: the first install brings its dependencies;
# the second replaces its own code even when its version number did not move.
python3 -m pip install --quiet --upgrade "ttcrawl @ $CRAWLER" 2>&1 | tail -2 || true
python3 -m pip install --quiet --force-reinstall --no-deps "ttcrawl @ $CRAWLER" 2>&1 | tail -2 || true
python3 -m ttcrawl --version

# `tt-crawl` on the PATH, whatever pip did with its console script (a user
# install lands in ~/.local/bin, which a service shell may not have).
if ! command -v tt-crawl >/dev/null 2>&1; then
  for d in /usr/local/bin "$HOME/.local/bin"; do
    if [ -w "$d" ] || mkdir -p "$d" 2>/dev/null && [ -w "$d" ]; then
      printf '#!/bin/sh\nexec python3 -m ttcrawl "$@"\n' > "$d/tt-crawl" && chmod +x "$d/tt-crawl" && echo "tt-crawl launcher -> $d/tt-crawl" && break
    fi
  done
fi

# The browsers the crawler drives: Chrome reads pages and takes screenshots
# by default; Obscura is the small browser the browse skill uses. Installing
# them here keeps a first crawl from downloading a browser mid-conversation.
echo "== browsers"
python3 -m ttcrawl install-browser chrome || echo "chrome did not install; tt-crawl falls back to obscura"
python3 -m ttcrawl install-browser obscura || echo "obscura did not install; the browse skill needs it"
BIN="$(dirname "$(command -v obscura || echo "$HOME/.local/bin/obscura")")"

# Register Obscura's MCP server with Claude Code (user scope, so it is not
# written into the app's repo) for interactive browsing: navigate, click,
# fill, snapshot. One-shot fetches use the CLI (see the browse skill).
if command -v claude >/dev/null 2>&1; then
  if ! claude mcp get obscura >/dev/null 2>&1; then
    claude mcp add --scope user obscura -- "$BIN/obscura" mcp >/dev/null 2>&1 \
      && echo "registered obscura MCP server with Claude Code" \
      || echo "could not register the obscura MCP server (CLI use still works)"
  fi
fi
echo "== company brain setup done"
