#!/usr/bin/env python3
"""
NBSM Release Tool - Unified CLI for release management

Extract Jira IDs from git tags, generate reports, and update Jira tickets with build information.

QUICK START:
    # Full release workflow (recommended)
    python3 nbsm_release_tool.py process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range

    # Dry run first
    python3 nbsm_release_tool.py process --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --dry-run

COMMANDS:
    list-tags       List available tags in repository
    extract-jiras   Extract Jira IDs from git commits
    report          Generate detailed Jira report
    update          Update specific Jira tickets directly
    process         Full pipeline: extract → report → confirm → update (RECOMMENDED)
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

For detailed help with examples:
    python3 nbsm_release_tool.py --help
    python3 nbsm_release_tool.py <command> --help
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
    
    def __init__(self, repo_path: str):
        self.repo_path = os.path.expanduser(repo_path)
        if not os.path.isdir(self.repo_path):
            raise ValueError(f"Repository not found: {self.repo_path}")
    
    def _run_git(self, *args) -> str:
        """Run a git command and return output."""
        cmd = ['git', '-C', self.repo_path] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Git command failed: {result.stderr}")
        return result.stdout.strip()
    
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
    
    def __init__(self, repos: List[str], jira_client: JiraClient = None):
        self.extractors = [GitExtractor(repo) for repo in repos]
        self.jira = jira_client or JiraClient()
    
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
    
    def walk_tag_range(self, from_tag: str, to_tag: str) -> OrderedDict:
        """Walk through tag range and extract Jiras for each step.
        
        If a Jira appears in multiple tag ranges, it is assigned to the
        HIGHEST (latest) build number.
        
        Returns:
            OrderedDict: {to_tag: [jira_ids]} for each tag pair
        """
        # Get tags in range from first extractor
        tags = self.extractors[0].get_tags_in_range(from_tag, to_tag)
        
        if len(tags) < 2:
            raise ValueError(f"Need at least 2 tags in range, found: {tags}")
        
        # Track Jira -> latest tag mapping (higher tag wins)
        jira_to_tag: Dict[str, str] = {}
        
        for i in range(len(tags) - 1):
            tag_from = tags[i]
            tag_to = tags[i + 1]
            
            jira_repos = self.extract_jiras_single(tag_from, tag_to)
            
            # Update mapping - later tags overwrite earlier ones
            for jira in jira_repos.keys():
                jira_to_tag[jira] = tag_to
        
        # Invert mapping: tag -> list of Jiras
        result = OrderedDict()
        for tag in tags[1:]:  # Skip the from_tag, only include to_tags
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
            format: 'table', 'json', 'csv', 'markdown'
            fetch_details: Whether to fetch Jira details from API
        """
        if format == 'json':
            return json.dumps(jiras_by_tag, indent=2)
        
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
                            (fields.get('summary', '')[:60] + '...') 
                                if len(fields.get('summary', '')) > 60 
                                else fields.get('summary', ''),
                            fields.get('status', {}).get('name', ''),
                            fields.get('assignee', {}).get('displayName', 'Unassigned') 
                                if fields.get('assignee') else 'Unassigned',
                            fields.get('priority', {}).get('name', ''),
                        ])
                        all_jiras.append({'key': issue.get('key'), 'tag': tag, **fields})
                    
                    lines.append(tabulate(
                        rows,
                        headers=['Key', 'Summary', 'Status', 'Assignee', 'Priority'],
                        tablefmt='simple'
                    ))
                elif format == 'markdown':
                    for issue in details:
                        fields = issue.get('fields', {})
                        lines.append(f"- **{issue.get('key')}**: {fields.get('summary', '')}")
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
                     dry_run: bool = False, confirm: bool = True) -> Dict:
        """Update Jiras with build IDs, labels, and assignee.
        
        Args:
            jiras_by_tag: Dict mapping build_id (tag) to list of Jira IDs
            labels: Labels to add (e.g., ['Verify'])
            assignee: Assignee username
            dry_run: If True, only show what would be done
            confirm: If True, prompt for confirmation
        
        Returns:
            Dict with success/failure counts
        """
        total = sum(len(jiras) for jiras in jiras_by_tag.values())
        
        if total == 0:
            print("No Jiras to update.")
            return {'total': 0, 'success': 0, 'failed': 0}
        
        # Show what will be done
        print(f"\n{'='*60}")
        print("UPDATE PREVIEW")
        print(f"{'='*60}")
        print(f"Total Jiras to update: {total}")
        print(f"Labels to add: {', '.join(labels) if labels else '(none)'}")
        print(f"Assignee: {assignee or '(unchanged)'}")
        print()
        
        for tag, jiras in jiras_by_tag.items():
            if jiras:
                print(f"  {tag}: {', '.join(jiras)}")
        
        if dry_run:
            print("\n[DRY RUN] No changes made.")
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
                
                if result['success']:
                    success_count += 1
                    status = []
                    if result['build']:
                        status.append('build')
                    if result['labels']:
                        status.append('labels')
                    if result['assignee']:
                        status.append('assignee')
                    print(f"  ✓ Updated: {', '.join(status)}")
                else:
                    failed_count += 1
                    print("  ✗ Failed")
        
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

EXTRACT-JIRAS - Extract Jira IDs from git
-----------------------------------------
  # Single tag pair (auto-detect predecessor)
  %(prog)s extract-jiras --tag NBSM_2.9_0010

  # Explicit tag range (single comparison)
  %(prog)s extract-jiras --from NBSM_2.9_0009 --to NBSM_2.9_0010

  # Walk entire range (process all intermediate tags)
  %(prog)s extract-jiras --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range

  # Use commit hash as start (when first tag has no predecessor)
  %(prog)s extract-jiras --from abc1234 --to NBSM_2.9_0001
  %(prog)s extract-jiras --from abc1234 --to NBSM_2.9_0005 --walk-range

  # Output as JSON
  %(prog)s extract-jiras --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --format json

  # Use latest tag (auto-detect)
  %(prog)s extract-jiras

REPORT - Generate Jira report
-----------------------------
  # Table format (default) with Jira details
  %(prog)s report --from NBSM_2.9_0009 --to NBSM_2.9_0010

  # Walk range and show all builds
  %(prog)s report --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range

  # Markdown format (for release notes)
  %(prog)s report --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --format markdown

  # JSON format
  %(prog)s report --from NBSM_2.9_0001 --to NBSM_2.9_0010 --format json

  # Skip fetching Jira details (just show IDs)
  %(prog)s report --from NBSM_2.9_0009 --to NBSM_2.9_0010 --no-fetch

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

VALIDATE - Pre-release validation
---------------------------------
  # Check if all Jiras are Resolved/Closed
  %(prog)s validate --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range

  # Fail exit code if any Jira not resolved
  %(prog)s validate --from NBSM_2.9_0001 --to NBSM_2.9_0010 --walk-range --require-resolved

CHECK-COMMITS - Find commits without Jira IDs
----------------------------------------------
  # Find bad commits (missing NBU-xxxxx)
  %(prog)s check-commits --from NBSM_2.9_0001 --to NBSM_2.9_0010

  # Check latest tag
  %(prog)s check-commits --tag NBSM_2.9_0010

================================================================================
TAG RANGE WALK EXPLAINED
================================================================================

When using --walk-range with --from NBSM_2.9_0001 --to NBSM_2.9_0010:

  The tool processes each consecutive tag pair:
    NBSM_2.9_0001 → NBSM_2.9_0002: Jiras updated with build NBSM_2.9_0002
    NBSM_2.9_0002 → NBSM_2.9_0003: Jiras updated with build NBSM_2.9_0003
    ...
    NBSM_2.9_0009 → NBSM_2.9_0010: Jiras updated with build NBSM_2.9_0010

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
    
    def add_range_args(p):
        p.add_argument('--tag', help='Single tag (compare with predecessor)')
        p.add_argument('--from', dest='from_tag', help='Starting tag')
        p.add_argument('--to', dest='to_tag', help='Ending tag')
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
    p_report.add_argument('--format', choices=['table', 'json', 'csv', 'markdown'],
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


def resolve_tags(args, extractor: GitExtractor) -> Tuple[str, str]:
    """Resolve from_tag and to_tag from arguments."""
    if args.tag:
        to_tag = args.tag
        from_tag = extractor.get_previous_tag(to_tag)
        if not from_tag:
            raise ValueError(f"Could not find predecessor for tag: {to_tag}")
        return from_tag, to_tag
    
    if args.from_tag and args.to_tag:
        return args.from_tag, args.to_tag
    
    if hasattr(args, 'commits') and args.commits:
        return None, None  # Will use commits mode
    
    if hasattr(args, 'since') and args.since:
        return None, None  # Will use since mode
    
    # Default: latest tag vs predecessor
    to_tag = extractor.get_latest_tag()
    if not to_tag:
        raise ValueError("No tags found in repository")
    from_tag = extractor.get_previous_tag(to_tag)
    if not from_tag:
        raise ValueError(f"Could not find predecessor for tag: {to_tag}")
    
    return from_tag, to_tag


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
        processor = ReleaseProcessor(repos, jira)
        
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
            from_tag, to_tag = resolve_tags(args, extractor)
            
            if hasattr(args, 'walk_range') and args.walk_range:
                jiras_by_tag = processor.walk_tag_range(from_tag, to_tag)
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
            from_tag, to_tag = resolve_tags(args, extractor)
            
            if hasattr(args, 'walk_range') and args.walk_range:
                jiras_by_tag = processor.walk_tag_range(from_tag, to_tag)
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
            from_tag, to_tag = resolve_tags(args, extractor)
            
            print(f"{'='*60}")
            print("NBSM Release Tool - Process")
            print(f"{'='*60}")
            print(f"Repository: {repos[0]}")
            print(f"Tag range: {from_tag} → {to_tag}")
            print(f"Walk range: {args.walk_range}")
            print()
            
            # Extract
            if hasattr(args, 'walk_range') and args.walk_range:
                jiras_by_tag = processor.walk_tag_range(from_tag, to_tag)
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
                dry_run=args.dry_run,
                confirm=not args.no_confirm
            )
        
        # =====================================================================
        # validate
        # =====================================================================
        elif args.command == 'validate':
            extractor = processor.extractors[0]
            from_tag, to_tag = resolve_tags(args, extractor)
            
            if hasattr(args, 'walk_range') and args.walk_range:
                jiras_by_tag = processor.walk_tag_range(from_tag, to_tag)
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
                print(f"\n⚠ {len(not_resolved)} Jiras not in Resolved/Closed status:")
                for key, status in not_resolved:
                    print(f"  {key}: {status}")
                
                if args.require_resolved:
                    print("\n✗ Validation FAILED")
                    sys.exit(1)
            else:
                print("✓ All Jiras are in Resolved/Closed status")
        
        # =====================================================================
        # check-commits
        # =====================================================================
        elif args.command == 'check-commits':
            extractor = processor.extractors[0]
            from_tag, to_tag = resolve_tags(args, extractor)
            
            bad_commits = extractor.get_commits_without_jira(from_tag, to_tag)
            
            if bad_commits:
                print(f"⚠ Found {len(bad_commits)} commits without Jira IDs:")
                for commit in bad_commits:
                    print(f"  {commit}")
            else:
                print("✓ All commits have Jira IDs")
    
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
