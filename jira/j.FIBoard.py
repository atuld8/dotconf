#!/usr/bin/env python3
"""
Jira FI (Field Issue) Board Display Script

This script fetches FI issues from Jira using a JQL query and displays them in a
board format with assignees as rows and FI status columns.

Requirements:
    pip install requests python-dotenv prettytable

Usage:
    # Basic usage with default JQL (uses JIRA_MYTEAM_USERS env var)
    ./j.FIBoard.py

    # Specify users explicitly
    ./j.FIBoard.py -u "john.doe, jane.smith"

    # Custom JQL query
    ./j.FIBoard.py -q "project = FIELDISSUE AND type = Task"

    # With detailed issue list
    ./j.FIBoard.py -d

Features:
    - Groups issues by assignee
    - Displays FI status columns: In Progress, Waiting on Support, Pre closing, Solution Provided, Done - Solution provided
    - Shows issue type indicators (prepended): Task: "+ FI-123"
    - Lists full issue details below the board
    - Dynamic field discovery (no hardcoded custom field IDs)
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
JIRA_URL = "https://" + os.getenv('JIRA_SERVER_NAME', '')
JIRA_API_TOKEN = os.getenv('JIRA_ACC_TOKEN', '')
JIRA_MYTEAM_USERS = os.getenv('JIRA_MYTEAM_USERS', '')

if not JIRA_URL or JIRA_URL == "https://" or not JIRA_API_TOKEN:
    print("Error: JIRA_SERVER_NAME and JIRA_ACC_TOKEN must be set in environment variables")
    sys.exit(1)

# Headers for authentication
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}

# FI Status mapping to board columns
# Board columns: In Progress | Waiting on Support | Pre closing | Solution Provided | Done - Solution provided
STATUS_COLUMNS = [
    'In Progress',
    'Waiting on Support',
    'Pre closing',
    'Solution Provided',
    'Done - Solution provided'
]

STATUS_MAPPING = {
    # In Progress
    'In Progress': 'In Progress',
    'In Dev': 'In Progress',
    'Development': 'In Progress',
    'Open': 'In Progress',
    'To Do': 'In Progress',
    'TODO': 'In Progress',
    'Reopened': 'In Progress',

    # Waiting on Support
    'Waiting on Support': 'Waiting on Support',
    'Waiting': 'Waiting on Support',
    'Blocked': 'Waiting on Support',
    'On Hold': 'Waiting on Support',

    # Pre closing
    'Pre closing': 'Pre closing',
    'Pre-closing': 'Pre closing',
    'Preclosing': 'Pre closing',

    # Solution Provided
    'Solution Provided': 'Solution Provided',
    'Resolved': 'Solution Provided',
    'Fixed': 'Solution Provided',

    # Done - Solution provided
    'Done - Solution provided': 'Done - Solution provided',
    'Done - Solution Provided': 'Done - Solution provided',
    'Done': 'Done - Solution provided',
    'Closed': 'Done - Solution provided',
    'Complete': 'Done - Solution provided',
}

# Issue type symbols (prepended)
TYPE_SYMBOLS = {
    'Task': '+ ',
    'Sub-task': '-- ',
    'Subtask': '-- ',
    'Story': '+ ',
    'Defect': '- ',
    'Bug': '- ',
}

# Cache for field name to ID mapping
_fields_by_name = None


def _normalize_field_selector(value: str) -> str:
    """Normalize field name for case-insensitive matching."""
    return re.sub(r"\s+", " ", value.strip()).casefold()


def get_field_key_by_name(display_name: str) -> str:
    """Get Jira field ID by display name.

    Args:
        display_name: Field display name (e.g., 'Case Status', 'Case Account Name')

    Returns:
        Field ID (e.g., 'customfield_12345') or None if not found
    """
    global _fields_by_name

    if _fields_by_name is None:
        try:
            url = f'{JIRA_URL}/rest/api/2/field'
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            _fields_by_name = {}
            for field in response.json():
                name = field.get("name")
                field_id = field.get("id")
                if isinstance(name, str) and isinstance(field_id, str):
                    _fields_by_name[_normalize_field_selector(name)] = field_id
        except requests.exceptions.RequestException as e:
            print(f"[WARN] Unable to fetch Jira fields: {e}", file=sys.stderr)
            _fields_by_name = {}

    return _fields_by_name.get(_normalize_field_selector(display_name))


def _field_value_by_name(issue: dict, display_name: str):
    """Extract field value from issue using display name.

    Uses the 'names' mapping returned with expand=names to find field by display name.

    Args:
        issue: Jira issue dict (must include 'names' from expand=names)
        display_name: Field display name (e.g., 'Case Status')

    Returns:
        Field value or None if not found
    """
    fields = issue.get("fields")
    names = issue.get("names")
    if not isinstance(fields, dict) or not isinstance(names, dict):
        return None

    normalized_name = _normalize_field_selector(display_name)
    for key, mapped_name in names.items():
        if key in fields and isinstance(mapped_name, str):
            if _normalize_field_selector(mapped_name) == normalized_name:
                return fields.get(key)
    return None


def _safe_print(text):
    """Print text safely, handling Unicode encoding errors for ASCII terminals."""
    replacements = {
        '\u2011': '-',   # Non-breaking hyphen
        '\u2010': '-',   # Hyphen
        '\u2013': '-',   # En dash
        '\u2014': '--',  # Em dash
        '\u2018': "'",   # Left single quote
        '\u2019': "'",   # Right single quote
        '\u201c': '"',   # Left double quote
        '\u201d': '"',   # Right double quote
        '\u2026': '...', # Ellipsis
        '\u00a0': ' ',   # Non-breaking space
        '\u2022': '*',   # Bullet
        '\u2023': '>',   # Triangular bullet
        '\u00b7': '*',   # Middle dot
    }

    text_str = str(text)
    for char, replacement in replacements.items():
        text_str = text_str.replace(char, replacement)

    try:
        print(text_str)
    except UnicodeEncodeError:
        print(text_str.encode(sys.stdout.encoding or 'ascii', errors='replace').decode())


def _parse_jira_datetime(value: str) -> str:
    """Parse Jira datetime string and return display-friendly value."""
    if not value:
        return 'N/A'
    try:
        val = value.replace('Z', '+00:00')
        if len(val) > 6 and val[-3] == ':' and val[-6] in ('+', '-'):
            val = val[:-3] + val[-2:]

        try:
            if '.' in val:
                parsed = datetime.strptime(val, '%Y-%m-%dT%H:%M:%S.%f%z')
            else:
                parsed = datetime.strptime(val, '%Y-%m-%dT%H:%M:%S%z')
        except ValueError:
            if '.' in val:
                parsed = datetime.strptime(val[:23], '%Y-%m-%dT%H:%M:%S.%f')
            else:
                parsed = datetime.strptime(val[:19], '%Y-%m-%dT%H:%M:%S')

        return parsed.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return str(value)[:10] if value else 'N/A'


def _extract_display_value(value) -> str:
    """Extract display value from Jira field value (handles dict, list, str)."""
    if value is None:
        return 'N/A'
    if isinstance(value, str):
        return value.strip() or 'N/A'
    if isinstance(value, dict):
        # Common patterns: {'name': ...}, {'value': ...}, {'displayName': ...}
        for key in ['displayName', 'name', 'value']:
            if key in value:
                return str(value[key])
        return str(value)
    if isinstance(value, list):
        if not value:
            return 'N/A'
        # Join list of values
        parts = []
        for item in value:
            parts.append(_extract_display_value(item))
        return ', '.join(p for p in parts if p and p != 'N/A')
    return str(value)


def get_issues_by_jql(jql_query: str, max_results: int = 200) -> list:
    """Fetch issues from Jira based on JQL query."""
    url = f'{JIRA_URL}/rest/api/2/search'

    # Use *all fields and expand=names for dynamic field discovery
    params = {
        'jql': jql_query,
        'maxResults': max_results,
        'fields': '*all',
        'expand': 'names'
    }

    # Retry with increasing timeouts
    timeouts = [60, 120, 180]
    last_error = None

    for attempt, timeout in enumerate(timeouts, 1):
        try:
            print(f"[INFO] Attempt {attempt}/{len(timeouts)} (timeout={timeout}s)...", file=sys.stderr)
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()

            result = response.json()
            issues = result.get('issues', [])

            # Inject names mapping into each issue for _field_value_by_name() compatibility
            names = result.get('names')
            if names:
                for issue in issues:
                    issue['names'] = names

            print(f"[INFO] Fetched {len(issues)} issues from Jira", file=sys.stderr)
            return issues

        except requests.exceptions.Timeout as e:
            last_error = e
            if attempt < len(timeouts):
                print(f"[WARN] Request timed out, retrying...", file=sys.stderr)
            continue
        except requests.exceptions.RequestException as e:
            print(f"Error fetching issues from Jira: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Error fetching issues from Jira: {last_error}", file=sys.stderr)
    sys.exit(1)


def get_issue_key_with_type(issue: dict, for_board: bool = True, priority: str = None) -> str:
    """Get issue key with type symbol and optionally priority."""
    key = issue['key']
    issue_type = issue['fields']['issuetype']['name']
    symbol = TYPE_SYMBOLS.get(issue_type, '')

    if for_board and priority and priority != 'N/A':
        return f"{symbol}{key} ({priority})"
    else:
        return f"{symbol}{key}"


def get_mapped_status(status_name: str) -> str:
    """Map Jira status to board column."""
    mapped = STATUS_MAPPING.get(status_name)
    if mapped:
        return mapped
    # Fallback: try case-insensitive match
    status_lower = status_name.lower()
    for key, value in STATUS_MAPPING.items():
        if key.lower() == status_lower:
            return value
    # Default to In Progress if no mapping found
    return 'In Progress'


def organize_issues_by_assignee_and_status(issues: list) -> tuple:
    """Organize issues by assignee and status, grouping sub-tasks under parents.

    Returns:
        tuple: (board_data dict, issue_details list)
    """
    board_data = defaultdict(lambda: defaultdict(list))
    parent_to_subtasks = defaultdict(list)
    parent_info = {}

    for issue in issues:
        key = issue['key']
        fields = issue['fields']
        summary = fields.get('summary', '')
        status = fields.get('status', {}).get('name', 'Unknown')
        assignee_obj = fields.get('assignee')
        priority_obj = fields.get('priority')
        issue_type = fields.get('issuetype', {}).get('name', 'Task')
        parent_field = fields.get('parent')

        # Standard fields
        assignee = assignee_obj.get('displayName', 'Unassigned') if assignee_obj else 'Unassigned'
        priority = priority_obj.get('name', 'N/A') if priority_obj else 'N/A'

        # Components (standard field)
        components_list = fields.get('components', [])
        components = ', '.join(c.get('name', '') for c in components_list) if components_list else 'N/A'

        # Affects Version/s (standard field)
        versions_list = fields.get('versions', [])
        affects_versions = ', '.join(v.get('name', '') for v in versions_list) if versions_list else 'N/A'

        # Updated (standard field)
        updated_raw = fields.get('updated', '')
        updated = _parse_jira_datetime(updated_raw)

        # Custom fields by display name
        case_status = _extract_display_value(_field_value_by_name(issue, 'Case Status'))
        customer = _extract_display_value(_field_value_by_name(issue, 'Case Account Name'))
        cap_involvement_raw = _extract_display_value(_field_value_by_name(issue, 'CAP Involvement'))
        cap_involvement = '-' if cap_involvement_raw == 'N/A' else cap_involvement_raw

        # Board display key
        key_with_type_board = get_issue_key_with_type(issue, for_board=True, priority=priority)
        key_with_type_details = get_issue_key_with_type(issue, for_board=False)

        # Map status to board column
        board_status = get_mapped_status(status)

        issue_info = {
            'key': key,
            'key_with_type_board': key_with_type_board,
            'key_with_type_details': key_with_type_details,
            'summary': summary,
            'status': status,
            'board_status': board_status,
            'assignee': assignee,
            'priority': priority,
            'issue_type': issue_type,
            'components': components,
            'affects_versions': affects_versions,
            'case_status': case_status,
            'customer': customer,
            'updated': updated,
            'cap_involvement': cap_involvement,
            'parent': parent_field.get('key') if parent_field else None
        }

        # Group sub-tasks under parents
        if issue_type in ['Sub-task', 'Subtask'] and parent_field:
            parent_key = parent_field.get('key')
            parent_to_subtasks[parent_key].append(issue_info)
        else:
            parent_info[key] = issue_info

    # Build board data and ordered details list
    issue_details_list = []

    for parent_key in sorted(parent_info.keys()):
        parent = parent_info[parent_key]

        # Add parent to board data
        board_data[parent['assignee']][parent['board_status']].append(parent['key_with_type_board'])

        # Add parent to details list
        issue_details_list.append(parent)

        # Add sub-tasks immediately after parent
        if parent_key in parent_to_subtasks:
            subtasks = sorted(parent_to_subtasks[parent_key], key=lambda x: x['key'])
            for subtask in subtasks:
                board_data[subtask['assignee']][subtask['board_status']].append(subtask['key_with_type_board'])
                issue_details_list.append(subtask)

    return board_data, issue_details_list


def display_legend():
    """Display legend explaining issue type symbols."""
    print("\nLEGEND - Issue Type Indicators: + Task")
    print()


def display_fi_board(board_data: dict, status_counts: dict):
    """Display the FI board using PrettyTable."""
    # Create headers with counts
    headers_with_counts = ['Assignee'] + [f"{col} ({status_counts.get(col, 0)})" for col in STATUS_COLUMNS]

    table = PrettyTable()
    table.field_names = headers_with_counts

    # Set alignment
    for col in headers_with_counts:
        table.align[col] = 'l'

    # Sort assignees (Unassigned at the end)
    assignees = sorted(board_data.keys(), key=lambda x: (x == 'Unassigned', x))

    for assignee_idx, assignee in enumerate(assignees):
        status_data = board_data[assignee]

        max_issues = max([len(status_data.get(status, [])) for status in STATUS_COLUMNS], default=0)

        if max_issues == 0:
            continue

        # Calculate total issues for this assignee
        total_issues = sum(len(status_data.get(status, [])) for status in STATUS_COLUMNS)

        for i in range(max_issues):
            row = []

            # Assignee column (only show name and total count in first row)
            if i == 0:
                row.append(f"{assignee} ({total_issues})")
            else:
                row.append('')

            # Status columns
            for status in STATUS_COLUMNS:
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

    print("\n" + "="*120)
    print("FI BOARD")
    print("="*120)
    _safe_print(table)
    print()


def display_issue_details(issue_details_list: list, verbose: bool = False):
    """Display full issue details below the board."""
    print("\n" + "="*120)
    print("ISSUE DETAILS")
    print("="*120)

    # Sort by status order, then by key
    state_order = {status: idx for idx, status in enumerate(STATUS_COLUMNS)}

    def _jira_key_sort_value(issue_key):
        match = re.search(r'([A-Z][A-Z0-9_]*-)(\d+)', issue_key or '')
        if not match:
            return (issue_key or '', 0)
        return (match.group(1), int(match.group(2)))

    sorted_details = sorted(
        issue_details_list,
        key=lambda item: (
            state_order.get(item['board_status'], 99),
            _jira_key_sort_value(item['key'])
        )
    )

    table = PrettyTable()
    table.header = True
    table.field_names = [
        'Key', 'Components', 'Priority', 'Status', 'Assignee',
        'Affects Version/s', 'Case Status', 'Customer', 'Summary', 'Updated', 'CAP Involvement'
    ]

    for col in table.field_names:
        table.align[col] = 'l'

    # Set max widths
    table.max_width['Summary'] = 50
    table.max_width['Customer'] = 20
    table.max_width['Components'] = 20

    current_status = None

    for issue in sorted_details:
        # Add separator between status groups
        if current_status is None:
            current_status = issue['board_status']
        elif issue['board_status'] != current_status:
            table.add_row([''] * len(table.field_names))
            current_status = issue['board_status']

        summary = issue['summary']
        if len(summary) > 50:
            summary = summary[:47] + '...'

        customer = issue['customer']
        if len(customer) > 20:
            customer = customer[:17] + '...'

        table.add_row([
            issue['key_with_type_details'],
            issue['components'],
            issue['priority'],
            issue['board_status'],
            issue['assignee'],
            issue['affects_versions'],
            issue['case_status'],
            customer,
            summary,
            issue['updated'],
            issue['cap_involvement'],
        ])

    _safe_print(table)
    print()


def get_default_jql(users: str = None) -> str:
    """Build default JQL query.

    Args:
        users: Comma-separated list of usernames. If None, uses JIRA_MYTEAM_USERS env var.
    """
    assignees = users if users else JIRA_MYTEAM_USERS

    if not assignees:
        print("Warning: No users specified and JIRA_MYTEAM_USERS env var not set. Using query without assignee filter.", file=sys.stderr)
        return '("Business Unit" in (NBU, DP) or "Business Unit" is EMPTY) and created > 2025-01-01 and Project in (FIELDISSUE) and (statusCategory != Done OR status = "Pre closing")'

    return f'("Business Unit" in (NBU, DP) or "Business Unit" is EMPTY) and created > 2025-01-01 and Project in (FIELDISSUE) and Assignee in ({assignees}) and (statusCategory != Done OR status = "Pre closing")'


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Display Jira FI Board with issues grouped by assignee and FI status',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with default JQL (uses JIRA_MYTEAM_USERS env var)
  %(prog)s

  # Specify users explicitly (overrides JIRA_MYTEAM_USERS)
  %(prog)s -u "john.doe, jane.smith"

  # Custom JQL query
  %(prog)s -q "project = FIELDISSUE AND type = Task AND assignee = currentUser()"

  # With detailed issue list
  %(prog)s -d

  # Full example
  %(prog)s -u "john.doe" -d

Issue Type Indicators:
  Task:         + FI-123 (P1)

FI Status Columns:
  In Progress | Waiting on Support | Pre closing | Solution Provided | Done - Solution provided

Environment Variables:
  JIRA_SERVER_NAME    Jira server hostname (required)
  JIRA_ACC_TOKEN      Jira API Bearer token (required)
  JIRA_MYTEAM_USERS   Comma-separated list of usernames for default query (used if -u not provided)
        """
    )

    parser.add_argument(
        '-u', '--user',
        help='Comma-separated usernames to filter by (overrides JIRA_MYTEAM_USERS env var)'
    )

    parser.add_argument(
        '-q', '--query',
        help='JQL query to fetch issues (overrides default query including -u)'
    )

    parser.add_argument(
        '-d', '--show-details',
        action='store_true',
        help='Display detailed issue list below the board'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output (use with -d)'
    )

    parser.add_argument(
        '--max-results',
        type=int,
        default=200,
        help='Maximum number of results to fetch (default: 200)'
    )

    args = parser.parse_args()

    # Use custom query if provided, otherwise build default with -u or env var
    if args.query:
        jql_query = args.query
    else:
        jql_query = get_default_jql(users=args.user)

    print(f"[INFO] Executing JQL: {jql_query}", file=sys.stderr)

    # Fetch issues
    issues = get_issues_by_jql(jql_query, args.max_results)

    if not issues:
        print("No issues found matching the query.")
        return

    # Organize issues
    board_data, issue_details_list = organize_issues_by_assignee_and_status(issues)

    # Calculate status counts
    status_counts = {status: 0 for status in STATUS_COLUMNS}
    for assignee_data in board_data.values():
        for status, issues_list in assignee_data.items():
            if status in status_counts:
                status_counts[status] += len(issues_list)

    # Display header
    print("\n" + "="*120)
    print("JIRA FI BOARD")
    print("="*120)
    print(f"Query: {jql_query}")
    print(f"Total Issues Found: {len(issues)}")

    display_legend()

    # Display FI board
    display_fi_board(board_data, status_counts)

    # Display issue details if requested
    if args.show_details:
        display_issue_details(issue_details_list, verbose=args.verbose)

    print(f"\nTotal issues displayed: {len(issue_details_list)}")


if __name__ == '__main__':
    main()
