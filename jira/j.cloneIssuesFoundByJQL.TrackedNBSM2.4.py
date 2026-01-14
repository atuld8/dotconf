#!/usr/bin/env python3
# pip install requests
# pip install python-dotenv
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Jira credentials and URL
JIRA_URL = "https://" + os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN = os.getenv('JIRA_ACC_TOKEN')

# JQL query to filter issues
JQL_QUERY = 'labels = Tracking and labels = NBServerMigrator_2.4'

# New label to be added to cloned issues
NEW_LABEL = 'Cloned'

# Headers for authentication and content type
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}


# Function to get issues by JQL
def get_issues_by_jql(jql):

    try:
        url = f'{JIRA_URL}/rest/api/2/search'
        params = {
            'jql': jql,
        }
        response = requests.get(url, headers=headers, params=params, timeout=20)

        response.raise_for_status()  # Raises an HTTPError if the response code was unsuccessful

        return response.json().get('issues', [])

    except requests.exceptions.RequestException as e:

        print(f"Error fetching issues: {e}")
        return []


# Function to clone an issue
def clone_issue(issue):

    issue_key = issue['key']
    url = f'{JIRA_URL}/rest/api/2/issue/{issue_key}/clone'
    clone_payload = {
        'fields': {
            'labels': issue['fields']['labels'] + [NEW_LABEL]
        }
    }
    response = requests.post(url, headers=headers, data=json.dumps(clone_payload), timeout=20)
    if response.status_code == 201:
        print(f"Issue {issue_key} cloned successfully.")
    else:
        print(f"Failed to clone issue {issue_key}. Response: {response.text}")


# Main function
def main():

    issues = get_issues_by_jql(JQL_QUERY)

    if not issues:
        print("No issues found.")
        return

    for issue in issues:
        print("Cloning issue issue['key']")
        clone_issue(issue)


if __name__ == '__main__':
    main()
