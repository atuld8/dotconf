#!/usr/bin/env bash

[[ "$1" =~ ^NBU-[0-9]+$ ]] || (echo "Error. Please enter Jira_ID ..." & exit 1)

JIRA_ISSUE_ID=$1


# Add Tracking Label
echo "Setting Verify Label in Ticket"
$(dirname "${BASH_SOURCE[0]}")/j.addLabels..id.labels.sh $JIRA_ISSUE_ID Tracking


# Prepend [Tracking] word to summary
echo "Prepend [Tracking] word to summary of the Ticket"
$(dirname "${BASH_SOURCE[0]}")/j.updateSummary.py --skip-if-present $JIRA_ISSUE_ID prepend "[Tracking]"
