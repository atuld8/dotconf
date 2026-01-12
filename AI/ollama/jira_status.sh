#!/usr/bin/env bash
set -e

JQL='Project = \"BnR - NetBackup\" AND labels in (NBServerMigrator_2.8) ORDER BY updated DESC'

curl -s \
  -H "Authorization: Bearer $JIRA_ACC_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST \
  "https://$JIRA_SERVER_NAME/rest/api/2/search" \
  -d "{
    \"jql\": \"$JQL\",
    \"fields\": [\"key\", \"summary\", \"status\", \"assignee\", \"updated\"]
  }" \
| jq -r '
  .issues[] |
  "\(.key)\t\(.fields.status.name)\t\(.fields.assignee.displayName // "Unassigned")\t\(.fields.updated)"
'

