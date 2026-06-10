#!/usr/bin/env python3
"""
FI Validator - Validate FI tickets against group-based version/component rules.

Validates FI tickets using group-based configuration:
- Components belong to groups (e.g., NetBackup_Core, ALTA_IT)
- Each group has valid versions
- A component's version must be in one of its group's valid versions

Input Methods:
- JQL query via -j/--jql
- File with FI IDs via -f/--file
- Stdin (pipe FI IDs or JQL)

Output:
- Console table with validation results
- Optional CSV export via -o/--output

Configuration File Format (INI-style):
    [GroupName:components]
    component1  # count
    component2

    [GroupName:versions]
    10.1.1  # count
    10.2.0.1

    [Unknown:components]
    # New/unassigned components go here

    [Unknown:versions]
    # New/unassigned versions go here

Environment variables expected:
- JIRA_SERVER_NAME
- JIRA_ACC_TOKEN

Examples:
    # Build groups config from FI data (creates Unknown groups)
    j.fi.validate.py -j "project = FI AND 'Business Unit' = NBU" \\
        --build-groups groups.ini

    # Update existing config (merges, new items go to Unknown)
    j.fi.validate.py -j "project = FI" --build-groups groups.ini

    # Validate using groups config
    j.fi.validate.py -j "project = FI" -g groups.ini

    # Show only invalid FIs
    j.fi.validate.py -j "project = FI" -g groups.ini --errors-only

    # Export results to CSV
    j.fi.validate.py -j "project = FI" -g groups.ini -o report.csv
"""

from __future__ import print_function

import argparse
import csv
import os
import re
import sys
import time
from collections import OrderedDict
from configparser import ConfigParser
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure console output is UTF-8 safe
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
else:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
from dotenv import load_dotenv

try:
    from prettytable import PrettyTable
except ImportError:
    PrettyTable = None

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None


# ---------------------------------------------------------------------------
# Configuration and Constants
# ---------------------------------------------------------------------------

load_dotenv()

JIRA_SERVER = os.getenv('JIRA_SERVER_NAME')
JIRA_TOKEN = os.getenv('JIRA_ACC_TOKEN')
JIRA_BASE_URL = f"https://{JIRA_SERVER}" if JIRA_SERVER else None

# FI ID pattern
FI_PATTERN = re.compile(r'^FI-\d+$')

# Invalid values to filter out in discovery mode
INVALID_VALUES = {
    '', '-', 'n/a', 'na', 'none', 'null', 'tbd', 'unknown', 'unassigned',
    'not set', 'not specified', 'not applicable', 'not available',
}

# Aging buckets (days)
AGING_BUCKETS = [
    (7, "< 1 week"),
    (14, "1-2 weeks"),
    (30, "2-4 weeks"),
    (60, "1-2 months"),
    (90, "2-3 months"),
    (180, "3-6 months"),
    (365, "6-12 months"),
    (None, "> 1 year"),
]

# Field display order
OUTPUT_COLUMNS = [
    'Key',
    'Summary',
    'Priority',
    'Assignee',
    'Assignee Manager',
    'Manager Groups',
    'Case Status',
    'Status',
    'Created',
    'Updated',
    'Days Since Update',
    'Age Bucket',
    'Component/s',
    'Affects Version/s',
    'Business Unit',
    'Resolution',
    'Linked Etracks',
    'Aged Reason',
    'Validation Notes',
]


# ---------------------------------------------------------------------------
# Jira Client
# ---------------------------------------------------------------------------

class JiraClient:
    """Client for interacting with Jira REST API."""

    def __init__(self, base_url: str, token: str, timeout: int = 30):
        self.base_url = base_url
        self.token = token
        self.timeout = timeout
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Connection': 'close',
        }
        self._field_cache: Optional[Dict[str, Dict]] = None
        self._user_groups_cache: Dict[str, List[str]] = {}  # username -> groups

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
                            operation: str = "Request", max_retries: int = 5) -> requests.Response:
        """Make HTTP request with retry logic for transient failures."""
        retryable_http = {429, 500, 502, 503, 504}
        last_exc = None

        for attempt in range(1, max_retries + 1):
            session = requests.Session()
            try:
                if method.upper() == 'GET':
                    response = session.get(url, headers=self.headers, params=params, timeout=self.timeout)
                else:
                    response = session.request(method, url, headers=self.headers, params=params, timeout=self.timeout)

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
                    requests.exceptions.ConnectTimeout,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.Timeout) as exc:
                last_exc = exc
                if attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    print(f"{operation}: network error (attempt {attempt}/{max_retries}), "
                          f"retrying in {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                raise

            finally:
                session.close()

        if last_exc:
            raise last_exc
        raise RuntimeError(f"{operation} failed after retries")

    def get_all_fields(self) -> Dict[str, Dict]:
        """Fetch all Jira fields and return name-to-info mapping."""
        if self._field_cache is not None:
            return self._field_cache

        url = f"{self.base_url}/rest/api/2/field"
        response = self._request_with_retry('GET', url, operation='Field discovery')
        response.raise_for_status()

        self._field_cache = {}
        for field in response.json():
            name_lower = field['name'].lower()
            self._field_cache[name_lower] = {
                'id': field['id'],
                'name': field['name'],
                'custom': field.get('custom', False),
            }
        return self._field_cache

    def get_field_id(self, field_name: str) -> Optional[str]:
        """Get field ID by display name (case-insensitive)."""
        fields = self.get_all_fields()
        field_info = fields.get(field_name.lower().strip())
        return field_info['id'] if field_info else None

    def get_field_id_by_candidates(self, candidates: List[str]) -> Optional[str]:
        """Get field ID from first matching candidate name."""
        for name in candidates:
            field_id = self.get_field_id(name)
            if field_id:
                return field_id
        return None

    def search_issues(self, jql: str, fields: List[str], max_results: int = 0) -> List[Dict]:
        """Search issues using JQL query."""
        url = f"{self.base_url}/rest/api/2/search"
        all_issues = []
        seen_keys = set()  # Track seen issue keys to prevent duplicates
        start_at = 0
        batch_size = 100

        while True:
            params = {
                'jql': jql,
                'startAt': start_at,
                'maxResults': batch_size if max_results == 0 else min(batch_size, max_results - len(all_issues)),
                'fields': ','.join(fields),
                'expand': 'names',
            }

            response = self._request_with_retry('GET', url, params=params, operation='Issue search')
            response.raise_for_status()

            payload = response.json()
            issues = payload.get('issues', [])
            total = payload.get('total', 0)

            if not issues:
                break

            # Deduplicate issues by key
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

    def get_issue(self, issue_key: str, fields: List[str]) -> Optional[Dict]:
        """Fetch a single issue by key."""
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        params = {
            'fields': ','.join(fields),
            'expand': 'names',
        }

        try:
            response = self._request_with_retry('GET', url, params=params, operation=f'Fetch {issue_key}')
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    def get_user_groups(self, username: str, filter_patterns: List[str] = None) -> List[str]:
        """
        Get groups for a user. Results are cached.

        Args:
            username: Jira username
            filter_patterns: Optional list of glob patterns to filter groups (e.g., ['*-managers', '*-directors'])

        Returns:
            List of group names (filtered if patterns provided)
        """
        if not username:
            return []

        # Check cache first
        if username in self._user_groups_cache:
            groups = self._user_groups_cache[username]
        else:
            url = f"{self.base_url}/rest/api/2/user"
            params = {
                'username': username,
                'expand': 'groups',
            }

            try:
                response = self._request_with_retry('GET', url, params=params, operation=f'User groups {username}')
                if response.status_code == 404:
                    self._user_groups_cache[username] = []
                    return []
                response.raise_for_status()

                user_data = response.json()
                groups_data = user_data.get('groups', {}).get('items', [])
                groups = [g.get('name', '') for g in groups_data if g.get('name')]
                self._user_groups_cache[username] = groups

            except Exception as e:
                print(f"Warning: Could not fetch groups for {username}: {e}", file=sys.stderr)
                self._user_groups_cache[username] = []
                return []

        # Apply filter patterns if provided
        if filter_patterns and groups:
            import fnmatch
            filtered = []
            for g in groups:
                for pattern in filter_patterns:
                    if fnmatch.fnmatch(g.lower(), pattern.lower()):
                        filtered.append(g)
                        break
            return filtered

        return groups

    def get_issues_batch(self, issue_keys: List[str], fields: List[str]) -> Tuple[List[Dict], List[str]]:
        """Fetch multiple issues by keys. Returns (found_issues, not_found_keys)."""
        if not issue_keys:
            return [], []

        # Batch fetch using JQL IN clause
        unique_keys = sorted(set(issue_keys))
        found_issues = []
        not_found = set(unique_keys)

        # Process in chunks to avoid JQL length limits
        chunk_size = 50
        for i in range(0, len(unique_keys), chunk_size):
            chunk = unique_keys[i:i + chunk_size]
            jql = f"key in ({', '.join(chunk)})"

            try:
                issues = self.search_issues(jql, fields)
                for issue in issues:
                    key = issue.get('key')
                    if key:
                        found_issues.append(issue)
                        not_found.discard(key)
            except Exception as e:
                print(f"Warning: Error fetching batch: {e}", file=sys.stderr)
                # Fall back to individual fetches for this chunk
                for key in chunk:
                    try:
                        issue = self.get_issue(key, fields)
                        if issue:
                            found_issues.append(issue)
                            not_found.discard(key)
                    except Exception as ie:
                        print(f"Warning: Could not fetch {key}: {ie}", file=sys.stderr)

        return found_issues, sorted(not_found)


# ---------------------------------------------------------------------------
# Configuration Loading
# ---------------------------------------------------------------------------

def load_file_lines(filepath: str) -> List[str]:
    """
    Load non-empty, stripped lines from a file.

    Supports:
    - Full line comments: lines starting with #
    - Inline comments: anything after # is stripped

    Example input (discovery file format):
        # Header comment
        WORKLOADS_CLOUD_SNAPSHOT  # 34
        WORKLOADS_DB_AGENT_SQL  # 12
        10.5.0.1  # 45

    Returns: ['WORKLOADS_CLOUD_SNAPSHOT', 'WORKLOADS_DB_AGENT_SQL', '10.5.0.1']
    """
    if not filepath:
        return []
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Configuration file not found: {filepath}")

    lines = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            # Skip empty lines and full-line comments
            if not stripped or stripped.startswith('#'):
                continue
            # Strip inline comments (anything after #)
            if '#' in stripped:
                stripped = stripped.split('#', 1)[0].strip()
            # Add if still has content after stripping
            if stripped:
                lines.append(stripped)
    return lines


# ---------------------------------------------------------------------------
# Group-Based Configuration
# ---------------------------------------------------------------------------

class GroupConfig:
    """
    Group-based validation configuration.

    Config file format (INI-style):
        [GroupName:components]
        component1  # count
        component2

        [GroupName:versions]
        10.1.1  # count
        10.2.0.1

        [Unknown:components]
        # New/unassigned components

        [Unknown:versions]
        # New/unassigned versions
    """

    def __init__(self):
        # group_name -> set of components (lowercase for comparison)
        self.group_components: Dict[str, Set[str]] = {}
        # group_name -> set of versions
        self.group_versions: Dict[str, Set[str]] = {}
        # component (lowercase) -> list of group names
        self.component_to_groups: Dict[str, List[str]] = {}
        # version -> list of group names
        self.version_to_groups: Dict[str, List[str]] = {}
        # For preserving counts during merge
        self.component_counts: Dict[str, int] = {}
        self.version_counts: Dict[str, int] = {}

    @classmethod
    def load(cls, filepath: str) -> 'GroupConfig':
        """Load configuration from INI file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Configuration file not found: {filepath}")

        config = cls()
        current_section = None
        current_group = None
        current_type = None  # 'components' or 'versions'

        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                stripped = line.strip()

                # Skip empty lines and full comments
                if not stripped or stripped.startswith('#'):
                    continue

                # Section header: [GroupName:type]
                if stripped.startswith('[') and stripped.endswith(']'):
                    section = stripped[1:-1]
                    if ':' not in section:
                        print(f"Warning: Invalid section '{section}' at line {line_num}, expected [GroupName:components] or [GroupName:versions]", file=sys.stderr)
                        current_section = None
                        continue

                    group_name, section_type = section.rsplit(':', 1)
                    group_name = group_name.strip()
                    section_type = section_type.strip().lower()

                    if section_type not in ('components', 'versions'):
                        print(f"Warning: Invalid section type '{section_type}' at line {line_num}, expected 'components' or 'versions'", file=sys.stderr)
                        current_section = None
                        continue

                    current_group = group_name
                    current_type = section_type

                    # Initialize group sets if needed
                    if current_group not in config.group_components:
                        config.group_components[current_group] = set()
                    if current_group not in config.group_versions:
                        config.group_versions[current_group] = set()
                    continue

                # Value line
                if current_group and current_type:
                    # Parse value and optional count comment
                    value = stripped
                    count = 0
                    if '#' in stripped:
                        parts = stripped.split('#', 1)
                        value = parts[0].strip()
                        try:
                            count = int(parts[1].strip())
                        except ValueError:
                            pass  # Non-numeric comment

                    if not value:
                        continue

                    if current_type == 'components':
                        value_lower = value.lower()
                        config.group_components[current_group].add(value_lower)
                        config.component_counts[value_lower] = count
                        # Build reverse mapping
                        if value_lower not in config.component_to_groups:
                            config.component_to_groups[value_lower] = []
                        if current_group not in config.component_to_groups[value_lower]:
                            config.component_to_groups[value_lower].append(current_group)
                    else:  # versions
                        config.group_versions[current_group].add(value)
                        config.version_counts[value] = count
                        # Build reverse mapping
                        if value not in config.version_to_groups:
                            config.version_to_groups[value] = []
                        if current_group not in config.version_to_groups[value]:
                            config.version_to_groups[value].append(current_group)

        # Summary
        num_groups = len(set(config.group_components.keys()) | set(config.group_versions.keys()))
        num_components = len(config.component_to_groups)
        num_versions = len(config.version_to_groups)
        print(f"Loaded {num_groups} groups with {num_components} components and {num_versions} versions from {filepath}", file=sys.stderr)

        return config

    def get_groups_for_component(self, component: str) -> List[str]:
        """Get list of groups that contain this component."""
        return self.component_to_groups.get(component.lower(), [])

    def get_valid_versions_for_component(self, component: str) -> Set[str]:
        """Get all valid versions for a component (union of all its groups' versions)."""
        groups = self.get_groups_for_component(component)
        versions = set()
        for group in groups:
            versions.update(self.group_versions.get(group, set()))
        return versions

    def is_component_known(self, component: str) -> bool:
        """Check if component exists in any group (including Unknown)."""
        return component.lower() in self.component_to_groups

    def is_component_in_unknown(self, component: str) -> bool:
        """Check if component is only in Unknown group."""
        groups = self.get_groups_for_component(component)
        return groups == ['Unknown']


def write_groups_config(filepath: str, groups_data: Dict[str, Dict[str, Dict[str, int]]],
                        existing_config: Optional[GroupConfig] = None):
    """
    Write groups configuration to INI file.

    Args:
        filepath: Output file path
        groups_data: Dict of {group_name: {'components': {comp: count}, 'versions': {ver: count}}}
        existing_config: If provided, preserve existing group assignments
    """
    # Merge with existing if provided
    if existing_config:
        # Find items not in any existing group -> add to Unknown
        all_existing_components = set()
        all_existing_versions = set()
        for group, comps in existing_config.group_components.items():
            all_existing_components.update(comps)
        for group, vers in existing_config.group_versions.items():
            all_existing_versions.update(vers)

        # Get new discovered items
        new_components = {}
        new_versions = {}
        for group, data in groups_data.items():
            for comp, count in data.get('components', {}).items():
                comp_lower = comp.lower()
                if comp_lower not in all_existing_components:
                    new_components[comp] = new_components.get(comp, 0) + count
            for ver, count in data.get('versions', {}).items():
                if ver not in all_existing_versions:
                    new_versions[ver] = new_versions.get(ver, 0) + count

        # Build output: existing groups + Unknown with new items
        output_groups = OrderedDict()

        # Copy existing groups with updated counts
        for group in sorted(existing_config.group_components.keys()):
            if group == 'Unknown':
                continue  # Handle Unknown last
            output_groups[group] = {
                'components': {},
                'versions': {}
            }
            for comp in sorted(existing_config.group_components.get(group, set())):
                # Use new count if available, else existing
                new_count = 0
                for g, d in groups_data.items():
                    for c, cnt in d.get('components', {}).items():
                        if c.lower() == comp:
                            new_count = cnt
                            break
                output_groups[group]['components'][comp] = new_count or existing_config.component_counts.get(comp, 0)

            for ver in sort_versions(list(existing_config.group_versions.get(group, set()))):
                new_count = 0
                for g, d in groups_data.items():
                    new_count = d.get('versions', {}).get(ver, 0)
                    if new_count:
                        break
                output_groups[group]['versions'][ver] = new_count or existing_config.version_counts.get(ver, 0)

        # Add Unknown group with new + existing unknown items
        existing_unknown_comps = existing_config.group_components.get('Unknown', set())
        existing_unknown_vers = existing_config.group_versions.get('Unknown', set())

        unknown_comps = {}
        unknown_vers = {}

        # Add existing unknown items
        for comp in existing_unknown_comps:
            unknown_comps[comp] = existing_config.component_counts.get(comp, 0)
        for ver in existing_unknown_vers:
            unknown_vers[ver] = existing_config.version_counts.get(ver, 0)

        # Add new items
        for comp, count in new_components.items():
            unknown_comps[comp.lower()] = count
        for ver, count in new_versions.items():
            unknown_vers[ver] = count

        if unknown_comps or unknown_vers:
            output_groups['Unknown'] = {
                'components': unknown_comps,
                'versions': unknown_vers
            }

        groups_data = output_groups

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# FI Validation Groups Configuration\n")
        f.write("# Format: [GroupName:components] and [GroupName:versions]\n")
        f.write("# Move items from [Unknown] to appropriate groups\n")
        f.write("#\n\n")

        for group_name, data in groups_data.items():
            components = data.get('components', {})
            versions = data.get('versions', {})

            if components:
                f.write(f"[{group_name}:components]\n")
                for comp in sorted(components.keys(), key=str.lower):
                    count = components[comp]
                    if count:
                        f.write(f"{comp}  # {count}\n")
                    else:
                        f.write(f"{comp}\n")
                f.write("\n")

            if versions:
                f.write(f"[{group_name}:versions]\n")
                for ver in sort_versions(list(versions.keys())):
                    count = versions[ver]
                    if count:
                        f.write(f"{ver}  # {count}\n")
                    else:
                        f.write(f"{ver}\n")
                f.write("\n")

    print(f"Wrote groups configuration to {filepath}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Field Extraction Utilities
# ---------------------------------------------------------------------------

def extract_field_value(field_value: Any) -> str:
    """Extract display value from Jira field."""
    if field_value is None:
        return "-"

    if isinstance(field_value, str):
        return field_value.strip() if field_value.strip() else "-"

    if isinstance(field_value, dict):
        for key in ('value', 'displayName', 'name', 'key'):
            if field_value.get(key):
                return str(field_value[key])
        return "-"

    if isinstance(field_value, list):
        values = []
        for item in field_value:
            val = extract_field_value(item)
            if val and val != "-":
                values.append(val)
        return "; ".join(values) if values else "-"

    return str(field_value)


def extract_email_address(field_value: Any, email_domain: Optional[str] = None) -> Optional[str]:
    """
    Extract email address from Jira user field.

    Args:
        field_value: Jira user field (dict with emailAddress, name, key, displayName)
        email_domain: If provided, construct email from username@domain when no email found

    Returns:
        Email address string or None
    """
    if field_value is None:
        return None

    if isinstance(field_value, dict):
        # 1. Prefer explicit emailAddress field
        email = field_value.get('emailAddress')
        if email:
            return email.strip()

        # 2. Try name field (often username = email in corporate Jira)
        name = field_value.get('name')
        if name:
            name = name.strip()
            if '@' in name:
                return name
            # Construct email if domain provided
            if email_domain:
                return f"{name}@{email_domain}"

        # 3. Try key field (some Jira instances use key as email/username)
        key = field_value.get('key')
        if key:
            key = key.strip()
            if '@' in key:
                return key
            if email_domain and not name:
                return f"{key}@{email_domain}"

        # 4. Last resort: try to extract from displayName (less reliable)
        display_name = field_value.get('displayName', '')
        if display_name and '@' in display_name:
            # Extract email-like pattern from displayName
            import re
            match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', display_name)
            if match:
                return match.group(0)

    return None


def extract_list_values(field_value: Any) -> List[str]:
    """Extract list of values from Jira field (for components, versions, etc.)."""
    if field_value is None:
        return []

    if isinstance(field_value, str):
        return [field_value.strip()] if field_value.strip() else []

    if isinstance(field_value, list):
        values = []
        for item in field_value:
            if isinstance(item, dict):
                for key in ('value', 'displayName', 'name', 'key'):
                    if item.get(key):
                        values.append(str(item[key]).strip())
                        break
            elif isinstance(item, str) and item.strip():
                values.append(item.strip())
        return values

    if isinstance(field_value, dict):
        for key in ('value', 'displayName', 'name', 'key'):
            if field_value.get(key):
                return [str(field_value[key]).strip()]

    return []


def normalize_timestamp(value: Optional[str]) -> str:
    """Format Jira timestamp to readable format."""
    if not value:
        return "-"
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        try:
            dt = datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value


def calculate_days_since(timestamp: Optional[str]) -> int:
    """Calculate days since timestamp."""
    if not timestamp:
        return -1
    try:
        dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f%z")
        now = datetime.now(timezone.utc)
        delta = now - dt
        return delta.days
    except ValueError:
        try:
            dt = datetime.strptime(timestamp[:19], "%Y-%m-%dT%H:%M:%S")
            now = datetime.now()
            delta = now - dt
            return delta.days
        except ValueError:
            return -1


def get_age_bucket(days: int) -> str:
    """Get human-readable age bucket for days since update."""
    if days < 0:
        return "-"

    for threshold, label in AGING_BUCKETS:
        if threshold is None or days <= threshold:
            return label

    return "> 1 year"


def extract_etracks(fields: Dict[str, Any], etrack_field_id: str, alt_etrack_field_id: str) -> str:
    """Extract etrack IDs from issue fields."""
    etracks = []

    # Main etrack field
    main_et = fields.get(etrack_field_id)
    if main_et:
        etracks.extend(re.findall(r'\d+', str(main_et)))

    # Alternate etrack field
    alt_et = fields.get(alt_etrack_field_id)
    if alt_et:
        etracks.extend(re.findall(r'\d+', str(alt_et)))

    unique_etracks = sorted(set(etracks), key=int)
    return "; ".join(unique_etracks) if unique_etracks else "-"


# ---------------------------------------------------------------------------
# Validation Logic
# ---------------------------------------------------------------------------

class FIValidator:
    """Validate FI issues against group-based configuration rules."""

    def __init__(self, config: Optional[GroupConfig] = None, debug: bool = False):
        self.config = config
        self.debug = debug

    def validate_issue(self, versions: List[str], components: List[str], bu: str = "") -> List[str]:
        """
        Validate component-version combinations using group rules.

        Logic:
        - Check if components exist in any group
        - Check if versions exist in any group
        - Check if version-component combinations are valid
        - N/A versions are filtered out but warned about
        - If at least one version is valid, invalid versions become warnings (IgnVer)

        Returns list of validation error messages (compact format).
        """
        errors = []

        if not self.config:
            return errors  # No validation if no config

        if not components:
            errors.append("NoComp")
            return errors

        if not versions:
            errors.append("NoVer")
            return errors

        # Filter out N/A from versions but track if present
        has_na = any(v.upper() == 'N/A' for v in versions)
        valid_versions_list = [v for v in versions if v.upper() != 'N/A']

        if has_na:
            errors.append("HasN/A")

        if not valid_versions_list:
            # Only N/A was present
            errors.append("NoVer")
            return errors

        # Check each component
        for component in components:
            groups = self.config.get_groups_for_component(component)

            if not groups:
                # Component not in any group
                errors.append(f"BadComp:{component}")
                continue

            if self.config.is_component_in_unknown(component):
                # Component only in Unknown group - warn
                errors.append(f"Unassigned:{component}")
                continue

        # Check each version - is it in ANY group?
        all_known_versions = set()
        for group_vers in self.config.group_versions.values():
            all_known_versions.update(group_vers)

        # Separate known and unknown versions
        known_versions = [v for v in valid_versions_list if v in all_known_versions]
        unknown_versions = [v for v in valid_versions_list if v not in all_known_versions]

        # If at least one version is known, unknown versions are warnings; otherwise errors
        has_any_known_version = len(known_versions) > 0
        for version in unknown_versions:
            if has_any_known_version:
                errors.append(f"IgnVer:{version}")  # Warning - ignored
            else:
                errors.append(f"BadVer:{version}")  # Error - no valid versions

        # Check version-component combinations (only for known versions)
        for component in components:
            groups = self.config.get_groups_for_component(component)
            if not groups or self.config.is_component_in_unknown(component):
                continue  # Already reported above

            valid_versions = self.config.get_valid_versions_for_component(component)
            if not valid_versions:
                if self.debug:
                    print(f"DEBUG: Component '{component}' groups {groups} have no versions defined", file=sys.stderr)
                continue

            # Separate valid and invalid versions for this component
            comp_valid = [v for v in known_versions if v in valid_versions]
            comp_invalid = [v for v in known_versions if v not in valid_versions]

            # If at least one version is valid for component, mismatches are warnings
            has_valid_for_comp = len(comp_valid) > 0
            for version in comp_invalid:
                if has_valid_for_comp:
                    errors.append(f"IgnV:{version}/C:{component}")  # Warning - ignored
                else:
                    errors.append(f"V:{version}/C:{component}")  # Error - no valid combo

        return errors


# ---------------------------------------------------------------------------
# Input Parsing
# ---------------------------------------------------------------------------

def parse_fi_ids_from_text(text: str) -> List[str]:
    """Extract FI IDs from text (supports FI-12345 format)."""
    # Find all FI-<digits> patterns
    matches = re.findall(r'FI-\d+', text, re.IGNORECASE)
    # Normalize to uppercase and dedupe while preserving order
    seen = set()
    result = []
    for m in matches:
        key = m.upper()
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def is_jql_query(text: str) -> bool:
    """Check if text looks like a JQL query rather than FI IDs."""
    text = text.strip()
    # JQL typically contains operators or keywords
    jql_indicators = ['=', '~', 'AND', 'OR', 'ORDER BY', 'project', 'status', 'assignee', 'IN', 'NOT']
    text_upper = text.upper()
    for indicator in jql_indicators:
        if indicator.upper() in text_upper:
            return True
    return False


def read_stdin_input() -> str:
    """Read input from stdin if available."""
    try:
        if sys.stdin.isatty():
            return ""
        return sys.stdin.read()
    except (OSError, IOError):
        # Handle bad file descriptor or other stdin issues
        return ""


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

class FIReport:
    """Generate validation report for FI issues."""

    # Known custom field IDs (from existing scripts)
    KNOWN_FIELDS = {
        'case_status': 'customfield_16200',
        'etrack_incident': 'customfield_33802',
        'etrack_alt': 'customfield_36508',
        'customer_name': 'customfield_18901',
        'aged_reason': None,  # Will be resolved dynamically
        'assignee_manager': None,  # Will be resolved dynamically
        'business_unit': None,  # Will be resolved dynamically
    }

    # Warning codes that don't count as errors (exact matches and prefixes)
    WARNING_CODES = {'HasN/A'}  # Exact matches
    WARNING_PREFIXES = ('IgnVer:', 'IgnV:')  # Prefix matches

    @classmethod
    def is_warning(cls, error: str) -> bool:
        """Check if an error code is a warning (doesn't count as error)."""
        if error in cls.WARNING_CODES:
            return True
        for prefix in cls.WARNING_PREFIXES:
            if error.startswith(prefix):
                return True
        return False

    def __init__(self, client: JiraClient, validator: FIValidator, email_domain: Optional[str] = None,
                 fetch_manager_groups: bool = False, ignore_warnings: bool = False):
        self.client = client
        self.validator = validator
        self.email_domain = email_domain
        self.fetch_manager_groups = fetch_manager_groups
        self.ignore_warnings = ignore_warnings
        self._resolve_custom_fields()

    def _resolve_custom_fields(self):
        """Resolve dynamic custom field IDs."""
        # Aged Reason
        aged_reason_id = self.client.get_field_id_by_candidates(['Aged Reason', 'AgedReason'])
        if aged_reason_id:
            self.KNOWN_FIELDS['aged_reason'] = aged_reason_id

        # Assignee Manager
        manager_id = self.client.get_field_id_by_candidates(['Assignee Manager', 'AssigneeManager'])
        if manager_id:
            self.KNOWN_FIELDS['assignee_manager'] = manager_id

        # Business Unit
        bu_id = self.client.get_field_id_by_candidates(['Business Unit', 'BusinessUnit'])
        if bu_id:
            self.KNOWN_FIELDS['business_unit'] = bu_id

    def _get_required_fields(self) -> List[str]:
        """Get list of required Jira fields for validation."""
        fields = [
            'key', 'summary', 'status', 'priority', 'assignee', 'reporter',
            'created', 'updated', 'components', 'versions', 'resolution',
        ]

        # Add known custom fields
        for field_id in self.KNOWN_FIELDS.values():
            if field_id:
                fields.append(field_id)

        return fields

    def _extract_issue_data(self, issue: Dict) -> Dict[str, Any]:
        """Extract relevant data from issue for report."""
        fields = issue.get('fields', {})

        # Basic fields
        key = issue.get('key', '-')
        summary = fields.get('summary', '-')
        if len(summary) > 80:
            summary = summary[:77] + "..."

        # Status and Priority
        status = extract_field_value(fields.get('status'))
        priority = extract_field_value(fields.get('priority'))
        resolution = extract_field_value(fields.get('resolution'))

        # Assignee and Manager (with emails)
        assignee = extract_field_value(fields.get('assignee'))
        assignee_email = extract_email_address(fields.get('assignee'), self.email_domain)
        manager_field = self.KNOWN_FIELDS.get('assignee_manager')
        assignee_manager = extract_field_value(fields.get(manager_field)) if manager_field else "-"
        # Assignee Manager field value is often the email itself
        if assignee_manager and assignee_manager != "-" and '@' in assignee_manager:
            assignee_manager_email = assignee_manager.strip()
        else:
            assignee_manager_email = extract_email_address(fields.get(manager_field), self.email_domain) if manager_field else None

        # Manager Groups (optional - requires extra API calls)
        manager_groups = "-"
        manager_groups_list = []  # Raw list for filtering
        if self.fetch_manager_groups and assignee_manager_email and '@' in assignee_manager_email:
            # Extract username from email (strip @domain.com)
            manager_username = assignee_manager_email.split('@')[0]
            groups = self.client.get_user_groups(
                manager_username,
                filter_patterns=['*-managers', '*-directors']
            )
            manager_groups_list = groups if groups else []
            manager_groups = "; ".join(sorted(groups)) if groups else "-"

        # Dates
        created = normalize_timestamp(fields.get('created'))
        updated = normalize_timestamp(fields.get('updated'))
        days_since = calculate_days_since(fields.get('updated'))
        age_bucket = get_age_bucket(days_since)

        # Case Status
        case_status_field = self.KNOWN_FIELDS.get('case_status')
        case_status = extract_field_value(fields.get(case_status_field)) if case_status_field else "-"

        # Components and Versions
        components_list = extract_list_values(fields.get('components'))
        components = "; ".join(components_list) if components_list else "-"

        versions_list = extract_list_values(fields.get('versions'))
        versions = "; ".join(versions_list) if versions_list else "-"

        # Business Unit
        bu_field = self.KNOWN_FIELDS.get('business_unit')
        business_unit = extract_field_value(fields.get(bu_field)) if bu_field else "-"

        # Etracks
        etrack_id = self.KNOWN_FIELDS.get('etrack_incident', '')
        alt_etrack_id = self.KNOWN_FIELDS.get('etrack_alt', '')
        etracks = extract_etracks(fields, etrack_id, alt_etrack_id)

        # Aged Reason
        aged_reason_field = self.KNOWN_FIELDS.get('aged_reason')
        aged_reason = extract_field_value(fields.get(aged_reason_field)) if aged_reason_field else "-"

        # Validation
        validation_errors = self.validator.validate_issue(versions_list, components_list, business_unit)
        # Store all codes for summary, but filter display based on ignore_warnings
        all_validation_codes = "; ".join(validation_errors) if validation_errors else "OK"
        display_errors = [e for e in validation_errors if not self.is_warning(e)] if self.ignore_warnings else validation_errors
        validation_notes = "; ".join(display_errors) if display_errors else "OK"

        return {
            'Key': key,
            'Summary': summary,
            'Priority': priority,
            'Assignee': assignee,
            'Assignee Manager': assignee_manager,
            'Manager Groups': manager_groups,
            'Case Status': case_status,
            'Status': status,
            'Created': created,
            'Updated': updated,
            'Days Since Update': str(days_since) if days_since >= 0 else "-",
            'Age Bucket': age_bucket,
            'Component/s': components,
            'Affects Version/s': versions,
            'Business Unit': business_unit,
            'Resolution': resolution,
            'Linked Etracks': etracks,
            'Aged Reason': aged_reason,
            'Validation Notes': validation_notes,
            '_all_validation_codes': all_validation_codes,  # For summary stats (includes warnings)
            '_has_errors': any(not self.is_warning(e) for e in validation_errors),
            '_error_count': sum(1 for e in validation_errors if not self.is_warning(e)),
            '_versions_list': versions_list,
            '_components_list': components_list,
            '_assignee_email': assignee_email,
            '_assignee_manager_email': assignee_manager_email,
            '_manager_groups_list': manager_groups_list,
        }

    def fetch_and_validate(self, fi_ids: List[str] = None, jql: str = None) -> Tuple[List[Dict], List[str]]:
        """
        Fetch issues and validate them.
        Returns (validated_records, not_found_keys).
        """
        fields = self._get_required_fields()

        if jql:
            print(f"Executing JQL: {jql}", file=sys.stderr)
            issues = self.client.search_issues(jql, fields)
            not_found = []
        elif fi_ids:
            print(f"Fetching {len(fi_ids)} FI IDs...", file=sys.stderr)
            issues, not_found = self.client.get_issues_batch(fi_ids, fields)
        else:
            return [], []

        records = []
        seen_keys = set()
        for issue in issues:
            record = self._extract_issue_data(issue)
            # Deduplicate by key
            if record['Key'] not in seen_keys:
                seen_keys.add(record['Key'])
                records.append(record)

        # Sort by Key numerically
        records.sort(key=lambda r: int(r['Key'].split('-')[1]) if '-' in r['Key'] else 0)

        return records, not_found


def filter_columns(all_columns: List[str], include_cols: Optional[str] = None,
                   exclude_cols: Optional[str] = None) -> List[str]:
    """
    Filter columns based on include/exclude lists.

    Args:
        all_columns: Full list of available columns
        include_cols: Comma-separated list of columns to include (case-insensitive)
        exclude_cols: Comma-separated list of columns to exclude (case-insensitive)

    Returns:
        Filtered list of columns preserving original order
    """
    # Build case-insensitive lookup
    col_map = {c.lower(): c for c in all_columns}

    if include_cols:
        # Only include specified columns
        requested = [c.strip() for c in include_cols.split(',')]
        result = []
        for req in requested:
            matched = col_map.get(req.lower())
            if matched:
                result.append(matched)
            else:
                print(f"Warning: Unknown column '{req}' (ignored)", file=sys.stderr)
        return result if result else all_columns

    if exclude_cols:
        # Exclude specified columns
        excluded = {c.strip().lower() for c in exclude_cols.split(',')}
        result = [c for c in all_columns if c.lower() not in excluded]
        # Warn about unknown exclusions
        known_lower = {c.lower() for c in all_columns}
        unknown = excluded - known_lower
        for u in unknown:
            print(f"Warning: Unknown column '{u}' in exclusion list (ignored)", file=sys.stderr)
        return result

    return all_columns


def print_table(records: List[Dict], columns: List[str] = None):
    """Print records as a formatted table."""
    if not records:
        print("No records to display.")
        return

    if columns is None:
        columns = OUTPUT_COLUMNS

    # Filter columns that have data
    available_columns = [c for c in columns if c in records[0]]

    if PrettyTable:
        table = PrettyTable()
        table.field_names = available_columns

        for col in available_columns:
            if col in ['Days Since Update', 'Priority']:
                table.align[col] = "c"
            elif col in ['Key']:
                table.align[col] = "l"
            else:
                table.align[col] = "l"

        for record in records:
            row = [record.get(col, "-") for col in available_columns]
            table.add_row(row)

        print(table)

    elif tabulate:
        rows = [[record.get(col, "-") for col in available_columns] for record in records]
        print(tabulate(rows, headers=available_columns, tablefmt="grid"))

    else:
        # Simple fallback
        print("\t".join(available_columns))
        print("-" * 120)
        for record in records:
            row = [str(record.get(col, "-")) for col in available_columns]
            print("\t".join(row))


def print_summary(records: List[Dict], not_found: List[str]):
    """Print validation summary."""
    total = len(records)
    with_errors = sum(1 for r in records if r.get('_has_errors', False))
    without_errors = total - with_errors

    # Count records with warnings (use _all_validation_codes to include even when -iw used)
    def has_warning(notes):
        if not notes or notes == 'OK':
            return False
        for code in notes.split('; '):
            if code == 'HasN/A' or code.startswith('IgnVer:') or code.startswith('IgnV:'):
                return True
        return False

    with_warnings = sum(1 for r in records if has_warning(r.get('_all_validation_codes', '')))

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total FIs Validated:    {total}")
    print(f"Valid (No Issues):      {without_errors}")
    print(f"Invalid (Has Issues):   {with_errors}")
    print(f"With Warnings:          {with_warnings}")

    if not_found:
        print(f"Not Found/Inaccessible: {len(not_found)}")

    if with_errors > 0:
        print(f"\nValidation Error Rate:  {with_errors / total * 100:.1f}%")

    # Aging distribution
    print("\n--- Aging Distribution ---")
    age_counts = {}
    for r in records:
        bucket = r.get('Age Bucket', '-')
        age_counts[bucket] = age_counts.get(bucket, 0) + 1

    for bucket, _ in AGING_BUCKETS:
        label = get_age_bucket(bucket if bucket else 366)
        count = age_counts.get(label, 0)
        if count > 0:
            print(f"  {label:15s}: {count:4d}")

    # Error/Warning breakdown - use _all_validation_codes to always show warnings
    error_counts = {}
    warning_counts = {}
    warning_types = {'Ignored Version (warn)', 'Ignored Ver/Comp (warn)', 'Has N/A Version'}

    for r in records:
        # Use _all_validation_codes for summary (includes warnings even with -iw)
        notes = r.get('_all_validation_codes', r.get('Validation Notes', ''))
        if notes and notes != 'OK':
            for error in notes.split('; '):
                # Normalize error type (compact format)
                if error.startswith('V:') and '/C:' in error:
                    key = 'Ver/Comp Mismatch'
                elif error.startswith('BadComp:'):
                    key = 'Bad Component'
                elif error.startswith('BadVer:'):
                    key = 'Bad Version'
                elif error.startswith('Unassigned:'):
                    key = 'Unassigned Component'
                elif error.startswith('IgnVer:'):
                    key = 'Ignored Version (warn)'
                elif error.startswith('IgnV:') and '/C:' in error:
                    key = 'Ignored Ver/Comp (warn)'
                elif error == 'HasN/A':
                    key = 'Has N/A Version'
                elif error == 'NoVer':
                    key = 'Missing Version'
                elif error == 'NoComp':
                    key = 'Missing Component'
                else:
                    key = error

                if key in warning_types:
                    warning_counts[key] = warning_counts.get(key, 0) + 1
                else:
                    error_counts[key] = error_counts.get(key, 0) + 1

    if error_counts:
        print("\n--- Validation Errors ---")
        for error, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            print(f"  {error:25s}: {count:4d}")

    if warning_counts:
        print("\n--- Validation Warnings ---")
        for warn, count in sorted(warning_counts.items(), key=lambda x: -x[1]):
            print(f"  {warn:25s}: {count:4d}")


def print_validation_legend():
    """Print the validation error code legend."""
    print("\n" + "=" * 60)
    print("VALIDATION NOTES LEGEND")
    print("=" * 60)
    print("  BadComp:X      - Component X not in any group")
    print("  BadVer:Y       - Version Y not in any group")
    print("  V:Y/C:X        - Version Y valid but wrong for component X")
    print("  Unassigned:X   - Component X in Unknown group (needs assignment)")
    print("  --- Warnings (ignored if valid version exists) ---")
    print("  IgnVer:Y       - Version Y ignored (unknown but has valid version)")
    print("  IgnV:Y/C:X     - Version Y ignored for component X (has valid combo)")
    print("  HasN/A         - N/A version present (ignored for validation)")
    print("  NoComp         - No component specified")
    print("  NoVer          - No version specified")
    print("  OK             - Valid")


def print_detailed_failures(records: List[Dict]):
    """Print detailed failure information for each invalid FI (one line per FI)."""
    invalid_records = [r for r in records if r.get('_has_errors', False)]
    if not invalid_records:
        return

    print("\n" + "=" * 60)
    print("DETAILED VALIDATION FAILURES")
    print("=" * 60)

    for record in invalid_records:
        key = record.get('Key', '-')
        notes = record.get('Validation Notes', '')
        if notes and notes != 'OK':
            comp = record.get('Component/s', '-')
            ver = record.get('Affects Version/s', '-')
            print(f"{key}: C={comp} V={ver} => {notes}")


def print_not_found(not_found: List[str]):
    """Print list of not found FI IDs."""
    if not not_found:
        return

    print("\n" + "=" * 60)
    print("NOT FOUND / INACCESSIBLE FIs")
    print("=" * 60)
    for key in not_found:
        print(f"  - {key}")


def export_csv(records: List[Dict], output_path: str, columns: List[str] = None):
    """Export records to CSV file."""
    if not records:
        print("No records to export.", file=sys.stderr)
        return

    if columns is None:
        columns = OUTPUT_COLUMNS

    # Filter columns that have data
    available_columns = [c for c in columns if c in records[0]]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=available_columns, extrasaction='ignore')
        writer.writeheader()
        for record in records:
            writer.writerow({col: record.get(col, "") for col in available_columns})

    print(f"Exported {len(records)} records to {output_path}", file=sys.stderr)


def print_email_lists(records: List[Dict]):
    """
    Print email lists for Outlook.
    TO: All unique assignee emails (comma-separated)
    CC: All unique assignee manager emails (comma-separated)
    """
    assignee_emails = set()
    manager_emails = set()

    for record in records:
        email = record.get('_assignee_email')
        if email:
            assignee_emails.add(email)
        manager_email = record.get('_assignee_manager_email')
        if manager_email:
            manager_emails.add(manager_email)

    print("\n" + "=" * 60)
    print("EMAIL NOTIFICATION LISTS (for Outlook)")
    print("=" * 60)

    if assignee_emails:
        print(f"TO: {', '.join(sorted(assignee_emails))}")
    else:
        print("TO: (no assignee emails found)")

    print()
    print()

    if manager_emails:
        print(f"CC: {', '.join(sorted(manager_emails))}")
    else:
        print("CC: (no assignee manager emails found)")


# ---------------------------------------------------------------------------
# Discovery Mode Functions
# ---------------------------------------------------------------------------

def is_invalid_value(value: str) -> bool:
    """Check if a value should be filtered out in discovery mode."""
    if not value:
        return True
    normalized = value.strip().lower()
    return normalized in INVALID_VALUES


def parse_version_tuple(version: str) -> Tuple:
    """
    Parse version string to tuple for numeric sorting.
    Handles formats like: 9.1, 10.1.1, 11.0.0.1, 6.3.1c
    """
    parts = []
    # Split by dots
    for part in version.split('.'):
        # Extract numeric and suffix parts
        match = re.match(r'^(\d+)(.*)$', part)
        if match:
            parts.append((int(match.group(1)), match.group(2)))
        else:
            # Non-numeric part, use string comparison
            parts.append((0, part))
    return tuple(parts)


def sort_versions(versions: List[str]) -> List[str]:
    """Sort version strings numerically."""
    return sorted(versions, key=parse_version_tuple)


def sort_strings(strings: List[str]) -> List[str]:
    """Sort strings alphabetically (case-insensitive)."""
    return sorted(strings, key=lambda s: s.lower())


def discover_values_from_records(records: List[Dict]) -> Dict[str, Dict[str, int]]:
    """
    Extract unique values with counts from records.
    Returns dict with 'versions', 'components', 'business_units' keys.
    Each contains {value: count} dict.
    """
    versions: Dict[str, int] = {}
    components: Dict[str, int] = {}
    business_units: Dict[str, int] = {}

    for record in records:
        # Extract versions (may be comma-separated in display)
        versions_list = record.get('_versions_list', [])
        for v in versions_list:
            v = v.strip()
            if not is_invalid_value(v):
                versions[v] = versions.get(v, 0) + 1

        # Extract components (may be comma-separated in display)
        components_list = record.get('_components_list', [])
        for c in components_list:
            c = c.strip()
            if not is_invalid_value(c):
                components[c] = components.get(c, 0) + 1

        # Extract business unit
        bu = record.get('Business Unit', '').strip()
        if not is_invalid_value(bu):
            business_units[bu] = business_units.get(bu, 0) + 1

    return {
        'versions': versions,
        'components': components,
        'business_units': business_units,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Validate FI tickets against version/component rules.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Input sources
    input_group = parser.add_argument_group('Input Sources')
    input_group.add_argument('-j', '--jql', type=str,
                             help='JQL query to fetch FI issues')
    input_group.add_argument('-f', '--file', type=str,
                             help='File containing FI IDs (one per line or mixed text)')

    # Configuration
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument('-g', '--groups', type=str, metavar='FILE',
                              help='Groups configuration file (INI format with [Group:components] and [Group:versions])')

    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument('-o', '--output', type=str,
                              help='Export results to CSV file')
    output_group.add_argument('-s', '--no-summary', action='store_true',
                              help='Skip printing summary')
    output_group.add_argument('-S', '--show', type=str, choices=['all', 'valid', 'invalid'],
                              default='all',
                              help='Filter output: all (default), valid (no errors), invalid (has errors)')
    output_group.add_argument('-e', '--errors-only', action='store_true',
                              help='Shortcut for --show invalid')
    output_group.add_argument('-v', '--valid-only', action='store_true',
                              help='Shortcut for --show valid')
    output_group.add_argument('-m', '--max', type=int, default=0,
                              help='Maximum number of results (0 = unlimited)')
    output_group.add_argument('-I', '--include-cols', type=str, metavar='COLS',
                              help='Only show these columns (comma-separated, case-insensitive)')
    output_group.add_argument('-E', '--exclude-cols', type=str, metavar='COLS',
                              help='Exclude these columns from output (comma-separated, case-insensitive)')
    output_group.add_argument('-L', '--list-cols', action='store_true',
                              help='List available column names and exit')
    output_group.add_argument('-en', '--email-notification', action='store_true',
                              help='Print TO: (assignee emails) and CC: (manager emails) for Outlook')
    output_group.add_argument('-ed', '--email-domain', type=str, metavar='DOMAIN',
                              help='Email domain to construct emails from usernames (e.g., veritas.com)')
    output_group.add_argument('-mg', '--manager-groups', action='store_true',
                              help='Fetch manager groups (*-managers, *-directors) - adds API calls')
    output_group.add_argument('-fg', '--filter-groups', type=str, metavar='GROUPS',
                              help='Filter to FIs where manager belongs to any of these groups (comma-separated, requires -mg)')
    output_group.add_argument('-V', '--verbose', action='store_true',
                              help='Show detailed failures and validation legend')
    output_group.add_argument('-iw', '--ignore-warnings', action='store_true',
                              help='Hide warning codes (HasN/A) from validation notes')

    # Discovery mode - build config file
    discovery_group = parser.add_argument_group('Discovery Mode')
    discovery_group.add_argument('-bg', '--build-groups', type=str, metavar='FILE',
                                  help='Build/update groups config file from discovered data (merges with existing)')

    # Debug
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Enable debug output')

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Handle --list-cols: show available columns and exit
    if args.list_cols:
        print("Available columns:")
        for i, col in enumerate(OUTPUT_COLUMNS, 1):
            print(f"  {i:2d}. {col}")
        sys.exit(0)

    # Validate environment
    if not JIRA_BASE_URL or not JIRA_TOKEN:
        print("Error: JIRA_SERVER_NAME and JIRA_ACC_TOKEN environment variables required.",
              file=sys.stderr)
        sys.exit(1)

    # Determine input source
    fi_ids = []
    jql = None
    stdin_input = read_stdin_input()

    if args.jql:
        jql = args.jql
    elif args.file:
        file_content = ""
        with open(args.file, 'r', encoding='utf-8') as f:
            file_content = f.read()
        fi_ids = parse_fi_ids_from_text(file_content)
        if not fi_ids:
            print(f"Error: No valid FI IDs found in {args.file}", file=sys.stderr)
            sys.exit(1)
    elif stdin_input:
        stdin_input = stdin_input.strip()
        if is_jql_query(stdin_input):
            jql = stdin_input
        else:
            fi_ids = parse_fi_ids_from_text(stdin_input)
            if not fi_ids:
                # Maybe it's a JQL after all
                jql = stdin_input
    else:
        print("Error: No input provided. Use -j/--jql, -f/--file, or pipe input to stdin.",
              file=sys.stderr)
        sys.exit(1)

    # Check if discovery mode is enabled
    discovery_mode = args.build_groups

    # Load group config if provided (not in discovery mode)
    config = None
    if not discovery_mode and args.groups:
        try:
            config = GroupConfig.load(args.groups)
        except (FileNotFoundError, ValueError) as e:
            print(f"Configuration Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Initialize client and validator
    client = JiraClient(JIRA_BASE_URL, JIRA_TOKEN)
    validator = FIValidator(config, debug=args.debug)
    report = FIReport(client, validator, email_domain=args.email_domain,
                      fetch_manager_groups=args.manager_groups,
                      ignore_warnings=args.ignore_warnings)

    # Fetch and validate
    try:
        records, not_found = report.fetch_and_validate(fi_ids=fi_ids, jql=jql)
    except Exception as e:
        print(f"Error fetching issues: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    if not records and not not_found:
        print("No FI issues found matching the criteria.", file=sys.stderr)
        sys.exit(0)

    # Discovery mode: build groups config file, then exit
    if discovery_mode:
        print(f"\nDiscovery mode: Analyzing {len(records)} FI records...", file=sys.stderr)
        discovered = discover_values_from_records(records)

        # Load existing config if file exists (for merging)
        existing_config = None
        if os.path.exists(args.build_groups):
            try:
                existing_config = GroupConfig.load(args.build_groups)
                print(f"Merging with existing config: {args.build_groups}", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Could not load existing config, creating new: {e}", file=sys.stderr)

        # Build groups data (all discovered items go to Unknown for new file)
        groups_data = {
            'Unknown': {
                'components': discovered['components'],
                'versions': discovered['versions']
            }
        }

        write_groups_config(args.build_groups, groups_data, existing_config)

        print("\nDiscovery complete. Edit the config file to move items from [Unknown] to appropriate groups.", file=sys.stderr)
        sys.exit(0)

    # Determine show filter (--errors-only and --valid-only are shortcuts)
    show_filter = args.show
    if args.errors_only:
        show_filter = 'invalid'
    elif args.valid_only:
        show_filter = 'valid'

    # Keep original records for summary, apply filter for display
    all_records = records  # preserve reference to all records
    original_count = len(records)
    if show_filter == 'invalid':
        records = [r for r in records if r.get('_has_errors', False)]
        print(f"Showing {len(records)} invalid FIs (filtered from {original_count} total)", file=sys.stderr)
    elif show_filter == 'valid':
        records = [r for r in records if not r.get('_has_errors', False)]
        print(f"Showing {len(records)} valid FIs (filtered from {original_count} total)", file=sys.stderr)

    # Filter by manager groups if requested
    if args.filter_groups:
        if not args.manager_groups:
            print("Warning: -fg/--filter-groups requires -mg/--manager-groups to fetch group data", file=sys.stderr)
        else:
            filter_group_set = {g.strip().lower() for g in args.filter_groups.split(',')}
            pre_filter_count = len(records)
            records = [
                r for r in records
                if any(g.lower() in filter_group_set for g in r.get('_manager_groups_list', []))
            ]
            print(f"Filtered to {len(records)} FIs where manager belongs to: {args.filter_groups} "
                  f"(from {pre_filter_count})", file=sys.stderr)

    # Compute display columns based on include/exclude options
    display_columns = filter_columns(
        OUTPUT_COLUMNS,
        include_cols=args.include_cols,
        exclude_cols=args.exclude_cols
    )

    # Print results
    if records:
        print_table(records, columns=display_columns)
    elif show_filter != 'all':
        print(f"No {show_filter} FIs found.", file=sys.stderr)

    if not args.no_summary:
        print_summary(all_records, not_found)  # use all_records for accurate summary

    # Verbose output: legend and detailed failures
    if args.verbose:
        print_validation_legend()
        print_detailed_failures(all_records)

    if not_found:
        print_not_found(not_found)

    # Export to CSV if requested
    if args.output:
        export_csv(records, args.output, columns=display_columns)

    # Email notification output
    if args.email_notification and records:
        print_email_lists(records)

    # Exit with error code if any validation errors
    errors_count = sum(1 for r in records if r.get('_has_errors', False))
    sys.exit(1 if errors_count > 0 else 0)


if __name__ == '__main__':
    main()
