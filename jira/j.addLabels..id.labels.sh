#!/bin/bash
# Ex: j.addLabels_id_labels.sh NBU-189147 "label1 label2"
# Ex: j.addLabels_id_labels.sh NBU-189147 label1 label2

#Set below env before using it
#export JIRA_ACC_TOKEN='tkn'
#export JIRA_WATCHERS_LIST="user1 user2 user3"
#export JIRA_SERVER_NAME=".com"
#export JIRA_PROJECT_NAME="PROJ"

JIRA_ID=$1
shift;
JIRA_LABELS=$@


#
# Function
#
generatePostDataToUpdateLabels() {
  cat <<POST_DATA_EOF
  {
    "update": {
        "labels": [{
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
update_field_with_value() {
    REST_API_PATH="issue/$JIRA_ID"
    jira_put_call $REST_API_PATH generatePostDataToUpdateField $JIRA_FIELD_ID $JIRA_FIELD_VALUE
}


#
# Function
#
get_issue_labels_details() {
    REST_API_PATH="issue/$JIRA_ID"
    jira_get_call $REST_API_PATH | jq -jr '(.fields.labels| join(" , "))'
}


#
# Function
#
set_labels_id_to_jira_ticket() {
    REST_API_PATH="issue/$JIRA_ID"

    if [[ ! -z $JIRA_LABELS ]]; then
        for label in $JIRA_LABELS; do
            echo "Setting label: $label"
            jira_put_call $REST_API_PATH generatePostDataToUpdateLabels $label
        done
    fi
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

if [[ ! -z $JIRA_LABELS ]]; then
    echo -e "\n"
    echo -n "Labels before updating it: " & get_issue_labels_details
    echo -e "\n\n"
    set_labels_id_to_jira_ticket
    echo -e "\n\n"
    echo -n "Labels after updating it: "
    get_issue_labels_details
    echo -e "\n"
else
    echo -e "\n\nError: No labels are mentioned here to update"
fi

