#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

DO_AUTH=1
RUN_NOW=0
UNLOCK_FIRST=0
RUN_ARGS=()

usage() {
  cat <<'USAGE'
Usage:
  ./ops/start_outreach_machine.sh [--no-auth] [--run] [--unlock] [-- <run_once args>]

Examples:
  ./ops/start_outreach_machine.sh
  ./ops/start_outreach_machine.sh --run -- --live --channels email,instagram,tiktok --verbose-summary
  ./ops/start_outreach_machine.sh --unlock --run -- --live --max-leads 75 --verbose-summary
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-auth)
      DO_AUTH=0
      shift
      ;;
    --run)
      RUN_NOW=1
      shift
      ;;
    --unlock)
      UNLOCK_FIRST=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      RUN_ARGS=("$@")
      break
      ;;
    *)
      echo "Unknown arg: $1"
      usage
      exit 1
      ;;
  esac
done

cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.venv/bin/activate"
fi

load_env_file() {
  local env_path="$1"
  [[ -f "${env_path}" ]] || return 0
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"
    [[ -z "${line}" ]] && continue
    [[ "${line}" =~ ^[[:space:]]*# ]] && continue
    [[ "${line}" != *"="* ]] && continue

    local key="${line%%=*}"
    local value="${line#*=}"
    key="$(echo "${key}" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')"
    value="$(echo "${value}" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')"
    [[ -z "${key}" ]] && continue
    if [[ "${value}" =~ ^\".*\"$ ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "${value}" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "${key}=${value}"
  done < "${env_path}"
}

load_env_file "${ENV_FILE}"

is_reachable() {
  local host="$1"
  local port="$2"
  if command -v nc >/dev/null 2>&1; then
    nc -z "${host}" "${port}" >/dev/null 2>&1
    return $?
  fi
  python - "$host" "$port" <<'PY'
import socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
try:
    with socket.create_connection((host, port), timeout=2):
        pass
    raise SystemExit(0)
except OSError:
    raise SystemExit(1)
PY
}

parse_host_port() {
  local url="$1"
  local rest="${url#*://}"
  local hostport="${rest%%/*}"
  local host="${hostport%%:*}"
  local port="${hostport##*:}"
  echo "${host}" "${port}"
}

start_ig_attach() {
  if [[ "${IG_ATTACH_MODE:-false}" != "true" ]]; then
    return
  fi

  if [[ -n "${IG_ATTACH_ACCOUNT_CDP_URLS:-}" ]]; then
    IFS=',' read -r -a mappings <<< "${IG_ATTACH_ACCOUNT_CDP_URLS}"
    for pair in "${mappings[@]}"; do
      [[ -z "${pair}" ]] && continue
      local handle="${pair%%=*}"
      local url="${pair#*=}"
      local hp
      hp="$(parse_host_port "${url}")"
      local host port
      host="$(awk '{print $1}' <<< "${hp}")"
      port="$(awk '{print $2}' <<< "${hp}")"
      if ! is_reachable "${host}" "${port}"; then
        ./ops/start_ig_account_debug.sh "${handle}" "${port}"
      fi
    done
    return
  fi

  if [[ -n "${IG_CDP_URL:-}" ]]; then
    local hp
    hp="$(parse_host_port "${IG_CDP_URL}")"
    local host port
    host="$(awk '{print $1}' <<< "${hp}")"
    port="$(awk '{print $2}' <<< "${hp}")"
    if ! is_reachable "${host}" "${port}"; then
      local ig_handle="${INSTAGRAM_SENDER_HANDLE:-@regenhealth.app}"
      ./ops/start_ig_account_debug.sh "${ig_handle}" "${port}"
    fi
  fi
}

start_tiktok_attach() {
  if [[ "${TIKTOK_ATTACH_MODE:-false}" != "true" ]]; then
    return
  fi

  if [[ -n "${TIKTOK_ATTACH_ACCOUNT_CDP_URLS:-}" ]]; then
    IFS=',' read -r -a mappings <<< "${TIKTOK_ATTACH_ACCOUNT_CDP_URLS}"
    for pair in "${mappings[@]}"; do
      [[ -z "${pair}" ]] && continue
      local handle="${pair%%=*}"
      local url="${pair#*=}"
      local hp
      hp="$(parse_host_port "${url}")"
      local host port
      host="$(awk '{print $1}' <<< "${hp}")"
      port="$(awk '{print $2}' <<< "${hp}")"
      if ! is_reachable "${host}" "${port}"; then
        ./ops/start_tiktok_account_debug.sh "${handle}" "${port}"
      fi
    done
    return
  fi

  if [[ -n "${TIKTOK_CDP_URL:-}" ]]; then
    local hp
    hp="$(parse_host_port "${TIKTOK_CDP_URL}")"
    local host port
    host="$(awk '{print $1}' <<< "${hp}")"
    port="$(awk '{print $2}' <<< "${hp}")"
    if ! is_reachable "${host}" "${port}"; then
      local tt_handle="${TIKTOK_SENDER_HANDLE:-@regen.app}"
      ./ops/start_tiktok_account_debug.sh "${tt_handle}" "${port}"
    fi
  fi
}

ensure_adc() {
  if [[ "${DO_AUTH}" -eq 0 ]]; then
    return
  fi
  if gcloud auth application-default print-access-token >/dev/null 2>&1; then
    return
  fi

  echo "ADC not ready. Starting Google auth flow..."
  gcloud auth application-default login \
    --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive
  local quota_project="${GOOGLE_CLOUD_QUOTA_PROJECT:-${FIRESTORE_PROJECT_ID:-}}"
  if [[ -n "${quota_project}" ]]; then
    gcloud auth application-default set-quota-project "${quota_project}" || true
  fi
}

echo "Bootstrapping outreach machine..."
ensure_adc
start_ig_attach
start_tiktok_attach

if [[ "${UNLOCK_FIRST}" -eq 1 ]]; then
  python -m outreach_automation.unlock_run_lock || true
fi

python -m outreach_automation.doctor

if [[ "${RUN_NOW}" -eq 1 ]]; then
  if [[ ${#RUN_ARGS[@]} -eq 0 ]]; then
    RUN_ARGS=(--live --channels email,instagram,tiktok --verbose-summary)
  fi
  python -m outreach_automation.run_once "${RUN_ARGS[@]}"
else
  cat <<'EOF'

Machine bootstrap complete.
Run command:
python -m outreach_automation.run_once --live --channels email,instagram,tiktok --verbose-summary
EOF
fi
