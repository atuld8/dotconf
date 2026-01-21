#!/usr/bin/env python3
"""
Jira Sprint Board Display Script

This script fetches issues from Jira using a JQL query and displays them in a
sprint board format with assignees as rows and status columns (To-Do, In Progress,
Blocked, Done, Closed).

Requirements:
    pip install requests python-dotenv prettytable

Usage:
    # Basic usage with JQL query
    ./j.sprintBoard.py -q "project = PROJ AND sprint in openSprints()"

    # Include sub-tasks
    ./j.sprintBoard.py -q "project = PROJ AND type in (Story, defect) AND sprint in openSprints()" -s

    # Full example
    ./j.sprintBoard.py -q "project = PROJ AND component = Scrum_team AND type in (Story, defect) AND sprint in openSprints() ORDER BY priority DESC" --show-sub-tasks

Features:
    - Groups issues by assignee
    - Displays status in columns: To-Do, In Progress, Blocked, Done, Closed
    - Shows issue type indicators (prepended):
        * Story: "+ JIRA_ID-123"
        * Defect: "- JIRA_ID-456"
        * Sub-task: "-- JIRA_ID-789"
    - Lists full issue details below the board with tree indentation for sub-tasks
    - Optional sub-task inclusion with --show-sub-tasks flag
"""

import os
import sys
import argparse
import requests
import re
from collections import defaultdict
from dotenv import load_dotenv
from prettytable import PrettyTable

# Load environment variables
load_dotenv()

# Jira credentials and URL
JIRA_URL = "https://" + os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN = os.getenv('JIRA_ACC_TOKEN')

if not JIRA_URL or not JIRA_API_TOKEN:
    print("Error: JIRA_SERVER_NAME and JIRA_ACC_TOKEN must be set in environment variables")
    sys.exit(1)

# Headers for authentication
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}

# Status mapping to board columns
STATUS_MAPPING = {
    'To Do': 'To-Do',
    'TODO': 'To-Do',
    'To-Do': 'To-Do',
    'Open': 'To-Do',
    'Reopened': 'To-Do',

    'In Progress': 'In Progress',
    'In Dev': 'In Progress',
    'Progress': 'In Progress',
    'Development': 'In Progress',

    'Blocked': 'Blocked',
    'On Hold': 'Blocked',
    'Waiting': 'Blocked',

    'Done': 'Done',
    'Resolved': 'Done',
    'Fixed': 'Done',

    'Closed': 'Closed',
    'Complete': 'Closed',
}

# Issue type symbols (prepended)
TYPE_SYMBOLS = {
    'Story': '+ ',
    'Defect': '- ',
    'Bug': '- ',
    'Sub-task': '-- ',
    'Subtask': '-- ',
}


def modify_query_for_subtasks(jql_query):
    """
    Modify the JQL query to include Sub-task type.

    Args:
        jql_query (str): Original JQL query

    Returns:
        str: Modified JQL query with Sub-task included
    """
    # Pattern to find "type in (...)"
    pattern = r'type\s+in\s*\(([^)]+)\)'

    def add_subtask(match):
        types = match.group(1)
        # Check if Sub-task is already included
        if 'sub-task' in types.lower() or 'subtask' in types.lower():
            return match.group(0)
        # Add Sub-task to the list
        return f'type in ({types}, Sub-task)'

    modified_query = re.sub(pattern, add_subtask, jql_query, flags=re.IGNORECASE)
    return modified_query


def get_issues_by_jql(jql_query, max_results=200):
    """
    Fetch issues from Jira based on JQL query.

    Args:
        jql_query (str): JQL query string
        max_results (int): Maximum number of results to fetch

    Returns:
        list: List of issue objects
    """
    try:
        url = f'{JIRA_URL}/rest/api/2/search'
        params = {
            'jql': jql_query,
            'maxResults': max_results,
            'fields': ['key', 'summary', 'status', 'assignee', 'issuetype', 'priority', 'parent']
        }

        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        result = response.json()
        issues = result.get('issues', [])

        print(f"[INFO] Fetched {len(issues)} issues from Jira", file=sys.stderr)
        return issues

    except requests.exceptions.RequestException as e:
        print(f"Error fetching issues from Jira: {e}", file=sys.stderr)
        sys.exit(1)


def get_issue_key_with_type(issue, for_board=True):
    """
    Get issue key with type symbol.

    Args:
        issue (dict): Jira issue object
        for_board (bool): If True, use board format. If False, use details format.

    Returns:
        str: Issue key with type indicator:
             - Stories: "+ JIRA_ID-123" (prefix)
             - Defects: "- JIRA_ID-123" (prefix)
             - Sub-tasks: "-- JIRA_ID-123" (prefix, no indentation)
    """
    key = issue['key']
    issue_type = issue['fields']['issuetype']['name']

    # Get symbol prefix
    symbol = TYPE_SYMBOLS.get(issue_type, '')

    # All types get prefix symbols (no special indentation)
    return f"{symbol}{key}"


def get_mapped_status(status_name):
    """
    Map Jira status to board column.

    Args:
        status_name (str): Jira status name

    Returns:
        str: Mapped board column name
    """
    return STATUS_MAPPING.get(status_name, 'To-Do')


def organize_issues_by_assignee_and_status(issues):
    """
    Organize issues by assignee and status, grouping sub-tasks under their parents.

    Args:
        issues (list): List of Jira issues

    Returns:
        tuple: (board_data dict, issue_details list)
            - board_data: {assignee: {status: [issue_keys]}} (with sub-tasks grouped under parents)
            - issue_details: [(issue_key, type, summary)] (ordered list with sub-tasks under parents)
    """
    board_data = defaultdict(lambda: defaultdict(list))
    issue_details_dict = {}  # Temporary dict for organizing
    parent_to_subtasks = defaultdict(list)  # Map parent key to sub-tasks
    parent_info = {}  # Store parent issue info

    # First pass: collect all issues and identify parent-subtask relationships
    for issue in issues:
        key = issue['key']
        key_with_type_board = get_issue_key_with_type(issue, for_board=True)
        key_with_type_details = get_issue_key_with_type(issue, for_board=False)
        summary = issue['fields']['summary']
        status = issue['fields']['status']['name']
        assignee_obj = issue['fields'].get('assignee')
        issue_type = issue['fields']['issuetype']['name']
        parent_field = issue['fields'].get('parent')

        # Get assignee name or "Unassigned"
        assignee = assignee_obj['displayName'] if assignee_obj else 'Unassigned'

        # Map status to board column
        board_status = get_mapped_status(status)

        # Store issue info
        issue_info = {
            'key': key,
            'key_with_type_board': key_with_type_board,
            'key_with_type_details': key_with_type_details,
            'summary': summary,
            'status': board_status,
            'assignee': assignee,
            'issue_type': issue_type,
            'parent': parent_field['key'] if parent_field else None
        }

        # If this is a sub-task, map it to its parent
        if issue_type in ['Sub-task', 'Subtask'] and parent_field:
            parent_key = parent_field['key']
            parent_to_subtasks[parent_key].append(issue_info)
        else:
            # Store parent/regular issue info
            parent_info[key] = issue_info

        # Store in details dict
        issue_details_dict[key] = (issue_type, summary)

    # Second pass: build board data and ordered details list with sub-tasks grouped under parents
    issue_details_list = []

    # Sort parent issues by key
    for parent_key in sorted(parent_info.keys()):
        parent = parent_info[parent_key]

        # Add parent to board data
        board_data[parent['assignee']][parent['status']].append(parent['key_with_type_board'])

        # Add parent to details list
        issue_details_list.append((parent['key_with_type_details'], parent['issue_type'], parent['summary']))

        # Add sub-tasks immediately after parent (sorted by key)
        if parent_key in parent_to_subtasks:
            subtasks = sorted(parent_to_subtasks[parent_key], key=lambda x: x['key'])
            for subtask in subtasks:
                # Add sub-task to board data (under parent)
                board_data[subtask['assignee']][subtask['status']].append(subtask['key_with_type_board'])

                # Add sub-task to details list
                issue_details_list.append((subtask['key_with_type_details'], subtask['issue_type'], subtask['summary']))

    return board_data, issue_details_list


def display_legend():
    """
    Display legend explaining issue type symbols.
    """
    print("\nLEGEND - Issue Type Indicators: + Story  | - Defect/Bug  | -- Sub-task")
    print()


def display_sprint_board(board_data, status_counts):
    """
    Display the sprint board using PrettyTable.

    Args:
        board_data (dict): Organized board data by assignee and status
        status_counts (dict): Count of issues per status {status: count}
    """
    # Define column headers with counts
    status_columns = ['To-Do', 'In Progress', 'Blocked', 'Done', 'Closed']

    # Create headers with counts
    headers_with_counts = ['Assignee'] + [f"{col} ({status_counts.get(col, 0)})" for col in status_columns]

    # Create table
    table = PrettyTable()
    table.field_names = headers_with_counts

    # Set alignment
    table.align[headers_with_counts[0]] = 'l'
    for col in headers_with_counts[1:]:
        table.align[col] = 'l'

    # Sort assignees (Unassigned at the end)
    assignees = sorted(board_data.keys(), key=lambda x: (x == 'Unassigned', x))

    # Add rows for each assignee
    for assignee_idx, assignee in enumerate(assignees):
        status_data = board_data[assignee]

        # Get max number of issues in any status for this assignee
        max_issues = max([len(status_data.get(status, [])) for status in status_columns], default=0)

        if max_issues == 0:
            continue

        # Create rows (one row per issue, with assignee name only in first row)
        for i in range(max_issues):
            row = []

            # Assignee column (only show name in first row)
            if i == 0:
                row.append(assignee)
            else:
                row.append('')

            # Status columns
            for status in status_columns:
                issues = status_data.get(status, [])
                if i < len(issues):
                    row.append(issues[i])
                else:
                    row.append('')

            table.add_row(row)

        # Add empty row between assignees (except after the last one)
        if assignee_idx < len(assignees) - 1:
            empty_row = [''] * len(headers_with_counts)
            table.add_row(empty_row)

    print("\n" + "="*80)
    print("SPRINT BOARD")
    print("="*80)
    print(table)
    print()


def display_issue_details(issue_details_list):
    """
    Display full issue details below the board.

    Args:
        issue_details_list (list): List of tuples (issue_key, type, summary) in order
    """
    print("\n" + "="*80)
    print("ISSUE DETAILS")
    print("="*80)

    for issue_key, issue_type, summary in issue_details_list:
        # Truncate summary if too long
        if len(summary) > 100:
            summary = summary[:97] + "..."

        # Add indentation for sub-tasks to show tree structure
        if issue_type in ['Sub-task', 'Subtask']:
            # Add extra indentation for sub-tasks to create tree view
            print(f"  {issue_key} ({issue_type}): {summary}")
        else:
            print(f"{issue_key} ({issue_type}): {summary}")

    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Display Jira Sprint Board with issues grouped by assignee and status',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  %(prog)s -q "project = PROJ AND sprint in openSprints()"

  # With sub-tasks included
  %(prog)s -q "project = PROJ AND type in (Story, defect) AND sprint in openSprints()" -s

  # With detailed issue list
  %(prog)s -q "project = PROJ AND sprint in openSprints()" -d

  # Full example with all options
  %(prog)s -q "project = PROJ AND component = Scrum_team AND type in (Story, defect) AND sprint in openSprints() ORDER BY priority DESC" -s -d

Issue Type Indicators:
  Story:        + JIRA_ID-123
  Defect/Bug:   - JIRA_ID-456
  Sub-task:     -- JIRA_ID-789
        """
    )

    parser.add_argument(
        '-q', '--query',
        required=True,
        help='JQL query to fetch issues'
    )

    parser.add_argument(
        '-s', '--show-sub-tasks',
        action='store_true',
        help='Include sub-tasks in the results (adds Sub-task to type filter)'
    )

    parser.add_argument(
        '-d', '--show-details',
        action='store_true',
        help='Display detailed issue list below the board (default: False)'
    )

    parser.add_argument(
        '--max-results',
        type=int,
        default=200,
        help='Maximum number of results to fetch (default: 200)'
    )

    args = parser.parse_args()

    # Modify query if sub-tasks should be included
    jql_query = args.query
    if args.show_sub_tasks:
        original_query = jql_query
        jql_query = modify_query_for_subtasks(jql_query)
        if jql_query != original_query:
            print(f"[INFO] Modified query to include Sub-tasks", file=sys.stderr)

    print(f"[INFO] Executing JQL: {jql_query}", file=sys.stderr)

    # Fetch issues
    issues = get_issues_by_jql(jql_query, args.max_results)

    if not issues:
        print("No issues found matching the query.")
        return

    # Organize issues (now returns list for issue_details instead of dict)
    board_data, issue_details_list = organize_issues_by_assignee_and_status(issues)

    # Calculate status counts
    status_columns = ['To-Do', 'In Progress', 'Blocked', 'Done', 'Closed']
    status_counts = {status: 0 for status in status_columns}
    for assignee_data in board_data.values():
        for status, issues_list in assignee_data.items():
            status_counts[status] += len(issues_list)

    # Display help section BEFORE the board
    print("\n" + "="*80)
    print("JIRA SPRINT BOARD")
    print("="*80)
    print(f"Query: {jql_query}")
    print(f"Total Issues Found: {len(issues)}")
    if args.show_sub_tasks:
        print("Sub-tasks: INCLUDED")
    #print()
    # Display legend at the end
    display_legend()

    # Display sprint board with status counts
    display_sprint_board(board_data, status_counts)

    # Display issue details if requested
    if args.show_details:
        display_issue_details(issue_details_list)

    print(f"\nTotal issues displayed: {len(issue_details_list)}")


if __name__ == '__main__':
    main()
