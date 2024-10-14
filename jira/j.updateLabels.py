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


# Function to get the current labels of a Jira issue
def get_current_labels(ticket_id):
    url = f"{issue_url}/{ticket_id}"
    response = requests.get(url, headers=headers, timeout=20)

    if response.status_code == 200:
        try:
            issue_data = response.json()
            return issue_data['fields']['labels']
        except requests.exceptions.JSONDecodeError as e:
            print(f'Error decoding JSON: {e}')
    else:
        print(f"Failed to fetch issue details: {response.status_code} - {response.text}")

    return None


# Function to update labels for the Jira issue
def update_labels(ticket_id, new_labels):
    url = f"{issue_url}/{ticket_id}"

    payload = json.dumps({
        "fields": {
            "labels": new_labels
        }
    })

    response = requests.put(url, headers=headers, data=payload, timeout=20)

    if response.status_code == 204:
        print(f"Labels updated successfully for ticket {ticket_id}")
        print(f"Updated labels in {ticket_id}: {new_labels}")
    else:
        print(f"Failed to update labels: {response.status_code} - {response.text}")


# Main function to add and remove labels
def manage_labels(ticket_id, add_labels, remove_labels):
    current_labels = get_current_labels(ticket_id)

    if current_labels is None:
        return

    # Remove specified labels
    if remove_labels:
        updated_labels = [label for label in current_labels if label not in remove_labels]
    else:
        updated_labels = current_labels.copy()

    # Add specified labels
    if add_labels:
        updated_labels.extend([label for label in add_labels if label not in updated_labels])

    # Check if updated_labels is different from the current labels
    if updated_labels != current_labels:
        # Update Jira ticket with new labels
        print(f"Current labels in {ticket_id}: {current_labels}")
        update_labels(ticket_id, updated_labels)
    else:
        print(f"No changes needed for ticket {ticket_id}: {current_labels}")


# Command-line argument parser
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update labels for a Jira ticket",
                                     usage="%(prog)s [-h] <ticket_id> --add List --remove List")
    parser.add_argument("ticket_id", help="Jira ticket ID (e.g., JIR-123)")
    parser.add_argument("--add", nargs="*", default=[], help="List of labels to add")
    parser.add_argument("--remove", nargs="*", default=[], help="List of labels to remove")

    args = parser.parse_args()

    # Perform label management
    manage_labels(args.ticket_id, args.add, args.remove)
