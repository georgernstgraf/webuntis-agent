#!/usr/bin/env bash
# Start Brave with the Chrome DevTools Protocol remote debugging port so
# that webuntis-cli.recorder can attach to it.
#
# Uses the existing Default profile so all cookies/logins are available.
# If Brave is already running, this will fail (port in use); close all
# Brave windows first.
set -euo pipefail

PORT="${WEBUNTIS_CDP_PORT:-9222}"
BRAVE="${BRAVE_BIN:-brave-browser}"

if ! command -v "$BRAVE" >/dev/null 2>&1; then
    echo "Brave binary '$BRAVE' not found. Try: BRAVE_BIN=/opt/brave.com/brave/brave $0" >&2
    exit 1
fi

if curl -s "http://localhost:${PORT}/json/version" >/dev/null 2>&1; then
    echo "CDP port ${PORT} already in use. Is Brave already running with debug?" >&2
    echo "Proceeding anyway — recorder will attach to the existing instance." >&2
    exit 0
fi

exec "$BRAVE" \
    --remote-debugging-port="$PORT" \
    --user-data-dir="${HOME}/.config/BraveSoftware/Brave-Browser" \
    --profile-directory="Default" \
    "https://spengergasse.webuntis.com/"
