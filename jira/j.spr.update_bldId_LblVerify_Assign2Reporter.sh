#!/bin/bash

[[ "$2" =~ ^(NBSM|NBSVRUP)_[0-9.]+_[0-9]{4}$ ]] && [[ "$1" =~ ^NBU-[0-9]+$ ]] || (echo "Error. Please enter Jira_ID Build_ID correctly..." & exit 1)

JIRA_ISSUE_ID=$1
TARGET_BLD_ID=$2


# Update the Target Build
echo "Updating the $JIRA_ISSUE_ID ticket with build id $TARGET_BLD_ID"
$(dirname "${BASH_SOURCE[0]}")/j.updateFieldWithValue_id_field_value.sh $JIRA_ISSUE_ID Solution \"*Target_Build:* {{$TARGET_BLD_ID}}\"

# Add Verify label to Labels
echo "Setting Verify Label in Ticket"
$(dirname "${BASH_SOURCE[0]}")/j.addLabels..id.labels.sh $JIRA_ISSUE_ID Verify

# Update assignee to reporter for further verification
echo "Assigning the ticket to reporter"
python3.12 $(dirname "${BASH_SOURCE[0]}")/j.updateAssignee2Reporter.py $JIRA_ISSUE_ID

