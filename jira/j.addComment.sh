#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/jira_api.sh"
jira_init || exit 1
#

JIRA_ID=$1
shift


if [[ "$1" == "-f" ]]; then
    if [[ -f $2 ]]; then
        JIRA_COMMENT=`cat $2`;
    fi
else
    if [[ ! -z "$1" ]]; then
        JIRA_COMMENT=$@
    else
        echo "Enter your comment, then press Ctrl+D when finished:"
        JIRA_COMMENT=$(cat)
    fi
fi

# Replace newlines with \n (escaped newline for JSON)
JIRA_COMMENT=$(echo "$JIRA_COMMENT" | awk '{printf "%s\\n", $0}')

if [[ -z "$JIRA_COMMENT" ]]; then
    echo "Usage: $0 Jira_Id  <DubleQuoteComment...>| -f <file_Path>"
    exit 0
fi

generatePostData() {
  cat <<POST_DATA_EOF
  {
    "body": "$JIRA_COMMENT"
  }
POST_DATA_EOF
}

echo  "$(generatePostData)"
curl -i -X POST \
    -H "$JIRA_AUTH_HEADER" \
    -H "Content-Type:application/json" \
    "$JIRA_BASE_URL/rest/api/2/issue/$JIRA_ID/comment" \
    -d "$(generatePostData)"
