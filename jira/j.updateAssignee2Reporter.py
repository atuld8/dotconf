#!/usr/bin/env python3
import os
import sys
import json
import argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jira_api import load_config, get, put

cfg = load_config()

# Jira credentials and URL
JIRA_PROJECT_KEY    = os.getenv('JIRA_PROJECT_KEY')

parser = argparse.ArgumentParser(description='Get Jira Epic details by ID.')
parser.add_argument('jira_id', type=str, help='The ID of the Jira')

args = parser.parse_args()
print(f"[CMD] {' '.join(sys.argv)}", file=sys.stderr)
JIRA_ISSUE_ID      = args.jira_id

# Jira API endpoint for updating assignee
issue_url = f'rest/api/2/issue/{JIRA_ISSUE_ID}'
assignee_url = issue_url + '/assignee'


# Get issue details to extract the reporter's username
def get_issue_reporter(ticket_id):
    response = get(issue_url, timeout=20)

    if response.status_code == 200:
        issue_data = response.json()
        reporter_obj = issue_data['fields']['reporter'] or {}
        # Cloud users are identified by accountId, Server/DC by username
        if cfg.is_cloud:
            reporter = reporter_obj.get('accountId')
        else:
            reporter = reporter_obj.get('name')
        return reporter

    print(f"Failed to fetch issue details: {response.status_code}")
    return None

# Assign the ticket to the reporter
def assign_ticket_to_reporter(ticket_id, reporter):
    if cfg.is_cloud:
        payload = json.dumps({"accountId": reporter})
    else:
        payload = json.dumps({"name": reporter})

    response = put(assignee_url, data=payload, timeout=20)

    if response.status_code == 204:
        print(f"Ticket {ticket_id} assigned to {reporter}.")
    else:
        print(f"Failed to assign ticket: {response.status_code} - {response.text}")


# Main function
def main():
    reporter = get_issue_reporter(JIRA_ISSUE_ID)
    if reporter:
        assign_ticket_to_reporter(JIRA_ISSUE_ID, reporter)


if __name__ == "__main__":
    main()
