#!/usr/bin/env python3.12
import os
import argparse
import requests
from tabulate import tabulate
from dotenv import load_dotenv

# Load the environment variables configured on the system
load_dotenv()

# Jira credentials and URL
JIRA_URL            = "https://" + os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN      = os.getenv('JIRA_ACC_TOKEN')
JIRA_PROJECT_KEY    = os.getenv('JIRA_PROJECT_KEY')

parser = argparse.ArgumentParser(description='Get Jira user name details.')
parser.add_argument('jira_user_str', type=str, help='The user string of the Jira')

args = parser.parse_args()
JIRA_ASSIGNEE_NAME      = args.jira_user_str

# Jira API endpoint for updating assignee
url = f'{JIRA_URL}/rest/api/2/user/search?username={JIRA_ASSIGNEE_NAME}'

print(url)
# Headers
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}

# Make the PUT request to update the assignee
response = requests.get(url, headers=headers, timeout=20)

# Check the response
if response.status_code == 200:
    try:
        users = response.json()
        if users:
            print(f"\n\nUser ID (accountId) for {JIRA_ASSIGNEE_NAME}")
            table = []
            for user in users:
                table.append([user['key'], user['name'], user.get('emailAddress', 'N/A')])

            # Print table
            print(tabulate(table, headers=['Key', 'Name', 'Email-Address']))
        else:
            print(f"No users found for query {JIRA_ASSIGNEE_NAME}")
    except requests.exceptions.JSONDecodeError as e:
        print(f'Error decoding JSON: {e}')
else:
    print(f'Failed to retrive user data for user string {JIRA_ASSIGNEE_NAME}')
