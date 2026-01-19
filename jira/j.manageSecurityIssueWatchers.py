#!/usr/bin/env python3
import os
import sys
import argparse
import json
import requests
from dotenv import load_dotenv

# Load the environment variables configured on the system
load_dotenv()

# Jira credentials and URL
JIRA_SERVER_NAME = os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN   = os.getenv('JIRA_ACC_TOKEN')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY')

if not JIRA_SERVER_NAME or not JIRA_API_TOKEN or not JIRA_PROJECT_KEY:
    raise EnvironmentError(
        "One or more required environment variables are missing: "
        "JIRA_SERVER_NAME, JIRA_ACC_TOKEN, JIRA_PROJECT_KEY"
    )

JIRA_URL = f"https://{JIRA_SERVER_NAME}"

JIRA_SEC_ISSUE_WATCHER_CUST_ID = "customfield_33432"

# Headers
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}


# Function to get the securirty watchers list for the Jira id
def get_current_sec_issue_watcher_list(ticket_id):
    """
    Fetches the current list of security issue watchers for a given Jira ticket.

    Args:
        ticket_id (str): The ID of the Jira ticket to retrieve watcher information for.

    Returns:
        list: A list of current watchers associated with the security issue custom field.

    Raises:
        SystemExit: If the request to the Jira API fails (non-200 status code).

    Side Effects:
        Prints status messages indicating success or failure of the API request.
    """

    # Jira API endpoint for updating assignee
    issue_url = f'{JIRA_URL}/rest/api/2/issue/{ticket_id}'

    # Make the get request to get issue details
    response = requests.get(issue_url, headers=headers, timeout=20)

    # Check the response
    if response.status_code == 200:
        print(f'Successfully received data for the issue {ticket_id}')
    else:
        print(
            f'Failed to receive data for the issue. '
            f'Status code: {response.status_code}, '
            f'Response: {response.text}'
        )
        sys.exit()

    issue_details = response.json()
    current_watchers = issue_details['fields'].get(JIRA_SEC_ISSUE_WATCHER_CUST_ID, [])

    return current_watchers


# Function to get the user details
def get_user_details(user):
    """
    Fetches the details of a specified user from the JIRA API.

    Args:
        user (str): The username of the user whose details are to be retrieved.

    Returns:
        dict: A dictionary containing the user's details as returned by the JIRA API.

    Raises:
        SystemExit: If the API request fails (i.e., response status code is not 200).
    """

    user_url  = f'{JIRA_URL}/rest/api/2/user?username={user}'

    # Make the get request to get user details
    response = requests.get(user_url, headers=headers, timeout=20)

    # Check the response
    if response.status_code == 200:
        print(f'Successfully received data for the user {user}')
    else:
        print(
            f'Failed to receive data for the user {user}. '
            f'Status code: {response.status_code}, '
            f'Response: {response.text}'
        )
        sys.exit()

    user_details = response.json()

    return user_details


# Function to update watcher list by removing entries
def delete_watchers_from_list(watcher_list, remove_list):
    """
    Removes watchers from the given watcher list based on a list of users to remove.

    Args:
        watcher_list (list): A list of watcher dictionaries, each containing at least 'self' and 'name' keys.
        remove_list (list): A list of user identifiers (e.g., usernames) to be removed from the watcher list.

    Returns:
        list: The updated watcher list with specified users removed.

    Note:
        This function relies on an external function `get_user_details(user)` that should return a dictionary
        with at least 'self' and 'name' keys for the given user.
    """
    # Check if the new watcher is already in the list
    watcher_urls = [watcher['self'] for watcher in watcher_list]

    for user in remove_list:
        user_details = get_user_details(user)

        if user_details['self'] in watcher_urls[:]:
            print(f"{user_details['name']} : {user_details['self']} is matched. Detele it")

            print(f"Removing {user_details['name']} : {user_details['self']} to the security watcher list.")

            # Remove
            watcher_list = [watcher for watcher in watcher_list if watcher["name"] != user_details["name"]]

    return watcher_list


# Function to update watcher list by adding entries
def add_watchers_to_list(watcher_list, add_list):
    """
    Adds new watchers to the existing watcher list if they are not already present.

    Args:
        watcher_list (list): A list of dictionaries representing current watchers. Each dictionary must contain a 'self' key with the watcher's unique URL.
        add_list (list): A list of user identifiers (e.g., usernames) to be added as watchers.

    Returns:
        list: The updated watcher list including any new watchers added.

    Notes:
        - Uses the get_user_details(user) function to retrieve user details for each user in add_list.
        - Prints a message for each user indicating whether they were added or already present.
    """
    # Check if the new watcher is already in the list
    watcher_urls = [watcher['self'] for watcher in watcher_list]

    for user in add_list:
        user_details = get_user_details(user)

        if user_details['self'] in watcher_urls:
            print(
                f"{user_details['name']} : {user_details['self']} "
                "is already in the security watcher list."
            )
            continue

        print(
            f"Adding {user_details['name']} : {user_details['self']} "
            "to the security watcher list."
        )
        # Add the new watcher to the list
        watcher_list.append(user_details)

    return watcher_list

# Function to update the watcher list in ticket
def update_ticket_with_final_list(ticket_id, final_watcher_list):
    # Jira API endpoint for updating assignee
    issue_url = f'{JIRA_URL}/rest/api/2/issue/{ticket_id}'

    data = {
        "fields": {
            JIRA_SEC_ISSUE_WATCHER_CUST_ID: final_watcher_list
        }
    }

    response = requests.put(issue_url, headers=headers,
                            data=json.dumps(data), timeout=20)
    if response.status_code == 204:
        final_watcher_name_list = [watcher["name"] for watcher in final_watcher_list]
        print(f'{final_watcher_name_list} has been set to the security watcher list.')
    else:
        print(f'Failed to update security watcher: {response.status_code} {response.text}')


# Function to update the security watchers list for the Jira id
def update_watchers(args):
    """
    Update the security watchers for Jira issues.

    Args:
        args (Namespace): Command-line arguments containing:
            - jira_ids (list of str): List of Jira issue IDs.
            - add (list of str): List of users to add as watchers.
            - remove (list of str): List of users to remove from watchers.
            - dry_run (bool): Flag to skip calling the update method (dry run).
    """
    add_list = args.add
    remove_list = args.remove
    dry_run = args.dry_run

    for ticket_id in args.jira_ids:
        print(f"\n{'='*60}")
        print(f"Processing {ticket_id}")
        print(f"{'='*60}")

        original_watcher_list = get_current_sec_issue_watcher_list(ticket_id)

        watcher_list_after_delete = delete_watchers_from_list(original_watcher_list[:], remove_list)

        watcher_list_after_add = add_watchers_to_list(watcher_list_after_delete, add_list)

        original_watchers_name = [watcher["name"] for watcher in original_watcher_list]
        print(f"\n\nList of watchers before update : {original_watchers_name}")

        final_watcher_names = [watcher["name"] for watcher in watcher_list_after_add]
        print(f"List of watchers after update  : {final_watcher_names}")

        if not dry_run:
            if set(original_watchers_name) != set(final_watcher_names):
                update_ticket_with_final_list(ticket_id, watcher_list_after_add)
            else:
                print("\nNothing to update as both list are identicals.")
        print()  # Add blank line between issues



def print_watchers(args):
    """
    Prints the list of current security watchers for specified JIRA issues.

    Args:
        args (Namespace):
            An object containing command-line arguments, expected to have a 'jira_ids' attribute.

    Returns:
        None
    """
    for jira_id in args.jira_ids:
        current_watchers = get_current_sec_issue_watcher_list(jira_id)
        watcher_names = [watcher["name"] for watcher in current_watchers]
        print(f"Current security watchers for {jira_id}: {watcher_names}")
        print()  # Add blank line between issues


def parse_jira_watchers_args():
    """
    Parses command-line arguments for managing Jira issue watchers.

    Returns:
        argparse.Namespace: Parsed arguments containing:
            jira_ids (list of str): List of Jira issue IDs.
            add (list of str): List of users to add as watchers.
            remove (list of str): List of users to remove from watchers.
            list (bool): Flag to display the list of existing watchers.
            dry_run (bool): Flag to skip calling the update method (dry run).
    """
    parser = argparse.ArgumentParser(
        description=(
            'Get Jira Epic details by ID. '
            '<script> '
            '-j XXX-1234 XXX-5678 '
            '-a add.user3 add.user4 '
            '-r remove.user1 remove.user2 '
            '-d -l'
        )
    )
    parser.add_argument(
        "-j", "--jira-ids",
        nargs="+",
        required=True,
        dest="jira_ids",
        help="List of Jira IDs to process")
    parser.add_argument(
        "-a", "--add",
        nargs="*",
        default=[],
        help="List of Users to add")
    parser.add_argument(
        "-r", "--remove",
        nargs="*",
        default=[],
        help="List of Users to remove")
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="Display the list of existing watchers")
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Skip calling the update method")

    parsed_args = parser.parse_args()

    # If no operation flags are passed, default to --list
    if not (parsed_args.add or parsed_args.remove or parsed_args.list):
        parsed_args.list = True

    return parsed_args

# Main function to execute the script
if __name__ == "__main__":

    args = parse_jira_watchers_args()

    if args.list:
        print_watchers(args)
    else:
        update_watchers(args)
