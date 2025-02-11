#!/usr/bin/env python3.12
# pip install requests
# pip install python-dotenv
# pip install pandas
# pip install tabulate
# pip install prettytable

import os
import argparse
import requests
import pandas as pd
from dotenv import load_dotenv
from prettytable import PrettyTable

load_dotenv()

# Jira credentials and URL
JIRA_URL = "https://" + os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN = os.getenv('JIRA_ACC_TOKEN')

# JQL query to filter issues
JQL_QUERY = 'labels = Tracking and labels = NBServerMigrator_2.4'
MAX_RESULTS = 150  # Adjust this based on the expected number of results

# Headers for authentication and content type
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}


# Set up the command line argument parser
parser = argparse.ArgumentParser(description='Run a JQL query and display the results in a table format.')
parser.add_argument(
    'jql',
    type=str,
    nargs='?',
    default=JQL_QUERY,
    help='The JQL query to execute.')

# Add optional argument to accept a comma-separated list
parser.add_argument(
    "--excludeCols",
    type=lambda s: s.split(','),
    help="Comma-separated list of Headers",
    default=[]
)

args = parser.parse_args()


# Function to get issues by JQL
def get_issues_by_jql(jql):

    try:
        url = f'{JIRA_URL}/rest/api/2/search'
        params = {
            'jql': jql,
            'maxResults': MAX_RESULTS,
            'fields': ['key',
                       'summary',
                       'status',
                       'assignee',
                       'reporter',
                       'priority',
                       'issuetype',
                       'labels',
                       'fixVersions',
                       'customfield_16006',
                       'customfield_10001',
                       'customfield_16007']  # Adjust based on required fields
        }

        response = requests.get(url, headers=headers, params=params, timeout=20)

        response.raise_for_status()  # Raises an HTTPError if the response code was unsuccessful

        return response.json().get('issues', [])

    except requests.exceptions.RequestException as e:
        print(f"Error fetching issues: {e}")
        return []


# Function to get issues by JQL
def print_issues_in_table_format(issues, excludeCols):

    # Extract the relevant data into a list of dictionaries
    data = []

    for index, issue in enumerate(issues, start=1):
        key = issue['key']
        summary = issue['fields']['summary'] if len(issue['fields']['summary']) < 120 else issue['fields']['summary'][:120] + "..."
        status = issue['fields']['status']['name']
        assignee = issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else 'Unassigned'
        reporter = issue['fields']['reporter']['displayName'] if issue['fields']['reporter'] else 'Unknown'
        priority = issue['fields']['priority']['name'] if issue['fields']['priority']['name'] else 'NA'
        severity = issue['fields']['customfield_16006']['value'] if issue['fields']['customfield_16006']['value'] else 'NA'
        issuetype = issue['fields']['issuetype']['name'] if issue['fields']['issuetype']['name'] else 'Unknown'
        labels = ', '.join(issue['fields']['labels']) if issue['fields']['labels'] else '-'
        epic_link = issue['fields']['customfield_10001'] if issue['fields']['customfield_10001'] else '-'
        cvss_score = issue['fields']['customfield_16007'] if issue['fields']['customfield_16007'] else '-'
        fixVersions = ', '.join(fv['name'] for fv in issue['fields']['fixVersions']) if issue['fields'].get('fixVersions') else '-'


        unfiltered_entry = {
            'Sr.': index,
            'Key': key,
            'Summary': summary,
            'Status': status,
            'Assignee': assignee,
            'Reporter': reporter,
            'Priority': priority,
            'Severity': severity,
            'IssueType': issuetype,
            'Labels': labels,
            'FixVers': fixVersions,
            'Epic': epic_link,
            'CVSS': cvss_score
        }

        # Filter the entry to exclude any key that is in the exclude_keys list
        filtered_entry = {k: v for k, v in unfiltered_entry.items() if k not in excludeCols}

        # Append the filtered dictionary to the data list
        data.append(filtered_entry)

    # Convert the data to a pandas DataFrame and display it as a table
    df = pd.DataFrame(data)

    # print(df.to_markdown())  # Prints a table in markdown format, good for command line

    # Use PrettyTable to print the DataFrame in a table format
    table = PrettyTable()
    table.field_names = df.columns.tolist()

    # Set column alignment to left
    for field in table.field_names:
        if field == 'Sr.':
            table.align[field] = "r"  # Align to the right
        elif field == 'Priority':
            table.align[field] = "c"  # Align to the right
        else:
            table.align[field] = "l"  # Align to the left
    for _, row in df.iterrows():
        table.add_row(row.tolist())
    print(table)
    # print(table.get_html_string())


# Main function
def main():

    issues = get_issues_by_jql(args.jql)

    if not issues:
        print("No issues found.")
        return

    print_issues_in_table_format(issues, args.excludeCols)


if __name__ == '__main__':
    main()
