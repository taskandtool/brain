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

# tt-crawl on the PATH, then the browsers it drives: Chrome reads pages and
# takes screenshots, Obscura is the small fallback (the browse skill uses it
# too). Done here so a first crawl never downloads a browser mid-conversation.
python3 -m ttcrawl setup || echo "tt-crawl setup did not finish every step; its JSON line says which"

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
