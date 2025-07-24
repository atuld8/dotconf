#!/bin/bash
#
# This script provides functionality for <describe what the script does>.
#
# Usage:
#   ./<script_name> [options]
#
# Options:
#   -h, --help    Show this usage message and exit.
#
# Example:
#   ./<script_name> -h
#
# To print the usage on screen, call the usage method:
#   usage
#
# The 'usage' method displays this help message and exits the script.
# Function
#

#Set below env before using it
#export JIRA_ACC_TOKEN='tkn'
#export JIRA_SERVER_NAME=".com"
#export JIRA_PROJECT_NAME="PROJ"
#export JIRA_EPIC_LINK="EPIC-1234"

# Arguments
JIRA_ID=$1
NEW_EPIC_ID=${2:-$JIRA_EPIC_LINK}

echo "JIRA_ID set to: $JIRA_ID"
if [[ -n "$2" ]]; then
    echo "NEW_EPIC_ID set to (from argument): $NEW_EPIC_ID"
else
    echo "NEW_EPIC_ID set to (from JIRA_EPIC_LINK env): $NEW_EPIC_ID"
fi


usage() {
    echo "Usage: $0 <JIRA_ID> [EPIC_ID]"
    echo ""
    echo "Sets the Epic Link for a given Jira ticket."
    echo ""
    echo "Arguments:"
    echo "  JIRA_ID      The Jira issue ID to update."
    echo "  EPIC_ID      (Optional) The Epic issue ID to set as the Epic Link."
    echo ""
    echo "Environment Variables:"
    echo "  JIRA_ACC_TOKEN     Jira API access token."
    echo "  JIRA_SERVER_NAME   Jira server domain (e.g., yourcompany.atlassian.net)."
    echo "  JIRA_PROJECT_NAME  Jira project key."
    echo "  JIRA_EPIC_LINK     Default Epic issue ID."
    echo ""
    echo "Example:"
    echo "  $0 PROJ-1234 EPIC-5678"
    exit 0
}

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    usage
fi

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Error: Invalid number of arguments."
    usage
fi

generatePostDataToUpdateEpicLink() {
  _JIRA_FIELD_ID=$1
  shift
  _JIRA_FIELD_VALUE=$1
  cat <<POST_DATA_EOF
  {
    "fields":
        {
            "${_JIRA_FIELD_ID}": "$_JIRA_FIELD_VALUE"
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
set_epic_link_to_jira_ticket() {
    REST_API_PATH="issue/$JIRA_ID"
    epic_link=($NEW_EPIC_ID)

    if [ ! -z ${NEW_EPIC_ID} ]; then
        echo "Setting Epic Link to $NEW_EPIC_ID"
        jira_put_call $REST_API_PATH generatePostDataToUpdateEpicLink customfield_10001 $NEW_EPIC_ID
    else
        echo "Skipping the Epic Link value setting as it is empty"
    fi
}


#
# Main starts here

# Function to check required environment variables and arguments
check_required_vars() {
    local missing_vars=()

    [[ -z "$JIRA_ACC_TOKEN" ]] && missing_vars+=("JIRA_ACC_TOKEN")
    [[ -z "$JIRA_SERVER_NAME" ]] && missing_vars+=("JIRA_SERVER_NAME")
    [[ -z "$JIRA_ID" ]] && missing_vars+=("JIRA_ID argument")
    [[ -z "$NEW_EPIC_ID" ]] && missing_vars+=("EPIC_ID argument")

    if (( ${#missing_vars[@]} )); then
        echo "Error: Missing required value(s): ${missing_vars[*]}"
        usage
        exit 1
    fi
}

# Function to run the main logic
main() {
    check_required_vars
    set_epic_link_to_jira_ticket
}

# Run main
main
