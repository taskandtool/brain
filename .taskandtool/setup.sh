#!/usr/bin/env bash
# Company Brain setup. Task & Tool runs this in ~/app after the repository is
# cloned onto the machine, and again whenever the machine is replaced. It is
# safe to re-run any time to update the tools:
#
#     bash ~/app/.taskandtool/setup.sh
#
# Installs: the tt-crawl site reader at its latest (github.com/taskandtool/crawler)
# and the two browsers it drives, Chrome and Obscura; then the `web` service
# that serves the brain as a website, which installs the viewer (Quartz,
# outside the app) on its first start.
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

# The viewer's web service. `npm run dev` installs Quartz on its first start
# (minutes on a machine), so setup does not wait for it: the brain works in
# chat at once, and the Development address answers once Quartz is in.
if [ -f "$HOME/tools/taskandtool.py" ]; then
  echo "== the viewer: serving dev (npm run dev on port 3000); it installs Quartz on its first start"
  python3 "$HOME/tools/taskandtool.py" serve "npm run dev" --port 3000 \
    || echo "   not answering yet is expected while Quartz installs; python3 ~/tools/taskandtool.py logs shows its progress"
fi

echo "== company brain setup done"
