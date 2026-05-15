#!/usr/bin/env python3
# pip install requests
# pip install python-dotenv
# pip install pandas
# pip install tabulate
# pip install prettytable

import os
import argparse
import sys
import requests
import pandas as pd
from dotenv import load_dotenv
from prettytable import PrettyTable
from datetime import datetime
from collections import OrderedDict
from urllib.parse import urlparse

# Keep console output safe even when shell locale is ASCII.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
else:  # pragma: no cover
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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
    "-x", "--excludeCols",
    type=lambda s: s.split(','),
    help="Comma-separated list of Headers to exclude",
    default=[]
)

parser.add_argument(
    "-i", "--extraCols",
    type=lambda s: s.split(','),
    help="Comma-separated list of extra field names to include (e.g., 'Solution,Root Cause')",
    default=[]
)

parser.add_argument(
    "-p", "--profile",
    type=str,
    choices=['default', 'pvm', 'fi'],
    default='default',
    help="Output profile: 'default' (existing columns), 'pvm' (security/patch focused), 'fi' (FI-focused columns). "
         "When profile is default, auto-switches to fi if all keys are FI-* and to pvm if all keys are PVM-*"
)

# Add debug flag
parser.add_argument(
    "-d", "--debug",
    action="store_true",
    help="Enable debug output for field resolution and mapping."
)

args = parser.parse_args()

# Profile configurations: columns to exclude for each profile
PROFILE_EXCLUDES = {
    'default': ['CVSS', 'FixVers'],
    'pvm': ['Runtime', 'Reporter', 'IssueType', 'Labels', 'Epic'],
    'fi': []
}

FI_COLUMN_ORDER = [
    'Key',
    'Case Priority',
    'Priority',
    'Components',
    'Customer Name',
    'Assignee',
    'Affects Version/s',
    'Summary',
    'Status',
    'Case Status',
    'Updated',
    'Etrack Incident',
    'Squad Name',
    'Cap Involvement',
    'Customer Sentiment'
]

FI_DYNAMIC_FIELD_CANDIDATES = OrderedDict([
    ('Case Priority', ['Case Priority']),  # Removed incorrect alternative name
    ('Customer Name', ['Customer Name', 'Customer']),
    ('Case Status', ['Case Status']),
    ('Etrack Incident', ['Etrack Incident']),
    ('Squad Name', ['Squad Name']),
    ('Cap Involvement', ['CAP Involvement', 'Cap Involvement']),
    ('Customer Sentiment', ['Customer Sentiment'])
])

# Prefer stable Jira IDs (from working j.getJiraDetails.py behavior), then fall back to name resolution.
FI_STATIC_FIELD_IDS = {
    'Customer Name': 'customfield_18901',
    'Case Status': 'customfield_16200',
    'Etrack Incident': 'customfield_33802',
}


def format_jira_request_error(operation, url, timeout, exc):
    """Build actionable diagnostics for Jira SSL/network failures."""
    host = urlparse(url).hostname or 'unknown-host'
    details = str(exc)

    lines = [
        f"{operation} failed.",
        f"Endpoint: {url}",
        f"Host: {host} | Timeout: {timeout}s",
    ]

    if isinstance(exc, requests.exceptions.SSLError):
        lines.append("Cause: TLS/SSL handshake failure while connecting to Jira.")
        if 'UNEXPECTED_EOF_WHILE_READING' in details:
            lines.append(
                "Likely reason: VPN/proxy/network edge closed TLS handshake unexpectedly."
            )
        elif 'CERTIFICATE_VERIFY_FAILED' in details:
            lines.append(
                "Likely reason: certificate trust validation failed (CA chain/interception issue)."
            )
    elif isinstance(exc, requests.exceptions.ConnectTimeout):
        lines.append("Cause: connection timeout while trying to reach Jira.")
    elif isinstance(exc, requests.exceptions.ReadTimeout):
        lines.append("Cause: Jira did not respond before timeout.")
    elif isinstance(exc, requests.exceptions.ConnectionError):
        lines.append("Cause: network connection to Jira could not be established.")
    else:
        lines.append("Cause: HTTP request error while communicating with Jira.")

    lines.extend([
        f"Technical details: {details}",
        "Possible fixes:",
        "  1) Verify VPN/corporate network connectivity.",
        f"  2) Test TLS reachability: curl -Iv https://{host}/rest/api/2/myself",
        "  3) Check proxy/TLS interception settings and bypass Jira host if required.",
        "  4) Verify local certificate trust (system keychain/certifi) is up to date.",
        "  5) Retry in a few minutes to rule out transient edge/Jira issues.",
    ])

    return "\n".join(lines)


def get_all_fields():
    """Fetches all Jira fields and returns a name-to-ID mapping.

    Returns:
        dict: A dictionary mapping field names (lowercase) to their IDs.
    """
    global _field_cache
    if _field_cache is not None:
        return _field_cache

    timeout = 20
    url = f'{JIRA_URL}/rest/api/2/field'

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
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
        print(format_jira_request_error('Field discovery', url, timeout, e))
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


def get_field_id_by_any_name(field_names):
    """Resolve first matching Jira field ID from a list of display-name candidates."""
    for name in field_names:
        field_id, actual_name = get_field_id_by_name(name)
        if field_id:
            return field_id, actual_name
    return None, None


def resolve_fi_profile_fields():
    """Resolve FI profile dynamic columns to Jira field IDs."""
    mapping = {}
    extra_field_ids = []


    for column_name, candidates in FI_DYNAMIC_FIELD_CANDIDATES.items():
        static_id = FI_STATIC_FIELD_IDS.get(column_name)
        if static_id:
            mapping[column_name] = static_id
            extra_field_ids.append(static_id)
            if args.debug:
                print(f"Resolved FI column '{column_name}' -> {static_id} (static)")
            continue

        field_id, actual_name = get_field_id_by_any_name(candidates)
        if field_id:
            mapping[column_name] = field_id
            extra_field_ids.append(field_id)
            if args.debug:
                print(f"Resolved FI column '{column_name}' -> {field_id} ({actual_name})")
        else:
            mapping[column_name] = None
            if args.debug:
                print(f"Warning: FI column '{column_name}' field not found. Will show '-' values.")

    return mapping, extra_field_ids


def resolve_effective_profile(requested_profile, issues):
    """Auto-detect FI/PVM profile when requested profile is default."""
    if requested_profile != 'default' or not issues:
        return requested_profile

    keys = [issue.get('key', '') for issue in issues if issue.get('key')]
    if not keys:
        return requested_profile

    if all(key.startswith('FI-') for key in keys):
        return 'fi'

    if all(key.startswith('PVM-') for key in keys):
        return 'pvm'

    return requested_profile


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
        created = datetime.strptime(created_str.replace('Z', '+00:00').split('.')[0], "%Y-%m-%dT%H:%M:%S%z")

        if resolution_str and status in ['resolved', 'closed', 'done', 'complete', 'completed']:
            # Closed issue: creation to resolution
            resolved = datetime.strptime(resolution_str.replace('Z', '+00:00').split('.')[0], "%Y-%m-%dT%H:%M:%S%z")
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


def _extract_field_or_dash(issue, field_id):
    if not field_id:
        return '-'
    return extract_field_value(issue, field_id)


def _format_updated_timestamp(raw_value):
    if not raw_value:
        return '-'
    text = str(raw_value)
    if 'T' in text:
        text = text.replace('T', ' ')
    if len(text) >= 19:
        return text[:19]
    return text


# Function to get issues by JQL
def get_issues_by_jql(jql, extra_field_ids=None):
    """Fetches issues from Jira based on the provided JQL query.

    Args:
        jql (str): The JQL query to execute.
        extra_field_ids (list): Additional field IDs to fetch.

    Returns:
        list: A list of issues returned by the JQL query, or an empty list if an error occurs.
    """
    timeout = 20
    url = f'{JIRA_URL}/rest/api/2/search'

    try:

        base_fields = ['key',
                       'summary',
                       'status',
                       'assignee',
                       'reporter',
                       'priority',
                       'issuetype',
                       'labels',
                       'created',
                       'updated',
                       'resolutiondate',
                       'components',
                       'versions',
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

        response = requests.get(url, headers=headers, params=params, timeout=timeout)

        response.raise_for_status()  # Raises an HTTPError if the response code was unsuccessful

        return response.json().get('issues', [])

    except requests.exceptions.RequestException as e:
        print(format_jira_request_error('Issue search', url, timeout, e))
        return None


def print_issues_in_table_format(issues, excludeCols, extra_fields=None, profile='default', fi_field_map=None):
    """Prints the issues in a table format.

    Args:
        issues (list): The list of issues to display.
        excludeCols (list): The list of columns to exclude from the display.
        extra_fields (list): List of tuples (field_id, display_name) for extra columns.
    """
    # Extract the relevant data into a list of dictionaries
    data = []
    extra_fields = extra_fields or []
    fi_field_map = fi_field_map or {}

    for index, issue in enumerate(issues, start=1):
        key = issue['key']
        summary_limit = 70 if profile == 'fi' else 120
        summary = issue['fields']['summary'] if len(issue['fields']['summary']) < summary_limit else issue['fields']['summary'][:summary_limit] + "..."
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
        components = extract_field_value(issue, 'components')  # Use 'components' as the field ID directly
        affected_versions = extract_field_value(issue, 'versions')
        updated = _format_updated_timestamp(issue['fields'].get('updated'))

        # Highlight Customer Sentiment if RED or YELLOW
        customer_sentiment = _extract_field_or_dash(issue, fi_field_map.get('Customer Sentiment'))
        if customer_sentiment.upper() in ['RED', 'YELLOW']:
            customer_sentiment = f"\033[91m{customer_sentiment}\033[0m" if customer_sentiment.upper() == 'RED' else f"\033[93m{customer_sentiment}\033[0m"

        if profile == 'fi':
            fi_entry = {
                'Key': key,
                'Case Priority': _extract_field_or_dash(issue, fi_field_map.get('Case Priority')),  # Ensure only 'Case Priority' is used
                'Priority': priority,
                'Components': components,
                'Customer Name': _extract_field_or_dash(issue, fi_field_map.get('Customer Name')),
                'Assignee': assignee,
                'Affects Version/s': affected_versions,
                'Summary': summary,
                'Status': status,
                'Case Status': _extract_field_or_dash(issue, fi_field_map.get('Case Status')),
                'Updated': updated,
                'Etrack Incident': _extract_field_or_dash(issue, fi_field_map.get('Etrack Incident')),
                'Squad Name': _extract_field_or_dash(issue, fi_field_map.get('Squad Name')),
                'Cap Involvement': _extract_field_or_dash(issue, fi_field_map.get('Cap Involvement')),
                'Customer Sentiment': customer_sentiment,
            }

            for field_id, display_name in extra_fields:
                value = extract_field_value(issue, field_id)
                if len(str(value)) > 50:
                    value = str(value)[:50] + "..."
                fi_entry[display_name] = value

            filtered_entry = {k: v for k, v in fi_entry.items() if k not in excludeCols}
            data.append(filtered_entry)
            continue

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
    if profile == 'fi':
        ordered_columns = [col for col in FI_COLUMN_ORDER if col in df.columns.tolist()]
        remaining_columns = [col for col in df.columns.tolist() if col not in ordered_columns]
        table.field_names = ordered_columns + remaining_columns
    else:
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
    print(f"\nTotal rows: {len(df)}")
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

    fi_field_map = {}
    fi_extra_field_ids = []
    if args.profile in ['default', 'fi']:
        fi_field_map, fi_extra_field_ids = resolve_fi_profile_fields()

    requested_extra_ids = list(dict.fromkeys(extra_field_ids + fi_extra_field_ids))

    issues = get_issues_by_jql(args.jql, requested_extra_ids)

    if issues is None:
        print("Aborting due to Jira request failure.")
        return

    effective_profile = resolve_effective_profile(args.profile, issues)
    if effective_profile != args.profile:
        print(f"Auto-selected profile: {effective_profile} (from issue key pattern)")

    if not issues:
        print("No issues found.")
        return

    # Combine profile excludes with user-specified excludes
    all_excludes = list(set(args.excludeCols + PROFILE_EXCLUDES.get(effective_profile, [])))

    print_issues_in_table_format(issues, all_excludes, extra_fields, profile=effective_profile, fi_field_map=fi_field_map)


if __name__ == '__main__':
    main()
