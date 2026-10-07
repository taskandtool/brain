#!/usr/bin/env bash
# Company Brain setup. Task & Tool runs this in ~/app after the repository is
# cloned onto the machine, and again whenever the machine is replaced. It is
# safe to re-run any time to update the tools:
#
#     bash ~/app/.taskandtool/setup.sh
#
# Installs: the tt-crawl site reader at its latest (github.com/taskandtool/crawler)
# and the two browsers it drives, Chrome and Obscura; then the viewer (Quartz,
# outside the app) and the `web` service that serves the brain as a website.
# Nothing here touches the app's code.
set -euo pipefail
cd "$(dirname "$0")/.."

CRAWLER_REF="${CRAWLER_REF:-main}"
CRAWLER="git+https://github.com/taskandtool/crawler@$CRAWLER_REF"

echo "== tt-crawl $CRAWLER_REF (site reader) + python tools"
# The crawler's main, every run: the first install brings its dependencies;
# the second replaces its own code even when its version number did not move.
python3 -m pip install --quiet --upgrade "ttcrawl @ $CRAWLER" 2>&1 | tail -2 || true
python3 -m pip install --quiet --force-reinstall --no-deps "ttcrawl @ $CRAWLER" 2>&1 | tail -2 || true
python3 -m ttcrawl --version || echo "tt-crawl did not install; site capture is unavailable until it does"

# tt-crawl on the PATH, then the browsers it drives: Chrome reads pages and
# takes screenshots, Obscura is the small fallback. Done here so a first
# crawl never downloads a browser mid-conversation.
python3 -m ttcrawl setup || echo "tt-crawl setup did not finish every step; its output above says which"

# The viewer: Quartz outside the app, then the web service. A failure here
# leaves the brain itself working, and says why.
echo "== the viewer (Quartz)"
if python3 scripts/viewer.py install; then
  if [ -f "$HOME/tools/taskandtool.py" ]; then
    echo "== serving dev (npm run dev on port 3000)"
    python3 "$HOME/tools/taskandtool.py" serve "npm run dev" --port 3000 \
      || echo "the viewer did not start; python3 ~/tools/taskandtool.py logs says why"
  fi
else
  echo "the viewer did not install; the brain works without it. Re-run: bash .taskandtool/setup.sh"
fi

echo "== company brain setup done"
