#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/jira_api.sh"
jira_init || exit 1
#

#Set below env before using it
#export JIRA_ACC_TOKEN='tkn'
#export JIRA_SERVER_NAME=".com"
#export JIRA_PROJECT_NAME="PROJ"
#export JIRA_EPIC_LINK="EPIC-1234"


JIRA_ID=$1
JIRA_COMPONENT_NAME="${2:-Commandos}"
JIRA_COMPONENT_ID=""

#
# Function
#
generatePostDataToUnsetComponent() {
  cat <<POST_DATA_EOF
  {
    "update": {
        "components": [
            {
            "set": []
            }
        ]
    }
  }
POST_DATA_EOF
}



#
# Function
#
jira_put_call() {
   REST_API_PATH=$1;
   shift;
   REST_GET_DATA_FUNC=$@;

   curl --silent -X PUT \
        -H "$JIRA_AUTH_HEADER" \
        -H "Content-Type:application/json" \
        "$JIRA_BASE_URL/rest/api/2/$REST_API_PATH" \
        -d "$($REST_GET_DATA_FUNC)"
}

#
# Function
#
jira_post_call() {
   REST_API_PATH=$1;
   shift;
   REST_GET_DATA_FUNC=$@;

   echo "curl -D- -X POST \
        -H \"$JIRA_AUTH_HEADER\" \
        -H \"Content-Type:application/json\" \
        \"$JIRA_BASE_URL/rest/api/2/$REST_API_PATH\" \
        --data-raw '"$($REST_GET_DATA_FUNC)"'" | tee sh
}

#
# Function
#
get_component_id() {
    REST_API_PATH="project/$JIRA_PROJECT_NAME/components"
    JIRA_COMPONENT_ID=`jira_get_call $REST_API_PATH | jq -r --arg jira_comp_name "$JIRA_COMPONENT_NAME" '.[] | select (.name == $jira_comp_name) | .id'`
}

#
# Function
#
unset_component_id_to_jira_ticket() {
    REST_API_PATH="issue/$JIRA_ID"
    jira_put_call $REST_API_PATH generatePostDataToUnsetComponent $JIRA_COMPONENT_ID
}


#
# Main start here
#
if [ "$JIRA_ACC_TOKEN" == "" ]; then
    echo "JIRA_ACC_TOKEN not defined"
    exit 1
fi

if [ "$JIRA_SERVER_NAME" == "" ]; then
    echo "JIRA_SERVER_NAME not defined"
    exit 1
fi


if [ "$JIRA_ID" == "" ]; then
    echo "Please pass the JIRA_ID with this script"
    exit 1
fi

# To get the component id from component name
get_component_id
echo $JIRA_COMPONENT_ID

# Set the compoent id
unset_component_id_to_jira_ticket

