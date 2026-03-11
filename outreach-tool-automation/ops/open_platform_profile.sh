#!/usr/bin/env bash
set -euo pipefail

# Open a dedicated Chrome user-data-dir for manual login/2FA.
# This avoids automated login attempts for anti-bot-sensitive platforms.
#
# Usage:
#   ./ops/open_platform_profile.sh tiktok @regenapp
#   ./ops/open_platform_profile.sh instagram @ethan.peps

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <platform:tiktok|instagram> <@handle>"
  exit 1
fi

platform="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
raw_handle="$2"
handle="${raw_handle#@}"

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$platform" in
  tiktok)
    profile_dir="$project_root/sessions/tiktok/$handle"
    login_url="https://www.tiktok.com/login"
    ;;
  instagram)
    profile_dir="$project_root/sessions/instagram/$handle"
    login_url="https://www.instagram.com/accounts/login/"
    ;;
  *)
    echo "Unsupported platform: $platform (expected tiktok or instagram)"
    exit 1
    ;;
esac

mkdir -p "$profile_dir"
echo "Opening Chrome with profile dir:"
echo "  $profile_dir"
echo "Login URL:"
echo "  $login_url"

open -na "Google Chrome" --args \
  --user-data-dir="$profile_dir" \
  --profile-directory=Default \
  "$login_url"
