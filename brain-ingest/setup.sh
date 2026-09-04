#!/usr/bin/env bash
# Brain kit setup. Task & Tool runs this on the machine when the kit is
# installed, and again whenever the machine is replaced. It is safe to re-run
# any time to update the tools:
#
#     bash ~/app/.claude/skills/brain-ingest/setup.sh
#
# Installs: trafilatura (site -> markdown), markitdown (docs -> markdown),
# and the Obscura headless browser (the site crawler renders every page
# through it; the browse skill uses it too). Nothing here touches the app's
# code.
set -euo pipefail

OBSCURA_VERSION="${OBSCURA_VERSION:-v0.2.1}"
OBSCURA_REPO="https://github.com/h4ckf0r0day/obscura"

echo "== python tools"
python3 -m pip install --quiet --upgrade "trafilatura>=1.8" "markitdown" 2>&1 | tail -3 || true
python3 -c "import trafilatura; print('trafilatura', trafilatura.__version__)"

# Where the Obscura binary goes: system-wide when we can, else ~/.local/bin.
# brain_scrape.py and the browse skill look in both places.
if [ -w /usr/local/bin ]; then
  BIN=/usr/local/bin
elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  BIN=/usr/local/bin
  SUDO="sudo -n"
else
  BIN="$HOME/.local/bin"
fi
SUDO="${SUDO:-}"
$SUDO mkdir -p "$BIN"

echo "== obscura $OBSCURA_VERSION -> $BIN"
case "$(uname -m)" in
  x86_64|amd64) asset="obscura-x86_64-linux.tar.gz" ;;
  aarch64|arm64) asset="obscura-aarch64-linux.tar.gz" ;;
  *) echo "no obscura build for $(uname -m); skipping (the scraper falls back to static extraction)"; exit 0 ;;
esac

stamp="$BIN/.obscura-version"
if [ -x "$BIN/obscura" ] && [ "$(cat "$stamp" 2>/dev/null || true)" = "$OBSCURA_VERSION" ]; then
  echo "obscura $OBSCURA_VERSION already installed"
else
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL --retry 3 "$OBSCURA_REPO/releases/download/$OBSCURA_VERSION/$asset" -o "$tmp/obscura.tgz"
  tar xzf "$tmp/obscura.tgz" -C "$tmp"
  # The archive holds `obscura` and `obscura-worker` (keep them together: the
  # parallel `scrape` command spawns the worker). Layout varies by release, so
  # locate them rather than assume the top level.
  main_bin="$(find "$tmp" -type f -name obscura | head -1)"
  worker_bin="$(find "$tmp" -type f -name obscura-worker | head -1)"
  [ -n "$main_bin" ] || { echo "obscura binary not found in $asset"; exit 1; }
  $SUDO install -m 755 "$main_bin" "$BIN/obscura"
  [ -n "$worker_bin" ] && $SUDO install -m 755 "$worker_bin" "$BIN/obscura-worker"
  echo "$OBSCURA_VERSION" | $SUDO tee "$stamp" >/dev/null
  echo "installed obscura $OBSCURA_VERSION"
fi
"$BIN/obscura" --version 2>/dev/null || true

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
echo "== brain kit setup done"
