#!/usr/bin/env python3
"""
Jira Client - Interface for Jira API interactions
Based on existing Jira integration patterns
"""

import os
import requests
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv


class JiraClient:
    """
    Client for interacting with Jira API
    Uses environment variables for authentication
    """

    def __init__(self, jira_url: str = None, api_token: str = None):
        """
        Initialize Jira client

        Args:
            jira_url: Jira server URL (defaults to env JIRA_SERVER_NAME)
            api_token: API token (defaults to env JIRA_ACC_TOKEN)
        """
        # Load environment variables
        load_dotenv()

        # Setup Jira credentials
        server_name = jira_url or os.getenv('JIRA_SERVER_NAME')
        self.jira_url = f"https://{server_name}" if server_name else None
        self.api_token = api_token or os.getenv('JIRA_ACC_TOKEN')
        self.project_key = os.getenv('JIRA_PROJECT_KEY')

        if not self.jira_url or not self.api_token:
            raise ValueError("Jira URL and API token must be provided or set in environment")

        # Setup headers
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }

        self.timeout = 20  # Default timeout in seconds

    def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Get full issue details from Jira

        Args:
            issue_key: Jira issue key (e.g., 'FI-59131')

        Returns:
            Issue data dictionary or None if error
        """
        try:
            url = f"{self.jira_url}/rest/api/2/issue/{issue_key}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching issue {issue_key}: Status {response.status_code}, {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Request error fetching issue {issue_key}: {e}")
            return None

    def get_assignee(self, issue_key: str) -> Optional[str]:
        """
        Get assignee username for a Jira issue

        Args:
            issue_key: Jira issue key (e.g., 'FI-59131')

        Returns:
            Assignee username/name or None
        """
        issue_data = self.get_issue(issue_key)

        if not issue_data:
            return None

        try:
            assignee = issue_data.get('fields', {}).get('assignee')

            if assignee:
                # Return 'name' field (username)
                return assignee.get('name')

            return None

        except (KeyError, AttributeError) as e:
            print(f"Error parsing assignee for {issue_key}: {e}")
            return None

    def get_issue_summary(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Get summary information about an issue

        Args:
            issue_key: Jira issue key (e.g., 'FI-59131')

        Returns:
            Dictionary with key issue fields
        """
        issue_data = self.get_issue(issue_key)

        if not issue_data:
            return None

        try:
            fields = issue_data.get('fields', {})
            assignee = fields.get('assignee', {})
            status = fields.get('status', {})
            priority = fields.get('priority', {})

            return {
                'key': issue_data.get('key'),
                'summary': fields.get('summary'),
                'status': status.get('name'),
                'assignee': assignee.get('name') if assignee else None,
                'assignee_display_name': assignee.get('displayName') if assignee else None,
                'assignee_email': assignee.get('emailAddress') if assignee else None,
                'priority': priority.get('name') if priority else None,
                'created': fields.get('created'),
                'updated': fields.get('updated'),
                'description': fields.get('description'),
            }

        except (KeyError, AttributeError) as e:
            print(f"Error parsing issue summary for {issue_key}: {e}")
            return None

    def update_assignee(self, issue_key: str, assignee_name: str) -> bool:
        """
        Update assignee for a Jira issue

        Args:
            issue_key: Jira issue key (e.g., 'FI-59131')
            assignee_name: Username/name of new assignee

        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.jira_url}/rest/api/2/issue/{issue_key}/assignee"
            payload = {'name': assignee_name}

            response = requests.put(
                url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=self.timeout
            )

            if response.status_code == 204:
                print(f"+ Successfully updated assignee for {issue_key} to {assignee_name}")
                return True
            else:
                print(f"X Failed to update assignee for {issue_key}: Status {response.status_code}, {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"Request error updating assignee for {issue_key}: {e}")
            return False

    def get_multiple_assignees(self, issue_keys: List[str], batch_size: int = 50) -> Dict[str, Optional[str]]:
        """
        Get assignees for multiple issues efficiently using JQL batch search.

        This method uses Jira's search API to fetch multiple issues in a single
        request, dramatically reducing API calls from N to ceil(N/batch_size).

        Args:
            issue_keys: List of issue keys (e.g., ['FI-59131', 'FI-58985'])
            batch_size: Number of issues to fetch per API call (max 100, default 50)

        Returns:
            Dictionary mapping issue_key to assignee name (or None if unassigned/not found)
        """
        if not issue_keys:
            return {}

        # Initialize all keys with None (handles not found cases)
        assignees = {key: None for key in issue_keys}

        # Process in batches
        for i in range(0, len(issue_keys), batch_size):
            batch = issue_keys[i:i + batch_size]
            batch_result = self._fetch_assignees_batch(batch)
            assignees.update(batch_result)

        return assignees

    def _fetch_assignees_batch(self, issue_keys: List[str]) -> Dict[str, Optional[str]]:
        """
        Internal method to fetch assignees for a batch of issues using JQL.

        Args:
            issue_keys: List of issue keys (max ~50-100 for one request)

        Returns:
            Dictionary mapping issue_key to assignee name
        """
        if not issue_keys:
            return {}

        try:
            # Build JQL query: key in (FI-123, FI-456, ...)
            keys_str = ', '.join(issue_keys)
            jql = f'key in ({keys_str})'

            url = f"{self.jira_url}/rest/api/2/search"
            params = {
                'jql': jql,
                'maxResults': len(issue_keys),
                'fields': 'assignee'  # Only fetch assignee field for efficiency
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                results = {}

                for issue in data.get('issues', []):
                    key = issue.get('key')
                    assignee = issue.get('fields', {}).get('assignee')
                    # Return 'name' field (username) - consistent with get_assignee()
                    results[key] = assignee.get('name') if assignee else None

                return results
            else:
                # Fallback to individual requests on error
                print(f"Batch search failed (status {response.status_code}), falling back to individual requests")
                return {key: self.get_assignee(key) for key in issue_keys}

        except requests.exceptions.RequestException as e:
            print(f"Batch request error: {e}, falling back to individual requests")
            return {key: self.get_assignee(key) for key in issue_keys}

    def search_issues_by_assignee(self, assignee_name: str, max_results: int = 50) -> Optional[List[Dict[str, Any]]]:
        """
        Search for issues assigned to a specific user

        Args:
            assignee_name: Username to search for
            max_results: Maximum number of results to return

        Returns:
            List of issue summaries or None
        """
        try:
            url = f"{self.jira_url}/rest/api/2/search"
            params = {
                'jql': f'assignee = "{assignee_name}" AND project = {self.project_key}',
                'maxResults': max_results,
                'fields': 'summary,status,priority,created,updated'
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                return data.get('issues', [])
            else:
                print(f"Error searching issues: Status {response.status_code}, {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Request error searching issues: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test Jira connection and authentication

        Returns:
            True if connection successful, False otherwise
        """
        try:
            url = f"{self.jira_url}/rest/api/2/myself"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                user_data = response.json()
                print(f"+ Connected to Jira as: {user_data.get('displayName')} ({user_data.get('name')})")
                return True
            else:
                print(f"X Jira connection test failed: Status {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"X Jira connection test failed: {e}")
            return False

    def get_fi_details_batch(self, fi_ids: List[str], batch_size: int = 50) -> Dict[str, Dict[str, Any]]:
        """
        Get details for multiple FI IDs in batch using JQL search.

        This method uses Jira's search API to fetch multiple issues in a single
        request, dramatically reducing API calls.

        Args:
            fi_ids: List of FI IDs (e.g., ['FI-59131', 'FI-58985'])
            batch_size: Number of issues to fetch per API call (max 100, default 50)

        Returns:
            Dictionary mapping FI ID to its details
        """
        if not fi_ids:
            return {}

        results = {}

        # Process in batches
        for i in range(0, len(fi_ids), batch_size):
            batch = fi_ids[i:i + batch_size]
            batch_result = self._fetch_details_batch(batch)
            results.update(batch_result)

        return results

    def _fetch_details_batch(self, fi_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Internal method to fetch details for a batch of FIs using JQL.

        Args:
            fi_ids: List of FI IDs (max ~50-100 for one request)

        Returns:
            Dictionary mapping FI ID to its details
        """
        if not fi_ids:
            return {}

        try:
            # Build JQL query
            keys_str = ', '.join(fi_ids)
            jql = f'key in ({keys_str})'

            url = f"{self.jira_url}/rest/api/2/search"
            params = {
                'jql': jql,
                'maxResults': len(fi_ids),
                'fields': 'summary,status,priority,assignee,created,updated,description'
            }

            response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                results = {}

                for issue in data.get('issues', []):
                    key = issue.get('key')
                    fields = issue.get('fields', {})
                    assignee = fields.get('assignee', {})
                    status = fields.get('status', {})
                    priority = fields.get('priority', {})

                    results[key] = {
                        'key': key,
                        'summary': fields.get('summary'),
                        'status': status.get('name') if status else None,
                        'assignee': assignee.get('name') if assignee else None,
                        'assignee_display_name': assignee.get('displayName') if assignee else None,
                        'assignee_email': assignee.get('emailAddress') if assignee else None,
                        'priority': priority.get('name') if priority else None,
                        'created': fields.get('created'),
                        'updated': fields.get('updated'),
                        'description': fields.get('description'),
                    }

                # Mark missing FIs
                for fi_id in fi_ids:
                    if fi_id not in results:
                        results[fi_id] = {'error': 'Not found'}

                return results
            else:
                print(f"Batch details search failed (status {response.status_code})")
                return {fi_id: {'error': f'Batch failed: {response.status_code}'} for fi_id in fi_ids}

        except requests.exceptions.RequestException as e:
            print(f"Batch request error: {e}")
            return {fi_id: {'error': str(e)} for fi_id in fi_ids}

        return results

    def get_field_batch(self, issue_keys: List[str], field: str, batch_size: int = 50) -> Dict[str, Any]:
        """
        Get a specific field value for multiple issues in batch using JQL search.

        Args:
            issue_keys: List of issue keys (e.g., ['FI-59131', 'FI-58985'])
            field: Field name or ID to fetch (e.g., 'customfield_33802')
            batch_size: Number of issues to fetch per API call (max 100, default 50)

        Returns:
            Dictionary mapping issue_key to field value (or None if not found)
        """
        if not issue_keys:
            return {}

        results = {key: None for key in issue_keys}

        # Process in batches
        for i in range(0, len(issue_keys), batch_size):
            batch = issue_keys[i:i + batch_size]
            try:
                keys_str = ', '.join(batch)
                jql = f'key in ({keys_str})'

                url = f"{self.jira_url}/rest/api/2/search"
                params = {
                    'jql': jql,
                    'maxResults': len(batch),
                    'fields': field
                }

                response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)

                if response.status_code == 200:
                    data = response.json()
                    for issue in data.get('issues', []):
                        key = issue.get('key')
                        value = issue.get('fields', {}).get(field)
                        results[key] = value
                else:
                    print(f"Batch field search failed (status {response.status_code})")

            except requests.exceptions.RequestException as e:
                print(f"Batch request error: {e}")

        return results

    def search_users(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Search for JIRA users by name or email

        Uses Jira Server API v2 (same as j.getUserId.py)

        Args:
            query: Search query (username/name)
            max_results: Maximum number of results to return

        Returns:
            List of user dictionaries with accountId (key), displayName (name), emailAddress
        """
        # Use the same API as j.getUserId.py: /rest/api/2/user/search?username=
        url = f"{self.jira_url}/rest/api/2/user/search"
        params = {
            'username': query,
            'maxResults': max_results
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)

            if response.status_code == 200:
                try:
                    users = response.json()

                    if users and isinstance(users, list):
                        # Normalize to standard format matching j.getUserId.py fields:
                        # user['key'], user['name'], user.get('emailAddress')
                        return [
                            {
                                'accountId': u.get('key', ''),       # key is the JIRA account ID
                                'displayName': u.get('name', ''),    # name is the display name
                                'emailAddress': u.get('emailAddress', '')
                            }
                            for u in users
                        ]

                    return []

                except (json.JSONDecodeError, requests.exceptions.JSONDecodeError) as e:
                    print(f"Error decoding JSON: {e}")
                    return []
            else:
                print(f"Failed to retrieve user data for query '{query}': Status {response.status_code}")
                return []

        except requests.exceptions.RequestException as e:
            print(f"Error searching users: {e}")
            return []


class MockJiraClient:
    """
    Mock Jira client for testing without actual Jira connection
    """

    def __init__(self, mock_data: Dict[str, str] = None):
        """
        Initialize mock client

        Args:
            mock_data: Dictionary mapping FI-ID to assignee username
        """
        self.mock_data = mock_data or {}

    def get_assignee(self, issue_key: str) -> Optional[str]:
        """Get mock assignee"""
        return self.mock_data.get(issue_key)

    def add_mock_assignee(self, fi_id: str, assignee: str):
        """Add mock assignee data"""
        self.mock_data[fi_id] = assignee

    def get_issue_summary(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Get mock issue summary"""
        if issue_key in self.mock_data:
            return {
                'key': issue_key,
                'assignee': self.mock_data[issue_key],
                'summary': f'Mock issue {issue_key}',
                'status': 'Open'
            }
        return None

    def test_connection(self) -> bool:
        """Mock connection test"""
        print("+ Using Mock Jira Client (no actual connection)")
        return True

    def search_users(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Mock user search - returns sample data"""
        # Return mock users based on query
        mock_users = [
            {
                'accountId': 'mock_account_123',
                'displayName': query,
                'emailAddress': f'{query.lower().replace(" ", ".")}@cohesity.com'
            }
        ]
        return mock_users

    def update_assignee(self, issue_key: str, assignee_name: str) -> bool:
        """Mock update assignee"""
        print(f"  [MOCK] Would update {issue_key} assignee to {assignee_name}")
        self.mock_data[issue_key] = assignee_name
        return True

    def get_multiple_assignees(self, issue_keys: List[str], batch_size: int = 50) -> Dict[str, Optional[str]]:
        """Mock batch assignee fetch"""
        return {key: self.mock_data.get(key) for key in issue_keys}
