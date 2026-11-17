#!/usr/bin/env bash
# Shared Cloud/Server Jira helpers for shell scripts in this folder.
#
# Usage (near top of a script, after env is available):
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   # shellcheck source=/dev/null
#   source "$SCRIPT_DIR/jira_api.sh"
#   jira_init || exit 1
#
# Provides:
#   JIRA_BASE_URL, JIRA_AUTH_HEADER, JIRA_IS_CLOUD
#   jira_curl METHOD PATH [curl args...]
#   jira_get / jira_put / jira_post REST_API_PATH
#
# Env:
#   JIRA_SERVER_NAME, JIRA_ACC_TOKEN
#   JIRA_USER_EMAIL (or JIRA_EMAIL / JIRA_USER) for Cloud
#   JIRA_AUTH_MODE=basic|bearer
#   JIRA_CLOUD=1|0
#   JIRA_CLOUD_ID (scoped token gateway)
#   JIRA_INSECURE_SSL=1 -> curl -k

jira_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

jira_normalize_host() {
  local host="${1:-}"
  host="${host#https://}"
  host="${host#http://}"
  host="${host%%/*}"
  host="${host%/}"
  printf '%s' "$host"
}

jira_detect_cloud() {
  if jira_truthy "${JIRA_CLOUD:-}"; then
    return 0
  fi
  if [[ "${JIRA_CLOUD:-}" == "0" || "${JIRA_CLOUD:-}" == "false" || "${JIRA_CLOUD:-}" == "no" || "${JIRA_CLOUD:-}" == "off" ]]; then
    return 1
  fi
  local host
  host="$(jira_normalize_host "${JIRA_SERVER_NAME:-}")"
  host="$(printf '%s' "$host" | tr '[:upper:]' '[:lower:]')"
  [[ "$host" == *.atlassian.net || "$host" == "atlassian.net" ]]
}

jira_init() {
  local host email auth_mode encoded
  host="$(jira_normalize_host "${JIRA_SERVER_NAME:-}")"

  if [[ -z "${JIRA_ACC_TOKEN:-}" ]]; then
    echo "JIRA_ACC_TOKEN not defined" >&2
    return 1
  fi
  if [[ -z "$host" ]]; then
    echo "JIRA_SERVER_NAME not defined" >&2
    return 1
  fi

  if [[ -n "${JIRA_CLOUD_ID:-}" ]] && jira_detect_cloud; then
    JIRA_BASE_URL="https://api.atlassian.com/ex/jira/${JIRA_CLOUD_ID}"
  else
    JIRA_BASE_URL="https://${host}"
  fi

  if jira_detect_cloud; then
    JIRA_IS_CLOUD=1
  else
    JIRA_IS_CLOUD=0
  fi

  auth_mode="$(printf '%s' "${JIRA_AUTH_MODE:-}" | tr '[:upper:]' '[:lower:]')"
  if [[ -z "$auth_mode" ]]; then
    if [[ "$JIRA_IS_CLOUD" == "1" ]]; then
      auth_mode="basic"
    else
      auth_mode="bearer"
    fi
  fi

  if [[ "$auth_mode" == "basic" ]]; then
    email="${JIRA_USER_EMAIL:-${JIRA_EMAIL:-${JIRA_USER:-}}}"
    if [[ -z "$email" ]]; then
      echo "Jira Cloud Basic auth requires JIRA_USER_EMAIL (or JIRA_EMAIL) with JIRA_ACC_TOKEN" >&2
      return 1
    fi
    encoded="$(printf '%s:%s' "$email" "$JIRA_ACC_TOKEN" | base64 | tr -d '\n')"
    JIRA_AUTH_HEADER="Authorization: Basic ${encoded}"
  elif [[ "$auth_mode" == "bearer" ]]; then
    JIRA_AUTH_HEADER="Authorization: Bearer ${JIRA_ACC_TOKEN}"
  else
    echo "Unsupported JIRA_AUTH_MODE=${JIRA_AUTH_MODE} (use basic or bearer)" >&2
    return 1
  fi

  JIRA_CURL_INSECURE=()
  if jira_truthy "${JIRA_INSECURE_SSL:-}"; then
    JIRA_CURL_INSECURE=(-k)
    echo "WARNING: JIRA_INSECURE_SSL=1 — TLS certificate verification is disabled." >&2
  fi

  export JIRA_BASE_URL JIRA_AUTH_HEADER JIRA_IS_CLOUD
  return 0
}

# jira_curl METHOD relative-or-absolute-path [extra curl args...]
jira_curl() {
  local method="$1"
  local path="$2"
  shift 2
  local url
  if [[ "$path" == http://* || "$path" == https://* ]]; then
    url="$path"
  else
    url="${JIRA_BASE_URL%/}/${path#/}"
  fi
  curl --silent "${JIRA_CURL_INSECURE[@]}" \
    -X "$method" \
    -H "$JIRA_AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    "$url" \
    "$@"
}

jira_get_call() {
  local rest_api_path="$1"
  shift
  jira_curl GET "rest/api/2/${rest_api_path}" "$@"
}

jira_put_call() {
  local rest_api_path="$1"
  local data_fn="$2"
  shift 2
  jira_curl PUT "rest/api/2/${rest_api_path}" \
    --data "$("$data_fn" "$@")"
}

jira_post_call() {
  local rest_api_path="$1"
  local data_fn="$2"
  shift 2
  # Keep previous scripts' behavior of printing curl for debugging where used.
  jira_curl POST "rest/api/2/${rest_api_path}" \
    --data "$("$data_fn" "$@")"
}
