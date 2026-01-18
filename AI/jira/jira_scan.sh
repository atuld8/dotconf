#!/usr/bin/env bash
set -euo pipefail

# =========================
# Configuration (edit once)
# =========================
JIRA_BASE_URL="https://$JIRA_SERVER_NAME"
JIRA_API="/rest/api/2/search"

DEFAULT_FIELDS=("key" "summary" "status" "assignee")

# =========================
# Helpers
# =========================
usage() {
  cat <<EOF
Usage:
  jira_scan.sh "<JQL_QUERY>" [extra_field1,extra_field2,...]

Examples:
  jira_scan.sh "project = PROJ AND status != Done"
  jira_scan.sh "project = PROJ" "components,priority,updated"

Environment:
  JIRA_ACC_TOKEN must be set
EOF
  exit 1
}

log() {
  echo "[jira_scan] $*" >&2
}

fail() {
  echo "[jira_scan][ERROR] $*" >&2
  exit 1
}

# =========================
# Validation
# =========================
[[ $# -lt 1 ]] && usage
[[ -z "${JIRA_ACC_TOKEN:-}" ]] && fail "JIRA_ACC_TOKEN is not set"

JQL_QUERY="$1"
EXTRA_FIELDS="${2:-}"

# =========================
# Build fields list
# =========================
FIELDS=("${DEFAULT_FIELDS[@]}")

if [[ -n "$EXTRA_FIELDS" ]]; then
  IFS=',' read -ra EXTRA <<< "$EXTRA_FIELDS"
  FIELDS+=("${EXTRA[@]}")
fi

# Convert fields array to JSON
FIELDS_JSON=$(printf '"%s",' "${FIELDS[@]}")
FIELDS_JSON="[${FIELDS_JSON%,}]"

# =========================
# Build request body
# =========================
REQUEST_BODY=$(cat <<EOF
{
  "jql": "$JQL_QUERY",
  "fields": $FIELDS_JSON,
  "maxResults": 50
}
EOF
)

# =========================
# Debug output
# =========================
log "JQL        : $JQL_QUERY"
log "Fields     : ${FIELDS[*]}"
log "Endpoint   : $JIRA_BASE_URL$JIRA_API"

# =========================
# Execute request
# =========================
RESPONSE=$(curl -sS -w "\nHTTP_CODE=%{http_code}\n" \
  -H "Authorization: Bearer $JIRA_ACC_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST \
  "$JIRA_BASE_URL$JIRA_API" \
  -d "$REQUEST_BODY"
)

# =========================
# Parse HTTP code
# =========================
HTTP_CODE=$(echo "$RESPONSE" | sed -n 's/.*HTTP_CODE=//p')
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE=/d')

if [[ "$HTTP_CODE" != "200" ]]; then
  fail "HTTP $HTTP_CODE returned from Jira"
fi

# =========================
# Output
# =========================
echo "$BODY" \
| jq -r '.issues[] | "- \(.key): \(.fields.summary) [\(.fields.status.name)]"' \
| ollama run mistral

