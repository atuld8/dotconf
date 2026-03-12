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
import argparse
import subprocess
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


# =============================================================================
# JIRA CLIENT
# =============================================================================

class JiraClient:
    """Handles all Jira API interactions."""

    def __init__(self, url: str = JIRA_URL, token: str = JIRA_API_TOKEN):
        self.url = url.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        self._field_cache: Optional[Dict[str, Dict]] = None

    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None,
                 timeout: int = 30) -> requests.Response:
        """Make an API request."""
        if not HAS_REQUESTS:
            raise RuntimeError("requests library not installed. Run: pip install requests")

        url = f"{self.url}/rest/api/2/{endpoint}"
        response = requests.request(
            method, url, headers=self.headers,
            json=data, timeout=timeout
        )
        return response

    def get_all_fields(self) -> Dict[str, Dict]:
        """Fetch all Jira fields and cache the mapping."""
        if self._field_cache is not None:
            return self._field_cache

        response = self._request('GET', 'field')
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

    def get_issue(self, issue_key: str) -> Dict:
        """Get issue details."""
        response = self._request('GET', f'issue/{issue_key}')
        response.raise_for_status()
        return response.json()

    def get_issues(self, issue_keys: List[str]) -> List[Dict]:
        """Get multiple issues."""
        issues = []
        for key in issue_keys:
            try:
                issues.append(self.get_issue(key))
            except Exception as e:
                print(f"  Warning: Failed to fetch {key}: {e}")
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

    def update_issue(self, issue_key: str, build_id: str, labels: List[str] = None,
                     assignee: str = None, solution_field: str = "Solution") -> Dict:
        """Update an issue with build info, labels, and assignee.

        Returns:
            Dict with 'success', 'build', 'labels', 'assignee' status
        """
        result = {'success': True, 'build': False, 'labels': False, 'assignee': False}

        # Update Solution field with build ID
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

        return result


# =============================================================================
# GIT EXTRACTOR
# =============================================================================

class GitExtractor:
    """Handles git operations for extracting tags and Jira IDs."""

    DEFAULT_BRANCH = 'origin/master'

    def __init__(self, repo_path: str, branch: str = None):
        self.repo_path = os.path.expanduser(repo_path)
        self.branch = branch or self.DEFAULT_BRANCH
        if not os.path.isdir(self.repo_path):
            raise ValueError(f"Repository not found: {self.repo_path}")

    def _run_git(self, *args) -> str:
        """Run a git command and return output."""
        cmd = ['git', '-C', self.repo_path] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Git command failed: {result.stderr}")
        return result.stdout.strip()

    def fetch_branch(self) -> None:
        """Fetch the configured branch from remote before any operations.

        This ensures we have the latest commits and tags from the remote.
        """
        # Parse remote and branch from the full ref (e.g., 'origin/master' -> 'origin', 'master')
        if '/' in self.branch:
            remote, branch_name = self.branch.split('/', 1)
        else:
            remote = 'origin'
            branch_name = self.branch

        print(f"Fetching {remote}/{branch_name} from repository...")
        try:
            # Fetch the specific branch and tags
            self._run_git('fetch', remote, branch_name, '--tags')
            print(f"Fetch complete: {remote}/{branch_name}")
        except RuntimeError as e:
            print(f"Warning: Failed to fetch {remote}/{branch_name}: {e}")
            print("Continuing with local data...")

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
        """Fetch details for multiple Jira issues."""
        return self.jira.get_issues(jira_ids)

    def generate_report(self, jiras_by_tag: Dict[str, List[str]],
                        format: str = 'table', fetch_details: bool = True) -> str:
        """Generate a report of Jiras by tag.

        Args:
            jiras_by_tag: Dict mapping tag to list of Jira IDs
            format: 'table', 'json', 'csv', 'markdown', 'club'
            fetch_details: Whether to fetch Jira details from API
        """
        # For JSON, CSV and club with details, we need to collect all data first
        if format in ('json', 'csv', 'club') and fetch_details:
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

            if format == 'json':
                return json.dumps(all_data, indent=2)
            elif format == 'csv':
                lines = ['Build,Key,Summary,Status,Assignee,Priority']
                for row in all_data:
                    # Escape quotes in summary
                    summary = row['summary'].replace('"', '""')
                    lines.append(f'"{row["build"]}","{row["key"]}","{summary}","{row["status"]}","{row["assignee"]}","{row["priority"]}"')
                return '\n'.join(lines)
            elif format == 'club':
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
                        tablefmt='simple'
                    )
                else:
                    lines = []
                    for row in all_data:
                        lines.append(f"{row['build']}  {row['key']}  {row['type']}  {row['status']}  {row['assignee']}  {row['priority']}  {row['summary'][:80]}")
                    return '\n'.join(lines)

        if format == 'json':
            return json.dumps(jiras_by_tag, indent=2)

        # CSV without details - simple format
        if format == 'csv':
            lines = ['Build,Key']
            for tag, jiras in jiras_by_tag.items():
                for jira in jiras:
                    lines.append(f'"{tag}","{jira}"')
            return '\n'.join(lines)

        # Club without details - simple table
        if format == 'club':
            rows = []
            for tag, jiras in jiras_by_tag.items():
                for jira in jiras:
                    rows.append([tag, jira])
            if HAS_TABULATE:
                return tabulate(rows, headers=['Build', 'Key'], tablefmt='simple')
            else:
                lines = []
                for row in rows:
                    lines.append(f"{row[0]}  {row[1]}")
                return '\n'.join(lines)

        lines = []
        all_jiras = []

        for tag, jiras in jiras_by_tag.items():
            lines.append(f"\n{'='*60}")
            lines.append(f"Build: {tag}")
            lines.append(f"{'='*60}")

            if not jiras:
                lines.append("  (no new Jiras)")
                continue

            if fetch_details:
                details = self.get_issue_details(jiras)

                if format == 'table' and HAS_TABULATE:
                    rows = []
                    for issue in details:
                        fields = issue.get('fields', {})
                        rows.append([
                            issue.get('key', ''),
                            (fields.get('summary', '')[:80] + '...')
                                if len(fields.get('summary', '')) > 80
                                else fields.get('summary', ''),
                            fields.get('issuetype', {}).get('name', ''),
                            fields.get('status', {}).get('name', ''),
                            fields.get('assignee', {}).get('displayName', 'Unassigned')
                                if fields.get('assignee') else 'Unassigned',
                            fields.get('priority', {}).get('name', ''),
                        ])
                        all_jiras.append({'key': issue.get('key'), 'tag': tag, **fields})

                    lines.append(tabulate(
                        rows,
                        headers=['Key', 'Summary', 'Type', 'Status', 'Assignee', 'Priority'],
                        tablefmt='simple'
                    ))
                elif format == 'markdown':
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
                     confirm: bool = True) -> Dict:
        """Update Jiras with build IDs, labels, assignee, and state transitions.

        Args:
            jiras_by_tag: Dict mapping build_id (tag) to list of Jira IDs
            labels: Labels to add (e.g., ['Verify'])
            assignee: Assignee username
            state: Target state (e.g., 'Done')
            dry_run: If True, only show what would be done
            confirm: If True, prompt for confirmation

        Returns:
            Dict with success/failure counts
        """
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
            issues = self.jira.get_issues(all_jira_ids)
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
        print(f"Labels to add: {', '.join(labels) if labels else '(none)'}")
        print(f"Assignee: {assignee or '(unchanged)'}")
        print(f"State transition: {state or '(none)'}")
        print()

        for tag, jiras in jiras_by_tag.items():
            if jiras:
                print(f"  {tag}: {', '.join(jiras)}")

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
                print(f"\nUpdating {jira_id} with build {tag}...")
                result = self.jira.update_issue(
                    jira_id,
                    build_id=tag,
                    labels=labels,
                    assignee=assignee
                )

                status = []
                if result['success']:
                    if result['build']:
                        status.append('build')
                    if result['labels']:
                        status.append('labels')
                    if result['assignee']:
                        status.append('assignee')

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
  # Table format (default) with Jira details
  %(prog)s report --from NBSM_2.9_0009 --to NBSM_2.9_0010

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

  # Add multiple labels
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --labels Verify,Reviewed

  # Update with assignee
  %(prog)s update NBU-12345 --build-id NBSM_2.9_0010 --labels Verify --assignee john.doe

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
        p.add_argument('--repo', action='append', dest='repos',
                       help=f'Repository path (default: {DEFAULT_REPO})')
        p.add_argument('--branch', default='origin/master',
                       help='Git branch to fetch before operations (default: origin/master)')

    def add_range_args(p):
        p.add_argument('--tag', help='Single tag (compare with predecessor)')
        p.add_argument('--from', dest='from_tag', help='Starting tag')
        p.add_argument('--to', dest='to_tag', help='Ending tag')
        p.add_argument('--full-range', dest='full_range',
                       help='Version series (e.g., NBSM_2.9) - auto-resolve first to latest tag')
        p.add_argument('--base', dest='base_ref',
                       help='Base commit/tag for first build (what went INTO first tag)')
        p.add_argument('--auto-base', action='store_true',
                       help='Auto-detect base from previous version (e.g., last tag of NBSM_2.7 for NBSM_2.8)')
        p.add_argument('--walk-range', action='store_true',
                       help='Process all intermediate tags in range')
        p.add_argument('--commits', type=int, help='Last N commits instead of tags')
        p.add_argument('--since', help='Commits since date (YYYY-MM-DD)')

    # list-tags
    p_tags = subparsers.add_parser('list-tags',
        help='List available tags',
        description='List NBSM/NBSVRUP tags from the repository, optionally filtered by version or range.')
    add_common_args(p_tags)
    p_tags.add_argument('--version', help='Filter by version (e.g., 2.9)')
    p_tags.add_argument('--prefix', help='Filter by prefix (NBSM or NBSVRUP)')
    p_tags.add_argument('--from', dest='from_tag', help='Starting tag for range')
    p_tags.add_argument('--to', dest='to_tag', help='Ending tag for range')

    # extract-jiras
    p_extract = subparsers.add_parser('extract-jiras',
        help='Extract Jira IDs from git',
        description='Extract NBU-xxxxx Jira IDs from git commit messages between tags.')
    add_common_args(p_extract)
    add_range_args(p_extract)
    p_extract.add_argument('--format', choices=['list', 'json'], default='list',
                           help='Output format (default: list)')

    # report
    p_report = subparsers.add_parser('report',
        help='Generate Jira report',
        description='Generate a report showing Jira details for tickets found in git history.')
    add_common_args(p_report)
    add_range_args(p_report)
    p_report.add_argument('--format', choices=['table', 'json', 'csv', 'markdown', 'club'],
                          default='table', help='Output format (default: table)')
    p_report.add_argument('--no-fetch', action='store_true',
                          help='Skip fetching Jira details (just show IDs)')

    # update
    p_update = subparsers.add_parser('update',
        help='Update Jira tickets',
        description='Directly update specified Jira tickets with build ID, labels, and assignee.')
    p_update.add_argument('jiras', nargs='*', help='Jira IDs to update (e.g., NBU-12345 NBU-12346)')
    p_update.add_argument('--build-id', required=True,
                          help='Build ID for Solution field (e.g., NBSM_2.9_0010)')
    p_update.add_argument('--labels', type=lambda s: s.split(','), default=[],
                          help='Comma-separated labels to add (e.g., Verify,Reviewed)')
    p_update.add_argument('--assignee', help='Assignee username')
    p_update.add_argument('--state', choices=['Done'],
                          help='Transition issues to state (e.g., Done). Handles multi-step transitions.')
    p_update.add_argument('--dry-run', action='store_true',
                          help='Preview changes without applying')
    p_update.add_argument('--no-confirm', action='store_true',
                          help='Skip confirmation prompt (use with caution)')

    # process (full pipeline)
    p_process = subparsers.add_parser('process',
        help='Full pipeline: extract, report, update',
        description='''Full release pipeline: extract Jiras from git tags, generate report,
and update Jira tickets with build ID and labels. This is the recommended command for release workflows.''')
    add_common_args(p_process)
    add_range_args(p_process)
    p_process.add_argument('--labels', type=lambda s: s.split(','), default=['Verify'],
                           help='Labels to add (default: Verify)')
    p_process.add_argument('--assignee', help='Assignee username')
    p_process.add_argument('--state', choices=['Done'],
                           help='Transition issues to state (e.g., Done). Handles multi-step transitions.')
    p_process.add_argument('--dry-run', action='store_true',
                           help='Preview changes without applying')
    p_process.add_argument('--no-confirm', action='store_true',
                           help='Skip confirmation prompt (use with caution)')
    p_process.add_argument('--skip-report', action='store_true',
                           help='Skip report generation (faster)')

    # validate
    p_validate = subparsers.add_parser('validate',
        help='Validate Jiras before release',
        description='Pre-release validation: check that all Jiras are in Resolved/Closed status.')
    add_common_args(p_validate)
    add_range_args(p_validate)
    p_validate.add_argument('--require-resolved', action='store_true',
                            help='Exit with error code if any Jira is not Resolved/Closed')

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
    if args.command in ['update', 'process', 'report', 'validate']:
        if not JIRA_API_TOKEN:
            print("Error: JIRA_ACC_TOKEN environment variable not set")
            sys.exit(1)

    try:
        # Initialize
        jira = JiraClient() if args.command in ['update', 'process', 'report', 'validate'] else None
        branch = args.branch if hasattr(args, 'branch') else 'origin/master'
        processor = ReleaseProcessor(repos, jira, branch=branch)

        # Always fetch the branch before any git operations
        if args.command != 'update':  # update doesn't need git operations
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
                format=args.format,
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

            validate_jira_ids(args.jiras)
            jiras_by_tag = {args.build_id: args.jiras}
            processor.update_jiras(
                jiras_by_tag,
                labels=args.labels,
                assignee=args.assignee,
                dry_run=args.dry_run,
                confirm=not args.no_confirm
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
                print("\n" + processor.generate_report(jiras_by_tag, format='table'))

            # Update
            processor.update_jiras(
                jiras_by_tag,
                labels=args.labels,
                assignee=args.assignee,
                state=args.state,
                dry_run=args.dry_run,
                confirm=not args.no_confirm
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
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
