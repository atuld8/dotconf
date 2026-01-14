#!/usr/bin/env python3
import os
import json
import argparse
import requests
from dotenv import load_dotenv

# Load the environment variables configured on the system
load_dotenv()

# Jira credentials and URL
JIRA_URL            = "https://" + os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN      = os.getenv('JIRA_ACC_TOKEN')
JIRA_PROJECT_KEY    = os.getenv('JIRA_PROJECT_KEY')

parser = argparse.ArgumentParser(description='Get Jira Epic details by ID.')
parser.add_argument('jira_id', type=str, help='The ID of the Jira')

args = parser.parse_args()
JIRA_ISSUE_ID      = args.jira_id

# Jira API endpoint for updating assignee
issue_url = f'{JIRA_URL}/rest/api/2/issue/{JIRA_ISSUE_ID}'
assignee_url = issue_url + '/assignee'

# Headers
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}


# Get issue details to extract the reporter's username
def get_issue_reporter(ticket_id):
    response = requests.get(issue_url, headers=headers, timeout=20)

    if response.status_code == 200:
        issue_data = response.json()
        reporter = issue_data['fields']['reporter']['name']  # Get the reporter's username
        return reporter

    print(f"Failed to fetch issue details: {response.status_code}")
    return None

# Assign the ticket to the reporter
def assign_ticket_to_reporter(ticket_id, reporter):
    payload = json.dumps({"name": reporter})

    response = requests.put(assignee_url, headers=headers, data=payload,
                            timeout=20)

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
