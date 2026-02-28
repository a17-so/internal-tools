#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-9222}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROFILE_DIR="${2:-${ROOT_DIR}/sessions/chrome-debug}"
CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

mkdir -p "${PROFILE_DIR}"

echo "Starting separate Chrome debug profile on port ${PORT}..."
echo "profile_dir=${PROFILE_DIR}"
echo "Your normal Chrome tabs can stay open."

"${CHROME_BIN}" \
  --remote-debugging-port="${PORT}" \
  --user-data-dir="${PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  --new-window "https://www.tiktok.com" \
  >/tmp/outreach-chrome-debug.log 2>&1 &

echo "Chrome launched. Verify debugger at: http://127.0.0.1:${PORT}/json/version"
