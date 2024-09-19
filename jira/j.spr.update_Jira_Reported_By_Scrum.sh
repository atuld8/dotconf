#!/usr/bin/env bash

[[ "$1" =~ ^NBU-[0-9]+$ ]] || (echo "Error. Please enter Jira_ID ..." & exit 1)

JIRA_ISSUE_ID=$1

echo -e "\n\n------- Step 1/2 -------"

# Update Sprint value to current sprint
echo "Update Sprint value to current sprint"
$(dirname "${BASH_SOURCE[0]}")/j.updateSprint.py $JIRA_ISSUE_ID


echo -e "\n\n------- Step 2/2 -------"

# Update Compoent Labels Watcher and Epic
echo "Update Component, Label, Group Watcher, Epic link"
$(dirname "${BASH_SOURCE[0]}")/j.updateComponent.Labels.Watchers.IfEpicLink.sh $JIRA_ISSUE_ID
