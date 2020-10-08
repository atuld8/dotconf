#!/bin/bash
#

JIRA_ID=$1
shift
JIRA_COMMENT=$@

if [[ "$1" == "-f" ]]; then
    if [[ -f $2 ]]; then
        JIRA_COMMENT=`cat $2`;
    fi
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
    -H "Authorization: Bearer $JIRA_ACC_TOKEN" \
    -H "Content-Type:application/json" \
    "https://$JIRA_SERVER_NAME/rest/api/2/issue/$JIRA_ID/comment" \
    -d "$(generatePostData)"
