#!/usr/bin/env python3.12
import os
import sys
import argparse
import json
import requests
from dotenv import load_dotenv

# Load the environment variables configured on the system
load_dotenv()

# Jira credentials and URL
JIRA_URL            = "https://" + os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN      = os.getenv('JIRA_ACC_TOKEN')
JIRA_PROJECT_KEY    = os.getenv('JIRA_PROJECT_KEY')

JIRA_SEC_ISSUE_WATCHER_CUST_ID = "customfield_15901"

# Headers
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}


# Function to get the securirty watchers list for the Jira id
def get_current_sec_issue_watcher_list(ticket_id):

    # Jira API endpoint for updating assignee
    issue_url = f'{JIRA_URL}/rest/api/2/issue/{ticket_id}'

    # Make the get request to get issue details
    response = requests.get(issue_url, headers=headers, timeout=20)

    # Check the response
    if response.status_code == 200:
        print(f'Successfully received data for the issue {ticket_id}')
    else:
        print(f'Failed to receive data for the issue. Status code: {response.status_code}, Response: {response.text}')
        sys.exit()

    issue_details = response.json()
    current_watchers = issue_details['fields'].get(JIRA_SEC_ISSUE_WATCHER_CUST_ID, [])

    return current_watchers


# Function to get the user details
def get_user_details(user):

    user_url  = f'{JIRA_URL}/rest/api/2/user?username={user}'

    # Make the get request to get user details
    response = requests.get(user_url, headers=headers, timeout=20)

    # Check the response
    if response.status_code == 200:
        print(f'Successfully received data for the user {user}')
    else:
        print(f'Failed to receive data for the user {user}. Status code: {response.status_code}, Response: {response.text}')
        sys.exit()

    user_details = response.json()

    return user_details


# Function to update watcher list by removing entries
def delete_watchers_from_list(watcher_list, remove_list):
    # Check if the new watcher is already in the list
    watcher_urls = [watcher['self'] for watcher in watcher_list]
    watcher_updated_list = []

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
    # Check if the new watcher is already in the list
    watcher_urls = [watcher['self'] for watcher in watcher_list]

    for user in add_list:
        user_details = get_user_details(user)

        if user_details['self'] in watcher_urls:
            print(f"{user_details['name']} : {user_details['self']} is already in the security watcher list.")
            continue

        print(f"Adding {user_details['name']} : {user_details['self']} to the security watcher list.")
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
def update_watchers(ticket_id, add_list, remove_list, dry_run):

    original_watcher_list = get_current_sec_issue_watcher_list(ticket_id)

    watcher_list_after_delete = delete_watchers_from_list(original_watcher_list[:], remove_list)

    watcher_list_after_add = add_watchers_to_list(watcher_list_after_delete, add_list)

    original_watchers_name = [watcher["name"] for watcher in original_watcher_list]
    print(f"\n\nList of watchers before update : {original_watchers_name}")

    final_watcher_names = [watcher["name"] for watcher in watcher_list_after_add]
    print(f"List of watchers after update  : {final_watcher_names}")

    if dry_run == False:
       if set(original_watchers_name) != set(final_watcher_names):
            update_ticket_with_final_list(ticket_id, watcher_list_after_add)
       else:
            print("\nNothing to update as both list are identicals.")



# Main
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Get Jira Epic details by ID. <script> XXX-1234 -a add.user3 add.user4 -r remove.user1 remove.user2 -d') 
    parser.add_argument('jira_id', type=str, help='The ID of the Jira')
    parser.add_argument('-a', "--add", nargs="*", default=[], help="List of Users to add")
    parser.add_argument("-r", "--remove", nargs="*", default=[], help="List of Users to remove")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Skip calling the update method")

    args = parser.parse_args()

    update_watchers(args.jira_id, args.add, args.remove, args.dry_run)