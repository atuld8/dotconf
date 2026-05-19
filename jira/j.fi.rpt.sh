#!/bin/bash -x
echo "-----------------------------------------------------------------------------------------"
# Recommended enhanced command
j.fi.rpt.py -i $op/dump.ready.fi --report-format all --stale-days 14 --group-by status,priority,case-status,etrack
echo "-----------------------------------------------------------------------------------------"
# Manager-specific view:
j.fi.rpt.py -i $op/dump.ready.fi --report-format all -A $JIRA_USER_EMAIL
echo "-----------------------------------------------------------------------------------------"
# Focus on missing etracks only:
j.fi.rpt.py -i $op/dump.ready.fi --report-format all -W --stale-days 14
echo "-----------------------------------------------------------------------------------------"
# High-priority triage:
j.fi.rpt.py -i $op/dump.ready.fi --report-format risk -p critical
echo "-----------------------------------------------------------------------------------------"
# Full dump with issue list:
j.fi.rpt.py -i $op/dump.ready.fi --report-format all --stale-days 14 -l
echo "-----------------------------------------------------------------------------------------"
