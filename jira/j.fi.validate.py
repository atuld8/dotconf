#!/usr/bin/env python3
"""
FI Validator - Validate FI tickets for NBU product against version/component rules.

Validates FI tickets against:
- Affects Version/s: Must be within valid version list
- Component/s: Must match allowed components for the business unit
- Business Unit: Must match expected value (loaded from config)

Input Methods:
- JQL query via -j/--jql
- File with FI IDs via -f/--file
- Stdin (pipe FI IDs or JQL)

Output:
- Console table with validation results
- Optional CSV export via -o/--output

Configuration Files:
- Versions file: One valid version per line (e.g., 9.1, 10.1.1, 11.0)
- Components file: One valid component per line
- Business Unit file: Single line with expected BU value

Environment variables expected:
- JIRA_SERVER_NAME
- JIRA_ACC_TOKEN

Examples:
    # Validate using JQL query
    j.fi.validate.py -j "project = FI AND 'Business Unit' = NBU" \\
        --versions-file valid_versions.txt \\
        --components-file valid_components.txt \\
        --bu-file business_unit.txt

    # Validate from file with FI IDs
    j.fi.validate.py -f fi_ids.txt --versions-file versions.txt --components-file components.txt

    # Pipe FI IDs via stdin
    echo "FI-12345" | j.fi.validate.py --versions-file versions.txt --components-file components.txt

    # Export results to CSV
    j.fi.validate.py -j "project = FI" --versions-file v.txt --components-file c.txt -o report.csv

    # Discovery mode: Build config files from existing FI data
    j.fi.validate.py -j "project = FI AND 'Business Unit' = NBU" \\
        --build-vf discovered_versions.txt \\
        --build-cf discovered_components.txt \\
        --build-bu discovered_bu.txt
"""

from __future__ import print_function

import argparse
import csv
import os
import re
import sys
import time
from collections import OrderedDict
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


def load_single_value(filepath: str) -> str:
    """Load single value from file (first non-empty line)."""
    lines = load_file_lines(filepath)
    if not lines:
        raise ValueError(f"Configuration file is empty: {filepath}")
    return lines[0]


class ValidationConfig:
    """Configuration for FI validation rules."""

    def __init__(self, versions_file: str, components_file: str, bu_file: Optional[str] = None):
        self.valid_versions: Set[str] = set()
        self.valid_components: Set[str] = set()
        self.expected_bu: Optional[str] = None

        # Load versions (case-sensitive)
        if versions_file:
            self.valid_versions = set(load_file_lines(versions_file))
            print(f"Loaded {len(self.valid_versions)} valid versions from {versions_file}", file=sys.stderr)

        # Load components (case-insensitive comparison later)
        if components_file:
            self.valid_components = set(c.lower() for c in load_file_lines(components_file))
            print(f"Loaded {len(self.valid_components)} valid components from {components_file}", file=sys.stderr)

        # Load expected business unit
        if bu_file:
            self.expected_bu = load_single_value(bu_file)
            print(f"Expected Business Unit: {self.expected_bu}", file=sys.stderr)


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
        return ", ".join(values) if values else "-"

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
    return ", ".join(unique_etracks) if unique_etracks else "-"


# ---------------------------------------------------------------------------
# Validation Logic
# ---------------------------------------------------------------------------

class FIValidator:
    """Validate FI issues against configuration rules."""

    def __init__(self, config: ValidationConfig, debug: bool = False):
        self.config = config
        self.debug = debug

    def validate_versions(self, versions: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate versions against allowed list.
        Returns (is_valid, list_of_invalid_versions).
        """
        if not self.config.valid_versions:
            return True, []  # No validation if no versions configured

        if not versions:
            return False, ["No versions specified"]

        invalid = []
        for v in versions:
            if v not in self.config.valid_versions:
                invalid.append(v)

        return len(invalid) == 0, invalid

    def validate_components(self, components: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate components against allowed list.
        Returns (is_valid, list_of_invalid_components).
        """
        if not self.config.valid_components:
            return True, []  # No validation if no components configured

        if not components:
            return False, ["No components specified"]

        invalid = []
        for c in components:
            c_lower = c.lower()
            if c_lower not in self.config.valid_components:
                if self.debug:
                    print(f"DEBUG: Component '{c}' (lower='{c_lower}', "
                          f"bytes={c_lower.encode()}) not in valid set", file=sys.stderr)
                invalid.append(c)

        return len(invalid) == 0, invalid

    def validate_business_unit(self, bu: str) -> Tuple[bool, str]:
        """
        Validate business unit matches expected value.
        Returns (is_valid, error_message or empty string).
        """
        if not self.config.expected_bu:
            return True, ""  # No validation if no BU configured

        actual_bu = bu.strip() if bu and bu != "-" else ""

        if not actual_bu:
            return False, f"Business Unit not set (expected: {self.config.expected_bu})"

        if actual_bu.lower() != self.config.expected_bu.lower():
            return False, f"Business Unit mismatch: '{actual_bu}' (expected: {self.config.expected_bu})"

        return True, ""

    def validate_issue(self, versions: List[str], components: List[str], bu: str) -> List[str]:
        """
        Validate all rules for an issue.
        Returns list of validation error messages.
        """
        errors = []

        # Version validation
        version_ok, invalid_versions = self.validate_versions(versions)
        if not version_ok:
            if invalid_versions == ["No versions specified"]:
                errors.append("No Affects Version/s specified")
            else:
                errors.append(f"Invalid version(s): {', '.join(invalid_versions)}")

        # Component validation
        component_ok, invalid_components = self.validate_components(components)
        if not component_ok:
            if invalid_components == ["No components specified"]:
                errors.append("No Component/s specified")
            else:
                errors.append(f"Invalid component(s): {', '.join(invalid_components)}")

        # Business Unit validation
        bu_ok, bu_error = self.validate_business_unit(bu)
        if not bu_ok:
            errors.append(bu_error)

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
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read()


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

    def __init__(self, client: JiraClient, validator: FIValidator, email_domain: Optional[str] = None,
                 fetch_manager_groups: bool = False):
        self.client = client
        self.validator = validator
        self.email_domain = email_domain
        self.fetch_manager_groups = fetch_manager_groups
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
        if self.fetch_manager_groups and assignee_manager_email and '@' in assignee_manager_email:
            # Extract username from email (strip @domain.com)
            manager_username = assignee_manager_email.split('@')[0]
            groups = self.client.get_user_groups(
                manager_username,
                filter_patterns=['*-managers', '*-directors']
            )
            manager_groups = ", ".join(sorted(groups)) if groups else "-"

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
        components = ", ".join(components_list) if components_list else "-"

        versions_list = extract_list_values(fields.get('versions'))
        versions = ", ".join(versions_list) if versions_list else "-"

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
        validation_notes = "; ".join(validation_errors) if validation_errors else "OK"

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
            '_has_errors': len(validation_errors) > 0,
            '_error_count': len(validation_errors),
            '_versions_list': versions_list,
            '_components_list': components_list,
            '_assignee_email': assignee_email,
            '_assignee_manager_email': assignee_manager_email,
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

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total FIs Validated:    {total}")
    print(f"Valid (No Issues):      {without_errors}")
    print(f"Invalid (Has Issues):   {with_errors}")

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

    # Error breakdown
    if with_errors > 0:
        print("\n--- Common Validation Issues ---")
        error_counts = {}
        for r in records:
            notes = r.get('Validation Notes', '')
            if notes and notes != 'OK':
                for error in notes.split('; '):
                    # Normalize error type
                    if 'Invalid version' in error:
                        key = 'Invalid Affects Version/s'
                    elif 'Invalid component' in error:
                        key = 'Invalid Component/s'
                    elif 'Business Unit' in error:
                        key = 'Business Unit Issue'
                    elif 'No Affects Version' in error:
                        key = 'Missing Affects Version/s'
                    elif 'No Component' in error:
                        key = 'Missing Component/s'
                    else:
                        key = error
                    error_counts[key] = error_counts.get(key, 0) + 1

        for error, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            print(f"  {error:35s}: {count:4d}")


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


def write_discovery_file(filepath: str, values: Dict[str, int], sort_func, label: str):
    """
    Write discovered values to file with counts as comments.
    """
    if not values:
        print(f"No {label} values discovered.", file=sys.stderr)
        return

    # Sort values
    sorted_values = sort_func(list(values.keys()))

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {label} discovered from FI data\n")
        f.write(f"# Total unique values: {len(sorted_values)}\n")
        f.write("# Format: value  # count\n")
        f.write("# Remove or comment out invalid entries before using for validation\n")
        f.write("#\n")

        for value in sorted_values:
            count = values[value]
            f.write(f"{value}  # {count}\n")

    print(f"Wrote {len(sorted_values)} {label} to {filepath}", file=sys.stderr)


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

    # Configuration files
    config_group = parser.add_argument_group('Configuration Files')
    config_group.add_argument('-V', '--versions-file', '--vf', type=str,
                              help='File with valid versions (one per line)')
    config_group.add_argument('-C', '--components-file', '--cf', type=str,
                              help='File with valid components (one per line)')
    config_group.add_argument('-B', '--bu-file', '--bf', type=str,
                              help='File with expected Business Unit value')

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
    output_group.add_argument('--email-domain', type=str, metavar='DOMAIN',
                              help='Email domain to construct emails from usernames (e.g., veritas.com)')
    output_group.add_argument('-mg', '--manager-groups', action='store_true',
                              help='Fetch manager groups (*-managers, *-directors) - adds API calls')

    # Discovery mode - build config files
    discovery_group = parser.add_argument_group('Discovery Mode (Build Config Files)')
    discovery_group.add_argument('--build-vf', type=str, metavar='FILE',
                                  help='Discover unique versions and write to FILE (sorted numerically)')
    discovery_group.add_argument('--build-cf', type=str, metavar='FILE',
                                  help='Discover unique components and write to FILE (sorted alphabetically)')
    discovery_group.add_argument('--build-bu', type=str, metavar='FILE',
                                  help='Discover unique Business Units and write to FILE (sorted alphabetically)')

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
    discovery_mode = args.build_vf or args.build_cf or args.build_bu

    # In discovery mode, we don't need validation config files
    if not discovery_mode:
        # Load validation config (all optional - if not provided, that rule is skipped)
        try:
            config = ValidationConfig(
                versions_file=args.versions_file,
                components_file=args.components_file,
                bu_file=args.bu_file,
            )
        except (FileNotFoundError, ValueError) as e:
            print(f"Configuration Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Empty config for discovery mode
        config = ValidationConfig(
            versions_file=None,
            components_file=None,
            bu_file=None,
        )

    # Initialize client and validator
    client = JiraClient(JIRA_BASE_URL, JIRA_TOKEN)
    validator = FIValidator(config, debug=args.debug)
    report = FIReport(client, validator, email_domain=args.email_domain,
                      fetch_manager_groups=args.manager_groups)

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

    # Discovery mode: extract and write config files, then exit
    if discovery_mode:
        print(f"\nDiscovery mode: Analyzing {len(records)} FI records...", file=sys.stderr)
        discovered = discover_values_from_records(records)

        if args.build_vf:
            write_discovery_file(
                args.build_vf,
                discovered['versions'],
                sort_versions,
                'Affects Version/s'
            )

        if args.build_cf:
            write_discovery_file(
                args.build_cf,
                discovered['components'],
                sort_strings,
                'Component/s'
            )

        if args.build_bu:
            write_discovery_file(
                args.build_bu,
                discovered['business_units'],
                sort_strings,
                'Business Unit'
            )

        print("\nDiscovery complete. Review generated files and remove invalid entries.", file=sys.stderr)
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
