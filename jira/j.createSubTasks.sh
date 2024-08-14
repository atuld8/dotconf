#!/bin/bash
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# This script will create 3 sub-tasks under the given Jira Id
# 1. Development Task:
# 2. Documentation Task:
# 3. QA Task:
#
# I/P = Jira_ID Release_label Release_version [componentName] [Any append string"
# Ex: script JIRA-1234 "" 2.5 "" "Add support for option help"
#
# Hidden flag -d
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

DEBUG_MODE=0

if [ "$1" == "-d" ]; then
    set -x
    DEBUG_MODE=1
    shift
fi

JIRA_ID=$1;
JIRA_RELEASE_NAME=${2:-NBServerMigrator}
JIRA_RELEASE_VER=$3
JIRA_COMPONENT_NAME="${4:-Commandos}"
JIRA_APPEND_STRING_TO_SUBTASK="$5"
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
generatePostDataToCreateSubTasks() {
  cat <<POST_DATA_EOF
    { "issueUpdates": [
        {"fields": {
             "project": {"key": "NBU"},
             "parent": {"key": "$JIRA_ID"},
             "summary": "Development Task: ${JIRA_APPEND_STRING_TO_SUBTASK}",
             "description": "Keep track of all coding work, including new features and bug fixes.",
             "issuetype": {"id": "5"},
             "labels": ["${JIRA_RELEASE_NAME}","${JIRA_RELEASE_NAME}_$JIRA_RELEASE_VER"],
             "components": [ {"id" : "$JIRA_COMPONENT_ID"} ]
         } },
         {"fields": {
             "project": {"key": "NBU"},
             "parent": {"key": "$JIRA_ID"},
             "summary": "Documentation Task: ${JIRA_APPEND_STRING_TO_SUBTASK}",
             "description": "Update documents to reflect the latest changes and improvements.",
             "issuetype": {"id": "5"},
             "labels": ["${JIRA_RELEASE_NAME}","${JIRA_RELEASE_NAME}_$JIRA_RELEASE_VER"],
             "components": [ {"id" : "$JIRA_COMPONENT_ID"} ]
         } },
         {"fields": {
             "project": {"key": "NBU"},
             "parent": {"key": "$JIRA_ID"},
             "summary": "QA Task: ${JIRA_APPEND_STRING_TO_SUBTASK}",
             "description": "Follow and manage all testing activities to ensure everything works correctly.",
             "issuetype": {"id": "5"},
             "labels": ["${JIRA_RELEASE_NAME}","${JIRA_RELEASE_NAME}_$JIRA_RELEASE_VER"],
             "components": [ {"id" : "$JIRA_COMPONENT_ID"} ]
         } }
      ]}
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

   curl -D- -X PUT \
        -H "Authorization: Bearer $JIRA_ACC_TOKEN" \
        -H "Content-Type:application/json" \
        "https://$JIRA_SERVER_NAME/rest/api/2/$REST_API_PATH" \
        -d "$($REST_GET_DATA_FUNC)"
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
jira_post_call() {

   REST_API_PATH=$1;
   shift;
   REST_GET_DATA_FUNC=$@;


   if [ "$DEBUG_MODE" -eq 0 ]; then
       sub_task_ids=(`echo "curl --silent -X POST \
            -H \"Authorization: Bearer $JIRA_ACC_TOKEN\" \
            -H \"Content-Type:application/json\" \
            \"https://$JIRA_SERVER_NAME/rest/api/2/$REST_API_PATH\" \
            --data-raw '"$($REST_GET_DATA_FUNC)"'" | sh | jq -r ".issues[].key"`)

        echo "Total ${#sub_task_ids[@]} created."
        for sub_task_id in ${sub_task_ids[@]}; do
            echo $sub_task_id
        done
   else
       echo "--data-raw $($REST_GET_DATA_FUNC)"
   fi
        # set_component_id_to_jira_ticket $sub_task_id

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

if [ "$JIRA_ID" == "-h" ]; then
    echo "$0 JIRA_ID RELEASE_NAME RELEASE_VERSION [TEAM_NAME]"
    exit 0
fi

if [ "$JIRA_RELEASE_VER" == "" ]; then
    echo "Please pass the RELEASE_VER with this script"
    exit 1
fi

#
# Function
#
create_sub-tasks() {
    REST_API_PATH="issue/bulk"
    jira_post_call $REST_API_PATH generatePostDataToCreateSubTasks
}


# Set the component id in variable, so that it will be used every where
get_component_id

# Call create sub-task to create with all properties
create_sub-tasks
