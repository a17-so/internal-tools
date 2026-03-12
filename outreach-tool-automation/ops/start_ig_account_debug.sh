#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <@instagram_handle> <port>"
  echo "Example: $0 @regenhealth.app 9232"
  exit 1
fi

raw_handle="$1"
port="$2"
handle="${raw_handle#@}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROFILE_DIR="${ROOT_DIR}/sessions/instagram/${handle}"

mkdir -p "${PROFILE_DIR}"
echo "Starting Instagram debug Chrome for @${handle} on port ${port}"
echo "profile_dir=${PROFILE_DIR}"

"${SCRIPT_DIR}/start_chrome_debug.sh" "${port}" "${PROFILE_DIR}" "https://www.instagram.com/"
