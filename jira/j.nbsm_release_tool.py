#!/usr/bin/env python3
"""
NBSM Release Tool - Unified CLI for release management

Extract Jira IDs from git tags, generate reports, and update Jira tickets with build information.

QUICK START:
    # Full release workflow (recommended)
    python3 j.nbsm_release_tool.py process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range

    # Dry run first
    python3 j.nbsm_release_tool.py process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --dry-run

COMMANDS:
    list-tags       List available tags in repository
    extract-jiras   Extract Jira IDs from git commits
    report          Generate detailed Jira report
    update          Update specific Jira tickets directly
    process         Full pipeline: extract -> report -> confirm -> update (RECOMMENDED)
    validate        Pre-release: check Jiras are Resolved/Closed
    check-commits   Find commits missing Jira IDs

TAG SELECTION:
    --tag TAG                   Compare TAG with its predecessor (auto-detect)
    --from TAG1 --to TAG2       Explicit range (single comparison)
    --from TAG1 --to TAG2 --walk-range   Process ALL intermediate tags
    --from COMMIT --to TAG      Use commit hash as start (for first tag with no predecessor)

ENVIRONMENT VARIABLES:
    JIRA_SERVER_NAME    Jira server hostname (required)
    JIRA_ACC_TOKEN      Jira API Bearer token (required)
    NBSM_DEFAULT_REPO   Default repository path (optional)

GIT BRANCH:
    By default, the tool fetches origin/master before any git operations.
    Use --branch to specify a different branch (e.g., --branch origin/develop).

STATE TRANSITIONS:
    --state Done    Transition issues to Done (handles multi-step transitions automatically)

For detailed help with examples:
    python3 j.nbsm_release_tool.py --help
    python3 j.nbsm_release_tool.py <command> --help
"""

import os
import re
import sys
import json
import time
import argparse
import subprocess
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple, Set
from collections import OrderedDict

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_REPO = os.path.expanduser(
    os.getenv('NBSM_DEFAULT_REPO',
              '~/workspace/sandbox/git/stash/NB_Repos/nbsmr_repos/nbservermigrator')
)
JIRA_URL = "https://" + os.getenv('JIRA_SERVER_NAME', 'jira.example.com')
JIRA_API_TOKEN = os.getenv('JIRA_ACC_TOKEN', '')
JIRA_PATTERN = re.compile(r'NBU-\d{5,8}')
TAG_PATTERN = re.compile(r'^(NBSM|NBSVRUP)_(\d+\.\d+)_(\d{4})$')

# Field cache for auto-detection
_field_cache: Optional[Dict[str, Dict]] = None


def parse_env_multi_values(raw_value: str) -> List[str]:
    """Parse env var values that may be space or comma separated."""
    if not raw_value:
        return []
    return [part for part in re.split(r'[\s,]+', raw_value.strip()) if part]


# =============================================================================
# NETWORK RESILIENCE UTILITIES
# =============================================================================

class CircuitBreaker:
    """Circuit breaker pattern to prevent hammering a failing service.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is down, requests fail immediately
    - HALF_OPEN: Testing if service recovered
    """

    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 half_open_max_calls: int = 3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = self.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

    def can_execute(self) -> bool:
        """Check if request should be allowed."""
        if self.state == self.CLOSED:
            return True

        if self.state == self.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time and time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False

        if self.state == self.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls

        return False

    def record_success(self) -> None:
        """Record a successful request."""
        if self.state == self.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                # Service recovered
                self.state = self.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == self.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == self.HALF_OPEN:
            # Service still failing, back to open
            self.state = self.OPEN
            self.success_count = 0
        elif self.state == self.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = self.OPEN
                print(f"[Circuit Breaker] OPEN - {self.failure_count} consecutive failures. "
                      f"Will retry in {self.recovery_timeout}s", file=sys.stderr)

    def get_status(self) -> str:
        """Get current circuit breaker status."""
        return f"state={self.state}, failures={self.failure_count}"


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0,
                       max_delay: float = 30.0, exceptions: tuple = (Exception,)):
    """Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        print(f"[Retry] {func.__name__} failed (attempt {attempt}/{max_retries}): {e}. "
                              f"Retrying in {delay:.1f}s...", file=sys.stderr)
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


# =============================================================================
# JIRA CLIENT
# =============================================================================

class JiraClient:
    """Handles all Jira API interactions with built-in resilience."""

    # Default timeouts (seconds) for different operation types
    TIMEOUT_DEFAULT = 30
    TIMEOUT_FETCH_FIELDS = 60  # Field list can be large
    TIMEOUT_SEARCH = 60       # JQL searches can be slow
    TIMEOUT_UPDATE = 30       # Updates should be quick

    def __init__(self, url: str = JIRA_URL, token: str = JIRA_API_TOKEN,
                 circuit_breaker: CircuitBreaker = None):
        self.url = url.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        self._field_cache: Optional[Dict[str, Dict]] = None
        self._circuit_breaker = circuit_breaker or CircuitBreaker()

    def _format_request_error(self, method: str, url: str, timeout: int,
                              exc: Exception) -> str:
        """Build detailed, actionable error text for Jira request failures."""
        host = urlparse(url).hostname or "unknown-host"
        details = str(exc)

        lines = [
            f"Jira request failed for {method.upper()} {url}",
            f"Host: {host} | Timeout: {timeout}s",
        ]

        if isinstance(exc, requests.exceptions.SSLError):
            lines.append("Cause: TLS/SSL handshake failure while connecting to Jira.")
            if "UNEXPECTED_EOF_WHILE_READING" in details:
                lines.append(
                    "Likely reason: peer/proxy closed the TLS handshake unexpectedly "
                    "(common with VPN/proxy/interception issues)."
                )
            elif "CERTIFICATE_VERIFY_FAILED" in details:
                lines.append(
                    "Likely reason: certificate trust validation failed "
                    "(missing/intercepted/untrusted CA chain)."
                )
        elif isinstance(exc, requests.exceptions.ConnectTimeout):
            lines.append("Cause: connection timeout while trying to reach Jira.")
        elif isinstance(exc, requests.exceptions.ReadTimeout):
            lines.append("Cause: Jira did not respond within the configured timeout.")
        elif isinstance(exc, requests.exceptions.ConnectionError):
            lines.append("Cause: network connection to Jira could not be established.")
        else:
            lines.append("Cause: HTTP request error while communicating with Jira.")

        lines.extend([
            f"Technical details: {details}",
            "Possible fixes:",
            "  1) Verify VPN/corporate network is connected and stable.",
            f"  2) Test connectivity: curl -Iv https://{host}/rest/api/2/myself",
            "  3) Check proxy/TLS inspection settings (try bypassing proxy for Jira host).",
            "  4) Confirm local CA trust/certificates are up to date (certifi/system keychain).",
            "  5) Retry after a few minutes in case of transient Jira or network edge issues.",
        ])
        return "\n".join(lines)

    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None,
                 timeout: int = 30) -> requests.Response:
        """Make an API request with circuit breaker and retry logic."""
        if not HAS_REQUESTS:
            raise RuntimeError("requests library not installed. Run: pip install requests")

        # Check circuit breaker
        if not self._circuit_breaker.can_execute():
            raise RuntimeError(
                f"Jira circuit breaker is OPEN due to repeated failures. "
                f"Status: {self._circuit_breaker.get_status()}. "
                f"Will auto-retry in {self._circuit_breaker.recovery_timeout}s or restart the tool."
            )

        url = f"{self.url}/rest/api/2/{endpoint}"
        max_retries = 5
        retryable_http = {429, 500, 502, 503, 504}

        def _is_transient_ssl_error(exc: Exception) -> bool:
            details = str(exc)
            return (
                "UNEXPECTED_EOF_WHILE_READING" in details
                or "EOF occurred in violation of protocol" in details
                or "SSLEOFError" in details
                or "ConnectionResetError" in details
                or "bad record mac" in details.lower()
            )

        headers = dict(self.headers)
        # Avoid stale keep-alive sockets when the network edge is unstable.
        headers['Connection'] = 'close'

        last_exc: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            session = requests.Session()
            try:
                response = session.request(
                    method, url, headers=headers,
                    json=data, timeout=timeout
                )

                if response.status_code in retryable_http and attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    print(
                        f"Transient Jira HTTP {response.status_code} for {method.upper()} {endpoint} "
                        f"(attempt {attempt}/{max_retries}), retrying in {wait}s...",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                    continue

                # Record success in circuit breaker
                self._circuit_breaker.record_success()
                return response

            except requests.exceptions.SSLError as exc:
                last_exc = exc
                if _is_transient_ssl_error(exc) and attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    print(
                        f"Transient SSL error for {method.upper()} {endpoint} "
                        f"(attempt {attempt}/{max_retries}), retrying in {wait}s...",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                    continue
                self._circuit_breaker.record_failure()
                raise RuntimeError(self._format_request_error(method, url, timeout, exc)) from exc

            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError,
            ) as exc:
                last_exc = exc
                if attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    print(
                        f"Transient network error for {method.upper()} {endpoint} "
                        f"(attempt {attempt}/{max_retries}), retrying in {wait}s...",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                    continue
                self._circuit_breaker.record_failure()
                raise RuntimeError(self._format_request_error(method, url, timeout, exc)) from exc

            except requests.exceptions.RequestException as exc:
                self._circuit_breaker.record_failure()
                raise RuntimeError(self._format_request_error(method, url, timeout, exc)) from exc

            finally:
                session.close()

        if last_exc:
            self._circuit_breaker.record_failure()
            raise RuntimeError(self._format_request_error(method, url, timeout, last_exc)) from last_exc
        raise RuntimeError(f"Jira request failed for {method.upper()} {url} after retries")

    def get_all_fields(self) -> Dict[str, Dict]:
        """Fetch all Jira fields and cache the mapping.

        Uses longer timeout since field list can be large.
        """
        if self._field_cache is not None:
            return self._field_cache

        response = self._request('GET', 'field', timeout=self.TIMEOUT_FETCH_FIELDS)
        response.raise_for_status()

        self._field_cache = {}
        for field in response.json():
            name_lower = field['name'].lower()
            self._field_cache[name_lower] = {
                'id': field['id'],
                'name': field['name'],
                'custom': field.get('custom', False)
            }
        return self._field_cache

    def get_field_id(self, field_name: str) -> Optional[str]:
        """Get field ID by name (case-insensitive)."""
        fields = self.get_all_fields()
        field_info = fields.get(field_name.lower())
        return field_info['id'] if field_info else None

    def get_issue(self, issue_key: str, timeout: int = None) -> Dict:
        """Get issue details."""
        response = self._request('GET', f'issue/{issue_key}',
                                 timeout=timeout or self.TIMEOUT_DEFAULT)
        response.raise_for_status()
        return response.json()

    def get_issues(self, issue_keys: List[str], show_progress: bool = True,
                   continue_on_error: bool = True, max_per_issue_retries: int = 2) -> List[Dict]:
        """Get multiple issues with progress tracking and resilience.

        Args:
            issue_keys: List of Jira issue keys to fetch
            show_progress: Whether to show progress indicator
            continue_on_error: If True, continue fetching other issues even if one fails
            max_per_issue_retries: Retries per individual issue (beyond the built-in request retries)

        Returns:
            List of issue dicts (may be shorter than input if continue_on_error=True and some failed)
        """
        issues = []
        failed_keys = []
        total = len(issue_keys)

        for idx, key in enumerate(issue_keys, 1):
            if show_progress and total > 5:
                # Show progress for larger batches
                pct = (idx / total) * 100
                print(f"  Fetching issues: {idx}/{total} ({pct:.0f}%) - {key}", end='\r')

            last_error = None
            for attempt in range(1, max_per_issue_retries + 1):
                try:
                    issues.append(self.get_issue(key))
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    if attempt < max_per_issue_retries:
                        delay = min(2 ** attempt, 10)
                        print(f"\n  [Retry] {key} fetch failed (attempt {attempt}/{max_per_issue_retries}): "
                              f"{e}. Retrying in {delay}s...", file=sys.stderr)
                        time.sleep(delay)

            if last_error:
                failed_keys.append((key, str(last_error)))
                if continue_on_error:
                    print(f"\n  Warning: Failed to fetch {key}: {last_error}")
                else:
                    raise RuntimeError(f"Failed to fetch {key}: {last_error}")

        if show_progress and total > 5:
            print()  # Clear progress line

        if failed_keys:
            print(f"\n  [!] {len(failed_keys)}/{total} issues failed to fetch:")
            for key, err in failed_keys[:5]:  # Show first 5 failures
                print(f"      {key}: {err[:60]}...")
            if len(failed_keys) > 5:
                print(f"      ... and {len(failed_keys) - 5} more")

        return issues

    def get_issues_bulk(self, issue_keys: List[str], batch_size: int = 50,
                        fields: List[str] = None, show_progress: bool = True) -> Tuple[List[Dict], List[str]]:
        """Bulk fetch issues using JQL search - much faster than individual fetches.

        Args:
            issue_keys: List of Jira issue keys to fetch
            batch_size: Number of issues per JQL query (max ~100, default 50 for safety)
            fields: Specific fields to fetch (None = all fields)
            show_progress: Whether to show progress indicator

        Returns:
            Tuple of (list of issue dicts, list of keys that were not found)
        """
        if not issue_keys:
            return [], []

        all_issues = []
        not_found = set(issue_keys)  # Track which keys we haven't found yet
        total_keys = len(issue_keys)

        # Process in batches (JQL has limits on query length)
        for batch_start in range(0, len(issue_keys), batch_size):
            batch_keys = issue_keys[batch_start:batch_start + batch_size]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (len(issue_keys) + batch_size - 1) // batch_size

            if show_progress:
                print(f"  Bulk fetching: batch {batch_num}/{total_batches} "
                      f"({len(all_issues)}/{total_keys} fetched)", end='\r')

            # Build JQL query: key in (NBU-123, NBU-456, ...)
            keys_str = ', '.join(batch_keys)
            jql = f"key in ({keys_str})"

            # Build request data
            data = {
                'jql': jql,
                'maxResults': batch_size,
                'startAt': 0
            }
            if fields:
                data['fields'] = fields

            try:
                response = self._request('POST', 'search', data=data,
                                        timeout=self.TIMEOUT_SEARCH)
                response.raise_for_status()
                result = response.json()

                batch_issues = result.get('issues', [])
                all_issues.extend(batch_issues)

                # Mark found keys
                for issue in batch_issues:
                    key = issue.get('key')
                    if key in not_found:
                        not_found.remove(key)

            except Exception as e:
                print(f"\n  Warning: Bulk fetch failed for batch {batch_num}: {e}")
                print(f"  Falling back to individual fetch for {len(batch_keys)} issues...")
                # Fallback to individual fetches for this batch
                for key in batch_keys:
                    try:
                        issue = self.get_issue(key)
                        all_issues.append(issue)
                        not_found.discard(key)
                    except Exception as e2:
                        print(f"    Failed to fetch {key}: {e2}")

        if show_progress:
            print()  # Clear progress line

        return all_issues, list(not_found)

    def get_issues_fast(self, issue_keys: List[str], batch_size: int = 50,
                        fields: List[str] = None, show_progress: bool = True,
                        fallback_individual: bool = True) -> List[Dict]:
        """Fast bulk fetch with optional individual fallback for missing issues.

        This is the recommended method for fetching multiple issues.
        Uses JQL bulk fetch (~10-20x faster than individual fetches).

        Args:
            issue_keys: List of Jira issue keys to fetch
            batch_size: Number of issues per JQL query (default 50)
            fields: Specific fields to fetch (None = all)
            show_progress: Whether to show progress indicator
            fallback_individual: If True, try individual fetch for keys not found in bulk

        Returns:
            List of issue dicts (may be shorter than input if some issues don't exist)
        """
        issues, not_found = self.get_issues_bulk(issue_keys, batch_size, fields, show_progress)

        if not_found and fallback_individual:
            print(f"  {len(not_found)} issues not found in bulk, trying individual fetch...")
            for key in not_found:
                try:
                    issue = self.get_issue(key)
                    issues.append(issue)
                except Exception as e:
                    print(f"    {key}: Not found or error - {e}")
        elif not_found:
            print(f"  Note: {len(not_found)} issues not found: {', '.join(not_found[:10])}"
                  f"{'...' if len(not_found) > 10 else ''}")

        return issues

    def update_field(self, issue_key: str, field_name: str, value: str) -> bool:
        """Update a field by name."""
        field_id = self.get_field_id(field_name)
        if not field_id:
            print(f"  Error: Field '{field_name}' not found")
            return False

        data = {"fields": {field_id: value}}
        response = self._request('PUT', f'issue/{issue_key}', data)

        if response.status_code == 204:
            return True
        else:
            print(f"  Error updating {issue_key}: {response.status_code} - {response.text}")
            return False

    def add_label(self, issue_key: str, label: str) -> bool:
        """Add a label to an issue."""
        data = {"update": {"labels": [{"add": label}]}}
        response = self._request('PUT', f'issue/{issue_key}', data)

        if response.status_code == 204:
            return True
        else:
            print(f"  Error adding label to {issue_key}: {response.status_code}")
            return False

    def add_labels(self, issue_key: str, labels: List[str]) -> bool:
        """Add multiple labels to an issue."""
        success = True
        for label in labels:
            if not self.add_label(issue_key, label):
                success = False
        return success

    def set_assignee(self, issue_key: str, assignee: str) -> bool:
        """Set issue assignee."""
        data = {"name": assignee}
        response = self._request('PUT', f'issue/{issue_key}/assignee', data)

        if response.status_code == 204:
            return True
        else:
            print(f"  Error assigning {issue_key}: {response.status_code} - {response.text}")
            return False

    def get_transitions(self, issue_key: str) -> List[Dict]:
        """Get available transitions for an issue."""
        response = self._request('GET', f'issue/{issue_key}/transitions')
        if response.status_code == 200:
            return response.json().get('transitions', [])
        else:
            print(f"  Error getting transitions for {issue_key}: {response.status_code}")
            return []

    def do_transition(self, issue_key: str, transition_id: str, transition_name: str = None) -> bool:
        """Perform a transition on an issue."""
        data = {"transition": {"id": transition_id}}
        response = self._request('POST', f'issue/{issue_key}/transitions', data)

        if response.status_code == 204:
            return True
        else:
            name = f" ({transition_name})" if transition_name else ""
            print(f"  Error transitioning {issue_key}{name}: {response.status_code} - {response.text}")
            return False

    def find_transition_by_name(self, transitions: List[Dict], target_names: List[str]) -> Optional[Dict]:
        """Find a transition matching any of the target names (case-insensitive)."""
        target_lower = [n.lower() for n in target_names]
        for t in transitions:
            if t.get('name', '').lower() in target_lower:
                return t
            # Also check the target status name
            to_status = t.get('to', {}).get('name', '').lower()
            if to_status in target_lower:
                return t
        return None

    def transition_to_done(self, issue_key: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Transition an issue to Done state.

        Handles multi-step transitions if direct Done is not available.
        Tries: Done -> In Progress then Done.

        Returns:
            Tuple of (success, message)
        """
        transitions = self.get_transitions(issue_key)
        if not transitions:
            return False, "No transitions available"

        # Try direct Done transition
        done_transition = self.find_transition_by_name(transitions, ['Done', 'Close', 'Closed'])
        if done_transition:
            if dry_run:
                return True, f"Would transition to {done_transition['name']}"
            if self.do_transition(issue_key, done_transition['id'], done_transition['name']):
                return True, f"Transitioned to {done_transition['name']}"
            return False, "Failed to transition to Done"

        # Try In Progress first, then Done
        progress_transition = self.find_transition_by_name(
            transitions, ['In Progress', 'Start Progress', 'In Development', 'Start Work']
        )
        if progress_transition:
            if dry_run:
                return True, f"Would transition to {progress_transition['name']} then Done"

            if not self.do_transition(issue_key, progress_transition['id'], progress_transition['name']):
                return False, f"Failed to transition to {progress_transition['name']}"

            # Now get transitions again and try Done
            transitions = self.get_transitions(issue_key)
            done_transition = self.find_transition_by_name(transitions, ['Done', 'Close', 'Closed'])
            if done_transition:
                if self.do_transition(issue_key, done_transition['id'], done_transition['name']):
                    return True, f"Transitioned via {progress_transition['name']} to {done_transition['name']}"
                return False, "Failed to transition to Done after In Progress"
            return False, "Done transition not available after In Progress"

        available = [t.get('name', 'Unknown') for t in transitions]
        return False, f"No path to Done found. Available: {', '.join(available)}"

    def get_project_components(self, project_key: str) -> List[Dict]:
        """Get all components for a project."""
        response = self._request('GET', f'project/{project_key}/components')
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  Error fetching components for project {project_key}: {response.status_code}")
            return []

    def find_component_id(self, project_key: str, component_name: str) -> Optional[str]:
        """Find component ID by name."""
        components = self.get_project_components(project_key)
        for comp in components:
            if comp.get('name', '').lower() == component_name.lower():
                return comp.get('id')
        return None

    def set_component(self, issue_key: str, component_id: str) -> bool:
        """Set issue component by component ID."""
        data = {"update": {"components": [{"set": [{"id": component_id}]}]}}
        response = self._request('PUT', f'issue/{issue_key}', data)

        if response.status_code == 204:
            return True
        else:
            print(f"  Error setting component on {issue_key}: {response.status_code}")
            return False

    def set_multi_value_field(self, issue_key: str, field_id: str, values: List[str]) -> bool:
        """Set a multi-value field (like watcher group) on an issue.

        Args:
            issue_key: Jira issue key
            field_id: Field ID (or will attempt name lookup)
            values: List of values (e.g., group names) to set
        """
        # Try to resolve field_id if it's a name
        actual_field_id = field_id
        if not field_id.startswith('customfield_'):
            actual_field_id = self.get_field_id(field_id)
            if not actual_field_id:
                print(f"  Error: Field '{field_id}' not found")
                return False

        # Build the data structure for multi-value field
        field_data = [{"name": v} for v in values]
        data = {"fields": {actual_field_id: field_data}}

        response = self._request('PUT', f'issue/{issue_key}', data)

        if response.status_code == 204:
            return True
        else:
            print(f"  Error setting {field_id} on {issue_key}: {response.status_code}")
            return False

    def set_epic_link(self, issue_key: str, epic_key: str, field_name: str = "Epic Link") -> bool:
        """Set Epic Link on an issue."""
        field_id = self.get_field_id(field_name)
        if not field_id:
            # Fallback to hardcoded custom field ID
            field_id = "customfield_10008"

        data = {"fields": {field_id: epic_key}}
        response = self._request('PUT', f'issue/{issue_key}', data)

        if response.status_code == 204:
            return True
        else:
            print(f"  Error setting epic link on {issue_key}: {response.status_code}")
            return False

    def validate_issue_properties(self, issue_key: str, properties: List[str] = None) -> Dict:
        """Validate and fetch specific properties on an issue.

        Args:
            issue_key: Jira issue key
            properties: List of properties to check:
                       'labels', 'component', 'assignee', 'epic_link', 'watcher_group', 'solution'

        Returns:
            Dict with property names as keys and their values/status
        """
        if not properties:
            properties = ['labels', 'component', 'assignee', 'epic_link', 'solution']

        result = {}

        def _normalize_to_list(value):
            """Normalize Jira field values so None/scalars do not break iteration."""
            if value is None:
                return []
            if isinstance(value, list):
                return value
            return [value]

        try:
            issue = self.get_issue(issue_key)
            fields = issue.get('fields', {})

            for prop in properties:
                prop_name = prop.lower()

                try:
                    if prop_name == 'labels':
                        labels = _normalize_to_list(fields.get('labels'))
                        result['labels'] = {
                            'value': labels,
                            'count': len(labels),
                            'is_set': len(labels) > 0
                        }

                    elif prop_name == 'component':
                        components = _normalize_to_list(fields.get('components'))
                        comp_names = []
                        for comp in components:
                            if isinstance(comp, dict):
                                comp_names.append(comp.get('name') or str(comp.get('id') or ''))
                            elif comp is not None:
                                comp_names.append(str(comp))

                        # Remove empty placeholders
                        comp_names = [name for name in comp_names if name]
                        result['component'] = {
                            'value': comp_names,
                            'count': len(comp_names),
                            'is_set': len(comp_names) > 0
                        }

                    elif prop_name == 'assignee':
                        assignee = fields.get('assignee')
                        assignee_name = assignee.get('displayName') if isinstance(assignee, dict) else None
                        result['assignee'] = {
                            'value': assignee_name,
                            'is_set': assignee_name is not None
                        }

                    elif prop_name == 'epic_link':
                        # Try Epic Link field (customfield_10008 by default)
                        epic_field_id = self.get_field_id('Epic Link')
                        if not epic_field_id:
                            epic_field_id = 'customfield_10008'
                        epic_link = fields.get(epic_field_id)
                        result['epic_link'] = {
                            'value': epic_link,
                            'is_set': epic_link is not None
                        }

                    elif prop_name == 'watcher_group':
                        # Try Watcher Groups field first, then legacy singular name.
                        wg_field_id = self.get_field_id('Watcher Groups')
                        if not wg_field_id:
                            wg_field_id = self.get_field_id('Watcher Group')
                        if not wg_field_id:
                            wg_field_id = 'customfield_33462'
                        watcher_groups = _normalize_to_list(fields.get(wg_field_id))
                        wg_names = []
                        for watcher in watcher_groups:
                            if isinstance(watcher, dict):
                                name = watcher.get('name') or watcher.get('value')
                                if name:
                                    wg_names.append(str(name))
                            elif watcher is not None:
                                wg_names.append(str(watcher))

                        result['watcher_group'] = {
                            'value': wg_names,
                            'count': len(wg_names),
                            'is_set': len(wg_names) > 0
                        }

                    elif prop_name == 'solution':
                        # Try Solution field
                        solution_field_id = self.get_field_id('Solution')
                        if not solution_field_id:
                            solution_field_id = 'customfield_20303'
                        solution = fields.get(solution_field_id)
                        result['solution'] = {
                            'value': solution,
                            'is_set': solution is not None
                        }

                    else:
                        result[prop_name] = {
                            'value': None,
                            'is_set': False,
                            'error': f"Unknown property: {prop}"
                        }

                except Exception as prop_error:
                    # Keep validating other properties even if one property is malformed.
                    result[prop_name] = {
                        'value': None,
                        'is_set': False,
                        'error': str(prop_error)
                    }

            return {'issue_key': issue_key, 'properties': result, 'success': True}

        except Exception as e:
            return {'issue_key': issue_key, 'error': str(e), 'success': False}

    def update_issue(self, issue_key: str, build_id: Optional[str] = None, labels: List[str] = None,
                     assignee: str = None, component_id: str = None, watcher_groups: List[str] = None,
                     epic_key: str = None, watcher_group_field: str = "Watcher Groups",
                     solution_field: str = "Solution") -> Dict:
        """Update an issue with build info, labels, assignee, component, watcher groups, and epic link.

        Returns:
            Dict with 'success', 'build', 'labels', 'assignee', 'component', 'watcher_group', 'epic_link' status
        """
        result = {'success': True, 'build': False, 'labels': False, 'assignee': False,
                  'component': False, 'watcher_group': False, 'epic_link': False}

        # Update Solution field only when build ID is provided.
        if build_id:
            solution_value = f"*Target_Build:* {{{{{build_id}}}}}"
            if self.update_field(issue_key, solution_field, solution_value):
                result['build'] = True
            else:
                result['success'] = False

        # Add labels
        if labels:
            if self.add_labels(issue_key, labels):
                result['labels'] = True
            else:
                result['success'] = False

        # Set assignee
        if assignee:
            if self.set_assignee(issue_key, assignee):
                result['assignee'] = True
            else:
                result['success'] = False

        # Set component
        if component_id:
            if self.set_component(issue_key, component_id):
                result['component'] = True
            else:
                result['success'] = False

        # Set watcher groups
        if watcher_groups:
            if self.set_multi_value_field(issue_key, watcher_group_field, watcher_groups):
                result['watcher_group'] = True
            else:
                result['success'] = False

        # Set epic link
        if epic_key:
            if self.set_epic_link(issue_key, epic_key):
                result['epic_link'] = True
            else:
                result['success'] = False

        return result


# =============================================================================
# GIT EXTRACTOR
# =============================================================================

class GitExtractor:
    """Handles git operations for extracting tags and Jira IDs."""

    DEFAULT_BRANCH = 'origin/master'

    # Network-related error patterns in git output
    NETWORK_ERROR_PATTERNS = [
        'Could not resolve host',
        'Connection refused',
        'Connection timed out',
        'Network is unreachable',
        'unable to access',
        'SSL certificate problem',
        'Failed to connect',
        'couldn\'t connect to server',
        'The remote end hung up unexpectedly',
    ]

    def __init__(self, repo_path: str, branch: str = None):
        self.repo_path = os.path.expanduser(repo_path)
        self.branch = branch or self.DEFAULT_BRANCH
        if not os.path.isdir(self.repo_path):
            raise ValueError(f"Repository not found: {self.repo_path}")

    def _run_git(self, *args, timeout: int = 60) -> str:
        """Run a git command and return output.

        Args:
            *args: Git command arguments
            timeout: Command timeout in seconds (default 60)
        """
        cmd = ['git', '-C', self.repo_path] + list(args)
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Git command timed out after {timeout}s: {' '.join(cmd)}")

        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8', errors='replace')
            raise RuntimeError(f"Git command failed: {error_msg}")
        return result.stdout.decode('utf-8', errors='replace').strip()

    def _is_network_error(self, error_msg: str) -> bool:
        """Check if error message indicates a network issue."""
        error_lower = error_msg.lower()
        return any(pattern.lower() in error_lower for pattern in self.NETWORK_ERROR_PATTERNS)

    def fetch_branch(self, max_retries: int = 3) -> bool:
        """Fetch the configured branch from remote before any operations.

        This ensures we have the latest commits and tags from the remote.

        Args:
            max_retries: Number of retry attempts for network errors

        Returns:
            True if fetch succeeded, False if failed but can continue with local data
        """
        # Parse remote and branch from the full ref (e.g., 'origin/master' -> 'origin', 'master')
        if '/' in self.branch:
            remote, branch_name = self.branch.split('/', 1)
        else:
            remote = 'origin'
            branch_name = self.branch

        print(f"Fetching {remote}/{branch_name} from repository...")

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                # Fetch the specific branch and tags with timeout
                self._run_git('fetch', remote, branch_name, '--tags', timeout=120)
                print(f"Fetch complete: {remote}/{branch_name}")
                return True
            except RuntimeError as e:
                last_error = e
                error_str = str(e)

                if self._is_network_error(error_str):
                    if attempt < max_retries:
                        wait = min(5 * attempt, 30)
                        print(f"  [Retry] Network error during fetch (attempt {attempt}/{max_retries}): "
                              f"{error_str[:80]}...", file=sys.stderr)
                        print(f"  Retrying in {wait}s...", file=sys.stderr)
                        time.sleep(wait)
                        continue
                    else:
                        print(f"Warning: Network error fetching {remote}/{branch_name} "
                              f"after {max_retries} attempts: {error_str}", file=sys.stderr)
                else:
                    # Non-network error, don't retry
                    print(f"Warning: Failed to fetch {remote}/{branch_name}: {e}", file=sys.stderr)
                    break

        print("Continuing with local data (may be stale)...", file=sys.stderr)
        return False

    def list_tags(self, pattern: str = None) -> List[str]:
        """List all tags, optionally filtered by pattern."""
        output = self._run_git('tag', '-l')
        tags = output.split('\n') if output else []

        if pattern:
            regex = re.compile(pattern)
            tags = [t for t in tags if regex.match(t)]

        return sorted(tags)

    def list_matching_tags(self, prefix: str = None, version: str = None) -> List[Tuple[str, int]]:
        """List tags matching NBSM/NBSVRUP pattern with version, sorted by build number.

        Returns:
            List of (tag_name, build_number) tuples, sorted by build number
        """
        all_tags = self.list_tags()
        matching = []

        for tag in all_tags:
            match = TAG_PATTERN.match(tag)
            if match:
                tag_prefix, tag_version, build_num = match.groups()
                if prefix and tag_prefix != prefix:
                    continue
                if version and tag_version != version:
                    continue
                matching.append((tag, int(build_num)))

        return sorted(matching, key=lambda x: x[1])

    def get_latest_tag(self) -> Optional[str]:
        """Get the most recent tag."""
        try:
            return self._run_git('describe', '--tags', '--abbrev=0')
        except RuntimeError:
            return None

    def get_previous_tag(self, tag: str) -> Optional[str]:
        """Get the tag before the specified tag."""
        try:
            return self._run_git('describe', '--tags', '--abbrev=0', f'{tag}~1')
        except RuntimeError:
            return None

    def get_tags_in_range(self, from_tag: str, to_tag: str) -> List[str]:
        """Get all tags between from_tag and to_tag (inclusive).

        If from_tag is not a valid tag (e.g., commit hash), it returns
        [from_tag] + tags from first matching tag to to_tag.

        Parses the tag pattern to find intermediate tags.
        """
        # Parse to_tag to extract prefix and version
        to_match = TAG_PATTERN.match(to_tag)
        if not to_match:
            raise ValueError(f"to_tag must be a valid tag format: {to_tag}")

        to_prefix, to_version, to_build = to_match.groups()
        to_build_num = int(to_build)

        # Check if from_tag is a valid tag or a commit reference
        from_match = TAG_PATTERN.match(from_tag)

        if from_match:
            # Both are valid tags
            from_prefix, from_version, from_build = from_match.groups()

            if from_prefix != to_prefix or from_version != to_version:
                raise ValueError(f"Tags must have same prefix and version: {from_tag} vs {to_tag}")

            from_build_num = int(from_build)

            if from_build_num > to_build_num:
                raise ValueError(f"from_tag build ({from_build_num}) must be <= to_tag build ({to_build_num})")

            # Get all matching tags
            all_matching = self.list_matching_tags(prefix=from_prefix, version=from_version)

            # Filter to range
            tags_in_range = [
                tag for tag, build_num in all_matching
                if from_build_num <= build_num <= to_build_num
            ]

            return tags_in_range
        else:
            # from_tag is a commit hash or other ref - verify it exists
            try:
                self._run_git('rev-parse', '--verify', from_tag)
            except RuntimeError:
                raise ValueError(f"Invalid from reference (not a tag or commit): {from_tag}")

            # Get all tags matching to_tag's pattern, up to to_tag
            all_matching = self.list_matching_tags(prefix=to_prefix, version=to_version)

            tags_in_range = [
                tag for tag, build_num in all_matching
                if build_num <= to_build_num
            ]

            # Prepend the commit ref as starting point
            return [from_tag] + tags_in_range

    def tag_exists(self, tag: str) -> bool:
        """Check if a tag exists in the repository."""
        try:
            self._run_git('rev-parse', '--verify', f'refs/tags/{tag}')
            return True
        except RuntimeError:
            return False

    def ref_exists(self, ref: str) -> bool:
        """Check if a ref (tag or commit) exists in the repository."""
        try:
            self._run_git('rev-parse', '--verify', ref)
            return True
        except RuntimeError:
            return False

    def validate_ref(self, ref: str, ref_name: str = 'reference') -> None:
        """Validate that a ref exists, raising ValueError if not."""
        if TAG_PATTERN.match(ref):
            # It's a tag format - check if tag exists
            if not self.tag_exists(ref):
                raise ValueError(f"Tag not found in repository: {ref}")
        else:
            # It's a commit or other ref
            if not self.ref_exists(ref):
                raise ValueError(f"Invalid {ref_name} (not found): {ref}")

    def get_commits_between(self, from_ref: str, to_ref: str) -> str:
        """Get git log between two refs (full commit messages)."""
        return self._run_git('log', f'{from_ref}..{to_ref}', '--pretty=format:%H %s%n%b')

    def get_commits_last_n(self, count: int) -> str:
        """Get last N commits."""
        return self._run_git('log', f'-n{count}', '--pretty=format:%H %s%n%b')

    def get_commits_since(self, date: str) -> str:
        """Get commits since date."""
        return self._run_git('log', f'--since={date}', '--pretty=format:%H %s%n%b')

    def extract_jira_ids(self, text: str) -> List[str]:
        """Extract unique Jira IDs from text."""
        matches = JIRA_PATTERN.findall(text)
        return sorted(set(matches))

    def get_jiras_between_tags(self, from_tag: str, to_tag: str) -> List[str]:
        """Extract Jira IDs from commits between two tags."""
        commits = self.get_commits_between(from_tag, to_tag)
        return self.extract_jira_ids(commits)

    def get_commits_without_jira(self, from_ref: str, to_ref: str) -> List[str]:
        """Find commits that don't have a Jira ID (checks full commit message)."""
        # Get commits with full body, using delimiter to split
        output = self._run_git('log', f'{from_ref}..{to_ref}',
                               '--pretty=format:---COMMIT---%n%h %s%n%b')
        bad_commits = []
        for commit_block in output.split('---COMMIT---'):
            commit_block = commit_block.strip()
            if commit_block and not JIRA_PATTERN.search(commit_block):
                # Get just the first line (hash + subject) for display
                first_line = commit_block.split('\n')[0] if '\n' in commit_block else commit_block
                bad_commits.append(first_line)
        return bad_commits


# =============================================================================
# RELEASE PROCESSOR
# =============================================================================

class ReleaseProcessor:
    """Main processor for release operations."""

    def __init__(self, repos: List[str], jira_client: JiraClient = None, branch: str = None):
        self.extractors = [GitExtractor(repo, branch=branch) for repo in repos]
        self.jira = jira_client or JiraClient()

    def fetch_all(self) -> None:
        """Fetch the configured branch for all repositories."""
        for extractor in self.extractors:
            extractor.fetch_branch()

    def extract_jiras_single(self, from_tag: str, to_tag: str) -> Dict[str, List[str]]:
        """Extract Jiras for a single tag pair from all repos.

        Returns:
            Dict mapping Jira ID to list of repos it was found in
        """
        jira_repos: Dict[str, List[str]] = {}

        for extractor in self.extractors:
            try:
                jiras = extractor.get_jiras_between_tags(from_tag, to_tag)
                for jira in jiras:
                    if jira not in jira_repos:
                        jira_repos[jira] = []
                    jira_repos[jira].append(extractor.repo_path)
            except Exception as e:
                print(f"  Warning: Failed to extract from {extractor.repo_path}: {e}")

        return jira_repos

    def walk_tag_range(self, from_tag: str, to_tag: str, base_ref: str = None) -> OrderedDict:
        """Walk through tag range and extract Jiras for each step.

        If a Jira appears in multiple tag ranges, it is assigned to the
        HIGHEST (latest) build number.

        Args:
            from_tag: Starting tag (e.g., NBSM_2.8_0001)
            to_tag: Ending tag (e.g., NBSM_2.8_0010)
            base_ref: Optional base commit/tag for what went INTO from_tag

        Returns:
            OrderedDict: {to_tag: [jira_ids]} for each tag pair
        """
        # Get tags in range from first extractor
        tags = self.extractors[0].get_tags_in_range(from_tag, to_tag)

        if len(tags) < 1:
            raise ValueError(f"Need at least 1 tag in range, found: {tags}")

        # Track Jira -> latest tag mapping (higher tag wins)
        jira_to_tag: Dict[str, str] = {}

        # If base_ref provided, extract Jiras that went INTO the first tag
        if base_ref:
            first_tag = tags[0]
            jira_repos = self.extract_jiras_single(base_ref, first_tag)
            for jira in jira_repos.keys():
                jira_to_tag[jira] = first_tag

        # Walk through consecutive tag pairs
        for i in range(len(tags) - 1):
            tag_from = tags[i]
            tag_to = tags[i + 1]

            jira_repos = self.extract_jiras_single(tag_from, tag_to)

            # Update mapping - later tags overwrite earlier ones
            for jira in jira_repos.keys():
                jira_to_tag[jira] = tag_to

        # Invert mapping: tag -> list of Jiras
        result = OrderedDict()
        # Include all tags (including first if base_ref was used)
        for tag in tags:
            result[tag] = []

        for jira, tag in jira_to_tag.items():
            result[tag].append(jira)

        # Sort Jira lists
        for tag in result:
            result[tag] = sorted(result[tag])

        return result

    def get_issue_details(self, jira_ids: List[str]) -> List[Dict]:
        """Fetch details for multiple Jira issues using bulk fetch."""
        return self.jira.get_issues_fast(jira_ids)

    def generate_report(self, jiras_by_tag: Dict[str, List[str]],
                        output_format: str = 'list', fetch_details: bool = True) -> str:
        """Generate a report of Jiras by tag.

        Args:
            jiras_by_tag: Dict mapping tag to list of Jira IDs
            output_format: 'list', 'table', 'json', 'csv', 'markdown', 'club'
            fetch_details: Whether to fetch Jira details from API
        """
        # For JSON, CSV, table, and club with details, we need to collect all data first
        if output_format in ('json', 'csv', 'table', 'club') and fetch_details:
            all_data = []
            for tag, jiras in jiras_by_tag.items():
                if jiras:
                    details = self.get_issue_details(jiras)
                    for issue in details:
                        fields = issue.get('fields', {})
                        all_data.append({
                            'build': tag,
                            'key': issue.get('key', ''),
                            'summary': fields.get('summary', ''),
                            'type': fields.get('issuetype', {}).get('name', ''),
                            'status': fields.get('status', {}).get('name', ''),
                            'assignee': (fields.get('assignee', {}).get('displayName', 'Unassigned')
                                        if fields.get('assignee') else 'Unassigned'),
                            'priority': fields.get('priority', {}).get('name', ''),
                        })

            if output_format == 'json':
                return json.dumps(all_data, indent=2)
            elif output_format == 'csv':
                lines = ['Build,Key,Summary,Status,Assignee,Priority']
                for row in all_data:
                    # Escape quotes in summary
                    summary = row['summary'].replace('"', '""')
                    lines.append(f'"{row["build"]}","{row["key"]}","{summary}","{row["status"]}","{row["assignee"]}","{row["priority"]}"')
                return '\n'.join(lines)
            elif output_format in ('table', 'club'):
                if HAS_TABULATE:
                    rows = []
                    for row in all_data:
                        summary = (row['summary'][:80] + '...') if len(row['summary']) > 80 else row['summary']
                        rows.append([
                            row['build'],
                            row['key'],
                            row['type'],
                            row['status'],
                            row['assignee'],
                            row['priority'],
                            summary,
                        ])
                    return tabulate(
                        rows,
                        headers=['Build', 'Key', 'Type', 'Status', 'Assignee', 'Priority', 'Summary'],
                        tablefmt='grid' if output_format == 'table' else 'simple'
                    )
                else:
                    lines = []
                    for row in all_data:
                        lines.append(f"{row['build']}  {row['key']}  {row['type']}  {row['status']}  {row['assignee']}  {row['priority']}  {row['summary'][:80]}")
                    return '\n'.join(lines)

        if output_format == 'json':
            return json.dumps(jiras_by_tag, indent=2)

        # CSV without details - simple format
        if output_format == 'csv':
            lines = ['Build,Key']
            for tag, jiras in jiras_by_tag.items():
                for jira in jiras:
                    lines.append(f'"{tag}","{jira}"')
            return '\n'.join(lines)

        # Table/club without details
        if output_format in ('table', 'club'):
            rows = []
            for tag, jiras in jiras_by_tag.items():
                for jira in jiras:
                    rows.append([tag, jira])
            if HAS_TABULATE:
                return tabulate(
                    rows,
                    headers=['Build', 'Key'],
                    tablefmt='grid' if output_format == 'table' else 'simple'
                )
            else:
                lines = []
                for row in rows:
                    lines.append(f"{row[0]}  {row[1]}")
                return '\n'.join(lines)

        lines = []

        for tag, jiras in jiras_by_tag.items():
            lines.append(f"\n{'='*60}")
            lines.append(f"Build: {tag}")
            lines.append(f"{'='*60}")

            if not jiras:
                lines.append("  (no new Jiras)")
                continue

            if fetch_details:
                details = self.get_issue_details(jiras)

                if output_format == 'markdown':
                    for issue in details:
                        fields = issue.get('fields', {})
                        key = issue.get('key', '')
                        summary = fields.get('summary', '')
                        status = fields.get('status', {}).get('name', '')
                        assignee = (fields.get('assignee', {}).get('displayName', 'Unassigned')
                                   if fields.get('assignee') else 'Unassigned')
                        priority = fields.get('priority', {}).get('name', '')
                        lines.append(f"- **{key}**: {summary} ({status}, {assignee}, {priority})")
                else:
                    for issue in details:
                        fields = issue.get('fields', {})
                        lines.append(f"  {issue.get('key')}: {fields.get('summary', '')[:70]}")
            else:
                for jira in jiras:
                    lines.append(f"  {jira}")

        # Summary
        total = sum(len(jiras) for jiras in jiras_by_tag.values())
        lines.append(f"\n{'='*60}")
        lines.append(f"Total: {total} Jiras across {len(jiras_by_tag)} builds")
        lines.append(f"{'='*60}")

        return '\n'.join(lines)

    def update_jiras(self, jiras_by_tag: Dict[str, List[str]],
                     labels: List[str] = None, assignee: str = None,
                     state: str = None, dry_run: bool = False,
                     confirm: bool = True, project_key: str = None,
                     component_name: str = None, watcher_groups: List[str] = None,
                     epic_key: str = None, watcher_group_field: str = "Watcher Groups",
                     labels_from_env: bool = False, legacy_default_labels: bool = False,
                     metadata_from_env: bool = False) -> Dict:
        """Update Jiras with build IDs, labels, assignee, component, watcher groups, epic link, and state transitions.

        Args:
            jiras_by_tag: Dict mapping build_id (tag) to list of Jira IDs.
                          For metadata-only updates without Solution change, build_id can be empty.
            labels: Labels to add (e.g., ['Verify'])
            assignee: Assignee username
            state: Target state (e.g., 'Done')
            dry_run: If True, only show what would be done
            confirm: If True, prompt for confirmation
            project_key: Project key for component lookup (e.g., 'NBU')
            component_name: Component name to set
            watcher_groups: List of watcher group names to set
            epic_key: Epic key to link
            watcher_group_field: Watcher group field ID or name (default: 'Watcher Groups')
            labels_from_env: Use JIRA_LABELS env var if --labels not provided
            legacy_default_labels: Use default label 'NBServerMigrator' if no labels specified
            metadata_from_env: Use env vars for missing metadata values:
                              JIRA_LABELS, JIRA_COMPONENT, JIRA_EPIC_LINK, JIRA_WATCHER_GROUP

        Returns:
            Dict with success/failure counts
        """
        # Resolve labels with fallback logic
        resolved_labels = labels if labels else None
        resolved_component_name = component_name
        resolved_epic_key = epic_key
        resolved_watcher_groups = watcher_groups[:] if watcher_groups else None

        if not resolved_labels:
            if labels_from_env:
                env_labels = os.getenv('JIRA_LABELS', '').strip()
                if env_labels:
                    resolved_labels = parse_env_multi_values(env_labels)
            elif legacy_default_labels:
                resolved_labels = ['NBServerMigrator']
            # If nothing specified, no labels (let commands set their own defaults)

        # Unified env fallback for metadata values (does not override explicit CLI args)
        if metadata_from_env:
            env_labels = parse_env_multi_values(os.getenv('JIRA_LABELS', ''))
            env_component = os.getenv('JIRA_COMPONENT', '').strip()
            env_epic_link = os.getenv('JIRA_EPIC_LINK', '').strip()
            env_watcher_groups = parse_env_multi_values(os.getenv('JIRA_WATCHER_GROUP', ''))

            if not resolved_labels and env_labels:
                resolved_labels = env_labels
            if not resolved_component_name and env_component:
                resolved_component_name = env_component
            if not resolved_epic_key and env_epic_link:
                resolved_epic_key = env_epic_link
            if not resolved_watcher_groups and env_watcher_groups:
                resolved_watcher_groups = env_watcher_groups

        has_build_update = any(bool(tag) for tag in jiras_by_tag.keys())
        has_metadata_update = any([
            bool(resolved_labels),
            bool(assignee),
            bool(resolved_component_name),
            bool(resolved_watcher_groups),
            bool(resolved_epic_key),
            bool(state)
        ])

        if not has_build_update and not has_metadata_update:
            print("Error: No update actions resolved. Provide --build-id and/or metadata/state inputs.")
            return {'total': 0, 'success': 0, 'failed': 0, 'error': 'no_update_actions'}

        total = sum(len(jiras) for jiras in jiras_by_tag.values())

        if total == 0:
            print("No Jiras to update.")
            return {'total': 0, 'success': 0, 'failed': 0}

        # Collect all Jira IDs for fetching details
        all_jira_ids = []
        for jiras in jiras_by_tag.values():
            all_jira_ids.extend(jiras)

        # Fetch issue details for reporter check (needed for state=Done on Defects)
        issue_details = {}
        defects_to_reassign = []
        if state == 'Done':
            print("\nFetching issue details for state transition...")
            issues = self.jira.get_issues_fast(all_jira_ids)
            for issue in issues:
                key = issue.get('key', '')
                fields = issue.get('fields', {})
                issue_type = fields.get('issuetype', {}).get('name', '')
                reporter = fields.get('reporter', {})
                reporter_name = reporter.get('name', '') if reporter else ''
                reporter_display = reporter.get('displayName', 'Unknown') if reporter else 'Unknown'
                current_assignee = fields.get('assignee', {})
                current_assignee_name = current_assignee.get('name', '') if current_assignee else ''

                issue_details[key] = {
                    'type': issue_type,
                    'reporter_name': reporter_name,
                    'reporter_display': reporter_display,
                    'current_assignee': current_assignee_name
                }

                # Check if Defect needs reassignment to reporter
                if issue_type.lower() == 'defect' and reporter_name and reporter_name != current_assignee_name:
                    defects_to_reassign.append({
                        'key': key,
                        'reporter_name': reporter_name,
                        'reporter_display': reporter_display
                    })

        # Show what will be done
        print(f"\n{'='*60}")
        print("UPDATE PREVIEW")
        print(f"{'='*60}")
        print(f"Total Jiras to update: {total}")
        print(f"Build ID update: {'enabled' if has_build_update else 'disabled'}")
        print(f"Labels to add: {', '.join(resolved_labels) if resolved_labels else '(none)'}")
        print(f"Assignee: {assignee or '(unchanged)'}")
        print(f"Component: {resolved_component_name or '(unchanged)'}")
        print(f"Watcher Groups: {', '.join(resolved_watcher_groups) if resolved_watcher_groups else '(none)'}")
        print(f"Epic Link: {resolved_epic_key or '(none)'}")
        print(f"State transition: {state or '(none)'}")
        print()

        for tag, jiras in jiras_by_tag.items():
            if jiras:
                tag_label = tag if tag else '(no build-id)'
                print(f"  {tag_label}: {', '.join(jiras)}")

        # Resolve component ID if component name provided
        component_id = None
        if resolved_component_name and project_key:
            print(f"\nResolving component '{resolved_component_name}' for project '{project_key}'...")
            component_id = self.jira.find_component_id(project_key, resolved_component_name)
            if not component_id:
                print(f"Warning: Component '{resolved_component_name}' not found in project '{project_key}'")
        elif resolved_component_name and not project_key:
            print("Error: --project-key required when using --component")
            return {'total': total, 'success': 0, 'failed': 0, 'error': 'project_key_required'}

        # Show Defects that need reassignment to reporter before Done
        reassign_confirmed = {}
        if defects_to_reassign and confirm:
            print(f"\n{'='*60}")
            print("DEFECTS - ASSIGN TO REPORTER BEFORE DONE")
            print(f"{'='*60}")
            print("The following Defects should be assigned to their reporter before moving to Done:")
            print()
            for defect in defects_to_reassign:
                print(f"  {defect['key']}: Assign to {defect['reporter_display']} ({defect['reporter_name']})")

            print()
            response = input("Assign these Defects to their reporters? [Y/n]: ").strip().lower()
            if response != 'n':
                for defect in defects_to_reassign:
                    reassign_confirmed[defect['key']] = defect['reporter_name']

        if dry_run:
            print("\n[DRY RUN] No changes made.")
            if state:
                print(f"Would transition {total} issues to {state}")
            if reassign_confirmed:
                print(f"Would reassign {len(reassign_confirmed)} Defects to their reporters")
            return {'total': total, 'success': 0, 'failed': 0, 'dry_run': True}

        # Confirm
        if confirm:
            print()
            response = input("Proceed with update? [y/N]: ").strip().lower()
            if response != 'y':
                print("Aborted.")
                return {'total': total, 'success': 0, 'failed': 0, 'aborted': True}

        # Perform updates
        print(f"\n{'='*60}")
        print("UPDATING JIRAS")
        print(f"{'='*60}")

        success_count = 0
        failed_count = 0

        for tag, jiras in jiras_by_tag.items():
            for jira_id in jiras:
                if tag:
                    print(f"\nUpdating {jira_id} with build {tag}...")
                else:
                    print(f"\nUpdating {jira_id} (metadata only; no build update)...")
                result = self.jira.update_issue(
                    jira_id,
                    build_id=tag or None,
                    labels=resolved_labels,
                    assignee=assignee,
                    component_id=component_id,
                    watcher_groups=resolved_watcher_groups,
                    epic_key=resolved_epic_key,
                    watcher_group_field=watcher_group_field
                )

                status = []
                if result['success']:
                    if result['build']:
                        status.append('build')
                    if result['labels']:
                        status.append('labels')
                    if result['assignee']:
                        status.append('assignee')
                    if result['component']:
                        status.append('component')
                    if result['watcher_group']:
                        status.append('watcher_group')
                    if result['epic_link']:
                        status.append('epic_link')

                # Reassign Defects to reporter before state transition
                if jira_id in reassign_confirmed:
                    reporter = reassign_confirmed[jira_id]
                    if self.jira.set_assignee(jira_id, reporter):
                        status.append(f'assignee->reporter')
                    else:
                        print(f"  [!] Failed to reassign to reporter")

                # State transition
                if state == 'Done':
                    success, msg = self.jira.transition_to_done(jira_id, dry_run=False)
                    if success:
                        status.append(f'state:{msg}')
                    else:
                        print(f"  [!] State transition failed: {msg}")
                        result['success'] = False

                if result['success']:
                    success_count += 1
                    print(f"  [OK] Updated: {', '.join(status)}")
                else:
                    failed_count += 1
                    print("  [X] Failed")

        print(f"\n{'='*60}")
        print(f"SUMMARY: {success_count} succeeded, {failed_count} failed")
        print(f"{'='*60}")

        return {'total': total, 'success': success_count, 'failed': failed_count}


# =============================================================================
# CLI
# =============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='NBSM Release Tool - Manage releases and update Jira tickets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
================================================================================
EXAMPLES
================================================================================

LIST-TAGS - Show available tags
-------------------------------
  # List all NBSM/NBSVRUP tags
  %(prog)s list-tags

  # Filter by version
  %(prog)s list-tags --version 2.9

  # Filter by prefix (NBSM or NBSVRUP)
  %(prog)s list-tags --prefix NBSM

  # Show tags in a specific range
  %(prog)s list-tags --from NBSM_2.9_0001 --to NBSM_2.9_0010

  # Use custom repository
  %(prog)s list-tags --repo ~/my/custom/repo

  # Use a different branch
  %(prog)s list-tags --branch origin/develop

EXTRACT-JIRAS - Extract Jira IDs from git
-----------------------------------------
  # Single tag pair (auto-detect predecessor)
  %(prog)s extract-jiras --tag NBSM_2.9_0010

  # Explicit tag range (single comparison)
  %(prog)s extract-jiras --from NBSM_2.9_0009 --to NBSM_2.9_0010

  # Walk entire range (process all intermediate tags)
  %(prog)s extract-jiras --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range

  # Full version range - auto-resolve first to latest tag
  %(prog)s extract-jiras --full-range NBSM_2.9 --walk-range
  %(prog)s extract-jiras --full-range NBSVRUP_3.0 --walk-range

  # Include what went INTO the first tag (using explicit base)
  %(prog)s extract-jiras --from NBSM_2.8_0001 --to NBSM_2.8_0010 --base NBSM_2.7_0050 --walk-range
  %(prog)s extract-jiras --full-range NBSM_2.8 --base abc1234 --walk-range

  # Auto-detect base from previous version (NBSM_2.7's last tag)
  %(prog)s extract-jiras --from NBSM_2.8_0001 --to NBSM_2.8_0010 --auto-base --walk-range
  %(prog)s extract-jiras --full-range NBSM_2.8 --auto-base --walk-range

  # Output as JSON
  %(prog)s extract-jiras --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --format json

  # Use latest tag (auto-detect)
  %(prog)s extract-jiras

  # Use a different branch
  %(prog)s extract-jiras --branch origin/develop --tag NBSM_2.9_0010

REPORT - Generate Jira report
-----------------------------
    # List format (default) grouped by build with Jira details
  %(prog)s report --from NBSM_2.9_0009 --to NBSM_2.9_0010

    # Bordered table format
    %(prog)s report --from NBSM_2.9_0009 --to NBSM_2.9_0010 --format table

  # Walk range and show all builds
  %(prog)s report --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range

  # Full version range with auto-base (includes first tag's Jiras)
  %(prog)s report --full-range NBSM_2.8 --auto-base --walk-range --format club

  # Full version range - auto-resolve first to latest tag
  %(prog)s report --full-range NBSM_2.9 --walk-range --format club

  # Markdown format (for release notes)
  %(prog)s report --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --format markdown

  # JSON format
  %(prog)s report --from NBSM_2.9_0001 --to NBSM_2.9_0010 --format json

  # Skip fetching Jira details (just show IDs)
  %(prog)s report --from NBSM_2.9_0009 --to NBSM_2.9_0010 --no-fetch

  # Use a different branch
  %(prog)s report --branch origin/develop --from NBSM_2.9_0001 --to NBSM_2.9_0010

UPDATE - Update Jira tickets directly
-------------------------------------
    # Update specific Jiras with build ID and labels
  %(prog)s update NBU-12345 NBU-12346 --build-id NBSM_2.9_0010 --labels Verify

    # Metadata-only update (no Solution/build update)
    %(prog)s update NBU-12345 --project-key NBU --component Commandos --labels Verify

  # Add multiple labels
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --labels Verify,Reviewed

  # Update with assignee
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --labels Verify --assignee john.doe

  # Set component (requires --project-key)
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --project-key NBU --component Commandos

  # Set watcher group (single or multiple)
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --watcher-group DL
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --watcher-group DL1,DL2

  # Set epic link
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --epic-link NBU-99999

  # Full metadata update (legacy script behavior)
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --project-key NBU --component Commandos --watcher-group DL --epic-link NBU-99999 --labels Verify,Reviewed

  # Use env-based labels (JIRA_LABELS env var)
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --labels-from-env
  export JIRA_LABELS="NBServerMigrator NBServerMigrator_2.7"
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --labels-from-env

    # Use env-based metadata (fills missing metadata values)
    export JIRA_LABELS="Verify Reviewed"
    export JIRA_COMPONENT="Commandos"
    export JIRA_EPIC_LINK="NBU-99999"
    export JIRA_WATCHER_GROUP="DL1 DL2"
    %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --project-key NBU --metadata-from-env

  # Legacy default labels (NBServerMigrator only)
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --legacy-default-labels

  # Dry run (preview only)
  %(prog)s update NBU-12345 NBU-12346 --build-id NBSM_2.9_0010 --dry-run

  # Skip confirmation prompt
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --no-confirm

PROCESS - Full pipeline (recommended)
-------------------------------------
  # Single tag pair: extract, report, confirm, update
  %(prog)s process --tag NBSM_2.9_0010 --labels Verify

  # Explicit range (single comparison)
  %(prog)s process --from NBSM_2.9_0009 --to NBSM_2.9_0010 --labels Verify

  # Walk entire range (each Jira tagged with its first appearance)
  %(prog)s process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --labels Verify

  # With assignee
  %(prog)s process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --labels Verify --assignee john.doe

  # With component, watcher group, epic link
  %(prog)s process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --project-key NBU --component Commandos --watcher-group DL --epic-link NBU-99999 --labels Verify

  # Full metadata update with all options
  %(prog)s process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --project-key NBU --component Commandos --watcher-group DL1,DL2 --epic-link NBU-99999 --labels Verify,Reviewed --assignee john.doe

  # Use env labels for release (migration labels from environment)
  %(prog)s process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --labels-from-env --project-key NBU --component Commandos

  # Legacy mode (default labels + component + watcher group)
  %(prog)s process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --legacy-default-labels --project-key NBU --component Commandos

  # Dry run (preview without making changes)
  %(prog)s process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --dry-run

  # Skip confirmation (use with caution)
  %(prog)s process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --no-confirm

  # Skip report display (faster)
  %(prog)s process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --skip-report

  # Use custom repository
  %(prog)s process --repo ~/my/repo --from NBSM_2.9_0009 --to NBSM_2.9_0010

  # Use a different branch
  %(prog)s process --branch origin/release-2.9 --from NBSM_2.9_0009 --to NBSM_2.9_0010

VALIDATE - Pre-release validation
---------------------------------
  # Check if all Jiras are Resolved/Closed
  %(prog)s validate --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range

  # Fail exit code if any Jira not resolved
  %(prog)s validate --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --require-resolved

  # Use a different branch
  %(prog)s validate --branch origin/release-2.9 --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range

VALIDATE-PROPERTIES - Check properties set on issues
----------------------------------------------------
  # Check all default properties on single issue (labels, component, assignee, solution, epic-link, watcher-group)
  %(prog)s validate-properties NBU-12345

  # Check multiple issues
  %(prog)s validate-properties NBU-12345 NBU-12346 NBU-12347

  # Check specific properties only
  %(prog)s validate-properties NBU-12345 --properties labels,component,solution

  # Check all properties with JSON output
  %(prog)s validate-properties NBU-12345 NBU-12346 --format json

  # Summary output (only shows if set or not)
  %(prog)s validate-properties NBU-12345 --format summary

  # Check epic-link and watcher-group only
  %(prog)s validate-properties NBU-12345 --properties epic_link,watcher_group

    # Extract Jira IDs from tag range, then validate properties
    %(prog)s validate-properties --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range

    # Validate properties for all Jiras in a full version range
    %(prog)s validate-properties --full-range NBSM_2.9 --walk-range

CHECK-COMMITS - Find commits without Jira IDs
----------------------------------------------
  # Find bad commits (missing NBU-xxxxx)
  %(prog)s check-commits --from NBSM_2.9_0001 --to NBSM_2.9_0010

  # Check latest tag
  %(prog)s check-commits --tag NBSM_2.9_0010

  # Use a different branch
  %(prog)s check-commits --branch origin/develop --from NBSM_2.9_0001 --to NBSM_2.9_0010

================================================================================
TAG RANGE WALK EXPLAINED
================================================================================

When using --walk-range with --from NBSM_2.9_0001 --to NBSM_2.9_0010:

  The tool processes each consecutive tag pair:
    NBSM_2.9_0001 -> NBSM_2.9_0002: Jiras updated with build NBSM_2.9_0002
    NBSM_2.9_0002 -> NBSM_2.9_0003: Jiras updated with build NBSM_2.9_0003
    ...
    NBSM_2.9_0009 -> NBSM_2.9_0010: Jiras updated with build NBSM_2.9_0010

  Each Jira is tagged with the build where it FIRST appeared.
  Duplicates across ranges are automatically skipped.

================================================================================
ENVIRONMENT VARIABLES
================================================================================

  JIRA_SERVER_NAME    Jira server hostname (required for Jira operations)
  JIRA_ACC_TOKEN      Jira API Bearer token (required for Jira operations)
  NBSM_DEFAULT_REPO   Default repository path (optional)

================================================================================
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Common arguments
    def add_common_args(p):
        p.add_argument('-r', '--repo', action='append', dest='repos',
                       help=f'Repository path (default: {DEFAULT_REPO})')
        p.add_argument('-b', '--branch', default='origin/master',
                       help='Git branch to fetch before operations (default: origin/master)')

    def add_range_args(p):
        p.add_argument('-t', '--tag', help='Single tag (compare with predecessor)')
        p.add_argument('-f', '--from', dest='from_tag', help='Starting tag')
        p.add_argument('-T', '--to', dest='to_tag', help='Ending tag')
        p.add_argument('-F', '--full-range', dest='full_range',
                       help='Version series (e.g., NBSM_2.9) - auto-resolve first to latest tag')
        p.add_argument('-B', '--base', dest='base_ref',
                       help='Base commit/tag for first build (what went INTO first tag)')
        p.add_argument('-a', '--auto-base', action='store_true',
                       help='Auto-detect base from previous version (e.g., last tag of NBSM_2.7 for NBSM_2.8)')
        p.add_argument('-w', '--walk-range', action='store_true',
                       help='Process all intermediate tags in range')
        p.add_argument('-c', '--commits', type=int, help='Last N commits instead of tags')
        p.add_argument('-s', '--since', help='Commits since date (YYYY-MM-DD)')

    # list-tags
    p_tags = subparsers.add_parser('list-tags',
        help='List available tags',
        description='List NBSM/NBSVRUP tags from the repository, optionally filtered by version or range.')
    add_common_args(p_tags)
    p_tags.add_argument('-v', '--version', help='Filter by version (e.g., 2.9)')
    p_tags.add_argument('-p', '--prefix', help='Filter by prefix (NBSM or NBSVRUP)')
    p_tags.add_argument('-f', '--from', dest='from_tag', help='Starting tag for range')
    p_tags.add_argument('-T', '--to', dest='to_tag', help='Ending tag for range')

    # extract-jiras
    p_extract = subparsers.add_parser('extract-jiras',
        help='Extract Jira IDs from git',
        description='Extract NBU-xxxxx Jira IDs from git commit messages between tags.')
    add_common_args(p_extract)
    add_range_args(p_extract)
    p_extract.add_argument('-o', '--format', choices=['list', 'json'], default='list',
                           help='Output format (default: list)')

    # report
    p_report = subparsers.add_parser('report',
        help='Generate Jira report',
        description='Generate a report showing Jira details for tickets found in git history.')
    add_common_args(p_report)
    add_range_args(p_report)
    p_report.add_argument('-o', '--format', choices=['list', 'table', 'json', 'csv', 'markdown', 'club'],
                          default='list', help='Output format (default: list)')
    p_report.add_argument('-N', '--no-fetch', action='store_true',
                          help='Skip fetching Jira details (just show IDs)')

    # update
    p_update = subparsers.add_parser('update',
        help='Update Jira tickets',
        description='Directly update specified Jira tickets with build ID, labels, assignee, component, watcher groups, and epic link.')
    p_update.add_argument('jiras', nargs='*', help='Jira IDs to update (e.g., NBU-12345 NBU-12346)')
    p_update.add_argument('-i', '--build-id',
                          help='Build ID for Solution field (e.g., NBSM_2.9_0010). Optional for metadata-only updates.')
    p_update.add_argument('-l', '--labels', type=lambda s: s.split(','), default=[],
                          help='Comma-separated labels to add (e.g., Verify,Reviewed)')
    p_update.add_argument('-A', '--assignee', help='Assignee username')
    p_update.add_argument('-P', '--project-key', help='Project key for component lookup (e.g., NBU)')
    p_update.add_argument('-C', '--component', help='Component name to set (requires -P/--project-key)')
    p_update.add_argument('-W', '--watcher-group', type=lambda s: s.split(','),
                          help='Comma-separated watcher group names to set')
    p_update.add_argument('-G', '--watcher-group-field', default='Watcher Groups',
                          help='Watcher group field ID or name (default: Watcher Groups)')
    p_update.add_argument('-E', '--epic-link', help='Epic key to link (e.g., NBU-99999)')
    p_update.add_argument('-L', '--labels-from-env', action='store_true',
                          help='Use JIRA_LABELS env var if -l/--labels not provided')
    p_update.add_argument('-M', '--metadata-from-env', action='store_true',
                          help='Fill missing labels/component/epic-link/watcher-group from env: JIRA_LABELS, JIRA_COMPONENT, JIRA_EPIC_LINK, JIRA_WATCHER_GROUP')
    p_update.add_argument('-D', '--legacy-default-labels', action='store_true',
                          help='Use default label "NBServerMigrator" if no labels specified')
    p_update.add_argument('-S', '--state', choices=['Done'],
                          help='Transition issues to state (e.g., Done). Handles multi-step transitions.')
    p_update.add_argument('-n', '--dry-run', action='store_true',
                          help='Preview changes without applying')
    p_update.add_argument('-y', '--no-confirm', action='store_true',
                          help='Skip confirmation prompt (use with caution)')

    # process (full pipeline)
    p_process = subparsers.add_parser('process',
        help='Full pipeline: extract, report, update',
        description='''Full release pipeline: extract Jiras from git tags, generate report,
and update Jira tickets with build ID, labels, component, watcher groups, epic link, and state. This is the recommended command for release workflows.''')
    add_common_args(p_process)
    add_range_args(p_process)
    p_process.add_argument('-l', '--labels', type=lambda s: s.split(','),
                           help='Labels to add (comma-separated, e.g., Verify,Reviewed). If not provided with -L/--labels-from-env or -D/--legacy-default-labels, uses Verify as default.')
    p_process.add_argument('-A', '--assignee', help='Assignee username')
    p_process.add_argument('-P', '--project-key', help='Project key for component lookup (e.g., NBU)')
    p_process.add_argument('-C', '--component', help='Component name to set (requires -P/--project-key)')
    p_process.add_argument('-W', '--watcher-group', type=lambda s: s.split(','),
                          help='Comma-separated watcher group names to set')
    p_process.add_argument('-G', '--watcher-group-field', default='Watcher Groups',
                          help='Watcher group field ID or name (default: Watcher Groups)')
    p_process.add_argument('-E', '--epic-link', help='Epic key to link (e.g., NBU-99999)')
    p_process.add_argument('-L', '--labels-from-env', action='store_true',
                          help='Use JIRA_LABELS env var instead of -l/--labels')
    p_process.add_argument('-D', '--legacy-default-labels', action='store_true',
                          help='Use default label "NBServerMigrator" instead of -l/--labels')
    p_process.add_argument('-S', '--state', choices=['Done'],
                           help='Transition issues to state (e.g., Done). Handles multi-step transitions.')
    p_process.add_argument('-n', '--dry-run', action='store_true',
                           help='Preview changes without applying')
    p_process.add_argument('-y', '--no-confirm', action='store_true',
                           help='Skip confirmation prompt (use with caution)')
    p_process.add_argument('-R', '--skip-report', action='store_true',
                           help='Skip report generation (faster)')

    # validate
    p_validate = subparsers.add_parser('validate',
        help='Validate Jiras before release',
        description='Pre-release validation: check that all Jiras are in Resolved/Closed status.')
    add_common_args(p_validate)
    add_range_args(p_validate)
    p_validate.add_argument('-R', '--require-resolved', action='store_true',
                            help='Exit with error code if any Jira is not Resolved/Closed')

    # validate-properties
    p_validate_props = subparsers.add_parser('validate-properties',
        help='Validate properties set on Jira issues',
        description='Check and display specific properties on Jira keys (labels, component, assignee, epic-link, watcher-group, solution). You can pass Jira keys directly or extract them from a tag range.')
    add_common_args(p_validate_props)
    add_range_args(p_validate_props)
    p_validate_props.add_argument('keys', nargs='*', help='Jira IDs to validate (e.g., NBU-12345 NBU-12346)')
    p_validate_props.add_argument('-p', '--properties', type=lambda s: [p.strip().lower() for p in s.split(',')],
                                  default=['labels', 'component', 'assignee', 'solution', 'epic_link', 'watcher_group'],
                                  help='Comma-separated properties to check (default: labels,component,assignee,solution,epic_link,watcher_group)')
    p_validate_props.add_argument('-o', '--format', choices=['list', 'table', 'json', 'summary'],
                                  default='table',
                                  help='Output format (default: table)')

    # check-commits
    p_check = subparsers.add_parser('check-commits',
        help='Find commits without Jira IDs',
        description='Quality check: find commits that do not contain a valid NBU-xxxxx Jira ID.')
    add_common_args(p_check)
    add_range_args(p_check)

    # help
    subparsers.add_parser('help', help='Show detailed help with examples')

    return parser.parse_args()


def validate_jira_ids(jira_ids: List[str]) -> None:
    """Validate Jira ID format."""
    invalid = []
    for jira_id in jira_ids:
        if not JIRA_PATTERN.match(jira_id):
            invalid.append(jira_id)
    if invalid:
        raise ValueError(f"Invalid Jira ID format: {', '.join(invalid)}. Expected: NBU-NNNNN")


def resolve_tags(args, extractor: GitExtractor) -> Tuple[str, str, Optional[str]]:
    """Resolve from_tag, to_tag, and base_ref from arguments.

    Returns:
        Tuple of (from_tag, to_tag, base_ref) where base_ref is optional
    """
    base_ref = None

    # Handle explicit --base
    if hasattr(args, 'base_ref') and args.base_ref:
        base_ref = args.base_ref
        extractor.validate_ref(base_ref, 'base')

    if args.tag:
        to_tag = args.tag
        extractor.validate_ref(to_tag, 'tag')  # Validate tag exists
        from_tag = extractor.get_previous_tag(to_tag)
        if not from_tag:
            raise ValueError(f"Could not find predecessor for tag: {to_tag}")
        return from_tag, to_tag, base_ref

    # Handle --full-range (e.g., NBSM_2.9)
    if hasattr(args, 'full_range') and args.full_range:
        version_spec = args.full_range
        # Parse prefix_version format (e.g., NBSM_2.9 or NBSVRUP_3.0)
        match = re.match(r'^(NBSM|NBSVRUP)_([0-9]+\.[0-9]+)$', version_spec)
        if not match:
            raise ValueError(f"Invalid version format: {version_spec}. Expected: NBSM_X.Y or NBSVRUP_X.Y")

        prefix, version = match.groups()
        matching_tags = extractor.list_matching_tags(prefix=prefix, version=version)

        if not matching_tags:
            raise ValueError(f"No tags found for {version_spec}")

        # matching_tags is sorted by build number: [(tag, build_num), ...]
        from_tag = matching_tags[0][0]   # First tag (lowest build num)
        to_tag = matching_tags[-1][0]    # Last tag (highest build num)

        # Handle --auto-base: find last tag of previous version
        if hasattr(args, 'auto_base') and args.auto_base and not base_ref:
            # Parse current version to find previous
            major, minor = version.split('.')
            prev_version = None

            # Try previous minor version first (e.g., 2.8 -> 2.7)
            if int(minor) > 0:
                prev_version = f"{major}.{int(minor) - 1}"
            else:
                # Try previous major version last minor (e.g., 3.0 -> 2.x)
                prev_major = int(major) - 1
                if prev_major >= 0:
                    # Find highest minor version of previous major
                    all_tags = extractor.list_matching_tags(prefix=prefix)
                    prev_majors = [t for t, _ in all_tags if t.startswith(f"{prefix}_{prev_major}.")]
                    if prev_majors:
                        # Extract version from first matching tag
                        m = TAG_PATTERN.match(prev_majors[-1])
                        if m:
                            prev_version = m.group(2)

            if prev_version:
                prev_tags = extractor.list_matching_tags(prefix=prefix, version=prev_version)
                if prev_tags:
                    base_ref = prev_tags[-1][0]  # Last tag of previous version
                    print(f"Auto-detected base: {base_ref}")

        print(f"Resolved {version_spec} -> {from_tag} to {to_tag} ({len(matching_tags)} tags)")
        if base_ref:
            print(f"Using base ref: {base_ref} (for commits INTO {from_tag})")
        return from_tag, to_tag, base_ref

    if args.from_tag and args.to_tag:
        extractor.validate_ref(args.to_tag, 'to_tag')  # Validate to_tag exists
        extractor.validate_ref(args.from_tag, 'from_tag')  # Validate from_tag exists

        from_tag = args.from_tag
        to_tag = args.to_tag

        # Handle --auto-base: find predecessor of from_tag
        if hasattr(args, 'auto_base') and args.auto_base and not base_ref:
            # Parse from_tag to find prefix/version
            from_match = TAG_PATTERN.match(from_tag)
            if from_match:
                prefix, version, _ = from_match.groups()
                # Find last tag of previous version
                major, minor = version.split('.')
                prev_version = None

                if int(minor) > 0:
                    prev_version = f"{major}.{int(minor) - 1}"
                else:
                    prev_major = int(major) - 1
                    if prev_major >= 0:
                        all_tags = extractor.list_matching_tags(prefix=prefix)
                        prev_majors = [t for t, _ in all_tags if t.startswith(f"{prefix}_{prev_major}.")]
                        if prev_majors:
                            m = TAG_PATTERN.match(prev_majors[-1])
                            if m:
                                prev_version = m.group(2)

                if prev_version:
                    prev_tags = extractor.list_matching_tags(prefix=prefix, version=prev_version)
                    if prev_tags:
                        base_ref = prev_tags[-1][0]
                        print(f"Auto-detected base: {base_ref}")

        if base_ref:
            print(f"Using base ref: {base_ref} (for commits INTO {from_tag})")
        return from_tag, to_tag, base_ref

    if hasattr(args, 'commits') and args.commits:
        return None, None, None  # Will use commits mode

    if hasattr(args, 'since') and args.since:
        return None, None, None  # Will use since mode

    # Default: latest tag vs predecessor
    to_tag = extractor.get_latest_tag()
    if not to_tag:
        raise ValueError("No tags found in repository")
    from_tag = extractor.get_previous_tag(to_tag)
    if not from_tag:
        raise ValueError(f"Could not find predecessor for tag: {to_tag}")

    return from_tag, to_tag, base_ref


def main():
    """Main entry point."""
    args = parse_args()

    if not args.command or args.command == 'help':
        # Re-run with --help to show full help
        sys.argv = [sys.argv[0], '--help']
        parse_args()
        return

    # Set up repos
    repos = args.repos if hasattr(args, 'repos') and args.repos else [DEFAULT_REPO]

    # Validate environment
    if args.command in ['update', 'process', 'report', 'validate', 'validate-properties']:
        if not JIRA_API_TOKEN:
            print("Error: JIRA_ACC_TOKEN environment variable not set")
            sys.exit(1)

    try:
        # Initialize
        jira = JiraClient() if args.command in ['update', 'process', 'report', 'validate', 'validate-properties'] else None
        branch = args.branch if hasattr(args, 'branch') else 'origin/master'
        processor = ReleaseProcessor(repos, jira, branch=branch)

        # Always fetch the branch before any git operations
        validate_props_needs_git = (
            args.command == 'validate-properties' and
            bool(getattr(args, 'tag', None) or getattr(args, 'from_tag', None) or getattr(args, 'to_tag', None) or getattr(args, 'full_range', None))
        )
        if args.command != 'update' and (args.command != 'validate-properties' or validate_props_needs_git):
            processor.fetch_all()

        # =====================================================================
        # list-tags
        # =====================================================================
        if args.command == 'list-tags':
            extractor = processor.extractors[0]

            if args.from_tag and args.to_tag:
                tags = extractor.get_tags_in_range(args.from_tag, args.to_tag)
            else:
                matching = extractor.list_matching_tags(
                    prefix=args.prefix,
                    version=args.version
                )
                tags = [t[0] for t in matching]

            if tags:
                print(f"Found {len(tags)} tags:")
                for tag in tags:
                    print(f"  {tag}")
            else:
                print("No matching tags found.")

        # =====================================================================
        # extract-jiras
        # =====================================================================
        elif args.command == 'extract-jiras':
            extractor = processor.extractors[0]
            from_tag, to_tag, base_ref = resolve_tags(args, extractor)

            if hasattr(args, 'walk_range') and args.walk_range:
                jiras_by_tag = processor.walk_tag_range(from_tag, to_tag, base_ref)
            else:
                jiras = list(processor.extract_jiras_single(from_tag, to_tag).keys())
                jiras_by_tag = {to_tag: jiras}

            if args.format == 'json':
                print(json.dumps(jiras_by_tag, indent=2))
            else:
                for tag, jiras in jiras_by_tag.items():
                    print(f"\n{tag}:")
                    if jiras:
                        print(f"  {', '.join(jiras)}")
                    else:
                        print("  (no Jiras)")

                total = sum(len(j) for j in jiras_by_tag.values())
                print(f"\nTotal: {total} unique Jiras")

        # =====================================================================
        # report
        # =====================================================================
        elif args.command == 'report':
            extractor = processor.extractors[0]
            from_tag, to_tag, base_ref = resolve_tags(args, extractor)

            if hasattr(args, 'walk_range') and args.walk_range:
                jiras_by_tag = processor.walk_tag_range(from_tag, to_tag, base_ref)
            else:
                jiras = list(processor.extract_jiras_single(from_tag, to_tag).keys())
                jiras_by_tag = {to_tag: jiras}

            report = processor.generate_report(
                jiras_by_tag,
                output_format=args.format,
                fetch_details=not args.no_fetch
            )
            print(report)

        # =====================================================================
        # update (direct Jira update)
        # =====================================================================
        elif args.command == 'update':
            if not args.jiras:
                print("Error: No Jira IDs provided")
                sys.exit(1)

            has_direct_metadata_args = any([
                bool(args.labels),
                bool(args.assignee),
                bool(args.component),
                bool(args.watcher_group),
                bool(args.epic_link),
                bool(args.state if hasattr(args, 'state') else None)
            ])
            has_env_metadata_args = any([
                bool(args.labels_from_env) if hasattr(args, 'labels_from_env') else False,
                bool(args.legacy_default_labels) if hasattr(args, 'legacy_default_labels') else False,
                bool(args.metadata_from_env) if hasattr(args, 'metadata_from_env') else False
            ])

            if not args.build_id and not (has_direct_metadata_args or has_env_metadata_args):
                print("Error: --build-id is required unless metadata/state updates are requested")
                print("       Use options like --labels/--component/--assignee/--watcher-group/--epic-link/--state or --metadata-from-env")
                sys.exit(1)

            validate_jira_ids(args.jiras)
            jiras_by_tag = {args.build_id or '': args.jiras}
            processor.update_jiras(
                jiras_by_tag,
                labels=args.labels if args.labels else None,
                assignee=args.assignee,
                state=args.state if hasattr(args, 'state') else None,
                dry_run=args.dry_run,
                confirm=not args.no_confirm,
                project_key=args.project_key if hasattr(args, 'project_key') else None,
                component_name=args.component if hasattr(args, 'component') else None,
                watcher_groups=args.watcher_group if hasattr(args, 'watcher_group') and args.watcher_group else None,
                epic_key=args.epic_link if hasattr(args, 'epic_link') else None,
                watcher_group_field=args.watcher_group_field if hasattr(args, 'watcher_group_field') else 'Watcher Groups',
                labels_from_env=args.labels_from_env if hasattr(args, 'labels_from_env') else False,
                legacy_default_labels=args.legacy_default_labels if hasattr(args, 'legacy_default_labels') else False,
                metadata_from_env=args.metadata_from_env if hasattr(args, 'metadata_from_env') else False
            )

        # =====================================================================
        # process (full pipeline)
        # =====================================================================
        elif args.command == 'process':
            extractor = processor.extractors[0]
            from_tag, to_tag, base_ref = resolve_tags(args, extractor)

            print(f"{'='*60}")
            print("NBSM Release Tool - Process")
            print(f"{'='*60}")
            print(f"Repository: {repos[0]}")
            print(f"Tag range: {from_tag} -> {to_tag}")
            if base_ref:
                print(f"Base ref: {base_ref}")
            print(f"Walk range: {args.walk_range}")
            print()

            # Extract
            if hasattr(args, 'walk_range') and args.walk_range:
                jiras_by_tag = processor.walk_tag_range(from_tag, to_tag, base_ref)
            else:
                jiras = list(processor.extract_jiras_single(from_tag, to_tag).keys())
                jiras_by_tag = {to_tag: jiras}

            total = sum(len(j) for j in jiras_by_tag.values())
            print(f"Found {total} Jiras to process")

            if total == 0:
                print("No Jiras found. Exiting.")
                return

            # Report
            if not args.skip_report:
                print("\n" + processor.generate_report(jiras_by_tag, output_format='list'))

            # Determine labels to use with proper fallback
            final_labels = args.labels  # This comes from argparse
            labels_from_env = getattr(args, 'labels_from_env', False)
            legacy_default = getattr(args, 'legacy_default_labels', False)

            # If labels not explicitly provided, check other options
            if not final_labels:
                if labels_from_env or legacy_default:
                    # Will be handled in update_jiras via flags
                    final_labels = None
                else:
                    # Use default ['Verify'] for backward compatibility
                    final_labels = ['Verify']

            # Update
            processor.update_jiras(
                jiras_by_tag,
                labels=final_labels,
                assignee=getattr(args, 'assignee', None),
                state=getattr(args, 'state', None),
                dry_run=args.dry_run,
                confirm=not args.no_confirm,
                project_key=getattr(args, 'project_key', None),
                component_name=getattr(args, 'component', None),
                watcher_groups=getattr(args, 'watcher_group', None),
                epic_key=getattr(args, 'epic_link', None),
                watcher_group_field=getattr(args, 'watcher_group_field', 'Watcher Groups'),
                labels_from_env=labels_from_env,
                legacy_default_labels=legacy_default
            )

        # =====================================================================
        # validate
        # =====================================================================
        elif args.command == 'validate':
            extractor = processor.extractors[0]
            from_tag, to_tag, base_ref = resolve_tags(args, extractor)

            if hasattr(args, 'walk_range') and args.walk_range:
                jiras_by_tag = processor.walk_tag_range(from_tag, to_tag, base_ref)
            else:
                jiras = list(processor.extract_jiras_single(from_tag, to_tag).keys())
                jiras_by_tag = {to_tag: jiras}

            all_jiras = []
            for jiras in jiras_by_tag.values():
                all_jiras.extend(jiras)

            print(f"Validating {len(all_jiras)} Jiras...")

            issues = processor.get_issue_details(all_jiras)

            not_resolved = []
            for issue in issues:
                status = issue.get('fields', {}).get('status', {}).get('name', '')
                if status.lower() not in ['resolved', 'closed', 'done']:
                    not_resolved.append((issue.get('key'), status))

            if not_resolved:
                print(f"\n[!] {len(not_resolved)} Jiras not in Resolved/Closed status:")
                for key, status in not_resolved:
                    print(f"  {key}: {status}")

                if args.require_resolved:
                    print("\n[X] Validation FAILED")
                    sys.exit(1)
            else:
                print("[OK] All Jiras are in Resolved/Closed status")

        # =====================================================================
        # validate-properties
        # =====================================================================
        elif args.command == 'validate-properties':
            print(f"{'='*60}")
            print("VALIDATE PROPERTIES")
            print(f"{'='*60}")

            # Resolve Jira IDs either from positional keys or tag-range extraction.
            has_key_input = bool(args.keys)
            has_range_input = bool(getattr(args, 'tag', None) or getattr(args, 'from_tag', None) or getattr(args, 'to_tag', None) or getattr(args, 'full_range', None))

            if has_key_input and has_range_input:
                print("Error: Provide either Jira keys or tag range arguments, not both")
                sys.exit(1)

            if not has_key_input and not has_range_input:
                print("Error: Provide Jira keys or a tag range (--tag / --from+--to / --full-range)")
                sys.exit(1)

            if has_key_input:
                validate_jira_ids(args.keys)
                input_keys = args.keys
            else:
                extractor = processor.extractors[0]
                from_tag, to_tag, base_ref = resolve_tags(args, extractor)
                if args.walk_range:
                    jiras_by_tag = processor.walk_tag_range(from_tag, to_tag, base_ref)
                else:
                    jiras = list(processor.extract_jiras_single(from_tag, to_tag).keys())
                    jiras_by_tag = {to_tag: jiras}

                input_keys = []
                for jiras in jiras_by_tag.values():
                    input_keys.extend(jiras)

                if not input_keys:
                    print("No Jira IDs found for the selected range.")
                    return

                print(f"[*] Extracted {len(input_keys)} Jira reference(s) from range")

            # Detect and remove duplicates
            unique_keys = []
            seen = set()
            for key in input_keys:
                if key in seen:
                    print(f"[!] Duplicate key detected: {key} (skipping)")
                else:
                    unique_keys.append(key)
                    seen.add(key)

            # Validate final Jira ID list format
            validate_jira_ids(unique_keys)

            if not unique_keys:
                print("No unique keys to validate.")
                return

            print(f"[*] Validating {len(unique_keys)} unique issue(s)...")
            print()

            # Fetch and validate properties for each key
            all_results = []
            for jira_key in unique_keys:
                result = processor.jira.validate_issue_properties(jira_key, args.properties)
                all_results.append(result)

            def _is_issue_fully_validated(result_obj: Dict) -> bool:
                if not result_obj.get('success'):
                    return False
                props = result_obj.get('properties', {})
                if not props:
                    return False
                for prop_info in props.values():
                    if prop_info.get('error'):
                        return False
                    if not prop_info.get('is_set'):
                        return False
                return True

            validated_results = [r for r in all_results if _is_issue_fully_validated(r)]
            failed_results = [r for r in all_results if not _is_issue_fully_validated(r)]

            print(f"[*] Validated: {len(validated_results)}  Failed: {len(failed_results)}")
            print()

            # Output based on format
            if args.format == 'json':
                payload = {
                    'validated': validated_results,
                    'failed': failed_results,
                    'all_results': all_results
                }
                print(json.dumps(payload, indent=2))

            elif args.format == 'summary':
                print()
                print("VALIDATED ISSUES")
                print("-" * 60)
                if validated_results:
                    for result in validated_results:
                        print(f"[OK] {result['issue_key']}")
                else:
                    print("(none)")

                print("\nFAILED ISSUES")
                print("-" * 60)
                for result in failed_results:
                    if result['success']:
                        key = result['issue_key']
                        props = result['properties']
                        print(f"{key}:")
                        for prop_name, prop_info in props.items():
                            if prop_info.get('error'):
                                print(f"  [!] {prop_name}: ERROR - {prop_info.get('error')}")
                                continue
                            status = "[+]" if prop_info.get('is_set') else "[-]"
                            print(f"  {status} {prop_name}: {'SET' if prop_info.get('is_set') else 'NOT SET'}")
                    else:
                        print(f"{result['issue_key']}: ERROR - {result.get('error', 'Unknown error')}")
                    print()

            elif args.format == 'list':
                print()
                print("VALIDATED ISSUES")
                print("=" * 60)
                if validated_results:
                    for result in validated_results:
                        print(f"  [OK] {result['issue_key']}")
                else:
                    print("  (none)")

                print("\nFAILED ISSUES")
                print("=" * 60)
                for result in failed_results:
                    if result['success']:
                        key = result['issue_key']
                        props = result['properties']
                        print(f"{'='*60}")
                        print(f"Issue: {key}")
                        print(f"{'='*60}")

                        for prop_name, prop_info in props.items():
                            if prop_info.get('error'):
                                print(f"\n{prop_name.upper()} [!] ERROR")
                                print(f"  {prop_info.get('error')}")
                                continue

                            status = "[+] SET" if prop_info.get('is_set') else "[-] NOT SET"

                            if prop_name in ['labels', 'component', 'watcher_group']:
                                count = prop_info.get('count', 0)
                                value = prop_info.get('value', [])
                                print(f"\n{prop_name.upper()} ({count}) {status}")
                                if value:
                                    for item in value:
                                        print(f"  - {item}")
                            elif prop_name == 'assignee':
                                value = prop_info.get('value')
                                print(f"\n{prop_name.upper()} {status}")
                                if value:
                                    print(f"  {value}")
                            elif prop_name == 'epic_link':
                                value = prop_info.get('value')
                                print(f"\n{prop_name.upper()} {status}")
                                if value:
                                    print(f"  {value}")
                            elif prop_name == 'solution':
                                value = prop_info.get('value')
                                print(f"\n{prop_name.upper()} {status}")
                                if value:
                                    print(f"  {value}")
                        print()
                    else:
                        print(f"\n{result['issue_key']}: ERROR - {result.get('error', 'Unknown error')}")

            else:  # table format
                print()
                property_order = ['labels', 'component', 'assignee', 'solution', 'epic_link', 'watcher_group']

                def _build_rows(results: List[Dict]) -> List[List[str]]:
                    rows = []
                    for result in results:
                        if result.get('success'):
                            key = result.get('issue_key', '')
                            props = result.get('properties', {})

                            row_map = {'Issue': key}
                            for prop_name in property_order:
                                prop_info = props.get(prop_name, {})
                                if prop_info.get('error'):
                                    row_map[prop_name] = f"ERROR: {prop_info.get('error')}"
                                    continue

                                is_set = bool(prop_info.get('is_set'))
                                value = prop_info.get('value')

                                if isinstance(value, list):
                                    value_str = ', '.join(str(v) for v in value) if value else '-'
                                else:
                                    value_str = str(value) if value else '-'

                                row_map[prop_name] = value_str if is_set else 'NOT SET'

                            rows.append([
                                row_map['Issue'],
                                row_map['labels'],
                                row_map['component'],
                                row_map['assignee'],
                                row_map['solution'],
                                row_map['epic_link'],
                                row_map['watcher_group']
                            ])
                        else:
                            rows.append([
                                result.get('issue_key', ''),
                                'ERROR',
                                'ERROR',
                                'ERROR',
                                result.get('error', 'Unknown error'),
                                'ERROR',
                                'ERROR'
                            ])
                    return rows

                validated_rows = _build_rows(validated_results)
                failed_rows = _build_rows(failed_results)
                headers = ['Issue', 'labels', 'component', 'assignee', 'solution', 'epic_link', 'watcher_group']

                print("VALIDATED ISSUES")
                print("-" * 60)
                if validated_rows:
                    if HAS_TABULATE:
                        print(tabulate(validated_rows, headers=headers, tablefmt='grid'))
                    else:
                        print(' | '.join(headers))
                        print('-' * 120)
                        for row in validated_rows:
                            print(' | '.join(row))
                else:
                    print("(none)")

                print("\nFAILED ISSUES")
                print("-" * 60)
                if failed_rows:
                    if HAS_TABULATE:
                        print(tabulate(failed_rows, headers=headers, tablefmt='grid'))
                    else:
                        print(' | '.join(headers))
                        print('-' * 120)
                        for row in failed_rows:
                            print(' | '.join(row))
                else:
                    print("(none)")

        # =====================================================================
        # check-commits
        # =====================================================================
        elif args.command == 'check-commits':
            extractor = processor.extractors[0]
            from_tag, to_tag, _ = resolve_tags(args, extractor)

            bad_commits = extractor.get_commits_without_jira(from_tag, to_tag)

            if bad_commits:
                print(f"[!] Found {len(bad_commits)} commits without Jira IDs:")
                for commit in bad_commits:
                    print(f"  {commit}")
            else:
                print("[OK] All commits have Jira IDs")

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
