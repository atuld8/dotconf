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
board_url = f'{JIRA_URL}/rest/agile/1.0/board'

# Headers
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}


def get_board_id(board_name):
    """Fetch the board ID using the board name."""

    url = f'{board_url}?name={board_name}'
    response = requests.get(url, headers=headers, timeout=20)

    if response.status_code == 200:
        boards = response.json().get('values', [])
        if boards:
            board_id = boards[0].get('id')
            print(f"Board ID for '{board_name}' is: {board_id}\n")
            return board_id

        print(f"No board found with name: {board_name}")

    else:
        print(f"Error fetching board ID: {response.status_code} - {response.text}")

    return None


def get_sprints(board_id):
    """Fetch all sprints for a given board ID."""
    url = f'{board_url}/{board_id}/sprint?state=active'
    response = requests.get(url, headers=headers, timeout=20)

    if response.status_code == 200:
        return response.json().get('values', [])

    print(f"Error fetching sprints: {response.status_code} - {response.text}")
    return []


def get_active_sprint(board_id):
    """Find and return the ID of the active sprint."""
    sprints = get_sprints(board_id)
    for sprint in sprints:
        if sprint['state'] == 'active':
            print(f"Active Sprint Name: {sprint['name']} Sprint Id: {sprint['id']}\n")

            return sprint['id']

    print("No active sprint found.")
    return None


def get_field_id(field_name):
    """Fetch the field ID using the field name."""
    url = f'{JIRA_URL}/rest/api/2/field'

    try:
        response = requests.get(url, headers=headers, timeout=20)

        if response.status_code == 200:
            try:
                fields = response.json()

                for field in fields:
                    if field['name'].lower() == field_name.lower():
                        field_id = field['id']
                        print(f"Field ID for '{field_name}' is: {field_id}\n")
                        return field_id

            except ValueError as e:
                print(f"Error parsing JSON response: {e}")

            print(f"No field found with name: {field_name}")

        else:
            print(f"Error fetching field ID: {response.status_code} - {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")

    return None


def update_issue_sprint(issue_key, sprint_id):
    """Update the sprint field of a Jira issue."""
    url = f'{issue_url}/{issue_key}'

    # Replace with your field name
    field_name = "Sprint"
    sprint_fid = get_field_id(field_name)

    if sprint_fid is not None:
        payload = json.dumps({
            "fields": {
                sprint_fid: sprint_id  # Ensure you use the correct field for sprint
            }
        })

        print(f"{payload}")
        response = requests.put(url, headers=headers, timeout=20, data=payload)
        if response.status_code == 204:
            print(f"Sprint updated successfully for issue {issue_key}.")
        else:
            print(f"Failed to update sprint. \
                    Status code: {response.status_code}, \
                    Response: {response.text}")


# Main function to add and remove labels
def update_sprint(ticket_id, board, sprint):

    """
    ${1:Description of the function or method.}

    Parameters:
    ${2:param} (${3:type}): ${4:Description of the parameter.}

    Returns:
    ${5:type}: ${6:Description of the return value.}
    """
    if not board:
        board = os.getenv('JIRA_BOARD_NAME')
        print(f"Board was not passed. Read from the enviornment: {board}")

    board_id = get_board_id(board)
    if board_id is not None:

        active_sprint_id = get_active_sprint(board_id)
        if active_sprint_id:
            update_issue_sprint(ticket_id, active_sprint_id)
        else:
            print("No active sprint to update the issue with.")


# Command-line argument parser
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update labels for a Jira ticket")
    parser.add_argument("ticket_id", help="Jira ticket ID (e.g., JIR-123)")
    parser.add_argument("--board", default=None, help="Board Name")
    parser.add_argument("--sprint", default=None, help="Sprint Name")

    args = parser.parse_args()

    # Perform label management
    update_sprint(args.ticket_id, args.board, args.sprint)
