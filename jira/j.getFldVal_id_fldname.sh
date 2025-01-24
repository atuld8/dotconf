#!/bin/bash
# Ex: j.updateFieldWithValue_id_field_value.sh NBU-189147 Solution "This solution is available in the build " <Build_ID> 

#Set below env before using it
#export JIRA_ACC_TOKEN='tkn'
#export JIRA_WATCHERS_LIST="user1 user2 user3"
#export JIRA_SERVER_NAME=".com"
#export JIRA_PROJECT_NAME="PROJ"

JIRA_ID=$1
JIRA_FIELD_NAME="${2:-Comments}"
JIRA_FIELD_ID=""
shift;
shift;
JIRA_FIELD_VALUE=$@

#
# Function
#
generatePostDataToUpdateField() {
  _JIRA_FIELD_ID=$1
  shift
  _JIRA_FIELD_VALUE=$@
  _JIRA_FIELD_VALUE="${_JIRA_FIELD_VALUE%\"}"
  _JIRA_FIELD_VALUE="${_JIRA_FIELD_VALUE#\"}"
  cat <<POST_DATA_EOF
  {
    "fields":
        {
            "$_JIRA_FIELD_ID": "$_JIRA_FIELD_VALUE"
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
get_field_id() {
    REST_API_PATH="field"
    JIRA_FIELD_ID=`jira_get_call $REST_API_PATH | jq -r --arg jira_field_name "$JIRA_FIELD_NAME" '.[] | select (.name == $jira_field_name) | .id'`
    echo "Field Name = $JIRA_FIELD_NAME and Field Id = $JIRA_FIELD_ID"
}

#
# Function
#
get_field_value_using_field_id() {
    REST_API_PATH="issue/$JIRA_ID?fields=$JIRA_FIELD_ID"
    JIRA_FIELD_VALUE=`jira_get_call $REST_API_PATH | jq -r --arg jira_field_id "$JIRA_FIELD_ID" ".fields[\"$JIRA_FIELD_ID\"]"`
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
get_field_id

if [[ ! -z $JIRA_FIELD_ID ]]; then
# Set the compoent id
    get_field_value_using_field_id
    echo -e "Jira ID ==> $JIRA_ID"
    echo -e "$JIRA_FIELD_NAME ==> $JIRA_FIELD_VALUE\n"
else
    echo -e "Error: Jira field id is null for field name '$JIRA_FIELD_NAME'\n"
fi

