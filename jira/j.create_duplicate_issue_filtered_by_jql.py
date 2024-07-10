# pip install requests
# pip install python-dotenv
import os
import requests
import json
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
        response = requests.get(url, headers=headers, params=params)

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
    response = requests.post(url, headers=headers, data=json.dumps(clone_payload))
    if response.status_code == 201:
        print(f"Issue {issue_key} cloned successfully.")
    else:
        print(f"Failed to clone issue {issue_key}. Response: {response.text}")


def create_issue(issue_details):
    url = f'{JIRA_URL}/rest/api/2/issue'

    try:
        response = requests.post(url, headers=headers, data=json.dumps(issue_details))
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

    response = requests.get(url, headers=headers)
    issue_details = response.json()

    # Create a new issue using fetched details
    if issue_details:
        del issue_details['id']  # Remove id to create a new issue
        del issue_details['key'] # Remove key to create a new issue

        issue_details['fields']['labels'].append('COPIED_BY_API')

        created_issue = create_issue(issue_details)
        if created_issue:
            print(f"New issue created with key: {created_issue['key']}")


# Main function
def main():

    issues = get_issues_by_jql(JQL_QUERY)

    if not issues:
        print(f"No issues found.")
        return

    for issue in issues:
        print(f"Cloning issue " + issue['key'])
        fetch_issue_and_create_new(issue)


if __name__ == '__main__':
    main()
