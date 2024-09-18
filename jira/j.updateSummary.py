#!/usr/bin/env python3.12
import json
import os
import argparse
import requests
from dotenv import load_dotenv


# Load the environment variables configured on the system
load_dotenv()

# Jira credentials and URL
JIRA_URL            = "https://" + os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN      = os.getenv('JIRA_ACC_TOKEN')


# Jira API endpoint for updating assignee
issue_url = f'{JIRA_URL}/rest/api/2/issue'

# Headers
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}


# Function to get the current summary of a Jira issue
def get_current_summary(ticket_id):
    url = f"{issue_url}/{ticket_id}"
    response = requests.get(url, headers=headers, timeout=20)

    if response.status_code == 200:
        try:
            issue_data = response.json()
            return issue_data['fields']['summary']
        except requests.exceptions.JSONDecodeError as e:
            print(f'Error decoding JSON: {e}')
    else:
        print(f"Failed to fetch issue details: {response.status_code} - {response.text}")

    return None


# Function to update summary for the Jira issue
def update_summary(ticket_id, new_summary):
    url = f"{issue_url}/{ticket_id}"

    payload = json.dumps({
        "fields": {
            "summary": new_summary
        }
    })

    response = requests.put(url, headers=headers, data=payload, timeout=20)

    if response.status_code == 204:
        print(f"Summary updated successfully for ticket {ticket_id}: {new_summary}")
    else:
        print(f"Failed to update summary: {response.status_code} - {response.text}")


def manage_summary(current_summary, operations, data):

    if data is None or data == "":
        return None

    new_summary = ""
    # Determine the new summary based on the operation
    if operations == "prepend":
        new_summary = f"{data} {current_summary}"
    elif operations == "append":
        new_summary = f"{current_summary} {data}"
    elif operations == "update":
        new_summary = data

    return new_summary


def parse_options():
    """ Command-line argument parser """
    parser = argparse.ArgumentParser(description="Update summary for a Jira ticket")
    parser.add_argument("ticket_id", help="Jira ticket ID (e.g., JIR-123)")
    parser.add_argument("operations", choices=["prepend", "append", "update"],
                        help="The operation to perform on the summary")
    parser.add_argument("data", help="The data to prepend, append, or use to update the summary")
    parser.add_argument("--skip-if-present",
                        action="store_true",
                        help=("Skip the prepend or append operation if the data is already"
                              "present in the summary")
                        )

    args = parser.parse_args()

    return args


def main():
    """Main function to generate updated summary"""

    args = parse_options()

    org_summary = get_current_summary(args.ticket_id)

    # Perform summary update
    new_summary = manage_summary(org_summary, args.operations, args.data)

    if new_summary is None:
        print("Skipping the update of summary as new summary is empty")
        return

    if args.skip_if_present and args.data in org_summary:
        print(f"Skipping the update of summary as {args.data} present in {org_summary}")
        return

    if new_summary == org_summary:
        print("Skipping the update of summary as new summary is same as orginal summary")
        return

    update_summary(args.ticket_id, new_summary)


if __name__ == "__main__":
    main()
