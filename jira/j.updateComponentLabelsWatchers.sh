#!/bin/bash
#

#Set below env before using it
#export JIRA_ACC_TOKEN='tkn'
#export JIRA_WATCHERS_LIST="user1 user2 user3"
#export JIRA_SERVER_NAME=".com"
#export JIRA_PROJECT_NAME="PROJ"

JIRA_ID=$1
JIRA_COMPONENT_NAME="${2:-Commandos}"
JIRA_COMPONENT_ID=""

#
# Function
#
generatePostDataToUpdateComponent() {
  cat <<POST_DATA_EOF
  {
    "update": {
        "components": [
            {
            "set": [
                {
                "id": "$JIRA_COMPONENT_ID"
                }
                ]
            }
        ]
    }
  }
POST_DATA_EOF
}

#
# Function
#
generatePostDataToUpdateLabels() {
  cat <<POST_DATA_EOF
  {
    "update": {
        "labels": [
            {
            "add": "$1"
            }
        ]
    }
  }
POST_DATA_EOF
}

#
# Function
#
generatePostDataToUpdateWatcher() {
  cat <<POST_DATA_EOF
"$1"
POST_DATA_EOF
}

#
# Function
#
jira_get_call() {
   REST_API_PATH=$1;
   shift;
   curl --silent -H "Authorization: Bearer $JIRA_ACC_TOKEN" "https://$JIRA_SERVER_NAME/rest/api/2/$REST_API_PATH" $@;
}

#
# Function
#
jira_put_call() {
   REST_API_PATH=$1;
   shift;
   REST_GET_DATA_FUNC=$@;

   curl --silent -X PUT \
        -H "Authorization: Bearer $JIRA_ACC_TOKEN" \
        -H "Content-Type:application/json" \
        "https://$JIRA_SERVER_NAME/rest/api/2/$REST_API_PATH" \
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
        -H \"Authorization: Bearer $JIRA_ACC_TOKEN\" \
        -H \"Content-Type:application/json\" \
        \"https://$JIRA_SERVER_NAME/rest/api/2/$REST_API_PATH\" \
        --data-raw '"$($REST_GET_DATA_FUNC)"'" | sh
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
set_component_id_to_jira_ticket() {
    REST_API_PATH="issue/$JIRA_ID"
    jira_put_call $REST_API_PATH generatePostDataToUpdateComponent $JIRA_COMPONENT_ID
}

#
# Function
#
set_labels_id_to_jira_ticket() {
    REST_API_PATH="issue/$JIRA_ID"
    jira_put_call $REST_API_PATH generatePostDataToUpdateLabels "NBServerMigrator"
    jira_put_call $REST_API_PATH generatePostDataToUpdateLabels "NBServerMigrator_mainline"
}

#
# Function
#
set_watchers_to_jira_ticket() {
    REST_API_PATH="issue/$JIRA_ID/watchers"
    watchersArray=($JIRA_WATCHERS_LIST)

    echo "$JIRA_WATCHERS_LIST"
    for user in ${watchersArray[@]}; do
        echo "Adding $user to watcher"
        jira_post_call $REST_API_PATH generatePostDataToUpdateWatcher $user
    done
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
set_component_id_to_jira_ticket

# Set the labels
set_labels_id_to_jira_ticket

# set the watchers
set_watchers_to_jira_ticket
