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
JIRA_WATCHER_GROUP  = os.getenv('JIRA_WATCHER_GROUP')
JIRA_WATCHERS_LIST  = os.getenv('JIRA_WATCHERS_LIST')

parser = argparse.ArgumentParser(description='Get Jira Epic details by ID.')
parser.add_argument('jira_epic_id', type=str, help='The ID of the Epic')
parser.add_argument('story_file', type=str, help='The file containing the story details')

args = parser.parse_args()
JIRA_EPIC_LINK      = args.jira_epic_id


def create_jira_story(project_key, summary, description, watcher_group, epic_link=None):
    url = f'{JIRA_URL}/rest/api/2/issue'
    headers = {
        'Authorization': f'Bearer {JIRA_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    fields = {
        "fields": {
            "project": {
                "key": project_key
            },
            "issuetype": {
                "name": "Story"
            },
            "summary": summary,
            "description": description,
            "labels": ["TOOL_NAME", "TOOL_NAME_2.5", "Tracking"],
            "priority": {
                "name": "P3"
            },
            "components": [
                {"name": "Commandos"}
            ]
        }
    }

     # Add Epic link if provided
    if epic_link:
        fields["fields"]["customfield_10001"] = epic_link  # Change customfield_10008 to your instance's Epic Link field ID

    if JIRA_WATCHER_GROUP:
        fields["fields"]["customfield_14600"] = [{'name': JIRA_WATCHER_GROUP}]

    payload = fields

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
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
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()  # Raise HTTPError for bad responses
        print(f"Watcher group '{watcher_group}' added to issue {issue_key}")
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while adding watcher group: {http_err}")
        print(f"Response content: {response.content}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred while adding watcher group: {req_err}")


def create_multiple_stories(project_key, watcher_group, stories):
    for story in stories:
        summary = story['summary']
        description = story['description']
        epic_link = story.get('epic_link')
        create_jira_story(project_key, summary, description, watcher_group, epic_link)


def generate_json_structure(file_path):
    stories = []
    with open(file_path, 'r') as file:
        lines = file.readlines()
        if lines:
            summary = lines[0].strip()
            description = ''.join(lines[1:]).strip()
            story = {
                    'summary': summary,
                    'description': description,
                    'epic_link': JIRA_EPIC_LINK
                }
            stories.append(story)
    return stories


stories = generate_json_structure(args.story_file)

create_multiple_stories(JIRA_PROJECT_KEY, JIRA_WATCHER_GROUP, stories)
