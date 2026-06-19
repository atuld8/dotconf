#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update Jira issue fields (works with any project: FI, PVM, NBU, etc.)

Features:
- Update standard fields (summary, priority, assignee, components, labels, versions)
- Update custom fields (current status, next steps, aged reason, etc.)
- Transition status with optional resolution
- Add comments (explicit, separate from field updates)
- Validate dropdown values before submitting
- Support both single-field and JSON batch updates
- Short option names for quick access
- Sync fields from linked etrack (auto-fetch or explicit ID)
- Transform etrack values via mapping file before applying

Environment variables expected:
- JIRA_SERVER_NAME
- JIRA_ACC_TOKEN

Usage Examples:
  # Single field update
  j.updateJiraDetails.py FI-12345 -s "New summary"
  j.updateJiraDetails.py PVM-5678 --assignee john.doe
  j.updateJiraDetails.py NBU-9999 -p High

  # Multiple fields via JSON
  j.updateJiraDetails.py FI-12345 --update '{"summary": "New title", "priority": "High"}'

  # Add comment with field changes
  j.updateJiraDetails.py FI-12345 -p High --comment "Escalating priority due to customer impact"

  # Transition status
  j.updateJiraDetails.py PVM-5678 --transition "In Progress"

  # Dry run
  j.updateJiraDetails.py FI-12345 -s "Test" --dry-run

  # Etrack sync (auto-fetch etrack ID from FI linked fields)
  j.updateJiraDetails.py FI-12345 -set -sc              # Sync component
  j.updateJiraDetails.py FI-12345 -set -sc -sav         # Sync component & version
  j.updateJiraDetails.py FI-12345 -set -sc -mf map.json # Sync with value mapping

  # Etrack sync (explicit etrack ID)
  j.updateJiraDetails.py FI-12345 -set 12345678 -sc -sav

Etrack Sync Options:
  -set [ID]  --sync-with-et   Etrack ID (or auto-fetch if omitted)
  -sc        --sync-component Sync component from etrack
  -sav       --sync-affectsversion  Sync affects version from etrack
  -mf FILE   --mapping-file   JSON file with etrack_mapping section

Mapping File Format (JSON):
  {
    "fi_mapping": {
      "component": {"CurrentFIValue": "NewValue"},
      "version": {"6.1": "11.1"}
    },
    "etrack_mapping": {
      "component": {"EtrackValue": "TargetJiraValue"},
      "version": {"EtrackVer": "JiraVer"}
    }
  }

  Sections:
    fi_mapping     - Used by j.validateAndSyncFIs.py -mo mode
    etrack_mapping - Used by -set -mf: transform etrack values before setting
"""

from __future__ import print_function

import argparse
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# Ensure console output is UTF-8 safe
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add parent directory to path for account_manager imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from account_manager.etrack_integration import EtrackExecutor
    ETRACK_AVAILABLE = True
except ImportError:
    ETRACK_AVAILABLE = False
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
else:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Field Definitions
# ---------------------------------------------------------------------------

# Standard Jira fields that can be updated
STANDARD_FIELDS = {
    'summary': {'type': 'string', 'jira_key': 'summary'},
    'description': {'type': 'string', 'jira_key': 'description'},
    'priority': {'type': 'dropdown', 'jira_key': 'priority'},
    'assignee': {'type': 'user', 'jira_key': 'assignee'},
    'reporter': {'type': 'user', 'jira_key': 'reporter', 'restricted': True},
    'components': {'type': 'array', 'jira_key': 'components'},
    'labels': {'type': 'array_string', 'jira_key': 'labels'},
    'fixversions': {'type': 'array', 'jira_key': 'fixVersions'},
    'affectsversions': {'type': 'array', 'jira_key': 'versions'},
}

# Custom fields with known IDs
CUSTOM_FIELDS = {
    'currentstatus': {'type': 'string', 'jira_key': 'customfield_11202', 'display': 'Current Status'},
    'nextsteps': {'type': 'string', 'jira_key': 'customfield_11203', 'display': 'Next Steps'},
    'casestatus': {'type': 'dropdown', 'jira_key': 'customfield_16200', 'display': 'Case Status'},
    'customer': {'type': 'string', 'jira_key': 'customfield_18901', 'display': 'Customer'},
    'etrackincident': {'type': 'array_number', 'jira_key': 'customfield_33802', 'display': 'Etrack Incident'},
    'etrackref': {'type': 'string', 'jira_key': 'customfield_36508', 'display': 'Etrack Ref'},
    'caseid': {'type': 'string', 'jira_key': 'customfield_11814', 'display': 'Case#'},
    'slack': {'type': 'string', 'jira_key': 'customfield_24004', 'display': 'Slack'},
}

# Custom fields resolved by name (need API lookup for ID)
NAMED_CUSTOM_FIELDS = {
    'severity': {'type': 'dropdown', 'names': ['Severity']},
    'businessunit': {'type': 'dropdown', 'names': ['Business Unit', 'BusinessUnit']},
    'capinvolvement': {'type': 'dropdown', 'names': ['CAP Involvement', 'CAPInvolvement']},
    'agedreason': {'type': 'dropdown', 'names': ['Aged Reason', 'AgedReason']},
    'assigneemanager': {'type': 'user', 'names': ['Assignee Manager', 'AssigneeManager']},
    'fircacategory': {'type': 'dropdown', 'names': ['FI RCA Category']},
    'actiontaken': {'type': 'dropdown', 'names': ['Action Taken']},
    'etrackresolution': {'type': 'dropdown', 'names': ['Etrack-Resolution', 'Etrack Resolution']},
    'solution': {'type': 'dropdown', 'names': ['Solution']},
    'progressstatus': {'type': 'dropdown', 'names': ['Progress Status']},
    'securitylevel': {'type': 'dropdown', 'names': ['Security Level']},
    'cvssscore': {'type': 'string', 'names': ['CVSS Score']},
    'impact': {'type': 'dropdown', 'names': ['Impact']},
    'source': {'type': 'dropdown', 'names': ['Source']},
}

# Short option mappings
SHORT_OPTIONS = {
    's': 'summary',
    'd': 'description',
    'p': 'priority',
    'a': 'assignee',
    'c': 'components',
    'l': 'labels',
    'fv': 'fixversions',
    'av': 'affectsversions',
    'cs': 'currentstatus',
    'ns': 'nextsteps',
    'ar': 'agedreason',
    'bu': 'businessunit',
    'sv': 'severity',
    'cap': 'capinvolvement',
    'cst': 'casestatus',
    'et': 'etrackincident',
    'er': 'etrackref',
    'cid': 'caseid',
    'sl': 'slack',
    'am': 'assigneemanager',
    'rca': 'fircacategory',
    'at': 'actiontaken',
    'sol': 'solution',
    'ps': 'progressstatus',
}

# Fields that cannot be updated directly
READ_ONLY_FIELDS = {'key', 'project', 'issuetype', 'created', 'updated', 'status', 'resolution'}


# ---------------------------------------------------------------------------
# Jira Client
# ---------------------------------------------------------------------------

class JiraUpdateClient:
    """Jira client with read and write capabilities."""

    def __init__(self):
        load_dotenv()
        self.server = os.getenv("JIRA_SERVER_NAME")
        self.token = os.getenv("JIRA_ACC_TOKEN")
        self.base_url = "https://{}".format(self.server) if self.server else None
        self.timeout = 30
        self._fields_cache = None  # type: Optional[Dict[str, Dict[str, Any]]]
        self._field_options_cache = {}  # type: Dict[str, List[Dict[str, str]]]

        if not self.base_url or not self.token:
            raise RuntimeError("Missing JIRA_SERVER_NAME or JIRA_ACC_TOKEN in environment")

        self.headers = {
            "Authorization": "Bearer {}".format(self.token),
            "Content-Type": "application/json",
        }

    def _request(self, method, url, params=None, json_data=None):
        # type: (str, str, Optional[Dict], Optional[Dict]) -> requests.Response
        """Make HTTP request with retry logic."""
        max_retries = 5
        last_exc = None  # type: Optional[Exception]
        request_headers = dict(self.headers)
        request_headers["Connection"] = "close"

        for attempt in range(1, max_retries + 1):
            session = requests.Session()
            try:
                try:
                    if method.upper() == 'GET':
                        response = session.get(url, headers=request_headers, params=params, timeout=self.timeout)
                    elif method.upper() == 'PUT':
                        response = session.put(url, headers=request_headers, json=json_data, timeout=self.timeout)
                    elif method.upper() == 'POST':
                        response = session.post(url, headers=request_headers, json=json_data, timeout=self.timeout)
                    else:
                        raise ValueError("Unsupported HTTP method: {}".format(method))
                except requests.exceptions.SSLError as exc:
                    msg = str(exc)
                    is_transient = any(x in msg for x in [
                        "UNEXPECTED_EOF", "EOF occurred", "SSLEOFError", "ConnectionReset", "bad record"
                    ])
                    if is_transient and attempt < max_retries:
                        last_exc = exc
                        wait = min(2 ** attempt, 30)
                        print("Transient SSL error (attempt {}/{}): {}. Retrying in {}s...".format(
                            attempt, max_retries, exc, wait), file=sys.stderr)
                        time.sleep(wait)
                        continue
                    raise RuntimeError("TLS/SSL error: {}".format(exc))
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        wait = min(2 ** attempt, 30)
                        print("Network error (attempt {}/{}): {}. Retrying in {}s...".format(
                            attempt, max_retries, exc, wait), file=sys.stderr)
                        time.sleep(wait)
                        continue
                    raise RuntimeError("Network error: {}".format(exc))

                if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    print("Jira returned {} (attempt {}/{}). Retrying in {}s...".format(
                        response.status_code, attempt, max_retries, wait), file=sys.stderr)
                    time.sleep(wait)
                    continue

                return response
            finally:
                session.close()

        raise RuntimeError("Network error after {} attempts: {}".format(max_retries, last_exc))

    def get_issue(self, issue_key):
        # type: (str) -> Dict[str, Any]
        """Fetch issue details."""
        url = "{}/rest/api/2/issue/{}".format(self.base_url, issue_key)
        params = {"expand": "names,editmeta"}
        response = self._request('GET', url, params=params)
        if response.status_code != 200:
            raise RuntimeError("Failed to fetch {}: {} {}".format(
                issue_key, response.status_code, response.text[:400]))
        return response.json()

    def update_issue(self, issue_key, fields_data, notify_users=True):
        # type: (str, Dict[str, Any], bool) -> bool
        """Update issue fields."""
        url = "{}/rest/api/2/issue/{}".format(self.base_url, issue_key)
        if not notify_users:
            url += "?notifyUsers=false"

        payload = {"fields": fields_data}
        response = self._request('PUT', url, json_data=payload)

        if response.status_code == 204:
            return True
        elif response.status_code == 200:
            return True
        else:
            error_msg = response.text[:500]
            try:
                error_json = response.json()
                if 'errors' in error_json:
                    error_msg = json.dumps(error_json['errors'], indent=2)
                elif 'errorMessages' in error_json:
                    error_msg = "; ".join(error_json['errorMessages'])
            except Exception:
                pass
            raise RuntimeError("Failed to update {}: {} - {}".format(
                issue_key, response.status_code, error_msg))

    def add_comment(self, issue_key, comment_body):
        # type: (str, str) -> bool
        """Add a comment to an issue."""
        url = "{}/rest/api/2/issue/{}/comment".format(self.base_url, issue_key)
        payload = {"body": comment_body}
        response = self._request('POST', url, json_data=payload)

        if response.status_code in (200, 201):
            return True
        else:
            raise RuntimeError("Failed to add comment to {}: {} {}".format(
                issue_key, response.status_code, response.text[:400]))

    def get_transitions(self, issue_key):
        # type: (str) -> List[Dict[str, Any]]
        """Get available transitions for an issue."""
        url = "{}/rest/api/2/issue/{}/transitions".format(self.base_url, issue_key)
        response = self._request('GET', url)
        if response.status_code != 200:
            raise RuntimeError("Failed to get transitions for {}: {} {}".format(
                issue_key, response.status_code, response.text[:400]))
        return response.json().get('transitions', [])

    def do_transition(self, issue_key, transition_id, fields_data=None, comment=None):
        # type: (str, str, Optional[Dict], Optional[str]) -> bool
        """Perform a status transition."""
        url = "{}/rest/api/2/issue/{}/transitions".format(self.base_url, issue_key)
        payload = {"transition": {"id": transition_id}}  # type: Dict[str, Any]

        if fields_data:
            payload["fields"] = fields_data
        if comment:
            payload["update"] = {"comment": [{"add": {"body": comment}}]}

        response = self._request('POST', url, json_data=payload)
        if response.status_code == 204:
            return True
        else:
            raise RuntimeError("Failed to transition {}: {} {}".format(
                issue_key, response.status_code, response.text[:400]))

    def get_all_fields(self):
        # type: () -> Dict[str, Dict[str, Any]]
        """Get all Jira fields with their metadata."""
        if self._fields_cache is not None:
            return self._fields_cache

        url = "{}/rest/api/2/field".format(self.base_url)
        response = self._request('GET', url)
        if response.status_code != 200:
            raise RuntimeError("Failed to fetch fields: {} {}".format(
                response.status_code, response.text[:400]))

        self._fields_cache = {}
        for field in response.json():
            field_id = field.get('id', '')
            self._fields_cache[field_id] = {
                'id': field_id,
                'name': field.get('name', ''),
                'custom': field.get('custom', False),
                'schema': field.get('schema', {}),
            }
        return self._fields_cache

    def get_field_id_by_name(self, display_name):
        # type: (str) -> Optional[str]
        """Find field ID by display name."""
        fields = self.get_all_fields()
        normalized = display_name.strip().lower().replace(' ', '').replace('-', '').replace('_', '')

        for field_id, field_info in fields.items():
            field_name = field_info.get('name', '')
            field_normalized = field_name.strip().lower().replace(' ', '').replace('-', '').replace('_', '')
            if field_normalized == normalized:
                return field_id
        return None

    def get_field_options(self, issue_key, field_key):
        # type: (str, str) -> List[Dict[str, str]]
        """Get allowed values for a dropdown field from issue edit metadata."""
        cache_key = "{}:{}".format(issue_key.split('-')[0], field_key)  # Cache by project
        if cache_key in self._field_options_cache:
            return self._field_options_cache[cache_key]

        issue = self.get_issue(issue_key)
        editmeta = issue.get('editmeta', {}).get('fields', {})
        field_meta = editmeta.get(field_key, {})
        allowed = field_meta.get('allowedValues', [])

        options = []
        for item in allowed:
            if isinstance(item, dict):
                options.append({
                    'id': str(item.get('id', '')),
                    'name': item.get('name', item.get('value', '')),
                    'value': item.get('value', item.get('name', '')),
                })

        self._field_options_cache[cache_key] = options
        return options

    def get_priority_options(self):
        # type: () -> List[Dict[str, str]]
        """Get available priorities."""
        url = "{}/rest/api/2/priority".format(self.base_url)
        response = self._request('GET', url)
        if response.status_code != 200:
            return []

        options = []
        for item in response.json():
            options.append({
                'id': str(item.get('id', '')),
                'name': item.get('name', ''),
            })
        return options

    def find_user(self, username_or_email):
        # type: (str) -> Optional[Dict[str, str]]
        """Find user by username or email."""
        # Try exact username first
        url = "{}/rest/api/2/user".format(self.base_url)
        response = self._request('GET', url, params={'username': username_or_email})
        if response.status_code == 200:
            data = response.json()
            return {'name': data.get('name', data.get('key', ''))}

        # Try search
        url = "{}/rest/api/2/user/search".format(self.base_url)
        response = self._request('GET', url, params={'username': username_or_email, 'maxResults': 5})
        if response.status_code == 200:
            users = response.json()
            if users:
                return {'name': users[0].get('name', users[0].get('key', ''))}

        return None


# ---------------------------------------------------------------------------
# Field Value Formatters
# ---------------------------------------------------------------------------

def format_field_value(client, issue_key, field_name, value, field_def):
    # type: (JiraUpdateClient, str, str, Any, Dict[str, Any]) -> Tuple[str, Any]
    """
    Format a field value for Jira API.
    Returns (jira_key, formatted_value).
    """
    field_type = field_def.get('type', 'string')
    jira_key = field_def.get('jira_key')

    # Resolve named custom field to ID
    if not jira_key and 'names' in field_def:
        for name in field_def['names']:
            jira_key = client.get_field_id_by_name(name)
            if jira_key:
                break
        if not jira_key:
            raise ValueError("Could not find field ID for: {}".format(field_name))

    if field_type == 'string':
        return (jira_key, str(value))

    elif field_type == 'user':
        user = client.find_user(str(value))
        if not user:
            raise ValueError("User not found: {}".format(value))
        return (jira_key, user)

    elif field_type == 'dropdown':
        # Validate against allowed values
        if jira_key == 'priority':
            options = client.get_priority_options()
        else:
            options = client.get_field_options(issue_key, jira_key)

        value_str = str(value).strip()
        value_lower = value_str.lower()

        matched = None
        for opt in options:
            if opt.get('name', '').lower() == value_lower or opt.get('value', '').lower() == value_lower:
                matched = opt
                break
            if opt.get('id') == value_str:
                matched = opt
                break

        if not matched:
            available = [opt.get('name', opt.get('value', '')) for opt in options]
            raise ValueError("Invalid value '{}' for field '{}'. Available: {}".format(
                value, field_name, ", ".join(available[:15])))

        # Priority uses 'name', custom fields use 'value' or 'name'
        if jira_key == 'priority':
            return (jira_key, {'name': matched['name']})
        else:
            if matched.get('value'):
                return (jira_key, {'value': matched['value']})
            else:
                return (jira_key, {'name': matched['name']})

    elif field_type == 'array':
        # Array of objects with 'name' (components, versions)
        if isinstance(value, str):
            items = [v.strip() for v in value.split(',') if v.strip()]
        elif isinstance(value, list):
            items = value
        else:
            items = [str(value)]
        return (jira_key, [{'name': item} for item in items])

    elif field_type == 'array_string':
        # Array of plain strings (labels)
        if isinstance(value, str):
            items = [v.strip() for v in value.split(',') if v.strip()]
        elif isinstance(value, list):
            items = value
        else:
            items = [str(value)]
        return (jira_key, items)

    elif field_type == 'array_number':
        # Array of numbers (etrack incident)
        if isinstance(value, str):
            items = [int(v.strip()) for v in re.findall(r'\d+', value)]
        elif isinstance(value, list):
            items = [int(v) for v in value]
        else:
            items = [int(value)]
        return (jira_key, items)

    else:
        return (jira_key, value)


def resolve_field_name(name):
    # type: (str) -> Tuple[str, Dict[str, Any]]
    """
    Resolve field name (short or full) to canonical name and definition.
    Returns (canonical_name, field_definition).
    """
    normalized = name.strip().lower().replace(' ', '').replace('-', '').replace('_', '')

    # Handle singular to plural aliases
    SINGULAR_TO_PLURAL = {
        'component': 'components',
        'label': 'labels',
        'fixversion': 'fixversions',
        'affectsversion': 'affectsversions',
    }
    if normalized in SINGULAR_TO_PLURAL:
        normalized = SINGULAR_TO_PLURAL[normalized]

    # Check short options first
    if normalized in SHORT_OPTIONS:
        normalized = SHORT_OPTIONS[normalized]

    # Check standard fields
    if normalized in STANDARD_FIELDS:
        return (normalized, STANDARD_FIELDS[normalized])

    # Check custom fields with known IDs
    if normalized in CUSTOM_FIELDS:
        return (normalized, CUSTOM_FIELDS[normalized])

    # Check named custom fields
    if normalized in NAMED_CUSTOM_FIELDS:
        return (normalized, NAMED_CUSTOM_FIELDS[normalized])

    # Check if it's a read-only field
    if normalized in READ_ONLY_FIELDS:
        raise ValueError("Field '{}' is read-only and cannot be updated".format(name))

    raise ValueError("Unknown field: '{}'. Use --list-fields to see available fields.".format(name))


def parse_json_update(json_str):
    # type: (str) -> Dict[str, Any]
    """Parse JSON update string."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON: {}".format(e))


# ---------------------------------------------------------------------------
# Main Functions
# ---------------------------------------------------------------------------

def list_available_fields():
    """Print all available fields with their short names."""
    print("\n=== Standard Fields ===")
    print("{:<20} {:<10} {:<15} {}".format("Field", "Short", "Type", "Jira Key"))
    print("-" * 70)
    for name, defn in sorted(STANDARD_FIELDS.items()):
        short = next((k for k, v in SHORT_OPTIONS.items() if v == name), '-')
        print("{:<20} {:<10} {:<15} {}".format(
            name, short, defn.get('type', '-'), defn.get('jira_key', '-')))

    print("\n=== Custom Fields (Known IDs) ===")
    print("{:<20} {:<10} {:<15} {}".format("Field", "Short", "Type", "Display Name"))
    print("-" * 70)
    for name, defn in sorted(CUSTOM_FIELDS.items()):
        short = next((k for k, v in SHORT_OPTIONS.items() if v == name), '-')
        display = defn.get('display', defn.get('jira_key', '-'))
        print("{:<20} {:<10} {:<15} {}".format(
            name, short, defn.get('type', '-'), display))

    print("\n=== Custom Fields (Name-based) ===")
    print("{:<20} {:<10} {:<15} {}".format("Field", "Short", "Type", "Jira Names"))
    print("-" * 70)
    for name, defn in sorted(NAMED_CUSTOM_FIELDS.items()):
        short = next((k for k, v in SHORT_OPTIONS.items() if v == name), '-')
        names = ", ".join(defn.get('names', []))
        print("{:<20} {:<10} {:<15} {}".format(
            name, short, defn.get('type', '-'), names))

    print("\n=== Read-Only Fields (cannot update) ===")
    print(", ".join(sorted(READ_ONLY_FIELDS)))
    print()


def show_transitions(client, issue_key):
    # type: (JiraUpdateClient, str) -> None
    """Show available transitions for an issue."""
    transitions = client.get_transitions(issue_key)
    print("\nAvailable transitions for {}:".format(issue_key))
    print("{:<10} {:<30} {}".format("ID", "Name", "To Status"))
    print("-" * 60)
    for t in transitions:
        to_status = t.get('to', {}).get('name', '-')
        print("{:<10} {:<30} {}".format(t.get('id', '-'), t.get('name', '-'), to_status))
    print()


def show_field_options(client, issue_key, field_name):
    # type: (JiraUpdateClient, str, str) -> None
    """Show allowed values for a dropdown field."""
    canonical, defn = resolve_field_name(field_name)
    jira_key = defn.get('jira_key')

    if not jira_key and 'names' in defn:
        for name in defn['names']:
            jira_key = client.get_field_id_by_name(name)
            if jira_key:
                break

    if not jira_key:
        print("Could not resolve field: {}".format(field_name), file=sys.stderr)
        return

    if jira_key == 'priority':
        options = client.get_priority_options()
    else:
        options = client.get_field_options(issue_key, jira_key)

    print("\nAllowed values for '{}' ({}):".format(canonical, jira_key))
    for opt in options:
        name = opt.get('name', opt.get('value', '-'))
        opt_id = opt.get('id', '-')
        print("  {} (id: {})".format(name, opt_id))
    print()


def load_etrack_mappings(filepath, silent=False):
    # type: (str, bool) -> Dict[str, Dict[str, str]]
    """
    Load etrack-to-jira value mappings from a JSON file.

    Reads the 'etrack_mapping' section from the mapping file.
    Used to transform etrack values before setting them in Jira.

    Args:
        filepath: Path to JSON mapping file
        silent: Suppress warning messages

    Returns:
        Dict with 'component' and 'version' mappings (lowercase keys)

    File format:
    {
        "fi_mapping": {...},
        "etrack_mapping": {
            "component": {"EtrackValue": "TargetJiraValue"},
            "version": {"EtrackVer": "JiraVer"}
        }
    }
    """
    mappings = {"component": {}, "version": {}}  # type: Dict[str, Dict[str, str]]

    if not filepath:
        return mappings

    expanded_path = os.path.expanduser(filepath)
    if not os.path.isfile(expanded_path):
        if not silent:
            print("Warning: Mapping file not found: {}".format(expanded_path), file=sys.stderr)
        return mappings

    try:
        with open(expanded_path, 'r') as f:
            data = json.load(f)

        section_data = data.get('etrack_mapping', {})
        if not section_data:
            if not silent:
                print("Warning: No 'etrack_mapping' section in mapping file", file=sys.stderr)
            return mappings

        # Normalize keys to lowercase for case-insensitive matching
        if "component" in section_data:
            mappings["component"] = {
                k.lower(): v for k, v in section_data["component"].items()
            }
        if "version" in section_data:
            mappings["version"] = {
                k.lower(): v for k, v in section_data["version"].items()
            }

        return mappings

    except json.JSONDecodeError as e:
        if not silent:
            print("Warning: Invalid JSON in mapping file: {}".format(e), file=sys.stderr)
        return mappings
    except Exception as e:
        if not silent:
            print("Warning: Error loading mapping file: {}".format(e), file=sys.stderr)
        return mappings


def apply_etrack_mapping(value, mapping_type, mappings):
    # type: (str, str, Dict[str, Dict[str, str]]) -> Tuple[str, bool]
    """
    Apply etrack value mapping if available.

    Args:
        value: Original etrack value
        mapping_type: 'component' or 'version'
        mappings: Loaded etrack_mapping dict

    Returns:
        Tuple of (mapped_value, was_mapped)
    """
    if not value:
        return value, False

    type_mappings = mappings.get(mapping_type, {})
    if not type_mappings:
        return value, False

    # Try exact match (case-insensitive)
    normalized = value.lower().strip()
    if normalized in type_mappings:
        return type_mappings[normalized], True

    return value, False


def extract_validated_etrack_id(client, issue_key, silent=False):
    # type: (JiraUpdateClient, str, bool) -> str
    """
    Extract and validate a single etrack ID from FI's linked etrack fields.

    Validates etrack format:
    - Whole number (e.g., 12345678)
    - ET prefix variants: ET12345678, ET-12345678, ET 12345678

    Checks 4 source fields:
    - EI = Etrack Incident (customfield_33802)
    - ER = Etrack Ref (customfield_36508)
    - RD = NBU R&D Ticket (named field)
    - INT = Etrack Incident (Internal) (named field)

    Raises:
        RuntimeError: If no etrack ID found, or multiple distinct IDs from different sources,
                      or invalid etrack format

    Returns:
        The single validated etrack ID string
    """
    import re

    # Import validate_etrack_format from etrack_integration
    try:
        from account_manager.etrack_integration import validate_etrack_format
    except ImportError:
        # Fallback: basic validation if import fails
        def validate_etrack_format(value):
            if not value:
                return (False, None, "Empty value")
            value_str = str(value).strip()
            # Handle float values from Jira numeric fields (e.g., 4223773.0)
            if re.match(r'^\d+\.0$', value_str):
                value_str = value_str[:-2]
            if re.match(r'^\d+$', value_str):
                return (True, value_str, None)
            et_match = re.match(r'^ET[\s\-]?(\d+)$', value_str, re.IGNORECASE)
            if et_match:
                return (True, et_match.group(1), None)
            return (False, None, "Value '{}' does not match etrack format".format(value_str))

    # Fetch issue (names already expanded by default)
    issue_data = client.get_issue(issue_key)
    fields = issue_data.get('fields', {})
    names = issue_data.get('names', {})

    # Build sources dict: etrack_id -> [source_codes]
    sources = {}  # type: Dict[str, List[str]]
    format_errors = []  # type: List[str]

    def add_ids(raw_value, source_name):
        # type: (Any, str) -> None
        if raw_value:
            raw_str = str(raw_value).strip()
            # Handle comma/space-separated multiple values
            for val in re.split(r'[,;\s]+', raw_str):
                val = val.strip()
                if not val:
                    continue
                is_valid, extracted, error_msg = validate_etrack_format(val)
                if is_valid and extracted:
                    # Filter small numbers (real etrack IDs are typically 6-7 digits)
                    if int(extracted) >= 100000:
                        if extracted not in sources:
                            sources[extracted] = []
                        if source_name not in sources[extracted]:
                            sources[extracted].append(source_name)
                elif error_msg and val:
                    # Value exists but doesn't match etrack criteria
                    format_errors.append("[{}] {}".format(source_name, error_msg))

    # Check known customfield IDs
    add_ids(fields.get("customfield_33802"), "EI")
    add_ids(fields.get("customfield_36508"), "ER")

    # Check by field name using names mapping
    name_patterns = {
        "nbu r&d ticket": "RD",
        "nbu r&d ticket:": "RD",
        "etrack incident (internal)": "INT",
        "etrack incident (internal):": "INT",
    }
    for key, mapped_name in names.items():
        if not isinstance(mapped_name, str):
            continue
        normalized = mapped_name.strip().casefold()
        for pattern, display_name in name_patterns.items():
            if normalized == pattern or normalized.startswith(pattern.rstrip(":")):
                add_ids(fields.get(key), display_name)
                break

    # Report format validation errors
    if format_errors and not silent:
        print("! Etrack format validation errors:")
        for err in format_errors:
            print("  - {}".format(err))

    # Validation
    if not sources:
        error_msg = "No valid etrack ID found in {}.\n".format(issue_key)
        error_msg += "Checked fields: Etrack Incident (EI), Etrack Ref (ER), "
        error_msg += "NBU R&D Ticket (RD), Etrack Incident Internal (INT)"
        if format_errors:
            error_msg += "\nFormat errors were found - see above."
        raise RuntimeError(error_msg)

    unique_ids = list(sources.keys())

    if len(unique_ids) == 1:
        etrack_id = unique_ids[0]
        source_list = sources[etrack_id]
        if not silent:
            print("Auto-detected etrack ID: {} (from: {})".format(etrack_id, ', '.join(source_list)))
        return etrack_id

    # Multiple distinct etrack IDs found
    details = []
    for eid, src_list in sorted(sources.items(), key=lambda x: int(x[0])):
        details.append("{} (from {})".format(eid, ', '.join(src_list)))

    raise RuntimeError(
        "Multiple distinct etrack IDs found in {} from different sources:\n  {}\n"
        "Please specify one explicitly with: -set <etrack_id>".format(
            issue_key, '\n  '.join(details)
        )
    )


def sync_etrack_to_jira(client, issue_key, etrack_id, sync_component=False, sync_affectsversion=False, silent=False, etrack_mappings=None):
    # type: (JiraUpdateClient, str, str, bool, bool, bool, Optional[Dict[str, Dict[str, str]]]) -> Tuple[Dict[str, Any], Optional[str]]
    """
    Fetch etrack info and return updates dict for mismatched fields only.

    Args:
        client: JiraUpdateClient instance
        issue_key: Jira issue key (e.g., FI-12345)
        etrack_id: Etrack incident ID to sync from
        sync_component: Sync component field
        sync_affectsversion: Sync affects version field
        silent: Suppress output messages
        etrack_mappings: Optional dict to transform etrack values before setting
                         Format: {"component": {"EtrackVal": "JiraVal"}, "version": {...}}

    Returns:
        Tuple of (field_updates_dict, sync_comment_string)
        - field_updates: Dict of fields that differ from Jira current values
        - sync_comment: Comment describing what was synced (None if nothing synced)
    """
    if not ETRACK_AVAILABLE:
        raise RuntimeError("Etrack integration not available. Check account_manager.etrack_integration module.")

    updates = {}  # type: Dict[str, Any]
    sync_actions = []  # type: List[str]

    # Fetch etrack info
    executor = EtrackExecutor()
    etrack_info = executor.get_etrack_info(etrack_id)

    if not etrack_info:
        raise RuntimeError("Could not fetch etrack info for incident: {}".format(etrack_id))

    # Validate etrack type is SERVICE_REQUEST
    et_type = getattr(etrack_info, 'type', None) or '-'
    if et_type != '-' and et_type.upper() != 'SERVICE_REQUEST':
        if not silent:
            print("! WARNING: Etrack {} type is '{}', expected SERVICE_REQUEST".format(etrack_id, et_type))

    # Fetch current Jira issue values
    issue_data = client.get_issue(issue_key)
    fields = issue_data.get('fields', {})

    # Extract current Jira values
    current_components = [c.get('name', '') for c in (fields.get('components') or [])]
    current_versions = [v.get('name', '') for v in (fields.get('versions') or [])]  # affects versions

    if not silent:
        print("\nEtrack {} info:".format(etrack_id))
        print("  Component: {}".format(etrack_info.component or '(none)'))
        print("  Version: {}".format(etrack_info.version or '(none)'))
        print("\nJira {} current values:".format(issue_key))
        print("  Components: {}".format(', '.join(current_components) if current_components else '(none)'))
        print("  Affects Version/s: {}".format(', '.join(current_versions) if current_versions else '(none)'))

    # Initialize mappings if not provided
    if etrack_mappings is None:
        etrack_mappings = {"component": {}, "version": {}}

    # Sync component if requested and value exists in etrack
    if sync_component:
        et_component = etrack_info.component
        if et_component:
            # Apply mapping if available
            mapped_component, was_mapped = apply_etrack_mapping(et_component, "component", etrack_mappings)
            target_component = mapped_component

            # Check if target component is already the only component in Jira
            if current_components == [target_component]:
                if not silent:
                    print("\n  -> Component '{}' already set in Jira (skipping)".format(target_component))
            else:
                # Replace all components with target component
                updates['components'] = target_component
                if was_mapped:
                    mapping_note = " (mapped from '{}')".format(et_component)
                else:
                    mapping_note = ""
                if current_components:
                    sync_actions.append("Component: {}{} (replaced {})".format(target_component, mapping_note, ', '.join(current_components)))
                    if not silent:
                        if was_mapped:
                            print("\n  -> Component '{}' (mapped from etrack '{}') will replace '{}' in Jira".format(
                                target_component, et_component, ', '.join(current_components)))
                        else:
                            print("\n  -> Component '{}' will replace '{}' in Jira".format(target_component, ', '.join(current_components)))
                else:
                    sync_actions.append("Component: {}{}".format(target_component, mapping_note))
                    if not silent:
                        if was_mapped:
                            print("\n  -> Component '{}' (mapped from etrack '{}') will be set in Jira".format(target_component, et_component))
                        else:
                            print("\n  -> Component '{}' will be set in Jira".format(target_component))
        else:
            if not silent:
                print("\n  -> Etrack component is empty (skipping)")

    # Sync affects version if requested and value exists in etrack
    if sync_affectsversion:
        et_version = etrack_info.version
        if et_version:
            # Apply mapping if available
            mapped_version, was_mapped = apply_etrack_mapping(et_version, "version", etrack_mappings)
            target_version = mapped_version

            # Check if target version is already the only version in Jira
            if current_versions == [target_version]:
                if not silent:
                    print("  -> Affects Version '{}' already set in Jira (skipping)".format(target_version))
            else:
                # Replace all versions with target version
                updates['affectsversions'] = target_version
                if was_mapped:
                    mapping_note = " (mapped from '{}')".format(et_version)
                else:
                    mapping_note = ""
                if current_versions:
                    sync_actions.append("Affects Version: {}{} (replaced {})".format(target_version, mapping_note, ', '.join(current_versions)))
                    if not silent:
                        if was_mapped:
                            print("  -> Affects Version '{}' (mapped from etrack '{}') will replace '{}' in Jira".format(
                                target_version, et_version, ', '.join(current_versions)))
                        else:
                            print("  -> Affects Version '{}' will replace '{}' in Jira".format(target_version, ', '.join(current_versions)))
                else:
                    sync_actions.append("Affects Version: {}{}".format(target_version, mapping_note))
                    if not silent:
                        if was_mapped:
                            print("  -> Affects Version '{}' (mapped from etrack '{}') will be set in Jira".format(target_version, et_version))
                        else:
                            print("  -> Affects Version '{}' will be set in Jira".format(target_version))
        else:
            if not silent:
                print("  -> Etrack version is empty (skipping)")

    # Build sync comment if there were any updates
    sync_comment = None  # type: Optional[str]
    if sync_actions:
        sync_comment = "Synced from Etrack {}: {}".format(etrack_id, ', '.join(sync_actions))

    return (updates, sync_comment)


def perform_update(client, issue_key, updates, comment=None, dry_run=False, silent=False, potential_comment=None):
    # type: (JiraUpdateClient, str, Dict[str, Any], Optional[str], bool, bool, Optional[str]) -> bool
    """
    Perform the actual update.
    updates: dict of {field_name: value}
    potential_comment: For dry-run only - show what comment would be added if -m was passed
    """
    if not updates and not comment:
        print("Nothing to update.", file=sys.stderr)
        return False

    # Build the fields payload
    fields_data = {}  # type: Dict[str, Any]

    for field_name, value in updates.items():
        try:
            canonical, defn = resolve_field_name(field_name)
            jira_key, formatted = format_field_value(client, issue_key, canonical, value, defn)
            fields_data[jira_key] = formatted
            if not silent:
                print("  {} ({}) = {}".format(canonical, jira_key, formatted))
        except ValueError as e:
            print("Error: {}".format(e), file=sys.stderr)
            return False

    if dry_run:
        print("\n[DRY RUN] Would update {} with:".format(issue_key))
        print(json.dumps({"fields": fields_data}, indent=2))
        if comment:
            print("\n[DRY RUN] Would add comment:")
            print("  {}".format(comment[:200]))
        elif potential_comment:
            print("\n[DRY RUN] Potential comment (use -m to add):")
            print("  {}".format(potential_comment[:200]))
        return True

    # Perform update
    success = True
    if fields_data:
        try:
            client.update_issue(issue_key, fields_data)
            if not silent:
                print("\n[OK] Updated {} successfully".format(issue_key))
        except RuntimeError as e:
            print("[FAIL] Update failed: {}".format(e), file=sys.stderr)
            success = False

    # Add comment if provided
    if comment and success:
        try:
            client.add_comment(issue_key, comment)
            if not silent:
                print("[OK] Comment added")
        except RuntimeError as e:
            print("[FAIL] Failed to add comment: {}".format(e), file=sys.stderr)
            success = False

    return success


def perform_transition(client, issue_key, target_status, resolution=None, comment=None, dry_run=False):
    # type: (JiraUpdateClient, str, str, Optional[str], Optional[str], bool) -> bool
    """Perform a status transition."""
    transitions = client.get_transitions(issue_key)

    # Find matching transition
    target_lower = target_status.strip().lower()
    matched = None
    for t in transitions:
        t_name = t.get('name', '').lower()
        to_status = t.get('to', {}).get('name', '').lower()
        if t_name == target_lower or to_status == target_lower:
            matched = t
            break

    if not matched:
        available = [t.get('name', '') for t in transitions]
        print("Transition '{}' not available. Available: {}".format(
            target_status, ", ".join(available)), file=sys.stderr)
        return False

    transition_id = matched.get('id')
    fields_data = None

    # Handle resolution if provided
    if resolution:
        # Check if resolution field is available in this transition
        trans_fields = matched.get('fields', {})
        if 'resolution' in trans_fields:
            fields_data = {'resolution': {'name': resolution}}

    if dry_run:
        print("[DRY RUN] Would transition {} via '{}' (id: {})".format(
            issue_key, matched.get('name'), transition_id))
        if fields_data:
            print("  With fields: {}".format(json.dumps(fields_data)))
        if comment:
            print("  With comment: {}".format(comment[:100]))
        return True

    try:
        client.do_transition(issue_key, transition_id, fields_data, comment)
        print("[OK] Transitioned {} to '{}'".format(issue_key, matched.get('to', {}).get('name', target_status)))
        return True
    except RuntimeError as e:
        print("[FAIL] Transition failed: {}".format(e), file=sys.stderr)
        return False


class ShortLongHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom formatter that shows both short and long options in usage.

    Compatible with Python 3.9 (_format_actions_usage) and
    Python 3.14+ (_get_actions_usage_parts).
    """

    def _build_usage_parts(self, actions, return_pos_start=False):
        """Build usage parts showing both short and long options.

        If return_pos_start is True, returns (parts, pos_start) tuple
        where pos_start is the index where positionals begin.
        """
        opt_parts = []
        pos_parts = []

        for action in actions:
            if action.option_strings:
                opts = action.option_strings
                if len(opts) == 2:
                    # Has both short and long - show as [-s/--summary VALUE]
                    # Short options start with single -, long with --
                    # If both start with --, pick shorter one first
                    if opts[0].startswith('--') and opts[1].startswith('--'):
                        # Both are long options, shorter one first
                        if len(opts[0]) <= len(opts[1]):
                            short, long_opt = opts[0], opts[1]
                        else:
                            short, long_opt = opts[1], opts[0]
                    elif opts[0].startswith('--'):
                        short, long_opt = opts[1], opts[0]
                    else:
                        short, long_opt = opts[0], opts[1]
                    if action.nargs == 0 or action.const is not None:
                        # Flag (store_true/store_false)
                        opt_parts.append('[{}/{}]'.format(short, long_opt))
                    else:
                        metavar = action.metavar or action.dest.upper()
                        opt_parts.append('[{}/{} {}]'.format(short, long_opt, metavar))
                else:
                    # Only one option
                    opt = opts[0]
                    if action.nargs == 0 or action.const is not None:
                        opt_parts.append('[{}]'.format(opt))
                    else:
                        metavar = action.metavar or action.dest.upper()
                        opt_parts.append('[{} {}]'.format(opt, metavar))
            else:
                # Positional argument
                if action.nargs == '?':
                    pos_parts.append('[{}]'.format(action.dest))
                else:
                    pos_parts.append(action.dest)

        parts = opt_parts + pos_parts
        if return_pos_start:
            return parts, len(opt_parts)
        return parts

    # Python 3.9 and earlier
    def _format_actions_usage(self, actions, groups):
        return ' '.join(self._build_usage_parts(actions))

    # Python 3.14+ (renamed method, returns tuple (parts, pos_start))
    def _get_actions_usage_parts(self, actions, groups):
        return self._build_usage_parts(actions, return_pos_start=True)


def main():
    parser = argparse.ArgumentParser(
        description="Update Jira issue fields (FI, PVM, NBU, etc.)",
        formatter_class=ShortLongHelpFormatter,
        epilog="""
Examples:
  %(prog)s FI-12345 -s "New summary"
  %(prog)s PVM-5678 -p High -a john.doe --comment "Assigned to John"
  %(prog)s NBU-9999 --update '{"summary": "Title", "priority": "High"}'
  %(prog)s FI-12345 --transition "In Progress"
  %(prog)s FI-12345 --cs "Working on fix" --ns "Deploy next week"
  %(prog)s FI-12345 --ar "Waiting for customer" --comment "Customer not responding"
  %(prog)s FI-12345 -s "Test" --dry-run
  %(prog)s FI-12345 -lo priority
  %(prog)s FI-12345 -lt
  %(prog)s -lf

  # Etrack sync examples:
  %(prog)s FI-12345 -set 12345678 -sc             # Sync component with explicit etrack ID
  %(prog)s FI-12345 -set -sc                      # Auto-fetch etrack from FI linked fields
  %(prog)s FI-12345 -set -sc -sav                 # Auto-fetch and sync both component & version
  %(prog)s FI-12345 -set -sc -m                   # Auto-fetch, sync with auto-generated comment
  %(prog)s FI-12345 -set 12345678 -sc -m "Note"   # Explicit ID, sync with custom + auto comment
  %(prog)s FI-12345 -set -sc --dry-run            # Preview auto-fetch sync (shows potential comment)
  %(prog)s FI-12345 -set -sc -mf mapping.json     # Sync with etrack value mapping
""")

    parser.add_argument('issue_key', nargs='?', help='Issue key (e.g., FI-12345, PVM-5678, NBU-9999)')

    # List modes
    parser.add_argument('--list-fields', '-lf', action='store_true',
                        help='List all available fields')
    parser.add_argument('--list-transitions', '-lt', action='store_true',
                        help='List available transitions for issue')
    parser.add_argument('--list-options', '-lo', type=str, metavar='FIELD',
                        help='List allowed values for a dropdown field')

    # Single field updates (short options)
    field_group = parser.add_argument_group('Field Updates (short options)')
    field_group.add_argument('-s', '--summary', type=str, help='Summary')
    field_group.add_argument('-d', '--description', type=str, help='Description')
    field_group.add_argument('-p', '--priority', type=str, help='Priority')
    field_group.add_argument('-a', '--assignee', type=str, help='Assignee username')
    field_group.add_argument('-c', '--components', type=str, help='Components (comma-separated)')
    field_group.add_argument('-l', '--labels', type=str, help='Labels (comma-separated)')
    field_group.add_argument('--fv', '--fixversions', type=str, dest='fixversions', help='Fix versions')
    field_group.add_argument('--av', '--affectsversions', type=str, dest='affectsversions', help='Affects versions')

    # FI-specific fields
    fi_group = parser.add_argument_group('FI Custom Fields')
    fi_group.add_argument('--cs', '--currentstatus', type=str, dest='currentstatus', help='Current Status')
    fi_group.add_argument('--ns', '--nextsteps', type=str, dest='nextsteps', help='Next Steps')
    fi_group.add_argument('--ar', '--agedreason', type=str, dest='agedreason', help='Aged Reason')
    fi_group.add_argument('--bu', '--businessunit', type=str, dest='businessunit', help='Business Unit')
    fi_group.add_argument('--sv', '--severity', type=str, dest='severity', help='Severity')
    fi_group.add_argument('--cap', '--capinvolvement', type=str, dest='capinvolvement', help='CAP Involvement')
    fi_group.add_argument('--cst', '--casestatus', type=str, dest='casestatus', help='Case Status')
    fi_group.add_argument('--et', '--etrackincident', type=str, dest='etrackincident', help='Etrack Incident')
    fi_group.add_argument('--er', '--etrackref', type=str, dest='etrackref', help='Etrack Ref')
    fi_group.add_argument('--cid', '--caseid', type=str, dest='caseid', help='Case# (SFDC)')
    fi_group.add_argument('--sl', '--slack', type=str, dest='slack', help='Slack channel URL')
    fi_group.add_argument('--am', '--assigneemanager', type=str, dest='assigneemanager', help='Assignee Manager')
    fi_group.add_argument('--rca', '--fircacategory', type=str, dest='fircacategory', help='FI RCA Category')
    fi_group.add_argument('--at', '--actiontaken', type=str, dest='actiontaken', help='Action Taken')
    fi_group.add_argument('--sol', '--solution', type=str, dest='solution', help='Solution')
    fi_group.add_argument('--ps', '--progressstatus', type=str, dest='progressstatus', help='Progress Status')

    # Etrack sync options
    sync_group = parser.add_argument_group('Etrack Sync Options')
    sync_group.add_argument('-set', '--sync-with-et', nargs='?', const='auto', dest='sync_with_et', metavar='ETRACK_ID',
                            help='Etrack ID to sync from. If omitted, auto-fetch from FI linked etracks (requires -sc or -sav)')
    sync_group.add_argument('-sc', '--sync-component', action='store_true', dest='sync_component',
                            help='Sync component from etrack to Jira (requires -set)')
    sync_group.add_argument('-sav', '--sync-affectsversion', action='store_true', dest='sync_affectsversion',
                            help='Sync affects version from etrack to Jira (requires -set)')
    sync_group.add_argument('-mf', '--mapping-file', type=str, dest='mapping_file', metavar='FILE',
                            help='JSON mapping file with etrack_mapping section to transform etrack values')

    # JSON update
    parser.add_argument('--update', '-u', type=str, metavar='JSON',
                        help='JSON object with field updates: \'{"field": "value", ...}\'')

    # Transition
    parser.add_argument('--transition', '-t', type=str, metavar='STATUS',
                        help='Transition to a new status')
    parser.add_argument('--resolution', '-r', type=str,
                        help='Resolution (for closing transitions)')

    # Comment (explicit, separate from field updates)
    parser.add_argument('--comment', '-m', type=str, nargs='?', const='',
                        help='Add a comment. With -set: pass -m alone for auto-generated sync comment, or -m "text" for custom')

    # Options
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Show what would be updated without making changes')
    parser.add_argument('--silent', '-q', action='store_true',
                        help='Suppress success messages')
    parser.add_argument('--no-notify', action='store_true',
                        help='Do not send email notifications for this update')

    args = parser.parse_args()

    # Handle list-fields (no issue required)
    if args.list_fields:
        list_available_fields()
        return 0

    # Require issue key for other operations
    if not args.issue_key:
        parser.error("issue_key is required")

    issue_key = args.issue_key.upper()

    # Validate etrack sync options: -set is required for -sc or -sav
    if (args.sync_component or args.sync_affectsversion) and not args.sync_with_et:
        parser.error("-set/--sync-with-et is required when using -sc or -sav")

    # Initialize client
    try:
        client = JiraUpdateClient()
    except RuntimeError as e:
        print("Error: {}".format(e), file=sys.stderr)
        return 1

    # Handle list-transitions
    if args.list_transitions:
        show_transitions(client, issue_key)
        return 0

    # Handle list-options
    if args.list_options:
        show_field_options(client, issue_key, args.list_options)
        return 0

    # Handle transition
    if args.transition:
        success = perform_transition(
            client, issue_key, args.transition,
            resolution=args.resolution,
            comment=args.comment,
            dry_run=args.dry_run
        )
        return 0 if success else 1

    # Collect field updates
    updates = {}  # type: Dict[str, Any]
    sync_comment = None  # type: Optional[str]

    # Handle etrack sync if requested
    if args.sync_with_et and (args.sync_component or args.sync_affectsversion):
        # Resolve etrack ID (explicit or auto-fetch)
        etrack_id_to_use = args.sync_with_et
        if etrack_id_to_use == 'auto':
            try:
                etrack_id_to_use = extract_validated_etrack_id(client, issue_key, silent=args.silent)
            except RuntimeError as e:
                print("Error: {}".format(e), file=sys.stderr)
                return 1

        # Load etrack mappings if specified
        etrack_mappings = None  # type: Optional[Dict[str, Dict[str, str]]]
        if args.mapping_file:
            etrack_mappings = load_etrack_mappings(args.mapping_file, silent=args.silent)
            if etrack_mappings and (etrack_mappings.get('component') or etrack_mappings.get('version')):
                if not args.silent:
                    print("Loaded etrack mappings: {} component, {} version".format(
                        len(etrack_mappings.get('component', {})),
                        len(etrack_mappings.get('version', {}))
                    ))

        try:
            sync_updates, sync_comment = sync_etrack_to_jira(
                client, issue_key, etrack_id_to_use,
                sync_component=args.sync_component,
                sync_affectsversion=args.sync_affectsversion,
                silent=args.silent,
                etrack_mappings=etrack_mappings
            )
            updates.update(sync_updates)
        except RuntimeError as e:
            print("Error: {}".format(e), file=sys.stderr)
            return 1

    # Combine user comment with sync comment (only if -m is passed)
    final_comment = None  # type: Optional[str]
    if args.comment is not None:  # -m was passed (could be empty string or with value)
        if args.comment == '' and sync_comment:
            # -m passed without value: use auto-generated sync comment
            final_comment = sync_comment
        elif args.comment and sync_comment:
            # -m passed with value and sync_comment exists: combine them
            final_comment = "{}\n\n{}".format(args.comment, sync_comment)
        elif args.comment:
            # -m passed with value, no sync_comment
            final_comment = args.comment
        # else: -m passed without value but no sync_comment -> final_comment stays None

    # Add updates from command-line arguments
    field_args = [
        'summary', 'description', 'priority', 'assignee', 'components', 'labels',
        'fixversions', 'affectsversions', 'currentstatus', 'nextsteps', 'agedreason',
        'businessunit', 'severity', 'capinvolvement', 'casestatus', 'etrackincident',
        'etrackref', 'caseid', 'slack', 'assigneemanager', 'fircacategory',
        'actiontaken', 'solution', 'progressstatus',
    ]

    for field in field_args:
        value = getattr(args, field, None)
        if value is not None:
            updates[field] = value

    # Add updates from JSON
    if args.update:
        try:
            json_updates = parse_json_update(args.update)
            updates.update(json_updates)
        except ValueError as e:
            print("Error: {}".format(e), file=sys.stderr)
            return 1

    # Check if we have anything to do
    if not updates and not final_comment:
        print("No updates specified. Use --help for usage.", file=sys.stderr)
        return 1

    # Show what we're updating
    if not args.silent:
        print("\nUpdating {}:".format(issue_key))

    # Perform update
    success = perform_update(
        client, issue_key, updates,
        comment=final_comment,
        dry_run=args.dry_run,
        silent=args.silent,
        potential_comment=sync_comment if not final_comment else None
    )

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
