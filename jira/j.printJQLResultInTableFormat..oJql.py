#!/usr/bin/env python3
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
from datetime import datetime

load_dotenv()

# Cache for field name to ID mapping
_field_cache = None

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
    help="Comma-separated list of Headers to exclude",
    default=[]
)

parser.add_argument(
    "--extraCols",
    type=lambda s: s.split(','),
    help="Comma-separated list of extra field names to include (e.g., 'Solution,Root Cause')",
    default=[]
)

parser.add_argument(
    "--preset",
    type=str,
    choices=['default', 'sp'],
    default='default',
    help="Column preset: 'default' (all columns), 'sp' (security/patch focused - hides Runtime, Reporter, IssueType, Labels, Epic)"
)

args = parser.parse_args()

# Preset configurations: columns to exclude for each preset
PRESET_EXCLUDES = {
    'default': ['CVSS', 'FixVers'],
    'sp': ['Runtime', 'Reporter', 'IssueType', 'Labels', 'Epic']
}


def get_all_fields():
    """Fetches all Jira fields and returns a name-to-ID mapping.

    Returns:
        dict: A dictionary mapping field names (lowercase) to their IDs.
    """
    global _field_cache
    if _field_cache is not None:
        return _field_cache

    try:
        url = f'{JIRA_URL}/rest/api/2/field'
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        fields = response.json()
        # Create mapping: lowercase name -> {id, name, custom}
        _field_cache = {}
        for field in fields:
            name_lower = field['name'].lower()
            _field_cache[name_lower] = {
                'id': field['id'],
                'name': field['name'],
                'custom': field.get('custom', False)
            }
        return _field_cache
    except requests.exceptions.RequestException as e:
        print(f"Error fetching fields: {e}")
        return {}


def get_field_id_by_name(field_name):
    """Resolves a field name to its Jira field ID.

    Args:
        field_name (str): The human-readable field name (case-insensitive).

    Returns:
        tuple: (field_id, actual_name) or (None, None) if not found.
    """
    fields = get_all_fields()
    field_info = fields.get(field_name.lower().strip())
    if field_info:
        return field_info['id'], field_info['name']
    return None, None


def format_runtime(days):
    """Formats runtime in adaptive human-readable format.

    Args:
        days (int): Number of days.

    Returns:
        str: Formatted runtime string (e.g., '5d', '2w 3d', '1mo 15d').
    """
    if days < 0:
        return '-'
    if days == 0:
        return '0d'

    if days < 14:  # Less than 2 weeks: show days
        return f"{days}d"
    elif days < 60:  # Less than 2 months: show weeks + days
        weeks = days // 7
        remaining_days = days % 7
        if remaining_days == 0:
            return f"{weeks}w"
        return f"{weeks}w {remaining_days}d"
    else:  # 2+ months: show months + days
        months = days // 30
        remaining_days = days % 30
        if remaining_days == 0:
            return f"{months}mo"
        return f"{months}mo {remaining_days}d"


def calculate_runtime(issue):
    """Calculates runtime for an issue.

    For open issues: days since creation.
    For resolved/closed issues: days from creation to resolution.

    Args:
        issue (dict): The Jira issue.

    Returns:
        str: Formatted runtime string.
    """
    created_str = issue['fields'].get('created')
    resolution_str = issue['fields'].get('resolutiondate')
    status = issue['fields']['status']['name'].lower()

    if not created_str:
        return '-'

    try:
        # Jira datetime format: 2024-01-15T10:30:00.000+0000
        created = datetime.fromisoformat(created_str.replace('Z', '+00:00').split('.')[0])

        if resolution_str and status in ['resolved', 'closed', 'done', 'complete', 'completed']:
            # Closed issue: creation to resolution
            resolved = datetime.fromisoformat(resolution_str.replace('Z', '+00:00').split('.')[0])
            delta = resolved - created
        else:
            # Open issue: creation to now
            delta = datetime.now() - created

        return format_runtime(delta.days)
    except (ValueError, TypeError):
        return '-'


def extract_field_value(issue, field_id):
    """Extracts the value of a field from an issue, handling various field types.

    Args:
        issue (dict): The Jira issue.
        field_id (str): The field ID to extract.

    Returns:
        str: The field value as a string.
    """
    value = issue['fields'].get(field_id)

    if value is None:
        return '-'

    # Handle different field types
    if isinstance(value, dict):
        # Could be a user, status, priority, or custom field with 'value' or 'name'
        if 'displayName' in value:
            return value['displayName']
        if 'name' in value:
            return value['name']
        if 'value' in value:
            return value['value']
        return str(value)
    elif isinstance(value, list):
        # Array fields (labels, components, etc.)
        if len(value) == 0:
            return '-'
        if isinstance(value[0], dict):
            return ', '.join(v.get('name', v.get('value', str(v))) for v in value)
        return ', '.join(str(v) for v in value)
    else:
        return str(value)


# Function to get issues by JQL
def get_issues_by_jql(jql, extra_field_ids=None):
    """Fetches issues from Jira based on the provided JQL query.

    Args:
        jql (str): The JQL query to execute.
        extra_field_ids (list): Additional field IDs to fetch.

    Returns:
        list: A list of issues returned by the JQL query, or an empty list if an error occurs.
    """
    try:
        url = f'{JIRA_URL}/rest/api/2/search'

        base_fields = ['key',
                       'summary',
                       'status',
                       'assignee',
                       'reporter',
                       'priority',
                       'issuetype',
                       'labels',
                       'created',
                       'resolutiondate',
                       'fixVersions',
                       'customfield_20303',
                       'customfield_10008',
                       'customfield_33415']  # CVSS Score

        # Add any extra fields requested
        if extra_field_ids:
            base_fields.extend(extra_field_ids)

        params = {
            'jql': jql,
            'maxResults': MAX_RESULTS,
            'fields': base_fields
        }

        response = requests.get(url, headers=headers, params=params, timeout=20)

        response.raise_for_status()  # Raises an HTTPError if the response code was unsuccessful

        return response.json().get('issues', [])

    except requests.exceptions.RequestException as e:
        print(f"Error fetching issues: {e}")
        return []


def print_issues_in_table_format(issues, excludeCols, extra_fields=None):
    """Prints the issues in a table format.

    Args:
        issues (list): The list of issues to display.
        excludeCols (list): The list of columns to exclude from the display.
        extra_fields (list): List of tuples (field_id, display_name) for extra columns.
    """
    # Extract the relevant data into a list of dictionaries
    data = []
    extra_fields = extra_fields or []

    for index, issue in enumerate(issues, start=1):
        key = issue['key']
        summary = issue['fields']['summary'] if len(issue['fields']['summary']) < 120 else issue['fields']['summary'][:120] + "..."
        status = issue['fields']['status']['name']
        assignee = issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else 'Unassigned'
        reporter = issue['fields']['reporter']['displayName'] if issue['fields']['reporter'] else 'Unknown'
        priority = issue['fields']['priority']['name'] if issue['fields']['priority']['name'] else 'NA'
        severity = issue['fields']['customfield_20303']['value'] if issue['fields']['customfield_20303'] and issue['fields']['customfield_20303']['value'] else 'NA'
        issuetype = issue['fields']['issuetype']['name'] if issue['fields']['issuetype']['name'] else 'Unknown'
        labels = ', '.join(issue['fields']['labels']) if issue['fields']['labels'] else '-'
        epic_link = issue['fields']['customfield_10008'] if issue['fields']['customfield_10008'] else '-'
        runtime = calculate_runtime(issue)
        fix_versions = ', '.join(fv['name'] for fv in issue['fields']['fixVersions']) if issue['fields'].get('fixVersions') else '-'
        cvss_score = issue['fields']['customfield_33415'] if issue['fields'].get('customfield_33415') else '-'

        unfiltered_entry = {
            'Sr.': index,
            'Key': key,
            'Summary': summary,
            'Status': status,
            'Runtime': runtime,
            'Assignee': assignee,
            'Reporter': reporter,
            'Priority': priority,
            'Severity': severity,
            'IssueType': issuetype,
            'Labels': labels,
            'FixVers': fix_versions,
            'Epic': epic_link,
            'CVSS': cvss_score
        }

        # Add extra dynamic fields
        for field_id, display_name in extra_fields:
            value = extract_field_value(issue, field_id)
            # Truncate long values
            if len(str(value)) > 50:
                value = str(value)[:50] + "..."
            unfiltered_entry[display_name] = value

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
        if field in ['Sr.', 'Runtime', 'CVSS']:
            table.align[field] = "r"  # Align to the right
        elif field == 'Priority':
            table.align[field] = "c"  # Align to center
        else:
            table.align[field] = "l"  # Align to the left
    for _, row in df.iterrows():
        table.add_row(row.tolist())
    print(table)
    # print(table.get_html_string())


def main():
    """ Main function """

    # Resolve extra column names to field IDs
    extra_fields = []  # List of (field_id, display_name)
    extra_field_ids = []

    if args.extraCols:
        for field_name in args.extraCols:
            field_name = field_name.strip()
            if not field_name:
                continue
            field_id, actual_name = get_field_id_by_name(field_name)
            if field_id:
                extra_fields.append((field_id, actual_name))
                extra_field_ids.append(field_id)
                print(f"Resolved '{field_name}' -> {field_id}")
            else:
                print(f"Warning: Field '{field_name}' not found in Jira. Skipping.")

    issues = get_issues_by_jql(args.jql, extra_field_ids)

    if not issues:
        print("No issues found.")
        return

    # Combine preset excludes with user-specified excludes
    all_excludes = list(set(args.excludeCols + PRESET_EXCLUDES.get(args.preset, [])))

    print_issues_in_table_format(issues, all_excludes, extra_fields)


if __name__ == '__main__':
    main()
