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


# Function to get the current labels of a Jira issue
def get_pull_request_details(repo_name, pr_num):
    url = f"{repos_url}/{repo_name}/pull-requests/{pr_num}"
    response = requests.get(url, headers=headers, timeout=20)

    if response.status_code == 200:
        try:
            pr_data = response.json()

            if not pr_data['id']:
                print("No open pull requests found.")
                return []

            print(f"PR Repo:        {pr_data['fromRef']['repository']['name']}")
            print(f"PR Hash:        {pr_data['fromRef']['latestCommit']}")
            print(f"PR Title:       {pr_data['title']}")
            print(f"Author:         {pr_data['author']['user']['name']}")
            print(f"Source Branch:  {pr_data['fromRef']['displayId']}")
            print(f"Target Branch:  {pr_data['toRef']['displayId']}")
            print(f"Status:         {pr_data['state']}")

            reviewers = ""
            for reviewer in pr_data.get("reviewers", []):
                reviewers = reviewers + reviewer['user']['name'] + ", "
            print(f"Reviewers:      {reviewers}")

            print(f"WebPR Links:    {pr_data['links']['self'][0]['href']}")

            # Get the list of files in the PR
            files_url = f"{url}/diff"
            print(f"PR links:       {files_url}")
            print("Descriptions:   ")
            print("--------------------------------------")
            print(f"{pr_data['description']}")
            print("--------------------------------------")
            files_response = requests.get(files_url, headers=headers, timeout=20)

            if files_response.status_code == 200:
                files_data = files_response.json()
                print("\nFiles Changed:")
                max_length = 10
                for file in files_data.get("diffs", []):
                    source = file.get('source') or {'toString': 'N/A'}
                    max_length = max(max_length, len(source.get('toString', '')))
                for file in files_data.get("diffs", []):
                    # print(f"- Source: {file.get('source', {}).get('toString', 'N/A')}\t\t- destination: {file.get('destination', {}).get('toString', 'N/A')}")
                    # print(f"- Source: {file.get('source', {}).get('toString', 'N/A').ljust(50)}\t- Destination: {file.get('destination', {}).get('toString', 'N/A')}")
                    # print(f"- Source: {file.get('source', {}).get('toString', 'N/A').ljust(50)}\t- Destination: {file.get('destination', {}).get('toString', 'N/A')}")

                    source = file.get('source') or {'toString': 'N/A'}
                    destination = file.get('destination') or {'toString': 'N/A'}

                    print(f"- Source: {source.get('toString', 'N/A').ljust(max_length)}\t- Destination: {destination.get('toString', 'N/A')}")

            else:
                print("Error fetching files.")

        except requests.exceptions.JSONDecodeError as e:
            print(f'Error decoding JSON: {e}')
    else:
        print(f"Failed to fetch issue details: {response.status_code} - {response.text}")

    return None


# Command-line argument parser
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get list of open PR for mentioned repository",
                                     usage="%(prog)s [-h] --repo_name <name> --pr_num #")
    parser.add_argument("-r", "--repo_name", default="src", help="repository name to get the list. Default is src")
    parser.add_argument("-p", "--pr_num", required=True, help="PR request ID")

    args = parser.parse_args()

    # Perform label management
    get_pull_request_details(args.repo_name, args.pr_num)
