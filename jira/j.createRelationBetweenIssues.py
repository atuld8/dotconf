#!/usr/bin/env python3
import json
import os
import argparse
import requests
from dotenv import load_dotenv


# Load the environment variables configured on the system
load_dotenv()

# Jira credentials and URL
JIRA_URL            = "https://" + os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN      = os.getenv('JIRA_ACC_TOKEN')


# Jira API endpoint for updating assignee
issue_url = f'{JIRA_URL}/rest/api/2/issueLink'

# Headers
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}


# Main function to setup a relation between Jira ids
def link_Jira_ids_with_relation(src_id, dest_id, relation):
    url = f"{issue_url}"

    if src_id is None:
        return

    if dest_id is None:
        return

    if relation is None:
        return

    payload = {
        "type": {"name": relation},
        "inwardIssue": {"key": src_id},
        "outwardIssue": {"key": dest_id}
    }

    response = requests.post(url, headers=headers, json=payload, timeout=20)

    if response.status_code == 201:
        print(f"Updated relation between {src_id} and {dest_id} with {relation}")
    else:
        print(f"Failed to update relation between {src_id} and {dest_id} with {relation} : {response.status_code} - {response.text}")


# Command-line argument parser
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Link the Jira issues with relations",
                                     usage="%(prog)s [-h] --src_id <id> --dest_id <id> --relation [Relates|Duplicate|Blocks|Cloners]")
    parser.add_argument("-s", "--src_id", help="Source Jira ticket ID (e.g., JIR-123)")
    parser.add_argument("-d", "--dest_id", help="Destination Jira ticket ID (e.g.  JIR-789)")
    parser.add_argument("-r", "--relation", help="Relation between source and destination Jira tickets")

    args = parser.parse_args()

    # Perform relation setting
    link_Jira_ids_with_relation(args.src_id, args.dest_id, args.relation)
