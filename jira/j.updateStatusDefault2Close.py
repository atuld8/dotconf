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


# Function to get the current status of the Jira issue
def get_current_status(ticket_id):
    """
    Get the status of the Jira ticket
    """
    url = f"{issue_url}/{ticket_id}"
    response = requests.get(url, headers=headers, timeout=20)

    if response.status_code == 200:
        try:
            issue_data = response.json()
            status = issue_data['fields']['status']['name']
            return status
        except requests.exceptions.JSONDecodeError as e:
            print(f'Error decoding JSON: {e}')
    else:
        print(f"Failed to fetch issue details: {response.status_code} - {response.text}")

    return None


# Function to get the status id allowed for the Jira issue
def get_status_id(ticket_id, status):
    """
    Get the transition id if the status and allowed transition matches
    """
    url = f"{issue_url}/{ticket_id}/transitions"
    response = requests.get(url, headers=headers, timeout=20)

    if response.status_code == 200:
        try:
            transitions = response.json()['transitions']
            for transition in transitions:
                print(f"ID: {transition['id']}, Name: {transition['name']}")
                if transition['name'] == status:
                    print(f"Returning {transition['id']}")
                    return transition['id']
        except requests.exceptions.JSONDecodeError as e:
            print(f'Error decoding JSON: {e}')
    else:
        print(f"Failed to fetch issue details: {response.status_code} - {response.text}")

    return None


# Function to update status for the Jira issue
def update_status(ticket_id, status_id):
    """
    set the transition id to jira
    """

    url = f"{issue_url}/{ticket_id}/transitions"

    payload = json.dumps({
        "transition": {
            "id": status_id
        }
    })

    response = requests.post(url, headers=headers, data=payload, timeout=20)

    if response.status_code == 204:
        print(f"Status updated successfully for ticket {ticket_id}: {status_id}")
    else:
        print(f"Failed to update labels: {response.status_code} - {response.text}")


# Main function to update the status
def main(ticket_id, status):

    """
    Update the status of jira ticket id to status
    """

    current_status = get_current_status(ticket_id)

    if current_status == "Open" and status == "Done":
        print(r"Requested change is Done.Hence, changing the state from Open to open to \"Start Progress\"")
        status_id = get_status_id(ticket_id, "Start Progress")
        if status_id is None:
            print(f"Status id in none. Transition is not allowed to {status}")
            return

        # Update Jira ticket with new status
        print(f"Setting the status id to {status_id}")
        update_status(ticket_id, status_id)

    status_id = get_status_id(ticket_id, status)
    if status_id is None:
        print(f"Status id in none. Transition is not allowed to {status}")
        return

    # Update Jira ticket with new status
    print(f"Setting the status id to {status_id}")
    update_status(ticket_id, status_id)


# Command-line argument parser
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update labels for a Jira ticket")
    parser.add_argument("ticket_id", help="Jira ticket ID (e.g., JIR-123)")
    parser.add_argument("--status", default="Close", help="The status value. Default is Closed.")

    args = parser.parse_args()

    # Perform label management
    main(args.ticket_id, args.status)
