#!/usr/bin/env python3.12
import os
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

parser = argparse.ArgumentParser(description='Get Jira Epic details by ID.')
parser.add_argument('jira_id', type=str, help='The ID of the Jira')
parser.add_argument('jira_assignee', type=str, help='The assingnee name/id')

args = parser.parse_args()
JIRA_ISSUE_ID      = args.jira_id
JIRA_ASSIGNEE      = args.jira_assignee

# Jira API endpoint for updating assignee
url = f'{JIRA_URL}/rest/api/2/issue/{JIRA_ISSUE_ID}/assignee'

# Headers
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}

# Payload
payload = {
    'name': JIRA_ASSIGNEE
}

# Make the PUT request to update the assignee
response = requests.put(url, headers=headers, data=json.dumps(payload))

# Check the response
if response.status_code == 204:
    print(f'Successfully updated the assignee for issue {JIRA_ISSUE_ID} to {JIRA_ASSIGNEE}')
else:
    print(f'Failed to update the assignee. Status code: {response.status_code}, Response: {response.text}')
