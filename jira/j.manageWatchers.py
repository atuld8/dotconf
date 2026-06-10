#!/usr/bin/env python3
"""
Jira Watcher Manager - Manage watchers on Jira issues.

Manage multiple watcher fields including built-in Watchers, Issue Watchers,
Security Issue Watchers, and Watcher Groups. Supports bulk operations via
JQL queries, file input, and command-line arguments.

================================================================================
AVAILABLE WATCHER FIELDS
================================================================================

  Alias                        Field ID              Description
  -------------------------    ------------------    -------------------------
  W, watchers                  watches               Built-in Jira Watchers
  IW, issue-watchers,          customfield_33411     Issue Watchers
    "Issue Watchers"
  SIW, "Security Issue         customfield_33432     Security Issue Watchers
    Watchers"                                          (default)
  WG, watcher-groups,          customfield_33462     Watcher Groups
    "Watcher Groups"

  Use -W to list fields, or --custom-field for unlisted fields.
  Aliases are case-insensitive. Full names must be quoted.

================================================================================
QUICK START EXAMPLES
================================================================================

  List Fields:
    j.manageWatchers.py -W

  List Watchers:
    j.manageWatchers.py -j PROJ-1234 -l              # SIW (default)
    j.manageWatchers.py -j PROJ-1234 -l -w IW        # Issue Watchers
    j.manageWatchers.py -j PROJ-1234 -l -w W         # built-in watchers
    j.manageWatchers.py -j PROJ-1234 -l -w all       # all fields

  Add Watchers:
    j.manageWatchers.py -j PROJ-1234 -a user1 user2
    j.manageWatchers.py -j PROJ-1234 -a user1 -w IW
    j.manageWatchers.py -j PROJ-1234 -A users.txt    # from file

  Remove Watchers:
    j.manageWatchers.py -j PROJ-1234 -r user1 user2
    j.manageWatchers.py -j PROJ-1234 -R users.txt    # from file

  Set Watchers (replace all):
    j.manageWatchers.py -j PROJ-1234 -s user1 user2 user3
    j.manageWatchers.py -j PROJ-1234 -S team.txt     # from file

================================================================================
BULK OPERATIONS
================================================================================

  Multiple Issues:
    j.manageWatchers.py -j PROJ-1234 PROJ-5678 PROJ-9999 -a user1

  Issues from File:
    j.manageWatchers.py -f issues.txt -a user1

  Issues from JQL:
    j.manageWatchers.py -q "project = PROJ AND status = Open" -a user1

  Pipe Issues:
    echo "PROJ-1234" | j.manageWatchers.py -a user1

================================================================================
OUTPUT OPTIONS
================================================================================

  Export to CSV:
    j.manageWatchers.py -j PROJ-1234 -l -o watchers.csv

  Row Format (one issue per block):
    j.manageWatchers.py -j PROJ-1234 -l --row
    j.manageWatchers.py -j PROJ-1234 -l -w all --row

  Quiet Mode (less verbose):
    j.manageWatchers.py -j PROJ-1234 -a user1 -Q

  Dry Run (preview without changes):
    j.manageWatchers.py -j PROJ-1234 -a user1 -d

================================================================================
ENVIRONMENT VARIABLES
================================================================================

  Required:
    JIRA_SERVER_NAME   - Jira server hostname (e.g., jira.company.com)
    JIRA_ACC_TOKEN     - Personal access token for authentication

  Optional:
    JIRA_PROJECT_KEY   - Default project key for JQL queries

================================================================================
FILE FORMATS
================================================================================

  Issue file (-f): One issue ID per line, or mixed text with IDs extracted
    PROJ-1234
    PROJ-5678
    # Comments are supported

  User file (-A, -R, -S): One username per line
    john.doe
    jane.smith
    # Comments are supported
"""

from __future__ import print_function

import os
import sys
import argparse
import csv
import json
import re
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from dotenv import load_dotenv

try:
    from prettytable import PrettyTable
except ImportError:
    PrettyTable = None

# Load the environment variables configured on the system
load_dotenv()

# Jira credentials and URL
JIRA_SERVER_NAME = os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN = os.getenv('JIRA_ACC_TOKEN')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', '')

JIRA_URL = f"https://{JIRA_SERVER_NAME}" if JIRA_SERVER_NAME else None

# ---------------------------------------------------------------------------
# Watcher Field Configuration
# ---------------------------------------------------------------------------
# Define available watcher fields with aliases.
# Format: 'alias': ('field_id', 'Description')
#
# To add a new field:
#   'myalias': ('customfield_XXXXX', 'My Field Description'),
#
# The 'watches' field uses Jira's built-in Watchers API (individual add/remove).
# Custom fields use bulk update via the issue edit API.
# ---------------------------------------------------------------------------

WATCHER_FIELDS = {
    # Built-in Jira Watchers (uses /rest/api/2/issue/{key}/watchers endpoint)
    # Aliases: Watchers, watchers, W
    'watchers': ('watches', 'Watchers'),
    'w': ('watches', 'Watchers'),

    # Issue Watchers - custom user picker field
    # Aliases: Issue Watchers, issue-watchers, IW
    'issue watchers': ('customfield_33411', 'Issue Watchers'),
    'issue-watchers': ('customfield_33411', 'Issue Watchers'),
    'iw': ('customfield_33411', 'Issue Watchers'),

    # Security Issue Watchers - custom user picker field (DEFAULT)
    # Aliases: Security Issue Watchers, SIW
    'security issue watchers': ('customfield_33432', 'Security Issue Watchers'),
    'siw': ('customfield_33432', 'Security Issue Watchers'),

    # Watcher Groups - custom user picker field
    # Aliases: Watcher Groups, watcher-groups, WG
    'watcher groups': ('customfield_33462', 'Watcher Groups'),
    'watcher-groups': ('customfield_33462', 'Watcher Groups'),
    'wg': ('customfield_33462', 'Watcher Groups'),
}

# Default watcher field when -w is not specified
DEFAULT_WATCHER_FIELD = 'siw'

# Issue key pattern (e.g., PROJ-1234)
ISSUE_PATTERN = re.compile(r'^[A-Z]+-\d+$', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Jira Client with Retry Logic
# ---------------------------------------------------------------------------

class JiraClient:
    """Client for interacting with Jira REST API with retry support."""

    def __init__(self, base_url: str, token: str, timeout: int = 30):
        self.base_url = base_url
        self.token = token
        self.timeout = timeout
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Connection': 'close',
        }

    def _is_transient_error(self, exc: Exception) -> bool:
        """Check if error is transient and retryable."""
        details = str(exc)
        return any(indicator in details for indicator in [
            'UNEXPECTED_EOF_WHILE_READING',
            'EOF occurred in violation of protocol',
            'SSLEOFError',
            'ConnectionResetError',
            'bad record mac',
        ])

    def _request_with_retry(self, method: str, url: str, params: Optional[Dict] = None,
                            data: Optional[str] = None, operation: str = "Request",
                            max_retries: int = 5) -> requests.Response:
        """Make HTTP request with retry logic for transient failures."""
        retryable_http = {429, 500, 502, 503, 504}
        last_exc = None

        for attempt in range(1, max_retries + 1):
            session = requests.Session()
            try:
                response = session.request(
                    method, url,
                    headers=self.headers,
                    params=params,
                    data=data,
                    timeout=self.timeout
                )

                if response.status_code in retryable_http and attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    print(f"{operation}: HTTP {response.status_code} (attempt {attempt}/{max_retries}), "
                          f"retrying in {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue

                return response

            except requests.exceptions.SSLError as exc:
                last_exc = exc
                if self._is_transient_error(exc) and attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    print(f"{operation}: transient SSL error (attempt {attempt}/{max_retries}), "
                          f"retrying in {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                raise

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as exc:
                last_exc = exc
                if attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    print(f"{operation}: {type(exc).__name__} (attempt {attempt}/{max_retries}), "
                          f"retrying in {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                raise

            finally:
                session.close()

        if last_exc:
            raise last_exc
        raise RuntimeError(f"{operation}: Max retries exceeded")

    def get_issue(self, issue_key: str, fields: Optional[List[str]] = None) -> Optional[Dict]:
        """Fetch a single issue by key."""
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        params = {}
        if fields:
            params['fields'] = ','.join(fields)

        response = self._request_with_retry('GET', url, params=params, operation=f'Fetch {issue_key}')
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def update_issue(self, issue_key: str, fields: Dict) -> bool:
        """Update issue fields."""
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        data = json.dumps({"fields": fields})

        response = self._request_with_retry('PUT', url, data=data, operation=f'Update {issue_key}')
        return response.status_code == 204

    def get_user(self, username: str) -> Optional[Dict]:
        """Fetch user details by username."""
        url = f"{self.base_url}/rest/api/2/user"
        params = {'username': username}

        response = self._request_with_retry('GET', url, params=params, operation=f'Fetch user {username}')
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def search_issues(self, jql: str, fields: List[str], max_results: int = 0) -> List[Dict]:
        """Search issues using JQL query."""
        url = f"{self.base_url}/rest/api/2/search"
        all_issues = []
        seen_keys = set()
        start_at = 0
        batch_size = 100

        while True:
            params = {
                'jql': jql,
                'startAt': start_at,
                'maxResults': batch_size if max_results == 0 else min(batch_size, max_results - len(all_issues)),
                'fields': ','.join(fields),
            }

            response = self._request_with_retry('GET', url, params=params, operation='Issue search')

            # Handle JQL errors with clean messaging (no traceback)
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_msgs = error_data.get('errorMessages', [])
                    errors = error_data.get('errors', {})
                    msg = '; '.join(error_msgs) if error_msgs else str(errors)
                    print(f"JQL Error: {msg}", file=sys.stderr)
                except Exception:
                    print(f"Error: Bad request (400)", file=sys.stderr)
                sys.exit(1)

            response.raise_for_status()

            payload = response.json()
            issues = payload.get('issues', [])
            total = payload.get('total', 0)

            if not issues:
                break

            for issue in issues:
                key = issue.get('key', '')
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    all_issues.append(issue)

            if max_results > 0 and len(all_issues) >= max_results:
                all_issues = all_issues[:max_results]
                break

            start_at += len(issues)
            if start_at >= total:
                break

        return all_issues

    # --- Built-in Watchers API (for 'watches' field) ---

    def get_builtin_watchers(self, issue_key: str) -> List[Dict]:
        """Get watchers using the built-in watchers API."""
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/watchers"
        response = self._request_with_retry('GET', url, operation=f'Get watchers {issue_key}')
        if response.status_code == 404:
            return []
        response.raise_for_status()
        data = response.json()
        return data.get('watchers', [])

    def add_builtin_watcher(self, issue_key: str, username: str) -> bool:
        """Add a watcher using the built-in watchers API."""
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/watchers"
        # The API expects just the username as a JSON string
        response = self._request_with_retry(
            'POST', url, data=json.dumps(username),
            operation=f'Add watcher {username} to {issue_key}'
        )
        return response.status_code in (200, 204)

    def remove_builtin_watcher(self, issue_key: str, username: str) -> bool:
        """Remove a watcher using the built-in watchers API."""
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/watchers"
        params = {'username': username}
        response = self._request_with_retry(
            'DELETE', url, params=params,
            operation=f'Remove watcher {username} from {issue_key}'
        )
        return response.status_code in (200, 204)


# ---------------------------------------------------------------------------
# Watcher Management
# ---------------------------------------------------------------------------

class WatcherManager:
    """Manage issue watchers for configurable custom fields."""

    def __init__(self, client: JiraClient, custom_field: str):
        self.client = client
        self.custom_field = custom_field
        self._user_cache: Dict[str, Optional[Dict]] = {}
        # Check if using built-in watchers field
        self.is_builtin = (custom_field == 'watches')

    def get_user_details(self, username: str) -> Optional[Dict]:
        """Get user details with caching."""
        if username not in self._user_cache:
            self._user_cache[username] = self.client.get_user(username)
        return self._user_cache[username]

    def get_watchers(self, issue_key: str) -> List[Dict]:
        """Get current watchers for an issue."""
        if self.is_builtin:
            # Use built-in watchers API
            return self.client.get_builtin_watchers(issue_key)
        else:
            # Use custom field
            issue = self.client.get_issue(issue_key, fields=[self.custom_field])
            if not issue:
                print(f"Warning: Issue {issue_key} not found", file=sys.stderr)
                return []
            watchers = issue.get('fields', {}).get(self.custom_field) or []
            return watchers

    def get_watcher_names(self, issue_key: str) -> List[str]:
        """Get current watcher names for an issue."""
        watchers = self.get_watchers(issue_key)
        return [w.get('name', w.get('displayName', '')) for w in watchers]

    def update_watchers(self, issue_key: str, watchers: List[Dict], dry_run: bool = False) -> bool:
        """Update watchers for an issue."""
        if dry_run:
            return True

        if self.is_builtin:
            # Built-in watchers don't support bulk update, handled separately
            # This method shouldn't be called for built-in watchers
            print("Warning: Built-in watchers don't support bulk update", file=sys.stderr)
            return False

        success = self.client.update_issue(issue_key, {self.custom_field: watchers})
        return success

    def update_builtin_watchers(self, issue_key: str,
                                 add_users: List[str], remove_users: List[str],
                                 dry_run: bool = False) -> Tuple[List[str], List[str]]:
        """Update built-in watchers by adding/removing individual users.
        Returns (added_users, removed_users)."""
        added = []
        removed = []

        for username in remove_users:
            if dry_run:
                removed.append(username)
            else:
                if self.client.remove_builtin_watcher(issue_key, username):
                    removed.append(username)
                else:
                    print(f"  Failed to remove {username}", file=sys.stderr)

        for username in add_users:
            if dry_run:
                added.append(username)
            else:
                if self.client.add_builtin_watcher(issue_key, username):
                    added.append(username)
                else:
                    print(f"  Failed to add {username}", file=sys.stderr)

        return added, removed

    def add_watchers(self, watcher_list: List[Dict], users_to_add: List[str],
                     verbose: bool = True, force: bool = False) -> Tuple[List[Dict], List[str]]:
        """
        Add users to watcher list.
        Returns (updated_list, list_of_added_users).
        If force=True, skip user validation (for groups/DLs).
        """
        watcher_names = {w.get('name', '').lower() for w in watcher_list}
        added = []
        result = watcher_list[:]

        for username in users_to_add:
            if force:
                # Skip validation, create minimal user dict
                if username.lower() in watcher_names:
                    if verbose:
                        print(f"  {username} already in watcher list")
                    continue
                if verbose:
                    print(f"  Adding {username} (force mode)")
                result.append({'name': username})
                watcher_names.add(username.lower())
                added.append(username)
            else:
                user = self.get_user_details(username)
                if not user:
                    print(f"Warning: User '{username}' not found, skipping", file=sys.stderr)
                    continue

                if user.get('name', '').lower() in watcher_names:
                    if verbose:
                        print(f"  {user.get('name')} already in watcher list")
                    continue

                if verbose:
                    print(f"  Adding {user.get('name')}")
                result.append(user)
                watcher_names.add(user.get('name', '').lower())
                added.append(username)

        return result, added

    def remove_watchers(self, watcher_list: List[Dict], users_to_remove: List[str],
                        verbose: bool = True) -> Tuple[List[Dict], List[str]]:
        """
        Remove users from watcher list.
        Returns (updated_list, list_of_removed_users).
        """
        removed = []

        # Build lookup of users to remove
        remove_urls = set()
        remove_names = set()
        for username in users_to_remove:
            user = self.get_user_details(username)
            if user:
                remove_urls.add(user.get('self'))
                remove_names.add(user.get('name', '').lower())
            else:
                # Try matching by name directly
                remove_names.add(username.lower())

        result = []
        for watcher in watcher_list:
            watcher_url = watcher.get('self')
            watcher_name = watcher.get('name', '')

            if watcher_url in remove_urls or watcher_name.lower() in remove_names:
                if verbose:
                    print(f"  Removing {watcher_name}")
                removed.append(watcher_name)
            else:
                result.append(watcher)

        return result, removed

    def set_watchers(self, users: List[str], verbose: bool = True, force: bool = False) -> List[Dict]:
        """
        Create a new watcher list from usernames.
        Returns list of user dicts.
        If force=True, skip user validation (for groups/DLs).
        """
        result = []
        for username in users:
            if force:
                # Skip validation, create minimal user dict
                if verbose:
                    print(f"  Setting {username} (force mode)")
                result.append({'name': username})
            else:
                user = self.get_user_details(username)
                if not user:
                    print(f"Warning: User '{username}' not found, skipping", file=sys.stderr)
                    continue
                if verbose:
                    print(f"  Setting {user.get('name')}")
                result.append(user)
        return result


# ---------------------------------------------------------------------------
# Input/Output Utilities
# ---------------------------------------------------------------------------

def load_lines_from_file(filepath: str) -> List[str]:
    """Load non-empty, non-comment lines from file."""
    if not filepath or not os.path.exists(filepath):
        return []

    lines = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # Strip inline comments
            if '#' in stripped:
                stripped = stripped.split('#', 1)[0].strip()
            if stripped:
                lines.append(stripped)
    return lines


def parse_issue_keys_from_text(text: str) -> List[str]:
    """Extract issue keys from text."""
    # Find all PROJ-NNNN patterns
    matches = re.findall(r'[A-Z]+-\d+', text, re.IGNORECASE)
    # Normalize to uppercase and dedupe while preserving order
    seen = set()
    result = []
    for m in matches:
        key = m.upper()
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def read_stdin_input() -> Optional[str]:
    """Read from stdin if available (non-blocking check)."""
    import select
    if select.select([sys.stdin], [], [], 0.0)[0]:
        return sys.stdin.read()
    return None


def print_watchers_table(results: List[Dict], output_file: Optional[str] = None,
                         field_name: str = 'Watchers', row_format: bool = False):
    """Print watcher information in table format."""
    if not results:
        print("No results to display.")
        return

    if output_file:
        # Export to CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Issue Key', field_name, 'Count'])
            for r in results:
                writer.writerow([r['key'], ', '.join(r['watchers']), r['count']])
        print(f"Exported {len(results)} issues to {output_file}", file=sys.stderr)
        return

    if row_format:
        # Row format: one issue per block
        for r in results:
            print(f"Issue Key: {r['key']}")
            watchers_str = ', '.join(sorted(r['watchers'])) if r['watchers'] else '(none)'
            print(f"{field_name} ({r['count']}): {watchers_str}")
            print()
        return

    # Wrap long watcher lists for better readability
    max_width = 70

    if PrettyTable:
        table = PrettyTable()
        table.field_names = ['Issue Key', field_name, 'Count']
        table.align['Issue Key'] = 'l'
        table.align[field_name] = 'l'
        table.align['Count'] = 'c'
        table.max_width[field_name] = max_width

        for r in results:
            watchers_str = ', '.join(sorted(r['watchers']))
            # Wrap long lines
            if len(watchers_str) > max_width:
                wrapped = textwrap.fill(watchers_str, width=max_width)
            else:
                wrapped = watchers_str
            table.add_row([r['key'], wrapped, r['count']])
        print(table)
    else:
        # Simple format
        print(f"{'Issue Key':<15} {field_name:<60} {'Count'}")
        print("-" * 80)
        for r in results:
            watchers_str = ', '.join(sorted(r['watchers']))
            if len(watchers_str) > 55:
                watchers_str = watchers_str[:52] + '...'
            print(f"{r['key']:<15} {watchers_str:<60} {r['count']}")


def print_update_results(results: List[Dict], output_file: Optional[str] = None):
    """Print update results in table format."""
    if not results:
        print("No results to display.")
        return

    if output_file:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Issue Key', 'Before', 'After', 'Added', 'Removed', 'Status'])
            for r in results:
                writer.writerow([
                    r['key'],
                    ', '.join(sorted(r['before'])),
                    ', '.join(sorted(r['after'])),
                    ', '.join(sorted(r.get('added', []))),
                    ', '.join(sorted(r.get('removed', []))),
                    r['status']
                ])
        print(f"Exported {len(results)} results to {output_file}", file=sys.stderr)
        return

    max_width = 35

    if PrettyTable:
        table = PrettyTable()
        table.field_names = ['Issue Key', 'Before', 'After', 'Status']
        table.align['Issue Key'] = 'l'
        table.align['Before'] = 'l'
        table.align['After'] = 'l'
        table.align['Status'] = 'c'
        table.max_width['Before'] = max_width
        table.max_width['After'] = max_width

        for r in results:
            before_str = ', '.join(sorted(r['before']))
            after_str = ', '.join(sorted(r['after']))
            before = textwrap.fill(before_str, width=max_width) if len(before_str) > max_width else before_str
            after = textwrap.fill(after_str, width=max_width) if len(after_str) > max_width else after_str
            table.add_row([r['key'], before, after, r['status']])
        print(table)
    else:
        for r in results:
            print(f"\n{r['key']}:")
            print(f"  Before: {', '.join(sorted(r['before']))}")
            print(f"  After:  {', '.join(sorted(r['after']))}")
            print(f"  Status: {r['status']}")


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------

def cmd_list_watchers(client: JiraClient, issue_keys: List[str],
                      custom_field: str, field_name: str = 'Watchers',
                      output_file: Optional[str] = None, quiet: bool = False,
                      row_format: bool = False):
    """List watchers for issues."""
    manager = WatcherManager(client, custom_field=custom_field)
    results = []

    if not quiet:
        print(f"\nField: {field_name} ({custom_field})", file=sys.stderr)

    def fetch_watchers(key):
        """Fetch watchers for a single issue."""
        watchers = manager.get_watcher_names(key)
        return {'key': key, 'watchers': watchers, 'count': len(watchers)}

    # Parallel fetch
    with ThreadPoolExecutor(max_workers=min(10, len(issue_keys))) as executor:
        futures = {executor.submit(fetch_watchers, key): key for key in issue_keys}
        for future in as_completed(futures):
            key = futures[future]
            if not quiet:
                print(f"Fetched watchers for {key}", file=sys.stderr)
            results.append(future.result())

    # Sort results to maintain original order
    key_order = {key: i for i, key in enumerate(issue_keys)}
    results.sort(key=lambda x: key_order[x['key']])

    if not quiet:
        print(file=sys.stderr)  # Blank line between progress and output
    print_watchers_table(results, output_file, field_name, row_format)
    return results


def cmd_update_watchers(client: JiraClient, issue_keys: List[str],
                        add_users: List[str], remove_users: List[str],
                        custom_field: str, field_name: str = 'Watchers',
                        set_users: Optional[List[str]] = None,
                        dry_run: bool = False, quiet: bool = False,
                        output_file: Optional[str] = None, force: bool = False):
    """Add/remove/set watchers for issues."""
    manager = WatcherManager(client, custom_field=custom_field)
    results = []
    is_builtin = (custom_field == 'watches')

    print(f"\nField: {field_name} ({custom_field})")
    if is_builtin:
        print("(Using built-in Jira watchers API)")

    for key in issue_keys:
        print(f"\n{'='*60}")
        print(f"Processing {key}")
        print(f"{'='*60}")

        # Get current watchers
        current_watchers = manager.get_watchers(key)
        before_names = [w.get('name', w.get('displayName', '')) for w in current_watchers]

        if is_builtin:
            # Built-in watchers: handle add/remove individually
            actual_add = list(add_users)
            actual_remove = list(remove_users)

            if set_users is not None:
                # Set mode: remove all current, add all new
                actual_remove = [n for n in before_names if n not in set_users]
                actual_add = [u for u in set_users if u not in before_names]
                print(f"Setting {field_name} (built-in mode):")

            if actual_remove:
                print(f"Removing from {field_name}:")
                for u in actual_remove:
                    if not quiet:
                        print(f"  Removing {u}")

            if actual_add:
                print(f"Adding to {field_name}:")
                for u in actual_add:
                    if not quiet:
                        print(f"  Adding {u}")

            # Calculate expected after state
            after_names = [n for n in before_names if n not in actual_remove]
            after_names.extend([u for u in actual_add if u not in after_names])

            print(f"\nBefore: {before_names}")
            print(f"After:  {after_names}")

            # Execute updates
            if set(before_names) == set(after_names):
                status = "No changes"
                added = []
                removed = []
            elif dry_run:
                status = "Dry run (not updated)"
                added = actual_add
                removed = actual_remove
            else:
                added, removed = manager.update_builtin_watchers(
                    key, actual_add, actual_remove, dry_run=False)
                status = "Updated"

            print(f"\nStatus: {status}")

        else:
            # Custom field: bulk update
            if set_users is not None:
                # Set mode: replace entire list
                print(f"Setting {field_name}:")
                final_watchers = manager.set_watchers(set_users, verbose=not quiet, force=force)
                added = set_users
                removed = before_names
            else:
                # Add/Remove mode
                final_watchers = current_watchers[:]

                if remove_users:
                    print(f"Removing from {field_name}:")
                    final_watchers, removed = manager.remove_watchers(
                        final_watchers, remove_users, verbose=not quiet)
                else:
                    removed = []

                if add_users:
                    print(f"Adding to {field_name}:")
                    final_watchers, added = manager.add_watchers(
                        final_watchers, add_users, verbose=not quiet, force=force)
                else:
                    added = []

            after_names = [w.get('name', '') for w in final_watchers]

            print(f"\nBefore: {before_names}")
            print(f"After:  {after_names}")

            # Check if update needed
            if set(before_names) == set(after_names):
                status = "No changes"
                print(f"\nStatus: {status}")
            elif dry_run:
                status = "Dry run (not updated)"
                print(f"\nStatus: {status}")
            else:
                success = manager.update_watchers(key, final_watchers)
                status = "Updated" if success else "Failed"
                print(f"\nStatus: {status}")

        results.append({
            'key': key,
            'before': before_names,
            'after': after_names,
            'added': added if isinstance(added, list) else [],
            'removed': removed if isinstance(removed, list) else [],
            'status': status
        })

    if output_file:
        print_update_results(results, output_file)

    return results


# ---------------------------------------------------------------------------
# Argument Parsing
# ---------------------------------------------------------------------------

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Manage watchers on Jira issues. Supports multiple watcher fields '
                    'including built-in Watchers, Issue Watchers, Security Issue Watchers, '
                    'and Watcher Groups. Use -W to list available fields.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Input sources
    input_group = parser.add_argument_group('Input Sources',
        'Specify which issues to process. Multiple sources can be combined.')
    input_group.add_argument(
        '-j', '--jira-ids', nargs='+', dest='jira_ids', metavar='ID',
        help='Issue IDs to process (e.g., -j PROJ-1234 PROJ-5678)')
    input_group.add_argument(
        '-f', '--file', type=str, metavar='FILE',
        help='File containing issue IDs (one per line, comments with #)')
    input_group.add_argument(
        '-q', '--jql', type=str, metavar='JQL',
        help='JQL query to select issues (e.g., "project = PROJ AND status = Open")')

    # Operations
    ops_group = parser.add_argument_group('Operations',
        'What to do with watchers. Default is -l (list) if no operation specified.')
    ops_group.add_argument(
        '-l', '--list', action='store_true',
        help='List current watchers (default if no operation specified)')
    ops_group.add_argument(
        '-a', '--add', nargs='*', default=[], metavar='USER',
        help='Add users as watchers (e.g., -a john.doe jane.smith)')
    ops_group.add_argument(
        '-r', '--remove', nargs='*', default=[], metavar='USER',
        help='Remove users from watchers (e.g., -r john.doe)')
    ops_group.add_argument(
        '-s', '--set', nargs='*', default=None, dest='set_users', metavar='USER',
        help='Set watchers to exactly these users (replaces entire list)')

    # User lists from file
    file_group = parser.add_argument_group('User Lists from File',
        'Load usernames from files instead of command line.')
    file_group.add_argument(
        '-A', '--add-file', type=str, metavar='FILE',
        help='File with usernames to add (one per line)')
    file_group.add_argument(
        '-R', '--remove-file', type=str, metavar='FILE',
        help='File with usernames to remove (one per line)')
    file_group.add_argument(
        '-S', '--set-file', type=str, metavar='FILE',
        help='File with usernames to set as watchers (replaces entire list)')

    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '-o', '--output', type=str, metavar='FILE',
        help='Export results to CSV file')
    output_group.add_argument(
        '-Q', '--quiet', action='store_true',
        help='Suppress verbose output (show only summary)')
    output_group.add_argument(
        '--row', action='store_true',
        help='Row format: print each issue with watchers on separate lines')

    # Execution options
    exec_group = parser.add_argument_group('Execution Options')
    exec_group.add_argument(
        '-d', '--dry-run', action='store_true',
        help='Preview changes without actually updating issues')
    exec_group.add_argument(
        '-m', '--max', type=int, default=0, metavar='N',
        help='Limit number of issues to process (0 = unlimited)')
    exec_group.add_argument(
        '-F', '--force', action='store_true',
        help='Skip user validation (use for groups/distribution lists)')

    # Watcher field selection
    field_group = parser.add_argument_group('Watcher Field Selection',
        f'Choose which watcher field to manage. Default: {DEFAULT_WATCHER_FIELD}')
    field_group.add_argument(
        '-w', '--watcher-field', type=str, default=DEFAULT_WATCHER_FIELD,
        metavar='FIELD',
        help='Watcher field alias (e.g., SIW, IW, WG, W, "all" for all fields). '
             'Use -W to see all available fields')
    field_group.add_argument(
        '-W', '--list-fields', action='store_true',
        help='List all available watcher fields with their IDs and exit')
    field_group.add_argument(
        '--custom-field', type=str, metavar='ID',
        help='Use a custom field ID directly (e.g., customfield_12345)')

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Main entry point."""
    args = parse_args()

    # Handle --list-fields early (no env vars needed)
    if args.list_fields:
        print()
        print("=" * 78)
        print("AVAILABLE WATCHER FIELDS")
        print("=" * 78)
        print()
        print(f"  {'Alias':<35} {'Field ID':<22} Description")
        print(f"  {'-'*33:<35} {'-'*20:<22} {'-'*20}")

        # Group by custom field ID to show aliases
        by_field = {}
        for alias, (field_id, desc) in WATCHER_FIELDS.items():
            if field_id not in by_field:
                by_field[field_id] = {'desc': desc, 'aliases': []}
            by_field[field_id]['aliases'].append(alias)

        for field_id, info in sorted(by_field.items(), key=lambda x: x[1]['desc']):
            # Format aliases: quote those with spaces, uppercase short ones
            formatted = []
            for a in sorted(info['aliases'], key=len):
                if ' ' in a:
                    formatted.append(f'"{a}"')
                elif len(a) <= 3:
                    formatted.append(a.upper())
                else:
                    formatted.append(a)
            aliases = ', '.join(formatted)
            print(f"  {aliases:<35} {field_id:<22} {info['desc']}")

        print()
        print(f"  Default field: {DEFAULT_WATCHER_FIELD.upper()}")
        print(f"  Use -w all to list all watcher fields at once (list mode only).")
        print()
        print("  Aliases are case-insensitive. Full names must be quoted on command line.")
        print("  Note: 'watchers' (W) uses the built-in Jira Watchers API.")
        print()
        print("  Use --custom-field ID to use an unlisted custom field.")
        print()
        sys.exit(0)

    # Validate environment
    if not JIRA_URL or not JIRA_API_TOKEN:
        print("Error: JIRA_SERVER_NAME and JIRA_ACC_TOKEN environment variables required.",
              file=sys.stderr)
        sys.exit(1)

    # Resolve watcher field (case-insensitive lookup)
    field_key = args.watcher_field.lower()
    all_fields = (field_key == 'all')  # Special case for -w all

    if all_fields:
        # Will iterate through all fields later
        custom_field = None
        field_name = None
    elif args.custom_field:
        # Direct custom field ID
        custom_field = args.custom_field
        field_name = f"Custom ({custom_field})"
    elif field_key in WATCHER_FIELDS:
        custom_field, field_name = WATCHER_FIELDS[field_key]
    elif args.watcher_field.startswith('customfield_'):
        # Allow direct field ID via -w too
        custom_field = args.watcher_field
        field_name = f"Custom ({custom_field})"
    else:
        print(f"Error: Unknown watcher field '{args.watcher_field}'.", file=sys.stderr)
        print("Use -W to list available fields, or --custom-field for unlisted fields.",
              file=sys.stderr)
        sys.exit(1)

    # Collect issue keys from all sources
    issue_keys = []

    # From command line
    if args.jira_ids:
        issue_keys.extend(args.jira_ids)

    # From file
    if args.file:
        file_content = ""
        with open(args.file, 'r', encoding='utf-8') as f:
            file_content = f.read()
        file_keys = parse_issue_keys_from_text(file_content)
        issue_keys.extend(file_keys)
        if not args.quiet:
            print(f"Loaded {len(file_keys)} issues from {args.file}", file=sys.stderr)

    # From stdin
    stdin_input = read_stdin_input()
    if stdin_input:
        stdin_keys = parse_issue_keys_from_text(stdin_input)
        issue_keys.extend(stdin_keys)
        if not args.quiet and stdin_keys:
            print(f"Loaded {len(stdin_keys)} issues from stdin", file=sys.stderr)

    # Initialize client
    client = JiraClient(JIRA_URL, JIRA_API_TOKEN)

    # From JQL
    if args.jql:
        if not args.quiet:
            print(f"Executing JQL: {args.jql}", file=sys.stderr)
        issues = client.search_issues(args.jql, ['key'], max_results=args.max or 0)
        jql_keys = [i['key'] for i in issues]
        issue_keys.extend(jql_keys)
        if not args.quiet:
            print(f"Found {len(jql_keys)} issues from JQL", file=sys.stderr)

    # Deduplicate and validate
    seen = set()
    unique_keys = []
    for key in issue_keys:
        key_upper = key.upper()
        if key_upper not in seen:
            seen.add(key_upper)
            unique_keys.append(key_upper)
    issue_keys = unique_keys

    # Apply max limit
    if args.max > 0 and len(issue_keys) > args.max:
        issue_keys = issue_keys[:args.max]
        if not args.quiet:
            print(f"Limited to first {args.max} issues", file=sys.stderr)

    if not issue_keys:
        if args.jql:
            print("No issues found matching the JQL query.", file=sys.stderr)
        else:
            print("Error: No issue keys provided. Use -j, -f, -q, or pipe to stdin.",
                  file=sys.stderr)
        sys.exit(0 if args.jql else 1)

    # Collect users to add/remove/set
    add_users = list(args.add) if args.add else []
    remove_users = list(args.remove) if args.remove else []
    set_users = list(args.set_users) if args.set_users is not None else None

    # Load users from files
    if args.add_file:
        file_users = load_lines_from_file(args.add_file)
        add_users.extend(file_users)
        if not args.quiet:
            print(f"Loaded {len(file_users)} users to add from {args.add_file}", file=sys.stderr)

    if args.remove_file:
        file_users = load_lines_from_file(args.remove_file)
        remove_users.extend(file_users)
        if not args.quiet:
            print(f"Loaded {len(file_users)} users to remove from {args.remove_file}", file=sys.stderr)

    if args.set_file:
        set_users = load_lines_from_file(args.set_file)
        if not args.quiet:
            print(f"Loaded {len(set_users)} users to set from {args.set_file}", file=sys.stderr)

    # Determine operation
    is_list = args.list
    is_update = add_users or remove_users or set_users is not None

    # Default to list if no operation specified
    if not is_list and not is_update:
        is_list = True

    # Handle -w all (all fields)
    if all_fields:
        if is_update:
            print("Error: -w all is only supported for listing (-l), not for add/remove/set.",
                  file=sys.stderr)
            sys.exit(1)

        # Get unique fields (dedupe by field_id)
        unique_fields = {}
        for alias, (fid, fname) in WATCHER_FIELDS.items():
            if fid not in unique_fields:
                unique_fields[fid] = fname

        if args.row:
            # Row format for -w all: group by issue key (parallel fetch)
            all_results = {}  # key -> {field_name: watchers}

            def fetch_field_watchers(fid, fname, key):
                """Fetch watchers for a single field/issue combination."""
                manager = WatcherManager(client, custom_field=fid)
                watchers = manager.get_watcher_names(key)
                return (key, fname, watchers)

            # Build list of all fetch tasks
            fetch_tasks = []
            for fid, fname in sorted(unique_fields.items(), key=lambda x: x[1]):
                for key in issue_keys:
                    fetch_tasks.append((fid, fname, key))

            # Parallel fetch all combinations
            with ThreadPoolExecutor(max_workers=min(10, len(fetch_tasks))) as executor:
                futures = {
                    executor.submit(fetch_field_watchers, fid, fname, key): (fname, key)
                    for fid, fname, key in fetch_tasks
                }
                for future in as_completed(futures):
                    fname, key = futures[future]
                    if not args.quiet:
                        print(f"Fetched {fname} for {key}", file=sys.stderr)
                    issue_key, field_name_result, watchers = future.result()
                    if issue_key not in all_results:
                        all_results[issue_key] = {}
                    all_results[issue_key][field_name_result] = watchers

            # Separator between progress and output
            if not args.quiet:
                print(file=sys.stderr)

            # Print in row format grouped by issue
            for key in issue_keys:
                if key in all_results:
                    print(f"Issue Key: {key}")
                    for fname in sorted(all_results[key].keys()):
                        watchers = all_results[key][fname]
                        count = len(watchers)
                        watchers_str = ', '.join(sorted(watchers)) if watchers else '(none)'
                        print(f"{fname} ({count}): {watchers_str}")
                    print()
        else:
            # Table format: separate table per field
            for fid, fname in sorted(unique_fields.items(), key=lambda x: x[1]):
                cmd_list_watchers(client, issue_keys, fid, fname,
                                  args.output, args.quiet, args.row)
    elif is_list:
        cmd_list_watchers(client, issue_keys, custom_field, field_name,
                          args.output, args.quiet, args.row)
    else:
        cmd_update_watchers(
            client, issue_keys,
            add_users, remove_users,
            custom_field, field_name,
            set_users=set_users,
            dry_run=args.dry_run,
            quiet=args.quiet,
            output_file=args.output,
            force=args.force
        )


if __name__ == "__main__":
    main()
