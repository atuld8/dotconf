#!/usr/bin/env python3.12
import os
import sys
import argparse
import requests
import json
from dotenv import load_dotenv

# Load the environment variables configured on the system
load_dotenv()

# Jira credentials and URL
JIRA_URL            = "https://" + os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN      = os.getenv('JIRA_ACC_TOKEN')
JIRA_PROJECT_KEY    = os.getenv('JIRA_PROJECT_KEY')

JIRA_SEC_ISSUE_WATCHER_CUST_ID = "customfield_15901"

parser = argparse.ArgumentParser(description='Get Jira Epic details by ID.')
parser.add_argument('jira_id', type=str, help='The ID of the Jira')
parser.add_argument('jira_sec_issue_watcher', type=str, help='The security issue watcher name/id')

args = parser.parse_args()
JIRA_ISSUE_ID      = args.jira_id
JIRA_NEW_WATCHER   = args.jira_sec_issue_watcher

# Jira API endpoint for updating assignee
issue_url = f'{JIRA_URL}/rest/api/2/issue/{JIRA_ISSUE_ID}'
user_url  = f'{JIRA_URL}/rest/api/2/user?username={JIRA_NEW_WATCHER}'

# Headers
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}


# Make the get request to get issue details
response = requests.get(issue_url, headers=headers, timeout=20)

# Check the response
if response.status_code == 200:
    print(f'Successfully received data for the issue {JIRA_ISSUE_ID}')
else:
    print(f'Failed to receive data for the issue. Status code: {response.status_code}, Response: {response.text}')
    sys.exit()

issue_details = response.json()
current_watchers = issue_details['fields'].get(JIRA_SEC_ISSUE_WATCHER_CUST_ID, [])


# Make the get request to get user details
response = requests.get(user_url, headers=headers, timeout=20)

# Check the response
if response.status_code == 200:
    print(f'Successfully received data for the user {JIRA_NEW_WATCHER}')
else:
    print(f'Failed to receive data for the user. Status code: {response.status_code}, Response: {response.text}')
    sys.exit()

new_user_details = response.json()


# Check if the new watcher is already in the list
watcher_urls = [watcher['self'] for watcher in current_watchers]
if new_user_details['self'] in watcher_urls:
    print(f"{new_user_details['name']} : {new_user_details['self']} is already in the security watcher list.")
    sys.exit()

watcher_before_update_names = [watcher['name'] for watcher in current_watchers]

print(f"Adding {new_user_details['name']} : {new_user_details['self']} to the security watcher list.")
# Add the new watcher to the list
current_watchers.append(new_user_details)

data = {
    "fields": {
        JIRA_SEC_ISSUE_WATCHER_CUST_ID: current_watchers
    }
}

response = requests.put(issue_url, headers=headers,
                        data=json.dumps(data), timeout=20)
if response.status_code == 204:
    print(f'{JIRA_NEW_WATCHER} has been added to the security watcher list.')
else:
    print(f'Failed to update security watcher: {response.status_code} {response.text}')


# Make the get request to get issue details
response = requests.get(issue_url, headers=headers, timeout=20)

# Check the response
if response.status_code == 200:
    print(f'Successfully received data for the issue {JIRA_ISSUE_ID}')
else:
    print(f'Failed to receive data for the issue. Status code: {response.status_code}, Response: {response.text}')
    sys.exit()

issue_details = response.json()
current_watchers = issue_details['fields'].get(JIRA_SEC_ISSUE_WATCHER_CUST_ID, [])

watcher_after_update_names = [watcher['name'] for watcher in current_watchers]

print(f"List of watchers before update : {watcher_before_update_names}")
print(f"List of watchers after update  : {watcher_after_update_names}")
