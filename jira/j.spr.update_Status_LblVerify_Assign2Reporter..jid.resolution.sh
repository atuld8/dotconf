#!/bin/bash

[[ "$1" =~ ^NBU-[0-9]+$ ]] || (echo -e "Error. Please enter Jira_ID <Resolutions>\n[Fixed, Can't Fix, Won't Fix, Duplicate, Incomplete, Cannot Reproduce, Done, Rejected, Won't Do, Monitored, Not an Issue]. Pass with correct order..." )
[[ "$1" =~ ^NBU-[0-9]+$ ]] || exit 1
JIRA_ISSUE_ID=$1
CUSTOM_RESOLUTION=${2:Fixed}


# Add Verify label to Labels
echo "Setting Verify Label in Ticket"
$(dirname "${BASH_SOURCE[0]}")/j.addLabels..id.labels.sh $JIRA_ISSUE_ID Verify

# Update assignee to reporter for further verification
echo "Assigning the ticket to reporter"
python3.12 $(dirname "${BASH_SOURCE[0]}")/j.updateAssignee2Reporter.py $JIRA_ISSUE_ID

# Update the status to done
echo "Updating the status to Done"
python3.12 $(dirname "${BASH_SOURCE[0]}")/j.updateStatusDefault2Close.py --status Done --resolution "$CUSTOM_RESOLUTION" $JIRA_ISSUE_ID
