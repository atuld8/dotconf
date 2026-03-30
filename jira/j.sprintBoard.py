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
from datetime import datetime
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

_SPRINT_FIELD_ID = None


def get_sprint_field_id():
    """Get Jira custom field ID for Sprint (e.g., customfield_10020)."""
    global _SPRINT_FIELD_ID
    if _SPRINT_FIELD_ID:
        return _SPRINT_FIELD_ID

    try:
        url = f'{JIRA_URL}/rest/api/2/field'
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        fields = response.json()
        for field in fields:
            if (field.get('name') or '').strip().lower() == 'sprint':
                _SPRINT_FIELD_ID = field.get('id')
                return _SPRINT_FIELD_ID
    except requests.exceptions.RequestException as e:
        print(f"[WARN] Unable to fetch Sprint field ID: {e}", file=sys.stderr)

    return None


def _extract_attr_from_legacy_sprint(sprint_str, attr):
    """Extract attribute from legacy sprint string format."""
    match = re.search(rf'{attr}=([^,\]]+)', sprint_str)
    return match.group(1).strip() if match else None


def _parse_jira_datetime(value):
    """Parse Jira datetime string and return display-friendly value."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.strftime('%Y-%m-%d %H:%M %z')
    except (ValueError, TypeError):
        return value


def get_sprint_info_from_issues(issues, sprint_field_id, allowed_states=None):
    """Extract unique sprint metadata from issues.

    Args:
        issues (list): Jira issues
        sprint_field_id (str): Sprint field id (e.g., customfield_10020)
        allowed_states (set|None): Allowed sprint states (uppercase), e.g. {'ACTIVE'}
    """
    if not sprint_field_id:
        return []

    sprint_map = {}

    for issue in issues:
        sprint_data = issue.get('fields', {}).get(sprint_field_id)
        if not sprint_data:
            continue

        sprint_entries = sprint_data if isinstance(sprint_data, list) else [sprint_data]

        for sprint in sprint_entries:
            sprint_id = None
            sprint_name = None
            sprint_state = None
            sprint_start = None
            sprint_end = None

            if isinstance(sprint, dict):
                sprint_id = sprint.get('id')
                sprint_name = sprint.get('name')
                sprint_state = sprint.get('state')
                sprint_start = sprint.get('startDate')
                sprint_end = sprint.get('endDate')
            elif isinstance(sprint, str):
                sprint_id = _extract_attr_from_legacy_sprint(sprint, 'id')
                sprint_name = _extract_attr_from_legacy_sprint(sprint, 'name')
                sprint_state = _extract_attr_from_legacy_sprint(sprint, 'state')
                sprint_start = _extract_attr_from_legacy_sprint(sprint, 'startDate')
                sprint_end = _extract_attr_from_legacy_sprint(sprint, 'endDate')
            else:
                continue

            sprint_key = sprint_id or sprint_name
            if not sprint_key:
                continue

            existing = sprint_map.get(sprint_key, {})
            sprint_map[sprint_key] = {
                'name': sprint_name or existing.get('name') or str(sprint_key),
                'state': sprint_state or existing.get('state') or 'N/A',
                'start': sprint_start or existing.get('start') or 'N/A',
                'end': sprint_end or existing.get('end') or 'N/A',
            }

    allowed_states_normalized = {s.upper() for s in allowed_states} if allowed_states else None

    sprint_list = []
    for data in sprint_map.values():
        state_value = (data['state'] or 'N/A')
        state_upper = state_value.upper() if isinstance(state_value, str) else str(state_value).upper()
        if allowed_states_normalized and state_upper not in allowed_states_normalized:
            continue

        sprint_list.append({
            'name': data['name'],
            'state': state_value,
            'start': _parse_jira_datetime(data['start']) or 'N/A',
            'end': _parse_jira_datetime(data['end']) or 'N/A',
        })

    sprint_list.sort(key=lambda x: (x['start'] == 'N/A', x['start'], x['name']))
    return sprint_list


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
        sprint_field_id = get_sprint_field_id()
        fields = ['key', 'summary', 'status', 'assignee', 'issuetype', 'priority', 'parent', 'reporter', 'customfield_20303']
        if sprint_field_id:
            fields.append(sprint_field_id)

        params = {
            'jql': jql_query,
            'maxResults': max_results,
            'fields': fields
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


def get_issue_key_with_type(issue, for_board=True, priority=None):
    """
    Get issue key with type symbol and optionally priority.

    Args:
        issue (dict): Jira issue object
        for_board (bool): If True, use board format with priority. If False, use details format.
        priority (str): Priority name (e.g., 'P1', 'Critical', etc.)

    Returns:
        str: Issue key with type indicator and priority:
             - Board format: "+ NBU-123 (P1)" or "- NBU-456 (P2)"
             - Details format: "+ NBU-123" or "-- NBU-456"
    """
    key = issue['key']
    issue_type = issue['fields']['issuetype']['name']

    # Get symbol prefix
    symbol = TYPE_SYMBOLS.get(issue_type, '')

    # For board view, add priority in parentheses
    if for_board and priority and priority != 'N/A':
        return f"{symbol}{key} ({priority})"
    else:
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


def _format_details_status_bucket(status_name):
    """Return compact status bucket for issue details display.

    Uses the same board mapping as sprint board columns.
    """
    return get_mapped_status(status_name)


def _format_issue_details_title(issue_key, issue_type, priority, status_name, widths=None):
    """Format issue details line prefix for readability.

    Example: + NBU-256751 (Story) (P3) (To-Do)
    """
    widths = widths or {}
    type_width = max(5, int(widths.get('type', 0)))
    priority_width = max(2, int(widths.get('priority', 0)))
    status_width = max(5, int(widths.get('status', 0)))

    priority_text = priority if priority and priority != 'N/A' else 'N/A'
    status_bucket = _format_details_status_bucket(status_name)
    return (
        f"{issue_key} "
        f"({issue_type:<{type_width}}) "
        f"({priority_text:<{priority_width}}) "
        f"({status_bucket:<{status_width}})"
    )


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
        summary = issue['fields']['summary']
        status = issue['fields']['status']['name']
        assignee_obj = issue['fields'].get('assignee')
        reporter_obj = issue['fields'].get('reporter')
        priority_obj = issue['fields'].get('priority')
        severity_obj = issue['fields'].get('customfield_20303')
        issue_type = issue['fields']['issuetype']['name']
        parent_field = issue['fields'].get('parent')

        # Get assignee name or "Unassigned"
        assignee = assignee_obj['displayName'] if assignee_obj else 'Unassigned'
        reporter = reporter_obj['displayName'] if reporter_obj else 'N/A'
        priority = priority_obj['name'] if priority_obj else 'N/A'
        severity = severity_obj['value'] if severity_obj else 'N/A'

        # Generate keys with priority for board display
        key_with_type_board = get_issue_key_with_type(issue, for_board=True, priority=priority)
        key_with_type_details = get_issue_key_with_type(issue, for_board=False)

        # Map status to board column
        board_status = get_mapped_status(status)

        # Store issue info
        issue_info = {
            'key': key,
            'key_with_type_board': key_with_type_board,
            'key_with_type_details': key_with_type_details,
            'summary': summary,
            'status': status,
            'board_status': board_status,
            'assignee': assignee,
            'reporter': reporter,
            'priority': priority,
            'severity': severity,
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
        issue_details_dict[key] = (issue_type, summary, status, assignee, reporter, priority, severity)

    # Second pass: build board data and ordered details list with sub-tasks grouped under parents
    issue_details_list = []

    # Sort parent issues by key
    for parent_key in sorted(parent_info.keys()):
        parent = parent_info[parent_key]

        # Add parent to board data
        board_data[parent['assignee']][parent['board_status']].append(parent['key_with_type_board'])

        # Add parent to details list
        issue_details_list.append((parent['key_with_type_details'], parent['issue_type'], parent['summary'],
                                   parent['status'], parent['assignee'], parent['reporter'],
                                   parent['priority'], parent['severity']))

        # Add sub-tasks immediately after parent (sorted by key)
        if parent_key in parent_to_subtasks:
            subtasks = sorted(parent_to_subtasks[parent_key], key=lambda x: x['key'])
            for subtask in subtasks:
                # Add sub-task to board data (under parent)
                board_data[subtask['assignee']][subtask['board_status']].append(subtask['key_with_type_board'])

                # Add sub-task to details list
                issue_details_list.append((subtask['key_with_type_details'], subtask['issue_type'], subtask['summary'],
                                          subtask['status'], subtask['assignee'], subtask['reporter'],
                                          subtask['priority'], subtask['severity']))

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


def display_issue_details(issue_details_list, verbose=False):
    """
    Display full issue details below the board.

    Args:
        issue_details_list (list): List of tuples (issue_key, type, summary, status, assignee, reporter, priority, severity) in order
        verbose (bool): If True, include table header row (used for -d -v)
    """
    print("\n" + "="*80)
    print("ISSUE DETAILS")
    print("="*80)

    state_order = {
        'To-Do': 0,
        'In Progress': 1,
        'Blocked': 2,
        'Done': 3,
        'Closed': 4,
    }

    def _jira_key_sort_value(issue_key):
        match = re.search(r'([A-Z][A-Z0-9_]*-)(\d+)', issue_key or '')
        if not match:
            return (issue_key or '', 0)
        return (match.group(1), int(match.group(2)))

    sorted_issue_details = sorted(
        issue_details_list,
        key=lambda item: (
            state_order.get(_format_details_status_bucket(item[3]), 99),
            _jira_key_sort_value(item[0])
        )
    )

    table = PrettyTable()
    table.header = bool(verbose)
    table.field_names = ['Issue', 'Type', 'Priority', 'Status', 'Summary', 'Assignee', 'Reporter', 'Severity']

    table.align['Issue'] = 'l'
    table.align['Type'] = 'l'
    table.align['Priority'] = 'l'
    table.align['Status'] = 'l'
    table.align['Summary'] = 'l'
    table.align['Assignee'] = 'l'
    table.align['Reporter'] = 'l'
    table.align['Severity'] = 'l'

    current_status_bucket = None
    has_rows = False

    for issue_key, issue_type, summary, status, assignee, reporter, priority, severity in sorted_issue_details:
        summary_display = summary if len(summary) <= 100 else summary[:97] + '...'
        assignee_display = assignee if assignee and assignee != 'N/A' else 'Unassigned'
        priority_display = priority if priority and priority != 'N/A' else 'N/A'
        status_bucket = _format_details_status_bucket(status)

        if current_status_bucket is None:
            current_status_bucket = status_bucket
        elif status_bucket != current_status_bucket:
            if has_rows:
                table.add_row([''] * len(table.field_names))
            current_status_bucket = status_bucket

        table.add_row([
            issue_key,
            issue_type,
            priority_display,
            status_bucket,
            summary_display,
            assignee_display,
            reporter,
            severity,
        ])
        has_rows = True

    # Always print table so headers are visible under ISSUE DETAILS,
    # including verbose mode (-d -v) even when there are no rows.
    print(table)

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
  Story:        + JIRA_ID-123 (P1)
  Defect/Bug:   - JIRA_ID-456 (P2)
  Sub-task:     -- JIRA_ID-789 (P3)

  Note: Priority is shown in parentheses in the sprint board.
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
        '-v', '--verbose',
        action='store_true',
        help='Display verbose issue details including status, assignee, reporter, priority, and severity (use with -d)'
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

    # Extract sprint metadata (start/end/state) from returned issues
    sprint_field_id = get_sprint_field_id()
    # Default: show ACTIVE sprint metadata only.
    # With both -d/--show-details AND -v/--verbose: show both ACTIVE and CLOSED sprint metadata.
    sprint_states_to_show = {'ACTIVE', 'CLOSED'} if (args.verbose and args.show_details) else {'ACTIVE'}
    sprint_info = get_sprint_info_from_issues(issues, sprint_field_id, allowed_states=sprint_states_to_show)

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
    if sprint_info:
        print("Sprint(s):")
        sprint_name_width = max(len(sprint['name']) for sprint in sprint_info)
        sprint_start_width = max(len(sprint['start']) for sprint in sprint_info)
        sprint_end_width = max(len(sprint['end']) for sprint in sprint_info)
        sprint_state_width = max(len(sprint['state']) for sprint in sprint_info)
        for sprint in sprint_info:
            print(
                f"  - {sprint['name']:<{sprint_name_width}} | "
                f"Start: {sprint['start']:<{sprint_start_width}} | "
                f"End: {sprint['end']:<{sprint_end_width}} | "
                f"State: {sprint['state']:<{sprint_state_width}}"
            )
    if args.show_sub_tasks:
        print("Sub-tasks: INCLUDED")
    #print()
    # Display legend at the end
    display_legend()

    # Display sprint board with status counts
    display_sprint_board(board_data, status_counts)

    # Display issue details if requested
    if args.show_details:
        details_verbose = args.verbose and any(flag in sys.argv for flag in ('-v', '--verbose'))
        display_issue_details(issue_details_list, verbose=details_verbose)

    print(f"\nTotal issues displayed: {len(issue_details_list)}")


if __name__ == '__main__':
    main()
