#!/bin/bash
#

#Set below env before using it
#export JIRA_ACC_TOKEN='tkn'
#export JIRA_SERVER_NAME=".com"
#export JIRA_PROJECT_NAME="PROJ"
#export JIRA_EPIC_LINK="EPIC-1234"

# Arguments 
JIRA_ID=$1


#
# Function
#
generatePostDataToUpdateEpicLink() {
  _JIRA_FIELD_ID=$1
  shift
  _JIRA_FIELD_VALUE=$1
  cat <<POST_DATA_EOF
  {
    "fields":
        {
            "${_JIRA_FIELD_ID}": $_JIRA_FIELD_VALUE
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
        --data-raw '"$($REST_GET_DATA_FUNC)"'" | tee sh
}


#
# Function
#
unset_epic_link_to_jira_ticket() {
    REST_API_PATH="issue/$JIRA_ID"
    epic_link=($JIRA_EPIC_LINK)

    if [ ! -z ${JIRA_EPIC_LINK} ]; then
        echo "Setting Epic Link to $JIRA_EPIC_LINK"
        jira_put_call $REST_API_PATH generatePostDataToUpdateEpicLink customfield_10001 null
    else
        echo "Skipping the Epic Link value setting as it is empty"
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


# set the epic link
unset_epic_link_to_jira_ticket
