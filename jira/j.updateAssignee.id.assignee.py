#!/usr/bin/env python3
import os
import sys
import argparse
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jira_api import load_config, put

cfg = load_config()

# Jira credentials and URL
JIRA_PROJECT_KEY    = os.getenv('JIRA_PROJECT_KEY')

parser = argparse.ArgumentParser(description='Get Jira Epic details by ID.')
parser.add_argument('jira_id', type=str, help='The ID of the Jira')
parser.add_argument('jira_assignee', type=str, help='The assingnee name/id')

args = parser.parse_args()
JIRA_ISSUE_ID      = args.jira_id
JIRA_ASSIGNEE      = args.jira_assignee

# Jira API endpoint for updating assignee
url = f'rest/api/2/issue/{JIRA_ISSUE_ID}/assignee'

# Payload: Cloud identifies users by accountId, Server/DC by name
if cfg.is_cloud:
    payload = {'accountId': JIRA_ASSIGNEE}
else:
    payload = {'name': JIRA_ASSIGNEE}

# Make the PUT request to update the assignee
response = put(url, data=json.dumps(payload), timeout=20)

# Check the response
if response.status_code == 204:
    print(f'Successfully updated the assignee for issue {JIRA_ISSUE_ID} to {JIRA_ASSIGNEE}')
else:
    print(f'Failed to update the assignee. Status code: {response.status_code}, Response: {response.text}')
