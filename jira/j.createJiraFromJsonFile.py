#!/usr/bin/env python3.12
import os
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
JIRA_WATCHER_GROUP  = os.getenv('JIRA_WATCHER_GROUP')
JIRA_WATCHERS_LIST  = os.getenv('JIRA_WATCHERS_LIST')

DRY_RUN = False


def create_jira_story(project_key, summary, description, assignee, generic_data):

    url = f'{JIRA_URL}/rest/api/2/issue'
    headers = {
        'Authorization': f'Bearer {JIRA_API_TOKEN}',
        'Content-Type': 'application/json'
    }

    labels_array = generic_data["labels"]
    priority = generic_data["priority"]
    watcher_group = generic_data["watcher_group"]
    epic_link = generic_data["epic_link"]
    issue_type = generic_data["issue_type"]

    fields = {
        "fields": {
            "project": {
                "key": project_key
            },
            "issuetype": {
                "name": issue_type
            },
            "summary": summary,
            "description": description,
            "labels": labels_array,
            "priority": {
                "name": priority
            },
            "components": [
                {"name": "Commandos"}
            ]
        }
    }

    if assignee:
        fields["fields"]["assignee"] = {"name": assignee}

    # Add Epic link if provided
    if epic_link:
        fields["fields"]["customfield_10001"] = epic_link  # Change customfield_10008 to your instance's Epic Link field ID

    if JIRA_WATCHER_GROUP:
        fields["fields"]["customfield_14600"] = [{'name': JIRA_WATCHER_GROUP}]

    if watcher_group:
        fields["fields"]["customfield_14600"] = [{'name': watcher_group}]

    payload = fields

    print(payload)
    if DRY_RUN:
        return

    try:
        response = requests.post(url, headers=headers,
                                 data=json.dumps(payload), timeout=20)
        response.raise_for_status()  # Raise HTTPError for bad responses
        issue = response.json()
        print(f"Jira story created successfully with key: {issue['key']}")

        # Add watcher groups to the issue
        # add_watcher_list({JIRA_URL}, {JIRA_API_TOKEN}, issue['key'], {JIRA_WATCHERS_LIST})

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.content}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")


def add_watcher_group(jira_url, api_token, issue_key, watcher_group):
    url = f'{jira_url}/rest/api/2/issue/{issue_key}/watchers'
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }
    payload = json.dumps(watcher_group)

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=20)
        response.raise_for_status()  # Raise HTTPError for bad responses
        print(f"Watcher group '{watcher_group}' added to issue {issue_key}")
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while adding watcher group: {http_err}")
        print(f"Response content: {response.content}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred while adding watcher group: {req_err}")


def create_multiple_stories(project_key, stories, generic_data):
    for story in stories:
        summary = story['summary']
        description = story['description']
        assignee = story['assignee']
        create_jira_story(project_key, summary, description, assignee, generic_data)


def main():
    global DRY_RUN

    parser = argparse.ArgumentParser(description='Get Jira Epic details by ID.')
    parser.add_argument('-j', '--json-file', type=str, required=True, help='Json file \
                        which has all the story related details')
    parser.add_argument('-d', '--dry-run', action="store_true", help='Skip calling of Rest API')

    args = parser.parse_args()
    json_file = args.json_file
    DRY_RUN = args.dry_run

    # Read the JSON file
    with open(json_file, "r") as file:
        data = json.load(file)

    # Extract generic fields and multiple entries
    generic_data = data["Generic_field"]
    multiple_entries = data["Multiple_entries"]

    create_multiple_stories(JIRA_PROJECT_KEY, multiple_entries, generic_data)


if __name__ == "__main__":
    main()
