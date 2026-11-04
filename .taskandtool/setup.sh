#!/usr/bin/env bash
# Company Brain setup. Task & Tool runs this in ~/app after the repository is
# cloned onto the machine, and again whenever the machine is replaced. It is
# safe to re-run any time to update the tools:
#
#     bash ~/app/.taskandtool/setup.sh
#
# Installs the `web` service that serves the brain as a website, which installs
# the viewer (Quartz, outside the app) on its first start. tt-crawl and its
# browsers are after-setup.sh's, once the app is up.
# Nothing here touches the app's code.
set -euo pipefail
cd "$(dirname "$0")/.."

# The viewer's web service. `npm run dev` installs Quartz on its first start
# (minutes on a machine), so setup does not wait for it: the brain works in
# chat at once, and dev's address answers once Quartz is in.
if [ -f "$HOME/tools/taskandtool.py" ]; then
  echo "== the viewer: serving dev (npm run dev on port 3000); it installs Quartz on its first start"
  python3 "$HOME/tools/taskandtool.py" serve "npm run dev" --port 3000 \
    || echo "   not answering yet is expected while Quartz installs; python3 ~/tools/taskandtool.py logs shows its progress"
fi

echo "== company brain setup done"
