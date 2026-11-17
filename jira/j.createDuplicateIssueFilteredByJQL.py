#!/usr/bin/env python3
# pip install requests
# pip install python-dotenv
import os
import sys
import json
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jira_api import load_config, get, post, search_all_issues, search_all_or_fail

cfg = load_config()

# Jira credentials and URL
JIRA_URL = cfg.base_url

# JQL query to filter issues
JQL_QUERY = 'labels = Tracking and labels = NBServerMigrator_2.4'

# New label to be added to cloned issues
NEW_LABEL = 'Cloned'


# Function to get issues by JQL
def get_issues_by_jql(jql):

    try:
        # Cloud-compatible search (nextPageToken on Cloud, startAt on Server)
        # Returns [] only when the search succeeded with 0 issues (hints are printed).
        return search_all_or_fail(
            jql, fields='*all', expand='', page_size=100,
            context="Issue search", on_empty="return",
        )

    except (requests.exceptions.RequestException, RuntimeError) as e:
        # Do NOT treat a failed search as "no issues".
        print(f"Error fetching issues: {e}", file=sys.stderr)
        sys.exit(1)


# Function to clone an issue
def clone_issue(issue):

    issue_key = issue['key']
    url = f'{JIRA_URL}/rest/api/2/issue/{issue_key}/clone'
    clone_payload = {
        'fields': {
            'labels': issue['fields']['labels'] + [NEW_LABEL]
        }
    }
    response = post(url,
                    data=json.dumps(clone_payload),
                    timeout=20)
    if response.status_code == 201:
        print(f"Issue {issue_key} cloned successfully.")
    else:
        print(f"Failed to clone issue {issue_key}. Response: {response.text}")


def create_issue(issue_details):
    url = f'{JIRA_URL}/rest/api/2/issue'

    try:
        response = post(url,
                         data=json.dumps(issue_details),
                         timeout=20)
        response.raise_for_status()  # Raise HTTPError for bad responses
        print("Issue created successfully.")
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.content}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")

    return None


def fetch_issue_and_create_new(issue):
    issue_key = issue['key']
    url = f'{JIRA_URL}/rest/api/2/issue/{issue_key}'

    response = get(url, timeout=20)
    issue_details = response.json()

    # Create a new issue using fetched details
    if issue_details:
        del issue_details['id']   # Remove id to create a new issue
        del issue_details['key']  # Remove key to create a new issue

        issue_details['fields']['labels'].append('COPIED_BY_API')

        created_issue = create_issue(issue_details)
        if created_issue:
            print(f"New issue created with key: {created_issue['key']}")


# Main function
def main():

    issues = get_issues_by_jql(JQL_QUERY)

    if not issues:
        print("No issues found.", file=sys.stderr)
        sys.exit(2)

    for issue in issues:
        print("Cloning issue " + issue['key'])
        fetch_issue_and_create_new(issue)


if __name__ == '__main__':
    main()
