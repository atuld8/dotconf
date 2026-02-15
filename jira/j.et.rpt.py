#!/usr/bin/env python3
"""
Bulk Jira Issue Report Generator

Reads Jira issue IDs from file/stdin or executes JQL query,
fetches issues in bulk for performance, and generates tabular reports.

Usage:
    # From file
    python3 j.bulkIssueReport.py -f issues.txt

    # From stdin
    cat issues.txt | python3 j.bulkIssueReport.py

    # With JQL where clause
    python3 j.bulkIssueReport.py -where "project = FI AND status = Open"

    # Custom fields
    python3 j.bulkIssueReport.py -f issues.txt --fields key,summary,status,assignee

    # Output formats
    python3 j.bulkIssueReport.py -f issues.txt --csv output.csv
    python3 j.bulkIssueReport.py -f issues.txt --json output.json

Dependencies:
    pip install requests python-dotenv pandas prettytable tabulate

Environment Variables:
    JIRA_SERVER_NAME    Jira server hostname (e.g., company.atlassian.net)
    JIRA_ACC_TOKEN      Jira API Bearer token
"""

import os
import sys
import re
import json
import argparse
import time
import shutil
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Check for required modules
try:
    import requests
except ImportError:
    print("Error: 'requests' module not found. Install with: pip3 install requests")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    pd = None  # Optional, for CSV/markdown export

try:
    from prettytable import PrettyTable
except ImportError:
    PrettyTable = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# ============================================================================
# Terminal Colors
# ============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'

    # Foreground colors
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'

    # Control flags
    enabled = False  # Set to True via --color flag
    notruncate = False  # Set to True via --notruncate flag
    BG_BLUE = '\033[44m'

    # Enabled flag - controlled by --color argument
    enabled = False

    @classmethod
    def c(cls, text: str, *colors) -> str:
        """Apply colors to text if colors are enabled."""
        if not cls.enabled:
            return text
        color_str = ''.join(colors)
        return f"{color_str}{text}{cls.RESET}"

    @classmethod
    def header(cls, text: str) -> str:
        """Format header text."""
        return cls.c(text, cls.BOLD, cls.CYAN)

    @classmethod
    def success(cls, text: str) -> str:
        """Format success/good text."""
        return cls.c(text, cls.GREEN)

    @classmethod
    def warning(cls, text: str) -> str:
        """Format warning text."""
        return cls.c(text, cls.YELLOW)

    @classmethod
    def error(cls, text: str) -> str:
        """Format error/critical text."""
        return cls.c(text, cls.RED)

    @classmethod
    def info(cls, text: str) -> str:
        """Format info text."""
        return cls.c(text, cls.BLUE)

    @classmethod
    def priority(cls, text: str, priority: str) -> str:
        """Color based on priority level."""
        if not cls.enabled:
            return text
        p = priority.lower() if priority else ''
        if p in ['blocker', 'critical']:
            return cls.c(text, cls.RED, cls.BOLD)
        elif p in ['p1', 'major']:
            return cls.c(text, cls.YELLOW)
        elif p in ['minor', 'trivial']:
            return cls.c(text, cls.DIM)
        return text

    @classmethod
    def category(cls, cat_id: str, text: str) -> str:
        """Color based on category."""
        if not cls.enabled:
            return text
        color_map = {
            'NO_ETRACK': cls.RED,
            'ET_CLOSED_JIRA_ACTIVE': cls.YELLOW,
            'JIRA_DONE_ET_ACTIVE': cls.YELLOW,
            'ET_WAITING_CASE_CLOSED': cls.YELLOW,
            'CASE_CLOSED_ET_NOT_CLOSED': cls.YELLOW,
            'READY_TO_CLOSE': cls.GREEN,
            'BOTH_CLOSED': cls.GREEN,
            'BOTH_ACTIVE': cls.BLUE,
            'CUSTOMER_WAITING': cls.CYAN,
        }
        color = color_map.get(cat_id, '')
        return cls.c(text, color) if color else text

    @classmethod
    def print_table(cls, table) -> None:
        """Print a PrettyTable with colored headers and borders."""
        if not cls.enabled:
            print(table)
            return

        table_str = str(table)
        lines = table_str.split('\n')

        for i, line in enumerate(lines):
            if line.startswith('+') or line.startswith('|---'):
                # Border/separator line - dim it
                print(cls.c(line, cls.DIM))
            elif i == 1:
                # Header row (second line, after top border)
                print(cls.c(line, cls.BOLD, cls.CYAN))
            else:
                print(line)

# ============================================================================
# Configuration
# ============================================================================

# Jira credentials
JIRA_URL = "https://" + os.getenv('JIRA_SERVER_NAME', '')
JIRA_API_TOKEN = os.getenv('JIRA_ACC_TOKEN', '')

# Default settings
DEFAULT_BATCH_SIZE = 50
DEFAULT_MAX_RESULTS = 1000
DEFAULT_TIMEOUT = 30

# Default fields to display (field_id -> display_name)
DEFAULT_FIELDS = {
    'key': 'Key',
    'summary': 'Summary',
    'assignee': 'Assignee',
    'priority': 'Priority',
    'status': 'Status',
    'customfield_16200': 'Case Status',
    'customfield_33802': 'Etrack Incident',
}

# Etrack configuration
DEFAULT_ETRACK_FIELDS = ['priority', 'severity', 'assigned_to', 'component', 'customer', 'state']
ETRACK_BATCH_SIZE = 10  # Number of etrack IDs per eprint call
RMTCMD_HOST = os.environ.get('RMTCMD_HOST', '')

# Common field aliases for user convenience
FIELD_ALIASES = {
    'key': 'key',
    'id': 'key',
    'summary': 'summary',
    'title': 'summary',
    'status': 'status',
    'state': 'status',
    'assignee': 'assignee',
    'owner': 'assignee',
    'reporter': 'reporter',
    'creator': 'reporter',
    'priority': 'priority',
    'severity': 'customfield_20303',
    'labels': 'labels',
    'fixversion': 'fixVersions',
    'fixversions': 'fixVersions',
    'issuetype': 'issuetype',
    'type': 'issuetype',
    'created': 'created',
    'updated': 'updated',
    'resolved': 'resolutiondate',
    'resolution': 'resolution',
    'epic': 'customfield_10008',
    'epiclink': 'customfield_10008',
    'epic_link': 'customfield_10008',
    'components': 'components',
    'casestatus': 'customfield_16200',
    'case_status': 'customfield_16200',
    'etrack': 'customfield_33802',
    'etrack_incident': 'customfield_33802',
    'cvss': 'customfield_33415',
    'cvss_score': 'customfield_33415',
    'sprint': 'customfield_10004',
    'storypoints': 'customfield_10002',
    'story_points': 'customfield_10002',
    'description': 'description',
    'comments': 'comment',
    'duedate': 'duedate',
    'due_date': 'duedate',
    'due': 'duedate',
    'project': 'project',
}

# Headers for API requests
HEADERS = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}


# ============================================================================
# Jira API Functions
# ============================================================================

class JiraReportClient:
    """Client for fetching Jira issues in bulk"""

    def __init__(self, jira_url: str = None, api_token: str = None,
                 batch_size: int = DEFAULT_BATCH_SIZE, timeout: int = DEFAULT_TIMEOUT):
        self.jira_url = jira_url or JIRA_URL
        self.api_token = api_token or JIRA_API_TOKEN
        self.batch_size = batch_size
        self.timeout = timeout
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
        self.api_calls = 0
        self.total_time = 0

        # Cache for field metadata
        self._field_cache = None

    def get_all_fields(self) -> Dict[str, Dict]:
        """
        Fetch all available Jira fields with their metadata.

        Returns:
            Dictionary mapping field_id to field metadata
        """
        if self._field_cache:
            return self._field_cache

        try:
            url = f'{self.jira_url}/rest/api/2/field'
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            self.api_calls += 1

            if response.status_code == 200:
                fields = response.json()
                self._field_cache = {
                    f['id']: {
                        'name': f.get('name', f['id']),
                        'type': f.get('schema', {}).get('type', 'string'),
                        'custom': f.get('custom', False),
                        'schema': f.get('schema', {})
                    }
                    for f in fields
                }
                return self._field_cache
            else:
                print(f"Warning: Could not fetch field metadata: {response.status_code}")
                return {}

        except Exception as e:
            print(f"Warning: Error fetching field metadata: {e}")
            return {}

    def resolve_field_name(self, field: str) -> Tuple[str, str]:
        """
        Resolve field name/alias to actual field ID and display name.

        Args:
            field: Field name, alias, or custom field ID

        Returns:
            Tuple of (field_id, display_name)
        """
        field_lower = field.lower().replace(' ', '_').replace('-', '_')

        # Check aliases first
        if field_lower in FIELD_ALIASES:
            field_id = FIELD_ALIASES[field_lower]
        elif field.startswith('customfield_'):
            field_id = field
        else:
            field_id = field

        # Get display name from field metadata
        all_fields = self.get_all_fields()
        if field_id in all_fields:
            display_name = all_fields[field_id]['name']
        elif field_id in DEFAULT_FIELDS:
            display_name = DEFAULT_FIELDS[field_id]
        else:
            display_name = field.replace('_', ' ').title()

        return field_id, display_name

    def fetch_issues_by_keys(self, issue_keys: List[str],
                              fields: List[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch multiple issues by their keys using batch JQL queries.

        Args:
            issue_keys: List of issue keys (e.g., ['FI-123', 'FI-456'])
            fields: List of field IDs to fetch

        Returns:
            List of issue data dictionaries
        """
        if not issue_keys:
            return []

        all_issues = []
        fields = fields or list(DEFAULT_FIELDS.keys())

        # Resolve field names
        resolved_fields = []
        for f in fields:
            field_id, _ = self.resolve_field_name(f)
            if field_id != 'key':  # key is always included
                resolved_fields.append(field_id)

        # Process in batches
        total_batches = (len(issue_keys) + self.batch_size - 1) // self.batch_size

        for i in range(0, len(issue_keys), self.batch_size):
            batch = issue_keys[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1

            if sys.stderr.isatty():
                print(f"\rFetching batch {batch_num}/{total_batches}...", end='', file=sys.stderr)

            batch_issues = self._fetch_batch(batch, resolved_fields)
            all_issues.extend(batch_issues)

        if sys.stderr.isatty():
            print(f"\rFetched {len(all_issues)} issues in {total_batches} API calls.    ", file=sys.stderr)

        return all_issues

    def _fetch_batch(self, issue_keys: List[str], fields: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch a batch of issues using JQL.

        Args:
            issue_keys: List of issue keys for this batch
            fields: List of field IDs to fetch

        Returns:
            List of issue data dictionaries
        """
        start_time = time.time()

        try:
            keys_str = ', '.join(issue_keys)
            jql = f'key in ({keys_str})'

            url = f'{self.jira_url}/rest/api/2/search'
            params = {
                'jql': jql,
                'maxResults': len(issue_keys),
                'fields': ','.join(fields)
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
            self.api_calls += 1
            self.total_time += time.time() - start_time

            if response.status_code == 200:
                return response.json().get('issues', [])
            else:
                print(f"\nWarning: Batch fetch failed: {response.status_code} - {response.text[:200]}", file=sys.stderr)
                return []

        except Exception as e:
            print(f"\nError fetching batch: {e}", file=sys.stderr)
            return []

    def fetch_issues_by_jql(self, jql: str, fields: List[str] = None,
                            max_results: int = DEFAULT_MAX_RESULTS) -> List[Dict[str, Any]]:
        """
        Fetch issues matching a JQL query.

        Args:
            jql: JQL query string
            fields: List of field IDs to fetch
            max_results: Maximum number of results

        Returns:
            List of issue data dictionaries
        """
        all_issues = []
        fields = fields or list(DEFAULT_FIELDS.keys())

        # Resolve field names
        resolved_fields = []
        for f in fields:
            field_id, _ = self.resolve_field_name(f)
            if field_id != 'key':
                resolved_fields.append(field_id)

        start_at = 0
        batch_num = 0

        while start_at < max_results:
            batch_num += 1
            if sys.stderr.isatty():
                print(f"\rFetching page {batch_num}...", end='', file=sys.stderr)

            try:
                start_time = time.time()
                url = f'{self.jira_url}/rest/api/2/search'
                params = {
                    'jql': jql,
                    'startAt': start_at,
                    'maxResults': min(self.batch_size, max_results - start_at),
                    'fields': ','.join(resolved_fields)
                }

                response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
                self.api_calls += 1
                self.total_time += time.time() - start_time

                if response.status_code == 200:
                    data = response.json()
                    issues = data.get('issues', [])
                    all_issues.extend(issues)

                    total = data.get('total', 0)
                    if len(issues) < self.batch_size or start_at + len(issues) >= total:
                        break

                    start_at += len(issues)
                else:
                    print(f"\nError: JQL search failed: {response.status_code} - {response.text[:200]}", file=sys.stderr)
                    break

            except Exception as e:
                print(f"\nError in JQL search: {e}", file=sys.stderr)
                break

        if sys.stderr.isatty():
            print(f"\rFetched {len(all_issues)} issues in {batch_num} API calls.    ", file=sys.stderr)

        return all_issues

    def get_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return {
            'api_calls': self.api_calls,
            'total_time': round(self.total_time, 2),
            'avg_time': round(self.total_time / self.api_calls, 2) if self.api_calls > 0 else 0
        }


# ============================================================================
# Etrack Client
# ============================================================================

class EtrackClient:
    """Client for fetching etrack incident data via esql command"""

    # Fields available in etrack incident table
    INCIDENT_FIELDS = [
        'incident', 'priority', 'severity', 'assigned_to', 'component',
        'customer', 'state', 'abstract', 'submitter', 'product', 'created_date',
        'group_owner', 'sr', 'type'
    ]

    def __init__(self, batch_size: int = ETRACK_BATCH_SIZE):
        self.batch_size = batch_size
        self.api_calls = 0
        self.total_time = 0.0
        # Check for local esql
        self.esql_local = shutil.which('esql')

    def _execute_esql(self, query: str, timeout: int = 120) -> str:
        """
        Execute esql query via stdin.

        Args:
            query: SQL query string
            timeout: Command timeout in seconds

        Returns:
            Raw output from esql
        """
        if RMTCMD_HOST and not self.esql_local:
            # Execute via SSH
            cmd = f"ssh {RMTCMD_HOST} esql"
        else:
            cmd = "esql"

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=query
        )

        if result.returncode != 0:
            raise RuntimeError(f"esql failed: {result.stderr[:200]}")

        return result.stdout

    def _parse_esql_output(self, output: str, fields: List[str]) -> Dict[str, Dict[str, str]]:
        """
        Parse esql output into dictionary of incident data.

        esql output is tab-separated with optional headers.

        Args:
            output: Raw esql output
            fields: List of field names in SELECT order

        Returns:
            Dict mapping incident_id -> {field: value}
        """
        results = {}
        lines = output.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Skip header/separator lines
            if line.startswith('---') or line.startswith('==='):
                continue
            if 'incident' in line.lower() and 'assigned_to' in line.lower():
                continue

            # Parse tab-separated values
            parts = line.split('\t')
            parts = [p.strip() for p in parts]

            if len(parts) >= 1 and parts[0].isdigit():
                incident_id = parts[0]
                data = {}
                for i, field in enumerate(fields):
                    if i < len(parts):
                        data[field.lower()] = parts[i]
                    else:
                        data[field.lower()] = ''
                results[incident_id] = data

        return results

    def fetch_etrack_data(self, incident_ids: List[str], etrack_fields: List[str] = None,
                          verbose: bool = False) -> Dict[str, Dict[str, str]]:
        """
        Fetch etrack data for given incident IDs using esql.

        Args:
            incident_ids: List of etrack incident IDs
            etrack_fields: List of fields to fetch (default: all common fields)
            verbose: Print progress info

        Returns:
            Dict mapping incident_id -> {field: value}
        """
        if not incident_ids:
            return {}

        unique_ids = list(set(eid.strip() for eid in incident_ids if eid.strip() and eid.strip().isdigit()))
        if not unique_ids:
            return {}

        # Determine fields to fetch
        if etrack_fields:
            # Always include incident as first field
            fields = ['incident'] + [f for f in etrack_fields if f.lower() != 'incident']
        else:
            fields = DEFAULT_ETRACK_FIELDS.copy()
            if 'incident' not in fields:
                fields.insert(0, 'incident')

        all_data = {}

        # Batch IDs to avoid overly long IN clauses (max ~500 per query)
        max_ids_per_query = 500
        batches = [unique_ids[i:i + max_ids_per_query] for i in range(0, len(unique_ids), max_ids_per_query)]

        for batch_num, batch in enumerate(batches, start=1):
            if verbose or sys.stderr.isatty():
                print(f"\rFetching etrack batch {batch_num}/{len(batches)} ({len(batch)} IDs)...", end='', file=sys.stderr)

            # Build SQL query
            id_list = ', '.join(batch)
            field_list = ', '.join(fields)
            query = f"SELECT {field_list} FROM incident WHERE incident IN ({id_list})"

            start = time.time()

            try:
                output = self._execute_esql(query)
                self.api_calls += 1
                self.total_time += time.time() - start

                batch_data = self._parse_esql_output(output, fields)
                all_data.update(batch_data)

            except subprocess.TimeoutExpired:
                print(f"\nWarning: esql timed out for batch {batch_num}", file=sys.stderr)
            except Exception as e:
                print(f"\nWarning: esql error: {e}", file=sys.stderr)

        if sys.stderr.isatty():
            print(f"\rFetched etrack data for {len(all_data)} incidents.    ", file=sys.stderr)

        return all_data

    def get_stats(self) -> Dict[str, Any]:
        """Get etrack fetch statistics"""
        return {
            'etrack_calls': self.api_calls,
            'etrack_time': round(self.total_time, 2),
            'avg_time': round(self.total_time / self.api_calls, 2) if self.api_calls > 0 else 0
        }


# ============================================================================
# Data Extraction Functions
# ============================================================================

def extract_field_value(issue: Dict[str, Any], field_id: str, field_meta: Dict = None) -> str:
    """
    Extract a field value from issue data, handling various field types.

    Args:
        issue: Raw issue data from Jira API
        field_id: Field ID to extract
        field_meta: Optional field metadata for type handling

    Returns:
        String representation of the field value (single line, cleaned)
    """
    if field_id == 'key':
        return issue.get('key', '')

    fields = issue.get('fields', {})
    value = fields.get(field_id)

    if value is None:
        return ''

    result = ''

    # Handle different field types
    if isinstance(value, str):
        result = value

    elif isinstance(value, dict):
        # Common nested objects: status, assignee, priority, etc.
        if 'displayName' in value:
            result = value['displayName']
        elif 'name' in value:
            result = value['name']
        elif 'value' in value:
            result = value['value']
        elif 'key' in value:
            result = value['key']
        else:
            result = str(value)

    elif isinstance(value, list):
        # Array fields: labels, components, fixVersions, etc.
        if len(value) == 0:
            result = ''
        elif isinstance(value[0], str):
            result = ', '.join(value)
        elif isinstance(value[0], dict):
            names = []
            for item in value:
                if 'name' in item:
                    names.append(item['name'])
                elif 'displayName' in item:
                    names.append(item['displayName'])
                elif 'value' in item:
                    names.append(item['value'])
            result = ', '.join(names) if names else str(value)
        else:
            result = str(value)

    elif isinstance(value, (int, float)):
        result = str(value)

    else:
        result = str(value)

    # Clean: remove newlines, normalize whitespace
    result = ' '.join(result.split())

    return result


def process_issues(issues: List[Dict[str, Any]], fields: List[str],
                   client: JiraReportClient, max_summary_len: int = 100) -> List[Dict[str, str]]:
    """
    Process raw issue data into a list of display-ready dictionaries.

    Args:
        issues: Raw issue data from Jira API
        fields: List of field names/IDs to include
        client: JiraReportClient for field resolution
        max_summary_len: Maximum summary length (truncate if longer)

    Returns:
        List of dictionaries with display names as keys
    """
    processed = []
    all_field_meta = client.get_all_fields()

    # Build field mapping
    field_mapping = []  # (field_id, display_name)
    for f in fields:
        field_id, display_name = client.resolve_field_name(f)
        field_mapping.append((field_id, display_name))

    for idx, issue in enumerate(issues, start=1):
        row = {'#': idx}

        for field_id, display_name in field_mapping:
            value = extract_field_value(issue, field_id, all_field_meta.get(field_id))

            # Truncate summary if too long
            if field_id == 'summary' and len(value) > max_summary_len:
                value = value[:max_summary_len] + '...'

            row[display_name] = value

        processed.append(row)

    return processed


# ============================================================================
# Input Functions
# ============================================================================

def parse_issue_ids(text: str) -> List[str]:
    """
    Parse Jira issue IDs from text.

    Handles various formats:
    - One ID per line
    - Comma/space separated
    - URLs containing IDs
    - Mixed content

    Args:
        text: Text containing issue IDs

    Returns:
        List of unique issue IDs
    """
    # Pattern to match Jira issue keys (PROJECT-NUMBER)
    pattern = r'([A-Z][A-Z0-9_]+-\d+)'

    matches = re.findall(pattern, text.upper())

    # Remove duplicates while preserving order
    seen = set()
    unique_ids = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique_ids.append(match)

    return unique_ids


def read_ids_from_file(filepath: str) -> List[str]:
    """Read issue IDs from a file"""
    with open(filepath, 'r') as f:
        content = f.read()
    return parse_issue_ids(content)


def read_ids_from_stdin() -> List[str]:
    """Read issue IDs from stdin"""
    if sys.stdin.isatty():
        return []
    content = sys.stdin.read()
    return parse_issue_ids(content)


# ============================================================================
# Output Functions
# ============================================================================

def print_table(data: List[Dict[str, str]], format_style: str = 'grid'):
    """
    Print data as a formatted table.

    Args:
        data: List of row dictionaries
        format_style: Table format (grid, simple, plain, markdown)
    """
    if not data:
        print("No data to display.")
        return

    # Clean data: remove newlines and control characters
    cleaned_data = []
    for row in data:
        cleaned_row = {}
        for k, v in row.items():
            if isinstance(v, str):
                # Replace newlines with spaces and strip
                v = ' '.join(v.split())
            cleaned_row[k] = v
        cleaned_data.append(cleaned_row)
    data = cleaned_data

    if PrettyTable is None:
        # Fallback: simple column output
        print("Warning: prettytable not installed, using simple format", file=sys.stderr)
        headers = list(data[0].keys())
        print('\t'.join(headers))
        print('-' * 80)
        for row in data:
            print('\t'.join(str(v) for v in row.values()))
        return

    # Define max width per field type (truncate, not wrap)
    field_max_widths = {}
    for field in data[0].keys():
        field_lower = field.lower()
        if 'summary' in field_lower:
            field_max_widths[field] = 70
        elif 'description' in field_lower:
            field_max_widths[field] = 50
        elif field_lower in ('labels', 'components', 'fixversions', 'fix versions'):
            field_max_widths[field] = 25
        elif field_lower in ('assignee', 'reporter'):
            field_max_widths[field] = 20

    # Pre-truncate all fields to prevent PrettyTable wrapping
    truncated_data = []
    for row in data:
        truncated_row = {}
        for k, v in row.items():
            v_str = str(v) if v is not None else ''
            max_w = field_max_widths.get(k)
            if max_w and len(v_str) > max_w:
                v_str = v_str[:max_w-3] + '...'
            truncated_row[k] = v_str
        truncated_data.append(truncated_row)
    data = truncated_data

    # Use PrettyTable for terminal output
    table = PrettyTable()
    table.field_names = list(data[0].keys())

    # Disable wrapping - all data is pre-truncated
    table.hrules = 0  # No horizontal rules between rows

    # Set alignment
    for field in table.field_names:
        if field in ('#', 'Key'):
            table.align[field] = 'l'
        elif field in ('Priority', 'Status'):
            table.align[field] = 'c'
        else:
            table.align[field] = 'l'

    for row in data:
        table.add_row(list(row.values()))

    Colors.print_table(table)


def export_csv(data: List[Dict[str, str]], filepath: str):
    """Export data to CSV file"""
    if not data:
        print("No data to export.")
        return

    if pd is not None:
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
    else:
        # Fallback: manual CSV writing
        import csv
        with open(filepath, 'w', newline='') as f:
            if data:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)

    print(f"Exported {len(data)} rows to {filepath}", file=sys.stderr)


def export_json(data: List[Dict[str, str]], filepath: str, raw_issues: List[Dict] = None):
    """
    Export data to JSON file.

    Args:
        data: Processed data for display
        filepath: Output file path
        raw_issues: Optional raw issue data for full export
    """
    if not data:
        print("No data to export.")
        return

    output = {
        'exported_at': datetime.now().isoformat(),
        'count': len(data),
        'issues': data
    }

    if raw_issues:
        output['raw_issues'] = raw_issues

    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"Exported {len(data)} issues to {filepath}", file=sys.stderr)


def print_markdown(data: List[Dict[str, str]]):
    """Print data as markdown table"""
    if not data:
        print("No data to display.")
        return

    if pd is not None:
        df = pd.DataFrame(data)
        print(df.to_markdown(index=False))
    else:
        # Fallback: manual markdown generation
        headers = list(data[0].keys())
        print('| ' + ' | '.join(headers) + ' |')
        print('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        for row in data:
            print('| ' + ' | '.join(str(v).replace('|', '\\|') for v in row.values()) + ' |')

    df = pd.DataFrame(data)
    print(df.to_markdown(index=False))


# ============================================================================
# CLI Functions
# ============================================================================

def list_available_fields(client: JiraReportClient):
    """List all available Jira fields"""
    print("\nFetching available fields...\n")
    fields = client.get_all_fields()

    # Organize by custom vs standard
    standard = []
    custom = []

    for field_id, meta in sorted(fields.items()):
        entry = (field_id, meta['name'], meta['type'])
        if meta['custom']:
            custom.append(entry)
        else:
            standard.append(entry)

    def print_field_table(title, entries, headers):
        print("=" * 80)
        print(title)
        print("=" * 80)
        if PrettyTable:
            table = PrettyTable(headers)
            table.align = 'l'
            for entry in entries:
                table.add_row(entry)
            Colors.print_table(table)
        else:
            # Fallback: simple format
            print(f"{headers[0]:<30} {headers[1]:<30} {headers[2] if len(headers) > 2 else ''}")
            print("-" * 80)
            for entry in entries:
                print(f"{entry[0]:<30} {entry[1]:<30} {entry[2] if len(entry) > 2 else ''}")

    print_field_table("STANDARD FIELDS",
                      sorted(standard, key=lambda x: x[1].lower()),
                      ['Field ID', 'Name', 'Type'])

    print()
    print_field_table("CUSTOM FIELDS",
                      sorted(custom, key=lambda x: x[1].lower()),
                      ['Field ID', 'Name', 'Type'])

    print()
    print_field_table("FIELD ALIASES (use these instead of field IDs)",
                      [(alias, field_id, '') for alias, field_id in sorted(FIELD_ALIASES.items())],
                      ['Alias', 'Maps To', ''])


# ============================================================================
# Analyzer Functions
# ============================================================================

def analyze_status_combinations(processed_data: List[Dict]) -> Dict[str, Any]:
    """
    Analyze data based on Jr Status, Jr Case Status, and ET State combinations.

    Returns analysis dict with categorized issues.
    """
    # Define status categories
    # Jira Status values: "In Progress", "Solution Provided", "Pre closing", "Waiting on Support", etc.
    # Case Status values: "Engineering pending", "Customer pending", "Closed", "Work in progress", etc.
    # ET State values: "OPEN", "WORKING", "WAITING", "CLOSED", "FIXED", "VERIFYING", "REOPEN", etc.

    JIRA_DONE_STATUSES = {'solution provided', 'pre closing', 'closed', 'resolved'}
    JIRA_ACTIVE_STATUSES = {'in progress', 'waiting on support', 'open', 'new'}

    CASE_CLOSED_STATUSES = {'closed', 'duplicate'}
    CASE_ENG_DONE_STATUSES = {'eng solution provided', 'eng responded', 'solution provided/monitoring'}
    CASE_ENG_PENDING_STATUSES = {'engineering pending', 'work in progress'}
    CASE_CUSTOMER_STATUSES = {'customer pending', 'customer updated', 'close pending', '3rd party pending'}

    ET_CLOSED_STATES = {'closed', 'fixed', 'verifying'}
    ET_ACTIVE_STATES = {'open', 'working', 'reopen'}
    ET_WAITING_STATES = {'waiting', 'pending'}

    # Analysis categories
    categories = {
        'NO_ETRACK': {
            'title': 'NO ETRACK LINKED',
            'description': 'FIs with no Etrack incident - needs triage',
            'issues': [],
            'priority': 1
        },
        'ET_CLOSED_JIRA_ACTIVE': {
            'title': 'ETRACK CLOSED BUT JIRA ACTIVE',
            'description': 'Etrack closed/fixed but Jira still In Progress - may need to update Jira',
            'issues': [],
            'priority': 2
        },
        'JIRA_DONE_ET_ACTIVE': {
            'title': 'JIRA DONE BUT ETRACK ACTIVE',
            'description': 'Jira Solution Provided but Etrack still OPEN/WORKING/REOPEN - needs eng follow-up',
            'issues': [],
            'priority': 3
        },
        'ET_WAITING_CASE_CLOSED': {
            'title': 'ETRACK WAITING BUT CASE CLOSED',
            'description': 'Etrack in WAITING state but Case Status is Closed - may need to close etrack',
            'issues': [],
            'priority': 4
        },
        'CASE_CLOSED_ET_NOT_CLOSED': {
            'title': 'CASE CLOSED BUT ETRACK NOT CLOSED',
            'description': 'Case Closed + Jira Solution Provided but Etrack in any non-closed state - may need to close etrack',
            'issues': [],
            'priority': 5
        },
        'CASE_CLOSED_JIRA_ACTIVE': {
            'title': 'CASE CLOSED BUT JIRA ACTIVE',
            'description': 'Case Closed but Jira still In Progress/Active - needs Jira status update',
            'issues': [],
            'priority': 6
        },
        'BOTH_CLOSED': {
            'title': 'ALL CLOSED/DONE',
            'description': 'Jira Done + Case Closed + Etrack Closed - fully completed',
            'issues': [],
            'priority': 10
        },
        'BOTH_ACTIVE': {
            'title': 'BOTH ACTIVE (Work in Progress)',
            'description': 'Both Jira and Etrack actively being worked on',
            'issues': [],
            'priority': 11
        },
        'CUSTOMER_WAITING': {
            'title': 'CUSTOMER PENDING',
            'description': 'Waiting on customer response',
            'issues': [],
            'priority': 12
        },
        'READY_TO_CLOSE': {
            'title': 'READY TO CLOSE',
            'description': 'Jira Solution Provided + Etrack CLOSED/FIXED - ready for final closure',
            'issues': [],
            'priority': 5
        },
        'OTHER': {
            'title': 'OTHER/REVIEW NEEDED',
            'description': 'State combinations that need manual review',
            'issues': [],
            'priority': 20
        }
    }

    def find_column(row: Dict, patterns: List[str], exclude_patterns: List[str] = None) -> str:
        """Find column value by pattern matching column names."""
        exclude_patterns = exclude_patterns or []
        for key, value in row.items():
            key_lower = key.lower().replace(' ', '').replace('_', '')
            # Check if any pattern matches
            if any(p in key_lower for p in patterns):
                # Check exclusions
                if not any(ex in key_lower for ex in exclude_patterns):
                    return str(value) if value else ''
        return ''

    # Track FIs with multiple Etracks
    multi_etrack_fis = []

    # Classify each issue
    for row in processed_data:
        # Extract relevant fields using flexible pattern matching
        jr_key = find_column(row, ['key', 'jrkey', 'fikey', 'issue'])
        jr_status = find_column(row, ['jrstatus', 'status'], exclude_patterns=['case', 'et']).lower().strip()
        jr_case_status = find_column(row, ['casestatus', 'jrcase']).lower().strip()
        jr_assignee = find_column(row, ['assignee', 'jrassignee'], exclude_patterns=['et'])
        jr_priority = find_column(row, ['priority', 'jrpriority'], exclude_patterns=['et'])
        et_state = find_column(row, ['etstate', 'state'], exclude_patterns=['case', 'jr']).lower().strip()
        et_incident_raw = find_column(row, ['etrack', 'incident', 'etincident', 'jretrack'])
        et_assigned = find_column(row, ['etassign', 'etassignedto'])

        # Parse multiple Etracks (comma-separated)
        et_incidents_list = []
        if et_incident_raw:
            for eid in str(et_incident_raw).split(','):
                eid = eid.strip()
                if eid:
                    et_incidents_list.append(eid)

        # Use first Etrack for classification
        et_incident = et_incidents_list[0] if et_incidents_list else ''

        # Track FIs with multiple Etracks
        if len(et_incidents_list) > 1:
            multi_etrack_fis.append({
                'key': jr_key,
                'etracks': et_incidents_list,
                'et_state': et_state  # Note: this is only the first Etrack's state
            })

        issue_info = {
            'key': jr_key,
            'jr_status': jr_status,
            'jr_case_status': jr_case_status,
            'jr_assignee': jr_assignee,
            'jr_priority': jr_priority,
            'et_state': et_state,
            'et_incident': et_incident,
            'et_all_incidents': et_incidents_list,  # Store all Etracks
            'et_assigned': et_assigned,
            'row': row
        }

        # Classification logic
        has_etrack = bool(et_incident and str(et_incident).strip())

        if not has_etrack:
            categories['NO_ETRACK']['issues'].append(issue_info)
        # BOTH_CLOSED now requires ALL THREE to be done/closed
        elif et_state in ET_CLOSED_STATES and jr_case_status in CASE_CLOSED_STATUSES and jr_status in JIRA_DONE_STATUSES:
            categories['BOTH_CLOSED']['issues'].append(issue_info)
        elif jr_status in JIRA_DONE_STATUSES and et_state in ET_CLOSED_STATES:
            categories['READY_TO_CLOSE']['issues'].append(issue_info)
        elif et_state in ET_CLOSED_STATES and jr_status in JIRA_ACTIVE_STATUSES:
            categories['ET_CLOSED_JIRA_ACTIVE']['issues'].append(issue_info)
        # NEW: Specific case - BOTH Case Closed AND Jira Done, but Etrack not closed
        elif jr_case_status in CASE_CLOSED_STATUSES and jr_status in JIRA_DONE_STATUSES and et_state not in ET_CLOSED_STATES:
            categories['CASE_CLOSED_ET_NOT_CLOSED']['issues'].append(issue_info)
        # Broader: Jira Done but Etrack active (Case may or may not be closed)
        elif jr_status in JIRA_DONE_STATUSES and et_state in ET_ACTIVE_STATES:
            categories['JIRA_DONE_ET_ACTIVE']['issues'].append(issue_info)
        # Broader: Case Closed and Etrack WAITING (Jira may or may not be done)
        elif et_state in ET_WAITING_STATES and jr_case_status in CASE_CLOSED_STATUSES:
            categories['ET_WAITING_CASE_CLOSED']['issues'].append(issue_info)
        # Case Closed but Jira still active (any Etrack state)
        elif jr_case_status in CASE_CLOSED_STATUSES and jr_status in JIRA_ACTIVE_STATUSES:
            categories['CASE_CLOSED_JIRA_ACTIVE']['issues'].append(issue_info)
        elif jr_case_status in CASE_CUSTOMER_STATUSES:
            categories['CUSTOMER_WAITING']['issues'].append(issue_info)
        elif et_state in ET_ACTIVE_STATES and jr_status in JIRA_ACTIVE_STATUSES:
            categories['BOTH_ACTIVE']['issues'].append(issue_info)
        else:
            # Further classify "other" based on patterns
            categories['OTHER']['issues'].append(issue_info)

    # Store multi-etrack FIs as metadata
    categories['_metadata'] = {
        'multi_etrack_fis': multi_etrack_fis
    }

    return categories


def get_unique_etracks(issues: List[Dict]) -> set:
    """Get unique Etrack IDs from a list of issues."""
    etracks = set()
    for issue in issues:
        et = issue.get('et_incident', '')
        if et and str(et).strip():
            etracks.add(str(et).strip())
    return etracks


def fi_sort_key(issue: Dict) -> tuple:
    """Extract sort key from FI key for natural sorting (e.g., FI-9 < FI-123)."""
    import re
    key = issue.get('key', '')
    # Extract prefix and numeric part (e.g., "FI-1234" -> ("FI-", 1234))
    match = re.match(r'^([A-Za-z]+-)(\d+)$', key)
    if match:
        return (match.group(1), int(match.group(2)))
    return (key, 0)


def print_analyzer_summary(categories: Dict[str, Any], total_count: int):
    """Print summary statistics for analyzer results."""
    print()
    print(Colors.header("=" * 80))
    print(Colors.header("ANALYZER SUMMARY"))
    print(Colors.header("=" * 80))
    print(f"Total Issues Analyzed: {Colors.c(str(total_count), Colors.BOLD)}")
    print(Colors.c("-" * 80, Colors.DIM))

    # Extract metadata (multi-etrack FIs info)
    metadata = categories.get('_metadata', {})
    multi_etrack_fis = metadata.get('multi_etrack_fis', [])

    # Sort by priority (exclude metadata)
    sorted_cats = sorted(
        [(k, v) for k, v in categories.items() if k != '_metadata'],
        key=lambda x: x[1].get('priority', 99)
    )

    # Build Etrack -> FI info mapping across all categories
    etrack_to_issues = {}  # etrack -> list of {key, jr_status, jr_case_status, category}
    for cat_id, cat_data in sorted_cats:
        for issue in cat_data.get('issues', []):
            et = issue.get('et_incident', '')
            if et and str(et).strip():
                et = str(et).strip()
                if et not in etrack_to_issues:
                    etrack_to_issues[et] = []
                etrack_to_issues[et].append({
                    'key': issue['key'],
                    'jr_status': issue.get('jr_status', ''),
                    'jr_case_status': issue.get('jr_case_status', ''),
                    'category': cat_id
                })

    # Find Etracks with multiple FIs or appearing in multiple categories
    dup_etracks = {et: fis for et, fis in etrack_to_issues.items() if len(fis) > 1}
    # Find Etracks where FIs have different statuses
    diff_status_etracks = {}
    for et, fis in dup_etracks.items():
        jr_statuses = set(f['jr_status'] for f in fis if f['jr_status'])
        case_statuses = set(f['jr_case_status'] for f in fis if f['jr_case_status'])
        if len(jr_statuses) > 1 or len(case_statuses) > 1:
            diff_status_etracks[et] = fis

    for cat_id, cat_data in sorted_cats:
        fi_count = len(cat_data['issues'])
        if fi_count > 0:
            unique_etracks = get_unique_etracks(cat_data['issues'])
            et_count = len(unique_etracks)
            pct = (fi_count / total_count * 100) if total_count > 0 else 0
            title_colored = Colors.category(cat_id, cat_data['title'])

            # Show both counts if different
            if et_count > 0 and et_count != fi_count:
                print(f"{title_colored}: {fi_count} FIs / {et_count} unique Etracks ({pct:.1f}%)")
            else:
                print(f"{title_colored}: {fi_count} ({pct:.1f}%)")
            print(f"    - {cat_data['description']}")

    # Warning about duplicate Etracks
    if dup_etracks:
        print(Colors.c("-" * 80, Colors.DIM))
        print(Colors.warning(f"NOTE: {len(dup_etracks)} Etrack(s) linked to multiple FIs"))

        # Etracks with DIFFERENT statuses
        if diff_status_etracks:
            print(Colors.error(f"WARNING: {len(diff_status_etracks)} Etrack(s) have FIs with DIFFERENT statuses:"))
            for et, fis in diff_status_etracks.items():
                fi_details = []
                for f in fis:
                    status_info = f"{f['key']} ({f['jr_status']}"
                    if f['jr_case_status']:
                        status_info += f" / {f['jr_case_status']}"
                    status_info += ")"
                    fi_details.append(status_info)
                print(f"  {et}: {', '.join(fi_details)}")

        # Etracks with SAME statuses (multiple FIs, but consistent status)
        same_status_etracks = {et: fis for et, fis in dup_etracks.items() if et not in diff_status_etracks}
        if same_status_etracks:
            print(Colors.info(f"INFO: {len(same_status_etracks)} Etrack(s) have multiple FIs with SAME status:"))
            for et, fis in same_status_etracks.items():
                fi_keys = [f['key'] for f in fis]
                # Get the common status
                common_status = fis[0]['jr_status'] if fis else ''
                common_case = fis[0]['jr_case_status'] if fis else ''
                status_str = common_status
                if common_case:
                    status_str += f" / {common_case}"
                print(f"  {et}: {', '.join(fi_keys)} (all: {status_str})")

    # Warning about FIs with multiple Etracks
    if multi_etrack_fis:
        print(Colors.c("-" * 80, Colors.DIM))
        print(Colors.warning(f"NOTE: {len(multi_etrack_fis)} FI(s) linked to MULTIPLE Etracks (only first Etrack's state used for classification):"))
        for fi_info in multi_etrack_fis:
            etracks_str = ', '.join(fi_info['etracks'])
            print(f"  {fi_info['key']}: {etracks_str} (classified using state: {fi_info['et_state'].upper() or 'N/A'})")

    print(Colors.header("=" * 80))


def print_analyzer_detailed(categories: Dict[str, Any]):
    """Print detailed breakdown for each category."""
    # Sort by priority (actionable items first, exclude metadata)
    sorted_cats = sorted(
        [(k, v) for k, v in categories.items() if k != '_metadata'],
        key=lambda x: x[1].get('priority', 99)
    )

    for cat_id, cat_data in sorted_cats:
        issues = cat_data['issues']
        if not issues:
            continue

        unique_etracks = get_unique_etracks(issues)
        et_count = len(unique_etracks)
        fi_count = len(issues)

        print("\n" + "=" * 80)
        if et_count > 0 and et_count != fi_count:
            print(f"{cat_data['title']} ({fi_count} FIs / {et_count} unique Etracks)")
        else:
            print(f"{cat_data['title']} ({fi_count} issues)")
        print(f"{cat_data['description']}")
        print("=" * 80)

        # Build table for this category
        if PrettyTable:
            table = PrettyTable()
            table.field_names = ['#', 'Key', 'Assignee', 'Priority', 'Jr Status', 'Case Status', 'ET State', 'ET Incident']
            table.align = 'l'

            # Sort issues by FI key
            sorted_issues = sorted(issues, key=fi_sort_key)
            display_issues = sorted_issues if Colors.notruncate else sorted_issues[:50]
            for idx, issue in enumerate(display_issues, 1):
                table.add_row([
                    idx,
                    issue['key'],
                    issue['jr_assignee'][:20] if issue['jr_assignee'] else '',
                    issue['jr_priority'],
                    issue['jr_status'][:20] if issue['jr_status'] else '',
                    issue['jr_case_status'][:25] if issue['jr_case_status'] else '',
                    issue['et_state'].upper() if issue['et_state'] else '',
                    issue['et_incident']
                ])

            Colors.print_table(table)

            if not Colors.notruncate and len(issues) > 50:
                print(f"... and {len(issues) - 50} more issues")
        else:
            # Fallback: simple format
            print(f"{'#':<4} {'Key':<10} {'Assignee':<20} {'Jr Status':<20} {'Case Status':<25} {'ET State':<10}")
            print("-" * 90)
            # Sort issues by FI key
            sorted_issues = sorted(issues, key=fi_sort_key)
            display_issues = sorted_issues if Colors.notruncate else sorted_issues[:50]
            for idx, issue in enumerate(display_issues, 1):
                print(f"{idx:<4} {issue['key']:<10} {str(issue['jr_assignee'])[:18]:<20} "
                      f"{issue['jr_status'][:18]:<20} {issue['jr_case_status'][:23]:<25} "
                      f"{issue['et_state'].upper():<10}")

        # Print FI list for easy copy-paste
        fi_list = ','.join([i['key'] for i in issues])
        if Colors.notruncate or len(fi_list) < 500:
            print(f"\nFI List: {fi_list}")
        else:
            print(f"\nFI List: {fi_list[:500]}...")

        # For categories where action is on Etrack, also print Etrack list (deduplicated)
        if cat_id in ['ET_WAITING_CASE_CLOSED', 'CASE_CLOSED_ET_NOT_CLOSED', 'JIRA_DONE_ET_ACTIVE', 'READY_TO_CLOSE']:
            unique_et = sorted(get_unique_etracks(issues))
            if unique_et:
                et_list = ','.join(unique_et)
                if Colors.notruncate or len(et_list) < 500:
                    print(f"Etrack List ({len(unique_et)} unique): {et_list}")
                else:
                    print(f"Etrack List ({len(unique_et)} unique): {et_list[:500]}...")

                # Check for duplicates (same etrack linked to multiple FIs in this category)
                et_to_fis = {}
                for issue in issues:
                    et = issue.get('et_incident', '')
                    if et:
                        if et not in et_to_fis:
                            et_to_fis[et] = []
                        et_to_fis[et].append({
                            'key': issue['key'],
                            'jr_status': issue.get('jr_status', ''),
                            'jr_case_status': issue.get('jr_case_status', '')
                        })

                multi_fi_etracks = {et: fis for et, fis in et_to_fis.items() if len(fis) > 1}
                if multi_fi_etracks:
                    print(Colors.warning(f"  [!] {len(multi_fi_etracks)} Etrack(s) linked to multiple FIs:"))
                    for et, fis in multi_fi_etracks.items():
                        fi_keys = [f['key'] for f in fis]
                        # Check if FIs have different statuses
                        jr_statuses = set(f['jr_status'] for f in fis if f['jr_status'])
                        case_statuses = set(f['jr_case_status'] for f in fis if f['jr_case_status'])

                        status_note = ""
                        if len(jr_statuses) > 1:
                            status_note += f" [Jr Status differs: {', '.join(sorted(jr_statuses))}]"
                        if len(case_statuses) > 1:
                            status_note += f" [Case Status differs: {', '.join(sorted(case_statuses))}]"

                        if status_note:
                            print(Colors.error(f"      {et} -> {', '.join(fi_keys)}{status_note}"))
                        else:
                            print(f"      {et} -> {', '.join(fi_keys)}")

        # Check for FIs with multiple Etracks in this category
        multi_et_fis = [i for i in issues if len(i.get('et_all_incidents', [])) > 1]
        if multi_et_fis:
            print(Colors.warning(f"  [!] {len(multi_et_fis)} FI(s) with MULTIPLE Etracks (only first used for classification):"))
            for issue in multi_et_fis:
                etracks_str = ', '.join(issue.get('et_all_incidents', []))
                print(f"      {issue['key']}: {etracks_str}")


def print_analyzer_state_matrix(categories: Dict[str, Any], processed_data: List[Dict]):
    """Print state combination matrix."""
    print("\n" + "=" * 80)
    print("STATE COMBINATION MATRIX")
    print("=" * 80)

    # Count combinations
    combos = {}
    for row in processed_data:
        jr_status = str(row.get('Jr Status', row.get('Status', ''))).strip() or '(empty)'
        et_state = str(row.get('ET State', '')).strip().upper() or '(empty)'

        key = (jr_status, et_state)
        if key not in combos:
            combos[key] = 0
        combos[key] += 1

    # Sort by count descending
    sorted_combos = sorted(combos.items(), key=lambda x: -x[1])

    if PrettyTable:
        table = PrettyTable()
        table.field_names = ['Jr Status', 'ET State', 'Count']
        table.align['Jr Status'] = 'l'
        table.align['ET State'] = 'l'
        table.align['Count'] = 'r'

        for (jr_status, et_state), count in sorted_combos:
            table.add_row([jr_status, et_state, count])

        Colors.print_table(table)
    else:
        print(f"{'Jr Status':<25} {'ET State':<15} {'Count':>8}")
        print("-" * 50)
        for (jr_status, et_state), count in sorted_combos:
            print(f"{jr_status:<25} {et_state:<15} {count:>8}")


def print_analyzer_priority_breakdown(categories: Dict[str, Any]):
    """Print breakdown by Jira priority for actionable categories."""
    print("\n" + "=" * 80)
    print("PRIORITY BREAKDOWN (Actionable Categories)")
    print("=" * 80)

    actionable_cats = ['NO_ETRACK', 'ET_CLOSED_JIRA_ACTIVE', 'JIRA_DONE_ET_ACTIVE',
                       'ET_WAITING_CASE_CLOSED', 'READY_TO_CLOSE']

    priority_counts = {}
    for cat_id in actionable_cats:
        if cat_id in categories:
            for issue in categories[cat_id]['issues']:
                priority = issue['jr_priority'] or 'Unknown'
                if priority not in priority_counts:
                    priority_counts[priority] = {'total': 0}
                if cat_id not in priority_counts[priority]:
                    priority_counts[priority][cat_id] = 0
                priority_counts[priority][cat_id] += 1
                priority_counts[priority]['total'] += 1

    # Priority order
    priority_order = ['Blocker', 'Critical', 'P1', 'Major', 'Minor', 'Trivial', 'Unknown']
    sorted_priorities = sorted(priority_counts.items(),
                               key=lambda x: priority_order.index(x[0]) if x[0] in priority_order else 99)

    if PrettyTable:
        table = PrettyTable()
        table.field_names = ['Priority', 'Total', 'No Etrack', 'ET Closed/Jira Active',
                             'Jira Done/ET Active', 'Ready to Close']
        table.align = 'r'
        table.align['Priority'] = 'l'

        for priority, counts in sorted_priorities:
            table.add_row([
                priority,
                counts['total'],
                counts.get('NO_ETRACK', 0),
                counts.get('ET_CLOSED_JIRA_ACTIVE', 0),
                counts.get('JIRA_DONE_ET_ACTIVE', 0),
                counts.get('READY_TO_CLOSE', 0)
            ])

        Colors.print_table(table)
    else:
        print(f"{'Priority':<12} {'Total':>6} {'No ET':>8} {'ET Closed':>10} {'Jr Done':>8} {'Ready':>6}")
        print("-" * 60)
        for priority, counts in sorted_priorities:
            print(f"{priority:<12} {counts['total']:>6} {counts.get('NO_ETRACK', 0):>8} "
                  f"{counts.get('ET_CLOSED_JIRA_ACTIVE', 0):>10} {counts.get('JIRA_DONE_ET_ACTIVE', 0):>8} "
                  f"{counts.get('READY_TO_CLOSE', 0):>6}")


def print_analyzer_assignee_breakdown(categories: Dict[str, Any]):
    """Print breakdown by assignee for actionable categories."""
    print("\n" + "=" * 80)
    print("ASSIGNEE BREAKDOWN (Actionable Categories)")
    print("=" * 80)

    actionable_cats = ['NO_ETRACK', 'ET_CLOSED_JIRA_ACTIVE', 'JIRA_DONE_ET_ACTIVE',
                       'ET_WAITING_CASE_CLOSED', 'READY_TO_CLOSE']

    assignee_counts = {}
    for cat_id in actionable_cats:
        if cat_id in categories:
            for issue in categories[cat_id]['issues']:
                assignee = issue['jr_assignee'] or 'Unassigned'
                if assignee not in assignee_counts:
                    assignee_counts[assignee] = {'total': 0, 'issues': []}
                assignee_counts[assignee]['total'] += 1
                assignee_counts[assignee]['issues'].append(issue['key'])

    # Sort by count descending
    sorted_assignees_all = sorted(assignee_counts.items(), key=lambda x: -x[1]['total'])
    sorted_assignees = sorted_assignees_all if Colors.notruncate else sorted_assignees_all[:20]

    if PrettyTable:
        table = PrettyTable()
        col_name = 'FIs' if Colors.notruncate else 'FIs (first 5)'
        table.field_names = ['Assignee', 'Count', col_name]
        table.align['Assignee'] = 'l'
        table.align['Count'] = 'r'
        table.align[col_name] = 'l'

        for assignee, data in sorted_assignees:
            if Colors.notruncate:
                fis = ', '.join(data['issues'])
            else:
                fis = ', '.join(data['issues'][:5])
                if len(data['issues']) > 5:
                    fis += f" (+{len(data['issues'])-5} more)"
            table.add_row([assignee[:25], data['total'], fis])

        Colors.print_table(table)
    else:
        print(f"{'Assignee':<25} {'Count':>6}")
        print("-" * 35)
        for assignee, data in sorted_assignees:
            print(f"{assignee[:25]:<25} {data['total']:>6}")


# ============================================================================
# Leadership Report Formats
# ============================================================================

def print_executive_report(categories: Dict[str, Any], total_count: int):
    """
    Executive Summary Report - Clean, high-level metrics for leadership.
    """
    total = total_count

    # Calculate key metrics
    actionable = sum(len(categories[c]['issues']) for c in
                     ['NO_ETRACK', 'ET_CLOSED_JIRA_ACTIVE', 'JIRA_DONE_ET_ACTIVE', 'ET_WAITING_CASE_CLOSED'])
    ready_to_close = len(categories.get('READY_TO_CLOSE', {}).get('issues', []))
    both_closed = len(categories.get('BOTH_CLOSED', {}).get('issues', []))
    in_progress = len(categories.get('BOTH_ACTIVE', {}).get('issues', []))
    customer_waiting = len(categories.get('CUSTOMER_WAITING', {}).get('issues', []))
    no_etrack = len(categories.get('NO_ETRACK', {}).get('issues', []))

    # Priority breakdown for actionable items
    priority_counts = {'Blocker': 0, 'Critical': 0, 'P1': 0, 'Major': 0, 'Minor': 0}
    for cat_id in ['NO_ETRACK', 'ET_CLOSED_JIRA_ACTIVE', 'JIRA_DONE_ET_ACTIVE', 'ET_WAITING_CASE_CLOSED']:
        for issue in categories.get(cat_id, {}).get('issues', []):
            p = issue['jr_priority']
            if p in priority_counts:
                priority_counts[p] += 1

    high_priority_actionable = priority_counts['Blocker'] + priority_counts['Critical'] + priority_counts['P1']

    # Health score
    health = 100 - (actionable / total * 100) if total > 0 else 100
    health_bar = "#" * int(health / 5) + "-" * (20 - int(health / 5))
    health_label = "GOOD" if health >= 80 else ("FAIR" if health >= 60 else "NEEDS ATTENTION")

    pct_actionable = (actionable / total * 100) if total > 0 else 0
    pct_ready = (ready_to_close / total * 100) if total > 0 else 0
    pct_closed = (both_closed / total * 100) if total > 0 else 0

    w = 72  # width

    print()
    print(Colors.header("=" * w))
    print(Colors.header("EXECUTIVE SUMMARY REPORT".center(w)))
    print(Colors.header("=" * w))
    print(f"  Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Total Issues Analyzed: {total}")
    print(Colors.header("=" * w))

    print()
    print(Colors.c("-" * w, Colors.DIM))
    print(Colors.header("KEY METRICS".center(w)))
    print(Colors.c("-" * w, Colors.DIM))
    print()
    print(f"  {'Action Required:':<25} {Colors.error(f'{actionable:>4}')} issues  ({pct_actionable:>5.1f}%)")
    print(f"  {'Ready to Close:':<25} {Colors.success(f'{ready_to_close:>4}')} issues  ({pct_ready:>5.1f}%)")
    print(f"  {'Fully Resolved:':<25} {Colors.success(f'{both_closed:>4}')} issues  ({pct_closed:>5.1f}%)")
    print(f"  {'In Progress:':<25} {Colors.info(f'{in_progress:>4}')} issues")
    print(f"  {'Customer Pending:':<25} {Colors.warning(f'{customer_waiting:>4}')} issues")
    print()

    print(Colors.c("-" * w, Colors.DIM))
    print(Colors.header("PRIORITY DISTRIBUTION (Actionable Items)".center(w)))
    print(Colors.c("-" * w, Colors.DIM))
    print()
    print(f"  High Priority (Blocker/Critical/P1): {Colors.error(str(high_priority_actionable))} actionable")
    print()
    blocker_cnt = priority_counts['Blocker']
    critical_cnt = priority_counts['Critical']
    p1_cnt = priority_counts['P1']
    major_cnt = priority_counts['Major']
    minor_cnt = priority_counts['Minor']
    print(f"    Blocker:  {Colors.c(f'{blocker_cnt:>3}', Colors.RED, Colors.BOLD)}      Critical: {Colors.c(f'{critical_cnt:>3}', Colors.RED)}      P1: {Colors.warning(f'{p1_cnt:>3}')}")
    print(f"    Major:    {Colors.warning(f'{major_cnt:>3}')}      Minor:    {Colors.c(f'{minor_cnt:>3}', Colors.DIM)}")
    print()

    if no_etrack > 0:
        print(Colors.c("-" * w, Colors.DIM))
        print(Colors.error(f"  [!] ATTENTION: {no_etrack} issues have NO ETRACK LINKED"))
        print(Colors.warning("      These require immediate triage and etrack assignment."))
        print()

    print(Colors.c("-" * w, Colors.DIM))
    print(Colors.header("HEALTH SCORE".center(w)))
    print(Colors.c("-" * w, Colors.DIM))
    print()
    # Color the health bar based on score
    if health >= 80:
        bar_color = Colors.success(f"[{health_bar}]")
        label_color = Colors.success(health_label)
    elif health >= 60:
        bar_color = Colors.warning(f"[{health_bar}]")
        label_color = Colors.warning(health_label)
    else:
        bar_color = Colors.error(f"[{health_bar}]")
        label_color = Colors.error(health_label)
    print(f"  {bar_color}  {health:>5.1f}%  ({label_color})")
    print()
    print("  Score = % of issues NOT requiring action")
    print()
    print(Colors.header("=" * w))


def print_action_report(categories: Dict[str, Any]):
    """
    Action Items Report - Grouped by urgency with clear next steps.
    """
    w = 72
    print()
    print(Colors.header("=" * w))
    print(Colors.header("ACTION ITEMS REPORT".center(w)))
    print(Colors.header("=" * w))
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(Colors.header("=" * w))

    # Priority order for actions
    action_order = [
        ('CRITICAL', 'NO_ETRACK', 'IMMEDIATE: Link Etrack Incidents',
         'These FIs have no associated Etrack incident - needs immediate triage'),
        ('HIGH', 'ET_CLOSED_JIRA_ACTIVE', 'HIGH: Update Jira Status',
         'Etrack is CLOSED but Jira still shows In Progress - update Jira'),
        ('HIGH', 'JIRA_DONE_ET_ACTIVE', 'HIGH: Follow Up on Etrack',
         'Jira shows Solution Provided but Etrack is still OPEN/WORKING - needs eng follow-up'),
        ('MEDIUM', 'ET_WAITING_CASE_CLOSED', 'MEDIUM: Close Etrack (Waiting)',
         'Case is Closed but Etrack is in WAITING state - may need to close etrack'),
        ('MEDIUM', 'CASE_CLOSED_ET_NOT_CLOSED', 'MEDIUM: Close Etrack (Any State)',
         'Case Closed + Jira Done but Etrack not closed - may need to close etrack'),
        ('LOW', 'READY_TO_CLOSE', 'LOW: Final Closure',
         'Both systems show completion - ready for final administrative closure'),
    ]

    total_actions = 0

    for urgency, cat_id, title, description in action_order:
        issues = categories.get(cat_id, {}).get('issues', [])
        if not issues:
            continue

        total_actions += len(issues)

        # Color based on urgency level
        if urgency == 'CRITICAL':
            urgency_color = Colors.error
        elif urgency == 'HIGH':
            urgency_color = Colors.warning
        elif urgency == 'MEDIUM':
            urgency_color = Colors.info
        else:
            urgency_color = Colors.success

        print()
        print(Colors.c("-" * w, Colors.DIM))
        print(urgency_color(f"[{urgency}] {title}"))
        print(Colors.c("-" * w, Colors.DIM))
        print(f"  {description}")

        # Show both FI count and unique Etrack count
        unique_etracks = get_unique_etracks(issues)
        if unique_etracks and len(unique_etracks) != len(issues):
            print(f"  Count: {urgency_color(str(len(issues)))} FIs / {len(unique_etracks)} unique Etracks")
        else:
            print(f"  Count: {urgency_color(str(len(issues)))}")

        # Group by priority
        by_priority = {}
        for issue in issues:
            p = issue['jr_priority'] or 'Unknown'
            if p not in by_priority:
                by_priority[p] = []
            by_priority[p].append(issue)

        priority_order = ['Blocker', 'Critical', 'P1', 'Major', 'Minor', 'Trivial', 'Unknown']

        # Determine if this category needs Etrack info (action is on Etrack side)
        show_etrack = cat_id in ['ET_WAITING_CASE_CLOSED', 'CASE_CLOSED_ET_NOT_CLOSED', 'JIRA_DONE_ET_ACTIVE', 'READY_TO_CLOSE']

        for priority in priority_order:
            if priority not in by_priority:
                continue
            p_issues = by_priority[priority]

            if show_etrack:
                # Show FI:Etrack pairs
                if Colors.notruncate:
                    pairs = [f"{i['key']}:{i['et_incident']}" if i.get('et_incident') else i['key']
                             for i in p_issues]
                    fi_list = ', '.join(pairs)
                else:
                    pairs = [f"{i['key']}:{i['et_incident']}" if i.get('et_incident') else i['key']
                             for i in p_issues[:8]]
                    fi_list = ', '.join(pairs)
                    if len(p_issues) > 8:
                        fi_list += f" (+{len(p_issues)-8} more)"
            else:
                if Colors.notruncate:
                    fi_list = ', '.join([i['key'] for i in p_issues])
                else:
                    fi_list = ', '.join([i['key'] for i in p_issues[:10]])
                    if len(p_issues) > 10:
                        fi_list += f" (+{len(p_issues)-10} more)"

            # Color priority label
            priority_colored = Colors.priority(f"[{priority}]", priority)
            print(f"\n  {priority_colored} {len(p_issues)} issues:")
            print(f"    {fi_list}")

        # Print separate lists for easy copy-paste
        all_fis = [i['key'] for i in issues]
        fi_str = ','.join(all_fis)
        if Colors.notruncate:
            print(f"\n  {Colors.info('FI List')} ({len(all_fis)}): {fi_str}")
        else:
            print(f"\n  {Colors.info('FI List')} ({len(all_fis)}): {fi_str[:200]}{'...' if len(fi_str) > 200 else ''}")

        if show_etrack:
            unique_et_sorted = sorted(get_unique_etracks(issues))
            if unique_et_sorted:
                et_str = ','.join(unique_et_sorted)
                if Colors.notruncate:
                    print(f"  {Colors.info('Etrack List')} ({len(unique_et_sorted)} unique): {et_str}")
                else:
                    print(f"  {Colors.info('Etrack List')} ({len(unique_et_sorted)} unique): {et_str[:200]}{'...' if len(et_str) > 200 else ''}")

    print()
    print(Colors.header("=" * w))
    print(f"  TOTAL ACTION ITEMS: {Colors.c(str(total_actions), Colors.BOLD, Colors.YELLOW)}")
    print(Colors.header("=" * w))


def print_team_report(categories: Dict[str, Any]):
    """
    Team Dashboard Report - Per-assignee breakdown for managers.
    """
    w = 80
    print()
    print(Colors.header("=" * w))
    print(Colors.header("TEAM DASHBOARD".center(w)))
    print(Colors.header("=" * w))
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(Colors.header("=" * w))

    # Collect all issues by assignee with category breakdown
    assignee_data = {}
    cat_names = {
        'NO_ETRACK': 'NoET',
        'ET_CLOSED_JIRA_ACTIVE': 'ETClosed',
        'JIRA_DONE_ET_ACTIVE': 'JrDone',
        'ET_WAITING_CASE_CLOSED': 'ETWait',
        'CASE_CLOSED_ET_NOT_CLOSED': 'CaseClsd',
        'READY_TO_CLOSE': 'Ready',
        'BOTH_CLOSED': 'Done',
        'BOTH_ACTIVE': 'Active',
        'CUSTOMER_WAITING': 'CustWait',
        'OTHER': 'Other'
    }

    for cat_id, cat_data in categories.items():
        if cat_id == '_metadata':
            continue
        for issue in cat_data.get('issues', []):
            assignee = issue['jr_assignee'] or 'Unassigned'
            if assignee not in assignee_data:
                assignee_data[assignee] = {
                    'total': 0,
                    'actionable': 0,
                    'high_priority': 0,
                    'categories': {},
                    'issues': []
                }

            assignee_data[assignee]['total'] += 1
            assignee_data[assignee]['issues'].append(issue)

            if cat_id not in assignee_data[assignee]['categories']:
                assignee_data[assignee]['categories'][cat_id] = 0
            assignee_data[assignee]['categories'][cat_id] += 1

            if cat_id in ['NO_ETRACK', 'ET_CLOSED_JIRA_ACTIVE', 'JIRA_DONE_ET_ACTIVE', 'ET_WAITING_CASE_CLOSED']:
                assignee_data[assignee]['actionable'] += 1
                if issue['jr_priority'] in ['Blocker', 'Critical', 'P1']:
                    assignee_data[assignee]['high_priority'] += 1

    # Sort by actionable count descending
    sorted_assignees = sorted(assignee_data.items(), key=lambda x: -x[1]['actionable'])

    # Print header
    header = f"{'Assignee':<25} {'Total':>6} {'Action':>7} {'Hi-Pri':>7} {'Status Breakdown':<30}"
    print(f"\n{Colors.header(header)}")
    print(Colors.c("-" * 80, Colors.DIM))

    for assignee, data in sorted_assignees:
        # Build status breakdown string
        status_parts = []
        for cat_id in ['NO_ETRACK', 'ET_CLOSED_JIRA_ACTIVE', 'JIRA_DONE_ET_ACTIVE', 'ET_WAITING_CASE_CLOSED', 'CASE_CLOSED_ET_NOT_CLOSED', 'READY_TO_CLOSE']:
            count = data['categories'].get(cat_id, 0)
            if count > 0:
                short_name = cat_names[cat_id]
                status_parts.append(Colors.category(cat_id, f"{short_name}:{count}"))

        status_str = ', '.join(status_parts) if status_parts else '-'

        # Add warning indicator with color
        if data['high_priority'] > 0:
            warning = Colors.error("[!]")
            hi_pri = Colors.error(f"{data['high_priority']:>7}")
        else:
            warning = "   "
            hi_pri = f"{data['high_priority']:>7}"

        # Color actionable count
        if data['actionable'] > 5:
            actionable = Colors.error(f"{data['actionable']:>7}")
        elif data['actionable'] > 0:
            actionable = Colors.warning(f"{data['actionable']:>7}")
        else:
            actionable = Colors.success(f"{data['actionable']:>7}")

        print(f"{warning}{assignee[:22]:<22} {data['total']:>6} {actionable} "
              f"{hi_pri} {status_str}")

    # Summary
    total_assignees = len(assignee_data)
    with_actions = sum(1 for a, d in assignee_data.items() if d['actionable'] > 0)

    print(Colors.c("-" * 80, Colors.DIM))
    print(f"Total Team Members: {Colors.info(str(total_assignees))}  |  With Action Items: {Colors.warning(str(with_actions))}")

    # Legend
    print()
    print(Colors.header("Legend:"))
    print(f"  {Colors.error('[!]')}      = Has high-priority (Blocker/Critical/P1) actionable items")
    print(f"  {Colors.error('NoET')}     = No Etrack linked (needs triage)")
    print(f"  {Colors.warning('ETClosed')} = Etrack closed but Jira still active (update Jira)")
    print(f"  {Colors.warning('JrDone')}   = Jira done but Etrack still active (follow up on Etrack)")
    print(f"  {Colors.warning('ETWait')}   = Case closed but Etrack in WAITING state")
    print(f"  {Colors.warning('CaseClsd')} = Case closed + Jira done but Etrack not closed")
    print(f"  {Colors.success('Ready')}    = Ready to close (both systems show completion)")
    print("=" * 80)


def print_risk_report(categories: Dict[str, Any]):
    """
    Risk Report - Focus on high-priority and critical items.
    """
    w = 72
    print()
    print(Colors.header("=" * w))
    print(Colors.header("RISK REPORT".center(w)))
    print(Colors.header("=" * w))
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(Colors.header("=" * w))

    # Collect high priority issues across actionable categories
    high_priority_issues = []
    actionable_cats = ['NO_ETRACK', 'ET_CLOSED_JIRA_ACTIVE', 'JIRA_DONE_ET_ACTIVE', 'ET_WAITING_CASE_CLOSED']

    for cat_id in actionable_cats:
        for issue in categories.get(cat_id, {}).get('issues', []):
            if issue['jr_priority'] in ['Blocker', 'Critical', 'P1']:
                issue['category'] = cat_id
                high_priority_issues.append(issue)

    # Sort by priority
    priority_order = {'Blocker': 0, 'Critical': 1, 'P1': 2}
    high_priority_issues.sort(key=lambda x: priority_order.get(x['jr_priority'], 99))

    if not high_priority_issues:
        print(f"\n  {Colors.success('[OK]')} No high-priority risk items found!")
        print("       All Blocker/Critical/P1 issues are in good state.")
        return

    print(f"\n  {Colors.error('[!] RISK ITEMS:')} {Colors.c(str(len(high_priority_issues)), Colors.BOLD, Colors.RED)} high-priority issues need attention")

    cat_labels = {
        'NO_ETRACK': 'Missing Etrack',
        'ET_CLOSED_JIRA_ACTIVE': 'Jira not updated',
        'JIRA_DONE_ET_ACTIVE': 'Etrack not closed',
        'ET_WAITING_CASE_CLOSED': 'Etrack waiting'
    }

    if PrettyTable:
        table = PrettyTable()
        table.field_names = ['#', 'Priority', 'FI', 'Assignee', 'Issue', 'Etrack']
        table.align = 'l'

        display_issues = high_priority_issues if Colors.notruncate else high_priority_issues[:30]
        for idx, issue in enumerate(display_issues, 1):
            table.add_row([
                idx,
                issue['jr_priority'],
                issue['key'],
                (issue['jr_assignee'] or '-')[:18],
                cat_labels.get(issue['category'], '-'),
                issue['et_incident'] or '-'
            ])

        Colors.print_table(table)

        if not Colors.notruncate and len(high_priority_issues) > 30:
            print(f"\n  ... and {len(high_priority_issues) - 30} more high-priority items")
    else:
        print(f"\n{'#':>3} {'Priority':<10} {'FI':<10} {'Assignee':<20} {'Issue':<20}")
        print("-" * 65)
        display_issues = high_priority_issues if Colors.notruncate else high_priority_issues[:30]
        for idx, issue in enumerate(display_issues, 1):
            print(f"{idx:>3} {issue['jr_priority']:<10} {issue['key']:<10} "
                  f"{(issue['jr_assignee'] or '-')[:18]:<20} {cat_labels.get(issue['category'], '-'):<20}")

    # FI list for easy action
    fi_list = ','.join([i['key'] for i in high_priority_issues])
    if Colors.notruncate:
        print(f"\n  Risk FI List (copy for triage):\n  {fi_list}")
    else:
        print(f"\n  Risk FI List (copy for triage):\n  {fi_list[:200]}{'...' if len(fi_list) > 200 else ''}")


def parse_prettytable_output(content: str) -> List[Dict]:
    """
    Parse PrettyTable output from saved j.et.rpt.py stdout.

    Handles tables like:
    +-----+----------+------------------------+-------------+
    | #   | Jr Key   | Jr Assignee            | Jr Priority |
    +-----+----------+------------------------+-------------+
    | 1   | FI-59535 | PXXXXX WXXXXXXX        | Major       |
    +-----+----------+------------------------+-------------+
    """
    rows = []
    headers = []
    in_table = False

    for line in content.splitlines():
        # Strip trailing whitespace but preserve leading for detection
        line = line.rstrip()

        # Skip empty lines
        if not line.strip():
            continue

        # Skip separator lines (lines with only +, -, |, and spaces)
        if set(line.replace(' ', '')) <= {'+', '-', '|'}:
            continue

        # Check if this is a table row (contains | but not just separators)
        if '|' in line:
            # Extract content between first and last |
            pipe_parts = line.split('|')

            # Filter out empty parts from leading/trailing pipes
            cells = []
            for part in pipe_parts:
                cell = part.strip()
                # Skip empty parts from leading/trailing |
                if part == pipe_parts[0] and not cell:
                    continue
                if part == pipe_parts[-1] and not cell:
                    continue
                cells.append(cell)

            if not cells:
                continue

            if not in_table:
                # First row with cells is header
                headers = cells
                in_table = True
            else:
                # Data row - check it's not a repeat of header
                first_cell = cells[0] if cells else ''
                if first_cell == '#' or first_cell == headers[0]:
                    # This is a repeated header, skip
                    continue

                # Build row dict
                row = {}
                for i, header in enumerate(headers):
                    if header == '#':
                        continue  # Skip row index column
                    if i < len(cells):
                        row[header] = cells[i]
                    else:
                        row[header] = ''

                if row:
                    rows.append(row)
        else:
            # Not a table line - if we were in a table and have rows, we're done
            if in_table and rows:
                break

    return rows


def parse_analyzer_input(filepath: str = None, verbose: bool = False) -> List[Dict]:
    """
    Parse saved j.et.rpt.py output from file or stdin.

    Args:
        filepath: Path to saved output file, or None to read from stdin
        verbose: Print debug info about parsing

    Returns:
        List of row dictionaries
    """
    if filepath:
        if not os.path.exists(filepath):
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        with open(filepath, 'r') as f:
            content = f.read()
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("Error: No input provided. Use --analyzer-input FILE or pipe data via stdin.", file=sys.stderr)
            sys.exit(1)
        content = sys.stdin.read()

    if verbose:
        print(f"Input content length: {len(content)} chars, {len(content.splitlines())} lines", file=sys.stderr)

    rows = parse_prettytable_output(content)

    if not rows:
        print("Error: Could not parse table data from input.", file=sys.stderr)
        print("Expected PrettyTable format with headers like: Jr Key, Jr Status, Jr Case Status, ET State", file=sys.stderr)
        print("\nDebug info:", file=sys.stderr)
        # Show first few lines of input
        lines = content.splitlines()[:10]
        for i, line in enumerate(lines):
            has_pipe = '|' in line
            print(f"  Line {i+1}: {'[TABLE]' if has_pipe else '[TEXT]'} {line[:80]}{'...' if len(line) > 80 else ''}", file=sys.stderr)
        if len(content.splitlines()) > 10:
            print(f"  ... ({len(content.splitlines()) - 10} more lines)", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"Parsed {len(rows)} rows", file=sys.stderr)
        if rows:
            print(f"Columns: {', '.join(rows[0].keys())}", file=sys.stderr)

    # Validate required columns exist
    sample_row = rows[0]
    found_cols = [col.lower().replace(' ', '') for col in sample_row.keys()]

    has_status = any('status' in col and 'case' not in col for col in found_cols)
    has_case_status = any('casestatus' in col or 'case' in col for col in found_cols)
    has_et_state = any('etstate' in col or ('et' in col and 'state' in col) for col in found_cols)

    if not (has_status or has_case_status or has_et_state):
        print("Warning: Could not find expected status columns (Jr Status, Jr Case Status, ET State).", file=sys.stderr)
        print(f"Found columns: {', '.join(sample_row.keys())}", file=sys.stderr)

    if not (has_status or has_case_status or has_et_state):
        print("Warning: Could not find expected status columns (Jr Status, Jr Case Status, ET State).", file=sys.stderr)
        print(f"Found columns: {', '.join(sample_row.keys())}", file=sys.stderr)

    return rows


def run_analyzer(processed_data: List[Dict], format: str = 'both'):
    """Run the full analyzer and print reports."""
    if not processed_data:
        print("No data to analyze.")
        return

    # Run analysis
    categories = analyze_status_combinations(processed_data)
    total_count = len(processed_data)

    # Technical formats
    if format in ['summary', 'both', 'all']:
        print_analyzer_summary(categories, total_count)
        print_analyzer_state_matrix(categories, processed_data)
        print_analyzer_priority_breakdown(categories)
        print_analyzer_assignee_breakdown(categories)

    if format in ['detailed', 'both', 'all']:
        print_analyzer_detailed(categories)

    # Leadership formats
    if format in ['executive', 'all']:
        print_executive_report(categories, total_count)

    if format in ['action', 'all']:
        print_action_report(categories)

    if format in ['team', 'all']:
        print_team_report(categories)

    if format in ['risk', 'all']:
        print_risk_report(categories)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        description='Bulk Jira + Etrack Issue Report Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read IDs from file
  %(prog)s -f issues.txt

  # Read IDs from stdin
  cat issues.txt | %(prog)s

  # Use JQL where clause
  %(prog)s -where "project = FI AND status = Open"
  %(prog)s -where "assignee = currentUser() AND status != Closed"

  # Custom Jira fields
  %(prog)s -f issues.txt --fields key,summary,status,assignee,created

  # Export to CSV
  %(prog)s -f issues.txt --csv report.csv

  # Export to JSON (includes raw data)
  %(prog)s -f issues.txt --json report.json --include-raw

  # Combine options
  %(prog)s -where "project = FI" --fields key,summary,severity --csv report.csv --limit 100

  # List available Jira fields
  %(prog)s --list-fields

  # ----- Etrack Integration -----

  # Jira + Etrack combined view (fetches etrack data via esql)
  %(prog)s -where "project = FI" \\
    --fields key,assignee,priority,status,casestatus,etrack \\
    --show-etrack-data etrack \\
    --etrack-fields priority,severity,assigned_to,component,state

  # Jira + Etrack with export to CSV
  %(prog)s -f issues.txt \\
    --fields key,assignee,priority,status,casestatus,etrack \\
    --show-etrack-data etrack \\
    --etrack-fields priority,severity,assigned_to,component,state \\
    --csv combined_report.csv

  # Etrack-only mode (no Jira call, parse IDs from input)
  %(prog)s --etrack-only 4200175 4208921

  # Etrack-only from file
  %(prog)s --etrack-only -f etrack_ids.txt

  # Etrack-only with custom fields
  %(prog)s --etrack-only -f ids.txt \\
    --etrack-fields priority,state,customer,abstract

  # Etrack-only with CSV export
  %(prog)s --etrack-only -f ids.txt \\
    --etrack-fields priority,severity,assigned_to,state \\
    --csv etrack_report.csv

  # ----- Analyzer -----

  # Analyze live data (fetch + analyze)
  %(prog)s -where "project = FI" \\
    --fields key,assignee,priority,status,casestatus,etrack \\
    --show-etrack-data etrack --etrack-fields priority,severity,assigned_to,component,state \\
    --analyzer

  # Analyze saved output file
  %(prog)s --analyzer-input saved_report.txt

  # Pipe saved output to analyzer
  cat saved_report.txt | %(prog)s --analyzer

  # Analyzer with summary only (skip detailed breakdown)
  %(prog)s --analyzer-input saved_report.txt --analyzer-format summary

  # Leadership reports (executive, action, team, risk)
  %(prog)s --analyzer-input saved_report.txt --analyzer-format executive
  %(prog)s --analyzer-input saved_report.txt --analyzer-format action
  %(prog)s --analyzer-input saved_report.txt --analyzer-format team
  %(prog)s --analyzer-input saved_report.txt --analyzer-format risk

  # All reports (technical + leadership)
  %(prog)s --analyzer-input saved_report.txt --analyzer-format all

Field Aliases (use instead of field IDs):
  key, summary, status, assignee, priority, reporter, labels
  casestatus (customfield_16200), etrack (customfield_33802)
  severity, epic, sprint, storypoints, duedate, etc.

Etrack Fields:
  incident, priority, severity, assigned_to, component, customer,
  state, abstract, submitter, product, group_owner, sr, type
"""
    )

    # Input sources
    input_group = parser.add_argument_group('Input Sources')
    input_group.add_argument('-f', '--file', metavar='FILE',
                             help='File containing Jira issue IDs (one per line)')
    input_group.add_argument('-where', '--where', metavar='JQL',
                             help='JQL where clause (e.g., "project = FI AND status = Open")')
    input_group.add_argument('--jql', metavar='JQL',
                             help='Full JQL query (alias for -where)')
    input_group.add_argument('ids', nargs='*', metavar='ID',
                             help='Issue IDs directly on command line')

    # Field selection
    field_group = parser.add_argument_group('Field Selection')
    field_group.add_argument('--fields', '-F', metavar='FIELDS',
                             help='Comma-separated list of fields to display '
                                  f'(default: {",".join(DEFAULT_FIELDS.keys())})')
    field_group.add_argument('--list-fields', action='store_true',
                             help='List all available Jira fields and exit')
    field_group.add_argument('--exclude', '-X', metavar='FIELDS',
                             help='Comma-separated list of fields to exclude')

    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument('--csv', metavar='FILE',
                              help='Export to CSV file')
    output_group.add_argument('--json', metavar='FILE',
                              help='Export to JSON file')
    output_group.add_argument('--markdown', '-m', action='store_true',
                              help='Output as markdown table')
    output_group.add_argument('--include-raw', action='store_true',
                              help='Include raw Jira data in JSON output')
    output_group.add_argument('--no-table', action='store_true',
                              help='Skip table output (useful with --csv/--json)')
    output_group.add_argument('--summary-len', type=int, default=100,
                              help='Max summary length (default: 100)')

    # Fetch options
    fetch_group = parser.add_argument_group('Fetch Options')
    fetch_group.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                             help=f'Number of issues per API call (default: {DEFAULT_BATCH_SIZE})')
    fetch_group.add_argument('--limit', type=int, default=DEFAULT_MAX_RESULTS,
                             help=f'Max issues to fetch for JQL (default: {DEFAULT_MAX_RESULTS})')
    fetch_group.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT,
                             help=f'API timeout in seconds (default: {DEFAULT_TIMEOUT})')

    # Etrack integration
    etrack_group = parser.add_argument_group('Etrack Integration')
    etrack_group.add_argument('--show-etrack-data', metavar='FIELD',
                              help='Fetch etrack data using values from this Jira field '
                                   '(e.g., "Etrack Incident" or "customfield_33802")')
    etrack_group.add_argument('--etrack-fields', metavar='FIELDS',
                              default=','.join(DEFAULT_ETRACK_FIELDS),
                              help=f'Comma-separated etrack fields to display '
                                   f'(default: {",".join(DEFAULT_ETRACK_FIELDS)})')
    etrack_group.add_argument('--etrack-batch-size', type=int, default=ETRACK_BATCH_SIZE,
                              help=f'Number of etrack IDs per eprint call (default: {ETRACK_BATCH_SIZE})')
    etrack_group.add_argument('--etrack-only', action='store_true',
                              help='Show only etrack data (no Jira call), parse IDs directly from input')

    # Analysis options
    analysis_group = parser.add_argument_group('Analysis Options')
    analysis_group.add_argument('--analyzer', action='store_true',
                                help='Generate analysis report based on Jr Status, Jr Case Status, and ET State combinations')
    analysis_group.add_argument('--analyzer-input', metavar='FILE',
                                help='Parse saved j.et.rpt.py output file for analysis (skip Jira/Etrack fetch)')
    analysis_group.add_argument('--analyzer-format', choices=['summary', 'detailed', 'both', 'executive', 'action', 'team', 'risk', 'all'],
                                default='both',
                                help='Analyzer output format: summary|detailed|both (technical), executive|action|team|risk (leadership), all (everything)')
    analysis_group.add_argument('--notruncate', action='store_true',
                                help='Show complete results without truncating lists (default: truncate long lists)')

    # Debug/troubleshooting
    debug_group = parser.add_argument_group('Debug/Troubleshooting')
    debug_group.add_argument('--verbose', '-v', action='store_true',
                             help='Show verbose output including API stats')
    debug_group.add_argument('--dry-run', action='store_true',
                             help='Parse input and show what would be fetched, without API calls')
    debug_group.add_argument('--show-jql', action='store_true',
                             help='Show the JQL query that will be used')
    debug_group.add_argument('--color', action='store_true',
                             help='Enable colored output for terminal display')

    return parser


def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()

    # Enable colored output if requested
    if args.color:
        Colors.enabled = True

    # Enable no-truncate mode if requested
    if args.notruncate:
        Colors.notruncate = True

    # Determine if this is "fetch + analyze" mode vs "parse saved output" mode
    # If --analyzer-input is given explicitly, always parse that file
    # If --analyzer is given with fetch sources (-where, -f, stdin IDs, etc.), fetch THEN analyze
    # If --analyzer is given with NO fetch sources AND stdin has piped table data, parse stdin

    # Check for explicit fetch-related args (these indicate we should fetch, not parse)
    has_fetch_args = args.file or args.where or args.jql or args.ids
    has_fetch_options = args.fields or args.show_etrack_data or args.etrack_only

    # Handle analyzer-input mode (parse saved output, skip Jira/Etrack fetch)
    if args.analyzer_input:
        # Explicit file input for analyzer
        processed_data = parse_analyzer_input(args.analyzer_input, verbose=args.verbose)
        if args.verbose:
            print(f"Parsed {len(processed_data)} rows from {args.analyzer_input}", file=sys.stderr)
        run_analyzer(processed_data, args.analyzer_format)
        return

    # If --analyzer with NO fetch sources AND NO fetch options, try parsing stdin as table
    if args.analyzer and not has_fetch_args and not has_fetch_options:
        if not sys.stdin.isatty():
            processed_data = parse_analyzer_input(None, verbose=args.verbose)  # Read from stdin
            if args.verbose:
                print(f"Parsed {len(processed_data)} rows from stdin", file=sys.stderr)
            run_analyzer(processed_data, args.analyzer_format)
            return
        else:
            # --analyzer without any input
            print("Error: --analyzer requires input. Use one of:", file=sys.stderr)
            print("  --analyzer-input FILE    # Parse saved j.et.rpt.py output", file=sys.stderr)
            print("  cat output.txt | j.et.rpt.py --analyzer  # Pipe saved output", file=sys.stderr)
            print("  j.et.rpt.py -where ... --analyzer  # Fetch and analyze", file=sys.stderr)
            sys.exit(1)

    # At this point, we're in fetch mode (with or without --analyzer)
    # --analyzer will be handled after fetching

    # Determine fields to fetch (needed for dry-run)
    if args.fields:
        fields = [f.strip() for f in args.fields.split(',')]
    else:
        fields = list(DEFAULT_FIELDS.keys())

    # Handle exclusions
    if args.exclude:
        exclude_set = {f.strip().lower() for f in args.exclude.split(',')}
        fields = [f for f in fields if f.lower() not in exclude_set]

    # Determine input source
    issue_ids = []
    jql_query = args.where or args.jql

    # Parse input sources first (for dry-run)
    if jql_query:
        pass  # Will be handled later
    elif args.file:
        issue_ids = read_ids_from_file(args.file)
        if not issue_ids:
            print(f"No valid issue IDs found in {args.file}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        issue_ids = read_ids_from_stdin()
        if not issue_ids:
            print("No valid issue IDs found in stdin", file=sys.stderr)
            sys.exit(1)
    elif args.ids:
        issue_ids = parse_issue_ids(' '.join(args.ids))
        if not issue_ids:
            print("No valid issue IDs provided", file=sys.stderr)
            sys.exit(1)
    elif not args.list_fields:
        parser.print_help()
        return

    # Handle dry-run (no API calls needed)
    if args.dry_run:
        if jql_query:
            print(f"Would execute JQL: {jql_query}")
        else:
            print(f"Would fetch {len(issue_ids)} issues:")
            for i, id in enumerate(issue_ids[:20]):
                print(f"  {id}")
            if len(issue_ids) > 20:
                print(f"  ... and {len(issue_ids) - 20} more")
        print(f"Fields: {', '.join(fields)}")
        if jql_query:
            print(f"Max results: {args.limit}")
        return

    # Handle etrack-only mode (no Jira call)
    if args.etrack_only:
        if not issue_ids:
            print("Error: --etrack-only requires input IDs (via -f, stdin, or command line)", file=sys.stderr)
            sys.exit(1)

        # Parse etrack fields
        etrack_fields = [f.strip().lower() for f in args.etrack_fields.split(',')]

        # Filter to numeric IDs only (etrack IDs are numeric)
        etrack_ids = [eid.strip() for eid in issue_ids if eid.strip().isdigit()]
        if not etrack_ids:
            print("Error: No numeric etrack IDs found in input", file=sys.stderr)
            sys.exit(1)

        # Fetch etrack data
        etrack_client = EtrackClient(batch_size=args.etrack_batch_size)
        etrack_data = etrack_client.fetch_etrack_data(etrack_ids, etrack_fields=etrack_fields, verbose=args.verbose)

        if not etrack_data:
            print("No etrack data found.", file=sys.stderr)
            sys.exit(1)

        # Build processed data for output
        processed_data = []
        for idx, eid in enumerate(etrack_ids, start=1):
            row = {'#': idx, 'Incident': eid}
            if eid in etrack_data:
                et_row = etrack_data[eid]
                for ef in etrack_fields:
                    col_name = ef.title().replace('_', ' ')
                    row[col_name] = et_row.get(ef, '')
            else:
                for ef in etrack_fields:
                    col_name = ef.title().replace('_', ' ')
                    row[col_name] = ''
            processed_data.append(row)

        # Output
        if args.csv:
            export_csv(processed_data, args.csv)

        if args.json:
            export_json(processed_data, args.json, None)

        if not args.no_table:
            if args.markdown:
                print_markdown(processed_data)
            else:
                print_table(processed_data)

        # Stats
        if args.verbose:
            et_stats = etrack_client.get_stats()
            print("\n--- Etrack Stats ---", file=sys.stderr)
            print(f"Etrack IDs requested: {len(etrack_ids)}", file=sys.stderr)
            print(f"Etrack records found: {len(etrack_data)}", file=sys.stderr)
            print(f"Etrack calls: {et_stats['etrack_calls']}", file=sys.stderr)
            print(f"Etrack time: {et_stats['etrack_time']}s", file=sys.stderr)

        return

    # Validate credentials (only for actual API calls)
    if not JIRA_URL or JIRA_URL == 'https://':
        print("Error: JIRA_SERVER_NAME environment variable not set", file=sys.stderr)
        print("Set it with: export JIRA_SERVER_NAME=your-server.atlassian.net", file=sys.stderr)
        sys.exit(1)

    if not JIRA_API_TOKEN:
        print("Error: JIRA_ACC_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Create client
    client = JiraReportClient(
        batch_size=args.batch_size,
        timeout=args.timeout
    )

    # Handle --list-fields
    if args.list_fields:
        list_available_fields(client)
        return

    raw_issues = []

    # Fetch issues
    if jql_query:
        if args.show_jql:
            print(f"JQL Query: {jql_query}")

        raw_issues = client.fetch_issues_by_jql(jql_query, fields, args.limit)

    elif issue_ids:
        if args.show_jql or args.verbose:
            jql = f"key in ({', '.join(issue_ids[:10])}{'...' if len(issue_ids) > 10 else ''})"
            print(f"JQL Query: {jql}")

        raw_issues = client.fetch_issues_by_keys(issue_ids, fields)

    if not raw_issues:
        print("No issues found.", file=sys.stderr)
        sys.exit(1)

    # Process issues
    processed_data = process_issues(raw_issues, fields, client, args.summary_len)

    # Etrack integration
    etrack_data = {}
    if args.show_etrack_data:
        # Resolve field name (e.g., "Etrack Incident" -> "customfield_33802")
        _, etrack_display_name = client.resolve_field_name(args.show_etrack_data)

        # Extract etrack IDs from processed data
        etrack_ids = []
        for row in processed_data:
            etrack_val = row.get(etrack_display_name, '')
            if etrack_val:
                # Handle comma-separated IDs
                for eid in str(etrack_val).split(','):
                    eid = eid.strip()
                    if eid and eid.isdigit():
                        etrack_ids.append(eid)

        if etrack_ids:
            # Parse requested etrack fields
            etrack_fields = [f.strip().lower() for f in args.etrack_fields.split(',')]

            # Fetch etrack data
            etrack_client = EtrackClient(batch_size=args.etrack_batch_size)
            etrack_data = etrack_client.fetch_etrack_data(etrack_ids, etrack_fields=etrack_fields, verbose=args.verbose)

            # Merge etrack data into processed rows with prefixed columns
            for row in processed_data:
                etrack_val = row.get(etrack_display_name, '')
                # Get first etrack ID if multiple
                first_eid = str(etrack_val).split(',')[0].strip() if etrack_val else ''

                if first_eid and first_eid in etrack_data:
                    et_row = etrack_data[first_eid]
                    for ef in etrack_fields:
                        col_name = f"ET {ef.title().replace('_', ' ')}"
                        row[col_name] = et_row.get(ef, '')
                else:
                    # Add empty columns
                    for ef in etrack_fields:
                        col_name = f"ET {ef.title().replace('_', ' ')}"
                        row[col_name] = ''

            # Prefix Jira columns with "Jr " (skip # and etrack columns)
            updated_data = []
            for row in processed_data:
                new_row = {}
                for key, value in row.items():
                    if key == '#' or key.startswith('ET '):
                        new_row[key] = value
                    else:
                        new_row[f"Jr {key}"] = value
                updated_data.append(new_row)
            processed_data = updated_data

            # Add etrack stats to verbose output
            if args.verbose:
                et_stats = etrack_client.get_stats()
                print(f"Etrack calls: {et_stats['etrack_calls']}", file=sys.stderr)
                print(f"Etrack time: {et_stats['etrack_time']}s", file=sys.stderr)
        elif args.verbose:
            print("No etrack IDs found in data", file=sys.stderr)

    # Output
    if args.csv:
        export_csv(processed_data, args.csv)

    if args.json:
        export_json(processed_data, args.json,
                   raw_issues if args.include_raw else None)

    if not args.no_table:
        if args.markdown:
            print_markdown(processed_data)
        else:
            print_table(processed_data)

    # Run analyzer if requested
    if args.analyzer:
        run_analyzer(processed_data, args.analyzer_format)

    # Stats
    if args.verbose:
        stats = client.get_stats()
        print(f"\n--- Stats ---", file=sys.stderr)
        print(f"Issues fetched: {len(raw_issues)}", file=sys.stderr)
        print(f"API calls: {stats['api_calls']}", file=sys.stderr)
        print(f"Total time: {stats['total_time']}s", file=sys.stderr)
        print(f"Avg time/call: {stats['avg_time']}s", file=sys.stderr)


if __name__ == '__main__':
    main()
