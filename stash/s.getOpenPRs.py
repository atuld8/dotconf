#!/usr/bin/env python3.12
import json
import os
import argparse
import requests
from dotenv import load_dotenv


# Load the environment variables configured on the system
load_dotenv()

# Jira credentials and URL
GIT_URL            = "https://" + os.getenv('GIT_SERVER')
GIT_USER           = os.getenv('GIT_USER')
GIT_PASSWORD       = os.getenv('GIT_TOKEN')
GIT_PROJECT        = os.getenv('GIT_PROJECT')


# Jira API endpoint for updating assignee
repos_url = f'{GIT_URL}/rest/api/1.0/projects/{GIT_PROJECT}/repos'

# Headers
headers = {
    'Authorization': f'Bearer {GIT_PASSWORD}',
    'Content-Type': 'application/json'
}

# Param
params = {"state": "OPEN"}

# Function to get the current labels of a Jira issue
def get_pull_request_list(repo_name):
    url = f"{repos_url}/{repo_name}/pull-requests"
    response = requests.get(url, headers=headers, params=params, timeout=20)

    if response.status_code == 200:
        try:
            pr_data = response.json()
            pr_list = pr_data.get("values", [])

            if not pr_list:
                print("No open pull requests found.")
                return []

            print(f"Found {len(pr_list)} open PR(s):")
            for pr in pr_list:
                print(f"- PR #{pr['id']}: {pr['title']} (Created by {pr['author']['user']['displayName']})")

            return pr_list

        except requests.exceptions.JSONDecodeError as e:
            print(f'Error decoding JSON: {e}')
    else:
        print(f"Failed to fetch issue details: {response.status_code} - {response.text}")

    return None


# Command-line argument parser
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get list of open PR for mentioned repository",
                                     usage="%(prog)s [-h] --repo_name <name>")
    parser.add_argument("-r", "--repo_name", default="src", help="repository name to get the list")

    args = parser.parse_args()

    # Perform label management
    get_pull_request_list(args.repo_name)
