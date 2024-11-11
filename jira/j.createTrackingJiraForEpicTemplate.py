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
JIRA_WATCHER_GROUP  = os.getenv('JIRA_WATCHER_GROUP')
JIRA_WATCHERS_LIST  = os.getenv('JIRA_WATCHERS_LIST')

parser = argparse.ArgumentParser(description='Get Jira Epic details by ID.')
parser.add_argument('--epic_id', type=str, required=True, help='The ID of the Epic')
parser.add_argument('--release_ver', type=str, required=True, help='The release version of the Epic')
parser.add_argument('--tool_name', type=str, required=True, help='The tool name of the Epic used for label creation')

args = parser.parse_args()
JIRA_EPIC_LINK      = args.epic_id
JIRA_RELEASE        = args.release_ver
JIRA_TOOL_NAME      = args.tool_name


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
            "labels": [f"{JIRA_TOOL_NAME}", f"{JIRA_TOOL_NAME}_{JIRA_RELEASE}", "Tracking"],
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


def create_multiple_stories(project_key, watcher_group, stories):
    for story in stories:
        summary = story['summary']
        description = story['description']
        epic_link = story.get('epic_link')
        create_jira_story(project_key, summary, description, watcher_group, epic_link)


generate_stories = [
    {
        'summary': '[Tracking] Update Version and Request Production Build Enablement',
        'description': 'This task is to track the code changes required to update the version.\n\nRequest the production build enablement after the changes.',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': '[Tracking] Update Confluence page and Technote for \"How to perform migration\"',
        'description': 'This Jira ticket is to track the work regarding TechNote update task for this release.',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': f"[Tracking] Threat Modeling and Threat analysis for {JIRA_TOOL_NAME}",
        'description': 'Please check whether any new threats are being introduced.\nAdditionally, verify that the current models address all the newly discovered threats.',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': f"[Tracking] Check EULA Year for {JIRA_TOOL_NAME}",
        'description': 'This Jira ticket is to track the work regarding the EULA Year of this release.',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': f"[Tracking] TechNote for {JIRA_TOOL_NAME}",
        'description': 'This Jira ticket is to track the work regarding TechNotes of this release.',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': '[Tracking] Remove Beta Tag for Release',
        'description': 'The Beta tag needs to be removed when the binaries are release-ready.',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': f"[Tracking] Documentation for {JIRA_TOOL_NAME}",
        'description': 'This ticket is intended to track the work related to the documentation for this release.',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': f"[Tracking] {JIRA_TOOL_NAME} GA build testing",
        'description': 'This ticket has been created to track testing activities for the GA build.',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': f"[Tracking] Validate {JIRA_TOOL_NAME} bundle is available for download from the Download Centre.",
        'description': 'To validate that the correct NBServerMigrtator binaries are uploaded to Download centre (DC).',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': '[Tracking] Horizon Test plan and report.',
        'description': 'This ticket is to generate the Horizon test plan and report to meet 100/100/0 criteria.',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': '[Tracking] OSRB Approval for this release',
        'description': 'This task is to track the BlackDuck scan activity and obtain OSRB approval.',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': '[Tracking] CSTS Enablement Document Update',
        'description': 'This task is to track the CSTS Enablement document update related progress',
        'epic_link': JIRA_EPIC_LINK
    },
    {
        'summary': '[Tracking] Demo Recording for current Epic.',
        'description': 'This task is to track the demo recording progress.',
        'epic_link': JIRA_EPIC_LINK
    },
    # Add more stories as needed
]


create_multiple_stories(JIRA_PROJECT_KEY, JIRA_WATCHER_GROUP, generate_stories)
