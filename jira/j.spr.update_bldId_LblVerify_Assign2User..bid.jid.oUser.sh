#!/bin/bash

[[ "$1" =~ ^((NBSM|NBSVRUP)_[0-9.]+_[0-9]{4})(, ((NBSM|NBSVRUP)_[0-9.]+_[0-9]{4}))*$ ]] && [[ "$2" =~ ^NBU-[0-9]+$ ]] || { echo "Error. Please enter Build_ID & Jira_ID Build_ID correctly in this order..." && exit 1; }

TARGET_BLD_ID=$1
JIRA_ISSUE_ID=$2
JIRA_USER_NAME=""

if [ "$3" != "" ]; then
    JIRA_USER_NAME=$3
fi


# Update the Target Build
echo "Updating the $JIRA_ISSUE_ID ticket with build id $TARGET_BLD_ID"
$(dirname "${BASH_SOURCE[0]}")/j.updateFldVal_id_fldname_value.sh $JIRA_ISSUE_ID Solution \"*Target_Build:* {{$TARGET_BLD_ID}}\"

# Add Verify label to Labels
echo "Setting Verify Label in Ticket"
$(dirname "${BASH_SOURCE[0]}")/j.addLabels..id.labels.sh $JIRA_ISSUE_ID Verify

if [[ ! -z $JIRA_USER_NAME ]]; then
    # Update assignee to user for further verification
    echo "Assigning the ticket to user $JIRA_USER_NAME"
    python3 $(dirname "${BASH_SOURCE[0]}")/j.updateAssignee.id.assignee.py $JIRA_ISSUE_ID $JIRA_USER_NAME
fi
