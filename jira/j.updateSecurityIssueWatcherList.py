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
JIRA_SEC_ISSUE_WATCHER = "customfield_15901"

parser = argparse.ArgumentParser(description='Get Jira Epic details by ID.')
parser.add_argument('jira_id', type=str, help='The ID of the Jira')
parser.add_argument('jira_sec_issue_watcher', type=str, help='The security issue watcher name/id')

args = parser.parse_args()
JIRA_ISSUE_ID      = args.jira_id
JIRA_NEW_WATCHER   = args.jira_sec_issue_watcher

# Jira API endpoint for updating assignee
url = f'{JIRA_URL}/rest/api/2/issue/{JIRA_ISSUE_ID}'

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
response = requests.get(url, headers=headers) #, data=json.dumps(payload))

# Check the response
if response.status_code == 200:
    print(f'Successfully received data for the issue {JIRA_ISSUE_ID}')
else:
    print(f'Failed to receive data for the issue. Status code: {response.status_code}, Response: {response.text}')
    sys.exit()

current_watchers = issue_details['fields'].get(JIRA_SEC_ISSUE_WATCHER, [])

# Add the new watcher if not already present
if JIRA_NEW_WATCHER not in current_watchers:
    current_watchers.append(new_watcher)
else:
    print(f'{new_watcher} is already in the security watcher list.')
    sys.exit()

print(current_watchers)
