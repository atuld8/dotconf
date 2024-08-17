# pip install requests
# pip install python-dotenv
# pip install pandas
# pip install tabulate
# pip install prettytable

import os
import requests
import pandas as pd
import argparse
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
args = parser.parse_args()


# Function to get issues by JQL
def get_issues_by_jql(jql):

    try:
        url = f'{JIRA_URL}/rest/api/2/search'
        params = {
            'jql': jql,
            'maxResults': MAX_RESULTS,
            'fields': ['key', 'summary', 'status', 'assignee']  # Adjust based on required fields
        }

        response = requests.get(url, headers=headers, params=params)

        response.raise_for_status()  # Raises an HTTPError if the response code was unsuccessful

        return response.json().get('issues', [])

    except requests.exceptions.RequestException as e:

        print(f"Error fetching issues: {e}")
        return []


# Function to get issues by JQL
def print_issues_in_table_format(issues):

    # Extract the relevant data into a list of dictionaries
    data = []

    for index, issue in enumerate(issues, start=1):
        key = issue['key']
        summary = issue['fields']['summary']
        status = issue['fields']['status']['name']
        assignee = issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else 'Unassigned'
        data.append({
            'Serial': index,
            'Key': key,
            'Summary': summary,
            'Status': status,
            'Assignee': assignee
        })

    # Convert the data to a pandas DataFrame and display it as a table
    df = pd.DataFrame(data)

    # print(df.to_markdown())  # Prints a table in markdown format, good for command line

    # Use PrettyTable to print the DataFrame in a table format
    table = PrettyTable()
    table.field_names = df.columns.tolist()

    # Set column alignment to left
    for field in table.field_names:
       table.align[field] = "l"  # Align to the left
    for _, row in df.iterrows():
        table.add_row(row.tolist())
    print(table)


# Main function
def main():

    issues = get_issues_by_jql(args.jql)

    if not issues:
        print("No issues found.")
        return

    print_issues_in_table_format(issues)


if __name__ == '__main__':
    main()
