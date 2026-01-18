#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Configuration
# ============================================================
JIRA_BASE_URL="https://$JIRA_SERVER_NAME"
JIRA_API="/rest/api/2/search"
MODEL="mistral"

DEFAULT_FIELDS=("key" "summary" "status" "assignee")
MAX_RESULTS=50

# ============================================================
# Helpers
# ============================================================
usage() {
  cat <<EOF
Usage:
  jira_scan.sh "<JQL_QUERY>" [extra_fields] [--debug]

Examples:
  jira_scan.sh "project = PROJ AND status != Done"
  jira_scan.sh "project = PROJ" "components,priority,updated"
  jira_scan.sh "project = PROJ AND component = ABCD" "" --debug

Environment:
  JIRA_ACC_TOKEN must be set
EOF
  exit 1
}

log()  { echo "[jira_scan] $*" >&2; }
fail() { echo "[jira_scan][ERROR] $*" >&2; exit 1; }

# ============================================================
# Validation
# ============================================================
[[ $# -lt 1 ]] && usage
[[ -z "${JIRA_ACC_TOKEN:-}" ]] && fail "JIRA_ACC_TOKEN is not set"

JQL_QUERY="$1"
EXTRA_FIELDS="${2:-}"
DEBUG="${3:-}"

# ============================================================
# Build fields list
# ============================================================
FIELDS=("${DEFAULT_FIELDS[@]}")

if [[ -n "$EXTRA_FIELDS" ]]; then
  IFS=',' read -ra EXTRA <<< "$EXTRA_FIELDS"
  FIELDS+=("${EXTRA[@]}")
fi

FIELDS_JSON=$(printf '"%s",' "${FIELDS[@]}")
FIELDS_JSON="[${FIELDS_JSON%,}]"

# ============================================================
# Build request body
# ============================================================
REQUEST_BODY=$(cat <<EOF
{
  "jql": "$JQL_QUERY",
  "fields": $FIELDS_JSON,
  "maxResults": $MAX_RESULTS
}
EOF
)

# ============================================================
# Debug info
# ============================================================
log "JQL        : $JQL_QUERY"
log "Fields     : ${FIELDS[*]}"
log "Endpoint   : $JIRA_BASE_URL$JIRA_API"
[[ "$DEBUG" == "--debug" ]] && log "Request body:\n$REQUEST_BODY"

# ============================================================
# Call Jira
# ============================================================
RESPONSE=$(curl -sS -w "\nHTTP_CODE=%{http_code}\n" \
  -H "Authorization: Bearer $JIRA_ACC_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST \
  "$JIRA_BASE_URL$JIRA_API" \
  -d "$REQUEST_BODY"
)

HTTP_CODE=$(echo "$RESPONSE" | sed -n 's/.*HTTP_CODE=//p')
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE=/d')

[[ "$HTTP_CODE" != "200" ]] && fail "Jira API returned HTTP $HTTP_CODE"

ISSUE_COUNT=$(echo "$BODY" | jq '.issues | length')
[[ "$ISSUE_COUNT" -eq 0 ]] && log "No issues returned for this query."

# ============================================================
# Ollama prompt + Jira data
# ============================================================
{
  cat <<'EOF'
You are a technical program manager.
Summarize the following Jira issues.

Produce:
- Overall status
- Key risks
- Action items
- Items needing escalation

Be concise and factual.
EOF

  echo
  echo "Jira Issues:"
  echo

  echo "$BODY" | jq -r '
    .issues[] |
    "- \(.key): \(.fields.summary)
      Status: \(.fields.status.name)
      Assignee: \(.fields.assignee.displayName // "Unassigned")"
  '

} | {
  [[ "$DEBUG" == "--debug" ]] && tee /tmp/ollama_input.txt || cat
} | ollama run "$MODEL"

