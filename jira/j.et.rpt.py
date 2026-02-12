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

    print(table)


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
            print(table)
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


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        description='Bulk Jira Issue Report Generator',
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

  # Custom fields
  %(prog)s -f issues.txt --fields key,summary,status,assignee,created

  # Export to CSV
  %(prog)s -f issues.txt --csv report.csv

  # Export to JSON (includes raw data)
  %(prog)s -f issues.txt --json report.json --include-raw

  # Combine options
  %(prog)s -where "project = FI" --fields key,summary,severity --csv report.csv --limit 100

  # List available fields
  %(prog)s --list-fields
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

    # Debug/troubleshooting
    debug_group = parser.add_argument_group('Debug/Troubleshooting')
    debug_group.add_argument('--verbose', '-v', action='store_true',
                             help='Show verbose output including API stats')
    debug_group.add_argument('--dry-run', action='store_true',
                             help='Parse input and show what would be fetched, without API calls')
    debug_group.add_argument('--show-jql', action='store_true',
                             help='Show the JQL query that will be used')

    return parser


def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()

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
