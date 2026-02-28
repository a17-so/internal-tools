#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-9222}"

echo "Starting Google Chrome with remote debugging on port ${PORT}..."
echo "Tip: quit existing Chrome first so the debug flag is applied to your main profile."

open -na "Google Chrome" --args \
  --remote-debugging-port="${PORT}" \
  --new-window "https://www.tiktok.com"

echo "Chrome launched. Verify debugger at: http://127.0.0.1:${PORT}/json/version"
